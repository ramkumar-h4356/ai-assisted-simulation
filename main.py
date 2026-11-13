
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



def run_ai_idea_formalization():
    """Capture a novel idea, clarify its meaning and save a traceable M6 draft."""
    from pathlib import Path
    import re

    from conceptual import save_idea_project
    from idea_assistant import GroqIdeaInterpreter, IdeaAssistantService, save_session
    from knowledge import load_knowledge_base

    root = Path(__file__).resolve().parent
    corpus_path = root / "knowledge" / "sample_knowledge_base.json"
    knowledge_base = load_knowledge_base(corpus_path) if corpus_path.exists() else None

    print("\n--- M6: AI-Assisted Idea Interpretation and Clarification ---")
    print("Describe your idea, including new concepts that may have no real-world equivalent.")
    print("The system will formalize a draft; it will not judge whether the idea is true or run a simulation.")
    request = input("\nYour idea: ").strip()
    if not request:
        print("Please enter an idea.")
        return

    def collect_answers(questions):
        print("\n--- Clarification questions ---")
        answers = {}
        for index, question in enumerate(questions, start=1):
            print(f"\n{index}. [{question.priority.upper()}] {question.question}")
            if question.reason:
                print(f"   Why it matters: {question.reason}")
            answer = input("   Your answer (Enter to leave open): ").strip()
            if answer:
                answers[question.id] = answer
        return answers

    try:
        interpreter = GroqIdeaInterpreter()
        service = IdeaAssistantService(interpreter, knowledge_base=knowledge_base)
        result = service.build(
            request,
            clarification_handler=collect_answers,
            max_clarification_rounds=3,
            max_questions_per_round=3,
        )
    except Exception as error:
        print(f"\nIdea interpretation failed: {error}")
        print("Check the Groq API key, connection and the idea description, then try again.")
        return

    revision = result.project.current_revision
    print("\n--- Interpreted Idea ---")
    print(f"Title: {result.project.title}")
    print(f"Working statement: {revision.working_statement}")
    if result.draft.summary:
        print(f"Summary: {result.draft.summary}")
    print("\n--- Conceptual elements ---")
    for group_name in ("concepts", "properties", "relationships", "mechanisms", "hypotheses", "assumptions", "constraints"):
        print(f"{group_name.capitalize()}: {len(getattr(revision, group_name))}")
    print(f"Unresolved questions: {len(revision.open_questions)}")
    print(f"Clarification answers recorded: {len(result.session.clarification_history)}")

    if revision.concepts:
        print("\nConcepts and origin:")
        provenance_by_element = {item.element_id: item for item in revision.provenance_records}
        for concept in revision.concepts:
            record = provenance_by_element.get(concept.id)
            label = record.kind.value if record else concept.origin.value
            print(f"  {concept.name}: {label} — {concept.definition or 'definition still open'}")

    if result.session.retrieved_context:
        print("\nLocal knowledge search leads (lexical relevance only, not confidence or proof):")
        for item in result.session.retrieved_context:
            print(f"  {item.title} | matched: {', '.join(item.matched_terms)}")

    if result.draft.uncertainties:
        print("\nRemaining uncertainties:")
        for item in result.draft.uncertainties:
            print(f"  - {item}")
    if revision.open_questions:
        print("\nOpen questions retained in the project:")
        for item in revision.open_questions:
            print(f"  - {item.question}")

    print(f"\nConceptual validation: {result.validation_report.readiness.value}")
    for issue in result.validation_report.warnings:
        print(f"  [warning] {issue.path}: {issue.message}")
    for issue in result.validation_report.errors:
        print(f"  [error] {issue.path}: {issue.message}")

    output_dir = root / "outputs"
    output_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9_-]+", "_", result.project.id.casefold()).strip("_") or "idea"
    project_path = output_dir / f"{stem}_m6_idea.json"
    session_path = output_dir / f"{stem}_m6_session.json"
    version = 2
    while project_path.exists() or session_path.exists():
        project_path = output_dir / f"{stem}_m6_idea_v{version}.json"
        session_path = output_dir / f"{stem}_m6_session_v{version}.json"
        version += 1
    save_idea_project(result.project, project_path)
    save_session(result.session, session_path)
    print("\nSaved the conceptual project and clarification audit trail:")
    print(f"  Project: {project_path}")
    print(f"  Session: {session_path}")
    print("The original idea remains unchanged. AI-generated elements remain visibly attributed and require review.")


def main():
    """Display the program menu."""
    print("\n=== AI-Assisted Simulation System ===")
    print("1. Generate a simulation using AI")
    print("2. Compare one machine vs. two machines")
    print("3. Generate an agent-based simulation using AI")
    print("4. Inspect and validate a conceptual idea model")
    print("5. Search knowledge and review real-world mapping candidates")
    print("6. Interpret and formalize a new idea with AI")

    choice = input("\nChoose an option (1-6): ").strip()

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
    elif choice == "6":
        run_ai_idea_formalization()
    else:
        print("Invalid choice. Please run the program again and choose a number from 1 to 6.")


if __name__ == "__main__":
    main()
