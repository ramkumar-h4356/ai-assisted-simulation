"""Command-line inspection of the included conceptual model example."""

from __future__ import annotations

import argparse
from pathlib import Path

from conceptual.serialization import load_idea_project
from conceptual.validation import validate_idea_project


def inspect_example(path: str | Path | None = None) -> int:
    """Print an example project's structure and validation findings.

    Returns 0 for a structurally valid project and 1 for validation errors.
    Warnings are expected for a deliberately incomplete early-stage theory.
    """
    if path is None:
        path = Path(__file__).resolve().parents[1] / "scenarios" / "conceptual" / "decentralized_resource_cooperation.json"
    project = load_idea_project(path)
    revision = project.current_revision
    report = validate_idea_project(project)

    print("\n--- Conceptual Idea Project ---")
    print(f"Title: {project.title}")
    print(f"Project ID: {project.id}")
    print(f"Current revision: {revision.version} ({revision.id})")
    print("Original idea (preserved):")
    print(project.original_statement)
    print("\nCurrent refined statement:")
    print(revision.working_statement)
    print("\nCurrent conceptual structure:")
    for label, values in (
        ("Concepts", revision.concepts),
        ("Properties", revision.properties),
        ("Relationships", revision.relationships),
        ("Mechanisms", revision.mechanisms),
        ("Hypotheses", revision.hypotheses),
        ("Assumptions", revision.assumptions),
        ("Constraints", revision.constraints),
        ("Evidence references", revision.evidence_references),
        ("Mapping claims", revision.mappings),
        ("Open questions", revision.open_questions),
    ):
        print(f"  {label}: {len(values)}")

    print(f"\nValidation: {report.readiness.value}")
    print(f"Errors: {len(report.errors)} | Warnings: {len(report.warnings)}")
    for issue in report.issues:
        print(f"  [{issue.severity.value.upper()}] {issue.code} at {issue.path}: {issue.message}")
    print("\nValidation checks structural consistency; it does not establish whether the theory is true or simulation-ready.")
    return 0 if report.is_valid else 1


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="Inspect and validate a conceptual idea project.")
    parser.add_argument("project", nargs="?", help="Path to a conceptual project JSON file; defaults to the included example.")
    arguments = parser.parse_args()
    raise SystemExit(inspect_example(arguments.project))
