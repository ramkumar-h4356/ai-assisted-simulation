"""Local browser application for the AI-Assisted Simulation Workbench (M14–M16)."""


def create_app(*args, **kwargs):
    """Lazily create the FastAPI application without importing the server on package import."""
    from webapp.app import create_app as factory

    return factory(*args, **kwargs)


__all__ = ["create_app"]
