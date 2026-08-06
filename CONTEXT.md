# Readwise corpus

Readwise Base builds a local corpus from selected documents in a Reader Library.

## Language

**Reader document**:
A top-level item stored in Reader, including its metadata, summary, note, full content, and child highlights.
_Avoid_: Article, source

**Highlight**:
A selected passage attached to a Reader document, with an optional note and tags.
_Avoid_: Comment, annotation

**Eligible document**:
A Reader document that is outside Feed, is not tagged as backfill, and has at least one document tag or highlight.
_Avoid_: Selected article, synced item

**Backfill document**:
A completed historical Reader document tagged `backfill` or `.backfill`. Backfill documents form a fixed reference collection rather than the working corpus.
_Avoid_: Archived document, eligible document

**Corpus record**:
The complete structured representation of one Reader document belonging to a corpus.
_Avoid_: Row, entry

**Markdown view**:
The generated human-readable representation of a corpus record.
_Avoid_: Obsidian note, source file

**Main corpus**:
The current, replaceable set of eligible document records and their Markdown views.
_Avoid_: Working export, database

**Backfill corpus**:
The static, one-time set of backfill document records and their Markdown views.
_Avoid_: Archive, old corpus

**Corpus**:
A named set of corpus records and their Markdown views, either the main corpus or the backfill corpus.
_Avoid_: Export, database
