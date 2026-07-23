"""All 12 launch-plan endpoints must be registered with the right method.

The 3 endpoints introduced by TG-05 · Task 3 (auth/otp, auth/verify,
push/subscriptions, price_history) are placeholders today — TG-12 and
TG-09i replace the bodies with real handlers.
"""

from __future__ import annotations

from backend.main import app

EXPECTED = {
    ("POST", "/api/session"),
    ("POST", "/api/search"),
    ("GET", "/api/memory"),
    ("PATCH", "/api/memory"),
    ("DELETE", "/api/memory/{field}"),
    ("GET", "/api/recommendations"),
    ("POST", "/api/alerts"),
    ("GET", "/api/alerts"),
    ("POST", "/api/auth/otp"),
    ("POST", "/api/auth/verify"),
    ("POST", "/api/auth/wechat/session"),
    ("POST", "/api/alerts/{alert_id}/wechat-subscription"),
    ("GET", "/api/alerts/{alert_id}"),
    ("PATCH", "/api/alerts/{alert_id}"),
    ("GET", "/api/price_history"),
    ("POST", "/api/push/subscriptions"),
}


def test_all_routes_registered():
    paths: set[tuple[str, str]] = set()
    for route in app.routes:
        methods = getattr(route, "methods", None)
        path = getattr(route, "path", None)
        if not methods or not path:
            continue
        for method in methods - {"HEAD", "OPTIONS"}:
            paths.add((method, path))
    missing = EXPECTED - paths
    assert not missing, f"missing routes: {sorted(missing)}"
