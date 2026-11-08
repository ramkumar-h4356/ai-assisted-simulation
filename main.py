
"""Run AI-generated simulations or compare resource capacities."""

from simulations.pipeline import run_prompt
from simulations.scenario import (
    Scenario,
    ServiceJob,
    compare_scenarios,
)


def run_machine_comparison():
    """Compare the same workload using one machine and two machines."""
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


def run_ai_simulation():
    """Generate and execute a simulation from a natural-language prompt."""
    print("\n--- AI-Assisted Simulation ---")
    print("Describe a real-world process to simulate.")
    prompt = input("\nYour scenario: ").strip()

    if not prompt:
        print("Please enter a scenario.")
        return

    try:
        result = run_prompt(prompt)

        print("\n--- Generated Simulation Model ---")
        print(f"Scenario: {result.simulation_result.scenario_name}")


        print("\nResource Statistics:")
        print("-" * 76)
        print(
            f"{'Resource':<18}"
            f"{'Completed':>12}"
            f"{'Avg. Wait':>12}"
            f"{'Avg. Service':>16}"
            f"{'Utilization':>14}"
        )
        print("-" * 76)

        for metrics in result.simulation_result.resource_metrics:
            print(
                f"{metrics.resource_name:<18}"
                f"{metrics.completed_services:>12}"
                f"{metrics.average_waiting_time:>12.2f}"
                f"{metrics.average_service_time:>16.2f}"
                f"{metrics.utilization:>13.2f}%"
            )

        print("-" * 76)


        print("\nJobs and stages:")
        for job in result.model_data["jobs"]:
            stages = " -> ".join(
                f"{stage['resource_name']} "
                f"({stage['service_duration']} time units)"
                for stage in job["stages"]
            )
            print(
                f"  {job['entity_id']}: "
                f"arrival={job['arrival_time']}, "
                f"stages={stages}"
            )

        print("\n--- Simulation Results ---")
        print(
            "Average waiting time: "
            f"{result.simulation_result.average_waiting_time:.2f}"
        )
        print(
            "Final completion time: "
            f"{result.simulation_result.completion_time:.2f}"
        )

        print("\nJob details:")
        for item in result.simulation_result.entity_metrics:
            print(
                f"  {item.entity_id}: "
                f"wait={item.waiting_time:.2f}, "
                f"service={item.service_time:.2f}, "
                f"total={item.time_in_system:.2f}"
            )

        print("\nResource statistics:")
        for name, metrics in result.simulation_result.resource_metrics.items():
            print(f"  {name}: {metrics}")

    except Exception as error:
        print(f"\nSimulation failed: {error}")
        print(
            "Check your Groq API key, internet connection, "
            "and scenario description, then try again."
        )


def main():
    """Display the program menu."""
    print("\n=== AI-Assisted Simulation System ===")
    print("1. Generate a simulation using AI")
    print("2. Compare one machine vs. two machines")

    choice = input("\nChoose an option (1 or 2): ").strip()

    if choice == "1":
        run_ai_simulation()
    elif choice == "2":
        run_machine_comparison()
    else:
        print("Invalid choice. Please run the program again and choose 1 or 2.")


if __name__ == "__main__":
    main()
