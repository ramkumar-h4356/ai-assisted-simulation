# Milestone 7 — Simulation Readiness Assessment and Paradigm Suitability

## Outcome

M7 adds an offline, deterministic assessment layer that evaluates a saved conceptual idea against four simulation paradigms and identifies what must be clarified before implementation planning.

## Delivered

- Four independent evaluators: DES, ABM, mathematical and data-driven.
- Qualitative fit labels and traceable findings, limitations and missing requirements.
- Explicit distinction between conceptual suitability and backend availability.
- Multiple recommendations when two or more paradigms share the highest fit.
- Readiness statuses: not assessable, needs clarification, ready for evaluation and ready for implementation planning.
- Clarification items derived from existing open questions, incomplete mechanisms, partial concepts, unknown property types, missing units and paradigm-specific requirements.
- Optional user-selected paradigm assessment.
- Strict JSON report serialization and persistence.
- CLI option 7 to assess a saved M6 project or any conceptual project JSON.
- Demo against `scenarios/conceptual/decentralized_resource_cooperation.json`.
- 23 focused M7 tests.

## Backend status

| Paradigm | M7 assessment | Execution backend status |
|---|---|---|
| DES | Implemented evaluator | Implemented |
| ABM | Implemented evaluator | Implemented |
| Mathematical | Implemented evaluator | Assessment only |
| Data-driven | Implemented evaluator | Assessment only |

## Important boundaries

M7 does not mutate the idea or append a conceptual revision. It records the exact revision ID/version used in a separate report. A dataset reference does not mean that the underlying file was accessed or profiled. A strong fit is not a scientific truth claim, and readiness for implementation planning is not proof that an executable model will be valid. No LLM, web retrieval, custom ML model or confidence percentage is used.

## Run

```powershell
python -m pytest -q
python -m readiness.demo
python main.py
```

Choose option 7 to assess an existing conceptual project.
