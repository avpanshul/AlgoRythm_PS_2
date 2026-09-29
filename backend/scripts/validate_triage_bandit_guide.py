r"""Offline validation of `app/ai/triage_bandit.py` (E7b) against Microsoft's
real GUIDE dataset (Kaggle: Microsoft/microsoft-security-incident-prediction,
CDLA-Permissive-2.0, arXiv:2407.09017 / arXiv:2607.16963).

This does NOT rerank ULPF's own live queue -- see the docstring in
app/ai/triage_bandit.py and docs/E7B_OFFLINE_VALIDATION.md for why that
still, correctly, needs ULPF's own real analyst history via E6. This script
answers a narrower, honest question: "does the LinUCB algorithm itself learn
a sensible triage policy from real incident features and real ground
truth?" -- using someone else's real SOC data, not this project's invented
data.

Two real evaluations, both against real Microsoft data:

1. **General accuracy/escalation** -- a random 1-in-N sample of real
   incidents (keyed on a hash of (OrgId, IncidentId) so every kept
   incident's full evidence set stays intact, never split) from
   GUIDE_Train.csv and GUIDE_Test.csv. Sampled rather than exhaustive
   because the full files are ~9.5M / ~4.1M evidence rows and this sandbox
   had ~2GB of free RAM at the time this was written -- documented here,
   not silently done.
2. **Ranking quality** -- a *targeted* (non-sampled) extraction of the
   exact incidents referenced in GUIDE_Test_Queue_Rankings.csv (the
   arXiv:2607.16963 queue-ranking extension: 499 org queues, real
   human-expert-ranked top-20 incidents each), compared via nDCG against
   the bandit's own learned priority ordering for those same incidents.

Run: `python scripts/validate_triage_bandit_guide.py --data-dir <path to the
folder containing GUIDE_Train.csv, GUIDE_Test.csv, GUIDE_Test_Queue_Rankings.csv>`
"""
import argparse
import os
import sys

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
from app.ai.triage_bandit import LinUCBTriageBandit, ARMS

CATEGORIES = [
    "Collection", "CommandAndControl", "CredentialAccess", "CredentialStealing",
    "DefenseEvasion", "Discovery", "Execution", "Exfiltration", "Exploit",
    "Impact", "InitialAccess", "LateralMovement", "Malware", "Persistence",
    "PrivilegeEscalation", "Ransomware", "SuspiciousActivity", "UnwantedSoftware",
    "Weaponization", "WebExploit",
]  # the real, complete set of values observed in GUIDE_Train.csv's Category column
SUSPICION_LEVELS = ["Suspicious", "Incriminated"]
VERDICTS = ["Malicious", "Suspicious", "NoThreatsFound"]

USECOLS = [
    "OrgId", "IncidentId", "AlertId", "DetectorId", "Category", "EntityType",
    "SuspicionLevel", "LastVerdict", "MitreTechniques", "IncidentGrade", "Timestamp",
]

# Target severity tier a "correctly behaving" bandit should learn to assign,
# derived from GUIDE's own 3-valued ground truth. BenignPositive ("real
# activity, confirmed non-malicious") is mapped to "medium" rather than
# "low", distinct from FalsePositive ("the detection itself was wrong") --
# an honest, stated modeling choice, not an artifact of the data.
TARGET_ARM = {"TruePositive": "critical", "BenignPositive": "medium", "FalsePositive": "low"}
_TIER_RANK = {"low": 0, "medium": 1, "high": 2, "critical": 3}


def _keep_mask(chunk: pd.DataFrame, sample_mod: int) -> pd.Series:
    """Deterministic hash on (OrgId, IncidentId) -- every evidence row of a
    kept incident is kept, none are split across the sample boundary."""
    key = chunk["OrgId"].astype("int64") * 1000003 + chunk["IncidentId"].astype("int64")
    return (key % sample_mod) == 0


