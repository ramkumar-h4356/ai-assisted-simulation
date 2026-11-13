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
- Deterministic M8 compilation profiles that bind target-model fields to exact conceptual elements or explicitly documented experiment parameters, then validate against the real DES/ABM model schemas.
- M9 controlled execution of integrity-verified M8 artifacts, reproducible seeded ABM runs, deterministic DES runs, native trace capture, failure records and integrity-checked experiment-result persistence.
- M10 bounded Cartesian parameter sweeps over explicit M8 `user_parameter` bindings, replication orchestration through M9, descriptive per-variant statistics, baseline deltas, marginal factor-level analysis, integrity-checked reports and CSV export.

## Planned capabilities

- `simulations/mathematical`: Equation-to-Simulation using validated mathematical representations and numerical solvers.
- `simulations/data_driven`: Dataset profiling and guided/automatic data-to-model construction.
- Inferential statistics, confidence intervals, optimization, common-random-number designs, richer sensitivity analysis, visualization and evidence-grounded result interpretation (future milestones).

These are separate model families that will reuse the common backend contracts where appropriate. Not every planned capability is implemented yet; consult each package's README and milestone report for its exact status.

## Project structure

```text
conceptual/      Idea representation, provenance, revisions, JSON persistence and validation
knowledge/       Knowledge documents, local corpus, retrieval, mapping candidates and review workflow
idea_assistant/  M6 structured idea interpretation, clarification, provenance and session audit
readiness/       M7 deterministic readiness and four-paradigm suitability assessment
compilation/     M8 traceable conceptual-to-DES/ABM specification compilation
execution/       M9 controlled backend execution, experiment records and trace persistence
experimentation/ M10 bounded parameter grids, comparative statistics and analysis persistence
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
  readiness/     M7 paradigm-fit, readiness, clarification and report-persistence tests
  compilation/   M8 profile provenance, native-model validation, compilation gates and artifact integrity tests
  execution/     M9 seeded execution, trace capture, bounded failures and result integrity tests
  experimentation/ M10 grid generation, provenance-safe analysis, statistics and report-integrity tests
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


## Simulation readiness assessment (M7)

Choose option 7 to assess a saved M6 conceptual project or another conceptual JSON project. M7 runs deterministic evaluators for DES, ABM, mathematical and data-driven approaches. Each result includes qualitative fit, traceable findings, limitations, missing requirements and execution-backend availability. The engine can return multiple equally best-supported paradigms; it does not force a single winner.

DES and ABM are reported as implemented backends. Mathematical and data-driven are assessment-only: M7 can inspect conceptual suitability, but their execution engines have not yet been delivered. A dataset reference is not treated as proof that a data file can be accessed or is usable.

The report is persisted separately from the conceptual project and records the exact revision assessed. It never mutates an idea, calls an LLM, generates executable code or proves scientific validity. See `readiness/README.md`, `M7_ARCHITECTURE.md`, `MILESTONE7_REPORT.md` and `M7_TEST_REPORT.md`.


## Conceptual-to-executable specification compilation (M8)

Choose option 8 to compile a saved conceptual project into a target specification for DES V1 or ABM V1. M8 requires M7 to report `READY_FOR_IMPLEMENTATION_PLANNING` for the selected paradigm. It then requires a user-approved compilation profile containing the exact native target model data and provenance bindings. A binding either points to one or more element IDs in the selected conceptual revision or documents an experiment parameter supplied by the user.

This boundary is intentional: an idea such as “people cooperate when trust is high” does not uniquely define a population size, initial trust distribution, threshold, activation schedule or stopping condition. M8 does not invent those details. It validates the explicit target model with the existing DES/ABM parsers and semantic validators, and writes a revision-bound artifact with a SHA-256 model fingerprint. Unmapped conceptual elements are surfaced as warnings; at least one conceptual element and one mechanism must be represented.

If no profile path is supplied, option 8 creates an intentionally incomplete JSON template for editing. The profile schema and API are documented in `compilation/README.md`; run `python -m compilation.demo` for an offline ABM compilation example. M8 does not execute a simulation, and mathematical/data-driven remain assessment-only until their backends exist. See `M8_ARCHITECTURE.md`, `MILESTONE8_REPORT.md` and `M8_TEST_REPORT.md`.


## Controlled execution and result capture (M9)

Choose option 9 to load an integrity-checked M8 specification artifact and execute it through its implemented backend. The workflow accepts named parameter sets (optional JSON input) and replications per set, with at most 100 total executions. A parameter can vary only when its exact target path is already documented as an M8 `user_parameter`; conceptual bindings cannot be overwritten. ABM runs receive consecutive random seeds, while DES V1 is deterministic and does not consume random seeds. M9 captures full DES event logs or ABM state/rule histories alongside metrics. Option 10 inspects a saved experiment result.

Every M9 result records the M8 artifact ID and fingerprint, project ID, exact conceptual revision, paradigm, backend, run seeds and timestamps. Failed runs are saved with bounded error details; successful runs retain machine-readable traces. Result JSON is fingerprinted and verified when loaded. A 500,000-record estimated trace budget bounds output size. See `execution/README.md`, `M9_ARCHITECTURE.md`, `MILESTONE9_REPORT.md` and `M9_TEST_REPORT.md`.


## Experiment design and comparative analysis (M10)

Choose option 11 to create a parameter sweep from a JSON grid-factor file, run its variants through the existing M9 execution layer, and compare the results. A grid factor must point to an exact scalar field already declared as an M8 `user_parameter`; conceptual bindings and inferred fields cannot be varied. The grid is bounded by 100 total executions, including replications. The current values in the M8 artifact can be included as an explicit baseline.

M10 reports per-variant run counts, numeric means/population standard deviations/medians/ranges, categorical counts, numeric deltas versus baseline and marginal factor-level summaries. Option 11 can also include earlier M9 results, but only when they come from the same exact M8 artifact and conceptual revision. It saves a fingerprinted analysis JSON and a CSV summary. Option 12 inspects a saved M10 report.

These are descriptive summaries of simulated outcomes, not significance tests or proof of real-world effects. With multiple varied factors, level summaries are marginal across the other factors and interactions are not independently estimated. ABM comparisons currently use M9's consecutive unpaired seeds; the report warns about this limitation. See `experimentation/README.md`, `M10_ARCHITECTURE.md`, `MILESTONE10_REPORT.md` and `M10_TEST_REPORT.md`.
