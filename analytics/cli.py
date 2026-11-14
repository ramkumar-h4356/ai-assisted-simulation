"""Standalone CLI for M25 analytics over saved milestone reports."""

from __future__ import annotations

import argparse
from pathlib import Path
import sys

from analytics import analyze_reports
from analytics.serialization import export_summary_csv, load_plan, load_report, save_report


def _inspect(path: Path) -> int:
    report = load_report(path)
    print(f"M25 analysis: {report.plan.analysis_name}")
    print(f"Groups: {len(report.groups)} | comparisons: {len(report.comparisons)} | Pareto entries: {len(report.pareto_frontier)}")
    print("\nGroup statistics:")
    for item in report.groups:
        interval = "not estimable" if item.confidence_lower is None else f"[{item.confidence_lower:.6g}, {item.confidence_upper:.6g}]"
        print(f"  {item.group_label} / {item.metric_name}: mean={item.mean:.6g} {item.unit or ''}; n={item.sample_size}; CI={interval}; unobserved={item.unobserved_runs}/{item.total_runs}")
    if report.comparisons:
        print("\nWelch comparisons (B minus A):")
        for item in report.comparisons:
            print(f"  {item.group_b} - {item.group_a}: diff={item.mean_difference_b_minus_a:.6g}; p={item.p_value:.4g}; Holm p={item.holm_adjusted_p_value:.4g}; Hedges g={item.hedges_g}")
    if report.pareto_frontier:
        print("\nPareto frontier:")
        for item in report.pareto_frontier:
            status = "non-dominated" if item.pareto_optimal else "dominated by " + ", ".join(item.dominated_by)
            print(f"  {item.group_label}: {status}")
    if report.insights:
        print("\nInsights:")
        for item in report.insights:
            print(f"  [{item.severity.upper()}] {item.message}")
    if report.warnings:
        print("\nInterpretation limits:")
        for item in report.warnings:
            print(f"  - {item}")
    print(f"\nFingerprint verified: {path}")
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Run M25 advanced analytics on integrity-verified M10/M11/M23/M24 reports.")
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--plan", help="Path to an M25 analytics plan JSON")
    mode.add_argument("--inspect", help="Inspect an integrity-verified M25 report JSON")
    parser.add_argument("--source-root", default=".", help="Root for relative source-report paths (default: current directory)")
    parser.add_argument("--output-dir", default="outputs/analytics", help="Directory for M25 JSON and CSV outputs")
    args = parser.parse_args(argv)
    if args.inspect:
        return _inspect(Path(args.inspect).expanduser())
    plan_path = Path(args.plan).expanduser()
    plan = load_plan(plan_path)
    report = analyze_reports(plan, source_root=args.source_root)
    output_dir = Path(args.output_dir).expanduser()
    json_path = output_dir / f"{report.analysis_id}_report.json"
    csv_path = output_dir / f"{report.analysis_id}_summary.csv"
    save_report(report, json_path)
    export_summary_csv(report, csv_path)
    print(f"M25 analysis completed: {report.plan.analysis_name}")
    print(f"Verified sources: {len(report.sources)} | groups: {len(report.groups)} | comparisons: {len(report.comparisons)}")
    print(f"JSON report: {json_path}")
    print(f"CSV export: {csv_path}")
    for finding in report.insights:
        print(f"[{finding.severity.upper()}] {finding.message}")
    for warning in report.warnings:
        print(f"[NOTE] {warning}")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as error:
        print(f"M25 analytics failed: {type(error).__name__}: {error}", file=sys.stderr)
        raise SystemExit(2)
