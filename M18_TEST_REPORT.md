# M18 Test Report

## Test environment

- Python: 3.13 (build container)
- Test runner: pytest
- Project baseline: `simulator_real_reorganized_M17.zip`

## Results

| Test selection | Result |
|---|---:|
| `python -m pytest -q tests/abm` | **176 passed** |
| `python -m pytest -q --ignore=tests/des` | **451 passed, 1 warning** |
| `python -m pytest -q` | **Collection blocked: 9 DES test modules** |

The non-DES warning is the existing intentional duplicate ZIP member warning in `test_zip_import_rejects_duplicate_normalized_paths`.

The full suite did not run because this build container did not have `groq` and `simpy` installed. These are declared in `requirements.txt`; the DES modules fail during import/collection without them. No DES tests were excluded from the project archive, and the package files were not modified to bypass those dependencies.

## M18 coverage

The M18 tests cover:

- grid row/column mapping, clipped edge cells and invalid cell access;
- deterministic spatial-index radius/bounds queries and insert/move/remove lifecycle;
- polygon region and zone lookup;
- environmental-object proximity queries and blocking collision behavior;
- impassable-zone checks for direct movement and A* detours;
- weighted-zone routing that chooses a longer lower-cost path;
- spatial-neighbour queries after earlier same-step movement;
- wrapped-world neighbourhood lookup across the world boundary;
- strict schema rejection of malformed polygons and duplicate environment IDs;
- the complete M18 park-navigation example.

## Compatibility coverage

All 176 tests under `tests/abm` pass, including the existing M16/M17 spatial, schema, validation, engine and scenario tests. The broader non-DES suite reports 451 passes, including workbench, execution, webapp, replay, uncertainty and experimentation tests.

## Required user-environment verification

After applying the M18 ZIP in the Windows development environment, run:

```powershell
python -m pytest -q tests/abm
python -m pytest -q
```

The second command is the required complete verification when `requirements-dev.txt` has been installed in the active virtual environment.
