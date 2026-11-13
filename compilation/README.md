# M8 — Conceptual-to-Executable Specification Compilation

M8 creates a deterministic and traceable boundary between an M4 conceptual
revision and the two executable model families that currently exist: DES V1
and ABM V1.

## The key design decision

M8 does **not** guess runtime semantics from natural-language descriptions.
Concepts and mechanisms describe what a user means; they do not automatically
specify concrete simulated instances, initial states, numeric parameters,
service durations, agent update rules, or stopping conditions.

A user-approved `CompilationProfile` supplies:

1. The exact project and conceptual revision IDs it was prepared for.
2. The selected executable paradigm (`discrete_event` or `agent_based`).
3. A native target `model_data` object using the existing target schema.
4. `ElementBinding` records that trace target-model paths to conceptual element
   IDs, or explain a user-specified experiment parameter.

The compiler then checks the M7 implementation-planning gate, verifies the
revision and all provenance references, parses the actual DES/ABM model, and
runs ABM semantic validation. Only then does it produce a portable
`CompilationArtifact` plus a native `SimulationSpecification`.

## Profile format

```json
{
  "profile_id": "queue-des-example",
  "project_id": "idea-project-id",
  "revision_id": "idea-revision-id",
  "paradigm": "discrete_event",
  "model_data": {
    "name": "Queue example",
    "resources": [{"name": "Machine", "capacity": 1}],
    "jobs": [{
      "entity_id": "job-1",
      "arrival_time": 0,
      "stages": [{"resource_name": "Machine", "service_duration": 5}]
    }]
  },
  "bindings": [
    {
      "target_path": "resources[0]",
      "source": "conceptual_element",
      "element_ids": ["machine"],
      "note": "The target resource represents the conceptual machine."
    },
    {
      "target_path": "jobs[0].stages[0]",
      "source": "conceptual_element",
      "element_ids": ["service-mechanism"],
      "note": "The stage operationalizes the service mechanism."
    },
    {
      "target_path": "jobs[0].stages[0].service_duration",
      "source": "user_parameter",
      "element_ids": [],
      "note": "Illustrative experiment parameter: 5 time units; not empirical evidence."
    }
  ]
}
```

`target_path` uses dotted object keys and numeric list indexes, for example
`agents[0].attributes.trust` or `behaviours[0]`. Wildcards are intentionally
not accepted. Each target path can have one binding. For conceptual bindings,
every element ID must exist in the exact current revision. User parameters
must include a note stating their experimental meaning. They are not
silently promoted to facts in the conceptual theory.

At least one binding must reference a conceptual element and at least one
must reference a mechanism. Unmapped concepts/mechanisms are reported as
warnings so users can intentionally scope an experiment to only part of a
theory without silently losing traceability.

## Supported target schemas

### DES V1

`model_data` must pass `simulations.des.schema.scenario_from_dict`. It needs a
scenario name, resources with positive integer capacities, and jobs with
non-negative arrival times and stages referencing known resources. Every job
must have one or more service stages.

### ABM V1

`model_data` must pass `simulations.abm.schema.agent_model_from_dict` and
`simulations.abm.validation.validate_agent_model`. V1 supports finite scalar
attributes, static relationships, declarative conditions/actions, sequential
activation in declaration order, and `max_steps` termination. Unsupported
behaviour or scheduling semantics must not be smuggled into this schema.

Mathematical and data-driven paradigms remain M7 assessment-only; M8 refuses
to compile them until corresponding execution backends exist.

## API

```python
from conceptual import load_idea_project
from compilation import compile_profile, load_profile, save_artifact

project = load_idea_project("outputs/my_idea_m6_idea.json")
profile = load_profile("profiles/my_idea_des.json")
result = compile_profile(project, profile)

if not result.is_ready:
    for issue in result.errors:
        print(issue.code, issue.path, issue.message)
else:
    save_artifact(result.artifact, "outputs/my_idea_m8_specification.json")
    # result.native_specification is ready for the later execution milestone.
    # M8 deliberately does not execute it.
```

## M7 readiness gate

The selected paradigm must reach
`READY_FOR_IMPLEMENTATION_PLANNING` in M7. The paradigm must also have an
implemented backend. A merely possible fit, unresolved blocking question,
non-operational mechanism, stale profile revision, or assessment-only
paradigm blocks compilation.

## Artifact integrity

The saved artifact records project/revision identity, target paradigm, backend
name, the M7 readiness/fit decision, exact validated target model data, provenance
bindings, a SHA-256 model fingerprint over the paradigm plus model data, and a
whole-artifact integrity fingerprint over metadata and bindings. `load_artifact`
recomputes both fingerprints and rejects altered model or provenance content. The artifact is a specification, not a
simulation result and not evidence that the conceptual theory is true.

## Scope boundary

M8 validates and compiles specifications; it does not run the DES or ABM
backend, choose experimental parameters, create agent populations, infer
behaviour rules, or train an ML model. Those decisions require explicit user
input or a separately evaluated milestone.
