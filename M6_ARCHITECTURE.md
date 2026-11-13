# M6 Architecture — AI-assisted idea interpretation and clarification

## 1. Objective

M6 adds a structured interpretation and clarification service above the M4 conceptual model and alongside the M5 knowledge layer. Its output is a human-reviewable conceptual draft, not a validated scientific theory or an executable simulation model.

## 2. Dependency direction

```text
User / CLI
   |
   v
IdeaAssistantService
   |                    \
   v                     v
IdeaInterpreter       M5 KnowledgeRetriever (optional)
   |                     |
   v                     v
Strict JSON parser    local source leads
   |
   v
M4 conceptual draft + provenance + open questions
   |
   +--> immutable IdeaProject revision
   +--> clarification session audit JSON
```

The conceptual model remains independent of Groq, M5 and simulation backends. The interpreter is injected through a small protocol so the implementation can be tested offline or replaced with another provider.

## 3. Processing stages

### Stage A — Initial capture

`IdeaAssistantService.build()` validates the initial user statement, keeps the exact string, optionally searches a supplied local `KnowledgeBase`, and calls the interpreter. The existing M5 BM25-style lexical retriever is used without changing its semantics.

### Stage B — Structured interpretation

The LLM is constrained to return JSON only. `parse_idea_draft()` performs deterministic validation of top-level keys, nested fields, enums, primitive types, duplicate concept names, and concept references. Properties, relationships, mechanisms and clarification references must point to concepts declared in the same draft.

### Stage C — Clarification loop

At most the configured number of rounds and questions per round are sent to the caller. The caller returns a mapping from generated question IDs to answers. Blank answers leave questions unresolved. Every nonblank answer is preserved in an `IdeaAssistantSession` exchange record. When a user answers only part of a round, the service deterministically carries unanswered and unasked questions forward even if the model omits them from its revised draft. Refinement requests include the original text, full previous interpretation, answer history and the same bounded retrieval context.

### Stage D — M4 integration

`apply_idea_draft()` builds typed M4 concepts, properties, relationships, mechanisms, hypotheses, assumptions, constraints and open questions. Python generates all stable IDs and resolves concept references. It creates an initial M4 revision and then appends the interpreted draft as a second revision; the original text is not modified.

### Stage E — Provenance

M4 now supports `ProvenanceRecord` and `ProvenanceKind` on each revision. For an element marked explicit, Python checks whether the provided excerpt is an exact substring of the initial user statement or one of the clarification answers. A failed match is downgraded to `ai_inferred`. The concept origin remains `AI_PROPOSED` because the formal element definition is AI-structured, while its provenance record can still identify a verbatim user phrase.

### Stage F — Persistence

The project uses the existing strict M4 JSON serializer. The session audit is saved separately and contains the initial request, clarification exchanges, retrieved-context metadata, final summary and uncertainties. Both files are saved by CLI option 6.

## 4. Knowledge context boundary

M5 results are supplied with source ID, bibliographic title, short indexed summary, URI, matched terms and an explicitly named lexical relevance score. The prompt warns the interpreter that these are leads, not proof. M6 does not create an `EvidenceReference` or `MappingClaim` from a retrieval hit and does not accept or reject a mapping on the user's behalf. Users continue to use the explicit M5 review workflow for that.

## 5. Deterministic versus probabilistic responsibilities

| Responsibility | Owner |
|---|---|
| Interpret natural language and suggest questions | LLM interpreter |
| Return structured draft | LLM under schema prompt |
| Check JSON fields, enum values and cross references | Python parser |
| Generate IDs and map concept names to IDs | Python |
| Verify an explicit excerpt exists verbatim in supplied user text | Python |
| Preserve revisions and provenance records | M4 data model |
| Execute DES/ABM | Not part of M6 |

## 6. Limitations and non-goals

- The model can still misunderstand context; deterministic schema validity does not imply semantic correctness.
- Exact excerpt matching verifies string presence, not whether the excerpt logically supports the AI interpretation.
- Retrieval remains lexical, local, and limited to the supplied corpus.
- No automatic source quality grading, semantic retrieval, citation verification, model selection, simulator compilation or execution is added.
- The user must inspect and revise AI-proposed elements before relying on them.

## 7. Completion criteria

M6 is complete when a user can describe an idea, receive a traceable structured draft, answer targeted clarification questions, retain unresolved uncertainties, optionally provide M5 source context, save the resulting M4 project and session audit, and run offline automated tests with a stub interpreter.
