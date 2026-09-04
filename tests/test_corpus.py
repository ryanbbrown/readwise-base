from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import pytest

import readwise_base.corpus as corpus_module
from readwise_base.corpus import JsonObject, build_backfill_corpus, build_corpus


def document(document_id: str, **overrides: object) -> JsonObject:
    row: JsonObject = {
        "id": document_id,
        "url": f"https://read.readwise.io/read/{document_id}",
        "title": f"Article {document_id}",
        "author": "Example Author",
        "source": "Reader Share Sheet iOS",
        "category": "article",
        "location": "archive",
        "tags": {},
        "site_name": "Example",
        "word_count": 100,
        "reading_time": "1 min",
        "listening_time": None,
        "created_at": "2026-01-01T00:00:00Z",
        "updated_at": "2026-01-03T00:00:00Z",
        "published_date": "2025-12-31",
        "summary": "A useful summary.",
        "image_url": "https://example.com/image.png",
        "source_url": f"https://example.com/{document_id}",
        "notes": "",
        "parent_id": None,
        "reading_progress": 1,
        "first_opened_at": "2026-01-02T00:00:00Z",
        "last_opened_at": "2026-01-03T00:00:00Z",
        "saved_at": "2026-01-01T00:00:00Z",
        "is_deleted": None,
    }
    row.update(overrides)
    return row


def highlight(highlight_id: str, parent_id: str, **overrides: object) -> JsonObject:
    row: JsonObject = {
        "id": highlight_id,
        "url": f"https://read.readwise.io/read/{highlight_id}",
        "category": "highlight",
        "content": "Highlighted evidence.",
        "notes": "",
        "tags": {"important": {}},
        "parent_id": parent_id,
        "created_at": "2026-01-02T00:00:00Z",
        "updated_at": "2026-01-02T01:00:00Z",
        "is_deleted": None,
    }
    row.update(overrides)
    return row


def note(note_id: str, parent_id: str, text: str) -> JsonObject:
    return {
        "id": note_id,
        "category": "note",
        "content": text,
        "parent_id": parent_id,
        "updated_at": "2026-01-02T02:00:00Z",
        "is_deleted": None,
    }


@dataclass
class FakeReaderSource:
    metadata: list[JsonObject]
    highlights: list[JsonObject]
    notes: list[JsonObject]
    details: dict[str, JsonObject]

    def list_records(self, *, category: str | None = None, include_content: bool = False) -> list[JsonObject]:
        del include_content
        if category == "highlight":
            return self.highlights
        if category == "note":
            return self.notes
        return self.metadata

    def get_document_details(self, document_id: str) -> JsonObject:
        return self.details[document_id]


class ExplodingReaderSource:
    def list_records(self, *, category: str | None = None, include_content: bool = False) -> list[JsonObject]:
        raise AssertionError("static snapshot guard must run before Reader is queried")

    def get_document_details(self, document_id: str) -> JsonObject:
        raise AssertionError("static snapshot guard must run before Reader is queried")


def read_jsonl(path: Path) -> list[JsonObject]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line]


