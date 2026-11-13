from conceptual import (
    Concept, ConceptKind, ConceptOrigin, DefinitionStatus, IdeaProject,
    IdeaRevision, create_idea_project, revise_idea_project,
)


def make_project():
    project = create_idea_project(
        "Example theory",
        "The original user statement must never be overwritten.",
        project_id="idea-1",
        revision_id="revision-1",
        created_at="2026-11-13T01:00:00+00:00",
    )
    return revise_idea_project(
        project,
        change_summary="Add the initial concept.",
        revision_id="revision-2",
        created_at="2026-11-13T01:05:00+00:00",
        concepts=(
            Concept(
                "participant", "Participant", ConceptKind.ACTOR,
                ConceptOrigin.USER_DEFINED, "A participant in the theory.",
                DefinitionStatus.DEFINED,
            ),
        ),
    )
