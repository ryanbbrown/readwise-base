# Build the Reader corpus

Build a complete local snapshot of eligible Reader documents at `~/vault/knowledge-base`.

## Contract

- Include top-level Reader documents outside Feed when they have a document tag or highlight.
- Include documents in Reader's Archive location.
- Exclude deleted documents and documents tagged `backfill` or `.backfill`, ignoring case.
- Write one complete document aggregate per line to `corpus.jsonl`, including full Markdown content and nested highlights.
- Write one Markdown view per record under `documents/`, using the document title as the filename.
- Provide an explicit one-time build that writes backfill documents to `backfill.jsonl` and `backfill/`.
- Refuse to replace an existing backfill snapshot, and never touch it during a normal sync.
- Add a short Reader ID only when sanitized titles collide.
- Treat both outputs as generated and replaceable.
- Remove only stale Markdown files named by the previous corpus; preserve unrelated files.

## Verification

- Tests cover inclusion, exclusion, nested notes and highlights, required full content, punctuation cleanup, portable filename limits, stable filename ownership, case-sensitive collisions, malformed Reader responses, retry behavior, failed-write rollback, interrupted-publication recovery, stale files, backfill isolation, and write-once protection.
- The live build contains 143 JSONL records and the same number of generated Markdown files.
- Every JSONL line parses independently and references an existing Markdown file.
- A second live build produces identical corpus content.
