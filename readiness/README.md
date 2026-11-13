# M7 — Simulation Readiness Assessment

The `readiness/` package evaluates a saved M4/M6 conceptual project without changing it or requiring an LLM. It provides four transparent evaluators:

- **Discrete-event simulation (DES):** event/process stages, resources, triggers, time semantics and operational event rules.
- **Agent-based modelling (ABM):** agent-like entities, interactions, attributes/states and operational behaviours.
- **Mathematical simulation:** numeric variables, quantitative relationships, equations and explicit update rules.
- **Data-driven modelling:** dataset references, measurable fields and temporal/ordered observations.

Each evaluation includes a qualitative fit (`strong_fit`, `possible_fit`, `insufficient_information`, `poor_fit`), traceable supporting findings, limitations, missing requirements and current backend availability. No arbitrary confidence percentages are generated.

## Use

```python
from conceptual import load_idea_project
from readiness import assess_readiness, Paradigm, save_report

project = load_idea_project("outputs/my_idea.json")
report = assess_readiness(project)
print(report.status.value)
for assessment in report.paradigm_assessments:
    print(assessment.paradigm.value, assessment.fit.value)

# Optional: test a user-selected direction for implementation-planning readiness.
selected_report = assess_readiness(project, selected_paradigm=Paradigm.AGENT_BASED)
save_report(selected_report, "outputs/my_idea_m7_readiness.json")
```

Or run the included example:

```powershell
python -m readiness.demo
```

## Readiness statuses

- `not_assessable`: structural validation errors must be resolved.
- `needs_clarification`: key definitions, rules or blocking questions remain incomplete.
- `ready_for_evaluation`: enough structure exists to compare paradigms; this is not execution readiness.
- `ready_for_implementation_planning`: a selected, implemented paradigm has a strong fit and its assessed requirements are operationalized. This is permission to begin detailed implementation planning, not a claim that the model is validated or executable.

## Backend availability

DES and ABM are marked `implemented` because their model and execution packages exist in this project. Mathematical and data-driven are marked `assessment_only`; M7 can evaluate conceptual suitability but those execution engines have not been delivered. For data-driven ideas, a dataset citation is not proof that the underlying file is accessible or has been profiled.

## Boundaries

M7 is deterministic and does not alter the `IdeaProject`, append a revision, retrieve evidence, or call an LLM. It is a transparent rule-based screening tool, not a scientific peer reviewer. Fit labels are qualitative rule outcomes, not probabilities or confidence scores. The report records the exact project revision it assessed. After changing the idea, run a new assessment against the new revision.
