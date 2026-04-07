"""Tests for Stage 6.2 TOC generation."""

from __future__ import annotations

import subprocess
from pathlib import Path
from unittest.mock import Mock

import pytest

from docdown.stages.toc import TocError, _count_headings_for_toc, generate_toc, log_heading_diagnostics


def test_generate_toc_runs_pandoc_and_logs_entry_count(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n\n## Intro\n\n### Details\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        assert "--toc" in command
        assert "--toc-depth=3" in command
        final.write_text(
            "## Table of Contents\n\n- [Title](#title)\n  - [Intro](#intro)\n\n# Title\n",
            encoding="utf-8",
        )
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    output = generate_toc(merged, final, toc_depth=3, logger=logger)

    assert output == final
    assert final.exists()
    assert "Table of Contents" in final.read_text(encoding="utf-8")
    logger.info.assert_called_once()
    assert logger.info.call_args.args[1] == "pandoc"
    assert logger.info.call_args.args[2] == 2


def test_generate_toc_copies_merged_when_pandoc_fails(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n\n## Intro\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        return subprocess.CompletedProcess(command, 1, "", "conversion failed")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    output = generate_toc(merged, final, logger=logger)

    assert output == final
    rendered = final.read_text(encoding="utf-8")
    assert rendered.startswith("## Table of Contents")
    assert "- [Title](#title)" in rendered
    assert "## Intro" in rendered
    logger.warning.assert_called_once()
    assert logger.info.call_count == 1


def test_generate_toc_inserts_python_fallback_when_pandoc_output_has_no_toc(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n\n## Intro\n\n### Details\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        final.write_text("# Title\n\n## Intro\n\n### Details\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    output = generate_toc(merged, final, toc_depth=3, logger=logger)

    assert output == final
    rendered = final.read_text(encoding="utf-8")
    assert rendered.startswith("## Table of Contents")
    assert "- [Title](#title)" in rendered
    assert "  - [Intro](#intro)" in rendered
    assert "    - [Details](#details)" in rendered
    assert logger.info.call_args.args[1] == "python-fallback"


def test_generate_toc_accepts_single_entry_pandoc_toc(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        final.write_text("## Table of Contents\n\n- [Title](#title)\n\n# Title\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    generate_toc(merged, final, toc_depth=3, logger=logger)

    rendered = final.read_text(encoding="utf-8")
    assert rendered.count("## Table of Contents") == 1
    assert logger.info.call_args.args[1] == "pandoc"


def test_generate_toc_accepts_div_toc_marker_without_duplicate_insertion(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        final.write_text("<div id=\"TOC\"></div>\n\n- [Title](#title)\n\n# Title\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    generate_toc(merged, final, toc_depth=3, logger=logger)

    rendered = final.read_text(encoding="utf-8")
    assert rendered.startswith("<div id=\"TOC\"></div>")
    assert "## Table of Contents" not in rendered
    assert logger.info.call_args.args[1] == "pandoc"
    assert logger.info.call_args.args[2] == 1


def test_generate_toc_logs_zero_emitted_entries_when_pandoc_toc_is_not_visible(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n\n## Intro\n\n### Details\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        final.write_text("# Title\n\n## Intro\n\n### Details\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    generate_toc(merged, final, toc_depth=3, logger=logger)

    assert logger.info.call_args.args[1] == "python-fallback"
    assert logger.info.call_args.args[2] == 3


def test_generate_toc_does_not_treat_single_non_marker_anchor_link_as_visible_toc(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n\n## Intro\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        final.write_text("- [Jump to intro](#intro)\n\n# Title\n\n## Intro\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    generate_toc(merged, final, toc_depth=3, logger=logger)

    rendered = final.read_text(encoding="utf-8")
    assert rendered.startswith("## Table of Contents")
    assert logger.info.call_args.args[1] == "python-fallback"


def test_generate_toc_rejects_invalid_depth(tmp_path):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n", encoding="utf-8")

    with pytest.raises(TocError, match="toc_depth must be between 1 and 6"):
        generate_toc(merged, tmp_path / "final.md", toc_depth=0)


def test_count_headings_for_toc_respects_depth_and_ignores_fenced_blocks():
    markdown = "\n".join(
        [
            "# One",
            "## Two",
            "### Three",
            "#### Four",
            "```",
            "# Not A Heading",
            "```",
        ]
    )

    assert _count_headings_for_toc(markdown, 3) == 3
    assert _count_headings_for_toc(markdown, 4) == 4


def test_count_headings_for_toc_accepts_commonmark_indent_rules():
    markdown = "\n".join(
        [
            "   ## Indented Heading",
            "    ### Too Indented",
            "   ```",
            "   ## Inside Fence",
            "   ```",
            "~~~",
            "## Also Inside Fence",
            "~~~",
            " # OneSpaceHeading",
        ]
    )

    assert _count_headings_for_toc(markdown, 3) == 2


def test_python_toc_fallback_uses_unique_github_anchors_for_duplicates(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("## Intro\n\n## Intro\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        final.write_text("## Intro\n\n## Intro\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    generate_toc(merged, final, toc_depth=3, logger=Mock())
    rendered = final.read_text(encoding="utf-8")
    assert "- [Intro](#intro)" in rendered
    assert "- [Intro](#intro-1)" in rendered


def test_python_toc_fallback_preserves_unicode_github_anchors(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("## Café\n\n## Überblick\n\n## 東京\n\n## Café\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        final.write_text("## Café\n\n## Überblick\n\n## 東京\n\n## Café\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    generate_toc(merged, final, toc_depth=3, logger=Mock())
    rendered = final.read_text(encoding="utf-8")
    assert "- [Café](#café)" in rendered
    assert "- [Überblick](#überblick)" in rendered
    assert "- [東京](#東京)" in rendered
    assert "- [Café](#café-1)" in rendered


def test_log_heading_diagnostics_reports_chunk_and_merged_heading_stats(tmp_path):
    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()
    (markdown_dir / "chunk-0001.md").write_text("# A\n\n## B\n", encoding="utf-8")
    (markdown_dir / "chunk-0002.md").write_text("no headings\n", encoding="utf-8")

    merged = tmp_path / "merged.md"
    merged.write_text("# A\n\n## B\n\n### C\n", encoding="utf-8")

    logger = Mock()
    log_heading_diagnostics(markdown_dir, merged, logger=logger)

    assert logger.info.call_count == 2
    first = logger.info.call_args_list[0].args
    assert first[0].startswith("Heading diagnostics (chunks):")
    assert first[1] == 2
    assert first[2] == 1
    assert first[3] == 1
    assert first[4] == 0
    assert first[5] == "h1:1,h2:1"

    second = logger.info.call_args_list[1].args
    assert second[0].startswith("Heading diagnostics (merged):")
    assert second[1] == 3
    assert second[2] == "h1:1,h2:1,h3:1"


def test_log_heading_diagnostics_includes_unreadable_chunk_count(tmp_path, monkeypatch):
    markdown_dir = tmp_path / "markdown"
    markdown_dir.mkdir()
    (markdown_dir / "chunk-0001.md").write_text("# A\n", encoding="utf-8")
    (markdown_dir / "chunk-0002.md").write_text("## B\n", encoding="utf-8")

    merged = tmp_path / "merged.md"
    merged.write_text("# A\n\n## B\n", encoding="utf-8")

    original_open = Path.open

    def _fake_open(self, *args, **kwargs):
        if self.name == "chunk-0002.md":
            raise OSError("permission denied")
        return original_open(self, *args, **kwargs)

    monkeypatch.setattr("docdown.stages.toc.Path.open", _fake_open)

    logger = Mock()
    log_heading_diagnostics(markdown_dir, merged, logger=logger)

    first = logger.info.call_args_list[0].args
    assert first[0].startswith("Heading diagnostics (chunks):")
    assert first[1] == 2
    assert first[2] == 1
    assert first[3] == 0
    assert first[4] == 1
    assert first[5] == "h1:1"
    logger.warning.assert_called_once()
