r"""Trains a binary "attack-technique-related vs. benign" event classifier on
real data only -- no synthetic/generated log lines anywhere in the training
or test set.

Positive class (label=1, malicious/attack-related): datasets/real/evtx_corpus.jsonl
-- sbousseaden/EVTX-ATTACK-SAMPLES (MIT), where every record's `mitre_tactic`
field is a genuine MITRE ATT&CK tactic assigned by that dataset's own
per-technique file naming (see build_evtx_corpus.py), not a label we invented.

Negative class (label=0, benign): datasets/real/corpus.jsonl (logpai/loghub
real system/application logs) plus the non-`ZEEK-NOTICE` Zeek corpora
(DHCP/SSL/APPSTATS/DPD/FTP/IRC -- routine protocol telemetry, not
security-flagged records). `ZEEK-NOTICE` and the CloudTrail corpus are
deliberately excluded from training: both come from contexts (a "notable
event" engine, and an attack-simulation account) where we cannot honestly
assert every individual record is benign, and mislabeling real data would
violate the project's no-fabrication standard as much as inventing data
would.

Classes are balanced by downsampling the larger one (fixed random seed) so
accuracy isn't a trivial majority-class artifact.

Output: backend/app/ai/models/event_risk_classifier.json -- a plain JSON
artifact (vocabulary, IDF weights, logistic-regression coefficients,
threshold, and metrics/model card), no pickle -- decoded by
app/ai/event_classifier.py without needing scikit-learn at inference time.

Usage: python scripts/train_event_classifier.py
"""
import json
import os
import random
import re

import numpy as np
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split, cross_val_score, StratifiedKFold
from sklearn.metrics import (
    accuracy_score, precision_score, recall_score, f1_score,
    roc_auc_score, confusion_matrix, classification_report,
)

SEED = 42
random.seed(SEED)
np.random.seed(SEED)

DATASET_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "datasets", "real")
MODEL_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "app", "ai", "models")
MODEL_PATH = os.path.join(MODEL_DIR, "event_risk_classifier.json")


def _load_jsonl(path):
    with open(path, encoding="utf-8") as f:
        return [json.loads(line) for line in f if line.strip()]


def build_dataset():
    evtx = _load_jsonl(os.path.join(DATASET_DIR, "evtx_corpus.jsonl"))
    loghub = _load_jsonl(os.path.join(DATASET_DIR, "corpus.jsonl"))
    zeek = _load_jsonl(os.path.join(DATASET_DIR, "zeek_corpus.jsonl"))

    positives = [r["raw"] for r in evtx]
    benign_zeek = [r["raw"] for r in zeek if r.get("source_id") != "ZEEK-NOTICE"]
    negatives_pool = [r["raw"] for r in loghub] + benign_zeek

    rng = random.Random(SEED)
    n = min(len(positives), len(negatives_pool))
    positives = rng.sample(positives, n) if len(positives) > n else positives
    negatives = rng.sample(negatives_pool, n) if len(negatives_pool) > n else negatives_pool

    texts = positives + negatives
    labels = [1] * len(positives) + [0] * len(negatives)
    print(f"Dataset: {len(positives)} malicious (real, MITRE-tagged EVTX-ATTACK-SAMPLES), "
          f"{len(negatives)} benign (real loghub + non-notice Zeek), balanced from a pool of "
          f"{len(negatives_pool)} candidate benign records.")
    return texts, labels


def _tokenizer(text: str):
    return re.findall(r"\b\w\w+\b", text.lower())


def train_and_evaluate(texts, labels, max_features, C):
    X_train_text, X_test_text, y_train, y_test = train_test_split(
        texts, labels, test_size=0.2, random_state=SEED, stratify=labels
    )

    vectorizer = TfidfVectorizer(
        tokenizer=_tokenizer, token_pattern=None, ngram_range=(1, 2),
        max_features=max_features, min_df=2,
    )
    X_train = vectorizer.fit_transform(X_train_text)
    X_test = vectorizer.transform(X_test_text)

    clf = LogisticRegression(C=C, max_iter=2000, class_weight="balanced", random_state=SEED)
    clf.fit(X_train, y_train)

    train_pred = clf.predict(X_train)
    test_pred = clf.predict(X_test)
    test_proba = clf.predict_proba(X_test)[:, 1]

    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=SEED)
    cv_scores = cross_val_score(clf, X_train, y_train, cv=cv, scoring="f1")

    metrics = {
        "train_accuracy": accuracy_score(y_train, train_pred),
        "test_accuracy": accuracy_score(y_test, test_pred),
        "test_precision": precision_score(y_test, test_pred),
        "test_recall": recall_score(y_test, test_pred),
        "test_f1": f1_score(y_test, test_pred),
        "test_roc_auc": roc_auc_score(y_test, test_proba),
        "cv_f1_mean": float(cv_scores.mean()),
        "cv_f1_std": float(cv_scores.std()),
        "overfit_gap": accuracy_score(y_train, train_pred) - accuracy_score(y_test, test_pred),
        "confusion_matrix": confusion_matrix(y_test, test_pred).tolist(),
        "n_train": len(y_train),
        "n_test": len(y_test),
    }
    return vectorizer, clf, metrics, classification_report(y_test, test_pred, target_names=["benign", "malicious"])


