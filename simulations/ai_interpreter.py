
"""Generate structured simulation models using Groq AI."""

import json
import os
from typing import Any

from dotenv import load_dotenv
from groq import Groq


MODEL_NAME = "openai/gpt-oss-120b"

SYSTEM_PROMPT = """
Convert the user's request into a JSON simulation model.

Return exactly these top-level keys:
- name: string
- resources: list of objects with name and capacity
- jobs: list of objects with entity_id, arrival_time, and stages
- each stage has resource_name and service_duration

Rules:
- Return JSON only, without Markdown fences.
- Resource capacity must be a positive integer.
- Arrival times must be non-negative.
- Service durations must be positive.
- Every stage must refer to a defined resource.
- Use unique entity IDs.
- Include at least one resource, job, and stage.
- Do not include extra fields.
"""


def generate_model(request: str) -> dict[str, Any]:
    """Convert a natural-language request into a model dictionary."""
    if not isinstance(request, str):
        raise TypeError("Request must be a string")

    if not request.strip():
        raise ValueError("Request must not be empty")

    load_dotenv()

    api_key = os.getenv("GROQ_API_KEY")
    if not api_key:
        raise RuntimeError("GROQ_API_KEY was not found in .env")

    client = Groq(
        api_key=api_key,
        timeout=120.0,
        max_retries=2,
    )

    try:
        response = client.chat.completions.create(
            model=MODEL_NAME,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": request},
            ],
            temperature=0.2,
            max_completion_tokens=4096,
            reasoning_effort="medium",
        )

        content = response.choices[0].message.content

        if not content:
            raise ValueError("The AI returned an empty response")

        try:
            data = json.loads(content)
        except json.JSONDecodeError as error:
            raise ValueError(
                "The AI returned invalid JSON"
            ) from error

        if not isinstance(data, dict):
            raise ValueError("The AI response must be a JSON object")

        return data

    finally:
        client.close()



