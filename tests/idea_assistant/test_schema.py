import pytest

from idea_assistant.schema import IdeaInterpretationError, parse_idea_draft
from tests.idea_assistant.helpers import draft_copy


def test_parse_normalizes_all_declared_groups():
    draft = parse_idea_draft(draft_copy())
    assert draft.title == "Community resource sharing idea"
    assert len(draft.concepts) == 2
    assert draft.properties[0]["data_type"] == "number"
    assert draft.clarification_questions[0].priority == "high"


def test_parser_rejects_relationship_to_unknown_concept():
    raw = draft_copy()
    raw["relationships"][0]["target_concept"] = "Unknown"
    with pytest.raises(IdeaInterpretationError, match="was not declared"):
        parse_idea_draft(raw)


def test_parser_rejects_unexpected_fields():
    raw = draft_copy()
    raw["code"] = "print('unsafe')"
    with pytest.raises(IdeaInterpretationError, match="unsupported field"):
        parse_idea_draft(raw)


def test_parser_rejects_duplicate_concept_names_case_insensitively():
    raw = draft_copy()
    raw["concepts"].append(dict(raw["concepts"][0], name="COMMUNITY MEMBER"))
    with pytest.raises(IdeaInterpretationError, match="Duplicate concept"):
        parse_idea_draft(raw)


def test_parser_rejects_invalid_enums_and_question_references():
    raw = draft_copy()
    raw["concepts"][0]["kind"] = "spaceship"
    with pytest.raises(IdeaInterpretationError, match="must be one of"):
        parse_idea_draft(raw)
    raw = draft_copy()
    raw["clarification_questions"][0]["related_concepts"] = ["unknown"]
    with pytest.raises(IdeaInterpretationError, match="undeclared concept"):
        parse_idea_draft(raw)


def test_defined_concept_or_property_without_definition_is_downgraded():
    raw = draft_copy()
    raw["concepts"][0]["status"] = "defined"
    raw["concepts"][0]["definition"] = ""
    raw["properties"][0]["status"] = "defined"
    raw["properties"][0]["definition"] = ""
    draft = parse_idea_draft(raw)
    assert draft.concepts[0]["status"] == "proposed"
    assert draft.properties[0]["status"] == "proposed"
