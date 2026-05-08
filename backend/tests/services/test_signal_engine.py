from __future__ import annotations

from backend.application.services.signal_engine import compute_signals


def test_historical_low_signal():
    sigs = compute_signals(
        price=380, hist_avg=500, user_band=None, holiday=False, frequent_route=False
    )
    assert "历史低价" in sigs


def test_within_psychological_band():
    sigs = compute_signals(
        price=460,
        hist_avg=500,
        user_band={"min": 400, "max": 500},
        holiday=False,
        frequent_route=False,
    )
    assert "符合心理价位" in sigs


def test_holiday_and_frequent_route():
    sigs = compute_signals(
        price=600, hist_avg=600, user_band=None, holiday=True, frequent_route=True
    )
    assert "节假日热门" in sigs
    assert "符合出行习惯" in sigs
