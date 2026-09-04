# Readwise corpus

Readwise Base builds a local corpus from a Reader Library.

## Language

**Reader document**:
A top-level item stored in Reader, including its metadata, summary, note, available content, and child highlights.
_Avoid_: Article, source

**Highlight**:
A user-created selection attached to a Reader document, with optional text, note, and tags. A highlight with no text still records a user interaction, but it cannot become a normalized text highlight.
_Avoid_: Comment, note

**Interaction**:
A user-added tag, active highlight, comment, or note on a Reader document. Deleted highlights and notes are not interactions.
_Avoid_: Engagement, activity

**Document with interactions**:
An eligible document that has at least one interaction.
_Avoid_: Engaged document, annotated article

**Document without interactions**:
An eligible document that has no interactions.
_Avoid_: Unengaged document, untouched article

**Eligible document**:
An active top-level Reader document that is outside Feed and is not tagged as backfill.
_Avoid_: Selected article, synced item

**Backfill document**:
A completed historical Reader document tagged `backfill` or `.backfill`. Backfill documents form a fixed reference collection rather than the working corpus.
_Avoid_: Archived document, eligible document

**Corpus record**:
The structured representation of one Reader document belonging to a corpus, including Reader open times and content when available.
_Avoid_: Row, entry

**Markdown view**:
The generated human-readable representation of a corpus record, classified by whether its Reader document has interactions.
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
