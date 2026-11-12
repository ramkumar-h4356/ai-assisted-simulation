# Agent-Based Modelling (ABM V1)

This package provides a declarative agent-based model, deterministic validation,
a sequential execution engine, a shared backend adapter, and an AI-assisted
natural-language construction pipeline.

## Model concepts

- **Agent** — an individual entity with an identifier, type, state, and scalar attributes.
- **Environment** — global scalar attributes retained as model context in V1.
- **AgentRelationship** — a static directed or undirected connection between two agents.
- **BehaviourRule** — a condition, an ordered tuple of actions, an optional agent-type filter, and an execution probability.
- **ActivationPolicy** — V1 supports sequential activation in agent declaration order.
- **MaxSteps** — V1 termination condition; the model stops after a fixed positive number of steps.

## AI model-construction pipeline

Call `run_agent_prompt(request, ...)` from `simulations.abm.pipeline` to:

1. Ask Groq to translate the natural-language description into the ABM JSON schema.
2. Normalize internal agent references and rule IDs in Python.
3. Parse the schema into the typed `AgentModel` representation.
4. Ask the user to clarify missing or invalid fields, then request a complete revised model from the AI.
5. Run deterministic semantic validation.
6. Create an `AGENT_BASED` `SimulationSpecification`, resolve the registered ABM backend, and execute only a valid model.

The pipeline accepts `generate_fn` and `refine_fn` injection points for deterministic tests. It does not require a live Groq call during unit tests.

### AI safety and interpretation boundary

The AI can select only the documented condition and action types. It cannot provide Python functions, code snippets, callbacks, or arbitrary expressions. Python parses the JSON, generates final agent IDs (`agent-1`, `agent-2`, ...), resolves relationship aliases, validates the typed model, and runs the engine. Unknown required facts are not silently turned into operational values.

The model-construction interface expects explicit individual agents. V1 supports small explicit populations (the AI prompt caps expansion at 100 individuals). Larger population templates, bulk agent generation, spatial movement, dynamic relationships, and network-generation methods are future work.

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
5. If a condition matches, the rule's probability is evaluated. Probabilities `0` and `1` are deterministic; intermediate probabilities use the model's seeded random generator.
6. Actions are applied immediately and in declaration order. A later rule for the same agent, or a later agent in the same step, observes committed changes.
7. Actions belonging to one rule are applied atomically to temporary agent values. A failed action does not partially update that agent for that rule.
8. An undirected relationship is visible from both endpoints. For a directed relationship, the source agent sees the target as an outgoing neighbour; the target does not see the source through that edge.
9. The model runs for exactly the configured `MaxSteps` unless a runtime error occurs.

The engine does not currently provide simultaneous activation, random activation order, dynamic relationships, spatial movement, environment mutation, or early-stop conditions.

## Results and reproducibility

`ABMSimulationResult` contains:

- An initial snapshot and one population snapshot after every completed step.
- A rule-evaluation trace, including condition and probability outcomes.
- Final population counts grouped by agent state.
- `trajectory(agent_id)`, which returns the recorded state and attributes for one agent.

When `random_seed` is an integer, stochastic rule execution is reproducible for the same model and compatible runtime implementation. When it is `None`, the random generator is not seeded explicitly.

## Backend integration and validation

`AgentBasedBackend` implements the shared `SimulationBackend` protocol and accepts `SimulationSpecification` objects whose paradigm is `AGENT_BASED` and whose model is an `AgentModel`.

Call `validate_agent_model(model)` to inspect a model without executing it. The engine and natural-language pipeline both call the validator, so invalid models cannot be run accidentally.

The AI must map user descriptions into the declarative schema. It must not provide executable Python code for model rules.

## Example schema

See `scenarios/disease_transmission_abm.json` for a complete three-agent network example. It can be parsed with `agent_model_from_dict` and passed to `run_agent_model`.
