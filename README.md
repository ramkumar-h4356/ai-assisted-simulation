# AI-Assisted Simulation Workbench

An extensible Python platform for helping people formalize, inspect and explore human ideas and theories, then translate sufficiently defined models into supported simulation paradigms.

## Current implementation

- Paradigm-independent conceptual modeling core: immutable original idea capture, append-only revisions, concepts, properties, relationships, mechanisms, hypotheses, assumptions, constraints, evidence references, mapping claims, open questions, strict JSON persistence, and structural validation.
- Knowledge retrieval and real-world mapping: local/imported knowledge corpora, BM25-style lexical retrieval, explained mapping candidates, source provenance, and explicit accept/reject decisions stored in new conceptual revisions.
- Discrete-event simulation (DES) using SimPy.
- AI-assisted DES interpretation and clarification using Groq.
- Hierarchical DES representation, validation, documented defaults and compilation.
- Shared simulation specification and backend registry.
- ABM declarative model types, AI-assisted construction and clarification, deterministic validation, sequential execution, seeded stochastic rules, result history, and shared backend integration.
- M16 spatial ABM extension: explicit 2D world dimensions, per-agent coordinates, clamp/wrap boundaries, relative/absolute movement actions, Euclidean neighbourhood conditions, position-recording M9 traces, and spatial replay in the browser.
- M17 advanced spatial mechanics: static rectangular/circular obstacles, circular agent bodies, agent/agent collision checks, deterministic block/slide movement resolution, cumulative per-step movement budgets, bounded direct/A* navigation, and persisted movement-event traces.
- M18 spatial environments: uniform world grids, polygon regions and navigation zones, environmental objects with collision footprints, weighted/impassable terrain routing, and a spatial hash index for efficient live neighbourhood queries.
- M19 DES replay: stable event timelines, per-entity multi-stage journeys, queue-length and wait intervals, resource occupancy/utilization, event/entity/resource inspection helpers, and provenance-checked replay from saved M9 runs.
- M20 mathematical simulation: validated ODE model contracts, safe expression parsing (no dynamic Python evaluation), deterministic Euler/Heun/RK4 solvers, coupled-state integration, time-series traces, variable summaries, and M7/M8/M9/workspace integration.
- M21 data-driven simulation: strict multivariate time-series model contracts, explicit bounded CSV ingestion, deterministic ridge-VAR(p) fitting, chronological holdout evaluation, recursive forecasting, dataset-evidence provenance and M7/M8/M9/workspace integration. Its coefficients are predictive associations, not causal rules.
- AI-assisted idea interpretation, bounded clarification, uncertainty retention and element-level provenance (M6).
- Deterministic M8 compilation profiles that bind target-model fields to exact conceptual elements or explicitly documented experiment parameters, then validate against the DES/ABM/mathematical/data-driven model schemas.
- M9 controlled execution of integrity-verified M8 artifacts, reproducible seeded ABM runs, deterministic DES/mathematical/data-driven runs, native trace capture, failure records and integrity-checked experiment-result persistence.
- M10 bounded Cartesian parameter sweeps over explicit M8 `user_parameter` bindings, replication orchestration through M9, descriptive per-variant statistics, baseline deltas, marginal factor-level analysis, integrity-checked reports and CSV export.
- M11 reproducible Monte Carlo sampling of numeric M8 `user_parameter` fields, outcome distributions, Spearman sensitivity screening, user-defined robustness criteria, provenance checks and integrity-checked JSON/CSV reports.
- M12 engine-independent visualization bundles and standalone offline HTML dashboards for M9 run metrics and DES/ABM traces, with optional provenance-matched M10 and M11 analysis panels. Mathematical and data-driven dedicated time-series dashboard rendering are not implemented.
- M13 persistent project workspaces with integrated M5 knowledge retrieval/mapping review and M6 interpretation/clarification, strict milestone-artifact intake, project/revision lineage checks, SHA-256 integrity verification, project-scoped M7–M12 orchestration, ZIP import/export, and a controlled extension contract for simulation paradigms.
- M14 local browser workbench and versioned FastAPI API for workspace management, artifact intake/download, M7 readiness, M8 compilation, M9 execution, M10 sweeps/analysis, M11 uncertainty, M12 dashboard preview, verification and export.

## Planned capabilities