def test_builds_queryable_jsonl_and_title_based_markdown_for_all_active_documents(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[
            document("tagged", title="Tagged / Article", tags={"research": {}}),
            document("highlighted", title="Highlighted Article"),
            document("backfill", tags={".Backfill": {}}),
            document("feed", location="feed", tags={"research": {}}),
            document("deleted", is_deleted=True),
            document("untouched", first_opened_at="2026-02-01T00:00:00Z", last_opened_at="2026-02-02T00:00:00Z"),
        ],
        highlights=[highlight("highlight-1", "highlighted")],
        notes=[note("note-1", "highlight-1", "My comment on the highlight.")],
        details={
            "tagged": {
                "id": "tagged",
                "title": "Tagged / Article",
                "author": "Example Author",
                "tags": ["research"],
                "category": "article",
                "content": "Full tagged article text.",
                "notes": "Why this article matters.",
            },
            "highlighted": {
                "id": "highlighted",
                "title": "Highlighted Article",
                "author": "Example Author",
                "tags": [],
                "category": "article",
                "content": "Full highlighted article text.",
                "notes": "",
            },
            "untouched": {
                "id": "untouched",
                "title": "Article untouched",
                "author": "Example Author",
                "tags": [],
                "category": "article",
                "content": "Full untouched article text.",
                "notes": "",
            },
        },
    )

    result = build_corpus(source, tmp_path, workers=2)

    assert result.documents == 3
    assert result.documents_without_content == 0
    assert result.documents_with_interactions == 2
    assert result.documents_without_interactions == 1
    assert result.highlights == 1
    assert result.omitted_highlights == 0
    assert result.excluded_backfill == 1
    rows = read_jsonl(result.jsonl_path)
    assert [row["id"] for row in rows] == ["highlighted", "tagged", "untouched"]
    highlighted = rows[0]
    assert highlighted["content"] == {"format": "markdown", "text": "Full highlighted article text."}
    assert highlighted["highlights"] == [
        {
            "id": "highlight-1",
            "text": "Highlighted evidence.",
            "note": "My comment on the highlight.",
            "tags": ["important"],
            "created_at": "2026-01-02T00:00:00Z",
            "updated_at": "2026-01-02T01:00:00Z",
            "reader_url": "https://read.readwise.io/read/highlight-1",
        }
    ]
    tagged = rows[1]
    assert tagged["summary"] == "A useful summary."
    assert tagged["document_note"] == "Why this article matters."
    assert tagged["markdown_path"] == "with-interactions/Tagged - Article.md"
    markdown = (tmp_path / tagged["markdown_path"]).read_text(encoding="utf-8")
    assert "# Tagged / Article" in markdown
    assert "## Summary\n\nA useful summary." in markdown
    assert "## Document note\n\nWhy this article matters." in markdown
    assert "## Full article\n\nFull tagged article text." in markdown
    untouched = rows[2]
    assert untouched["schema_version"] == 2
    assert untouched["markdown_path"] == "without-interactions/Article untouched.md"
    assert untouched["first_opened_at"] == "2026-02-01T00:00:00Z"
    assert untouched["last_opened_at"] == "2026-02-02T00:00:00Z"
    untouched_markdown = (tmp_path / untouched["markdown_path"]).read_text(encoding="utf-8")
    assert 'first_opened_at: "2026-02-01T00:00:00Z"' in untouched_markdown
    assert 'last_opened_at: "2026-02-02T00:00:00Z"' in untouched_markdown


def test_main_markdown_is_split_by_user_interactions(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[
            document("tagged", tags={"research": {}}),
            document("highlighted"),
            document("image-highlighted"),
            document("document-note", notes="A note in metadata."),
            document("child-note"),
            document("detail-note"),
            document("deleted-highlight"),
            document("deleted-note"),
            document("untouched"),
        ],
        highlights=[
            highlight("text-highlight", "highlighted"),
            highlight("image-highlight", "image-highlighted", content=""),
            highlight("deleted-highlight-row", "deleted-highlight", is_deleted=True),
        ],
        notes=[
            note("child-note-row", "child-note", "A child note."),
            {**note("deleted-note-row", "deleted-note", "Deleted."), "is_deleted": True},
        ],
        details={
            document_id: {
                "id": document_id,
                "title": f"Article {document_id}",
                "content": "Body.",
                "notes": "A note in details." if document_id == "detail-note" else "",
            }
            for document_id in (
                "tagged",
                "highlighted",
                "image-highlighted",
                "document-note",
                "child-note",
                "detail-note",
                "deleted-highlight",
                "deleted-note",
                "untouched",
            )
        },
    )

    with pytest.warns(UserWarning, match="Omitting highlight image-highlight because it has no text"):
        result = build_corpus(source, tmp_path)

    rows = {row["id"]: row for row in read_jsonl(result.jsonl_path)}
    assert {document_id: row["markdown_path"].split("/", maxsplit=1)[0] for document_id, row in rows.items()} == {
        "child-note": "with-interactions",
        "deleted-highlight": "without-interactions",
        "deleted-note": "without-interactions",
        "detail-note": "with-interactions",
        "document-note": "with-interactions",
        "highlighted": "with-interactions",
        "image-highlighted": "with-interactions",
        "tagged": "with-interactions",
        "untouched": "without-interactions",
    }
    assert len(list((tmp_path / "with-interactions").glob("*.md"))) == 6
    assert len(list((tmp_path / "without-interactions").glob("*.md"))) == 3
    assert not (tmp_path / "documents").exists()


