from __future__ import annotations

import pytest

from backend.services.booking_url_builder import Platform, build_booking_url


_IPHONE_UA = "Mozilla/5.0 (iPhone; CPU iPhone OS 17_0 like Mac OS X) AppleWebKit/605.1.15"
_ANDROID_UA = "Mozilla/5.0 (Linux; Android 14; Pixel 8) AppleWebKit/537.36"
_DESKTOP_UA = "Mozilla/5.0 (Windows NT 10.0; Win64; x64) Chrome/130.0"


def test_ctrip_app_with_cps():
    url = build_booking_url(
        Platform.CTRIP,
        flight_no="MU5137",
        date="2026-05-01",
        origin="BJS",
        destination="SYX",
        user_agent=_IPHONE_UA,
        cps_id="fs_demo",
    )
    assert url.startswith("ctripapp://")
    assert "allianceid=fs_demo" in url
    assert "MU5137" in url


def test_qunar_h5_fallback_when_app_missing():
    url = build_booking_url(
        Platform.QUNAR,
        flight_no="CZ3901",
        date="2026-05-01",
        origin="CAN",
        destination="HGH",
        user_agent=_DESKTOP_UA,
        cps_id="fs_demo",
    )
    assert url.startswith("https://m.flight.qunar.com")
    assert "qsid=fs_demo" in url


@pytest.mark.parametrize(
    "platform,expected_param",
    [
        (Platform.CTRIP, "allianceid"),
        (Platform.QUNAR, "qsid"),
        (Platform.TONGCHENG, "refid"),
        (Platform.FLIGGY, "afk"),
        (Platform.UMETRIP, "channel"),
    ],
)
def test_each_platform_uses_distinct_cps_param(platform, expected_param):
    url = build_booking_url(
        platform,
        flight_no="MU5137",
        date="2026-05-01",
        origin="BJS",
        destination="SYX",
        user_agent=_DESKTOP_UA,
        cps_id="fs_demo",
    )
    assert f"{expected_param}=fs_demo" in url


def test_android_ua_picks_app_scheme():
    url = build_booking_url(
        Platform.FLIGGY,
        flight_no="HU7301",
        date="2026-06-01",
        origin="HKG",
        destination="PVG",
        user_agent=_ANDROID_UA,
        cps_id="fs_demo",
    )
    assert url.startswith("tbtrip://")


def test_desktop_ua_picks_h5():
    url = build_booking_url(
        Platform.TONGCHENG,
        flight_no="MU5137",
        date="2026-05-01",
        origin="BJS",
        destination="SYX",
        user_agent=_DESKTOP_UA,
        cps_id="fs_demo",
    )
    assert url.startswith("https://m.ly.com")


def test_query_includes_route_and_date():
    url = build_booking_url(
        Platform.CTRIP,
        flight_no="MU5137",
        date="2026-05-01",
        origin="BJS",
        destination="SYX",
        user_agent=_DESKTOP_UA,
        cps_id="fs_demo",
    )
    assert "from=BJS" in url
    assert "to=SYX" in url
    assert "date=2026-05-01" in url
    assert "flight=MU5137" in url
