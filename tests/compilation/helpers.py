from compilation import BindingSource, CompilationParadigm, CompilationProfile, ElementBinding
from tests.readiness.helpers import abm_project, des_project


def des_profile(project=None):
    project = project or des_project()
    return CompilationProfile(
        profile_id="queue-des-profile",
        project_id=project.id,
        revision_id=project.current_revision_id,
        paradigm=CompilationParadigm.DISCRETE_EVENT,
        model_data={
            "name": "Queueing experiment",
            "resources": [{"name": "Machine", "capacity": 2}],
            "jobs": [{
                "entity_id": "job-1",
                "arrival_time": 0,
                "stages": [{"resource_name": "Machine", "service_duration": 5}],
            }],
        },
        bindings=(
            ElementBinding("resources[0]", BindingSource.CONCEPTUAL_ELEMENT, ("machine",), "Machine resource."),
            ElementBinding("jobs[0]", BindingSource.CONCEPTUAL_ELEMENT, ("queue",), "A job in the queue."),
            ElementBinding("jobs[0].stages[0]", BindingSource.CONCEPTUAL_ELEMENT, ("service",), "Service mechanism."),
            ElementBinding("resources[0].capacity", BindingSource.USER_PARAMETER, (), "Illustrative capacity of two parallel servers."),
            ElementBinding("jobs[0].arrival_time", BindingSource.USER_PARAMETER, (), "The example job arrives at time zero."),
            ElementBinding("jobs[0].stages[0].service_duration", BindingSource.USER_PARAMETER, (), "Illustrative service duration of five minutes."),
        ),
    )


def abm_profile(project=None):
    project = project or abm_project()
    return CompilationProfile(
        profile_id="cooperation-abm-profile",
        project_id=project.id,
        revision_id=project.current_revision_id,
        paradigm=CompilationParadigm.AGENT_BASED,
        model_data={
            "name": "Cooperation experiment",
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
            ElementBinding("agents[0]", BindingSource.CONCEPTUAL_ELEMENT, ("person",), "First explicit person instance."),
            ElementBinding("agents[1]", BindingSource.CONCEPTUAL_ELEMENT, ("person",), "Second explicit person instance."),
            ElementBinding("relationships[0]", BindingSource.CONCEPTUAL_ELEMENT, ("cooperates",), "Illustrative peer relationship."),
            ElementBinding("behaviours[0]", BindingSource.CONCEPTUAL_ELEMENT, ("cooperation",), "Implements the cooperation mechanism."),
            ElementBinding("agents[0].attributes.trust", BindingSource.USER_PARAMETER, (), "Illustrative initial trust of 0.8."),
            ElementBinding("agents[1].attributes.trust", BindingSource.USER_PARAMETER, (), "Illustrative initial trust of 0.4."),
            ElementBinding("termination.value", BindingSource.USER_PARAMETER, (), "Experiment horizon of 10 steps."),
        ),
    )
