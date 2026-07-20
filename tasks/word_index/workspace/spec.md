# Task: Word Index

Create a file `word_index.py` in this directory implementing a class
`WordIndex` — an inverted index over a text.

## API

- `WordIndex(text: str)` — tokenize and index the text once, in the
  constructor.
- `positions(word: str) -> list[int]` — 0-based token positions where the
  word occurs, in ascending order. Empty list if absent.
- `count(word: str) -> int` — number of occurrences.
- `first(word: str) -> int or None` — position of the first occurrence, or
  `None`.

## Tokenization rules

- A token is a maximal run of letters, digits, or apostrophes (`'`).
  Everything else (spaces, punctuation, newlines) separates tokens.
- Matching is case-insensitive: `positions("The")` and `positions("the")`
  return the same result. Indexed text and query words are both lowercased.
- Position numbering counts tokens from 0 in reading order.

## Constraints

- Queries (`positions`, `count`, `first`) must be O(1) dictionary lookups —
  NO rescanning of the text per query. (A performance test enforces this.)
- `positions` must return a fresh copy — callers mutating the returned list
  must not corrupt the index.
- Pure standard library. No third-party packages.
