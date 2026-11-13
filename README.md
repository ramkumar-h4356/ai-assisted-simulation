# AI-Assisted Simulation Workbench

An extensible Python platform for helping people formalize, inspect and explore human ideas and theories, then translate sufficiently defined models into supported simulation paradigms.

## Current implementation

- Paradigm-independent conceptual modeling core: immutable original idea capture, append-only revisions, concepts, properties, relationships, mechanisms, hypotheses, assumptions, constraints, evidence references, mapping claims, open questions, strict JSON persistence, and structural validation.
- Discrete-event simulation (DES) using SimPy.
- AI-assisted DES interpretation and clarification using Groq.
- Hierarchical DES representation, validation, documented defaults and compilation.
- Shared simulation specification and backend registry.
- ABM V1 declarative model types, AI-assisted construction and clarification, deterministic validation, sequential execution, seeded stochastic rules, result history, and shared backend integration.

## Planned capabilities

- Knowledge retrieval and real-world mapping assistance for conceptual models.
- AI-assisted conversational idea refinement and clarification.
- Readiness assessment and translation from conceptual structures into supported simulation representations.
- `simulations/mathematical`: Equation-to-Simulation using validated mathematical representations and numerical solvers.
- `simulations/data_driven`: Dataset profiling and guided/automatic data-to-model construction.

These are separate model families that will reuse the common backend contracts where appropriate. Not every planned capability is implemented yet; consult each package's README and milestone report for its exact status.

## Project structure

```text
conceptual/      Idea representation, provenance, revisions, JSON persistence and validation
simulations/
  core/          Shared specification and backend contracts
  des/           Discrete-event models, AI workflow, validation and execution
  abm/           ABM model contract, AI construction, validation, execution and backend
  mathematical/ Equation-to-Simulation (planned)
  data_driven/   Dataset-to-Simulation (planned)
tests/
  conceptual/    Conceptual model, validation, revision and serialization tests
  core/          Shared architecture tests
  des/           Discrete-event tests
  abm/           ABM schema, pipeline, model, validation, engine and backend tests
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements-dev.txt`.
3. Copy `.env.example` to `.env` and set `GROQ_API_KEY`.
4. Run tests: `python -m pytest`.
5. Start the CLI: `python main.py`.

## Conceptual layer

The `conceptual/` package is independent of DES and ABM execution. It preserves the original user statement and stores each refined conceptual model as an immutable revision. New concepts do not need real-world equivalents. Real-world mappings are explicit claims with a mapping type, rationale, evidence references and review state. Incomplete mechanisms and open questions are retained rather than silently converted into executable rules.

Run the included conceptual example with `python -m conceptual.demo`, or choose option 4 from `python main.py`. See `conceptual/README.md` and `MILESTONE4_REPORT.md` for scope and details.

## Architecture principles

- AI interprets requests and proposes structured models; it does not generate executable Python code for model rules.
- Deterministic Python validates and compiles models.
- Each simulation paradigm owns its model representation and execution semantics.
- Shared backend interfaces live in `simulations/core`.
- Stochastic models use an explicit random seed for reproducible experiments.
- Scientific credibility requires model verification, validation and uncertainty analysis; a successful run alone does not establish scientific correctness.
