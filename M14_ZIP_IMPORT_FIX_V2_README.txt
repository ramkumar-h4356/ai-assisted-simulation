M14.1 ZIP IMPORT FIX — Windows full-path correction

Why the previous fix was insufficient
The previous correction shortened the temporary leaf filename, but the extracted
member still lived below a long staging directory named "workspace-import-...".
Windows path-length limits apply to the complete path, so os.replace() could still
fail when restoring nested M10/M11 artifacts.

What this update changes
- Keeps the existing short temporary member filename (.i-*.tmp).
- Changes the ZIP-import staging directory prefix from "workspace-import-" to
  the compact ".i-". This reduces the full extracted path by about 14 characters.
- Leaves ZIP validation, checksums, workspace naming, and final workspace layout
  unchanged.

Apply
1. Back up or commit your current source code.
2. Extract this ZIP directly into:
   D:\Project Simulator\simulator_real_reorganized
3. Allow workbench\workspace.py to be replaced.
4. Run this targeted test from PowerShell in the project directory:
   python -m pytest -q tests/workbench/test_workspace.py::test_end_to_end_abm_workflow_runs_inside_one_workspace
5. If it passes, run:
   python -m pytest -q tests/workbench/test_workspace.py
6. Then run the full suite:
   python -m pytest -q

This patch does not include, overwrite, or modify the workspaces\ directory.
It is an update to source code only.

Validation performed in the build environment (Linux):
- Targeted end-to-end ABM workflow + ZIP export/import: 1 passed
- Workspace test module: 15 passed, 1 expected duplicate-entry warning
- Python compile check: passed

The Linux environment does not reproduce Windows MAX_PATH behavior. The targeted
Windows test result is still needed to confirm the issue is resolved on your PC.
