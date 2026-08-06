# readwise-base

Build a filesystem-native knowledge base from Readwise Reader. The output contains one complete document aggregate per line in JSONL and one title-based Markdown view per document.

## Requirements

- Python 3.12 or newer
- `uv`
- Readwise CLI 0.5.3 or newer, already authenticated with `readwise login`
- `jq` for structured corpus queries

## Build the corpus

```bash
uv sync
uv run readwise-base
```

The default destination is `~/vault/knowledge-base`:

```text
corpus.jsonl
documents/<Reader title>.md
backfill.jsonl
backfill/<Reader title>.md
```

Override it when needed:

```bash
uv run readwise-base --output /path/to/knowledge-base
```

The normal build updates only `corpus.jsonl` and `documents/`. It includes Library documents with a document tag or highlight. It excludes Feed items, deleted documents, and documents tagged `backfill` or `.backfill`. Reader's Archive location is included.

## Build the static backfill

Run this command once:

```bash
uv run readwise-base --build-backfill
```

The command writes every active, non-Feed document tagged `backfill` or `.backfill` to `backfill.jsonl` and `backfill/`. It includes full content, metadata, notes, and highlights. Once `backfill.jsonl` exists, the command refuses to replace the snapshot. A `backfill/` directory without `backfill.jsonl` is an incomplete build and can be replaced. Normal syncs never update or remove the completed backfill snapshot.

Markdown filenames use a filesystem-safe form of the Reader title. The sync removes quotation marks and question marks, changes path separators to ` - `, and preserves comparisons as `‹` and `›`. It adds a short Reader ID only when another file already uses the same name. Generated paths are unique and no unrelated file is overwritten.

The sync stages the complete JSONL and Markdown snapshot before publishing either output. A fetch, validation, write, or publication failure leaves the previous complete snapshot in place. The next sync recovers an interrupted publication before doing any work.

## Query the corpus

Find documents whose full content mentions one term and whose highlights mention another:

```bash
jq -c --arg article "distributed systems" --arg highlight "coordination" '
  select(
    (.content.text | test($article; "i"))
    and any(.highlights[]?; ((.text + " " + (.note // "")) | test($highlight; "i")))
  )
  | {id, title, source_url}
' ~/vault/knowledge-base/corpus.jsonl
```

Pass both JSONL files to search the main and backfill corpora together:

```bash
jq -c 'select(.content.text | test("prestige"; "i")) | {title, source_url, markdown_path}' \
  ~/vault/knowledge-base/corpus.jsonl \
  ~/vault/knowledge-base/backfill.jsonl
```

## Verify

```bash
uv run pytest
uv run ruff check .
uv run pyright
```
