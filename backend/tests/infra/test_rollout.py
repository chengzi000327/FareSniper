from __future__ import annotations

from collections import Counter

from backend.infrastructure.flags.rollout import in_rollout


def test_zero_pct_excludes_all():
    assert in_rollout("u1", "ai_value_judge", 0) is False
    assert in_rollout("u-other", "ai_value_judge", 0) is False


def test_full_pct_includes_all():
    assert in_rollout("u1", "ai_value_judge", 100) is True
    assert in_rollout("anything", "x", 100) is True


def test_negative_pct_excludes_all():
    assert in_rollout("u1", "x", -1) is False


def test_over_100_pct_includes_all():
    assert in_rollout("u1", "x", 200) is True


def test_50pct_is_deterministic():
    a = in_rollout("u1", "x", 50)
    b = in_rollout("u1", "x", 50)
    assert a == b


def test_different_flag_different_bucket():
    """Same user, different flag → independent buckets (collision is allowed
    but the assignment must not be a constant function of user_id alone)."""
    seen = {in_rollout("u1", f"flag_{i}", 50) for i in range(20)}
    # With 20 flag names hashed to a 50% bucket, both branches should appear.
    assert seen == {True, False}


def test_50pct_is_roughly_balanced_over_many_users():
    bucket = Counter(in_rollout(f"u{i}", "stable_flag", 50) for i in range(2000))
    # Allow generous slack; the test is a sanity check, not a chi-squared.
    assert 0.40 < bucket[True] / 2000 < 0.60