- Inferential statistics, confidence intervals, variance-based global sensitivity indices, optimization, common-random-number designs and evidence-grounded result interpretation (future milestones).

These are separate model families that will reuse the common backend contracts where appropriate. Not every planned capability is implemented yet; consult each package's README and milestone report for its exact status.

## Project structure

```text
conceptual/      Idea representation, provenance, revisions, JSON persistence and validation
knowledge/       Knowledge documents, local corpus, retrieval, mapping candidates and review workflow
idea_assistant/  M6 structured idea interpretation, clarification, provenance and session audit
readiness/       M7 deterministic readiness and four-paradigm suitability assessment
compilation/     M8 traceable conceptual-to-DES/ABM/mathematical specification compilation
execution/       M9 controlled backend execution, experiment records and trace persistence
experimentation/ M10 bounded parameter grids, comparative statistics and analysis persistence
uncertainty/     M11 Monte Carlo input sampling, sensitivity screening and robustness analysis
visualization/   M12 engine-independent dashboard data, trace adapters, JSON integrity and standalone HTML rendering
workbench/      M13 project workspaces, artifact validation, provenance, orchestration, extension registry and CLI
webapp/         M14 local FastAPI service and browser UI for the integrated project lifecycle
simulation_studio/ M15/M16 trace-backed 2D ABM replay plus M19 provenance-checked DES run replay
simulations/
  core/          Shared specification and backend contracts
  des/           Discrete-event models, AI workflow, validation, execution and M19 trace replay
  abm/           ABM model contract, AI construction, validation, execution and backend
  mathematical/ Validated ODE models, safe expression evaluator, fixed-step solvers and time-series results (M20)
  data_driven/   Deterministic ridge-VAR(p) model, CSV ingestion and forecasting (M21)
tests/
  conceptual/    Conceptual model, validation, revision and serialization tests
  knowledge/     Corpus persistence, retrieval, filters, mapping and review workflow tests
  idea_assistant/ M6 parser, clarification, provenance and audit persistence tests
  core/          Shared architecture tests
  des/           Discrete-event tests
  abm/           ABM schema, pipeline, model, validation, engine and backend tests
  readiness/     M7 paradigm-fit, readiness, clarification and report-persistence tests
  compilation/   M8 profile provenance, native-model validation, compilation gates and artifact integrity tests
  execution/     M9 seeded execution, mathematical time-series trace capture, bounded failures and result integrity tests
  mathematical/  M20 ODE model validation, safe expression parsing, Euler/Heun/RK4 solver and coupled-system tests
  simulation_studio/ M15/M16 ABM replay and M19 DES replay, event inspection and provenance checks
  experimentation/ M10 grid generation, provenance-safe analysis, statistics and report-integrity tests
  uncertainty/    M11 distribution sampling, M9 execution checks, sensitivity, robustness and report-integrity tests
  visualization/ M12 DES/ABM trace adapters, cross-milestone provenance, dashboard rendering and bundle-integrity tests
  workbench/     M13 workspace persistence, artifact lineage, ZIP portability, extension registry and end-to-end workflow tests
```

## Setup

1. Create and activate a virtual environment.
2. Install dependencies: `python -m pip install -r requirements-dev.txt`.
3. Copy `.env.example` to `.env` and set `GROQ_API_KEY`.
4. Run tests: `python -m pytest`.
5. Start the CLI: `python main.py` (option 17 opens the M13 Project Workbench; options 18–19 run/inspect M23 optimization; options 20–21 run/inspect M24 experiment suites).
6. The standalone workspace manager is also available with `python -m workbench`.
7. Start the M14 browser workbench with `python -m webapp`, then open `http://127.0.0.1:8765`.

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

DES, ABM, mathematical and data-driven simulation now have implemented backends (mathematical in M20; data-driven in M21). M7 still evaluates conceptual suitability only: a dataset reference does not prove the file is accessible or usable. M21 compilation requires validated observations embedded in an explicit user-approved M8 profile.

The report is persisted separately from the conceptual project and records the exact revision assessed. It never mutates an idea, calls an LLM, generates executable code or proves scientific validity. See `readiness/README.md`, `M7_ARCHITECTURE.md`, `MILESTONE7_REPORT.md` and `M7_TEST_REPORT.md`.


## Conceptual-to-executable specification compilation (M8)

