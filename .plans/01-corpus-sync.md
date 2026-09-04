# Build the Reader corpus

Build a complete local snapshot of eligible Reader documents at `~/vault/knowledge-base`.

## Contract

- Include every active top-level Reader document outside Feed, including documents with no tags, notes, or highlights.
- Include documents in Reader's Archive location.
- Exclude deleted documents and documents tagged `backfill` or `.backfill`, ignoring case.
- Write one complete document aggregate per line to `corpus.jsonl`, including Markdown content when available, Reader open times, and nested text highlights.
- Report and retain metadata-only documents when Reader has no content.
- Report and omit highlight rows with no text while retaining their parent documents.
- Write one Markdown view per record under `documents/`, using the document title as the filename.
- Provide an explicit one-time build that writes backfill documents to `backfill.jsonl` and `backfill/`.
- Refuse to replace an existing backfill snapshot, and never touch it during a normal sync.
- Add a short Reader ID only when sanitized titles collide.
- Treat both outputs as generated and replaceable.
- Remove only stale Markdown files named by the previous corpus; preserve unrelated files.

## Verification

- Tests cover complete active-document inclusion, Feed and backfill exclusion, Reader open times, nested notes and highlights, metadata-only documents, non-text highlight omission, invalid content types, punctuation cleanup, portable filename limits, stable filename ownership, case-sensitive collisions, malformed Reader responses, retry behavior, failed-write rollback, interrupted-publication recovery, stale files, backfill isolation, and write-once protection.
- The 2026-09-03 live build contains 676 JSONL records and the same number of generated Markdown files.
- It contains 253 text highlights, omits 5 non-text highlights with warnings, and retains 1 metadata-only document with a warning.
- Every JSONL line parses independently and references an existing Markdown file.
