# M7 Architecture — Simulation Readiness and Paradigm Suitability

## 1. Objective

M7 answers three separate questions about a specific conceptual revision:

1. Is the conceptual project structurally valid and sufficiently specified for further evaluation?
2. Which simulation paradigms appear to fit the represented concepts and mechanisms, and why?
3. Is a user-selected paradigm sufficiently specified to begin detailed implementation planning, and is an execution backend already implemented?

M7 is not a scientific validation system. A good fit means only that the representation contains recognizable structural signals for that paradigm.

## 2. Dependency direction

```text
M4 conceptual model and validator
                |
                v
         M7 readiness engine
          /      |       \
         v       v        v
       DES      ABM    Mathematical / Data-driven
     evaluator evaluator    evaluators
          \      |       /
           v     v      v
          ReadinessReport
                |
                v
    JSON persistence / CLI option 7
```

The `readiness` package imports the conceptual model and validation layer. It does not import simulation engines, M5 retrieval code or M6 LLM services. This keeps the assessment deterministic, offline-capable and independent of runtime engines.

## 3. Data contracts

- `Paradigm`: `discrete_event`, `agent_based`, `mathematical`, `data_driven`.
- `FitLevel`: `strong_fit`, `possible_fit`, `insufficient_information`, `poor_fit`.
- `BackendStatus`: `implemented`, `assessment_only`, `not_implemented`.
- `ReadinessStatus`: `not_assessable`, `needs_clarification`, `ready_for_evaluation`, `ready_for_implementation_planning`.
- `AssessmentFinding`: a human-readable explanation with stable code and IDs of the supporting conceptual elements.
- `ClarificationItem`: a prioritized, traceable question linked to conceptual element IDs.
- `ParadigmAssessment`: one independent fit assessment, backend status, supporting findings, limitations and missing requirements.
- `ReadinessReport`: project and revision identity, validation results, all four assessments, best-supported paradigm set, optional user selection, clarifications and explanation.

The report is a separate artifact. It does not append an M4 revision and cannot overwrite the original statement or conceptual history.

## 4. Evaluator rules

### DES

Looks for process concepts, resource concepts, event/trigger language, time-related properties, numeric parameters, and mechanisms with an operational definition. A strong fit requires process and resource concepts plus an operational event mechanism. Missing event timing, process definitions and units are exposed as requirements.

### ABM

Looks for actor/entity concepts, relationships involving those concepts, actor attributes, behavioural/decision mechanisms and operational rules. A strong fit requires agent-like concepts, interaction structure and an operational behaviour mechanism.

### Mathematical

Looks for numeric properties, variable concepts, quantitative/function/equation language in relationships or mechanisms, and operational mathematical rules. A strong fit requires at least two numeric properties and a quantitative relationship or operational quantitative mechanism. Merely having numbers is not enough.

### Data-driven

Looks for dataset-typed evidence references, measurable numeric properties and temporal properties. A strong fit requires a dataset reference, at least two numeric properties and a temporal property. Dataset metadata is not treated as proof that the actual file exists, is accessible, has sufficient observations or has suitable quality.

The heuristics are transparent screening rules, not learned classifiers. The implementation deliberately emits no probability or confidence percentage.

## 5. Readiness state transitions

- `NOT_ASSESSABLE`: conceptual validation has one or more errors.
- `NEEDS_CLARIFICATION`: no concepts exist, the model has no relationship/mechanism structure, blocking questions remain, or a mechanism lacks operational definition.
- `READY_FOR_EVALUATION`: the project has a valid conceptual structure adequate for comparing paradigms; this is not simulation execution readiness.
- `READY_FOR_IMPLEMENTATION_PLANNING`: a paradigm was explicitly selected, its fit is strong, required clarification items are absent, all mechanisms have trigger/effect/operational definitions, its missing-requirements list is empty, and its backend is implemented.

A mathematical or data-driven paradigm cannot reach implementation-planning readiness in this milestone because its backend is marked `assessment_only`.

## 6. Recommendation policy

Only `strong_fit` or `possible_fit` results can be recommended. The highest qualitative fit level is selected, and all paradigms tied at that level are returned. This avoids manufacturing a single winner where multiple paradigms are comparably supported. If no paradigm reaches possible fit, the recommendation set is empty.

A user may select a paradigm after reviewing the assessment. Selection is not a declaration that it is objectively correct; it asks M7 to evaluate that path's implementation-planning readiness.

## 7. Persistence and CLI

`readiness.serialization` provides strict JSON conversion and file save/load functions. Unknown fields and invalid enum values are rejected. CLI option 7 lists recently saved M6 ideas, accepts another conceptual JSON path, prints each paradigm's traceable findings and questions, optionally records a selected paradigm, and saves a unique `*_m7_readiness.json` file under `outputs/`.

## 8. Limitations and extension points

- The rule evaluators use existing M4 fields and transparent lexical/structural signals; they do not infer missing equations or behavioural rules.
- Some theories legitimately combine paradigms. The report can recommend multiple candidates.
- Fit results depend on how completely the idea has been formalized; poor wording can hide a relevant structural signal.
- The current readiness policy is intentionally conservative and may ask users to define a mechanism before implementation planning.
- Backend availability reflects delivered project packages, not whether every dependency is installed in the current Python environment.
- Future work can add evaluators through a registry/protocol, but any new paradigm should define its own evidence signals and readiness requirements rather than forcing it into another paradigm's model.
- M7 does not select an engine automatically, translate models, run experiments, validate datasets, or claim theoretical truth.
