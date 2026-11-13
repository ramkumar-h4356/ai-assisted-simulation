"""Offline M8 compilation demonstration for both currently supported paradigms."""

from pathlib import Path

from conceptual import (
    Concept, ConceptKind, ConceptOrigin, DefinitionStatus, Mechanism, Property,
    PropertyType, Relationship, create_idea_project, revise_idea_project,
)
from compilation import (
    BindingSource, CompilationParadigm, CompilationProfile, ElementBinding,
    compile_profile, save_artifact,
)


def _project():
    project = create_idea_project(
        "Shared resource cooperation",
        "People cooperate to manage a shared resource.",
        project_id="m8-demo-cooperation",
        revision_id="m8-demo-rev-1",
        created_at="2026-11-13T00:00:00+00:00",
    )
    return revise_idea_project(
        project,
        change_summary="Formalize a simple executable cooperation example.",
        revision_id="m8-demo-rev-2",
        created_at="2026-11-13T00:01:00+00:00",
        concepts=(
            Concept("person", "Person", ConceptKind.ACTOR, ConceptOrigin.USER_DEFINED,
                    "An autonomous participant.", DefinitionStatus.DEFINED),
            Concept("resource", "Shared resource", ConceptKind.RESOURCE, ConceptOrigin.USER_DEFINED,
                    "A limited shared resource.", DefinitionStatus.DEFINED),
        ),
        properties=(
            Property("trust", "person", "Trust", PropertyType.NUMBER, "0-1", "Participant trust.", DefinitionStatus.DEFINED),
        ),
        relationships=(
            Relationship("contribution", "person", "resource", "contributes to", "A person contributes to the shared resource.", True, DefinitionStatus.DEFINED),
        ),
        mechanisms=(
            Mechanism("cooperation", "Cooperation rule", "Participants decide whether to contribute.",
                      ("person", "resource"), ("resource",),
                      "At each decision step.", "A contribution count increases when trust exceeds the threshold.",
                      "If trust is greater than 0.5, increment the contribution count by one.", DefinitionStatus.DEFINED),
        ),
    )


def _des_demo_project():
    project = create_idea_project(
        "Queue and service process",
        "Jobs arrive, wait for a machine, receive service and then leave.",
        project_id="m8-demo-queue",
        revision_id="m8-demo-queue-rev-1",
        created_at="2026-11-13T00:00:00+00:00",
    )
    return revise_idea_project(
        project,
        change_summary="Define an operational queueing process.",
        revision_id="m8-demo-queue-rev-2",
        created_at="2026-11-13T00:01:00+00:00",
        concepts=(
            Concept("queue", "Queue", ConceptKind.PROCESS, ConceptOrigin.USER_DEFINED,
                    "Jobs waiting for service.", DefinitionStatus.DEFINED),
            Concept("machine", "Machine", ConceptKind.RESOURCE, ConceptOrigin.USER_DEFINED,
                    "A capacity-limited service resource.", DefinitionStatus.DEFINED),
        ),
        properties=(
            Property("service-duration", "machine", "Service duration", PropertyType.NUMBER,
                    "minutes", "Time required to process one job.", DefinitionStatus.DEFINED),
        ),
        relationships=(
            Relationship("served-by", "queue", "machine", "is served by",
                         "Queued jobs are processed by the machine.", True, DefinitionStatus.DEFINED),
        ),
        mechanisms=(
            Mechanism("service-event", "Service event", "A waiting job receives service.",
                      ("queue", "machine"), ("queue",),
                      "When a job arrives and the machine can accept it.",
                      "The job completes and the machine becomes available.",
                      "Select the next waiting job, process it for the configured duration, then release the machine.",
                      DefinitionStatus.DEFINED),
        ),
    )


