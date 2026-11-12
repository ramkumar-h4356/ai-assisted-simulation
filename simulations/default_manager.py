"""Apply documented simulation defaults transparently."""

from dataclasses import dataclass, replace
from typing import Any

from simulations.requirements import DEFAULT_VALUES
from simulations.scenario_ir import ResourceUnderstanding, ScenarioIR
from simulations.scenario_understanding import FactOrigin
from simulations.scenario_ir import KnownValue


@dataclass(frozen=True, slots=True)
class DefaultApplication:
    """Record a proposed or applied default."""

    path: str
    value: Any


@dataclass(frozen=True, slots=True)
class DefaultResolution:
    """Return the updated scenario and default application records."""

    scenario: ScenarioIR
    proposed: tuple[DefaultApplication, ...]
    applied: tuple[DefaultApplication, ...]


def apply_documented_defaults(
    scenario: ScenarioIR,
    *,
    approve: bool = False,
) -> DefaultResolution:
    """Propose defaults or apply them after explicit approval."""

    if not isinstance(scenario, ScenarioIR):
        raise TypeError("scenario must be a ScenarioIR instance")

    if not isinstance(approve, bool):
        raise TypeError("approve must be a boolean")

    if scenario.resources is None:
        return DefaultResolution(scenario, (), ())

    proposed = tuple(
        DefaultApplication(
            path=f"resources[{index}].capacity",
            value=DEFAULT_VALUES["resource.capacity"],
        )
        for index, resource in enumerate(scenario.resources)
        if (
            isinstance(resource, ResourceUnderstanding)
            and resource.capacity is None
        )
    )

    if not approve or not proposed:
        return DefaultResolution(scenario, proposed, ())

    updated_resources = tuple(
        replace(
            resource,
            capacity=KnownValue(
                DEFAULT_VALUES["resource.capacity"],
                FactOrigin.DEFAULTED,
            ),
        )
        if (
            isinstance(resource, ResourceUnderstanding)
            and resource.capacity is None
        )
        else resource
        for resource in scenario.resources
    )

    updated_scenario = replace(
        scenario,
        resources=updated_resources,
    )

    return DefaultResolution(
        scenario=updated_scenario,
        proposed=proposed,
        applied=proposed,
    )