def load_sampled(path: str, sample_mod: int, chunksize: int = 300_000) -> pd.DataFrame:
    kept = []
    total_rows = 0
    for chunk in pd.read_csv(path, usecols=USECOLS, chunksize=chunksize):
        total_rows += len(chunk)
        kept.append(chunk[_keep_mask(chunk, sample_mod)])
    df = pd.concat(kept, ignore_index=True) if kept else pd.DataFrame(columns=USECOLS)
    print(f"  scanned {total_rows:,} real evidence rows from {os.path.basename(path)}, "
          f"kept {len(df):,} ({len(df) / max(total_rows, 1):.1%}, 1-in-{sample_mod} incident sample)")
    return df


def load_targeted(path: str, pairs: set, chunksize: int = 300_000) -> pd.DataFrame:
    """Keeps only rows whose (OrgId, IncidentId) is in `pairs` -- an exact
    extraction, not a sample, used for the queue-ranking comparison so every
    ranked incident's real evidence is present."""
    kept = []
    total_rows = 0
    for chunk in pd.read_csv(path, usecols=USECOLS, chunksize=chunksize):
        total_rows += len(chunk)
        mask = list(zip(chunk["OrgId"], chunk["IncidentId"]))
        keep = pd.Series([p in pairs for p in mask], index=chunk.index)
        kept.append(chunk[keep])
    df = pd.concat(kept, ignore_index=True) if kept else pd.DataFrame(columns=USECOLS)
    print(f"  scanned {total_rows:,} real evidence rows from {os.path.basename(path)}, "
          f"found {len(df):,} rows for {len(pairs):,} targeted real incidents")
    return df


def aggregate_to_incidents(df: pd.DataFrame) -> pd.DataFrame:
    """One row per real (OrgId, IncidentId), with fixed-vocabulary features
    built only from fields genuinely available at triage time (no fields
    derived from the resolution itself)."""
    if df.empty:
        return pd.DataFrame()

    df = df.copy()
    df["has_mitre"] = df["MitreTechniques"].notna().astype(int)
    df["Timestamp"] = pd.to_datetime(df["Timestamp"], errors="coerce", utc=True)
    for cat in CATEGORIES:
        df[f"cat_{cat}"] = (df["Category"] == cat).astype(int)
    for lvl in SUSPICION_LEVELS:
        df[f"susp_{lvl}"] = (df["SuspicionLevel"] == lvl).astype(int)
    for v in VERDICTS:
        df[f"verdict_{v}"] = (df["LastVerdict"] == v).astype(int)
    # Hard, deterministic signal for the safety-override kill switch --
    # never the bandit's own learned opinion, a real fact already present
    # in the evidence (at least one row is a confirmed-malicious verdict or
    # an incriminated suspicion level).
    df["hard_signal_row"] = ((df["LastVerdict"] == "Malicious") | (df["SuspicionLevel"] == "Incriminated")).astype(int)

    agg = df.groupby(["OrgId", "IncidentId"]).agg(
        evidence_count=("AlertId", "size"),
        alert_count=("AlertId", "nunique"),
        detector_count=("DetectorId", "nunique"),
        entity_type_count=("EntityType", "nunique"),
        has_mitre_count=("has_mitre", "sum"),
        hard_signal=("hard_signal_row", "max"),
        first_seen=("Timestamp", "min"),
        last_seen=("Timestamp", "max"),
        label=("IncidentGrade", "first"),
        **{f"cat_{c}": (f"cat_{c}", "sum") for c in CATEGORIES},
        **{f"susp_{s}": (f"susp_{s}", "sum") for s in SUSPICION_LEVELS},
        **{f"verdict_{v}": (f"verdict_{v}", "sum") for v in VERDICTS},
    ).reset_index()

    # Recency/history features: how long this incident's evidence spans,
    # and how fast evidence arrived -- a burst of many pieces of evidence in
    # a short window looks different from the same count spread over days.
    duration_seconds = (agg["last_seen"] - agg["first_seen"]).dt.total_seconds().clip(lower=0).fillna(0)
    agg["duration_seconds"] = duration_seconds
    agg["evidence_rate"] = agg["evidence_count"] / (duration_seconds / 3600.0 + 1.0)  # evidence per hour

    agg = agg[agg["label"].isin(TARGET_ARM.keys())]  # drop the small fraction with no real label
    return agg


