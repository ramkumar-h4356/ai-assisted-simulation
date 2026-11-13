# M8 Architecture — Conceptual Model to Executable Simulation Specification

## 1. Objective

M8 bridges an immutable M4 conceptual revision to an executable model contract
for an already implemented simulation paradigm. It does not change the idea,
choose parameters on the user's behalf, generate arbitrary Python rules, or
execute a simulation.

The supported target backends are:

- DES V1 / SimPy, using `Scenario` and `scenario_from_dict`.
- ABM V1, using `AgentModel`, `agent_model_from_dict` and
  `validate_agent_model`.

Mathematical and data-driven paradigms remain assessment-only under M7 and are
rejected by M8 until actual execution backends exist.

## 2. Why compilation profiles are explicit

Conceptual models and simulation models answer different questions. A
conceptual mechanism may say that participants cooperate when trust is high;
a concrete ABM still needs the number of agents, their initial states and
attributes, the exact threshold, supported update actions, activation order,
random seed and termination condition. Those values are experiment design
choices, not details that can safely be guessed from a theory statement.

A DES scenario similarly needs concrete resources, capacities, arrivals,
routes and service durations. These may be measured, hypothesized, or merely
illustrative. M8 requires those origins to be stated rather than silently
converting an example parameter into evidence.

For that reason M8 introduces the user-approved `CompilationProfile`. It
contains native target `model_data` and path-level `ElementBinding` records.
Each binding either:

- maps a target path to one or more element IDs in the exact conceptual
  revision (`conceptual_element`); or
- records an explicit experimental parameter with a required explanatory note
  (`user_parameter`).

This is a deliberate semantic boundary. An AI-assisted profile proposer may
be added later, but any proposal must be reviewed and passed through this same
strict compiler.

## 3. End-to-end flow

```text
M4 IdeaProject / current IdeaRevision
                |
                v
M7 assess_readiness(project, selected_paradigm)
                |
       require READY_FOR_IMPLEMENTATION_PLANNING
                |
                v
       User-approved CompilationProfile
       - exact project and revision IDs
       - selected DES or ABM paradigm
       - native target model_data
       - provenance bindings
                |
                v
       M8 profile and provenance checks
       - revision identity is current
       - source element IDs exist
       - target paths exist
       - at least one concept is bound
       - at least one mechanism is bound
                |
                v
       Existing native model parser
         /                    \
        v                      v
   DES Scenario           ABM AgentModel
   schema/domain checks   schema + semantic validation
         \                    /
          +---------+----------+
                    |
                    v
       SimulationSpecification
       + revision-bound CompilationArtifact
       + SHA-256 model fingerprint
                    |
                    v
          Later execution milestone
```

## 4. Package responsibilities

### `compilation/models.py`

Defines the `CompilationProfile`, `ElementBinding`, `CompilationIssue`,
`CompilationArtifact` and `CompilationResult` contracts. Profiles are
revision-bound. Bindings reject duplicate element IDs, unsupported source
semantics and undocumented user parameters.

### `compilation/compiler.py`

Implements the deterministic compiler. It uses M7's `assess_readiness` as a
gate, checks all binding IDs against the current revision, validates target
paths, reports unmapped concepts/mechanisms and dispatches to the existing
native parser. Successful output wraps the native model in the shared
`SimulationSpecification` contract. It never calls a backend's `execute`.

### `compilation/serialization.py`

Provides strict JSON profile and artifact persistence. Unknown and missing
fields are rejected. `load_artifact` recomputes both model and whole-artifact integrity fingerprints
and refuses a payload whose model or provenance content no longer matches.

### `main.py`

Option 8 supports the interactive workflow. It loads a saved conceptual
project, lets the user select DES or ABM, checks M7 readiness, creates an
incomplete editable template when no profile path is supplied, or compiles a
provided profile and saves a specification artifact.

## 5. Validation rules

Compilation is blocked when any of the following applies:

- the selected paradigm is not implemented by an execution backend;
- the profile refers to a different project or stale revision;
- M7 does not return `READY_FOR_IMPLEMENTATION_PLANNING` for the selected
  paradigm;
- a conceptual source element ID is not present in that revision;
- a target path is invalid, missing, out of range or uses a wildcard;
- no conceptual element or no operational mechanism is bound;
- the native target model fails its existing parser/domain checks; or
- ABM semantic validation reports errors.

Unmapped concepts and mechanisms are warnings. This permits an experiment to
focus on a defensible subset of a broader theory while making the omission
visible. M8 does not require every conceptual element to be represented in
every experiment.

## 6. Target model semantics

### DES

The target profile must satisfy the existing DES scenario data contract:
scenario name, resources with positive integer capacities, jobs with
non-negative arrival times, and one or more service stages per job. Every
stage must refer to an existing resource and have a finite, non-negative
service duration.

### ABM

The profile must satisfy the current ABM V1 schema and semantic validator.
That includes explicit agents, supported scalar attributes, valid static
relationship endpoints, supported declarative conditions/actions, sequential
activation in declaration order, and positive `max_steps` termination.

ABM metadata normalization supplies only deterministic structural metadata
such as default environment/activation containers and generated internal
references/rule IDs. It does not manufacture model facts, populations,
parameter values or behavioural rules. The normalized validated model is what
is persisted in the compiled artifact.

## 7. Artifact and integrity

Each successful artifact records:

- artifact, project, profile and exact revision identities;
- revision version, target paradigm and backend name;
- the M7 readiness status and qualitative paradigm-fit status;
- normalized validated target model data;
- all provenance bindings; and
- SHA-256 model fingerprint over the target paradigm and model data; and
- whole-artifact integrity fingerprint over metadata, provenance bindings and
  the model fingerprint.

The artifact is portable JSON. The native `SimulationSpecification` is
available in memory to the next milestone. Loading an artifact verifies both
fingerprints before accepting the data.

## 8. Non-goals

M8 does not execute DES/ABM, run experiments, optimize parameters, infer
initial populations, invent rules, or claim that a simulation validates the
underlying theory. It does not compile mathematical or data-driven models.
Those require distinct model contracts and backends.

## 9. Next architectural step

M9 should focus on controlled execution of a validated M8 artifact: explicit
backend selection, bounded execution settings, seeded reproducibility,
structured result capture, safe failure handling and links from output metrics
back to the compiled artifact/revision. Experiment comparison and sensitivity
analysis should follow only after the single-run path is verified.
