"""Run the bundled two-stage clinic scenario and inspect its M19 replay."""

from pathlib import Path

from simulations.des.backend import run_scenario
from simulations.des.replay import build_des_replay, get_entity_journey, get_resource_replay
from simulations.des.schema import scenario_from_json


def main() -> None:
    scenario_path = Path(__file__).resolve().parents[2] / "scenarios" / "des" / "two_stage_clinic_replay.json"
    scenario = scenario_from_json(scenario_path.read_text(encoding="utf-8"))
    result = run_scenario(scenario)
    replay = build_des_replay(result.events, resource_capacities=dict(result.resource_capacities))

    print(f"Scenario: {scenario.name}")
    print("Summary:")
    for key, value in replay["summary"].items():
        print(f"  {key}: {value}")

    print("\nEntity C journey:")
    journey = get_entity_journey(replay, "Patient-C")
    for stage in journey["stages"]:
        print(
            f"  {stage['stage']}. {stage['resource_name']}: "
            f"arrived={stage['arrival_time']}, wait={stage['waiting_time']}, "
            f"service={stage['service_time']}, completed={stage['completion_time']}"
        )

    print("\nResource utilization:")
    for resource_name in ("Registration", "Consultation"):
        resource = get_resource_replay(replay, resource_name)
        print(
            f"  {resource_name}: {resource['utilization']:.1f}% "
            f"(peak queue {resource['peak_queue_length']}, "
            f"peak concurrent {resource['peak_concurrent']})"
        )


if __name__ == "__main__":
    main()
