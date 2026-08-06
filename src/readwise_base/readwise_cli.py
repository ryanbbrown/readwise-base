"""Readwise CLI adapter."""

from __future__ import annotations

import json
import subprocess
import time
from pathlib import Path
from typing import Any

JsonObject = dict[str, Any]


class ReadwiseCliSource:
    def __init__(self, command: str = "readwise", *, retries: int = 8) -> None:
        self.command = command
        self.retries = max(1, retries)

    def _run_json(self, arguments: list[str]) -> Any:
        command = [self.command, "--json", *arguments]
        last_error = "Readwise CLI failed"
        for attempt in range(self.retries):
            try:
                completed = subprocess.run(command, capture_output=True, text=True, check=False, timeout=120)
            except subprocess.TimeoutExpired:
                last_error = f"Readwise CLI timed out running {arguments[0]}"
                completed = None
            except OSError as error:
                raise RuntimeError(f"Could not run {self.command}: {error}") from error
            if completed is None:
                if attempt + 1 < self.retries:
                    time.sleep(min(2**attempt, 30))
                continue
            if completed.returncode == 0:
                try:
                    return json.loads(completed.stdout)
                except json.JSONDecodeError as error:
                    raise RuntimeError(f"Readwise CLI returned invalid JSON: {error}") from error
            last_error = completed.stderr.strip() or completed.stdout.strip() or last_error
            if attempt + 1 < self.retries and self._is_transient(last_error):
                time.sleep(min(2**attempt, 30))
                continue
            break
        raise RuntimeError(last_error)

    @staticmethod
    def _is_transient(message: str) -> bool:
        lowered = message.casefold()
        return any(
            marker in lowered
            for marker in (
                "429",
                "500",
                "502",
                "503",
                "504",
                "connection reset",
                "error getting document",
                "error listing documents from reader",
                "rate limit",
                "temporarily unavailable",
                "timed out",
                "timeout",
                "too many requests",
            )
        )

    def check(self) -> str:
        try:
            completed = subprocess.run(
                [self.command, "--version"], capture_output=True, text=True, check=False, timeout=30
            )
        except (OSError, subprocess.TimeoutExpired) as error:
            raise RuntimeError(f"Could not run {self.command}: {error}") from error
        if completed.returncode != 0:
            raise RuntimeError(completed.stderr.strip() or f"Could not run {self.command}")
        return completed.stdout.strip()

    def list_records(self, *, category: str | None = None, include_content: bool = False) -> list[JsonObject]:
        records: list[JsonObject] = []
        cursor: str | None = None
        seen_cursors: set[str] = set()
        seen_ids: set[str] = set()
        while True:
            arguments = ["reader-list-documents", "--limit", "100"]
            if category:
                arguments.extend(["--category", category])
            if include_content:
                arguments.extend(
                    [
                        "--response-fields",
                        "category,parent_id,tags,content,notes,created_at,updated_at,url,is_deleted",
                    ]
                )
            if cursor:
                arguments.extend(["--page-cursor", cursor])
            page = self._run_json(arguments)
            if not isinstance(page, dict):
                raise RuntimeError("Readwise CLI list response was not an object")
            page_records = page.get("results")
            if not isinstance(page_records, list):
                raise RuntimeError("Readwise CLI list response did not contain a results list")
            for record in page_records:
                if not isinstance(record, dict):
                    raise RuntimeError("Readwise CLI list response contained a non-object record")
                record_id = record.get("id")
                if not isinstance(record_id, str) or not record_id:
                    raise RuntimeError("Readwise CLI list response contained a record without an id")
                if record_id in seen_ids:
                    raise RuntimeError(f"Readwise CLI list response repeated record id {record_id}")
                seen_ids.add(record_id)
                records.append(record)
            cursor_value = page.get("nextPageCursor")
            cursor = str(cursor_value) if cursor_value else None
            if not cursor:
                return records
            if cursor in seen_cursors:
                raise RuntimeError(f"Readwise CLI returned repeated page cursor {cursor}")
            seen_cursors.add(cursor)

    def get_document_details(self, document_id: str) -> JsonObject:
        details = self._run_json(["reader-get-document-details", "--document-id", document_id])
        if not isinstance(details, dict):
            raise RuntimeError(f"Readwise CLI returned invalid details for {document_id}")
        return details


def default_destination() -> Path:
    return Path("~/vault/knowledge-base").expanduser()
