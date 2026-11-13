# AI-Assisted Simulation Workbench

An extensible Python platform for helping people formalize, inspect and explore human ideas and theories, then translate sufficiently defined models into supported simulation paradigms.

## Current implementation

- Paradigm-independent conceptual modeling core: immutable original idea capture, append-only revisions, concepts, properties, relationships, mechanisms, hypotheses, assumptions, constraints, evidence references, mapping claims, open questions, strict JSON persistence, and structural validation.
- Knowledge retrieval and real-world mapping: local/imported knowledge corpora, BM25-style lexical retrieval, explained mapping candidates, source provenance, and explicit accept/reject decisions stored in new conceptual revisions.
- Discrete-event simulation (DES) using SimPy.
- AI-assisted DES interpretation and clarification using Groq.
- Hierarchical DES representation, validation, documented defaults and compilation.
- Shared simulation specification and backend registry.
- ABM V1 declarative model types, AI-assisted construction and clarification, deterministic validation, sequential execution, seeded stochastic rules, result history, and shared backend integration.
- AI-assisted idea interpretation, bounded clarification, uncertainty retention and element-level provenance (M6).

## Planned capabilities

- Readiness assessment and translation from conceptual structures into supported simulation representations.
- `simulations/mathematical`: Equation-to-Simulation using validated mathematical representations and numerical solvers.
- `simulations/data_driven`: Dataset profiling and guided/automatic data-to-model construction.

These are separate model families that will reuse the common backend contracts where appropriate. Not every planned capability is implemented yet; consult each package's README and milestone report for its exact status.

## Project structure

```text
conceptual/      Idea representation, provenance, revisions, JSON persistence and validation
knowledge/       Knowledge documents, local corpus, retrieval, mapping candidates and review workflow
idea_assistant/  M6 structured idea interpretation, clarification, provenance and session audit
simulations/
  core/          Shared specification and backend contracts
  des/           Discrete-event models, AI workflow, validation and execution
  abm/           ABM model contract, AI construction, validation, execution and backend
  mathematical/ Equation-to-Simulation (planned)
  data_driven/   Dataset-to-Simulation (planned)
tests/
  conceptual/    Conceptual model, validation, revision and serialization tests
  knowledge/     Corpus persistence, retrieval, filters, mapping and review workflow tests
  idea_assistant/ M6 parser, clarification, provenance and audit persistence tests
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

## Knowledge retrieval and mapping (M5)

The `knowledge/` package retrieves source records from a local JSON knowledge base and proposes possible correspondences for concepts in an `IdeaProject`. It includes a small curated seed corpus covering commons governance, cooperation, social networks and shared-resource dilemmas. Search is deterministic BM25-style lexical retrieval with field boosts and domain/source filters; relevance scores are ranking scores, not confidence or truth estimates.

Mapping candidates include matched terms, a source reference and an explicit caution that the result is only a comparison lead. The default recorded status is `unreviewed`. A person must explicitly accept or reject the mapping, and each decision is appended as a new conceptual revision. Original idea text and earlier revisions remain unchanged.

Run `python -m knowledge.demo` or choose option 5 from `python main.py`. See `knowledge/README.md`, `M5_ARCHITECTURE.md` and `MILESTONE5_REPORT.md` for the delivered scope, source-ingestion contract, limitations and test results.

## AI-assisted idea interpretation (M6)

Choose option 6 to describe a new idea, receive a structured conceptual draft, answer targeted clarification questions and save both the project and a clarification audit trail. The workflow preserves the exact original request, keeps unanswered questions open, and distinguishes verbatim user-grounded excerpts from AI inferences and AI suggestions. It can pass local M5 knowledge retrieval leads as context, but it does not treat them as proof or automatically create accepted mappings. M6 is paradigm-independent and does not execute a simulation. See `idea_assistant/README.md`, `M6_ARCHITECTURE.md` and `M6_TEST_REPORT.md`.
