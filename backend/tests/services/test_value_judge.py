import backend.services.value_judge as vj


def test_value_judge_uses_loaded_prompt(monkeypatch):
    monkeypatch.setattr(vj, "load_prompt", lambda name: "PULLED VALUE JUDGE PROMPT")
    assert vj._system_prompt() == "PULLED VALUE JUDGE PROMPT"