FEATURE_COLS = (
    ["evidence_count", "alert_count", "detector_count", "entity_type_count",
     "has_mitre_count", "duration_seconds", "evidence_rate"]
    + [f"cat_{c}" for c in CATEGORIES]
    + [f"susp_{s}" for s in SUSPICION_LEVELS]
    + [f"verdict_{v}" for v in VERDICTS]
)


def to_context_matrix(agg: pd.DataFrame) -> np.ndarray:
    """Bias term + log1p-scaled counts, log1p-scaled since evidence/alert
    counts are heavily right-skewed in real incident data (most incidents
    have 1-3 pieces of evidence, a few have hundreds)."""
    raw = agg[FEATURE_COLS].to_numpy(dtype=float)
    scaled = np.log1p(raw)
    bias = np.ones((len(agg), 1))
    return np.hstack([bias, scaled])


def reward_for_choice(chosen_arm: str, target_arm: str, asymmetry: float = 1.0) -> float:
    """Partial credit by tier distance on the 4-tier scale. `asymmetry` > 1
    penalizes under-escalating more than over-escalating (a SOC risk
    preference). Two earlier real runs (see docs/E7B_OFFLINE_VALIDATION.md)
    showed asymmetry alone is a blunt instrument: 1.0 (symmetric) left the
    bandit ignoring the minority "should escalate" class (8.6% true-positive
    recall); 2.0 fixed that but collapsed false-positive deprioritization to
    under 1%. This run keeps the reward symmetric (asymmetry=1.0, the
    honest default) and instead rebalances class imbalance via `weight` in
    `LinUCBTriageBandit.update` -- see `class_weight_for` below -- so the
    *magnitude of what's learned* is rebalanced, not the *reward signal
    itself* being distorted."""
    signed_dist = _TIER_RANK[target_arm] - _TIER_RANK[chosen_arm]  # >0 = under-escalated
    penalty = (signed_dist * asymmetry if signed_dist > 0 else -signed_dist) / (3.0 * max(asymmetry, 1.0))
    return 1.0 - penalty


def class_weights(labels: list) -> dict:
    """Inverse-frequency importance weights, normalized so the average
    weight across the training set is 1.0 (keeps the bandit's overall
    learning rate comparable to the unweighted case, only rebalancing which
    classes it learns *faster* from)."""
    counts = pd.Series(labels).value_counts()
    n, k = len(labels), len(counts)
    raw = {label: n / (k * count) for label, count in counts.items()}
    return raw


def train(bandit: LinUCBTriageBandit, contexts: np.ndarray, labels: list, weights: dict = None) -> None:
    for x, label in zip(contexts, labels):
        target = TARGET_ARM[label]
        chosen = bandit.select_arm(x)
        reward = reward_for_choice(chosen, target)
        w = weights[label] if weights else 1.0
        bandit.update(x, chosen, reward, weight=w)  # only the chosen arm's model is updated -- genuine bandit feedback


def heuristic_baseline_arm(row) -> str:
    """A simple, non-learned, deterministic rule -- the honest comparison
    point a real deployment would ask "is the learned bandit even better
    than a few if-statements?" against. Not a stand-in for ULPF's own
    Sentinel score (GUIDE has no such field; that would be a real domain
    mismatch to fabricate), just a plain severity heuristic built from the
    same real GUIDE fields the bandit sees."""
    if row["hard_signal"]:
        return "critical"
    if row["has_mitre_count"] > 0 or row["susp_Suspicious"] > 0:
        return "high"
    if row["verdict_NoThreatsFound"] > 0:
        return "low"
    return "medium"


