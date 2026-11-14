"""Standalone M26 model verification and validation CLI."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from validation import export_check_csv, load_plan, load_report, save_report, validate_model


def _inspect(path: Path) -> int:
    report = load_report(path)
    print(f"M26 validation: {report.validation_name}")
    print(f"Overall status: {report.overall_status}")
    print(f"Paradigm: {report.paradigm} | Backend: {report.backend_name}")
    print(f"M8 artifact: {report.artifact_id} | fingerprint: {report.artifact_fingerprint}")
    print(f"M9 experiment: {report.experiment_id} | fingerprint: {report.result_fingerprint}")
    if report.repeatability_experiment_id:
        print(f"Repeatability run: {report.repeatability_experiment_id}")
    print("\nChecks:")
    for item in report.checks:
        print(f"  [{item.status.upper():7}] {item.check_id}: {item.message}")
    print("\nInterpretation limits:")
    for item in report.interpretation_limits:
        print(f"  - {item}")
    print(f"\nFingerprint verified: {path}")
    return 0 if report.overall_status != "failed" else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Verify M8 models and validate M9 execution evidence.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", help="Path to an M26 validation plan JSON")
    mode.add_argument("--inspect", help="Inspect an integrity-verified M26 report JSON")
    parser.add_argument("--artifact-root", default=".", help="Root directory for relative M8 artifact/M9 result paths")
    parser.add_argument("--output-dir", default="outputs/validation", help="Directory for generated M9 evidence and M26 reports")
    args = parser.parse_args(argv)
    if args.inspect:
        return _inspect(Path(args.inspect).expanduser())
    plan = load_plan(Path(args.plan).expanduser())
    report = validate_model(plan, artifact_root=args.artifact_root, output_dir=args.output_dir)
    output_dir = Path(args.output_dir).expanduser()
    output_dir.mkdir(parents=True, exist_ok=True)
    report_path = output_dir / f"{report.validation_id}_report.json"
    csv_path = output_dir / f"{report.validation_id}_checks.csv"
    save_report(report, report_path)
    export_check_csv(report, csv_path)
    passed = sum(item.status == "passed" for item in report.checks)
    failed = sum(item.status == "failed" for item in report.checks)
    skipped = sum(item.status == "skipped" for item in report.checks)
    print(f"M26 validation: {report.validation_name}")
    print(f"Overall status: {report.overall_status}")
    print(f"Paradigm: {report.paradigm} | checks passed={passed}, failed={failed}, skipped={skipped}")
    print(f"M8 artifact: {report.artifact_id}")
    print(f"M9 experiment: {report.experiment_id}")
    print(f"JSON report: {report_path}")
    print(f"Checks CSV: {csv_path}")
    for item in report.checks:
        if item.status in {"failed", "warning"}:
            print(f"[{item.status.upper()}] {item.check_id}: {item.message}")
    return 1 if report.overall_status == "failed" else 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"M26 validation failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(2)
