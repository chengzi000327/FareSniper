import backend.infrastructure.llm.prompt_loader as pl


def setup_function():
    pl._CACHE.clear()


def test_falls_back_to_default_when_langsmith_unavailable(monkeypatch):
    monkeypatch.setattr(pl, "_pull_from_langsmith", lambda name: None)
    text = pl.load_prompt("react_agent")
    assert "FareSniper" in text


def test_uses_langsmith_text_when_available(monkeypatch):
    monkeypatch.setattr(pl, "_pull_from_langsmith", lambda name: "HUB PROMPT BODY")
    assert pl.load_prompt("react_agent") == "HUB PROMPT BODY"


def test_caches_within_ttl(monkeypatch):
    calls = {"n": 0}

    def fake_pull(name):
        calls["n"] += 1
        return "HUB"

    monkeypatch.setattr(pl, "_pull_from_langsmith", fake_pull)
    pl.load_prompt("react_agent")
    pl.load_prompt("react_agent")
    assert calls["n"] == 1


def test_falls_back_to_local_file(monkeypatch, tmp_path):
    monkeypatch.setattr(pl, "_pull_from_langsmith", lambda name: None)
    monkeypatch.setattr(pl, "_PROMPTS_DIR", tmp_path)
    (tmp_path / "react_agent.txt").write_text("FILE PROMPT", encoding="utf-8")
    assert pl.load_prompt("react_agent") == "FILE PROMPT"


def test_refetches_after_ttl_expiry(monkeypatch):
    calls = {"n": 0}

    def fake_pull(name):
        calls["n"] += 1
        return "HUB"

    monkeypatch.setattr(pl, "_pull_from_langsmith", fake_pull)
    pl._CACHE["react_agent"] = ("OLD", 0.0)  # timestamp far in the past
    pl.load_prompt("react_agent")
    assert calls["n"] == 1
