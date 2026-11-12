import json

import pytest

from simulations.abm import interpreter


def test_generate_agent_model_uses_abm_system_prompt(monkeypatch):
    captured = {}

    def fake_request(system_prompt, user_content):
        captured["system"] = system_prompt
        captured["user"] = user_content
        return {"agents": []}

    monkeypatch.setattr(interpreter, "_request_json", fake_request)
    result = interpreter.generate_agent_model("A small disease spread model")

    assert result == {"agents": []}
    assert "Agent-Based Model" in captured["system"]
    assert "execute_python" not in captured["system"]
    assert captured["user"] == "A small disease spread model"


def test_generate_agent_model_rejects_empty_request_without_api_call(monkeypatch):
    monkeypatch.setattr(
        interpreter,
        "_request_json",
        lambda *_: pytest.fail("API layer must not be called"),
    )

    with pytest.raises(ValueError, match="non-empty"):
        interpreter.generate_agent_model(" ")


def test_refine_agent_model_serializes_complete_context(monkeypatch):
    captured = {}

    def fake_request(system_prompt, user_content):
        captured["system"] = system_prompt
        captured["user"] = json.loads(user_content)
        return {"agents": [{"reference": "a", "agent_type": "person", "state": "well"}]}

    monkeypatch.setattr(interpreter, "_request_json", fake_request)
    result = interpreter.refine_agent_model(
        "Original request",
        {"agents": []},
        [{"round": 1, "answer": "One person"}],
    )

    assert result["agents"][0]["state"] == "well"
    assert captured["user"]["original_user_request"] == "Original request"
    assert captured["user"]["current_model"] == {"agents": []}
    assert len(captured["user"]["clarification_history"]) == 1
