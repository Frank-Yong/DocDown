"""Tests for Stage 4.2 markdown cleanup."""

from __future__ import annotations

from pathlib import Path

from docdown.stages.cleanup import (
    cleanup_markdown_file,
    cleanup_markdown_text,
    collapse_blank_lines,
    normalize_headings,
    remove_repeated_header_footer_lines,
    strip_trailing_whitespace,
)


def test_collapse_blank_lines_reduces_runs_over_two():
    text = "line1\n\n\n\nline2\n"

    cleaned = collapse_blank_lines(text)

    assert cleaned == "line1\n\nline2\n"


def test_normalize_headings_demotes_when_h1_present():
    text = "# Title\n## Section\n### Subsection\n"

    cleaned = normalize_headings(text)

    assert cleaned == "## Title\n### Section\n#### Subsection\n"


def test_normalize_headings_no_change_without_h1():
    text = "## Section\n### Subsection\n"

    cleaned = normalize_headings(text)

    assert cleaned == text


def test_remove_repeated_header_footer_lines_removes_majority_edges():
    text = (
        "Doc Header\n"
        "Page 1 intro\n"
        "Body A\n"
        "Doc Footer\n"
        "\f"
        "Doc Header\n"
        "Page 2 intro\n"
        "Body B\n"
        "Doc Footer\n"
        "\f"
        "Doc Header\n"
        "Page 3 intro\n"
        "Body C\n"
        "Doc Footer\n"
    )

    cleaned = remove_repeated_header_footer_lines(text)

    assert "Doc Header" not in cleaned
    assert "Doc Footer" not in cleaned
    assert "Body A" in cleaned and "Body B" in cleaned and "Body C" in cleaned


def test_strip_trailing_whitespace_removes_line_suffix_spaces_tabs():
    text = "alpha  \n beta\t\ncharlie\n"

    cleaned = strip_trailing_whitespace(text)

    assert cleaned == "alpha\n beta\ncharlie\n"


def test_cleanup_markdown_file_overwrites_in_place(tmp_path):
    path = tmp_path / "chunk-0001.md"
    path.write_text("# Heading\n\n\nline  \n", encoding="utf-8")

    cleanup_markdown_file(path)

    assert path.read_text(encoding="utf-8") == "## Heading\n\nline\n"


def test_cleanup_markdown_text_is_idempotent():
    text = "# Heading\n\n\nDoc Header\nBody\nDoc Footer\n\f\nDoc Header\nBody 2\nDoc Footer\n"

    once = cleanup_markdown_text(text)
    twice = cleanup_markdown_text(once)

    assert twice == once
