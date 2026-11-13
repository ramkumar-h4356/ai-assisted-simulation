import json
from dataclasses import FrozenInstanceError

import pytest

from knowledge import (
    KnowledgeBase, KnowledgeBaseError, KnowledgeDocument, SourceKind,
    dumps_knowledge_base, knowledge_base_from_dict, load_knowledge_base,
    loads_knowledge_base, merge_knowledge_bases, save_knowledge_base,
)
from tests.knowledge.helpers import sample_base, tiny_base


def test_sample_knowledge_base_loads_four_curated_documents():
    base = sample_base()
    assert len(base.documents) == 4
    assert {item.reference.published_year for item in base.documents} == {1968, 1973, 1984, 1990}
    assert all(item.source_kind is SourceKind.CURATED for item in base.documents)


def test_knowledge_base_round_trip_is_lossless():
    base = sample_base()
    restored = loads_knowledge_base(dumps_knowledge_base(base))
    assert restored == base


def test_knowledge_base_file_save_and_load(tmp_path):
    path = save_knowledge_base(sample_base(), tmp_path / "nested" / "corpus.json")
    assert path.exists()
    assert load_knowledge_base(path) == sample_base()


def test_add_returns_new_base_without_mutating_original():
    base = tiny_base()
    document = sample_base().documents[0]
    updated = base.add(document)
    assert len(base.documents) == 2
    assert len(updated.documents) == 3
    assert updated.get(document.id) == document


def test_duplicate_document_id_is_rejected():
    base = tiny_base()
    with pytest.raises(ValueError, match="already exists"):
        base.add(base.documents[0])


def test_remove_returns_new_base_and_requires_existing_document():
    base = tiny_base()
    updated = base.remove("queue-doc")
    assert len(updated.documents) == 1
    assert len(base.documents) == 2
    with pytest.raises(KeyError):
        base.remove("missing")


def test_duplicate_ids_in_constructor_are_rejected():
    base = tiny_base()
    with pytest.raises(ValueError, match="unique"):
        KnowledgeBase("bad", "Bad", (base.documents[0], base.documents[0]))


def test_document_and_base_are_immutable():
    document = tiny_base().documents[0]
    with pytest.raises(FrozenInstanceError):
        document.title = "changed"
    with pytest.raises(FrozenInstanceError):
        tiny_base().name = "changed"


def test_merge_deduplicates_identical_documents():
    base = tiny_base()
    merged = merge_knowledge_bases(base, base, base_id="merged", name="Merged")
    assert len(merged.documents) == 2


def test_merge_rejects_conflicting_same_id_documents():
    base = tiny_base()
    altered = KnowledgeDocument(
        id="cooperation-doc", title="Different title", content="Different content",
        reference=base.documents[0].reference,
    )
    other = KnowledgeBase("other", "Other", (altered,))
    with pytest.raises(KnowledgeBaseError, match="Conflicting document ID"):
        merge_knowledge_bases(base, other, base_id="merged", name="Merged")


def test_unknown_json_fields_are_rejected():
    raw = json.loads(dumps_knowledge_base(sample_base()))
    raw["unexpected"] = True
    with pytest.raises(KnowledgeBaseError, match="Unsupported"):
        knowledge_base_from_dict(raw)


def test_invalid_reference_type_is_reported():
    raw = json.loads(dumps_knowledge_base(sample_base()))
    raw["documents"][0]["reference"]["reference_type"] = "unknown-type"
    with pytest.raises(KnowledgeBaseError, match="invalid"):
        knowledge_base_from_dict(raw)


def test_invalid_json_is_reported():
    with pytest.raises(KnowledgeBaseError, match="Invalid knowledge-base JSON"):
        loads_knowledge_base("{not json")