Choose option 8 to compile a saved conceptual project into a target specification for DES V1, ABM V1, Mathematical V1 or Data-Driven V1. M8 requires M7 to report `READY_FOR_IMPLEMENTATION_PLANNING` for the selected paradigm. It then requires a user-approved compilation profile containing the exact native target model data and provenance bindings. A binding either points to one or more element IDs in the selected conceptual revision or documents an experiment parameter supplied by the user.

This boundary is intentional: an idea such as “people cooperate when trust is high” does not uniquely define a population size, initial trust distribution, threshold, activation schedule or stopping condition. M8 does not invent those details. It validates the explicit target model with the corresponding paradigm validator, and writes a revision-bound artifact with a SHA-256 model fingerprint. Unmapped conceptual elements are surfaced as warnings; at least one conceptual element must be represented, plus an operational mechanism for DES/ABM or a quantitative relationship/operational mechanism for mathematical models.

If no profile path is supplied, option 8 creates an intentionally incomplete JSON template for editing. The profile schema and API are documented in `compilation/README.md`; run `python -m compilation.demo` for an offline ABM compilation example. M8 does not execute a simulation. Mathematical ODE profiles require explicit equations and a provenance binding to a quantitative relationship or operational mechanism. Data-driven profiles require a dataset evidence reference bound to the exact `dataset_reference_id` plus validated observations. See `M8_ARCHITECTURE.md`, `MILESTONE8_REPORT.md` and `M8_TEST_REPORT.md`.


## Controlled execution and result capture (M9)

Choose option 9 to load an integrity-checked M8 specification artifact and execute it through its implemented backend. The workflow accepts named parameter sets (optional JSON input) and replications per set, with at most 100 total executions. A parameter can vary only when its exact target path is already documented as an M8 `user_parameter`; conceptual bindings cannot be overwritten. ABM runs receive consecutive random seeds, while DES, mathematical and data-driven V1 are deterministic and do not consume random seeds. M9 captures DES event/replay logs, ABM state/rule histories, mathematical ODE time series or data-driven model coefficients, holdout evaluation and recursive forecasts alongside metrics. Option 10 inspects a saved experiment result.

Every M9 result records the M8 artifact ID and fingerprint, project ID, exact conceptual revision, paradigm, backend, run seeds and timestamps. Failed runs are saved with bounded error details; successful runs retain machine-readable traces. Result JSON is fingerprinted and verified when loaded. A 500,000-record estimated trace budget bounds output size. See `execution/README.md`, `M9_ARCHITECTURE.md`, `MILESTONE9_REPORT.md` and `M9_TEST_REPORT.md`.


## Discrete-event simulation replay (M19)

M19 derives a replay projection from the canonical event log already recorded by the DES engine. The timeline keeps the original event order and provides a stable sequence number. Each entity gains an ordered stage journey with arrival, service-start, completion, queue-wait and service-time values. Each resource gains occupancy intervals, peak concurrency, queue intervals, queue-length intervals, peak queue length and utilization normalized by capacity and the observed simulation horizon.

The M9 DES trace now stores `resource_capacities` and a `replay` object while retaining the existing `events`, `entities` and `resources` fields. The execution result fingerprint covers the additional data. `simulation_studio.build_des_run_replay(result, compilation, run_index=1)` validates the M8/M9 fingerprints and project/revision lineage, then recomputes the projection from the canonical event log. The lower-level inspection helpers `query_des_events`, `get_des_event`, `get_entity_journey` and `get_resource_replay` are available from `simulations.des.replay`.

Replay is post-run, not a live or animated simulation. The current DES runtime records arrivals, service starts and completions only; cancellation, preemption and arbitrary custom event types are not yet part of the replay contract. See `M19_ARCHITECTURE.md`, `M19_TEST_REPORT.md` and `scenarios/des/two_stage_clinic_replay.json`.


## Experiment design and comparative analysis (M10)

Choose option 11 to create a parameter sweep from a JSON grid-factor file, run its variants through the existing M9 execution layer, and compare the results. A grid factor must point to an exact scalar field already declared as an M8 `user_parameter`; conceptual bindings and inferred fields cannot be varied. The grid is bounded by 100 total executions, including replications. The current values in the M8 artifact can be included as an explicit baseline.

