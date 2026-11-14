# M12 Architecture — Simulation Visualization and Interactive Exploration

## Goal

Provide an inspectable, interactive, offline visualization layer for recorded simulation results without coupling chart rendering to DES, ABM or future simulation engines.

## Dependency flow

```text
M8 Compilation Artifact (provenance reference)
                 |
M9 ExperimentResult (required, fingerprint verified)
         |                         |
         |                         +--> M10 AnalysisReport (optional, exact result match)
         |                         |
         |                         +--> M11 UncertaintyReport (optional, exact result match)
         |                                      |
         +--------------------+-----------------+
                              |
                    M12 Visualization Builder
                              |
              Engine-independent visualization data
                       /                  \
          Fingerprinted JSON bundle   Standalone HTML
                                         |
                                 Browser CSS/JS/SVG
```

## Components

- `visualization/models.py`: immutable top-level bundle contract and JSON-compatible-data validation.
- `visualization/builder.py`: verifies source-result fingerprints, verifies optional analysis provenance, creates run-level metric series, builds paradigm-specific trace aggregates and downsamples display data where needed.
- `visualization/serialization.py`: canonical SHA-256 fingerprints, strict JSON parsing, atomic JSON writes, standalone HTML rendering and atomic HTML writes.
- `main.py` options 15–16: select source reports, build artifacts and open a saved dashboard.

## Dashboard sections

### Overview

KPI cards summarize run counts. A metric selector displays numeric metric values across completed executions. The run table includes status, seed, parameter-set name and recorded metrics.

### DES trace

The selected run displays a simulation-time event timeline with event-type lanes. Entity records show arrival, completion, waiting, service and time-in-system values. Resource summaries display completed services, average wait, average service and utilization.

### ABM trace

The selected run's history snapshots are aggregated into agent-state counts over simulation steps, final population by agent type, numeric agent-attribute means grouped by type and rule-evaluation counts. M12 does not generate coordinates because ABM V1's stored history does not contain spatial positions.

### Experiment and uncertainty panels

An optional M10 report contributes variant summaries and numeric metric comparisons. An optional M11 report contributes distribution summaries, Spearman sensitivity rankings and observed pass fractions for the declared robustness criteria.

## Provenance and integrity

A dashboard always has one exact M9 source result. The M9 fingerprint is recomputed before construction. An M10 report must include the selected experiment ID and its exact result fingerprint. An M11 report's source experiment ID and fingerprint must match the selected M9 result. Both reports must share the exact M8 artifact fingerprint, project, revision, paradigm and backend. The generated bundle receives its own SHA-256 fingerprint and strict schema validation on load.

## Size policy

The default dashboard trace point budget is 20,000 across completed runs. A custom budget must be at least 10 and at least two points per successful run; each run receives a deterministic share. DES events/entities and ABM snapshots use evenly spaced indices that preserve the first and last record. Resource summaries are retained. A warning is stored when any trace is downsampled. M9 source JSON remains unchanged.

## Security and portability

HTML embeds the JSON payload with `<`, `>` and `&` escaped so untrusted labels cannot terminate the data script element. The dashboard uses text nodes or escaped table values for data labels. It includes no third-party JavaScript, remote fonts, CDN assets, network fetches or server dependency. It can be opened directly as a local HTML file.

## Explicit limitations

- Charts summarize recorded values; they do not validate scientific assumptions or prove a theory.
- The default M9 result must contain at least one successful execution.
- Numeric metrics are charted as values over run index, not as continuous simulation-time series unless the paradigm trace contains time-indexed history.
- DES uses event timestamps and entity/resource outcomes; M12 does not reconstruct unrecorded internal queue states.
- ABM V1 does not currently record geometric positions or explicit interaction events; the dashboard does not infer either.
- M10/M11 reports from other executions are rejected even when they share a project or revision.
- Downsampled display points are not a replacement for the exact source data.
