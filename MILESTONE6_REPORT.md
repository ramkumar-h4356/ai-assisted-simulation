# Milestone 6 — AI-Assisted Idea Interpretation, Refinement and Clarification

**Status:** Implemented within the scope below. Automated validation is complete for all test groups available in this build environment; the full DES/Groq-dependent suite requires rerunning with the project's declared dependencies installed.

## Objective

Enable a user to describe an idea in natural language and receive a structured, traceable interpretation that can evolve through clarification. This milestone makes the user's meaning more explicit without replacing novel concepts with familiar real-world theories, inventing missing operational details, or attempting simulation execution.

## Delivered functionality

1. **Structured idea interpreter** — Groq adapter behind an injectable `IdeaInterpreter` protocol. The system prompt requires a complete JSON representation and distinguishes explicit user wording, AI inferences and optional AI suggestions.
2. **Strict deterministic parser** — validates the complete response shape, field types, supported conceptual enums, unique concept names, relationship endpoints, mechanism references, property owners and question references. Invalid or unsafe-to-integrate responses are rejected before they enter M4.
3. **Clarification workflow** — asks bounded questions, records user answers, requests a complete revised interpretation, and leaves unanswered questions open. Both maximum rounds and maximum questions per round are configurable.
4. **M4 integration** — generated concepts, properties, relationships, mechanisms, hypotheses, assumptions, constraints and open questions are converted into typed conceptual elements. Python generates all element IDs and resolves names to IDs.
5. **Element-level provenance** — added `ProvenanceRecord` and `ProvenanceKind` to M4 revisions. Exact user excerpts are verified by deterministic substring matching. An invalid `explicit` attribution is downgraded to `ai_inferred`. AI-structured concepts retain `AI_PROPOSED` origin even when a phrase in their name is grounded in user wording.
6. **M5 knowledge context** — optional local M5 corpus search is supplied to the interpreter as limited source leads. The source title, summary, URI, matched terms and lexical relevance score are retained. The score is never presented as confidence and source hits are not automatically added as evidence or accepted mappings.
7. **Session persistence** — a separate audit record stores the initial request, all clarification question/answer pairs, retrieved source metadata, final summary and remaining uncertainties.
8. **CLI integration** — option 6 guides idea capture, clarification, output review and saving. Project and session files are written to `outputs/` with duplicate-safe names.
9. **Offline tests** — M6 tests use a deterministic stub interpreter and do not require a Groq API key.

## Main files

- `idea_assistant/models.py`
- `idea_assistant/prompts.py`
- `idea_assistant/interpreter.py`
- `idea_assistant/schema.py`
- `idea_assistant/service.py`
- `idea_assistant/session.py`
- `idea_assistant/README.md`
- `tests/idea_assistant/`
- `M6_ARCHITECTURE.md`
- `M6_TEST_REPORT.md`

Existing files updated: `conceptual/model.py`, `conceptual/revision.py`, `conceptual/serialization.py`, `conceptual/validation.py`, `conceptual/__init__.py`, `knowledge/service.py`, `main.py`, `README.md` and `PROJECT_STRUCTURE.txt`.

## Scientific and architectural boundaries

- A well-formed interpretation is not necessarily a correct interpretation; the user must review it.
- A string excerpt that matches the user input proves only that the words occur there, not that they logically support the full AI-generated definition.
- Retrieved source summaries are search leads, not proof. M6 does not automatically create M5 mapping claims.
- User text and earlier project revisions remain immutable.
- Unanswered questions and unresolved uncertainties are not silently filled.
- M6 has no automatic DES/ABM compilation, paradigm selection, model execution, evidence grading or theory verification.

## Verification

The available run reported **256 passed** across `tests/idea_assistant`, `tests/conceptual`, `tests/knowledge`, `tests/core` and `tests/abm`. `compileall` also completed successfully. The complete suite could not be collected in this build workspace because `groq` and `simpy` are not installed and package-index access is unavailable. The full M5 suite had previously passed on the user's Windows setup (`369 passed, 27 subtests passed`); the updated archive should be tested there with `python -m pytest -q` before committing M6.
