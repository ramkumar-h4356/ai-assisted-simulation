
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



def run_readiness_assessment():
    """Assess a saved M4/M6 idea and compare supported simulation paradigms."""
    import re
    from pathlib import Path
    from conceptual import load_idea_project
    from readiness import Paradigm, assess_readiness, save_report

    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    candidates = sorted(
        output_dir.glob("*_m6_idea*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []

    print("\n--- M7: Simulation Readiness Assessment ---")
    if candidates:
        print("Recent M6 idea projects:")
        for index, candidate in enumerate(candidates[:10], start=1):
            print(f"  {index}. {candidate}")
        print("Enter a listed number, or provide a path to another saved conceptual project.")
    else:
        print("No saved M6 project was found automatically. You may provide a path to a conceptual JSON project.")

    selection = input("\nProject number or file path: ").strip().strip('"')
    if not selection:
        print("No project selected.")
        return
    if selection.isdigit() and candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(candidates)):
            print("Invalid project number.")
            return
        project_path = candidates[index - 1]
    else:
        project_path = Path(selection).expanduser()
        if not project_path.is_absolute():
            project_path = (Path.cwd() / project_path).resolve()

    try:
        project = load_idea_project(project_path)
        report = assess_readiness(project)
    except Exception as error:
        print(f"Could not assess the selected project: {error}")
        return

    def display(current_report):
        print(f"\nProject: {current_report.project_title}")
        print(f"Revision: {current_report.revision_id} (version {current_report.revision_version})")
        print(f"Readiness: {current_report.status.value}")
        print(current_report.explanation)
        if current_report.validation_errors:
            print("\nStructural validation errors:")
            for item in current_report.validation_errors:
                print(f"  - {item}")
        print("\nParadigm assessments:")
        for item in current_report.paradigm_assessments:
            print(f"\n  {item.paradigm.value}: {item.fit.value}")
            print(f"  Backend: {item.backend_status.value}")
            print(f"  {item.summary}")
            for finding in item.supporting_findings:
                print(f"    + {finding.title}: {finding.explanation}")
                if finding.element_ids:
                    print(f"      Elements: {', '.join(finding.element_ids)}")
            for limitation in item.limitations:
                print(f"    ! {limitation.title}: {limitation.explanation}")
            for requirement in item.missing_requirements:
                print(f"    - Missing: {requirement}")
        if current_report.recommended_paradigms:
            print("\nBest-supported paradigm(s): " + ", ".join(item.value for item in current_report.recommended_paradigms))
        else:
            print("\nNo paradigm can currently be recommended from the available structure.")
        if current_report.clarification_items:
            print("\nClarification questions:")
            for item in current_report.clarification_items:
                print(f"  [{item.priority.value}] {item.question}")
                print(f"    Why: {item.reason}")

    display(report)
    choices = {
        "1": Paradigm.DISCRETE_EVENT,
        "2": Paradigm.AGENT_BASED,
        "3": Paradigm.MATHEMATICAL,
        "4": Paradigm.DATA_DRIVEN,
    }
    print("\nOptional: select a paradigm to test implementation-planning readiness.")
    print("  1. Discrete-event  2. Agent-based  3. Mathematical  4. Data-driven")
    selected = input("Selection (Enter to skip): ").strip()
    if selected:
        if selected not in choices:
            print("Unknown selection; retaining the unselected assessment.")
        else:
            report = assess_readiness(project, selected_paradigm=choices[selected])
            print(f"\nSelected paradigm: {report.selected_paradigm.value}")
            print(f"Updated readiness: {report.status.value}")
            print(report.explanation)

    output_dir.mkdir(parents=True, exist_ok=True)
    stem = re.sub(r"[^a-z0-9_-]+", "_", project.id.casefold()).strip("_") or "idea"
    report_path = output_dir / f"{stem}_m7_readiness.json"
    version = 2
    while report_path.exists():
        report_path = output_dir / f"{stem}_m7_readiness_v{version}.json"
        version += 1
    save_report(report, report_path)
    print(f"\nM7 readiness report saved to: {report_path}")
    print("The conceptual project was not modified. The report is tied to the exact revision assessed.")

def main():
    """Display the program menu."""
    print("\n=== AI-Assisted Simulation System ===")
    print("1. Generate a simulation using AI")
    print("2. Compare one machine vs. two machines")
    print("3. Generate an agent-based simulation using AI")
    print("4. Inspect and validate a conceptual idea model")
    print("5. Search knowledge and review real-world mapping candidates")
    print("6. Interpret and formalize a new idea with AI")
    print("7. Assess simulation readiness and compare paradigms")

    choice = input("\nChoose an option (1-7): ").strip()

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
    elif choice == "7":
        run_readiness_assessment()
    else:
        print("Invalid choice. Please run the program again and choose a number from 1 to 7.")


if __name__ == "__main__":
    main()
