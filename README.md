# AI-Assisted Simulation Workbench

An extensible Python platform for turning natural-language descriptions and supported datasets into inspectable, validated simulation models.

## Current implementation

- Discrete-event simulation (DES) using SimPy.
- AI-assisted DES interpretation and clarification using Groq.
- Hierarchical DES representation, validation, documented defaults and compilation.
- Shared simulation specification and backend registry.
- ABM V1 declarative model types, deterministic validation, sequential execution, seeded stochastic rules, result history, and shared backend integration.

## Planned capabilities

- `simulations/abm`: Agent-Based Simulation execution and backend integration.
- `simulations/mathematical`: Equation-to-Simulation using validated mathematical representations and numerical solvers.
- `simulations/data_driven`: Dataset profiling and guided/automatic data-to-model construction.

These are separate model families that will reuse the common backend contracts where appropriate. Not every planned capability is implemented yet; consult each package's README and milestone report for its exact status.

## Project structure

```text
simulations/
  core/          Shared specification and backend contracts
  des/           Discrete-event models, AI workflow, validation and execution
  abm/           ABM model contract, validation, execution engine and backend
  mathematical/ Equation-to-Simulation (planned)
  data_driven/   Dataset-to-Simulation (planned)
tests/
  core/          Shared architecture tests
  des/           Discrete-event tests
  abm/           ABM model, validation, engine and backend tests
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements-dev.txt`.
3. Copy `.env.example` to `.env` and set `GROQ_API_KEY`.
4. Run tests: `python -m pytest`.
5. Start the CLI: `python main.py`.

## Architecture principles

- AI interprets requests and proposes structured models; it does not generate executable Python code for model rules.
- Deterministic Python validates and compiles models.
- Each simulation paradigm owns its model representation and execution semantics.
- Shared backend interfaces live in `simulations/core`.
- Stochastic models use an explicit random seed for reproducible experiments.
- Scientific credibility requires model verification, validation and uncertainty analysis; a successful run alone does not establish scientific correctness.
