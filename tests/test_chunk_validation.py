"""Tests for Stage 8.1 chunk validation."""

from __future__ import annotations

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
