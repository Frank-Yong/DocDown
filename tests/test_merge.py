"""Tests for merging and TOC generation."""

from __future__ import annotations

from unittest.mock import Mock

from docdown.stages.merge import merge_chunks


def test_merge_chunks_concatenates_in_numeric_order(tmp_path):
	markdown_dir = tmp_path / "markdown"
	markdown_dir.mkdir()
	(markdown_dir / "chunk-0001.md").write_text("first", encoding="utf-8")
	(markdown_dir / "chunk-0002.md").write_text("second", encoding="utf-8")
	(markdown_dir / "chunk-0003.md").write_text("third", encoding="utf-8")

	output_path = tmp_path / "merged.md"
	merge_chunks(markdown_dir, output_path, 3)

	assert output_path.read_text(encoding="utf-8") == "first\n\n---\n\nsecond\n\n---\n\nthird"


def test_merge_chunks_inserts_horizontal_rule_between_all_chunks(tmp_path):
	markdown_dir = tmp_path / "markdown"
	markdown_dir.mkdir()
	(markdown_dir / "chunk-0001.md").write_text("a", encoding="utf-8")
	(markdown_dir / "chunk-0002.md").write_text("b", encoding="utf-8")
	(markdown_dir / "chunk-0003.md").write_text("c", encoding="utf-8")

	output_path = tmp_path / "merged.md"
	merge_chunks(markdown_dir, output_path, 3)

	merged = output_path.read_text(encoding="utf-8")
	assert merged.count("\n\n---\n\n") == 2


def test_merge_chunks_writes_placeholder_for_missing_or_empty_chunks(tmp_path):
	markdown_dir = tmp_path / "markdown"
	markdown_dir.mkdir()
	(markdown_dir / "chunk-0001.md").write_text("ok", encoding="utf-8")
	(markdown_dir / "chunk-0003.md").write_text("", encoding="utf-8")

	output_path = tmp_path / "merged.md"
	merge_chunks(markdown_dir, output_path, 3)

	merged = output_path.read_text(encoding="utf-8")
	assert "ok" in merged
	assert "<!-- chunk-0002: extraction failed -->" in merged
	assert "<!-- chunk-0003: extraction failed -->" in merged


def test_merge_chunks_logs_line_count_and_file_size(tmp_path):
	markdown_dir = tmp_path / "markdown"
	markdown_dir.mkdir()
	(markdown_dir / "chunk-0001.md").write_text("line1\nline2\n", encoding="utf-8")

	output_path = tmp_path / "merged.md"
	logger = Mock()
	merge_chunks(markdown_dir, output_path, 1, logger=logger)

	assert output_path.exists()
	assert output_path.stat().st_size > 0
	logger.info.assert_called_once()
	logged_message = logger.info.call_args.args[0]
	assert "Merged markdown output: lines=" in logged_message
	assert "size_bytes=" in logged_message