M10 reports per-variant run counts, numeric means/population standard deviations/medians/ranges, categorical counts, numeric deltas versus baseline and marginal factor-level summaries. Option 11 can also include earlier M9 results, but only when they come from the same exact M8 artifact and conceptual revision. It saves a fingerprinted analysis JSON and a CSV summary. Option 12 inspects a saved M10 report.

These are descriptive summaries of simulated outcomes, not significance tests or proof of real-world effects. With multiple varied factors, level summaries are marginal across the other factors and interactions are not independently estimated. ABM comparisons currently use M9's consecutive unpaired seeds; the report warns about this limitation. See `experimentation/README.md`, `M10_ARCHITECTURE.md`, `MILESTONE10_REPORT.md` and `M10_TEST_REPORT.md`.


## Sensitivity, uncertainty and robustness analysis (M11)

Choose option 13 to load an M8 artifact and an M11 uncertainty-plan JSON file. The plan declares numeric input parameters, uniform or triangular distributions, a reproducible sampling seed, and optional output acceptance criteria. M11 creates 3–100 parameter samples and executes exactly one run per sample through M9. The workflow saves the M9 sampled execution result, a fingerprinted M11 JSON report and a CSV export. Option 14 inspects a saved report. An illustrative plan is available at `scenarios/uncertainty/plan_example.json`; its paths must be checked against the selected artifact's actual M8 `user_parameter` bindings.

M11 reports output means, population standard deviations, medians, interpolated 5th/95th percentiles and observed ranges. Spearman rank correlations provide exploratory monotonic sensitivity screening. User-defined `<=`, `>=` and `between` criteria are evaluated individually and jointly. For ABM, output spread includes both sampled input variation and stochastic run-to-run variation; V1 does not separate them. Spearman scores are not causal effects, and robustness fractions are finite-sample observed proportions—not real-world probabilities or proof of theory validity. See `uncertainty/README.md`, `M11_ARCHITECTURE.md`, `MILESTONE11_REPORT.md` and `M11_TEST_REPORT.md`.


## Simulation visualization and interactive exploration (M12)

Choose option 15 to build a standalone visualization dashboard from an integrity-verified M9 execution result. You can optionally attach an M10 comparative report and/or an M11 uncertainty report, but each attachment must refer to the exact same M8 artifact and the exact M9 result selected for the dashboard. M12 writes an integrity-checked visualization JSON bundle and a self-contained HTML dashboard under `outputs/`. Choose option 16 to open a saved dashboard in your default browser.

The HTML dashboard requires no Python server, CDN, external library or internet connection. It includes run-level numeric metric trends, run summaries and a selectable paradigm-specific trace view. DES views show event timing, entity outcomes and resource utilization. ABM views aggregate recorded agent states over simulation steps, final population by agent type, numeric attribute means and rule-evaluation counts. When matching reports are attached, the dashboard also presents M10 variant summaries and M11 outcome distributions, sensitivity scores and robustness criteria. Large traces are deterministically downsampled for display only; original M9 records are not modified.

M12 visualizations are descriptive presentations of recorded model outputs. They do not establish that a model is valid, infer spatial movement or interactions absent from the trace, prove a theory, or turn observed proportions into real-world probabilities. See `visualization/README.md`, `M12_ARCHITECTURE.md`, `MILESTONE12_REPORT.md` and `M12_TEST_REPORT.md`.


## Integrated project workspace (M13)

Choose option 17 from `python main.py`, or run `python -m workbench`, to create and reopen persistent project workspaces. A workspace captures the original idea and groups M4 conceptual projects, M5 knowledge bases and mapping revisions, M6 clarification sessions, M7 readiness reports, M8 profiles and compiled artifacts, M9 execution results, M10 analysis reports, M11 uncertainty plans/reports and M12 visualization bundles/HTML dashboards.

M6 interpretation and clarification can now run directly against the workspace's immutable original idea. M5 mapping can retrieve candidates from the bundled knowledge corpus or a custom imported M5 corpus, record a candidate as unreviewed, and append a separate user accept/reject decision. Mapping relevance is not treated as confidence or proof. Existing M4/M5/M6 artifacts can also be imported.

