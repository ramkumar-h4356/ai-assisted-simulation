"""Run M7 against the included conceptual resource-cooperation scenario."""

from pathlib import Path

from conceptual import load_idea_project
from readiness import assess_readiness


def main() -> None:
    root = Path(__file__).resolve().parents[1]
    source = root / "scenarios" / "conceptual" / "decentralized_resource_cooperation.json"
    project = load_idea_project(source)
    report = assess_readiness(project)
    print(f"Project: {report.project_title}")
    print(f"Revision: {report.revision_id} (v{report.revision_version})")
    print(f"Readiness: {report.status.value}")
    print(report.explanation)
    print("\nParadigm suitability:")
    for item in report.paradigm_assessments:
        print(f"- {item.paradigm.value}: {item.fit.value}; backend={item.backend_status.value}")
        print(f"  {item.summary}")
        for requirement in item.missing_requirements[:3]:
            print(f"  Missing: {requirement}")
    print("\nClarifications:")
    for item in report.clarification_items:
        print(f"- [{item.priority.value}] {item.question}")
    output = root / "outputs" / f"{project.id}_m7_readiness.json"
    from readiness import save_report
    save_report(report, output)
    print(f"\nReport saved to: {output}")


if __name__ == "__main__":
    main()
