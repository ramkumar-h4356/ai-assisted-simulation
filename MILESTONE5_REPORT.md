# Milestone 5 — Knowledge Retrieval and Real-World Mapping Engine

**Status:** Implemented and locally verified within the defined M5 scope.

## Objective

Connect the M4 conceptual model to a traceable body of existing knowledge. The engine must retrieve potentially relevant real-world sources, explain why they were found, and let the user decide whether a proposed correspondence belongs in the theory.

## Delivered functionality

1. **Knowledge corpus model** — immutable `KnowledgeDocument` and `KnowledgeBase` records, with bibliographic metadata, source origin, domains, keywords, concept labels and searchable content.
2. **Persistence and ingestion** — strict JSON load/save, a JSON Schema, immutable add/remove operations and merge conflict detection.
3. **Retrieval** — dependency-free BM25-style lexical ranking with title/label/keyword field boosts and filters for domain, reference type and source origin.
4. **Mapping suggestions** — candidate concept-to-source correspondences with matched terms, target labels, rationale and a retrieval relevance score. Two matched terms are required by default to reduce weak matches.
5. **Review and provenance** — recording a candidate adds an M4 `MappingClaim` and `EvidenceReference` in a new revision. The default status is `unreviewed`; user decisions are recorded as additional `accepted` or `rejected` revisions.
6. **Extensible retrieval interface** — `KnowledgeSearchProvider` allows a future lexical, semantic or vector search implementation to be swapped without changing conceptual schemas or review semantics.
7. **User workflow** — option 5 in `main.py` and `python -m knowledge.demo` provide a guided workflow; user output is written under `outputs/`, not over the sample theory.
8. **Sample corpus** — four concise source summaries with persistent bibliographic URIs: Ostrom (1990), Axelrod (1984), Granovetter (1973) and Hardin (1968).

## Example behaviour

For the sample theory's `shared-resource` concept, the engine retrieves:

- Ostrom's *Governing the Commons* as a candidate related to common-pool resource governance.
- Hardin's *The Tragedy of the Commons* as a candidate related to open-access shared-resource dilemmas.

The two perspectives are not collapsed into one conclusion. Each candidate carries matched terms and a source URI. A candidate remains unreviewed until a person explicitly records a decision.

## Files added

- `knowledge/models.py`
- `knowledge/repository.py`
- `knowledge/tokenizer.py`
- `knowledge/retrieval.py`
- `knowledge/providers.py`
- `knowledge/mapping.py`
- `knowledge/service.py`
- `knowledge/demo.py`
- `knowledge/sample_knowledge_base.json`
- `knowledge/knowledge_base.schema.json`
- `knowledge/README.md`
- `tests/knowledge/test_models_repository.py`
- `tests/knowledge/test_retrieval.py`
- `tests/knowledge/test_mapping_service.py`
- `M5_ARCHITECTURE.md`
- `M5_TEST_REPORT.md`

`main.py`, `README.md` and `PROJECT_STRUCTURE.txt` were updated to expose and document the milestone.

## Scope limitations

M5 searches a small local/imported corpus using lexical retrieval. It does not fetch live web content or academic-index records, perform embedding-based semantic search, grade the credibility of sources, automatically decide that a mapping is true, or translate conceptual models into simulation rules. These are deliberate boundaries, not silently assumed capabilities. External retrieval providers can be introduced behind the normalized document and search-provider contracts in a later milestone.

## Verification

The M5 test report records the exact automated test commands and environment limitations. The M4 conceptual, core and ABM tests were also rerun alongside the new knowledge tests. The complete DES/Groq-dependent suite must be rerun in the user's Windows environment with the project's declared dependencies installed; this build workspace does not have `simpy` or `groq` installed.