Once a conceptual project is linked, run M7 assessment, import an explicit user-approved M8 compilation profile, compile it, execute DES/ABM/mathematical/data-driven/system-dynamics models, run M10 sweeps/analysis, run M11 uncertainty and build supported M12 visualizations directly within the project workspace. Generated outputs are stored automatically. The workbench enforces project/revision lineage and exact result fingerprints; it does not bypass readiness or compilation gates or invent missing executable model details.

Each copied artifact has a SHA-256 digest and byte-size record. The workbench verifies integrity before export and supports a portable workspace ZIP. ZIP import rejects unsafe paths and duplicate entries. Local workspace data is stored under the ignored `workspaces/` directory; export a workspace explicitly when you need to back it up or move it. See `workbench/README.md`, `M13_ARCHITECTURE.md`, `MILESTONE13_REPORT.md` and `M13_TEST_REPORT.md`.

The extension registry registers DES V1, ABM V1, Mathematical V1, Data-Driven V1 and System Dynamics V1 lifecycle adapters through a controlled application-code registry; it does not dynamically load arbitrary third-party code. M13 delivered the local CLI/service layer; M14 adds a first local browser UI/API, but the full interactive spatial 2D environment remains future work.


## M14 local browser workbench

Run `python -m webapp` after installing `requirements-dev.txt`, then open `http://127.0.0.1:8765`. The server binds to loopback by default and refuses non-local bind addresses from its CLI. Workspaces remain under the local `workspaces/` directory.

The browser UI supports workspace creation/opening, validated milestone-artifact upload, M7 readiness, M8 profile compilation, M9 execution, M10 parameter sweeps and descriptive analysis, M11 uncertainty runs, M12 dashboard generation/preview, integrity checks and workspace ZIP export. M20 mathematical runs can be compiled and executed through the shared service/API; a dedicated mathematical time-series dashboard is still future work. The API is versioned under `/api/v1`; its OpenAPI schema is available at `/api/openapi.json`.

M14 does not yet replace the M13 CLI for interactive M6 clarification or M5 mapping review. It did not add real-time 2D spatial rendering, authentication or multi-user hosting. Do not expose this local service to a network; remote deployment requires a separate security milestone. See `M14_ARCHITECTURE.md` and `webapp/README.md`.


## M15 interactive ABM replay

M15 adds an interactive 2D replay panel to the M14 browser workbench. Select a verified M9 ABM execution result to view its agents and M8 relationships, scrub recorded simulation steps, play/pause at selectable speeds, inspect per-agent attributes, and review rule-evaluation outcomes. The replay is reconstructed from the exact integrity-checked M8/M9 artifacts and does not modify project files.

Non-spatial models use a deterministic display layout; M16 spatial models use actual recorded positions and movement from M9. DES event playback remains future work. See `M15_ARCHITECTURE.md`, `MILESTONE15_REPORT.md` and `M15_TEST_REPORT.md`.

## M16 spatial ABM

M16 extends ABM with an optional 2D `space` contract, per-agent starting `position`, `move_by` and `move_to` actions, and `spatial_neighbour_state_count` conditions. `clamp` boundaries keep agents within the rectangular world; `wrap` boundaries connect opposite edges and use shortest wrapped Euclidean distance for neighbourhood queries. Spatial positions are included in every M9 history frame and replayed by the browser. Existing non-spatial M8 models continue to use the M15 presentation-only layout. See `M16_ARCHITECTURE.md`, `MILESTONE16_REPORT.md`, `M16_TEST_REPORT.md` and `simulations/abm/README.md`.

## M17 advanced spatial mechanics

M17 adds static rectangular and circular obstacles, optional circular agent bodies, agent-agent collision prevention, block/slide movement resolution, cumulative per-step movement limits, and `move_towards` using direct or deterministic A* routes. A* uses an 8-connected grid, prevents diagonal corner-cutting, checks accepted route segments against continuous obstacle/body geometry, requires clamp boundaries and is bounded to 100,000 cells. Movement events are persisted in M9 traces and attached to replay frames. Rectangle clearance is conservative around corners. Sequential activation is unchanged: earlier committed movements affect later agents in the same step. See `M17_ARCHITECTURE.md`, `MILESTONE17_REPORT.md`, `M17_TEST_REPORT.md` and `simulations/abm/README.md`.

## M18 spatial environment and navigation

