"""Tests for the LinUCB contextual bandit (ULPF-phase2-prompt.md E7b).

Hand-constructed contexts/rewards -- exercising the bandit algorithm itself,
not real GUIDE data (that's `scripts/validate_triage_bandit_guide.py`,
run separately against the real downloaded dataset, documented in
docs/E7B_OFFLINE_VALIDATION.md)."""
import sys
import os
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..'))

import numpy as np

from app.ai.triage_bandit import LinUCBTriageBandit, ARMS


class TestLinUCBTriageBandit:
    def test_initial_scores_are_equal_across_arms_with_no_data(self):
        bandit = LinUCBTriageBandit(n_features=3)
        scores = bandit.score_arms(np.array([1.0, 0.5, 0.2]))
        assert len(set(round(s, 9) for s in scores.values())) == 1  # identical priors -> identical UCB

    def test_arms_are_ulpf_own_severity_tiers(self):
        assert ARMS == ["low", "medium", "high", "critical"]

    def test_learns_to_prefer_the_rewarded_arm_for_a_repeated_context(self):
        bandit = LinUCBTriageBandit(n_features=2, alpha=0.1)
        context = np.array([1.0, 5.0])
        for _ in range(50):
            bandit.update(context, "critical", reward=1.0)
            bandit.update(context, "low", reward=0.0)
        assert bandit.select_arm(context) == "critical"

    def test_update_only_changes_the_chosen_arms_model(self):
        bandit = LinUCBTriageBandit(n_features=2)
        context = np.array([1.0, 2.0])
        b_before = {arm: bandit.b[arm].copy() for arm in bandit.arms}
        bandit.update(context, "high", reward=1.0)
        for arm in bandit.arms:
            if arm == "high":
                assert not np.array_equal(bandit.b[arm], b_before[arm])
            else:
                assert np.array_equal(bandit.b[arm], b_before[arm])

    def test_priority_score_is_monotonic_with_learned_tier_preference(self):
        """Uses orthogonal contexts (no shared bias-like component) so each
        arm's linear model can only explain the reward it actually saw --
        a context sharing a dominant feature with both training contexts
        (e.g. a constant bias term) would let one arm's model generalize
        across both and mask the very separation this test checks for."""
        bandit = LinUCBTriageBandit(n_features=2, alpha=0.1)
        low_context = np.array([1.0, 0.0])
        high_context = np.array([0.0, 1.0])
        for _ in range(50):
            bandit.update(low_context, "low", reward=1.0)
            bandit.update(high_context, "critical", reward=1.0)
        assert bandit.priority_score(high_context) > bandit.priority_score(low_context)

    def test_unseen_context_falls_back_to_the_shared_prior_not_a_crash(self):
        bandit = LinUCBTriageBandit(n_features=4)
        arm = bandit.select_arm(np.array([0.0, 0.0, 0.0, 0.0]))
        assert arm in bandit.arms

    def test_update_weight_scales_learning_speed(self):
        """A weight=5 update should move the model roughly as far as 5
        weight=1 updates on the same (context, arm, reward) -- verifies the
        importance-weighting mechanism used to counter class imbalance."""
        bandit_weighted = LinUCBTriageBandit(n_features=2)
        bandit_repeated = LinUCBTriageBandit(n_features=2)
        context = np.array([1.0, 2.0])
        bandit_weighted.update(context, "high", reward=1.0, weight=5.0)
        for _ in range(5):
            bandit_repeated.update(context, "high", reward=1.0, weight=1.0)
        assert np.allclose(bandit_weighted.A["high"], bandit_repeated.A["high"])
        assert np.allclose(bandit_weighted.b["high"], bandit_repeated.b["high"])

    def test_safety_override_floors_a_hard_signal_at_min_arm(self):
        bandit = LinUCBTriageBandit(n_features=2, alpha=0.1)
        context = np.array([1.0, 0.0])
        for _ in range(50):
            bandit.update(context, "low", reward=1.0)  # bandit has learned to pick "low" here
        assert bandit.select_arm(context) == "low"
        overridden = bandit.select_arm_with_safety_override(context, hard_signal=True, min_arm="high")
        assert overridden == "high"

    def test_safety_override_does_not_change_a_choice_already_above_the_floor(self):
        bandit = LinUCBTriageBandit(n_features=2, alpha=0.1)
        context = np.array([1.0, 0.0])
        for _ in range(50):
            bandit.update(context, "critical", reward=1.0)
        result = bandit.select_arm_with_safety_override(context, hard_signal=True, min_arm="high")
        assert result == "critical"

    def test_safety_override_is_a_noop_without_a_hard_signal(self):
        bandit = LinUCBTriageBandit(n_features=2, alpha=0.1)
        context = np.array([1.0, 0.0])
        for _ in range(50):
            bandit.update(context, "low", reward=1.0)
        assert bandit.select_arm_with_safety_override(context, hard_signal=False, min_arm="high") == "low"
