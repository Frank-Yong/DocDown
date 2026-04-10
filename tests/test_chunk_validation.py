"""Tests for Stage 8.1 chunk validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from docdown.stages.chunk_validation import validate_chunk


def test_validate_chunk_fails_for_empty_output(tmp_path):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_text("", encoding="utf-8")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.01,
        expect_headings=True,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is False
    assert result.errors == ("Empty output",)


def test_validate_chunk_fails_for_invalid_utf8(tmp_path):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_bytes(b"\xff\xfe\x00")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.01,
        expect_headings=True,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is False
    assert result.errors == ("Invalid UTF-8 encoding",)


def test_validate_chunk_fails_for_whitespace_only_output(tmp_path):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_text("  \n\t\n", encoding="utf-8")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.01,
        expect_headings=True,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is False
    assert result.errors == ("Empty output",)


def test_validate_chunk_fails_when_markdown_stat_errors(tmp_path, monkeypatch):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_text("# Heading\n", encoding="utf-8")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)

    original_stat = Path.stat

    def _fake_stat(self):
        if self == md_path:
            raise OSError("permission denied")
        return original_stat(self)

    monkeypatch.setattr("pathlib.Path.stat", _fake_stat)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.01,
        expect_headings=True,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is False
    assert any("Failed reading markdown output metadata" in error for error in result.errors)


def test_validate_chunk_skips_ratio_when_pdf_stat_errors(tmp_path, monkeypatch):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_text("# Heading\n", encoding="utf-8")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)

    original_stat = Path.stat

    def _fake_stat(self):
        if self == pdf_path:
            raise OSError("permission denied")
        return original_stat(self)

    monkeypatch.setattr("pathlib.Path.stat", _fake_stat)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.5,
        expect_headings=False,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is True
    assert result.errors == ()
    assert result.warnings == ()


def test_validate_chunk_warns_for_small_output_ratio(tmp_path):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_text("# Heading\n", encoding="utf-8")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 5000)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.5,
        expect_headings=True,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is True
    assert result.errors == ()
    assert any("Output ratio" in warning for warning in result.warnings)


def test_validate_chunk_warns_when_headings_expected_but_missing(tmp_path):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_text("plain body text\n", encoding="utf-8")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.01,
        expect_headings=True,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is True
    assert result.errors == ()
    assert "No headings detected" in result.warnings


def test_validate_chunk_accepts_heading_with_leading_spaces(tmp_path):
    md_path = tmp_path / "chunk-0001.md"
    md_path.write_text("   ## Indented heading\nbody text\n", encoding="utf-8")
    pdf_path = tmp_path / "chunk-0001.pdf"
    pdf_path.write_bytes(b"%PDF-1.4\n" + b"x" * 200)

    result = validate_chunk(
        md_path,
        pdf_path,
        min_output_ratio=0.01,
        expect_headings=True,
        logger=Mock(),
        chunk_number=1,
    )

    assert result.valid is True
    assert result.errors == ()
    assert "No headings detected" not in result.warnings
