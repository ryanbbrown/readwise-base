from __future__ import annotations

import json
import subprocess

import pytest

import readwise_base.readwise_cli as readwise_cli
from readwise_base.readwise_cli import ReadwiseCliSource


def completed(payload: object, *, returncode: int = 0, stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(
        args=["readwise"],
        returncode=returncode,
        stdout=json.dumps(payload),
        stderr=stderr,
    )


def test_list_records_rejects_non_object_records(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        subprocess,
        "run",
        lambda *args, **kwargs: completed({"results": ["not an object"], "nextPageCursor": None}),
    )

    with pytest.raises(RuntimeError, match="non-object record"):
        ReadwiseCliSource().list_records()


def test_list_records_rejects_repeated_page_cursors(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        if calls > 2:
            raise AssertionError("pagination did not stop")
        return completed({"results": [{"id": f"record-{calls}"}], "nextPageCursor": "same-cursor"})

    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(RuntimeError, match="repeated page cursor"):
        ReadwiseCliSource().list_records()


def test_missing_executable_has_an_actionable_error(monkeypatch: pytest.MonkeyPatch) -> None:
    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        raise FileNotFoundError("No such file or directory")

    monkeypatch.setattr(subprocess, "run", run)

    with pytest.raises(RuntimeError, match="Could not run missing-readwise"):
        ReadwiseCliSource("missing-readwise").list_records()


def test_non_transient_failures_are_not_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    calls = 0

    def run(*args: object, **kwargs: object) -> subprocess.CompletedProcess[str]:
        nonlocal calls
        calls += 1
        return completed({}, returncode=1, stderr="Authentication failed")

    monkeypatch.setattr(subprocess, "run", run)
    monkeypatch.setattr(readwise_cli.time, "sleep", lambda seconds: pytest.fail(f"unexpected sleep: {seconds}"))

    with pytest.raises(RuntimeError, match="Authentication failed"):
        ReadwiseCliSource(retries=8).list_records()

    assert calls == 1


def test_transient_failures_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        completed({}, returncode=1, stderr="429 Too Many Requests"),
        completed({"results": [{"id": "article"}], "nextPageCursor": None}),
    ]
    sleeps: list[int] = []
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(readwise_cli.time, "sleep", sleeps.append)

    records = ReadwiseCliSource(retries=3).list_records()

    assert records == [{"id": "article"}]
    assert sleeps == [1]


def test_generic_reader_list_failures_are_retried(monkeypatch: pytest.MonkeyPatch) -> None:
    responses = [
        completed({}, returncode=1, stderr="Error listing documents from Reader"),
        completed({"results": [{"id": "article"}], "nextPageCursor": None}),
    ]
    monkeypatch.setattr(subprocess, "run", lambda *args, **kwargs: responses.pop(0))
    monkeypatch.setattr(readwise_cli.time, "sleep", lambda seconds: None)

    records = ReadwiseCliSource(retries=3).list_records()

    assert records == [{"id": "article"}]
