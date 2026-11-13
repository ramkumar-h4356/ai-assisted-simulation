"""Persistence helpers for the M6 clarification audit trail."""

from __future__ import annotations

import json
from dataclasses import asdict
from pathlib import Path
from typing import Any

from idea_assistant.models import ClarificationExchange, IdeaAssistantSession, RetrievedContext


class SessionSerializationError(ValueError):
    pass


def session_to_dict(session: IdeaAssistantSession) -> dict[str, Any]:
    if not isinstance(session, IdeaAssistantSession):
        raise TypeError("session must be an IdeaAssistantSession")
    return asdict(session)


def session_from_dict(data: Any) -> IdeaAssistantSession:
    if not isinstance(data, dict):
        raise SessionSerializationError("session must be a JSON object")
    allowed = {
        "id", "project_id", "created_at", "initial_request", "clarification_history",
        "retrieved_context", "final_summary", "uncertainties",
    }
    if set(data) != allowed:
        raise SessionSerializationError("session contains missing or unsupported fields")
    try:
        history = tuple(ClarificationExchange(**item) for item in data["clarification_history"])
        context = tuple(
            RetrievedContext(**{**item, "matched_terms": tuple(item.get("matched_terms", ()))})
            for item in data["retrieved_context"]
        )
        uncertainties = tuple(data["uncertainties"])
        if any(not isinstance(item, str) for item in uncertainties):
            raise TypeError("uncertainties must contain strings")
        return IdeaAssistantSession(
            id=data["id"], project_id=data["project_id"], created_at=data["created_at"],
            initial_request=data["initial_request"], clarification_history=history,
            retrieved_context=context, final_summary=data["final_summary"], uncertainties=uncertainties,
        )
    except (KeyError, TypeError, ValueError) as error:
        raise SessionSerializationError(f"Invalid session data: {error}") from error


def dumps_session(session: IdeaAssistantSession, *, indent: int = 2) -> str:
    return json.dumps(session_to_dict(session), ensure_ascii=False, indent=indent, allow_nan=False)


def loads_session(content: str) -> IdeaAssistantSession:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise SessionSerializationError(f"Invalid session JSON: {error}") from error
    return session_from_dict(raw)


def save_session(session: IdeaAssistantSession, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dumps_session(session), encoding="utf-8")
    return destination


def load_session(path: str | Path) -> IdeaAssistantSession:
    source = Path(path)
    return loads_session(source.read_text(encoding="utf-8"))
