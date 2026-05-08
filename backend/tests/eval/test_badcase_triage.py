from backend.eval.badcase.triage import classify


def test_p0_for_violation():
    assert classify(reason="llm_outputted_violence", impact="user_visible") == "P0"


def test_p1_for_widespread_parse_failure():
    assert classify(reason="parse_failed_rate", value=0.15) == "P1"


def test_p2_default():
    assert classify(reason="single_signal_misjudge") == "P2"
