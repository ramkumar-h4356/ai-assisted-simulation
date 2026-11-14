
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


def run_compilation_workflow():
    """Create or validate an explicit M8 profile for a saved conceptual revision."""
    import json
    from pathlib import Path
    from conceptual import load_idea_project
    from readiness import Paradigm, assess_readiness
    from compilation import (
        CompilationParadigm, compile_profile, create_profile_template,
        load_profile, save_artifact,
    )

    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    candidates = sorted(
        list(output_dir.glob("*_m6_idea*.json")) + list(output_dir.glob("*.idea.json")),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []

    print("\n--- M8: Conceptual-to-Executable Specification ---")
    if candidates:
        print("Recent conceptual projects:")
        for index, candidate in enumerate(candidates[:10], start=1):
            print(f"  {index}. {candidate}")
    selection = input("\nProject number or conceptual JSON path: ").strip().strip('"')
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
    except Exception as error:
        print(f"Could not load conceptual project: {error}")
        return

    revision = project.current_revision
    print(f"\nProject: {project.title}")
    print(f"Revision: {project.current_revision_id}")
    print("\nSource element catalog for profile bindings:")
    for label, collection, formatter in (
        ("Concept", revision.concepts, lambda item: f"{item.name} [{item.kind.value}]"),
        ("Property", revision.properties, lambda item: f"{item.name} -> {item.concept_id} [{item.data_type.value}]"),
        ("Relationship", revision.relationships, lambda item: f"{item.label}: {item.source_concept_id} -> {item.target_concept_id}"),
        ("Mechanism", revision.mechanisms, lambda item: f"{item.name} ({item.status.value})"),
        ("Assumption", revision.assumptions, lambda item: item.statement),
        ("Constraint", revision.constraints, lambda item: item.statement),
    ):
        for item in collection:
            print(f"  {label}: {item.id} — {formatter(item)}")
    print("Select the paradigm you have chosen after reviewing M7:")
    print("  1. Discrete-event (DES V1 / SimPy)")
    print("  2. Agent-based (ABM V1)")
    print("  3. Mathematical (assessment only; no M8 backend)")
    print("  4. Data-driven (assessment only; no M8 backend)")
    selected = input("Paradigm (1-4): ").strip()
    mapping = {
        "1": (CompilationParadigm.DISCRETE_EVENT, Paradigm.DISCRETE_EVENT),
        "2": (CompilationParadigm.AGENT_BASED, Paradigm.AGENT_BASED),
        "3": (CompilationParadigm.MATHEMATICAL, Paradigm.MATHEMATICAL),
        "4": (CompilationParadigm.DATA_DRIVEN, Paradigm.DATA_DRIVEN),
    }
    if selected not in mapping:
        print("Invalid paradigm selection.")
        return
    target_paradigm, readiness_paradigm = mapping[selected]
    readiness_report = assess_readiness(project, selected_paradigm=readiness_paradigm)
    selected_assessment = readiness_report.assessment_for(readiness_paradigm)
    print(f"\nM7 status: {readiness_report.status.value}")
    print(f"Paradigm fit: {selected_assessment.fit.value}")
    print(f"Backend: {selected_assessment.backend_status.value}")
    if selected in {"3", "4"}:
        print("This paradigm can be assessed in M7, but its executable backend has not been implemented. M8 will not create a pretend model.")
        return
    if readiness_report.status.value != "ready_for_implementation_planning":
        print("M8 requires M7 status ready_for_implementation_planning. Resolve the listed M7 questions first.")
        for question in readiness_report.clarification_items:
            print(f"  - {question.question}")
        return

    profile_path_text = input("\nCompilation profile JSON path (Enter to create an editable template): ").strip().strip('"')
    if not profile_path_text:
        template = create_profile_template(project, target_paradigm)
        output_dir.mkdir(parents=True, exist_ok=True)
        template_path = output_dir / f"{project.id}_m8_{target_paradigm.value}_profile_template.json"
        version = 2
        while template_path.exists():
            template_path = output_dir / f"{project.id}_m8_{target_paradigm.value}_profile_template_v{version}.json"
            version += 1
        template_path.write_text(json.dumps(template, ensure_ascii=False, indent=2), encoding="utf-8")
        print(f"\nAn intentionally incomplete template was created: {template_path}")
        print("Edit model_data with explicit runtime values, then add bindings that connect target paths to current conceptual element IDs.")
        print("Use source='user_parameter' with a clear note for experiment values; do not present illustrative values as evidence.")
        print("Run option 8 again and provide the edited profile path.")
        return

    profile_path = Path(profile_path_text).expanduser()
    if not profile_path.is_absolute():
        profile_path = (Path.cwd() / profile_path).resolve()
    try:
        profile = load_profile(profile_path)
        result = compile_profile(project, profile)
    except Exception as error:
        print(f"Could not compile profile: {error}")
        return

    print("\nCompilation diagnostics:")
    for issue in result.issues:
        print(f"  [{issue.severity.value}] {issue.code} ({issue.path}): {issue.message}")
    if not result.is_ready:
        print("\nNo executable specification was produced. Fix the errors and try again.")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    artifact_path = output_dir / f"{project.id}_m8_{target_paradigm.value}_specification.json"
    version = 2
    while artifact_path.exists():
        artifact_path = output_dir / f"{project.id}_m8_{target_paradigm.value}_specification_v{version}.json"
        version += 1
    save_artifact(result.artifact, artifact_path)
    print(f"\nValidated specification saved: {artifact_path}")
    print(f"Artifact ID: {result.artifact.artifact_id}")
    print(f"Backend: {result.artifact.backend_name}")
    print("The native SimulationSpecification is ready for the execution milestone. No simulation was run and the conceptual project was not modified.")



def run_execution_workflow():
    """Execute an integrity-checked M8 artifact and save an M9 result."""
    import json
    from pathlib import Path
    from compilation import load_artifact
    from execution import (
        ExperimentConfig, ParameterOverride, ParameterSet,
        execute_artifact, save_result,
    )

    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    candidates = sorted(
        output_dir.glob("*_m8_*_specification*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []

    print("\n--- M9: Controlled Simulation Execution ---")
    if candidates:
        print("Recent verified M8 artifact candidates:")
        for index, candidate in enumerate(candidates[:10], start=1):
            print(f"  {index}. {candidate}")
    selection = input("\nArtifact number or M8 artifact JSON path: ").strip().strip('"')
    if not selection:
        print("No artifact selected.")
        return
    if selection.isdigit() and candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(candidates)):
            print("Invalid artifact number.")
            return
        artifact_path = candidates[index - 1]
    else:
        artifact_path = Path(selection).expanduser()
        if not artifact_path.is_absolute():
            artifact_path = (Path.cwd() / artifact_path).resolve()

    try:
        artifact = load_artifact(artifact_path)
    except Exception as error:
        print(f"Could not load or verify the M8 artifact: {error}")
        print("Execution was not started.")
        return

    print(f"\nProject: {artifact.project_title}")
    print(f"Revision: {artifact.revision_id} (v{artifact.revision_version})")
    print(f"Paradigm: {artifact.paradigm.value}")
    print(f"Backend: {artifact.backend_name}")
    print(f"Artifact ID: {artifact.artifact_id}")

    runs_text = input("Replications per parameter set [1, maximum 100 total executions]: ").strip()
    try:
        runs = int(runs_text) if runs_text else 1
    except ValueError:
        print("Number of runs must be an integer.")
        return

    seed = None
    if artifact.paradigm.value == "agent_based":
        seed_text = input("Base random seed (blank uses the seed stored in the compiled model): ").strip()
        if seed_text:
            try:
                seed = int(seed_text)
            except ValueError:
                print("Base seed must be a non-negative integer.")
                return
    else:
        print("DES V1 is deterministic; it does not use random seeds.")

    parameter_sets = ()
    parameter_path_text = input("Optional JSON file with parameter sets (blank uses the compiled baseline): ").strip().strip('"')
    if parameter_path_text:
        parameter_path = Path(parameter_path_text).expanduser()
        if not parameter_path.is_absolute():
            parameter_path = (Path.cwd() / parameter_path).resolve()
        try:
            raw_parameter_sets = json.loads(parameter_path.read_text(encoding="utf-8"))
            if not isinstance(raw_parameter_sets, list):
                raise ValueError("parameter-set JSON must contain a top-level array")
            parameter_sets = tuple(
                ParameterSet(
                    name=item["name"],
                    overrides=tuple(ParameterOverride(**override) for override in item["overrides"]),
                )
                for item in raw_parameter_sets
            )
        except Exception as error:
            print(f"Could not read parameter sets: {error}")
            return

    try:
        config = ExperimentConfig(
            runs=runs, base_seed=seed, continue_on_error=True,
            parameter_sets=parameter_sets,
        )
        print(f"Total executions: {config.total_runs}")
        result = execute_artifact(artifact, config)
    except Exception as error:
        print(f"Execution setup rejected: {error}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{artifact.project_id}_m9_execution.json"
    version = 2
    while result_path.exists():
        result_path = output_dir / f"{artifact.project_id}_m9_execution_v{version}.json"
        version += 1
    save_result(result, result_path)

    completed = sum(run.status.value == "completed" for run in result.runs)
    failed = len(result.runs) - completed
    print("\n--- Experiment Summary ---")
    print(f"Status: {result.status.value}")
    print(f"Runs completed: {completed}")
    print(f"Runs failed: {failed}")
    for run in result.runs:
        print(f"\nRun {run.run_index}: {run.status.value} | set={run.parameter_set} | seed={run.seed} | elapsed={run.elapsed_seconds:.6f}s")
        if run.parameters:
            print(f"  Parameters: {run.parameters}")
        if run.status.value == "completed":
            for metric in run.metrics:
                suffix = f" {metric.unit}" if metric.unit else ""
                print(f"  {metric.name}: {metric.value}{suffix}")
        else:
            print(f"  {run.error_type}: {run.error_message}")
    print(f"\nFull result and execution trace saved to: {result_path}")
    print("The source conceptual project and M8 artifact were not modified.")


def inspect_execution_result():
    """Display a concise summary from a saved, integrity-checked M9 result."""
    from pathlib import Path
    from execution import load_result

    output_dir = Path(__file__).resolve().parent / "outputs"
    candidates = sorted(
        output_dir.glob("*_m9_execution*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []
    print("\n--- Inspect M9 Experiment Result ---")
    if candidates:
        for index, candidate in enumerate(candidates[:10], start=1):
            print(f"  {index}. {candidate}")
    selection = input("\nResult number or M9 result JSON path: ").strip().strip('"')
    if not selection:
        print("No result selected.")
        return
    if selection.isdigit() and candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(candidates)):
            print("Invalid result number.")
            return
        result_path = candidates[index - 1]
    else:
        result_path = Path(selection).expanduser()
        if not result_path.is_absolute():
            result_path = (Path.cwd() / result_path).resolve()
    try:
        result = load_result(result_path)
    except Exception as error:
        print(f"Could not load or verify the M9 result: {error}")
        return

    print(f"\nExperiment: {result.experiment_id}")
    print(f"Project: {result.project_title}")
    print(f"Revision: {result.revision_id} (v{result.revision_version})")
    print(f"Paradigm: {result.paradigm} | Backend: {result.backend_name}")
    print(f"Outcome: {result.status.value} | Runs: {len(result.runs)}/{result.config.total_runs} total executions")
    print(f"Source M8 artifact: {result.artifact_id}")
    for run in result.runs:
        print(f"\nRun {run.run_index}: {run.status.value} | set={run.parameter_set} | seed={run.seed}")
        if run.parameters:
            print(f"  Parameters: {run.parameters}")
        if run.status.value == "completed":
            for metric in run.metrics:
                suffix = f" {metric.unit}" if metric.unit else ""
                print(f"  {metric.name}: {metric.value}{suffix}")
            trace_counts = {key: len(value) for key, value in run.trace.items() if isinstance(value, list)}
            if trace_counts:
                print(f"  Trace records: {trace_counts}")
        else:
            print(f"  {run.error_type}: {run.error_message}")
    print(f"\nResult integrity verified: {result_path}")



def run_parameter_sweep_workflow():
    """Generate a bounded M10 parameter sweep, execute it and analyze results."""
    import json
    from pathlib import Path
    from compilation import load_artifact
    from execution import ExperimentConfig, execute_artifact, load_result, save_result
    from experimentation import (
        GridFactor, analyze_results, export_summary_csv,
        generate_parameter_grid, save_report,
    )

    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    artifact_candidates = sorted(
        output_dir.glob("*_m8_*_specification*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []

    print("\n--- M10: Parameter Sweep and Comparative Analysis ---")
    if artifact_candidates:
        print("Recent M8 artifact candidates:")
        for index, candidate in enumerate(artifact_candidates[:10], start=1):
            print(f"  {index}. {candidate}")
    selection = input("\nArtifact number or M8 artifact JSON path: ").strip().strip('"')
    if not selection:
        print("No artifact selected.")
        return
    if selection.isdigit() and artifact_candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(artifact_candidates)):
            print("Invalid artifact number.")
            return
        artifact_path = artifact_candidates[index - 1]
    else:
        artifact_path = Path(selection).expanduser()
        if not artifact_path.is_absolute():
            artifact_path = (Path.cwd() / artifact_path).resolve()

    try:
        artifact = load_artifact(artifact_path)
    except Exception as error:
        print(f"Could not load or verify the M8 artifact: {error}")
        return

    print(f"\nProject: {artifact.project_title}")
    print(f"Revision: {artifact.revision_id} (v{artifact.revision_version})")
    print(f"Paradigm: {artifact.paradigm.value} | Backend: {artifact.backend_name}")
    print("Only M8 fields explicitly declared as user_parameter can be varied.")

    factor_path_text = input("Path to JSON grid-factor file: ").strip().strip('"')
    if not factor_path_text:
        print("No grid file selected.")
        return
    factor_path = Path(factor_path_text).expanduser()
    if not factor_path.is_absolute():
        factor_path = (Path.cwd() / factor_path).resolve()
    try:
        raw_factors = json.loads(factor_path.read_text(encoding="utf-8"))
        if not isinstance(raw_factors, list):
            raise ValueError("grid-factor JSON must contain a top-level array")
        factors = tuple(
            GridFactor(target_path=item["target_path"], levels=tuple(item["levels"]))
            for item in raw_factors
        )
    except Exception as error:
        print(f"Could not load grid factors: {error}")
        return

    runs_text = input("Replications per parameter-set variant [1]: ").strip()
    try:
        runs = int(runs_text) if runs_text else 1
    except ValueError:
        print("Replications must be an integer.")
        return
    if not 1 <= runs <= 100:
        print("Replications must be between 1 and 100.")
        return

    base_seed = None
    if artifact.paradigm.value == "agent_based":
        seed_text = input("Base random seed (blank uses the compiled model seed): ").strip()
        if seed_text:
            try:
                base_seed = int(seed_text)
                if base_seed < 0:
                    raise ValueError
            except ValueError:
                print("Base seed must be a non-negative integer.")
                return
    else:
        print("DES V1 is deterministic; no seed is used.")

    include_baseline_text = input("Include current compiled model as baseline? [Y/n]: ").strip().lower()
    include_baseline = include_baseline_text not in {"n", "no"}
    try:
        parameter_sets = generate_parameter_grid(
            artifact, factors, include_baseline=include_baseline,
            max_variants=100 // runs,
        )
        config = ExperimentConfig(
            runs=runs, base_seed=base_seed, continue_on_error=True,
            parameter_sets=parameter_sets,
        )
    except Exception as error:
        print(f"Experiment design rejected: {error}")
        return

    print(f"\nGenerated variants: {len(parameter_sets)}")
    print(f"Total executions: {config.total_runs}")
    for variant in parameter_sets:
        print(f"  {variant.name}: {{" + ", ".join(f"{item.target_path}={item.value!r}" for item in variant.overrides) + "}")
    confirm = input("Start this experiment? [y/N]: ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("Experiment cancelled; no simulation was run.")
        return

    try:
        result = execute_artifact(artifact, config)
    except Exception as error:
        print(f"Execution setup rejected: {error}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{artifact.project_id}_m9_sweep_execution.json"
    version = 2
    while result_path.exists():
        result_path = output_dir / f"{artifact.project_id}_m9_sweep_execution_v{version}.json"
        version += 1
    save_result(result, result_path)
    print(f"\nM9 sweep result saved: {result_path}")

    comparison_results = [result]
    print("\nOptional: add previous M9 result JSON files from this exact M8 artifact for comparison.")
    print("Enter one path at a time; submit blank when finished.")
    while True:
        extra_path_text = input("Additional M9 result path: ").strip().strip('"')
        if not extra_path_text:
            break
        extra_path = Path(extra_path_text).expanduser()
        if not extra_path.is_absolute():
            extra_path = (Path.cwd() / extra_path).resolve()
        try:
            comparison_results.append(load_result(extra_path))
            print("Verified and added.")
        except Exception as error:
            print(f"Could not add result: {error}")

    baseline_name = "baseline" if include_baseline else None
    try:
        report = analyze_results(tuple(comparison_results), baseline_parameter_set=baseline_name)
    except Exception as error:
        print(f"The M9 result was saved, but comparative analysis could not be completed: {error}")
        return

    report_path = output_dir / f"{artifact.project_id}_m10_analysis.json"
    report_version = 2
    while report_path.exists():
        report_path = output_dir / f"{artifact.project_id}_m10_analysis_v{report_version}.json"
        report_version += 1
    csv_path = report_path.with_suffix(".csv")
    save_report(report, report_path)
    export_summary_csv(report, csv_path)

    print("\n--- M10 Analysis Summary ---")
    print(f"Analysis ID: {report.analysis_id}")
    print(f"Baseline parameter set: {report.baseline_parameter_set}")
    print(f"Variants analyzed: {len(report.variants)}")
    for variant in report.variants:
        print(f"\n{variant.parameter_set}: {variant.successful_runs}/{variant.total_runs} successful")
        if variant.parameters:
            print(f"  Parameters: {variant.parameters}")
        for metric in variant.metrics:
            if metric.value_type == "numeric":
                print(f"  {metric.metric_name}: mean={metric.mean:.6g}, population SD={metric.population_stddev:.6g}, n={metric.sample_size}")
            else:
                counts = {item.value: item.count for item in metric.categories}
                print(f"  {metric.metric_name}: {counts}")
        for delta in variant.deltas_vs_baseline:
            pct = f", {delta.percent_change:.3g}%" if delta.percent_change is not None else ", percent change undefined (baseline mean is zero)"
            print(f"  Δ {delta.metric_name}: {delta.absolute_change:+.6g}{pct}")
    for warning in report.warnings:
        print(f"\nAnalysis note: {warning}")
    print(f"\nM10 analysis JSON: {report_path}")
    print(f"M10 summary CSV: {csv_path}")
    print("These are descriptive model outcomes, not proof that the model represents the real world.")


def inspect_analysis_report():
    """Inspect a saved, integrity-verified M10 analysis report."""
    from pathlib import Path
    from experimentation import load_report

    output_dir = Path(__file__).resolve().parent / "outputs"
    candidates = sorted(
        output_dir.glob("*_m10_analysis*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []
    print("\n--- Inspect M10 Comparative Analysis ---")
    if candidates:
        for index, candidate in enumerate(candidates[:10], start=1):
            print(f"  {index}. {candidate}")
    selection = input("\nAnalysis number or M10 JSON path: ").strip().strip('"')
    if not selection:
        print("No analysis selected.")
        return
    if selection.isdigit() and candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(candidates)):
            print("Invalid analysis number.")
            return
        report_path = candidates[index - 1]
    else:
        report_path = Path(selection).expanduser()
        if not report_path.is_absolute():
            report_path = (Path.cwd() / report_path).resolve()
    try:
        report = load_report(report_path)
    except Exception as error:
        print(f"Could not load or verify the M10 report: {error}")
        return

    print(f"\nProject: {report.project_title}")
    print(f"Revision: {report.revision_id} (v{report.revision_version})")
    print(f"Paradigm: {report.paradigm} | Backend: {report.backend_name}")
    print(f"Baseline: {report.baseline_parameter_set}")
    print(f"Source M8 artifact: {report.artifact_id}")
    print(f"M9 experiments included: {len(report.input_experiment_ids)}")
    for variant in report.variants:
        print(f"\n{variant.parameter_set}: {variant.successful_runs}/{variant.total_runs} successful")
        for metric in variant.metrics:
            if metric.value_type == "numeric":
                print(f"  {metric.metric_name}: mean={metric.mean:.6g}, SD={metric.population_stddev:.6g}, median={metric.median:.6g}, min={metric.minimum:.6g}, max={metric.maximum:.6g}")
            else:
                print(f"  {metric.metric_name}: " + ", ".join(f"{item.value!r}: {item.count}" for item in metric.categories))
        for delta in variant.deltas_vs_baseline:
            print(f"  Δ {delta.metric_name}: {delta.absolute_change:+.6g}")
    for warning in report.warnings:
        print(f"\nAnalysis note: {warning}")
    print(f"\nReport integrity verified: {report_path}")

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
    print("8. Compile a conceptual revision into an executable specification")
    print("9. Execute a compiled specification and save experiment results")
    print("10. Inspect a saved experiment result")
    print("11. Design and run a parameter sweep; compare M9 results")
    print("12. Inspect a saved M10 comparative analysis")
    print("13. Run M11 sensitivity, uncertainty and robustness analysis")
    print("14. Inspect a saved M11 uncertainty report")
    print("15. Build an interactive visualization dashboard from M9/M10/M11 results")
    print("16. Open a saved M12 dashboard in your browser")
    print("17. Open the M13 project workbench")

    choice = input("\nChoose an option (1-17): ").strip()

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
    elif choice == "8":
        run_compilation_workflow()
    elif choice == "9":
        run_execution_workflow()
    elif choice == "10":
        inspect_execution_result()
    elif choice == "11":
        run_parameter_sweep_workflow()
    elif choice == "12":
        inspect_analysis_report()
    elif choice == "13":
        run_uncertainty_analysis_workflow()
    elif choice == "14":
        inspect_uncertainty_report()
    elif choice == "15":
        build_visualization_workflow()
    elif choice == "16":
        open_visualization_workflow()
    elif choice == "17":
        from workbench.cli import run_workbench
        run_workbench()
    else:
        print("Invalid choice. Please run the program again and choose a number from 1 to 17.")



def run_uncertainty_analysis_workflow():
    """Sample uncertain inputs, execute through M9, and produce an M11 report."""
    from pathlib import Path
    from compilation import load_artifact
    from execution import save_result
    from uncertainty import (
        export_summary_csv, load_plan, run_uncertainty_analysis, save_report,
    )

    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    artifact_candidates = sorted(
        output_dir.glob("*_m8_*_specification*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []

    print("\n--- M11: Sensitivity, Uncertainty and Robustness Analysis ---")
    if artifact_candidates:
        print("Recent M8 artifact candidates:")
        for index, candidate in enumerate(artifact_candidates[:10], start=1):
            print(f"  {index}. {candidate}")
    selection = input("\nArtifact number or M8 artifact JSON path: ").strip().strip('"')
    if not selection:
        print("No artifact selected.")
        return
    if selection.isdigit() and artifact_candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(artifact_candidates)):
            print("Invalid artifact number.")
            return
        artifact_path = artifact_candidates[index - 1]
    else:
        artifact_path = Path(selection).expanduser()
        if not artifact_path.is_absolute():
            artifact_path = (Path.cwd() / artifact_path).resolve()

    try:
        artifact = load_artifact(artifact_path)
    except Exception as error:
        print(f"Could not load or verify the M8 artifact: {error}")
        return

    print(f"\nProject: {artifact.project_title}")
    print(f"Revision: {artifact.revision_id} (v{artifact.revision_version})")
    print(f"Paradigm: {artifact.paradigm.value} | Backend: {artifact.backend_name}")
    print("Only numeric M8 fields explicitly declared as user_parameter can be sampled.")

    plan_path_text = input("Path to M11 uncertainty-plan JSON: ").strip().strip('"')
    if not plan_path_text:
        print("No uncertainty plan selected.")
        return
    plan_path = Path(plan_path_text).expanduser()
    if not plan_path.is_absolute():
        plan_path = (Path.cwd() / plan_path).resolve()
    try:
        plan = load_plan(plan_path)
    except Exception as error:
        print(f"Could not load M11 plan: {error}")
        return

    print(f"\nMonte Carlo samples: {plan.sample_count}")
    print(f"Sampling seed: {plan.sampling_seed}")
    for parameter in plan.parameters:
        details = f"{parameter.distribution} [{parameter.lower}, {parameter.upper}]"
        if parameter.mode is not None:
            details += f", mode={parameter.mode}"
        print(f"  {parameter.target_path}: {details}")
    if plan.criteria:
        print("\nUser-defined robustness criteria:")
        for criterion in plan.criteria:
            expression = f"metric {criterion.operator} {criterion.threshold}"
            if criterion.operator == "between":
                expression = f"{criterion.threshold} <= metric <= {criterion.upper_threshold}"
            print(f"  {criterion.metric_name}: {expression}")
    else:
        print("No robustness thresholds supplied; only uncertainty and sensitivity will be reported.")

    execution_base_seed = None
    if artifact.paradigm.value == "agent_based":
        seed_text = input("ABM execution base seed (blank uses compiled model seed): ").strip()
        if seed_text:
            try:
                execution_base_seed = int(seed_text)
                if execution_base_seed < 0:
                    raise ValueError
            except ValueError:
                print("Execution base seed must be a non-negative integer.")
                return
        print("ABM run-to-run randomness will contribute to the observed output spread.")
    else:
        print("DES V1 is deterministic; observed output spread comes from sampled inputs.")

    print(f"\nM11 will execute exactly {plan.sample_count} model runs through M9.")
    confirm = input("Start this uncertainty experiment? [y/N]: ").strip().lower()
    if confirm not in {"y", "yes"}:
        print("Experiment cancelled; no simulation was run.")
        return

    try:
        result, report = run_uncertainty_analysis(
            artifact, plan, execution_base_seed=execution_base_seed,
        )
    except Exception as error:
        print(f"M11 execution or analysis failed: {error}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    result_path = output_dir / f"{artifact.project_id}_m9_m11_sampling_execution.json"
    version = 2
    while result_path.exists():
        result_path = output_dir / f"{artifact.project_id}_m9_m11_sampling_execution_v{version}.json"
        version += 1
    report_path = output_dir / f"{artifact.project_id}_m11_uncertainty_report.json"
    report_version = 2
    while report_path.exists():
        report_path = output_dir / f"{artifact.project_id}_m11_uncertainty_report_v{report_version}.json"
        report_version += 1
    csv_path = report_path.with_suffix(".csv")
    save_result(result, result_path)
    save_report(report, report_path)
    export_summary_csv(report, csv_path)

    print("\n--- M11 Outcome Distributions ---")
    for metric in report.metric_distributions:
        unit = f" {metric.unit}" if metric.unit else ""
        print(
            f"{metric.metric_name}: mean={metric.mean:.6g}{unit}, "
            f"SD={metric.population_stddev:.6g}, median={metric.median:.6g}, "
            f"P05={metric.percentile_05:.6g}, P95={metric.percentile_95:.6g}, "
            f"range=[{metric.minimum:.6g}, {metric.maximum:.6g}], n={metric.sample_size}"
        )

    print("\n--- M11 Sensitivity Screening (Spearman rank correlation) ---")
    grouped = {}
    for score in report.sensitivity:
        grouped.setdefault(score.metric_name, []).append(score)
    for metric_name, scores in grouped.items():
        print(f"{metric_name}:")
        for score in sorted(scores, key=lambda item: item.absolute_rho or -1, reverse=True):
            value = f"{score.spearman_rho:+.4f}" if score.spearman_rho is not None else "not estimable"
            print(f"  {score.parameter_path}: rho={value}, rank={score.rank}")

    print("\n--- M11 Robustness ---")
    for criterion in report.robustness.criteria:
        fraction = f"{criterion.observed_fraction:.1%}" if criterion.observed_fraction is not None else "not evaluated"
        print(f"{criterion.metric_name}: {criterion.passing_runs}/{criterion.evaluated_runs} met criterion ({fraction})")
    if report.criteria:
        fraction = f"{report.robustness.observed_fraction:.1%}" if report.robustness.observed_fraction is not None else "not evaluated"
        print(f"All criteria jointly met: {report.robustness.passing_runs}/{report.robustness.evaluated_runs} ({fraction})")

    for warning in report.warnings:
        print(f"\nAnalysis note: {warning}")
    print(f"\nM9 sampled execution: {result_path}")
    print(f"M11 report JSON: {report_path}")
    print(f"M11 summary CSV: {csv_path}")
    print("Results are conditional on the specified model, distributions, sample design and execution settings.")


def inspect_uncertainty_report():
    """Inspect a saved, integrity-verified M11 report."""
    from pathlib import Path
    from uncertainty import load_report

    output_dir = Path(__file__).resolve().parent / "outputs"
    candidates = sorted(
        output_dir.glob("*_m11_uncertainty_report*.json"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []
    print("\n--- Inspect M11 Uncertainty Report ---")
    if candidates:
        for index, candidate in enumerate(candidates[:10], start=1):
            print(f"  {index}. {candidate}")
    selection = input("\nReport number or M11 JSON path: ").strip().strip('"')
    if not selection:
        print("No report selected.")
        return
    if selection.isdigit() and candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(candidates)):
            print("Invalid report number.")
            return
        report_path = candidates[index - 1]
    else:
        report_path = Path(selection).expanduser()
        if not report_path.is_absolute():
            report_path = (Path.cwd() / report_path).resolve()
    try:
        report = load_report(report_path)
    except Exception as error:
        print(f"Could not load or verify M11 report: {error}")
        return

    print(f"\nProject: {report.project_title}")
    print(f"Revision: {report.revision_id} (v{report.revision_version})")
    print(f"Paradigm: {report.paradigm} | Backend: {report.backend_name}")
    print(f"M8 artifact: {report.artifact_id}")
    print(f"M9 experiment: {report.experiment_id}")
    print(f"Samples: {report.sample_count} | Failed runs: {report.failed_runs}")
    print(f"Sampling seed: {report.sampling_seed}")
    print("\nOutcome distributions:")
    for metric in report.metric_distributions:
        print(f"  {metric.metric_name}: mean={metric.mean:.6g}, SD={metric.population_stddev:.6g}, P05={metric.percentile_05:.6g}, P95={metric.percentile_95:.6g}, range=[{metric.minimum:.6g}, {metric.maximum:.6g}]")
    print("\nSensitivity ranking:")
    for metric_name in sorted({item.metric_name for item in report.sensitivity}):
        print(f"  {metric_name}:")
        scores = [item for item in report.sensitivity if item.metric_name == metric_name]
        for score in sorted(scores, key=lambda item: item.absolute_rho or -1, reverse=True):
            rho = f"{score.spearman_rho:+.4f}" if score.spearman_rho is not None else "not estimable"
            print(f"    {score.parameter_path}: rho={rho}, rank={score.rank}")
    if report.criteria:
        print("\nRobustness criteria:")
        for item in report.robustness.criteria:
            fraction = f"{item.observed_fraction:.1%}" if item.observed_fraction is not None else "not evaluated"
            print(f"  {item.metric_name}: {item.passing_runs}/{item.evaluated_runs} ({fraction})")
        fraction = f"{report.robustness.observed_fraction:.1%}" if report.robustness.observed_fraction is not None else "not evaluated"
        print(f"  All criteria jointly met: {report.robustness.passing_runs}/{report.robustness.evaluated_runs} ({fraction})")
    for warning in report.warnings:
        print(f"\nAnalysis note: {warning}")
    print(f"\nReport integrity verified: {report_path}")



def build_visualization_workflow():
    """Build a standalone, offline M12 dashboard from verified M9/M10/M11 records."""
    from pathlib import Path
    from execution import load_result
    from experimentation import load_report as load_m10_report
    from uncertainty import load_report as load_m11_report
    from visualization import build_visualization_bundle, save_bundle, save_html

    root = Path(__file__).resolve().parent
    output_dir = root / "outputs"
    result_candidates = []
    if output_dir.exists():
        for candidate in sorted(output_dir.glob("*_m9*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
            try:
                result_candidates.append((candidate, load_result(candidate)))
            except Exception:
                continue

    print("\n--- M12: Interactive Simulation Visualization ---")
    if result_candidates:
        print("Recent integrity-verified M9 execution results:")
        for index, (candidate, result) in enumerate(result_candidates[:10], start=1):
            print(f"  {index}. {candidate} | {result.project_title} | {result.paradigm} | {len(result.runs)} runs")
    selection = input("\nM9 result number or M9 execution JSON path: ").strip().strip('"')
    if not selection:
        print("No M9 result selected.")
        return
    if selection.isdigit() and result_candidates:
        index = int(selection)
        if not 1 <= index <= min(10, len(result_candidates)):
            print("Invalid result number.")
            return
        result_path, result = result_candidates[index - 1]
    else:
        result_path = Path(selection).expanduser()
        if not result_path.is_absolute():
            result_path = (Path.cwd() / result_path).resolve()
        try:
            result = load_result(result_path)
        except Exception as error:
            print(f"Could not load or verify the M9 result: {error}")
            return

    print(f"\nProject: {result.project_title}")
    print(f"Revision: {result.revision_id} (v{result.revision_version})")
    print(f"Paradigm: {result.paradigm} | Backend: {result.backend_name}")
    print(f"Experiment: {result.experiment_id} | Runs: {len(result.runs)}")
    print("Optional analysis reports must refer to this exact M9 result and M8 artifact.")

    m10_report = None
    m10_path_text = input("Optional matching M10 analysis JSON path (blank to skip): ").strip().strip('"')
    if m10_path_text:
        m10_path = Path(m10_path_text).expanduser()
        if not m10_path.is_absolute():
            m10_path = (Path.cwd() / m10_path).resolve()
        try:
            m10_report = load_m10_report(m10_path)
        except Exception as error:
            print(f"Could not load or verify the M10 report: {error}")
            return

    m11_report = None
    m11_path_text = input("Optional matching M11 uncertainty report JSON path (blank to skip): ").strip().strip('"')
    if m11_path_text:
        m11_path = Path(m11_path_text).expanduser()
        if not m11_path.is_absolute():
            m11_path = (Path.cwd() / m11_path).resolve()
        try:
            m11_report = load_m11_report(m11_path)
        except Exception as error:
            print(f"Could not load or verify the M11 report: {error}")
            return

    point_limit_text = input("Maximum visual trace points [20000]: ").strip()
    try:
        point_limit = int(point_limit_text) if point_limit_text else 20_000
        if point_limit < 10:
            raise ValueError
    except ValueError:
        print("Point limit must be an integer of at least 10.")
        return

    try:
        bundle = build_visualization_bundle(
            result, analysis_report=m10_report,
            uncertainty_report=m11_report, point_limit=point_limit,
        )
    except Exception as error:
        print(f"Visualization build rejected: {error}")
        return

    output_dir.mkdir(parents=True, exist_ok=True)
    base = output_dir / f"{result.project_id}_m12_visualization"
    bundle_path = base.with_suffix(".json")
    html_path = output_dir / f"{result.project_id}_m12_dashboard.html"
    version = 2
    while bundle_path.exists() or html_path.exists():
        bundle_path = output_dir / f"{result.project_id}_m12_visualization_v{version}.json"
        html_path = output_dir / f"{result.project_id}_m12_dashboard_v{version}.html"
        version += 1
    save_bundle(bundle, bundle_path)
    save_html(bundle, html_path)

    print("\n--- M12 Dashboard Summary ---")
    print(f"Runs: {len(bundle.data['runs'])}")
    print(f"Numeric metrics: {len(bundle.data['metric_series'])}")
    print(f"Trace views: {len(bundle.data['trace_views'])}")
    print(f"M10 comparison attached: {'yes' if bundle.data['m10'] else 'no'}")
    print(f"M11 uncertainty attached: {'yes' if bundle.data['m11'] else 'no'}")
    for warning in bundle.warnings:
        print(f"\nVisualization note: {warning}")
    print(f"\nVisualization bundle JSON: {bundle_path}")
    print(f"Standalone dashboard HTML: {html_path}")
    print("Open the HTML file in a modern browser. It works offline and requires no server or external libraries.")


def open_visualization_workflow():
    """Open a saved standalone M12 dashboard in the default web browser."""
    from pathlib import Path
    import webbrowser

    output_dir = Path(__file__).resolve().parent / "outputs"
    candidates = sorted(
        output_dir.glob("*_m12_dashboard*.html"),
        key=lambda item: item.stat().st_mtime,
        reverse=True,
    ) if output_dir.exists() else []
    print("\n--- Open M12 Visualization Dashboard ---")
    if not candidates:
        print("No saved M12 dashboard was found. Run option 15 first.")
        return
    for index, candidate in enumerate(candidates[:10], start=1):
        print(f"  {index}. {candidate}")
    selection = input("\nDashboard number or HTML path: ").strip().strip('"')
    if not selection:
        print("No dashboard selected.")
        return
    if selection.isdigit():
        index = int(selection)
        if not 1 <= index <= min(10, len(candidates)):
            print("Invalid dashboard number.")
            return
        dashboard = candidates[index - 1]
    else:
        dashboard = Path(selection).expanduser()
        if not dashboard.is_absolute():
            dashboard = (Path.cwd() / dashboard).resolve()
    if not dashboard.exists() or dashboard.suffix.lower() != ".html":
        print("The selected HTML dashboard does not exist.")
        return
    opened = webbrowser.open(dashboard.as_uri())
    if opened:
        print(f"Opened dashboard: {dashboard}")
    else:
        print(f"The browser did not report that it opened. Open this file manually: {dashboard}")


if __name__ == "__main__":
    main()