def evaluate(bandit: LinUCBTriageBandit, agg: pd.DataFrame, use_safety_override: bool = False) -> dict:
    contexts = to_context_matrix(agg)
    labels = agg["label"].tolist()
    hard_signals = agg["hard_signal"].tolist()
    n = len(labels)
    exact_match = 0
    rewards = []
    tp_escalated = tp_total = 0
    fp_deprioritized = fp_total = 0
    priority_scores = []
    for x, label, hard_signal in zip(contexts, labels, hard_signals):
        target = TARGET_ARM[label]
        if use_safety_override:
            chosen = bandit.select_arm_with_safety_override(x, hard_signal=bool(hard_signal))
        else:
            chosen = bandit.select_arm(x)
        rewards.append(reward_for_choice(chosen, target))
        exact_match += int(chosen == target)
        priority_scores.append(bandit.priority_score(x))
        if label == "TruePositive":
            tp_total += 1
            tp_escalated += int(chosen in ("high", "critical"))
        if label == "FalsePositive":
            fp_total += 1
            fp_deprioritized += int(chosen == "low")

    # Precision@10%: of the top 10% of incidents by the bandit's own
    # priority score, what fraction are real confirmed true positives --
    # the operationally relevant question ("if an analyst only has time for
    # the top of the queue, how much of it is real?").
    k = max(1, n // 10)
    top_k_idx = np.argsort(priority_scores)[::-1][:k]
    top_k_labels = [labels[i] for i in top_k_idx]
    precision_at_k = sum(1 for l in top_k_labels if l == "TruePositive") / k

    return {
        "n": n,
        "exact_tier_match_rate": exact_match / n if n else None,
        "mean_partial_credit_reward": float(np.mean(rewards)) if rewards else None,
        "true_positive_escalation_recall": tp_escalated / tp_total if tp_total else None,
        "false_positive_deprioritization_rate": fp_deprioritized / fp_total if fp_total else None,
        f"precision_at_top_{k}": precision_at_k,
        "true_positive_count": tp_total,
        "false_positive_count": fp_total,
    }


def evaluate_heuristic_baseline(agg: pd.DataFrame) -> dict:
    """The same metrics computed for `heuristic_baseline_arm` instead of the
    bandit -- the "did the learned model even beat a few if-statements?"
    comparison."""
    tp_escalated = tp_total = 0
    fp_deprioritized = fp_total = 0
    exact_match = 0
    for _, row in agg.iterrows():
        target = TARGET_ARM[row["label"]]
        chosen = heuristic_baseline_arm(row)
        exact_match += int(chosen == target)
        if row["label"] == "TruePositive":
            tp_total += 1
            tp_escalated += int(chosen in ("high", "critical"))
        if row["label"] == "FalsePositive":
            fp_total += 1
            fp_deprioritized += int(chosen == "low")
    n = len(agg)
    return {
        "n": n,
        "exact_tier_match_rate": exact_match / n if n else None,
        "true_positive_escalation_recall": tp_escalated / tp_total if tp_total else None,
        "false_positive_deprioritization_rate": fp_deprioritized / fp_total if fp_total else None,
    }


def dcg_at_k(relevances: list, k: int) -> float:
    return sum(rel / np.log2(i + 2) for i, rel in enumerate(relevances[:k]))


def evaluate_ranking(bandit: LinUCBTriageBandit, agg: pd.DataFrame, rankings_path: str) -> dict:
    rankings = pd.read_csv(rankings_path)
    contexts = to_context_matrix(agg)
    agg = agg.reset_index(drop=True)
    agg["priority_score"] = [bandit.priority_score(x) for x in contexts]

    ndcgs = []
    for org_id, org_rank in rankings.groupby("OrgId"):
        org_incidents = agg[agg["OrgId"] == org_id]
        if org_incidents.empty:
            continue
        merged = org_rank.merge(org_incidents[["IncidentId", "priority_score"]], on="IncidentId", how="inner")
        if len(merged) < 2:
            continue
        # Real expert relevance: rank 1 (most urgent) -> highest relevance.
        max_rank = merged["QueueRank"].max()
        merged["true_relevance"] = max_rank - merged["QueueRank"] + 1
        ideal = sorted(merged["true_relevance"], reverse=True)
        predicted_order = merged.sort_values("priority_score", ascending=False)["true_relevance"].tolist()
        idcg = dcg_at_k(ideal, 10)
        if idcg == 0:
            continue
        ndcgs.append(dcg_at_k(predicted_order, 10) / idcg)

    return {
        "orgs_with_overlap": len(ndcgs),
        "orgs_in_rankings_file": rankings["OrgId"].nunique(),
        "mean_ndcg_at_10": float(np.mean(ndcgs)) if ndcgs else None,
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data-dir", required=True, help="Folder with GUIDE_Train.csv, GUIDE_Test.csv, GUIDE_Test_Queue_Rankings.csv")
    parser.add_argument("--sample-mod", type=int, default=20, help="Keep 1-in-N real incidents for the general accuracy evaluation")
    args = parser.parse_args()

    train_path = os.path.join(args.data_dir, "GUIDE_Train.csv")
    test_path = os.path.join(args.data_dir, "GUIDE_Test.csv")
    rankings_path = os.path.join(args.data_dir, "GUIDE_Test_Queue_Rankings.csv")
    for p in (train_path, test_path, rankings_path):
        if not os.path.isfile(p):
            print(f"FAIL: expected real GUIDE file not found: {p}")
            sys.exit(1)

    out_dir = os.path.join(os.path.dirname(__file__), "..", "data", "guide_validation")
    os.makedirs(out_dir, exist_ok=True)

    print(f"=== Loading a real 1-in-{args.sample_mod} incident sample from GUIDE_Train.csv ===")
    train_df = aggregate_to_incidents(load_sampled(train_path, args.sample_mod))
    print(f"  {len(train_df):,} real training incidents after aggregation")
    train_df.to_csv(os.path.join(out_dir, "train_incidents_sample.csv"), index=False)

    print(f"=== Loading a real 1-in-{args.sample_mod} incident sample from GUIDE_Test.csv ===")
    test_df = aggregate_to_incidents(load_sampled(test_path, args.sample_mod))
    print(f"  {len(test_df):,} real test incidents after aggregation")
    test_df.to_csv(os.path.join(out_dir, "test_incidents_sample.csv"), index=False)

    weights = class_weights(train_df["label"].tolist())
    print(f"  real class weights (inverse-frequency, normalized): {weights}")

    print("=== Training LinUCB bandit on real training incidents (bandit feedback only, class-weighted) ===")
    bandit = LinUCBTriageBandit(n_features=len(FEATURE_COLS) + 1, alpha=1.0)
    train(bandit, to_context_matrix(train_df), train_df["label"].tolist(), weights=weights)

    print("=== Evaluating on held-out real test incidents (bandit, no safety override) ===")
    metrics = evaluate(bandit, test_df, use_safety_override=False)
    for k, v in metrics.items():
        print(f"  {k}: {v}")

    print("=== Evaluating on held-out real test incidents (bandit + safety-override kill switch) ===")
    metrics_safe = evaluate(bandit, test_df, use_safety_override=True)
    for k, v in metrics_safe.items():
        print(f"  {k}: {v}")

    print("=== Baseline: simple deterministic heuristic (no learning) ===")
    baseline_metrics = evaluate_heuristic_baseline(test_df)
    for k, v in baseline_metrics.items():
        print(f"  {k}: {v}")

    print("=== Targeted extraction for real expert queue-ranking comparison ===")
    rankings = pd.read_csv(rankings_path)
    pairs = set(zip(rankings["OrgId"], rankings["IncidentId"]))
    ranking_df = aggregate_to_incidents(load_targeted(test_path, pairs))
    print(f"  {len(ranking_df):,} of {len(pairs):,} real ranked incidents found with real evidence in GUIDE_Test.csv")
    ranking_metrics = evaluate_ranking(bandit, ranking_df, rankings_path)
    for k, v in ranking_metrics.items():
        print(f"  {k}: {v}")

    print("\n=== DONE (all numbers above are real, computed from this run -- not fabricated) ===")


if __name__ == "__main__":
    main()
