# ABM Milestone 2 — Execution Engine and Backend

## Delivered

- Sequential, declaration-order agent activation.
- Behaviour rules evaluated in declaration order for each applicable agent.
- Immediate action commits, visible to subsequent rules and later agents in the same step.
- Conditions: agent state, agent attribute comparisons, related-agent state counts, `AllOf`, and `AnyOf`.
- Actions: set state, set attribute, and increment numeric attribute.
- Rule probability support using a model-local random generator and optional seed.
- Static undirected and directed relationship queries. Directed relationships are outgoing from source to target.
- Initial and per-step population snapshots.
- Per-agent trajectory extraction.
- Rule-evaluation trace and final state counts.
- Rule action batches are atomic for an individual agent.
- `AgentBasedBackend` implements the shared backend interface and can be registered in `BackendRegistry`.

## Execution contract

The engine validates the model before execution and raises on validation errors. The initial population is snapshot step 0. Exactly `MaxSteps.value` steps execute. Every agent activates once per step in declaration order. Each applicable rule is considered once per activation in declaration order. A matched rule evaluates its probability; 0 and 1 do not consume a random draw, while values strictly between 0 and 1 use the model-local PRNG. Actions apply immediately. A failed action batch does not partially commit that rule's changes.

## Tests added

- Engine semantics and snapshots.
- Sequential ordering and same-step visibility.
- Directed and undirected neighbour behaviour.
- Attribute conditions and mutations.
- Composite conditions and agent-type filters.
- Probability boundaries and seeded reproducibility.
- Rule trace, trajectories, final state counts and runtime error handling.
- Backend contract and shared registry integration.

## Verification in the authoring environment

- ABM-focused suite: **113 passed** without SimPy/Groq compatibility stubs.
- Full repository suite: **248 passed, 27 unittest subtests passed** using the project's temporary compatibility stubs for the unavailable DES-only external dependencies in this authoring environment.
- Python `compileall`: passed.
- Standalone three-agent disease-transmission smoke test: all 3 agents reached the infected state after 2 sequential steps.
- Backend/registry smoke test: passed.

The full suite in this environment used temporary test stubs because `simpy` and `groq` are not installed here. Run `python -m pytest` in the user's reorganized Windows environment, where the real dependencies are installed, before accepting the patch.

## Explicitly not included

- AI parsing or JSON schema for ABM models.
- Clarification workflow for ABM.
- Simultaneous or random activation.
- Dynamic relationships or spatial movement.
- Environment mutation.
- Early-stop termination conditions.
- Visualization or CLI integration.
