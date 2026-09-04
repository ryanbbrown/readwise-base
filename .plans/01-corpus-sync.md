# Build the Reader corpus

Build a complete local snapshot of eligible Reader documents at `~/vault/knowledge-base`.

## Contract

- Include every active top-level Reader document outside Feed, including documents with no tags, notes, or highlights.
- Include documents in Reader's Archive location.
- Exclude deleted documents and documents tagged `backfill` or `.backfill`, ignoring case.
- Write one complete document aggregate per line to `corpus.jsonl`, including Markdown content when available, Reader open times, and nested text highlights.
- Report and retain metadata-only documents when Reader has no content.
- Report and omit highlight rows with no text while retaining their parent documents and interaction classification.
- Write each main Markdown view under `with-interactions/` when its document has a user-added tag, any active highlight, or a comment or note.
- Write all other main Markdown views under `without-interactions/`.
- Point every main `markdown_path` at one of these two folders.
- Provide an explicit one-time build that writes backfill documents to `backfill.jsonl` and `backfill/`.
- Refuse to replace an existing backfill snapshot, and never touch it during a normal sync.
- Add a short Reader ID only when sanitized titles collide.
- Treat the main structured corpus and both main Markdown folders as one generated, replaceable snapshot.
- Remove the obsolete `documents/` folder only when publication succeeds.
- Remove only stale Markdown files named by the previous corpus from the two current folders; preserve unrelated files there.

## Verification

- Tests cover complete active-document inclusion, interaction classification, omitted non-text highlights, deleted interactions, layout migration, Feed and backfill exclusion, Reader open times, nested notes and highlights, metadata-only documents, invalid content types, punctuation cleanup, portable filename limits, stable filename ownership, case-sensitive collisions, malformed Reader responses, retry behavior, failed-write rollback, interrupted-publication recovery, stale files, backfill isolation, and write-once protection.
- The 2026-09-03 live main corpus contains 677 records: 164 with interactions and 513 without interactions.
- It contains 253 text highlights, omits 5 non-text highlights with warnings, and retains 1 metadata-only document with a warning.
- The static backfill remains unchanged at 87 records and 87 Markdown files.
- Every JSONL line parses independently and references an existing Markdown file in the correct main folder.