def test_rebuild_moves_documents_when_interaction_status_changes(tmp_path: Path) -> None:
    first = FakeReaderSource(
        metadata=[
            document("loses-tag", title="Loses tag", tags={"research": {}}),
            document("gains-tag", title="Gains tag"),
        ],
        highlights=[],
        notes=[],
        details={
            "loses-tag": {"id": "loses-tag", "title": "Loses tag", "content": "Body.", "notes": ""},
            "gains-tag": {"id": "gains-tag", "title": "Gains tag", "content": "Body.", "notes": ""},
        },
    )
    build_corpus(first, tmp_path)
    second = FakeReaderSource(
        metadata=[
            document("loses-tag", title="Loses tag"),
            document("gains-tag", title="Gains tag", tags={"research": {}}),
        ],
        highlights=[],
        notes=[],
        details=first.details,
    )

    build_corpus(second, tmp_path)

    paths = {row["id"]: row["markdown_path"] for row in read_jsonl(tmp_path / "corpus.jsonl")}
    assert paths == {
        "gains-tag": "with-interactions/Gains tag.md",
        "loses-tag": "without-interactions/Loses tag.md",
    }
    assert not (tmp_path / "with-interactions" / "Loses tag.md").exists()
    assert not (tmp_path / "without-interactions" / "Gains tag.md").exists()


def test_archive_location_is_included_and_title_collisions_get_stable_suffixes(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[
            document("aaa11111", title="Same / Title", tags={"one": {}}),
            document("bbb22222", title="Same: Title", tags={"two": {}}),
        ],
        highlights=[],
        notes=[],
        details={
            "aaa11111": {"id": "aaa11111", "title": "Same / Title", "content": "First.", "notes": ""},
            "bbb22222": {"id": "bbb22222", "title": "Same: Title", "content": "Second.", "notes": ""},
        },
    )

    build_corpus(source, tmp_path)
    rows = read_jsonl(tmp_path / "corpus.jsonl")

    assert [row["location"] for row in rows] == ["archive", "archive"]
    assert [row["markdown_path"] for row in rows] == [
        "with-interactions/Same - Title.md",
        "with-interactions/Same - Title — bbb22222.md",
    ]


