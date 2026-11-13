# M5 Architecture — Knowledge Retrieval and Real-World Mapping

## 1. Architectural objective

M5 supplies the first knowledge-grounded bridge between an abstract concept in the M4 conceptual model and a documented real-world mechanism or phenomenon. It does not formalize the user's entire theory and does not decide whether an analogy is correct.

The layer has four responsibilities:

1. Keep searchable source material in a normalized, persistent knowledge base.
2. Retrieve relevant source records and explain which terms caused the match.
3. Propose possible concept-to-source correspondences without approving them.
4. Attach a selected proposal and its source reference to a new, append-only conceptual revision after explicit user action.

## 2. Dependency direction

```text
User / CLI
   |
   v
KnowledgeMappingService
   |                 \
   v                  v
KnowledgeRetriever   MappingCandidate builder
   |                  |
   v                  v
KnowledgeBase       Candidate + rationale
   |                  |
   +------------------+
                      |
                      v
          M4 conceptual.revision API
                      |
                      v
       New IdeaProject revision containing
       EvidenceReference + MappingClaim
```

`knowledge/` may depend on the M4 conceptual data contracts. The conceptual package does not import `knowledge/`. DES and ABM do not import either layer. This direction prevents knowledge retrieval from becoming entangled with simulation execution.

## 3. Canonical data contracts

### KnowledgeDocument

A document contains a stable local ID, title, searchable content, a canonical `EvidenceReference`, domain tags, keywords, target concept labels, authors, source kind, language and notes. `content` is a short original summary or user-supplied searchable text, not a copy of restricted full text.

### KnowledgeBase

An immutable named collection of documents. `add` and `remove` return new instances. IDs must be unique. Merging corpora rejects conflicting IDs rather than silently selecting one source.

### SearchHit

A document, lexical relevance score and the matched query terms. The score is only a ranking value; it is never called confidence or probability.

### MappingCandidate

A candidate links one M4 concept ID to one knowledge document and an indexed target label. It contains a rationale, matched terms and retrieval score. It is not an M4 `MappingClaim` until a user chooses to record it.

## 4. Retrieval implementation

The shipped search implementation is dependency-free, deterministic BM25-style lexical retrieval:

- Content tokens use the base field weight.
- Title and concept-label tokens receive stronger weights.
- Keywords receive a medium boost; domains and authors receive smaller boosts.
- Inverse document frequency reduces the impact of terms appearing in many records.
- Optional domain, reference-type and source-kind filters constrain the corpus.
- Mapping suggestions apply a minimum matched-term gate (two terms by default) to suppress weak one-word matches.

This design is deliberately inspectable and reproducible. It is not semantic search. It does not stem words, understand synonyms, support multilingual morphology or judge source quality. A future provider can implement `KnowledgeSearchProvider` and return `SearchHit` values for the same normalized documents.

## 5. Mapping and review lifecycle

```text
Concept selected
      |
      v
Lexical retrieval + filters
      |
      v
Ranked source documents
      |
      v
Candidate label + matched-term explanation
      |
      v
Human selects a candidate
      |
      v
record_candidate(..., UNREVIEWED)
      |
      v
New M4 revision stores MappingClaim + EvidenceReference
      |
      +---- leave unreviewed
      |
      +---- review_mapping(..., ACCEPTED)
      |
      +---- review_mapping(..., REJECTED)
                    |
                    v
          Another immutable revision
```

The default candidate type is `analogous`; lexical similarity cannot establish equivalence or evidence support. The original `IdeaProject.original_statement` and earlier `IdeaRevision` snapshots are not mutated. Evidence references are reused by URI where possible to avoid needless duplicate source records.

## 6. Source corpus and ingestion boundary

M5 ships a small JSON corpus containing four source summaries and bibliographic links. The corpus is illustrative and domain-bounded, not an exhaustive search index. Users can create `KnowledgeDocument` records and add them to a base, or import an existing JSON corpus using `load_knowledge_base`. The JSON schema is included beside the sample corpus.

External web and scholarly APIs are not invoked at runtime in M5. Future connectors should:

1. Retrieve metadata and permitted abstracts/summaries from a source provider.
2. Normalize results into `KnowledgeDocument` and `EvidenceReference`.
3. Preserve the canonical URI, author, publisher, publication year, retrieval time and access/rights notes where available.
4. Add the normalized documents to the user's knowledge base before mapping.
5. Keep retrieval, source credibility assessment and conceptual review as separate operations.

The `KnowledgeSearchProvider` protocol allows another retrieval/index strategy to replace the current lexical one while preserving mapping and review code. A semantic/vector provider remains a future implementation, not a claimed M5 capability.

## 7. Scientific and epistemic safeguards

- A retrieval hit is not a verified fact.
- An analogy is not equivalence.
- A source's argument is not automatically applicable to a user's new theory.
- An accepted mapping records a user's scoped review decision; it does not prove the theory.
- Mapping candidates include their source and matched terms so a reviewer can inspect why they appeared.
- Contradictory perspectives can be retrieved; the sample corpus deliberately includes different treatments of shared-resource problems.
- A weak or absent lexical match can yield no candidate. The engine does not invent a replacement.

## 8. Explicit non-goals for M5

- Live web crawling or direct scholarly-index API access.
- Vector embeddings, LLM semantic retrieval, reranking or automated source-quality scoring.
- Automated literature review or automatic evidence grading.
- Automatic acceptance of analogy/equivalence claims.
- Generating executable DES/ABM rules or selecting a simulation paradigm.
- Proving or falsifying a new theory.

These boundaries keep M5 testable and allow each future capability to be evaluated independently.

## 9. Completion criteria

M5 is complete when a user can import or extend a local source corpus, search it using transparent ranking, inspect mapping candidates with matched-term explanations, record an unreviewed claim with source provenance, explicitly accept or reject that claim, and persist the resulting project without losing the original idea or prior revisions. Tests cover these behaviours and the sample CLI path demonstrates them end to end.
