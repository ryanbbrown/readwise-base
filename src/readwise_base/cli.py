"""Command-line interface for readwise-base."""

from __future__ import annotations

import argparse
from pathlib import Path

from readwise_base.corpus import build_backfill_corpus, build_corpus
from readwise_base.readwise_cli import ReadwiseCliSource, default_destination


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Build a JSONL and Markdown corpus from Readwise Reader.")
    parser.add_argument("--output", type=Path, default=default_destination(), help="Corpus destination directory")
    parser.add_argument("--readwise-command", default="readwise", help="Readwise CLI executable")
    parser.add_argument("--workers", type=int, default=4, help="Concurrent document detail requests")
    parser.add_argument("--retries", type=int, default=8, help="Attempts for transient Readwise CLI failures")
    parser.add_argument(
        "--build-backfill",
        action="store_true",
        help="Create the static backfill snapshot once; normal syncs never update it",
    )
    return parser


def main() -> None:
    parser = _parser()
    arguments = parser.parse_args()
    source = ReadwiseCliSource(arguments.readwise_command, retries=arguments.retries)
    version = source.check()
    print(f"Using Readwise CLI {version}")

    def progress(completed: int, total: int, title: str) -> None:
        if completed == total or completed == 1 or completed % 10 == 0:
            print(f"Fetched {completed}/{total}: {title}")

    builder = build_backfill_corpus if arguments.build_backfill else build_corpus
    try:
        result = builder(source, arguments.output, workers=arguments.workers, progress=progress)
    except FileExistsError as error:
        parser.exit(status=1, message=f"error: {error}\n")
    if arguments.build_backfill:
        print(f"Built static backfill with {result.documents} documents and {result.highlights} highlights.")
    else:
        print(
            f"Built {result.documents} documents with {result.highlights} highlights; "
            f"excluded {result.excluded_backfill} backfill documents."
        )
    print(f"JSONL: {result.jsonl_path}")
    print(f"Markdown: {result.markdown_dir}")


if __name__ == "__main__":
    main()
