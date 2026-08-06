# Store each corpus as JSONL with Markdown views

Each generated corpus uses one complete document aggregate per JSONL line and one title-based Markdown view per record. JSONL preserves document, highlight, note, tag, and full-content structure for `jq` and regular-expression queries, while Markdown keeps the same material readable and searchable in Obsidian. Both forms are generated because a Markdown-only corpus loses structure and a JSONL-only corpus is awkward to read.
