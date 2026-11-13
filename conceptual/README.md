# Conceptual Idea Formalization Core — M4

## Purpose

The conceptual package stores and validates a user's idea before selecting a
simulation paradigm. It is deliberately independent of SimPy, the ABM engine,
and all other execution backends.

The source idea is preserved separately from an append-only sequence of
conceptual-model revisions. Each revision stores a `working_statement` for the
latest refined wording and a `change_summary` explaining the revision. A
refinement creates a new snapshot; it never rewrites the original statement or
an earlier snapshot.

## Included representation

| Type | Meaning |
|---|---|
| `IdeaProject` | Project identity, immutable original statement and revision history |
| `IdeaRevision` | Complete snapshot of the idea's structured representation |
| `Concept` | Actor, entity, resource, process, state, variable or abstract concept |
| `Property` | A property/variable attached to a concept, with optional unit and definition |
| `Relationship` | A directed or undirected relationship between concepts |
| `Mechanism` | A proposed process explaining how inputs may produce effects or outputs |
| `Hypothesis` | A claim that may later be investigated or tested |
| `Assumption` | A premise accepted within a stated scope |
| `Constraint` | A limitation that bounds the theory or model |
| `EvidenceReference` | A source reference that can be linked to hypotheses or mappings |
| `MappingClaim` | An explicit analogy/equivalence/evidence mapping with rationale and review state |
| `OpenQuestion` | An unresolved question linked to relevant model elements |

Concept origins are recorded as `user_defined`, `ai_proposed`, or
`real_world_mapped`. An AI proposal is not treated as user-approved merely
because it exists in the model.

## Quick start

```python
from conceptual import (
    Concept, ConceptKind, ConceptOrigin, DefinitionStatus,
    create_idea_project, revise_idea_project, validate_idea_project,
    save_idea_project, load_idea_project,
)

project = create_idea_project(
    "My theory",
    "The original words supplied by the user are retained here.",
)
project = revise_idea_project(
    project,
    change_summary="Add the first identified concept.",
    working_statement="My refined explanation of the theory.",
    concepts=(Concept(
        id="actor-1",
        name="Participant",
        kind=ConceptKind.ACTOR,
        origin=ConceptOrigin.USER_DEFINED,
        definition="A participant in the proposed system.",
        status=DefinitionStatus.DEFINED,
    ),),
)

report = validate_idea_project(project)
print(report.readiness.value)
save_idea_project(project, "my_idea.json")
restored = load_idea_project("my_idea.json")
```

Run the included example with either:

```bash
python -m conceptual.demo
python -m conceptual.demo path/to/my_idea.json
```

or choose option `4` from `python main.py`.

## Validation semantics

Validation detects structural problems such as duplicate IDs, broken revision
chains, unknown concept/evidence references, invalid mapping references, and
inconsistent status declarations. It emits warnings for incomplete mechanisms,
untested hypotheses, unmapped real-world-origin concepts, blocking open
questions, unreviewed mappings and unsupported hypothesis status labels.

`Readiness.REVIEW_READY` means the conceptual snapshot passes the implemented
internal checks. It does **not** mean that a theory is true, externally
validated, mathematically operationalised, or executable in DES/ABM. This
milestone does not infer facts, search external literature, approve analogies,
or generate simulation rules.

## Mapping semantics

A `MappingClaim` must state its target, mapping kind and rationale. Its
`review_status` is explicit (`unreviewed`, `accepted`, `rejected`). A mapping is
not silently considered evidence. `EvidenceReference` objects can be linked to
claims, but this milestone does not verify source contents or citation accuracy.

Supported mapping kinds:

- `equivalent`
- `analogous`
- `inspired_by`
- `evidence_supported`
- `contradicted_by`

## Revision guarantees

`create_idea_project` makes revision 1. `revise_idea_project` copies omitted
component groups from the current snapshot and creates a new version. The
`append_revision` API checks version increment and parent linkage. Dataclasses
are frozen and nested collections are converted to tuples. The original user
statement is never rewritten by these APIs; the latest interpretation is stored
in `IdeaRevision.working_statement`.

## Scope boundaries

M4 delivers the conceptual data contract, revision history, JSON persistence,
structural validation, a representative theory example, a CLI inspection path,
and automated tests. It does not deliver the later M5 knowledge retrieval and
mapping engine, the M6 AI conversation/refinement pipeline, paradigm selection,
or translation into executable DES/ABM models.
