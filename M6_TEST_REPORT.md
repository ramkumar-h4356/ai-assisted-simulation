# M6 Test Report

## Environment

- Python: 3.13
- Test runner: pytest
- Live Groq calls: not used; M6 tests inject a deterministic stub interpreter.
- External network access: unavailable in the build environment.

## Results

Command:

```bash
python -m pytest tests/idea_assistant tests/conceptual tests/knowledge tests/core tests/abm -q
```

Result:

```text
256 passed in 0.32s
```

This run covers the new M6 tests plus the available conceptual, knowledge, shared-core and ABM groups.

A full `python -m pytest -q` collection was attempted but could not collect the DES tests in this build environment because the environment does not have the existing project dependencies `groq` and `simpy` installed. Installing them was also attempted, but package-index access was unavailable. No DES test failure was observed; collection was blocked before execution. The M5 project was previously validated by the user on Windows with `369 passed, 27 subtests passed`. The full Windows suite should be rerun after extracting this M6 archive; the expected total will include the 13 new M6 tests (approximately 382 passed and 27 subtests passed if the earlier suite remains unchanged).

## Coverage added

- Strict top-level and nested JSON validation.
- Enum, duplicate-concept and undeclared-reference rejection.
- Clarification question and answer loop.
- Preservation of original idea and append-only revision structure.
- Exact excerpt provenance and downgrade of false explicit claims.
- Optional M5 retrieval context handoff.
- Conceptual project serialization round trip with provenance.
- Clarification session serialization round trip.
- Open-question retention when no clarification answer is provided or when only part of a round is answered.
- Downgrade of unsupported `defined` labels when mandatory definitions are empty.
- Hiding application-generated clarification IDs from LLM refinement payloads.
