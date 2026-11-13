# Knowledge Retrieval and Real-World Mapping — M5

## Purpose

The `knowledge/` package searches a curated or user-imported local knowledge corpus and proposes traceable correspondences between a conceptual-model concept and mechanisms or phenomena discussed by a source. It integrates with the M4 `IdeaProject` without coupling the conceptual model to DES, ABM, SimPy or Groq.

A retrieved result is a **candidate for human review**, not a finding that two ideas are equivalent and not proof that a theory is true.

## Delivered components

| Module | Responsibility |
|---|---|
| `models.py` | Immutable `KnowledgeDocument`, `KnowledgeBase`, `SearchHit` and `MappingCandidate` data contracts |
| `repository.py` | Strict JSON load/save, immutable add/remove and corpus merge with ID-conflict detection |
| `tokenizer.py` | Dependency-free English-oriented tokenization and stop-word filtering |
| `retrieval.py` | Deterministic BM25-style search, weighted metadata fields and domain/source filters |
| `providers.py` | `KnowledgeSearchProvider` protocol for replacing the retrieval strategy later |
| `mapping.py` | Concept-to-source mapping candidates with matched-term explanations |
| `service.py` | Search, candidate recording and explicit accept/reject review as new M4 revisions |
| `demo.py` | Interactive workflow and non-interactive example |
| `sample_knowledge_base.json` | Four short, curated source summaries with bibliographic metadata and persistent URIs |

## Quick start

```python
from conceptual import load_idea_project, save_idea_project
from conceptual.model import ReviewStatus
from knowledge import KnowledgeMappingService, load_knowledge_base

project = load_idea_project("scenarios/conceptual/decentralized_resource_cooperation.json")
base = load_knowledge_base("knowledge/sample_knowledge_base.json")
service = KnowledgeMappingService(base)

# Search a concept against the local corpus.
candidates = service.suggest_for_concept(
    project,
    "shared-resource",
    limit=5,
)
for candidate in candidates:
    print(candidate.target_label, candidate.relevance_score, candidate.matched_terms)

# Record a selected candidate as unreviewed by default.
updated = service.record_candidate(project, candidates[0])

# Only after a person reviews it, explicitly accept or reject it.
mapping_id = f"mapping-{candidates[0].id}"
reviewed = service.review_mapping(
    updated,
    mapping_id,
    ReviewStatus.ACCEPTED,
    reviewer_note="Reviewed against the cited source and scope.",
)
save_idea_project(reviewed, "outputs/my_idea_with_mapping.json")
```

Run the guided workflow using `python -m knowledge.demo`, or choose option `5` in `python main.py`. It loads the included example idea and corpus, asks which concept to investigate, shows ranked source candidates and their matched terms, and allows the user to leave a candidate unreviewed, accept it or reject it. It writes a new file in `outputs/`; it does not overwrite the sample idea.

## Corpus format and importing sources

A knowledge base is ordinary JSON. The reference metadata uses the same `EvidenceReference` structure as the conceptual model. A document contains:

- A stable document ID, title and searchable original/paraphrased content.
- A bibliographic reference with type, URI, publisher and year.
- Domain tags, keywords and concept labels for retrieval and mapping.
- Authors, source origin (`curated`, `user_provided`, `imported`), language and notes.

The canonical format is demonstrated in `sample_knowledge_base.json`; `knowledge_base.schema.json` documents the accepted JSON shape. Users can load a corpus, create `KnowledgeDocument` instances, call `KnowledgeBase.add`, and save the resulting base. `merge_knowledge_bases` combines corpora but rejects conflicting IDs instead of silently overwriting a source.

The included seed corpus is intentionally small and demonstrates four different perspectives: commons governance (Ostrom), cooperation through repeated interactions (Axelrod), social-network weak ties and information diffusion (Granovetter), and the shared-resource dilemma (Hardin). Each record contains a short original paraphrase and a source URI; the full source should be consulted before asserting a substantive claim.

## Retrieval method and score meaning

Search uses a BM25-style lexical ranking. Query terms are matched against document content and metadata. Title and concept-label terms receive higher field weights than keywords, domains and body content. Optional filters restrict the search by domain, bibliographic reference type or source origin.

`SearchHit.score` and `MappingCandidate.relevance_score` are **ranking scores**, not probabilities, confidence values, source-quality ratings, or truth estimates. The engine does not currently provide embedding-based semantic search, stemming, multilingual retrieval, automatic source credibility grading, or live web/academic-index fetching. An empty result is preferable to inventing a connection.

The default tokenizer is English-oriented. Search terms are lowercased and common stop words are removed. Mapping suggestions require at least two matched query terms by default (`min_matched_terms=2`) to reduce weak one-word matches; this can be lowered for short, deliberate searches. A domain-specific corpus should use consistent terms in its `keywords` and `concept_labels` to improve retrieval quality.

## Mapping semantics and review

For a concept, the mapping engine retrieves relevant documents and chooses the indexed concept label with the strongest lexical overlap. It emits a `MappingCandidate` with:

- The source concept and knowledge-document IDs.
- The selected target label and source summary.
- The retrieval score and matched query terms.
- A rationale that explicitly says the result is only an analogy/comparison lead.

`record_candidate` adds an M4 `MappingClaim` and corresponding `EvidenceReference` in a new append-only idea revision. The default review state is `unreviewed`; the default mapping type is `analogous`. `review_mapping` creates another revision with an explicit `accepted` or `rejected` status and optional reviewer note. The original statement and earlier model snapshots remain unchanged. Reusing the same source URI reuses an existing evidence reference where possible.

An accepted mapping means the user accepted the proposed correspondence for the stated project scope. It does **not** mean the source proves the user's theory. Evidence claims, contradictions and equivalences require careful human interpretation and supporting references.

## Extension boundaries

The `KnowledgeSearchProvider` protocol separates the search strategy from the conceptual model and mapping-review API. The delivered implementation is local BM25-style retrieval over a `KnowledgeBase`. A future embedding/vector search provider can implement the same protocol and return `SearchHit` objects backed by documents already ingested into that base.

External source connectors (Crossref, scholarly indexes, web search, institutional repositories and connected personal libraries) are not activated in M5. Their ingestion layer should normalize results into `KnowledgeDocument` plus `EvidenceReference`, retain source metadata and access timestamps, and avoid copying restricted full text. This keeps source acquisition separate from conceptual mapping.

## Tests

```bash
python -m pytest -q tests/knowledge tests/conceptual tests/core tests/abm
```

M5 tests cover JSON validation and persistence, corpus merges, BM25 ranking and filters, candidate explanations, immutable project revisions, evidence-reference integration, review decisions, duplicate detection and the end-to-end sample corpus.
