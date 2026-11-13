"""Factories for creating projects and append-only conceptual revisions."""

from __future__ import annotations

from datetime import datetime, timezone
from uuid import uuid4

from conceptual.model import IdeaProject, IdeaRevision


def _timestamp(value: str | None) -> str:
    return value or datetime.now(timezone.utc).isoformat()


def create_idea_project(
    title: str,
    original_statement: str,
    *,
    project_id: str | None = None,
    revision_id: str | None = None,
    created_at: str | None = None,
) -> IdeaProject:
    """Create a project with an empty first revision and immutable source text."""
    revision = IdeaRevision(
        id=revision_id or f"rev-{uuid4().hex[:12]}",
        version=1,
        created_at=_timestamp(created_at),
        change_summary="Initial capture of the original idea.",
        working_statement=original_statement,
    )
    return IdeaProject(
        id=project_id or f"idea-{uuid4().hex[:12]}",
        title=title,
        original_statement=original_statement,
        current_revision_id=revision.id,
        revisions=(revision,),
    )


def append_revision(
    project: IdeaProject,
    revision: IdeaRevision,
) -> IdeaProject:
    """Append a full snapshot; existing revisions and original text are retained."""
    if not isinstance(project, IdeaProject):
        raise TypeError("project must be an IdeaProject")
    if not isinstance(revision, IdeaRevision):
        raise TypeError("revision must be an IdeaRevision")
    current = project.current_revision
    if revision.version != current.version + 1:
        raise ValueError("A new revision must increment the current version by one")
    if revision.parent_revision_id != current.id:
        raise ValueError("A new revision must reference the current revision as its parent")
    if any(item.id == revision.id for item in project.revisions):
        raise ValueError(f"Revision ID {revision.id!r} already exists")
    return IdeaProject(
        id=project.id,
        title=project.title,
        original_statement=project.original_statement,
        current_revision_id=revision.id,
        revisions=project.revisions + (revision,),
    )


def revise_idea_project(
    project: IdeaProject,
    *,
    change_summary: str,
    working_statement: str | None = None,
    revision_id: str | None = None,
    created_at: str | None = None,
    **component_overrides,
) -> IdeaProject:
    """Create the next snapshot, replacing only the supplied component groups.

    Omitted component groups are copied from the current revision. Pass an empty
    tuple explicitly to clear a group.
    """
    allowed = {
        "concepts", "properties", "relationships", "mechanisms", "hypotheses",
        "assumptions", "constraints", "evidence_references", "mappings",
        "open_questions",
    }
    if not isinstance(project, IdeaProject):
        raise TypeError("project must be an IdeaProject")
    unknown = set(component_overrides) - allowed
    if unknown:
        raise TypeError(f"Unknown revision component(s): {', '.join(sorted(unknown))}")
    current = project.current_revision
    values = {name: component_overrides.get(name, getattr(current, name)) for name in allowed}
    revision = IdeaRevision(
        id=revision_id or f"rev-{uuid4().hex[:12]}",
        version=current.version + 1,
        created_at=_timestamp(created_at),
        change_summary=change_summary,
        working_statement=(current.working_statement if working_statement is None else working_statement),
        parent_revision_id=current.id,
        **values,
    )
    return append_revision(project, revision)
