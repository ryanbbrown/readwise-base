# Keep backfill as a separate static corpus

Documents tagged `backfill` or `.backfill` are a completed historical collection. A one-time explicit build writes them to `backfill.jsonl` and `backfill/`; normal syncs update only the main corpus and never touch the backfill outputs. Keeping the collections separate makes historical documents searchable without adding them to the working corpus, while refusing replacement protects the completed snapshot from accidental changes.
