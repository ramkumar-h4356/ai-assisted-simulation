# M10 Test Report

Command:

```bash
python -m pytest -q tests/experimentation
```

Result at initial milestone verification:

```text
24 passed
```

Coverage includes:

- Cartesian grid generation with and without the compiled baseline.
- Stable, unique parameter-set naming.
- Rejection of conceptual fields, invalid bindings, type changes,
  overlapping/duplicate paths, duplicate levels and oversized grids.
- Rejection of tampered M8 artifacts.
- End-to-end ABM sweep execution through M9.
- Variant-level numeric summaries and percentage deltas.
- Factor-level aggregation and trace-derived ABM/DES metric summaries, including final agent attributes, entity timing and resource utilization.
- Categorical metric count aggregation and nested JSON round-trip.
- Multi-run M9 provenance requirements and duplicate-result rejection.
- Explicit baseline selection validation.
- Failed-run counting and successful-run-only aggregation.
- Rejection of conflicting parameter values under one variant label.
- M10 JSON round-trip, report fingerprint tampering detection, strict unknown
  field rejection and CSV export.

Combined offline-compatible command:

```bash
python -m pytest -q tests/experimentation tests/execution tests/abm tests/compilation tests/conceptual tests/idea_assistant tests/knowledge tests/readiness tests/core
```

Result after M10 integration:

```text
357 passed
```

Environment note: the build container lacks `simpy` and `groq`. A full
`python -m pytest -q` attempt therefore stops during collection with 9 import
errors in legacy DES/AI test modules. Real SimPy execution and those legacy
tests remain for Windows verification.
