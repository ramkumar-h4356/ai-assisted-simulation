"""JSON persistence and immutable operations for knowledge bases."""

from __future__ import annotations

import json
from dataclasses import fields
from pathlib import Path
from typing import Any

from conceptual.model import EvidenceReference, ReferenceType
from knowledge.models import KnowledgeBase, KnowledgeDocument, SourceKind


class KnowledgeBaseError(ValueError):
    """Raised for malformed or unsupported knowledge-base data."""


def knowledge_base_to_dict(base: KnowledgeBase) -> dict[str, Any]:
    if not isinstance(base, KnowledgeBase):
        raise TypeError("base must be a KnowledgeBase")
    return {
        "id": base.id,
        "name": base.name,
        "description": base.description,
        "documents": [
            {
                "id": item.id,
                "title": item.title,
                "content": item.content,
                "reference": {
                    "id": item.reference.id,
                    "title": item.reference.title,
                    "reference_type": item.reference.reference_type.value,
                    "uri": item.reference.uri,
                    "publisher": item.reference.publisher,
                    "published_year": item.reference.published_year,
                    "notes": item.reference.notes,
                },
                "domains": list(item.domains),
                "keywords": list(item.keywords),
                "concept_labels": list(item.concept_labels),
                "authors": list(item.authors),
                "source_kind": item.source_kind.value,
                "language": item.language,
                "notes": item.notes,
            }
            for item in base.documents
        ],
    }


def knowledge_base_from_dict(data: Any) -> KnowledgeBase:
    if not isinstance(data, dict):
        raise KnowledgeBaseError("knowledge_base must be a JSON object")
    allowed = {"id", "name", "description", "documents"}
    unknown = set(data) - allowed
    missing = {"id", "name", "documents"} - set(data)
    if unknown:
        raise KnowledgeBaseError(f"Unsupported knowledge-base fields: {', '.join(sorted(unknown))}")
    if missing:
        raise KnowledgeBaseError(f"Missing knowledge-base fields: {', '.join(sorted(missing))}")
    if not isinstance(data["documents"], list):
        raise KnowledgeBaseError("documents must be a JSON array")
    documents = []
    document_fields = {
        "id", "title", "content", "reference", "domains", "keywords",
        "concept_labels", "authors", "source_kind", "language", "notes",
    }
    reference_fields = {item.name for item in fields(EvidenceReference)}
    for index, raw in enumerate(data["documents"]):
        path = f"documents[{index}]"
        if not isinstance(raw, dict):
            raise KnowledgeBaseError(f"{path} must be a JSON object")
        unknown_doc = set(raw) - document_fields
        missing_doc = {"id", "title", "content", "reference"} - set(raw)
        if unknown_doc:
            raise KnowledgeBaseError(f"{path} has unsupported fields: {', '.join(sorted(unknown_doc))}")
        if missing_doc:
            raise KnowledgeBaseError(f"{path} is missing fields: {', '.join(sorted(missing_doc))}")
        ref = raw["reference"]
        if not isinstance(ref, dict):
            raise KnowledgeBaseError(f"{path}.reference must be a JSON object")
        unknown_ref = set(ref) - reference_fields
        missing_ref = {"id", "title"} - set(ref)
        if unknown_ref or missing_ref:
            detail = []
            if unknown_ref:
                detail.append("unsupported: " + ", ".join(sorted(unknown_ref)))
            if missing_ref:
                detail.append("missing: " + ", ".join(sorted(missing_ref)))
            raise KnowledgeBaseError(f"{path}.reference " + "; ".join(detail))
        try:
            reference = EvidenceReference(
                id=ref["id"], title=ref["title"],
                reference_type=ReferenceType(ref.get("reference_type", ReferenceType.OTHER.value)),
                uri=ref.get("uri"), publisher=ref.get("publisher", ""),
                published_year=ref.get("published_year"), notes=ref.get("notes", ""),
            )
            document = KnowledgeDocument(
                id=raw["id"], title=raw["title"], content=raw["content"],
                reference=reference,
                domains=raw.get("domains", ()), keywords=raw.get("keywords", ()),
                concept_labels=raw.get("concept_labels", ()), authors=raw.get("authors", ()),
                source_kind=SourceKind(raw.get("source_kind", SourceKind.IMPORTED.value)),
                language=raw.get("language", "en"), notes=raw.get("notes", ""),
            )
        except (TypeError, ValueError) as error:
            raise KnowledgeBaseError(f"{path} is invalid: {error}") from error
        documents.append(document)
    try:
        return KnowledgeBase(
            id=data["id"], name=data["name"], documents=tuple(documents),
            description=data.get("description", ""),
        )
    except (TypeError, ValueError) as error:
        raise KnowledgeBaseError(f"Knowledge base is invalid: {error}") from error


def dumps_knowledge_base(base: KnowledgeBase, *, indent: int = 2) -> str:
    return json.dumps(knowledge_base_to_dict(base), ensure_ascii=False, indent=indent, allow_nan=False)


def loads_knowledge_base(content: str) -> KnowledgeBase:
    try:
        raw = json.loads(content)
    except (TypeError, json.JSONDecodeError) as error:
        raise KnowledgeBaseError(f"Invalid knowledge-base JSON: {error}") from error
    return knowledge_base_from_dict(raw)


def save_knowledge_base(base: KnowledgeBase, path: str | Path) -> Path:
    destination = Path(path)
    destination.parent.mkdir(parents=True, exist_ok=True)
    destination.write_text(dumps_knowledge_base(base), encoding="utf-8")
    return destination


def load_knowledge_base(path: str | Path) -> KnowledgeBase:
    source = Path(path)
    try:
        return loads_knowledge_base(source.read_text(encoding="utf-8"))
    except OSError as error:
        raise OSError(f"Could not read knowledge base at {source}: {error}") from error


def merge_knowledge_bases(*bases: KnowledgeBase, base_id: str, name: str, description: str = "") -> KnowledgeBase:
    """Merge corpora, rejecting conflicting document IDs rather than overwriting."""
    documents: dict[str, KnowledgeDocument] = {}
    for base in bases:
        if not isinstance(base, KnowledgeBase):
            raise TypeError("all inputs must be KnowledgeBase instances")
        for document in base.documents:
            previous = documents.get(document.id)
            if previous is not None and previous != document:
                raise KnowledgeBaseError(f"Conflicting document ID {document.id!r} while merging knowledge bases")
            documents[document.id] = document
    return KnowledgeBase(base_id, name, tuple(documents.values()), description)
