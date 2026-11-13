# M11 Test Report

## Build-environment results

Focused M11 tests:

```text
16 passed
```

Combined offline-compatible project tests:

```text
373 passed in 1.09s
```

Python byte-compilation of `main.py` and the M11 package passed.

The M11 CLI was smoke-tested end to end using a valid ABM M8 artifact and a
six-sample plan. Option 13 executed all six samples through M9 and saved the
fingerprinted M9 execution JSON, M11 analysis JSON and CSV summary. Option 14
reloaded the report and verified its fingerprint.

## Test coverage

- Uniform and triangular Monte Carlo sampling.
- Repeatable input vectors from a fixed sampling seed.
- Integer/float type preservation and range constraints.
- Exact M8 `user_parameter` binding enforcement, numeric-only fields and
  overlapping-path rejection.
- Exact one-run-per-sample M9 execution and sample-vector verification.
- M9 result fingerprint and M8 artifact/revision provenance verification.
- Output mean, population standard deviation, median, interpolated P05/P95
  and observed range.
- Spearman rank-correlation sensitivity screening and per-metric ranking.
- User-defined `<=`, `>=` and `between` robustness criteria, including joint
  evaluation.
- Failed-run exclusion and warning retention.
- Strict M11 plan parsing, report JSON round-trip and fingerprint tampering
  detection.
- CSV export for distributions, sensitivity scores and robustness criteria.

## Environment limitation

The build container does not include `simpy` or `groq`, so a complete
unfiltered `python -m pytest -q` run cannot collect the legacy DES/AI modules
that depend on them. The 373-pass integration command covers M11, M10, M9
execution, ABM, M8 compilation, conceptual, idea assistant, knowledge,
readiness and core suites. Real SimPy tests and the complete project suite must
still be run in the user's Windows environment.

Run in Windows:

```bash
python -m pip install -r requirements-dev.txt
python -m pytest -q
```
