from backend.config import Settings


def test_collector_settings_are_fail_closed_and_bounded():
    settings = Settings(_env_file=None)

    assert settings.ctrip_collector_token == ""
    assert settings.ctrip_snapshot_ttl_minutes == 75
    assert settings.ctrip_collector_heartbeat_timeout_seconds == 180
    assert settings.ctrip_collector_lease_seconds == 180


def test_collector_settings_load_from_environment(monkeypatch):
    monkeypatch.setenv("CTRIP_COLLECTOR_TOKEN", "collector-secret")
    monkeypatch.setenv("CTRIP_SNAPSHOT_TTL_MINUTES", "90")
    monkeypatch.setenv("CTRIP_COLLECTOR_HEARTBEAT_TIMEOUT_SECONDS", "240")
    monkeypatch.setenv("CTRIP_COLLECTOR_LEASE_SECONDS", "120")

    settings = Settings(_env_file=None)

    assert settings.ctrip_collector_token == "collector-secret"
    assert settings.ctrip_snapshot_ttl_minutes == 90
    assert settings.ctrip_collector_heartbeat_timeout_seconds == 240
    assert settings.ctrip_collector_lease_seconds == 120