M18 adds optional `space.grid`, polygon `regions`, polygon `zones`, and positioned environmental `objects`. Regions provide semantic areas and scalar attributes. Zones can be impassable or assign a navigation cost of at least `1.0`; overlapping zone costs multiply. Blocking environmental objects use circular footprints and participate in the same movement checks as obstacles. A* now considers both impassable zones and weighted terrain while retaining the 100,000-cell safety limit. `SpatialIndex` provides deterministic radius and rectangle queries with dynamic insert/move/remove operations; the ABM engine uses it for live spatial-neighbour conditions and updates it after committed movement. The configured `space.grid.cell_size` controls spatial-index buckets and grid coordinate helpers; each `move_towards.grid_cell_size` continues to control A* resolution independently. Polygon area boundaries count as inside, and touching an impassable zone is blocked. Environmental geometry is static for one run; dynamic object/zone updates and environmental interaction rules remain future work. See `M18_ARCHITECTURE.md`, `MILESTONE18_REPORT.md`, `M18_TEST_REPORT.md` and `simulations/abm/README.md`.


## M20 mathematical simulation engine

M20 adds deterministic fixed-step ordinary differential equation (ODE) execution. Mathematical models declare a finite simulation time range, step size, solver (`euler`, `heun` or `rk4`), state variables with initial values and derivative expressions, and named numeric parameters. Expressions are parsed using Python's AST but evaluated by a strict allow-listed interpreter; arbitrary Python execution, attribute access, indexing, imports and unknown identifiers are rejected. Coupled derivatives are evaluated from the same intermediate state during each solver stage.

M20 connects the mathematical model contract to M7 readiness, M8 provenance-bound compilation, M9 execution records, parameter overrides and the M13 workspace extension registry. Saved M9 results include every integration time point, values per variable, solver metadata and initial/final/minimum/maximum summaries. Fixed-step ODEs are supported; adaptive/stiff solvers, algebraic equation systems, PDEs, symbolic equation discovery, scientific parameter estimation and dedicated M12 mathematical dashboard rendering remain out of scope. Example: `python -m simulations.mathematical.demo`. See `simulations/mathematical/README.md`, `M20_ARCHITECTURE.md`, `MILESTONE20_REPORT.md` and `M20_TEST_REPORT.md`.

## Data-driven simulation and forecasting (M21)

M21 adds a deterministic ridge-regularized VAR(p) backend for regularly spaced multivariate numeric time series. An M8 data-driven profile declares the exact dataset evidence-reference ID, time field/unit, observed variables, ordered observations, lag order, chronological training fraction, ridge strength and forecast horizon. CSVs can be imported with `simulations.data_driven.load_csv_model_data(...)`; selected numeric columns are validated and embedded into the profile so the compiled artifact and execution remain portable. In M13 workspaces, data-driven readiness, compilation and execution are available through the built-in `builtin.data_driven.v1` adapter.

M21 evaluates one-step predictions on a chronological holdout segment and then creates a recursive forecast from the final observed window. Traces retain the dataset reference, fitted coefficients, holdout predictions, error metrics and forecast values. The model discovers predictive statistical associations only: VAR coefficients are not causal rules, do not validate the underlying theory and should not be interpreted as physical mechanisms. V1 requires regular numeric time intervals and complete numeric values; irregular observations, categorical fields, automatic causal discovery and M12 data-driven visualization are not implemented. See `simulations/data_driven/README.md`, `M21_ARCHITECTURE.md`, `M21_TEST_REPORT.md` and `MILESTONE21_REPORT.md`.


## System dynamics simulation (M22)

M22 adds deterministic stock-and-flow execution with named stocks, directed inflows/outflows/transfers, optional auxiliary equations, parameters and fixed-step Euler, Heun or RK4 integration. Flow rates are non-negative and direction is represented explicitly with source and target stocks. Auxiliary equations are dependency-ordered and circular auxiliary definitions are rejected. Each saved M9 trace includes stock levels, auxiliary values, instantaneous flow rates, stock summaries and trapezoidally integrated cumulative flow. The capability is available through M7 readiness, M8 compilation and provenance, M9 execution, and the M13 built-in extension registry. V1 does not yet include delay structures, table functions, stochastic/hybrid flows, automated feedback-loop discovery, dimensional unit algebra, or adaptive/stiff solvers. Example: `python -m simulations.system_dynamics.demo`. See `simulations/system_dynamics/README.md`, `M22_ARCHITECTURE.md`, `MILESTONE22_REPORT.md` and `M22_TEST_REPORT.md`.

