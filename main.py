
"""Run AI-generated simulations or compare resource capacities."""



def run_machine_comparison():
    """Compare the same workload using one machine and two machines."""
    from simulations.des.model import Scenario, ServiceJob
    from simulations.des.backend import compare_scenarios
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
    """Generate and execute a simulation with conversational clarification."""
    from simulations.des.pipeline import run_prompt

    print("\n--- AI-Assisted Simulation ---")
    print("Describe a real-world process to simulate.")
    prompt = input("\nYour scenario: ").strip()

    if not prompt:
        print("Please enter a scenario.")
        return

    def collect_clarifications(questions):
        print("\n--- Clarification Required ---")

        for index, question in enumerate(questions, start=1):
            print(f"\n{index}. {question.path}")
            print(question.question)

        print(
            "\nAnswer as many questions as possible in one response. "
            "You can also explain corrections to earlier information."
        )

        return input("\nYour clarification: ").strip()

    def approve_defaults(defaults):
        print("\n--- Proposed Defaults ---")

        for item in defaults:
            print(f"{item.path} = {item.value}")

        answer = input(
            "\nApply these defaults? (y/n): "
        ).strip().lower()

        return answer in {"y", "yes"}

    try:
        result = run_prompt(
            prompt,
            clarification_handler=collect_clarifications,
            approve_defaults=approve_defaults,
            max_clarification_rounds=3,
        )

        report = result.validation_report

        if result.simulation_result is None:
            print("\n--- Simulation Not Executed ---")
            print(f"Readiness: {report.readiness.value}")

            print("\n--- Remaining Findings ---")

            for item in report.results:
                if item.status.value != "satisfied":
                    print(
                        f"[{item.status.value.upper()}] "
                        f"{item.path}: {item.message}"
                    )

            print(
                "\nThe scenario still needs information or corrections."
            )
            return

        simulation = result.simulation_result

        print("\n--- Generated Simulation Model ---")
        print(f"Scenario: {simulation.scenario_name}")

        print(
            f"Clarification rounds: "
            f"{len(result.clarification_history)}"
        )

        if result.default_resolution.applied:
            print("\nApplied defaults:")

            for item in result.default_resolution.applied:
                print(f"  {item.path} = {item.value}")

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

        for metrics in simulation.resource_metrics:
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
            f"{simulation.average_waiting_time:.2f}"
        )
        print(
            "Final completion time: "
            f"{simulation.completion_time:.2f}"
        )

        print("\nJob details:")

        for item in simulation.entity_metrics:
            print(
                f"  {item.entity_id}: "
                f"wait={item.waiting_time:.2f}, "
                f"service={item.service_time:.2f}, "
                f"total={item.time_in_system:.2f}"
            )

    except Exception as error:
        print(f"\nSimulation failed: {error}")
        print(
            "Check your Groq API key, internet connection, "
            "and scenario description, then try again."
        )

def run_ai_agent_simulation():
    """Generate, clarify, validate and execute an agent-based model."""
    from simulations.abm.pipeline import run_agent_prompt
    print("\n--- AI-Assisted Agent-Based Simulation ---")
    print("Describe the agents, their initial states, relationships and behaviours.")
    prompt = input("\nYour scenario: ").strip()

    if not prompt:
        print("Please enter a scenario.")
        return

    def collect_clarification(questions):
        print("\n--- ABM Clarification Required ---")
        for question in questions:
            print(f"\n{question.path}")
            print(question.question)
        return input("\nYour clarification: ").strip()

    try:
        result = run_agent_prompt(
            prompt,
            clarification_handler=collect_clarification,
            max_clarification_rounds=3,
        )

        if not result.is_ready:
            print("\n--- ABM Model Not Executed ---")
            for issue in result.validation_report.errors:
                print(f"[{issue.code}] {issue.path}: {issue.message}")
            print("\nNo simulation was run because the model is incomplete or invalid.")
            return

        simulation = result.simulation_result
        model = result.agent_model
        print("\n--- Validated ABM Model ---")
        print(f"Model: {model.name}")
        print(f"Agents: {len(model.agents)}")
        print(f"Relationships: {len(model.relationships)}")
        print(f"Behaviour rules: {len(model.behaviours)}")
        print(f"Steps completed: {simulation.steps_completed}")
        print(f"Random seed: {simulation.random_seed}")

        print("\nInitial agents:")
        raw_agents = result.model_data.get("agents", [])
        for index, agent in enumerate(model.agents):
            reference = raw_agents[index].get("reference", agent.identifier)
            print(
                f"  {reference} ({agent.identifier}): "
                f"type={agent.agent_type}, state={agent.state}, "
                f"attributes={dict(agent.attributes)}"
            )

        print("\nFinal state counts:")
        for state, count in simulation.final_state_counts.items():
            print(f"  {state}: {count}")

        print("\nStep-by-step population history:")
        for snapshot in simulation.history:
            counts = {}
            for agent in snapshot.agents:
                counts[agent.state] = counts.get(agent.state, 0) + 1
            summary = ", ".join(
                f"{state}={count}" for state, count in sorted(counts.items())
            )
            print(f"  Step {snapshot.step}: {summary}")

        print(f"\nRule evaluations recorded: {len(simulation.rule_evaluations)}")
        print("Simulation completed successfully.")

    except Exception as error:
        print(f"\nAgent-based simulation failed: {error}")
        print("Check your Groq API key, internet connection and scenario description.")



def run_conceptual_model_inspection():
    """Inspect and validate the included paradigm-independent idea model."""
    from conceptual.demo import inspect_example

    try:
        inspect_example()
    except Exception as error:
        print(f"\nConceptual model inspection failed: {error}")


def run_knowledge_mapping():
    """Search the local knowledge base and review mapping candidates."""
    from knowledge.demo import run_interactive_workflow
    try:
        run_interactive_workflow()
    except Exception as error:
        print(f"\nKnowledge mapping workflow failed: {error}")


def main():
    """Display the program menu."""
    print("\n=== AI-Assisted Simulation System ===")
    print("1. Generate a simulation using AI")
    print("2. Compare one machine vs. two machines")
    print("3. Generate an agent-based simulation using AI")
    print("4. Inspect and validate a conceptual idea model")
    print("5. Search knowledge and review real-world mapping candidates")

    choice = input("\nChoose an option (1-5): ").strip()

    if choice == "1":
        run_ai_simulation()
    elif choice == "2":
        run_machine_comparison()
    elif choice == "3":
        run_ai_agent_simulation()
    elif choice == "4":
        run_conceptual_model_inspection()
    elif choice == "5":
        run_knowledge_mapping()
    else:
        print("Invalid choice. Please run the program again and choose a number from 1 to 5.")


if __name__ == "__main__":
    main()
