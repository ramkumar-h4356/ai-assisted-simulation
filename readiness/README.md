# M7 — Simulation Readiness and Paradigm Suitability

M7 assesses a saved M4 conceptual revision and reports qualitative fit and
implementation-planning readiness for five paradigms: DES, ABM, mathematical,
data-driven and system dynamics. It is a deterministic, transparent screening layer; it does
not validate a scientific theory, prove a causal relationship or execute a
simulation.

## API

```python
from conceptual import load_idea_project
from readiness import assess_readiness, Paradigm

project = load_idea_project("outputs/my_idea_m6_idea.json")
report = assess_readiness(project, selected_paradigm=Paradigm.DATA_DRIVEN)
print(report.status.value)
for item in report.assessments:
    print(item.paradigm.value, item.fit.value, item.backend_status.value)
```

## Paradigm signals

- **DES:** process/resource concepts and operational event mechanisms.
- **ABM:** actor concepts, interactions and operational behaviour mechanisms.
- **Mathematical:** numeric properties and explicit quantitative relationships
  or operational quantitative rules.
- **Data-driven:** a DATASET evidence reference, at least two numeric
  properties and a temporal property. Data-driven readiness does not require
  a causal operational mechanism because M21 estimates predictive
  associations only.
- **System dynamics:** accumulated stock/level concepts, flow-like mechanisms
  or relationships, numeric state/rate properties and an explicit time basis.
  Feedback-loop signals are screened but must still be reviewed and mapped by
  the user; M7 does not infer a loop's polarity or prove its causal meaning.

A strong qualitative fit is not enough on its own. Implementation planning
also requires the selected paradigm's missing requirements and blocking
clarifications to be resolved and an implemented backend to be available.
M7 does not open or profile the real dataset file; M8 validates explicit
observations and binds them to the exact DATASET evidence-reference ID.

See `M7_ARCHITECTURE.md` for the detailed rules, state transitions,
clarification policy, persistence and limitations.
