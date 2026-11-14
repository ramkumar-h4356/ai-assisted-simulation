"""Command-line entry point for a reproducible M23 optimization run."""

from __future__ import annotations

import argparse
from pathlib import Path
import re

from compilation import load_artifact
from execution import save_result
from optimization import export_summary_csv, load_plan, optimize_parameters, save_report


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M23 objective-driven optimization on a verified M8 artifact.")
    parser.add_argument("--artifact", required=True, help="Path to an integrity-verified M8 artifact JSON file")
    parser.add_argument("--plan", required=True, help="Path to an M23 optimization-plan JSON file")
    parser.add_argument("--output-dir", default="outputs", help="Directory for M9 execution, M23 report and CSV")
    parser.add_argument("--execution-base-seed", type=int, default=None, help="Optional M9 base seed (used by ABM)")
    args = parser.parse_args(argv)

    try:
        artifact = load_artifact(args.artifact)
        plan = load_plan(args.plan)
        result, report = optimize_parameters(artifact, plan, execution_base_seed=args.execution_base_seed)
        output_dir = Path(args.output_dir).expanduser().resolve()
        output_dir.mkdir(parents=True, exist_ok=True)
        safe_project = re.sub(r"[^A-Za-z0-9._-]+", "_", artifact.project_id).strip("._-") or "project"
        result_path = output_dir / f"{safe_project}_m9_m23_execution.json"
        report_path = output_dir / f"{safe_project}_m23_optimization_report.json"
        csv_path = output_dir / f"{safe_project}_m23_candidates.csv"
        save_result(result, result_path)
        save_report(report, report_path)
        export_summary_csv(report, csv_path)
    except Exception as error:
        parser.exit(2, f"M23 optimization failed: {error}\n")

    print(f"Project: {report.project_title}")
    print(f"Revision: {report.revision_id} (v{report.revision_version})")
    print(f"Paradigm: {report.paradigm} | Backend: {report.backend_name}")
    print(f"Objective: {plan.objective.metric_name} ({plan.objective.direction})")
    print(f"Candidates: {len(report.candidates)} | M9 runs: {len(result.runs)}")
    if report.best_parameter_set is None:
        print("Best candidate: none (no feasible candidate)")
    else:
        best = next(item for item in report.candidates if item.parameter_set == report.best_parameter_set)
        print(f"Best candidate: {best.parameter_set}")
        print(f"Objective mean: {best.objective_mean:.8g}")
        print(f"Parameters: {best.parameters}")
        if report.objective_improvement is not None:
            print(f"Improvement over feasible baseline: {report.objective_improvement:+.8g}")
    for warning in report.warnings:
        print(f"Note: {warning}")
    print(f"M9 result: {result_path}")
    print(f"M23 report: {report_path}")
    print(f"Candidate CSV: {csv_path}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
