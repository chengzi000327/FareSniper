from backend.application.services.refund_rule_parser import parse_refund


def test_free_change_window():
    text = "起飞前24小时以上免费改签，24小时内收取票面价10%手续费"
    out = parse_refund(text)
    assert out.free_change_hours_before == 24
    assert out.late_change_pct == 10


def test_no_refund_after_departure():
    text = "起飞后不可退票，可改签下一航班需补差价"
    out = parse_refund(text)
    assert out.refund_after_depart is False
