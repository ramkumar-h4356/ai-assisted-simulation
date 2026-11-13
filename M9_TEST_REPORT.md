# M9 Test Report

## Tests executed

Command:

```bash
python -m pytest -q tests/execution tests/abm tests/compilation tests/conceptual tests/idea_assistant tests/knowledge tests/readiness tests/core --disable-warnings --maxfail=1
```

Result:

```text
333 passed in 1.12s
```

This run covers the new M9 tests plus the listed independent packages. It does
not include DES-dependent test modules because `simpy` is absent in the build
environment.

The focused M9 execution package was also run independently:

```text
24 passed in 0.25s
```

## M9-specific coverage

- ABM execution from a verified M8 artifact.
- Multiple runs with consecutive seeds.
- Replay reproducibility for identical seed schedules.
- Fallback to the compiled ABM model seed.
- Rejection of unseeded ABM runs.
- Rejection of random seeds for deterministic DES V1.
- Rejection of modified/tampered M8 artifact content.
- M7 implementation-readiness metadata gate.
- Parameter variation restricted to exact M8 `user_parameter` bindings;
  conceptual fields cannot be overridden.
- ABM and DES parameter-variant application, model revalidation and source
  artifact immutability.
- Parameter-set/replication run budgets and per-run parameter provenance.
- Run-count and estimated trace-budget limits.
- Structured failure records when a backend cannot execute.
- Continue-on-error partial results and early stop when configured.
- DES event, entity and resource trace serialization using the native result
  record contract.
- CLI smoke test for seeded ABM execution and option 10 result inspection.
- JSON round-trip, unknown-field rejection and result-tampering detection.

## Environment limitation

A full test-discovery attempt identified 384 test items, but collection was
interrupted by import errors in 9 DES test modules because this container
lacks the `groq` and `simpy` packages.
Network access was unavailable for installing these declared dependencies.
The DES event-trace serializer was tested against a representative native
trace record, but execution against the real SimPy engine and the complete DES
test group must still be verified in the user's configured Windows
environment.

## Follow-up Windows verification and correction

The project owner's Windows run reported `459 passed, 1 failed, 27 subtests
passed`. The failing test was the DES event-log ordering test added during M9.
Its original expectation incorrectly placed job A's completion before job B's
arrival, even though job B arrives at simulation time 2 and job A completes at
time 6. The DES runtime was unchanged from M8; the test expectation was wrong.

The test now asserts the complete chronological trace:

1. A arrives at 0.
2. A starts service at 0.
3. B arrives at 2.
4. A completes service at 6.
5. B starts service at 6.
6. B completes service at 10.

This is a test-only correction; simulation behavior and M9 execution logic are
unchanged. The corrected test must be rerun in the Windows environment to
confirm the final full-suite result.
