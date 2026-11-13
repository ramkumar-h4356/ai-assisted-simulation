# M8 Test Report

## M8-focused tests

Command:

```powershell
python -m pytest tests/compilation -q
```

Result in this environment:

```text
30 passed
```

Coverage includes successful DES/ABM native compilation, M7 gating, stale
revision and project mismatch, unsupported paradigms, source-ID validation,
target-path validation, mandatory concept/mechanism bindings, native DES
validation, ABM semantic validation, unmapped-element warnings, strict profile
serialization, artifact round-trip, model-payload and provenance-binding tamper detection, and template output.

## Combined offline-compatible integration tests

Command:

```powershell
python -m pytest tests/compilation tests/conceptual tests/knowledge tests/idea_assistant tests/readiness tests/abm tests/core -q
```

Result in this environment:

```text
309 passed
```

This run includes the M8 tests plus the conceptual, knowledge, M6 idea
assistant, M7 readiness, ABM and shared-core test groups.

## Additional checks

- `python -m compileall -q .` — passed.
- `python -m compilation.demo` — passed; DES and ABM artifacts generated.
- `python main.py` menu smoke test — option 8 displayed.

## Full-suite environment limitation

A full `python -m pytest -q` collection was attempted. It stopped during
collection because this environment does not have `groq` and `simpy` installed:
DES interpreter tests require `groq`; DES runtime/backend tests require
`simpy`. This is an environment limitation, not a reported test failure in
M8. Run the complete test suite on the configured Windows environment before
committing the milestone.