## Objective-driven simulation optimization (M23)

M23 adds bounded, seeded uniform random search over numeric M8 `user_parameter`
bindings. A plan specifies one objective metric to minimize or maximize,
parameter bounds, an optional compiled baseline, replications and optional
metric constraints. All candidates execute through the same integrity-checked
M9 service; the resulting M9 execution JSON, M23 fingerprinted report and CSV
candidate table are saved separately. The M23 report preserves the exact M8
artifact/revision and M9 result fingerprint. The optimizer supports the M9
backends implemented at this milestone: DES, ABM, mathematical, data-driven
and system dynamics.

M23 complements M10 grid comparisons and M11 uncertainty/sensitivity
analysis; it does not replace either. V1 is single-objective random search,
not a global-optimum guarantee. ABM candidates use M9's sequential seeds and
are not paired common-random-number experiments. Results are conditional on
the user-selected model, bounds, objective, constraints and execution plan.
Choose option 18 in `python main.py` to run optimization and option 19 to
inspect a saved report. A non-interactive CLI is available with
`python -m optimization.cli --help`. See `optimization/README.md`,
`M23_ARCHITECTURE.md`, `M23_TEST_REPORT.md` and `MILESTONE23_REPORT.md`.


## Cross-engine experiment orchestration (M24)

M24 defines one bounded suite containing multiple independently compiled M8
artifacts. Each member runs through the existing integrity-verified M9
executor; the suite keeps each artifact's identity, paradigm, backend, M9
experiment ID and result fingerprint separate. The suite report aggregates
numeric and categorical metrics per member and parameter set, stores each M9
result as a separate file, and writes an integrity-fingerprinted report plus
a CSV summary.

An optional comparison contract ranks groups only when the requested numeric
metric name and unit match exactly and every requested replication for that
group completed. The plan must supply a semantic definition asserting what
the shared observable means across models. Identical metric names and units
alone do not prove that different model outputs are conceptually equivalent.
The report repeats this qualification. No comparison ranking is generated
when fewer than two complete groups qualify.

The suite has a global budget of 100 M9 executions. Each artifact path is
relative to the explicitly configured artifact root and may not escape that
root. The sample plan `scenarios/orchestration/cross_engine_suite.json` is a
template: place the corresponding integrity-verified M8 artifacts beneath
`outputs/m8_artifacts` or edit the plan paths before running.

Run from the project root:

```powershell
python -m orchestration.cli --plan scenarios/orchestration/cross_engine_suite.json --artifact-root . --output-dir outputs
```

The main CLI exposes option 20 to run a suite and option 21 to inspect a
fingerprint-verified M24 report. M24 orchestrates M9 executions; it does not
merge different model equations, infer metric equivalence, alter artifacts,
or replace M10 grid experiments, M11 uncertainty analysis or M23
optimization. DES suite members require the SimPy runtime dependency.

## M25 advanced experiment analytics and results intelligence

M25 reads existing integrity-verified M10 parameter-sweep, M11 uncertainty, M23 optimization and M24 cross-engine suite reports. It does not rerun simulations. Choose option 22 to run an analytics plan and option 23 to inspect a saved M25 report; the standalone CLI is `python -m analytics.cli`. The plan requires exact metric names and units plus a user-authored semantic definition. It produces Student-t confidence intervals for group means, Welch independent-group comparisons, Hedges' g effect sizes, Holm-Bonferroni adjusted p-values, data-quality findings and a Pareto frontier when at least two directed objectives are available.

M25 works from aggregate report statistics, not raw observations. Welch testing assumes independent observations and approximately normal sampling distributions; those assumptions cannot be checked from aggregate summaries. It skips cross-source groups that share an M9 experiment ID to avoid obvious double counting. Cross-model or cross-project comparisons still rely on the user's semantic-definition assertion; statistical differences in simulated outputs are not causal effects, real-world probabilities or proof of theory validity. For M23 objective reports, M23 does not store an objective unit, so declare the corresponding M25 metric `unit` as `null`. See `analytics/README.md`, `M25_ARCHITECTURE.md`, `M25_TEST_REPORT.md` and `scenarios/analytics/plan_template.json`.
