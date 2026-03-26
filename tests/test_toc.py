"""Tests for Stage 6.2 TOC generation."""

from __future__ import annotations

import subprocess
from unittest.mock import Mock

import pytest

from docdown.stages.toc import TocError, _count_headings_for_toc, generate_toc


def test_generate_toc_runs_pandoc_and_logs_entry_count(tmp_path, monkeypatch):
    merged = tmp_path / "merged.md"
    merged.write_text("# Title\n\n## Intro\n\n### Details\n", encoding="utf-8")
    final = tmp_path / "final.md"

    def _fake_run(command, capture_output, text, check):
        assert "--toc" in command
        assert "--toc-depth=3" in command
        final.write_text("[TOC]\n\n- [Title](#title)\n", encoding="utf-8")
        return subprocess.CompletedProcess(command, 0, "", "")

    monkeypatch.setattr("docdown.stages.toc.subprocess.run", _fake_run)

    logger = Mock()
    output = generate_toc(merged, final, toc_depth=3, logger=logger)

    assert output == final
    assert final.exists()
    assert "[TOC]" in final.read_text(encoding="utf-8")
    logger.info.assert_called_once()
    assert logger.info.call_args.args[1] == 3


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
    assert final.read_text(encoding="utf-8") == merged.read_text(encoding="utf-8")
    logger.warning.assert_called_once()
    assert logger.info.call_count == 1


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