def main():
    texts, labels = build_dataset()

    # Small grid search over regularization strength and vocabulary size --
    # picks the configuration with the best cross-validated F1 that also
    # keeps the train/test accuracy gap small (an overfit model with great
    # training numbers is not "better" for this purpose).
    grid = [
        {"max_features": 3000, "C": 0.1},
        {"max_features": 3000, "C": 1.0},
        {"max_features": 5000, "C": 1.0},
        {"max_features": 5000, "C": 5.0},
        {"max_features": 8000, "C": 1.0},
    ]

    results = []
    for params in grid:
        vectorizer, clf, metrics, report = train_and_evaluate(texts, labels, **params)
        results.append((params, vectorizer, clf, metrics, report))
        print(f"\n=== max_features={params['max_features']} C={params['C']} ===")
        print(f"train_acc={metrics['train_accuracy']:.4f} test_acc={metrics['test_accuracy']:.4f} "
              f"overfit_gap={metrics['overfit_gap']:.4f}")
        print(f"test_precision={metrics['test_precision']:.4f} test_recall={metrics['test_recall']:.4f} "
              f"test_f1={metrics['test_f1']:.4f} test_roc_auc={metrics['test_roc_auc']:.4f}")
        print(f"cv_f1={metrics['cv_f1_mean']:.4f} +/- {metrics['cv_f1_std']:.4f}")
        print(f"confusion_matrix={metrics['confusion_matrix']}")

    # Selection rule, decided up front rather than cherry-picked after seeing
    # numbers: reject any config with overfit_gap > 0.05, then take the
    # highest cv_f1_mean among what's left.
    acceptable = [r for r in results if r[3]["overfit_gap"] <= 0.05]
    pool = acceptable if acceptable else results
    best = max(pool, key=lambda r: r[3]["cv_f1_mean"])
    params, vectorizer, clf, metrics, report = best

    print(f"\n=== SELECTED: max_features={params['max_features']} C={params['C']} ===")
    print(report)

    if metrics["test_f1"] < 0.90 or metrics["overfit_gap"] > 0.08:
        print("\nWARNING: selected model does not meet the target bar "
              "(test_f1 >= 0.90, overfit_gap <= 0.08). Inspect the grid results above; "
              "consider adding more real negative data or features before shipping this.")

    # Export as a plain JSON artifact -- vocabulary + IDF + LR weights --
    # decodable by app/ai/event_classifier.py without scikit-learn.
    feature_names = vectorizer.get_feature_names_out().tolist()
    idf = vectorizer.idf_.tolist()
    coef = clf.coef_[0].tolist()
    intercept = float(clf.intercept_[0])

    os.makedirs(MODEL_DIR, exist_ok=True)
    artifact = {
        "model_card": {
            "task": "Binary classification: is this raw log line drawn from a known "
                    "MITRE ATT&CK-tagged attack-technique sample, or from routine "
                    "system/network telemetry.",
            "training_data": {
                "positive_class": "sbousseaden/EVTX-ATTACK-SAMPLES (MIT) -- real Windows "
                                   "Event Log records, MITRE-tactic-tagged by that dataset's "
                                   "own per-technique file organization.",
                "negative_class": "logpai/loghub real system logs + non-ZEEK-NOTICE Zeek "
                                   "protocol telemetry (real IDS engine output, routine "
                                   "traffic categories only).",
                "n_positive": sum(1 for l in labels if l == 1),
                "n_negative": sum(1 for l in labels if l == 0),
                "synthetic_data_used": False,
            },
            "limitations": [
                "Trained on Windows Event Log (positive) vs. Linux/network telemetry "
                "(negative) text -- format/source differs between classes as well as "
                "malicious intent, so this may partly be a 'is this a Windows Event Log' "
                "detector rather than a pure malice detector. Treat its output as a weak, "
                "abstaining signal alongside the existing rule-based risk score, not a "
                "replacement for it.",
                "Not evaluated against benign Windows Event Logs (no real, large, "
                "confirmed-benign Windows Event Log corpus was available at training time) "
                "-- a genuine false-positive-rate gap for that specific case.",
                "Bag-of-words/TF-IDF features only; will not catch attacks whose log text "
                "looks lexically ordinary.",
                "Retrain if the vocabulary drifts (new vendor formats onboarded) -- coverage "
                "is only as good as the training corpora above.",
            ],
            "abstention_threshold": [0.4, 0.6],
            "abstention_policy": "Predicted probabilities inside this band are reported as "
                                  "'abstain', not forced into a class -- the classifier says "
                                  "so when it isn't confident rather than guessing.",
            "trained_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
            "selected_params": params,
            "status": "experimental_not_integrated",
            "status_reason": "Verified confounded with log format rather than malice: scores "
                              "a real, documented-benign Windows Firewall Event ID 5157 record "
                              "at >99% probability-malicious, purely because it is Windows Event "
                              "Log XML in the same shape as every positive training example. "
                              "The positive-class corpus's own EventID distribution (5145, a "
                              "routine share-access-check audit event, is its single most common "
                              "code) further shows the label is applied per attack-capture "
                              "session, not verified per event -- ordinary noise inside an attack "
                              "capture is mislabeled positive. Not wired into app/core/processing.py "
                              "or any API/UI surface. See docs/ML_EVENT_CLASSIFIER.md for the full "
                              "investigation and what would actually be needed to fix this.",
        },
        "metrics": metrics,
        "vectorizer": {
            "tokenizer": "lowercase, \\b\\w\\w+\\b word tokens, unigrams+bigrams",
            "vocabulary": {term: i for i, term in enumerate(feature_names)},
            "idf": idf,
        },
        "classifier": {
            "type": "logistic_regression",
            "coef": coef,
            "intercept": intercept,
        },
    }
    with open(MODEL_PATH, "w", encoding="utf-8") as f:
        json.dump(artifact, f)
    print(f"\nWrote model artifact to {MODEL_PATH}")


if __name__ == "__main__":
    main()
