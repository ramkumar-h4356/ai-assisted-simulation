"""Interpreter interfaces and lazy Groq implementation for M6."""

from __future__ import annotations

import json
import os
from typing import Any, Protocol, Sequence

from idea_assistant.prompts import IDEA_INTERPRETATION_PROMPT

MODEL_NAME = "openai/gpt-oss-120b"


class IdeaInterpreter(Protocol):
    def interpret(self, request: str, *, knowledge_context: Sequence[dict[str, Any]] = ()) -> dict[str, Any]: ...

    def refine(
        self,
        request: str,
        current_draft: dict[str, Any],
        clarification_history: Sequence[dict[str, Any]],
        *,
        knowledge_context: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]: ...


class GroqIdeaInterpreter:
    """Groq-backed structured interpreter. Importing this class needs no API call."""

    def __init__(self, *, model: str = MODEL_NAME, api_key: str | None = None) -> None:
        self.model = model
        self.api_key = api_key

    def _request_json(self, user_content: str) -> dict[str, Any]:
        from dotenv import load_dotenv
        from groq import Groq

        load_dotenv()
        api_key = self.api_key or os.getenv("GROQ_API_KEY")
        if not api_key:
            raise RuntimeError("GROQ_API_KEY was not found in .env or environment variables")
        client = Groq(api_key=api_key, timeout=120.0, max_retries=2)
        try:
            response = client.chat.completions.create(
                model=self.model,
                messages=[
                    {"role": "system", "content": IDEA_INTERPRETATION_PROMPT},
                    {"role": "user", "content": user_content},
                ],
                temperature=0.1,
                max_completion_tokens=8192,
                reasoning_effort="medium",
            )
            content = response.choices[0].message.content
            if not content:
                raise ValueError("The AI returned an empty interpretation response")
            try:
                value = json.loads(content)
            except json.JSONDecodeError as error:
                raise ValueError("The AI returned invalid JSON for the M6 interpretation schema") from error
            if not isinstance(value, dict):
                raise ValueError("The AI response must be a JSON object")
            return value
        finally:
            client.close()

    def interpret(self, request: str, *, knowledge_context: Sequence[dict[str, Any]] = ()) -> dict[str, Any]:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("The initial idea must be a non-empty string")
        payload = {
            "user_idea": request.strip(),
            "clarification_history": [],
            "local_knowledge_context": list(knowledge_context),
            "task": "Create the first structured interpretation and ask only material clarification questions.",
        }
        return self._request_json(json.dumps(payload, ensure_ascii=False))

    def refine(
        self,
        request: str,
        current_draft: dict[str, Any],
        clarification_history: Sequence[dict[str, Any]],
        *,
        knowledge_context: Sequence[dict[str, Any]] = (),
    ) -> dict[str, Any]:
        if not isinstance(request, str) or not request.strip():
            raise ValueError("The initial idea must be a non-empty string")
        if not isinstance(current_draft, dict):
            raise TypeError("current_draft must be a dictionary")
        payload = {
            "original_user_idea": request,
            "current_interpretation": current_draft,
            "clarification_history": list(clarification_history),
            "local_knowledge_context": list(knowledge_context),
            "task": "Return the complete revised interpretation. Preserve earlier established details and do not assume unanswered questions.",
        }
        return self._request_json(json.dumps(payload, ensure_ascii=False))
