r"""Contextual-bandit incident triage prioritization (ULPF-phase2-prompt.md
E7b, "human-in-the-loop RL triage").

Arms are ULPF's own severity tiers -- the same four this project already
uses everywhere else (`low`/`medium`/`high`/`critical`, see E6's `Case.severity`
and `notifications/engine.py`'s `_SEVERITY_ACTION`) -- so the bandit's output
plugs directly into the existing case/notification pipeline rather than
inventing a fifth taxonomy.

Algorithm: LinUCB (Li et al., 2010) -- a standard, well-understood linear
contextual bandit, not a black box. For each arm it keeps a ridge-regression
posterior over the reward-vs-context relationship and picks the arm with the
highest upper confidence bound, balancing exploiting what it has learned
against exploring arms it is still uncertain about. This is deliberately a
simple, auditable algorithm: an analyst (or this project) can inspect
`A`/`b` per arm and see exactly what it has learned, unlike a deep RL policy.

Two honestly separate lifecycles for this module:

1. **Offline validation** (`backend/scripts/validate_triage_bandit_guide.py`):
   fits and scores this exact class against Microsoft's real GUIDE dataset
   (real customer-SOC TP/FP/BP ground truth) to prove the *algorithm* can
   learn a sensible triage policy from real incident features before it is
   ever pointed at a live queue. See docs/E7B_OFFLINE_VALIDATION.md for the
   real numbers that run produced.
2. **Production use** (not wired up yet, and correctly so): reranking
   ULPF's *own* live incident queue needs ULPF's *own* analysts' real
   ack/resolve decisions (via E6) as the reward signal. That history does
   not exist yet in this environment -- inventing it would be exactly the
   fabrication this project's standing rule forbids. GUIDE validates the
   algorithm; it is not a substitute for this system's own usage data, and
   using another SOC's decisions to rank this system's queue would be a real
   domain mismatch, not a shortcut.
"""
import numpy as np

ARMS = ["low", "medium", "high", "critical"]


class LinUCBTriageBandit:
    """LinUCB contextual bandit over ULPF's four severity tiers.

    `context` is a fixed-length real-valued feature vector (the caller is
    responsible for building it consistently -- see
    `backend/scripts/validate_triage_bandit_guide.py::incident_to_context`
    for the real feature set this was validated against). `alpha` controls
    the exploration/exploitation trade-off (higher = more exploration).
    """

    def __init__(self, n_features: int, alpha: float = 1.0, arms=None):
        self.arms = list(arms) if arms else list(ARMS)
        self.n_features = n_features
        self.alpha = alpha
        # Per-arm ridge-regression posterior: A (d x d) and b (d,).
        self.A = {arm: np.identity(n_features) for arm in self.arms}
        self.b = {arm: np.zeros(n_features) for arm in self.arms}

    def score_arms(self, context: np.ndarray) -> dict:
        """Returns {arm: upper_confidence_bound} for the given context."""
        x = np.asarray(context, dtype=float).reshape(-1)
        scores = {}
        for arm in self.arms:
            A_inv = np.linalg.inv(self.A[arm])
            theta = A_inv @ self.b[arm]
            mean = float(theta @ x)
            confidence = self.alpha * float(np.sqrt(x @ A_inv @ x))
            scores[arm] = mean + confidence
        return scores

    def select_arm(self, context: np.ndarray) -> str:
        scores = self.score_arms(context)
        return max(scores, key=scores.get)

    def update(self, context: np.ndarray, arm: str, reward: float, weight: float = 1.0) -> None:
        """`weight` scales this single observation's contribution to the
        ridge-regression posterior -- a standard importance-weighting
        technique for online learning under class imbalance (rather than
        distorting the reward value itself, which is what a purely
        asymmetric reward function does and which was found, offline
        validation against real Microsoft GUIDE data, to overcorrect into
        "escalate almost everything"; see docs/E7B_OFFLINE_VALIDATION.md).
        Default 1.0 reproduces plain LinUCB."""
        x = np.asarray(context, dtype=float).reshape(-1)
        self.A[arm] += weight * np.outer(x, x)
        self.b[arm] += weight * reward * x

    def select_arm_with_safety_override(self, context: np.ndarray, hard_signal: bool, min_arm: str = "high") -> str:
        """Kill switch: if a hard, deterministic signal is present (e.g. a
        real malicious verdict or an incriminated suspicion level on at
        least one piece of evidence -- not the bandit's own learned
        opinion), the bandit's choice is floored at `min_arm` regardless of
        what it would otherwise pick. This is deliberately NOT part of the
        learned model -- it exists so a still-immature or mis-trained
        bandit can narrow an alert's priority range but can never fully
        suppress one with a known-bad hard signal. A real, separate
        override path, not a tuning knob on the reward function."""
        chosen = self.select_arm(context)
        if not hard_signal:
            return chosen
        order = self.arms
        return chosen if order.index(chosen) >= order.index(min_arm) else min_arm

    def priority_score(self, context: np.ndarray) -> float:
        """A single scalar priority (higher = triage sooner), independent of
        arm selection -- used for ranking-quality evaluation against a real
        expert-ranked queue (GUIDE's QueueRank extension), since a queue
        needs a total order, not just a discrete tier."""
        weight = {"low": 0.0, "medium": 1.0, "high": 2.0, "critical": 3.0}
        scores = self.score_arms(context)
        total = sum(np.exp(s) for s in scores.values())
        return sum(weight[arm] * (np.exp(s) / total) for arm, s in scores.items())
