# M12 Visualization Package

`visualization/` converts integrity-checked M9 execution records and optional matching M10/M11 reports into an engine-independent visualization bundle and self-contained HTML dashboard.

## Python API

```python
from execution import load_result
from experimentation import load_report as load_m10_report
from uncertainty import load_report as load_m11_report
from visualization import build_visualization_bundle, save_bundle, save_html

result = load_result("outputs/project_m9_execution.json")
bundle = build_visualization_bundle(result)
save_bundle(bundle, "outputs/project_m12_visualization.json")
save_html(bundle, "outputs/project_m12_dashboard.html")
```

Optional analysis attachments must refer to the exact selected M9 execution result and the exact M8 compilation artifact. The builder verifies their fingerprints and provenance before including them.

## CLI

- Option 15: Build a dashboard from a saved M9 result. Optional M10 and M11 reports can be attached.
- Option 16: Open a saved dashboard in the default browser.

The generated HTML is self-contained. It uses inline CSS, JavaScript and SVG; no browser network requests, CDN, chart library, Python server or additional package is required.

## Views

- Overview: numeric metric series by completed M9 run and run status/seed/variant summary.
- DES: event timing by event type, entity waiting/service/system-time outcomes, and resource utilization.
- ABM: population by agent state over simulation steps, final population by agent type, numeric agent-attribute means and rule-evaluation counts.
- M10: variant execution summaries and metric comparisons when a matching M10 report is attached.
- M11: outcome ranges, Spearman sensitivity screening and user-defined robustness criteria when a matching M11 report is attached.

## Trace size and scientific boundaries

The builder uses deterministic endpoint-preserving downsampling when the captured trace exceeds the configured per-dashboard display-point budget. The dashboard records a warning. The original M9 execution result is never changed. Per-run summaries and derived metric series are based on recorded data only.

ABM V1 does not currently record geometric positions, so M12 does not invent spatial movement or interaction networks. It displays state snapshots, scalar attributes and rule evaluations that M9 actually stores. DES event markers are observations from the runtime event log; they are not a process-animation engine. All charts are descriptive and do not establish model validity or prove a theory.
