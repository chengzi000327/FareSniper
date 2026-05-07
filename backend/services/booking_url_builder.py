"""Deep-link builder for the 5 supported booking platforms.

Each platform takes a different CPS query-param name and exposes both
an APP-scheme URL (preferred when the user is on iOS / Android) and an
HTTPS m.* fallback. ``build_booking_url`` picks the right channel based
on a quick UA sniff and merges the route / flight / CPS params.
"""
from __future__ import annotations

from enum import Enum
from urllib.parse import urlencode


class Platform(str, Enum):
    CTRIP = "ctrip"
    QUNAR = "qunar"
    TONGCHENG = "tongcheng"
    FLIGGY = "fliggy"
    UMETRIP = "umetrip"


CPS_PARAM: dict[Platform, str] = {
    Platform.CTRIP: "allianceid",
    Platform.QUNAR: "qsid",
    Platform.TONGCHENG: "refid",
    Platform.FLIGGY: "afk",
    Platform.UMETRIP: "channel",
}

APP_SCHEMES: dict[Platform, str] = {
    Platform.CTRIP: "ctripapp://flights/list",
    Platform.QUNAR: "qunaraphone://flight",
    Platform.TONGCHENG: "tctrip://flight/list",
    Platform.FLIGGY: "tbtrip://flight",
    Platform.UMETRIP: "umetrip://flight",
}

H5_BASES: dict[Platform, str] = {
    Platform.CTRIP: "https://m.ctrip.com/webapp/flight/schedule",
    Platform.QUNAR: "https://m.flight.qunar.com/h5/flight/list",
    Platform.TONGCHENG: "https://m.ly.com/flight/list",
    Platform.FLIGGY: "https://h5.m.taobao.com/trip/flight/list",
    Platform.UMETRIP: "https://m.umetrip.com/flight",
}


def _is_mobile_app_capable(user_agent: str) -> bool:
    return any(token in user_agent for token in ("iPhone", "Android"))


def build_booking_url(
    platform: Platform,
    *,
    flight_no: str,
    date: str,
    origin: str,
    destination: str,
    user_agent: str,
    cps_id: str,
) -> str:
    params = {
        "from": origin,
        "to": destination,
        "date": date,
        "flight": flight_no,
        CPS_PARAM[platform]: cps_id,
    }
    base = APP_SCHEMES[platform] if _is_mobile_app_capable(user_agent) else H5_BASES[platform]
    return f"{base}?{urlencode(params)}"
