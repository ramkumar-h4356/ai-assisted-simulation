# ABM Milestone 1 — Model Contract and Validation

## Delivered

- Immutable, typed ABM model objects for agents, environments, static relationships, conditions, actions, behaviour rules, activation policy, and termination.
- Declarative condition types: state checks, attribute comparisons, related-agent state counts, `AllOf`, and `AnyOf`.
- Declarative action types: state changes, scalar attribute assignment, and numeric attribute increments.
- Probability field with finite `[0, 1]` validation and an optional non-negative random seed.
- Deterministic model validation with structured errors and warnings support.
- Attribute-reference validation to catch missing/non-numeric values before an execution engine is introduced.
- 82 dedicated ABM tests covering model construction and validation.

## Explicit V1 boundaries at completion of Milestone 1

- The execution engine and backend were implemented in Milestone 2 (see `ABM_MILESTONE2_REPORT.md`).
- No AI JSON parser or clarification flow yet.
- Static relationships only.
- Sequential activation in declaration order only.
- `MaxSteps` is the only termination condition.
- `SetAttribute` can introduce an attribute, but attributes read by a condition and attributes incremented by a rule must exist initially on all applicable agents.
- Stochastic probability is represented in the model contract and executed with an optional model-local random seed in Milestone 2.

## Files

- `simulations/abm/model.py`
- `simulations/abm/validation.py`
- `simulations/abm/__init__.py`
- `simulations/abm/README.md`
- `tests/abm/test_model.py`
- `tests/abm/test_validation.py`

## Verification in the authoring environment

- ABM-focused tests: **82 passed**.
- Full suite: **217 passed, 27 unittest subtests passed**.
- Python compileall: passed.

The authoring environment used temporary compatibility stubs for the existing DES external dependencies. The ABM-specific tests do not require SimPy or Groq. The full suite should be rerun in the user's reorganized Windows environment using the real installed dependencies.


## Follow-up

Milestone 2 adds the execution engine, immutable execution history, rule-evaluation trace, trajectories, and backend integration. See `ABM_MILESTONE2_REPORT.md`.
