"""Small dependency-free English-oriented tokenizer for lexical retrieval."""

from __future__ import annotations

import re

_TOKEN_PATTERN = re.compile(r"[a-z0-9]+", re.IGNORECASE)
STOP_WORDS = frozenset({
    "a", "an", "and", "are", "as", "at", "be", "been", "by", "for",
    "from", "has", "have", "how", "in", "into", "is", "it", "its",
    "of", "on", "or", "that", "the", "their", "there", "these", "this",
    "those", "to", "was", "were", "what", "when", "where", "which", "who",
    "why", "with", "would", "could", "should", "can", "may", "might",
    "proposed", "proposal", "concept", "concepts", "describing", "description",
    "participant", "participants", "source", "record", "useful", "work",
    "article", "book", "system", "systems", "theory", "setting", "settings",
    "rather", "entirely", "based", "certain", "particular", "possible", "between",
})


def tokenize(text: str, *, remove_stop_words: bool = True) -> tuple[str, ...]:
    if not isinstance(text, str):
        raise TypeError("text must be a string")
    tokens = tuple(token.lower() for token in _TOKEN_PATTERN.findall(text))
    if not remove_stop_words:
        return tokens
    return tuple(token for token in tokens if token not in STOP_WORDS)
