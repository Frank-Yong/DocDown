"""Tests for Stage 4.2 markdown cleanup."""

from __future__ import annotations

from docdown.stages.cleanup import (
    cleanup_markdown_file,
    cleanup_markdown_text,
    collapse_blank_lines,
    normalize_headings,
    reconstruct_headings,
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


def test_remove_repeated_header_footer_lines_ignores_empty_blocks_for_threshold():
    text = (
        "\f"
        "Doc Header\n"
        "Page 1 intro\n"
        "Body A\n"
        "Doc Footer\n"
        "\f\f"
        "Doc Header\n"
        "Page 2 intro\n"
        "Body B\n"
        "Doc Footer\n"
        "\f"
    )

    cleaned = remove_repeated_header_footer_lines(text)

    assert "Doc Header" not in cleaned
    assert "Doc Footer" not in cleaned
    assert "Body A" in cleaned and "Body B" in cleaned


def test_remove_repeated_header_footer_lines_keeps_matching_body_lines():
    text = (
        "Doc Header\n"
        "Top A\n"
        "Doc Header\n"
        "Bottom A\n"
        "Doc Footer\n"
        "\f"
        "Doc Header\n"
        "Top B\n"
        "Doc Header\n"
        "Bottom B\n"
        "Doc Footer\n"
    )

    cleaned = remove_repeated_header_footer_lines(text)

    # Edge header/footer lines are removed per block.
    assert cleaned.split("\f")[0].split("\n")[0] != "Doc Header"
    assert cleaned.split("\f")[1].split("\n")[-1] != "Doc Footer"
    # Interior lines with the same text remain untouched.
    assert "Top A\nDoc Header\nBottom A" in cleaned
    assert "Top B\nDoc Header\nBottom B" in cleaned


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


def test_reconstruct_headings_promotes_numbered_lines_by_default():
    text = "1.2 Scope\nThis line is body text.\n"

    cleaned = cleanup_markdown_text(text)

    assert cleaned.startswith("## 1.2 Scope")
    assert "This line is body text." in cleaned


def test_reconstruct_headings_can_disable_numbered_heuristic():
    text = "1.2 Scope\n"

    cleaned = cleanup_markdown_text(
        text,
        heuristic_numbered_headings=False,
        heuristic_titlecase_headings=False,
        heuristic_allcaps_headings=False,
    )

    assert cleaned == text


def test_reconstruct_headings_can_enable_titlecase_heuristic():
    text = "Project Administration\nregular body sentence should stay plain\n"

    cleaned = cleanup_markdown_text(
        text,
        heuristic_numbered_headings=False,
        heuristic_titlecase_headings=True,
        heuristic_allcaps_headings=False,
    )

    assert cleaned.startswith("## Project Administration")
    assert "regular body sentence should stay plain" in cleaned


def test_reconstruct_headings_can_enable_allcaps_heuristic():
    text = "SYSTEM DATABASE\n"

    cleaned = cleanup_markdown_text(
        text,
        heuristic_numbered_headings=False,
        heuristic_titlecase_headings=False,
        heuristic_allcaps_headings=True,
    )

    assert cleaned == "## SYSTEM DATABASE\n"


def test_reconstruct_headings_keeps_existing_markdown_constructs_unchanged():
    text = "- bullet item\nhttps://example.com\nA normal sentence.\n"

    cleaned = reconstruct_headings(
        text,
        heuristic_numbered_headings=True,
        heuristic_titlecase_headings=True,
        heuristic_allcaps_headings=True,
    )

    assert cleaned == text


def test_reconstruct_headings_skips_indented_code_block_lines():
    text = "    1.2 Scope\nRegular body line\n"

    cleaned = cleanup_markdown_text(text)

    assert cleaned.startswith("    1.2 Scope")
    assert "## 1.2 Scope" not in cleaned
