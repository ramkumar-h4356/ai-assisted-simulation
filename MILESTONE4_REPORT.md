# Milestone 4 — Conceptual Idea Formalization Core

## Objective

Deliver a paradigm-independent, versioned representation of a user's idea so
that new concepts can be defined freely, selected concepts can be mapped to
real-world analogies, and incomplete mechanisms can remain explicit without
being silently converted into executable rules.

## Delivered

- New `conceptual/` package independent of DES/ABM runtimes.
- Typed representations for projects, immutable revisions, concepts,
  properties, relationships, mechanisms, hypotheses, assumptions, constraints,
  evidence references, mapping claims and open questions.
- Explicit provenance for user-defined, AI-proposed and real-world-mapped
  concepts.
- Explicit mapping kinds and review status; mappings are not treated as facts.
- Append-only revision helpers preserving the original idea statement, each
  revision's latest refined statement, change summary and previous snapshots.
- Strict JSON serialization/deserialization and file persistence.
- Validation of revision chains, duplicate IDs, concept/evidence references,
  incomplete definitions and readiness warnings.
- A decentralized resource-cooperation theory example demonstrating both
  real-world analogy and an original user-defined concept.
- CLI option 4 for inspecting and validating the example.
- Unit tests for model invariants, revision history, serialization and
  structural/semantic validation.

## Important semantics

- `review_ready` means internally consistent under the current validator. It
  does not mean scientifically true or ready for simulation execution.
- Open questions and partially defined mechanisms are retained as valid
  conceptual information and reported as warnings where applicable.
- The original source statement is stored separately and is not overwritten by
  revisions.
- AI-generated concepts are distinguishable from user-defined concepts and
  remain proposals until reviewed.

## Deliberate exclusions

M4 does not include external literature retrieval, automatic real-world
knowledge mapping, AI-assisted conversational refinement, paradigm selection,
translation to DES/ABM, or simulation execution. Those depend on the stable
conceptual representation delivered here and belong to later milestones.

## Verification

See `M4_TEST_REPORT.md` for the exact commands and observed test results. The
workspace used to prepare this archive did not have the runtime dependencies
SimPy and Groq installed and had no network access to install them. Therefore,
conceptual and dependency-independent tests are run here; the complete project
suite should also be run in the developer's existing Windows virtual
environment before treating the local runtime verification as complete.
