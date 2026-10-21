
from simulations.scenario import (
    Scenario,
    ServiceJob,
    compare_scenarios,
)


def main():
    # Keep the workload identical in both scenarios.
    jobs = (
        ServiceJob("A", arrival_time=0, service_duration=6),
        ServiceJob("B", arrival_time=2, service_duration=4),
    )

    scenarios = (
        Scenario(
            name="One machine",
            resource_name="machine",
            resource_capacity=1,
            jobs=jobs,
        ),
        Scenario(
            name="Two machines",
            resource_name="machine",
            resource_capacity=2,
            jobs=jobs,
        ),
    )

    results = compare_scenarios(scenarios)

    print("\n--- Scenario Comparison ---")

    for result in results:
        print(f"\n{result.scenario_name}")
        print(f"Average waiting time: {result.average_waiting_time:.2f}")
        print(f"Final completion time: {result.completion_time:.2f}")

        print("Job details:")
        for item in result.entity_metrics:
            print(
                f"  {item.entity_id}: "
                f"wait={item.waiting_time:.2f}, "
                f"service={item.service_time:.2f}, "
                f"total={item.time_in_system:.2f}"
            )


if __name__ == "__main__":
    main()