def test_rebuild_removes_only_stale_generated_markdown(tmp_path: Path) -> None:
    first = FakeReaderSource(
        metadata=[document("old", title="Old", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"old": {"id": "old", "title": "Old", "content": "Old body.", "notes": ""}},
    )
    build_corpus(first, tmp_path)
    unrelated = tmp_path / "with-interactions" / "My note.md"
    unrelated.write_text("Keep me.\n", encoding="utf-8")

    second = FakeReaderSource(metadata=[], highlights=[], notes=[], details={})
    result = build_corpus(second, tmp_path)

    assert result.documents == 0
    assert not (tmp_path / "with-interactions" / "Old.md").exists()
    assert unrelated.read_text(encoding="utf-8") == "Keep me.\n"
    assert (tmp_path / "corpus.jsonl").read_text(encoding="utf-8") == ""


def test_rebuild_reads_jsonl_with_unicode_line_separator_inside_content(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[document("article")],
        highlights=[],
        notes=[],
        details={
            "article": {
                "id": "article",
                "title": "Article",
                "content": "First paragraph.\u2028Second paragraph.",
                "notes": "",
            }
        },
    )

    build_corpus(source, tmp_path)
    result = build_corpus(source, tmp_path)

    assert result.documents == 1
    assert len((tmp_path / "corpus.jsonl").read_bytes().splitlines()) == 1


def test_filename_sanitization_does_not_turn_punctuation_into_stray_hyphens(tmp_path: Path) -> None:
    titles = {
        "quoted": '"What\'s Wrong With This Idea?"',
        "question": "Is SaaS dead?",
        "inner-quotes": 'Building a "personal brand"',
        "command": "/goal + Loss Functions: A Playbook",
        "comparison": "Code mode: code > calling tools",
        "literal-hyphens": "-​-dangerously-skip-reading-code",
    }
    source = FakeReaderSource(
        metadata=[document(document_id, title=title, tags={"keep": {}}) for document_id, title in titles.items()],
        highlights=[],
        notes=[],
        details={
            document_id: {"id": document_id, "title": title, "content": "Body.", "notes": ""}
            for document_id, title in titles.items()
        },
    )

    build_corpus(source, tmp_path)
    paths = {row["id"]: row["markdown_path"] for row in read_jsonl(tmp_path / "corpus.jsonl")}

    assert paths == {
        "command": "with-interactions/goal + Loss Functions - A Playbook.md",
        "comparison": "with-interactions/Code mode - code › calling tools.md",
        "inner-quotes": "with-interactions/Building a personal brand.md",
        "literal-hyphens": "with-interactions/-​-dangerously-skip-reading-code.md",
        "question": "with-interactions/Is SaaS dead.md",
        "quoted": "with-interactions/What's Wrong With This Idea.md",
    }


def test_colliding_titles_never_share_a_path_or_overwrite_an_unrelated_file(tmp_path: Path) -> None:
    documents_dir = tmp_path / "with-interactions"
    documents_dir.mkdir()
    unrelated = documents_dir / "Same.md"
    unrelated.write_text("Keep me.\n", encoding="utf-8")
    ids = ["abcdefgh1", "abcdefgh2", "abcdefgh3"]
    source = FakeReaderSource(
        metadata=[document(document_id, title="Same", tags={"keep": {}}) for document_id in ids],
        highlights=[],
        notes=[],
        details={
            document_id: {"id": document_id, "title": "Same", "content": document_id, "notes": ""}
            for document_id in ids
        },
    )

    build_corpus(source, tmp_path)
    rows = read_jsonl(tmp_path / "corpus.jsonl")
    paths = [row["markdown_path"] for row in rows]

    assert len(paths) == len(set(paths)) == 3
    assert unrelated.read_text(encoding="utf-8") == "Keep me.\n"
    for row in rows:
        markdown = (tmp_path / row["markdown_path"]).read_text(encoding="utf-8")
        assert f"## Full article\n\n{row['id']}" in markdown


def test_utf8_filenames_fit_common_filesystem_byte_limits(tmp_path: Path) -> None:
    title = "🔥" * 100
    source = FakeReaderSource(
        metadata=[document("emoji", title=title, tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"emoji": {"id": "emoji", "title": title, "content": "Body.", "notes": ""}},
    )

    build_corpus(source, tmp_path)
    row = read_jsonl(tmp_path / "corpus.jsonl")[0]

    assert len(Path(row["markdown_path"]).name.encode("utf-8")) <= 255
    assert (tmp_path / row["markdown_path"]).is_file()


def test_reserved_device_names_are_made_portable(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[document("reserved", title="CON.txt", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"reserved": {"id": "reserved", "title": "CON.txt", "content": "Body.", "notes": ""}},
    )

    build_corpus(source, tmp_path)

    assert read_jsonl(tmp_path / "corpus.jsonl")[0]["markdown_path"] == "with-interactions/_CON.txt.md"


def test_feed_and_backfill_exclusions_ignore_case_and_surrounding_space(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[
            document("feed", location="Feed", tags={"keep": {}}),
            document("backfill", tags={" .BACKFILL ": {}}),
        ],
        highlights=[],
        notes=[],
        details={
            "feed": {"id": "feed", "title": "Feed", "content": "Body.", "notes": ""},
            "backfill": {"id": "backfill", "title": "Backfill", "content": "Body.", "notes": ""},
        },
    )

    result = build_corpus(source, tmp_path)

    assert result.documents == 0
    assert result.excluded_backfill == 1


def test_document_without_content_is_warned_and_kept_as_metadata_only(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[document("article")],
        highlights=[],
        notes=[],
        details={"article": {"id": "article", "title": "Article", "content": "   ", "notes": ""}},
    )

    with pytest.warns(UserWarning, match=r"Including Reader document article \(Article\) without content"):
        result = build_corpus(source, tmp_path)

    assert result.documents == 1
    assert result.documents_without_content == 1
    row = read_jsonl(result.jsonl_path)[0]
    assert row["content"] == {"format": "markdown", "text": ""}
    markdown = (tmp_path / row["markdown_path"]).read_text(encoding="utf-8")
    assert "## Full article\n\n(No content available.)" in markdown


def test_duplicate_document_ids_fail_instead_of_creating_duplicate_records(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[
            document("duplicate", title="First", tags={"keep": {}}),
            document("duplicate", title="Second", tags={"keep": {}}),
        ],
        highlights=[],
        notes=[],
        details={"duplicate": {"id": "duplicate", "title": "Duplicate", "content": "Body.", "notes": ""}},
    )

    with pytest.raises(ValueError, match="duplicate document id: duplicate"):
        build_corpus(source, tmp_path)

    assert not (tmp_path / "corpus.jsonl").exists()


def test_unexpected_tag_shape_fails_instead_of_silently_excluding_a_document(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[document("article", tags="keep")],
        highlights=[],
        notes=[],
        details={},
    )

    with pytest.raises(ValueError, match="tags must be an object or list"):
        build_corpus(source, tmp_path)


def test_non_text_highlight_is_warned_and_omitted_while_its_parent_is_retained(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[document("article")],
        highlights=[highlight("image-highlight", "article", content="")],
        notes=[],
        details={"article": {"id": "article", "title": "Article", "content": "Body.", "notes": ""}},
    )

    with pytest.warns(UserWarning, match="Omitting highlight image-highlight because it has no text"):
        result = build_corpus(source, tmp_path)

    assert result.documents == 1
    assert result.highlights == 0
    assert result.omitted_highlights == 1
    row = read_jsonl(result.jsonl_path)[0]
    assert row["id"] == "article"
    assert row["highlights"] == []
    markdown = (tmp_path / row["markdown_path"]).read_text(encoding="utf-8")
    assert "## Highlights" not in markdown
    assert "## Full article\n\nBody." in markdown


def test_non_string_article_content_fails_instead_of_serializing_a_python_repr(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[document("article", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"article": {"id": "article", "title": "Article", "content": {"markdown": "Body."}, "notes": ""}},
    )

    with pytest.raises(ValueError, match="content was not text"):
        build_corpus(source, tmp_path)

    assert not (tmp_path / "corpus.jsonl").exists()


def test_builds_backfill_as_a_separate_complete_corpus(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[
            document("backfill", title="Building Prestige", tags={"career": {}, ".Backfill": {}}),
            document("main", tags={"research": {}}),
            document("feed", location="feed", tags={"backfill": {}}),
            document("deleted", tags={"backfill": {}}, is_deleted=True),
        ],
        highlights=[highlight("highlight-1", "backfill")],
        notes=[note("note-1", "highlight-1", "Relevant comment.")],
        details={
            "backfill": {
                "id": "backfill",
                "title": "Building Prestige",
                "author": "Example Author",
                "category": "article",
                "content": "Complete backfill article.",
                "notes": "Document note.",
            }
        },
    )

    result = build_backfill_corpus(source, tmp_path)

    assert result.documents == 1
    assert result.highlights == 1
    assert result.jsonl_path == tmp_path / "backfill.jsonl"
    assert result.markdown_dirs == (tmp_path / "backfill",)
    rows = read_jsonl(result.jsonl_path)
    assert [row["id"] for row in rows] == ["backfill"]
    assert rows[0]["markdown_path"] == "backfill/Building Prestige.md"
    assert rows[0]["highlights"][0]["note"] == "Relevant comment."
    assert rows[0]["content"]["text"] == "Complete backfill article."
    assert (tmp_path / rows[0]["markdown_path"]).is_file()
    assert not (tmp_path / "corpus.jsonl").exists()
    assert not (tmp_path / "documents").exists()
    assert not (tmp_path / "with-interactions").exists()
    assert not (tmp_path / "without-interactions").exists()


def test_normal_sync_never_changes_the_static_backfill_snapshot(tmp_path: Path) -> None:
    backfill_dir = tmp_path / "backfill"
    backfill_dir.mkdir()
    backfill_jsonl = tmp_path / "backfill.jsonl"
    backfill_markdown = backfill_dir / "Static.md"
    backfill_jsonl.write_bytes(b'{"static":true}\n')
    backfill_markdown.write_bytes(b"Static body.\n")
    source = FakeReaderSource(
        metadata=[document("main", title="Main", tags={"research": {}})],
        highlights=[],
        notes=[],
        details={"main": {"id": "main", "title": "Main", "content": "Main body.", "notes": ""}},
    )

    build_corpus(source, tmp_path)

    assert backfill_jsonl.read_bytes() == b'{"static":true}\n'
    assert backfill_markdown.read_bytes() == b"Static body.\n"
    assert (tmp_path / "corpus.jsonl").is_file()
    assert (tmp_path / "with-interactions" / "Main.md").is_file()


def test_backfill_build_refuses_to_replace_an_existing_static_snapshot(tmp_path: Path) -> None:
    backfill_jsonl = tmp_path / "backfill.jsonl"
    backfill_jsonl.write_bytes(b'{"static":true}\n')

    with pytest.raises(FileExistsError, match="static backfill snapshot already exists"):
        build_backfill_corpus(ExplodingReaderSource(), tmp_path)

    assert backfill_jsonl.read_bytes() == b'{"static":true}\n'


def test_successful_main_publication_removes_the_obsolete_documents_directory(tmp_path: Path) -> None:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    (documents_dir / "Old.md").write_text("Old layout.\n", encoding="utf-8")
    (tmp_path / "corpus.jsonl").write_text(
        json.dumps({"id": "old", "title": "Old", "markdown_path": "documents/Old.md"}) + "\n",
        encoding="utf-8",
    )
    source = FakeReaderSource(
        metadata=[document("new")],
        highlights=[],
        notes=[],
        details={"new": {"id": "new", "title": "New", "content": "Body.", "notes": ""}},
    )

    build_corpus(source, tmp_path)

    assert not documents_dir.exists()
    assert (tmp_path / "without-interactions" / "New.md").is_file()


def test_failed_main_publication_keeps_the_obsolete_documents_directory(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    documents_dir = tmp_path / "documents"
    documents_dir.mkdir()
    old_markdown = documents_dir / "Old.md"
    old_markdown.write_text("Old layout.\n", encoding="utf-8")
    old_jsonl = json.dumps({"id": "old", "title": "Old", "markdown_path": "documents/Old.md"}) + "\n"
    (tmp_path / "corpus.jsonl").write_text(old_jsonl, encoding="utf-8")
    source = FakeReaderSource(
        metadata=[document("new")],
        highlights=[],
        notes=[],
        details={"new": {"id": "new", "title": "New", "content": "Body.", "notes": ""}},
    )
    original_replace = corpus_module.os.replace
    failed = False

    def fail_without_interactions_publish(source_path: str | Path, target_path: str | Path) -> None:
        nonlocal failed
        if Path(target_path) == tmp_path / "without-interactions" and not failed:
            failed = True
            raise OSError("simulated publication failure")
        original_replace(source_path, target_path)

    monkeypatch.setattr(corpus_module.os, "replace", fail_without_interactions_publish)

    with pytest.raises(OSError, match="simulated publication failure"):
        build_corpus(source, tmp_path)

    assert (tmp_path / "corpus.jsonl").read_text(encoding="utf-8") == old_jsonl
    assert old_markdown.read_text(encoding="utf-8") == "Old layout.\n"
    assert not (tmp_path / "with-interactions").exists()
    assert not (tmp_path / "without-interactions").exists()


def test_failed_normal_sync_does_not_publish_any_partial_markdown(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = FakeReaderSource(
        metadata=[
            document("a", title="A", tags={"keep": {}}),
            document("b", title="B", tags={"keep": {}}),
        ],
        highlights=[],
        notes=[],
        details={
            "a": {"id": "a", "title": "A", "content": "Old A.", "notes": ""},
            "b": {"id": "b", "title": "B", "content": "Old B.", "notes": ""},
        },
    )
    build_corpus(initial, tmp_path)
    before = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    changed = FakeReaderSource(
        metadata=initial.metadata,
        highlights=[],
        notes=[],
        details={
            "a": {"id": "a", "title": "A", "content": "New A.", "notes": ""},
            "b": {"id": "b", "title": "B", "content": "New B.", "notes": ""},
        },
    )
    original_write = corpus_module._write_text_atomic
    markdown_writes = 0

    def fail_second_markdown(path: Path, content: str) -> None:
        nonlocal markdown_writes
        if path.suffix == ".md":
            markdown_writes += 1
            if markdown_writes == 2:
                raise OSError("simulated disk failure")
        original_write(path, content)

    monkeypatch.setattr(corpus_module, "_write_text_atomic", fail_second_markdown)

    with pytest.raises(OSError, match="simulated disk failure"):
        build_corpus(changed, tmp_path)

    after = {path.relative_to(tmp_path): path.read_bytes() for path in tmp_path.rglob("*") if path.is_file()}
    assert after == before


def test_publication_failure_restores_the_previous_complete_snapshot(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    initial = FakeReaderSource(
        metadata=[document("article", title="Article", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"article": {"id": "article", "title": "Article", "content": "Old body.", "notes": ""}},
    )
    build_corpus(initial, tmp_path)
    corpus_before = (tmp_path / "corpus.jsonl").read_bytes()
    markdown_before = (tmp_path / "with-interactions" / "Article.md").read_bytes()
    changed = FakeReaderSource(
        metadata=initial.metadata,
        highlights=[],
        notes=[],
        details={"article": {"id": "article", "title": "Article", "content": "New body.", "notes": ""}},
    )
    original_replace = corpus_module.os.replace
    failed = False

    def fail_first_live_jsonl_publish(source: str | Path, target: str | Path) -> None:
        nonlocal failed
        if Path(target) == tmp_path / "corpus.jsonl" and not failed:
            failed = True
            raise OSError("simulated publication failure")
        original_replace(source, target)

    monkeypatch.setattr(corpus_module.os, "replace", fail_first_live_jsonl_publish)

    with pytest.raises(OSError, match="simulated publication failure"):
        build_corpus(changed, tmp_path)

    assert (tmp_path / "corpus.jsonl").read_bytes() == corpus_before
    assert (tmp_path / "with-interactions" / "Article.md").read_bytes() == markdown_before


def test_transaction_setup_failure_cannot_be_recovered_as_an_interrupted_publication(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    original = FakeReaderSource(
        metadata=[document("z", title="Same", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"z": {"id": "z", "title": "Same", "content": "Original.", "notes": ""}},
    )
    build_corpus(original, tmp_path)
    corpus_before = (tmp_path / "corpus.jsonl").read_bytes()
    markdown_before = (tmp_path / "with-interactions" / "Same.md").read_bytes()
    changed = FakeReaderSource(
        metadata=[
            document("a", title="Same", tags={"keep": {}}),
            document("z", title="Same", tags={"keep": {}}),
        ],
        highlights=[],
        notes=[],
        details={
            "a": {"id": "a", "title": "Same", "content": "New article.", "notes": ""},
            "z": {"id": "z", "title": "Same", "content": "Original updated.", "notes": ""},
        },
    )
    original_write = corpus_module._write_text_atomic

    def fail_transaction_manifest(path: Path, content: str) -> None:
        if path.name == "transaction.json":
            raise OSError("simulated transaction setup failure")
        original_write(path, content)

    monkeypatch.setattr(corpus_module, "_write_text_atomic", fail_transaction_manifest)

    with pytest.raises(OSError, match="simulated transaction setup failure"):
        build_corpus(changed, tmp_path)

    assert (tmp_path / "corpus.jsonl").read_bytes() == corpus_before
    assert (tmp_path / "with-interactions" / "Same.md").read_bytes() == markdown_before
    assert not list(tmp_path.glob(".corpus.jsonl.backup.*"))
    assert not list(tmp_path.glob(".corpus.jsonl.preparing.*"))
    monkeypatch.setattr(corpus_module, "_write_text_atomic", original_write)

    build_corpus(changed, tmp_path)
    paths = {row["id"]: row["markdown_path"] for row in read_jsonl(tmp_path / "corpus.jsonl")}

    assert paths["z"] == "with-interactions/Same.md"
    assert paths["a"].startswith("with-interactions/Same — a")


def test_failed_first_backfill_build_can_be_retried(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    source = FakeReaderSource(
        metadata=[document("backfill", title="Backfill", tags={"backfill": {}})],
        highlights=[],
        notes=[],
        details={"backfill": {"id": "backfill", "title": "Backfill", "content": "Body.", "notes": ""}},
    )
    original_write = corpus_module._write_text_atomic

    def fail_markdown(path: Path, content: str) -> None:
        if path.suffix == ".md":
            raise OSError("simulated disk failure")
        original_write(path, content)

    monkeypatch.setattr(corpus_module, "_write_text_atomic", fail_markdown)

    with pytest.raises(OSError, match="simulated disk failure"):
        build_backfill_corpus(source, tmp_path)

    assert not (tmp_path / "backfill.jsonl").exists()
    assert not (tmp_path / "backfill").exists()
    monkeypatch.setattr(corpus_module, "_write_text_atomic", original_write)

    result = build_backfill_corpus(source, tmp_path)

    assert result.documents == 1
    assert (tmp_path / "backfill" / "Backfill.md").is_file()


def test_existing_document_keeps_its_path_when_a_new_title_collides(tmp_path: Path) -> None:
    original = FakeReaderSource(
        metadata=[document("z", title="Same", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"z": {"id": "z", "title": "Same", "content": "Original.", "notes": ""}},
    )
    build_corpus(original, tmp_path)
    changed = FakeReaderSource(
        metadata=[
            document("a", title="Same", tags={"keep": {}}),
            document("z", title="Same", tags={"keep": {}}),
        ],
        highlights=[],
        notes=[],
        details={
            "a": {"id": "a", "title": "Same", "content": "New article.", "notes": ""},
            "z": {"id": "z", "title": "Same", "content": "Original updated.", "notes": ""},
        },
    )

    build_corpus(changed, tmp_path)
    paths = {row["id"]: row["markdown_path"] for row in read_jsonl(tmp_path / "corpus.jsonl")}

    assert paths["z"] == "with-interactions/Same.md"
    assert paths["a"].startswith("with-interactions/Same — a")


def test_casefold_collision_does_not_hide_an_unrelated_exact_filename(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    destination = tmp_path
    documents_dir = destination / "with-interactions"
    documents_dir.mkdir()
    monkeypatch.setattr(
        Path,
        "iterdir",
        lambda path: iter([documents_dir / "Foo.md", documents_dir / "foo.md"]),
    )
    records: list[JsonObject] = [{"id": "new", "title": "foo"}]
    previous_records: dict[str, JsonObject] = {
        "old": {"id": "old", "title": "Foo", "markdown_path": "with-interactions/Foo.md"}
    }

    corpus_module._assign_markdown_paths(records, destination, previous_records, "with-interactions")

    assert records[0]["markdown_path"] != "with-interactions/foo.md"


def test_next_sync_recovers_an_interrupted_publication_before_allocating_paths(tmp_path: Path) -> None:
    original = FakeReaderSource(
        metadata=[document("z", title="Same", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"z": {"id": "z", "title": "Same", "content": "Original.", "notes": ""}},
    )
    build_corpus(original, tmp_path)
    backup = tmp_path / ".corpus.jsonl.backup.interrupted"
    backup.mkdir()
    manifest = {
        "had_paths": {
            "corpus.jsonl": True,
            "with-interactions": True,
            "without-interactions": True,
            "documents": False,
        }
    }
    (backup / "transaction.json").write_text(json.dumps(manifest), encoding="utf-8")
    (backup / "state").write_text("publishing\n", encoding="utf-8")
    (tmp_path / "corpus.jsonl").replace(backup / "corpus.jsonl")
    (tmp_path / "with-interactions").replace(backup / "with-interactions")
    (tmp_path / "without-interactions").replace(backup / "without-interactions")
    partial_documents = tmp_path / "with-interactions"
    partial_documents.mkdir()
    (partial_documents / "Partial.md").write_text("Incomplete publication.\n", encoding="utf-8")
    changed = FakeReaderSource(
        metadata=[
            document("a", title="Same", tags={"keep": {}}),
            document("z", title="Same", tags={"keep": {}}),
        ],
        highlights=[],
        notes=[],
        details={
            "a": {"id": "a", "title": "Same", "content": "New article.", "notes": ""},
            "z": {"id": "z", "title": "Same", "content": "Original updated.", "notes": ""},
        },
    )

    build_corpus(changed, tmp_path)
    paths = {row["id"]: row["markdown_path"] for row in read_jsonl(tmp_path / "corpus.jsonl")}

    assert paths["z"] == "with-interactions/Same.md"
    assert paths["a"].startswith("with-interactions/Same — a")
    assert not (tmp_path / "with-interactions" / "Partial.md").exists()
    assert not backup.exists()


def test_next_sync_discards_abandoned_transaction_setup(tmp_path: Path) -> None:
    source = FakeReaderSource(
        metadata=[document("article", title="Article", tags={"keep": {}})],
        highlights=[],
        notes=[],
        details={"article": {"id": "article", "title": "Article", "content": "Body.", "notes": ""}},
    )
    preparing = tmp_path / ".corpus.jsonl.preparing.interrupted"
    preparing.mkdir()
    (preparing / "transaction.json").write_text("partial", encoding="utf-8")

    build_corpus(source, tmp_path)

    assert (tmp_path / "corpus.jsonl").is_file()
    assert (tmp_path / "with-interactions" / "Article.md").is_file()
    assert not preparing.exists()


def test_orphaned_backfill_directory_without_a_manifest_can_be_replaced(tmp_path: Path) -> None:
    backfill_dir = tmp_path / "backfill"
    backfill_dir.mkdir()
    (backfill_dir / "Partial.md").write_text("Incomplete publication.\n", encoding="utf-8")
    source = FakeReaderSource(
        metadata=[document("backfill", title="Backfill", tags={"backfill": {}})],
        highlights=[],
        notes=[],
        details={"backfill": {"id": "backfill", "title": "Backfill", "content": "Body.", "notes": ""}},
    )

    build_backfill_corpus(source, tmp_path)

    assert (tmp_path / "backfill.jsonl").is_file()
    assert (tmp_path / "backfill" / "Backfill.md").is_file()
    assert not (tmp_path / "backfill" / "Partial.md").exists()
