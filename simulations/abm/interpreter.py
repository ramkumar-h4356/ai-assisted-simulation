"""Groq-based natural-language interpretation for Agent-Based Models."""

from __future__ import annotations

import json
import os
from typing import Any

MODEL_NAME = "openai/gpt-oss-120b"

SYSTEM_PROMPT = r"""
You convert natural-language descriptions into a declarative Agent-Based Model (ABM).
You are an interpreter, not a simulator and not a code generator.
Return exactly one valid JSON object. Never return Markdown, comments, Python,
JavaScript, executable expressions, or explanations outside the JSON.

REQUIRED TOP-LEVEL SCHEMA:
{
  "name": "descriptive model name",
  "agents": [
    {"reference": "temporary_unique_alias", "agent_type": "person",
     "state": "susceptible", "attributes": {}}
  ],
  "environment": {"attributes": {}},
  "relationships": [
    {"source": "agent_reference", "target": "agent_reference",
     "relation_type": "contact", "directed": false}
  ],
  "behaviours": [
    {"rule_id": "temporary_rule_name", "agent_type": "person_or_null",
     "condition": {"type": "agent_state_is", "state": "susceptible"},
     "actions": [{"type": "set_state", "state": "infected"}],
     "probability": 1.0}
  ],
  "activation": {"mode": "sequential", "order": "declaration"},
  "termination": {"type": "max_steps", "value": 5},
  "random_seed": null
}

INTERPRETATION RULES
1. Agents are individual entities in V1. Represent each described individual as one
   array item. For a small stated count (for example, three people), expand the count
   into three individual entries. Do not expand very large populations; when the
   description requires more than 100 individual agents, return an empty agents array
   and put a clear explanation in the uncertainty list is NOT supported by this
   schema, so instead set agents to null. The application will ask for a smaller,
   explicit V1 example.
2. "reference" is a temporary alias used only to connect relationships. Generate a
   unique short alias for every agent. The Python application generates final IDs.
   Do not ask the user for internal identifiers. Meaningful names may be used as
   references when the user supplied them.
3. Every agent needs an agent_type and an initial state. Preserve user terminology.
   Do not invent initial states. Use null for unknown required values.
4. Attributes must be JSON scalar values (string, number, boolean, or null). Do not
   encode nested objects or arrays as agent attributes.
5. Relationships are static links between agent references. Use an empty array only
   when no relationships are described or needed. Do not infer a complete network
   merely because agents are in the same population.
6. Behaviour conditions may use only:
   - {"type":"agent_state_is", "state":"..."}
   - {"type":"agent_attribute_comparison", "attribute":"...", "operator":"eq|ne|lt|le|gt|ge", "value":...}
   - {"type":"related_agent_state_count", "relation_type":"...", "state":"...", "operator":"eq|ne|lt|le|gt|ge", "count":0}
   - {"type":"all_of|any_of", "conditions":[...]}
7. Behaviour actions may use only:
   - {"type":"set_state", "state":"..."}
   - {"type":"set_attribute", "attribute":"...", "value":...}
   - {"type":"increment_attribute", "attribute":"...", "amount":1}
8. Rule conditions are tested for the currently activated agent. An agent_type filter
   may be null to apply to all types. Rules execute in declaration order.
9. A definite rule has probability 1.0. A chance/percentage must be converted to a
   probability from 0 to 1. Never invent probabilities. When the probability is
   genuinely unspecified and cannot be inferred, set it to null.
10. The engine supports sequential agent activation in declaration order only. Always
    emit that activation policy. Do not claim to support simultaneous or random order.
11. Termination in V1 is a positive integer max_steps. If the user did not state a
    meaningful run length, set termination.value to null; do not invent it.
12. random_seed is null unless the user specifies a non-negative integer seed.
13. Preserve uncertainty rather than silently guessing. Use null for unknown required
    fields. The application handles internal IDs and asks the user about missing facts.
14. The environment is a shared dictionary of scalar attributes. No environment mutation
    actions are supported in this version.
15. Do not create a rule if the user's description does not establish one.

CONDITION SEMANTICS: related_agent_state_count counts the currently visible neighbours
for the specified relation type. The relationship direction follows the model's static
edges. Do not confuse this with a global population count.

Do not omit any required top-level key. Use [] only when a collection is known to be empty; use null for an unknown required collection.
Output must have exactly these top-level keys and be directly parseable with json.loads:
name, agents, environment, relationships, behaviours, activation, termination, random_seed.
"""


def _request_json(system_prompt: str, user_content: str) -> dict[str, Any]:
    """Call Groq lazily so importing the package does not require API packages."""
    from dotenv import load_dotenv
    from groq import Groq

    load_dotenv()
    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY was not found in .env")

    client = Groq(api_key=api_key, timeout=120.0, max_retries=2)
    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_content},
            ],
            temperature=0.1,
            max_completion_tokens=4096,
            reasoning_effort="medium",
        )
        content = response.choices[0].message.content
        if not content:
            raise ValueError("The AI returned an empty response.")
        try:
            parsed = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError("The AI returned invalid JSON for the ABM schema.") from error
        if not isinstance(parsed, dict):
            raise ValueError("The AI response must be a JSON object.")
        return parsed
    finally:
        client.close()


def generate_agent_model(request: str) -> dict[str, Any]:
    if not isinstance(request, str) or not request.strip():
        raise ValueError("Request must be a non-empty string.")
    return _request_json(SYSTEM_PROMPT, request.strip())


def refine_agent_model(
    original_request: str,
    current_model_data: dict[str, Any],
    clarification_history: list[dict[str, Any]],
) -> dict[str, Any]:
    if not isinstance(original_request, str) or not original_request.strip():
        raise ValueError("Original request must be a non-empty string.")
    if not isinstance(current_model_data, dict):
        raise TypeError("Current model data must be a dictionary.")
    if not isinstance(clarification_history, list):
        raise TypeError("Clarification history must be a list.")

    context = {
        "original_user_request": original_request,
        "current_model": current_model_data,
        "clarification_history": clarification_history,
        "instructions": [
            "Return the complete updated ABM JSON object, not a partial patch.",
            "Preserve established facts unless the user explicitly corrects them.",
            "Use clarification answers to fill or correct missing fields.",
            "Do not invent missing operational facts or probabilities.",
            "Follow the exact ABM JSON schema in the system instructions.",
        ],
    }
    return _request_json(
        SYSTEM_PROMPT,
        json.dumps(context, ensure_ascii=False),
    )
