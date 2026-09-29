r"""Loads and runs the event-risk classifier trained by
scripts/train_event_classifier.py, reading its plain-JSON artifact
(app/ai/models/event_risk_classifier.json) directly -- no scikit-learn, no
pickle, no executable model format at inference time, matching the source
packs' own "no pickle" rule for on-disk model artifacts.

Reimplements scikit-learn's default TfidfVectorizer transform (lowercase,
\b\w\w+\b word tokens, unigrams+bigrams, smooth IDF, L2-normalized) and a
logistic-regression forward pass by hand so the artifact is portable to any
Python process without the training dependency.

See the artifact's own "model_card" key, and
docs/ML_EVENT_CLASSIFIER.md, for what this does and does not do -- most
importantly: it was trained on Windows Event Log text (positive) vs.
non-Windows text (negative), so treat it as weak and confounded with log
format, not a validated malice detector, until it's evaluated against real
benign Windows Event Log data at scale.
"""
import json
import math
import os
import re
import threading

_MODEL_PATH = os.path.join(os.path.dirname(os.path.abspath(__file__)), "models", "event_risk_classifier.json")
_TOKEN_RE = re.compile(r"\b\w\w+\b")

_lock = threading.Lock()
_artifact = None


def _load():
    global _artifact
    if _artifact is not None:
        return _artifact
    with _lock:
        if _artifact is None:
            if not os.path.exists(_MODEL_PATH):
                _artifact = False
                return _artifact
            with open(_MODEL_PATH, encoding="utf-8") as f:
                _artifact = json.load(f)
    return _artifact


def is_available() -> bool:
    return bool(_load())


def _tokenize(text: str):
    return _TOKEN_RE.findall(text.lower())


def _ngrams(tokens):
    grams = list(tokens)
    grams.extend(f"{tokens[i]} {tokens[i + 1]}" for i in range(len(tokens) - 1))
    return grams


def _tfidf_vector(text: str, vocabulary: dict, idf: list) -> dict:
    """Term -> tf*idf for terms present in `vocabulary`, L2-normalized --
    matches sklearn TfidfVectorizer(norm='l2', smooth_idf=True) exactly for
    the same vocabulary/idf it was fit with."""
    tokens = _tokenize(text)
    grams = _ngrams(tokens)
    counts = {}
    for g in grams:
        idx = vocabulary.get(g)
        if idx is not None:
            counts[idx] = counts.get(idx, 0) + 1
    if not counts:
        return {}
    weighted = {idx: count * idf[idx] for idx, count in counts.items()}
    norm = math.sqrt(sum(w * w for w in weighted.values())) or 1.0
    return {idx: w / norm for idx, w in weighted.items()}


def score(text: str):
    """Returns {"probability_malicious", "label", "abstained", "model_version"}
    or None if the model artifact isn't present. `label` is "malicious",
    "benign", or "abstain" (probability inside the model card's abstention
    band -- reported as uncertain rather than forced into a class)."""
    artifact = _load()
    if not artifact or not text:
        return None

    vec_cfg = artifact["vectorizer"]
    clf_cfg = artifact["classifier"]
    vector = _tfidf_vector(text, vec_cfg["vocabulary"], vec_cfg["idf"])
    coef = clf_cfg["coef"]
    z = clf_cfg["intercept"] + sum(coef[idx] * w for idx, w in vector.items())
    try:
        probability = 1.0 / (1.0 + math.exp(-z))
    except OverflowError:
        probability = 0.0 if z < 0 else 1.0

    low, high = artifact["model_card"]["abstention_threshold"]
    if low <= probability <= high:
        label = "abstain"
    else:
        label = "malicious" if probability >= 0.5 else "benign"

    return {
        "probability_malicious": probability,
        "label": label,
        "abstained": label == "abstain",
        "model_version": artifact["model_card"]["trained_at"],
    }