def _compile_des_demo(output: Path) -> Path:
    project = _des_demo_project()
    profile = CompilationProfile(
        profile_id="m8-demo-des",
        project_id=project.id,
        revision_id=project.current_revision_id,
        paradigm=CompilationParadigm.DISCRETE_EVENT,
        model_data={
            "name": "Queue and service process",
            "resources": [{"name": "Machine", "capacity": 1}],
            "jobs": [{"entity_id": "job-1", "arrival_time": 0,
                      "stages": [{"resource_name": "Machine", "service_duration": 5}]}],
        },
        bindings=(
            ElementBinding("resources[0]", BindingSource.CONCEPTUAL_ELEMENT, ("machine",), "Represents the resource concept."),
            ElementBinding("jobs[0]", BindingSource.CONCEPTUAL_ELEMENT, ("queue",), "Represents one explicitly configured job."),
            ElementBinding("jobs[0].stages[0]", BindingSource.CONCEPTUAL_ELEMENT, ("service-event",), "Operationalizes the service mechanism."),
            ElementBinding("resources[0].capacity", BindingSource.USER_PARAMETER, (), "Demonstration capacity: one machine."),
            ElementBinding("jobs[0].arrival_time", BindingSource.USER_PARAMETER, (), "Demonstration arrival time: zero minutes."),
            ElementBinding("jobs[0].stages[0].service_duration", BindingSource.USER_PARAMETER, (), "Demonstration service time: five minutes; not measured data."),
        ),
    )
    result = compile_profile(project, profile)
    if not result.is_ready:
        raise RuntimeError("DES demo compilation failed: " + "; ".join(issue.message for issue in result.errors))
    path = output / "m8_demo_des_artifact.json"
    save_artifact(result.artifact, path)
    print(f"DES compiled: {result.artifact.artifact_id} -> {path}")
    return path


def run_demo(output_dir: str | Path = "outputs/m8_demo") -> tuple[Path, ...]:
    project = _project()
    output = Path(output_dir)
    results: list[Path] = []
    results.append(_compile_des_demo(output))
    abm_profile = CompilationProfile(
        profile_id="m8-demo-abm",
        project_id=project.id,
        revision_id=project.current_revision_id,
        paradigm=CompilationParadigm.AGENT_BASED,
        model_data={
            "name": "Shared resource cooperation",
            "agents": [
                {"reference": "person-1", "agent_type": "Person", "state": "active", "attributes": {"trust": 0.8, "contributions": 0}},
                {"reference": "person-2", "agent_type": "Person", "state": "active", "attributes": {"trust": 0.4, "contributions": 0}},
            ],
            "environment": {"attributes": {"resource_units": 5}},
            "relationships": [
                {"source": "person-1", "target": "person-2", "relation_type": "peer", "directed": False}
            ],
            "behaviours": [
                {"rule_id": "cooperate-if-trust-high", "agent_type": "Person",
                 "condition": {"type": "agent_attribute_comparison", "attribute": "trust", "operator": "gt", "value": 0.5},
                 "actions": [{"type": "increment_attribute", "attribute": "contributions", "amount": 1}],
                 "probability": 1.0}
            ],
            "activation": {"mode": "sequential", "order": "declaration"},
            "termination": {"type": "max_steps", "value": 10},
            "random_seed": 7,
        },
        bindings=(
            ElementBinding("agents[0]", BindingSource.CONCEPTUAL_ELEMENT, ("person",), "First explicit participant instance."),
            ElementBinding("agents[1]", BindingSource.CONCEPTUAL_ELEMENT, ("person",), "Second explicit participant instance."),
            ElementBinding("relationships[0]", BindingSource.CONCEPTUAL_ELEMENT, ("contribution",), "Illustrative peer interaction topology."),
            ElementBinding("behaviours[0]", BindingSource.CONCEPTUAL_ELEMENT, ("cooperation",), "Operationalizes the cooperation mechanism."),
            ElementBinding("agents[0].attributes.trust", BindingSource.USER_PARAMETER, (), "Illustrative initial trust value 0.8; not measured evidence."),
            ElementBinding("agents[1].attributes.trust", BindingSource.USER_PARAMETER, (), "Illustrative initial trust value 0.4; not measured evidence."),
            ElementBinding("termination.value", BindingSource.USER_PARAMETER, (), "Experiment horizon: 10 steps, selected for demonstration."),
        ),
    )
    compiled = compile_profile(project, abm_profile)
    if not compiled.is_ready:
        raise RuntimeError("ABM demo compilation failed: " + "; ".join(issue.message for issue in compiled.errors))
    output.mkdir(parents=True, exist_ok=True)
    from compilation import save_artifact
    artifact_path = output / "m8_demo_abm_artifact.json"
    save_artifact(compiled.artifact, artifact_path)
    results.append(artifact_path)
    print(f"ABM compiled: {compiled.artifact.artifact_id} -> {artifact_path}")
    print("No simulation was executed.")
    return tuple(results)


if __name__ == "__main__":
    run_demo()
