from __future__ import annotations

from backend.infrastructure.experiment.assigner import assign_arm


def test_two_arms_50_50():
    arms = [assign_arm(f"u{i}", "H1_chat_vs_form") for i in range(1000)]
    assert 400 <= arms.count("control") <= 600
    assert 400 <= arms.count("treatment") <= 600


def test_assignment_is_stable():
    a = assign_arm("u1", "H1_chat_vs_form")
    b = assign_arm("u1", "H1_chat_vs_form")
    assert a == b
