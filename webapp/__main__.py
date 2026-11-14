"""Run the local Simulation Workbench web application."""

from __future__ import annotations

import argparse
import os

import uvicorn


def main() -> None:
    parser = argparse.ArgumentParser(description="Run the local Simulation Workbench browser UI")
    parser.add_argument("--host", default=os.getenv("SIMULATOR_WEB_HOST", "127.0.0.1"))
    parser.add_argument("--port", type=int, default=int(os.getenv("SIMULATOR_WEB_PORT", "8765")))
    parser.add_argument("--workspace-root", default=os.getenv("SIMULATOR_WORKSPACE_ROOT", "workspaces"))
    args = parser.parse_args()
    os.environ["SIMULATOR_WORKSPACE_ROOT"] = args.workspace_root
    if args.host not in {"127.0.0.1", "localhost", "::1"}:
        parser.error("The M14 web application is local-only; bind to 127.0.0.1, localhost or ::1")
    uvicorn.run("webapp.app:app", host=args.host, port=args.port, reload=False, factory=False, log_level="info", env_file=None, )


if __name__ == "__main__":
    main()
