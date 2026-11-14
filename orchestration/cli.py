"""Non-interactive command-line runner for M24 experiment suites."""

from __future__ import annotations

import argparse
from pathlib import Path

from orchestration.engine import execute_suite
from orchestration.serialization import export_summary_csv, load_plan, save_report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run an M24 cross-engine experiment suite through M9.")
    parser.add_argument("--plan", required=True, help="Path to an M24 experiment suite plan JSON")
    parser.add_argument("--artifact-root", default=".", help="Root directory for relative M8 artifact paths (default: current directory)")
    parser.add_argument("--output-dir", default="outputs", help="Directory for M9 results, M24 report and CSV")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    plan_path = Path(args.plan).expanduser().resolve()
    artifact_root = Path(args.artifact_root).expanduser().resolve()
    output_dir = Path(args.output_dir).expanduser().resolve()
    try:
        plan = load_plan(plan_path)
        report = execute_suite(plan, artifact_root=artifact_root, output_dir=output_dir)
        report_path = save_report(report, output_dir / f"{report.suite_id}_report.json")
        csv_path = export_summary_csv(report, output_dir / f"{report.suite_id}_metrics.csv")
    except Exception as error:
        print(f"M24 suite failed: {type(error).__name__}: {error}")
        return 2

    print(f"Suite: {report.suite_name} ({report.status})")
    print(f"Members: {len(report.members)} | requested M9 executions: {plan.total_executions}")
    for member in report.members:
        print(
            f"  {member.member_id}: {member.label} | paradigm={member.paradigm or 'unavailable'} | "
            f"status={member.status} | successful={member.successful_runs}/{member.total_runs}"
        )
        if member.error_message:
            print(f"    error: {member.error_type}: {member.error_message}")
    if report.ranking:
        print("Comparison ranking:")
        for item in report.ranking:
            suffix = f" {item.unit}" if item.unit else ""
            print(f"  {item.rank}. {item.member_label} / {item.parameter_set}: {item.mean:.8g}{suffix} (n={item.sample_size})")
    for warning in report.warnings:
        print(f"Note: {warning}")
    print(f"M24 report: {report_path}")
    print(f"Metric CSV: {csv_path}")
    print(f"M9 result files: {output_dir}")
    return 0 if report.status == "completed" else 1


if __name__ == "__main__":
    raise SystemExit(main())
