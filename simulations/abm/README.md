# Agent-Based Simulation (ABM V1)

This package provides a declarative agent-based model, deterministic validation, a sequential execution engine, and a backend adapter for the platform's shared simulation architecture.

## Model concepts

- **Agent** — an individual entity with an identifier, type, state, and scalar attributes.
- **Environment** — global scalar attributes retained as model context in V1.
- **AgentRelationship** — a static directed or undirected connection between two agents.
- **BehaviourRule** — a condition, an ordered tuple of actions, an optional agent-type filter, and an execution probability.
- **ActivationPolicy** — V1 supports sequential activation in agent declaration order.
- **MaxSteps** — V1 termination condition; the model stops after a fixed positive number of steps.

## Supported conditions

- `AgentStateIs`: compare the active agent's state.
- `AgentAttributeComparison`: compare one of the active agent's attributes using `eq`, `ne`, `lt`, `le`, `gt`, or `ge`.
- `RelatedAgentStateCount`: count connected agents of a specified state and relationship type, then compare the count.
- `AllOf` and `AnyOf`: combine nested conditions.

## Supported actions

- `SetState`: replace the active agent's state.
- `SetAttribute`: add or replace a scalar agent attribute.
- `IncrementAttribute`: increment an existing numeric agent attribute.

## Execution semantics

`AgentBasedSimulationEngine.run(model)` validates the model before execution. It raises `ValueError` for validation errors and returns an `ABMSimulationResult` for a valid model.

1. The result records the initial population as step `0`.
2. For each step, agents activate in declaration order.
3. For each agent, applicable rules execute in behaviour declaration order.
4. Each rule is evaluated at most once per agent per step.
5. If a condition matches, the rule's probability is evaluated. Probabilities `0` and `1` are handled deterministically; intermediate probabilities use the model's seeded random generator.
6. Actions are applied immediately and in declaration order. A later rule for the same agent, or a later agent in the same step, observes committed changes.
7. Actions belonging to one rule are applied atomically to temporary agent values. A failed action does not partially update that agent for that rule.
8. An undirected relationship is visible from both endpoints. For a directed relationship, the source agent sees the target as an outgoing neighbour; the target does not see the source through that edge.
9. The model runs for exactly the configured `MaxSteps` unless a runtime error occurs.

The engine does not currently provide simultaneous activation, random activation order, dynamic relationships, spatial movement, environment mutation, or early-stop conditions. These are possible future extensions, not V1 behaviour.

## Results and reproducibility

`ABMSimulationResult` contains:

- An initial snapshot and one population snapshot after every completed step.
- A rule-evaluation trace, including condition and probability outcomes.
- Final population counts grouped by agent state.
- `trajectory(agent_id)`, which returns the recorded state and attributes for one agent.

When `random_seed` is an integer, stochastic rule execution is reproducible for the same model and compatible runtime implementation. When it is `None`, the random generator is not seeded explicitly.

## Backend integration

`AgentBasedBackend` implements the shared `SimulationBackend` protocol and accepts `SimulationSpecification` objects whose paradigm is `AGENT_BASED` and whose model is an `AgentModel`. Register it with the shared `BackendRegistry` to make the paradigm available to the application.

## Validation boundary

Call `validate_agent_model(model)` to inspect a model without executing it. Its `ValidationReport` separates errors and warnings. The engine calls the validator itself, so invalid models cannot be run accidentally.

The validator checks agent IDs, relationship endpoints, duplicate relationships, rule IDs, agent type filters, supported conditions and actions, condition attributes, increment attributes, probability bounds, termination type, and random seed.

The AI must map user descriptions into these declarative types. It must not provide executable Python code for conditions or actions.
