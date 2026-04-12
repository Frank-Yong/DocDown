"""Tests for Stage 8.2 final output validation."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import Mock

from docdown.stages.chunk_validation import ChunkResult, ChunkValidationResult
from docdown.stages.final_validation import validate_final_output


def _chunk_result(
    chunk_number: int,
    markdown_path: Path,
    *,
    success: bool = True,
    error: str | None = None,
    validation_errors: tuple[str, ...] = (),
) -> ChunkResult:
    validation = ChunkValidationResult(
        valid=not validation_errors,
        errors=validation_errors,
        warnings=(),
    )
    return ChunkResult(
        chunk_number=chunk_number,
        success=success,
        markdown_path=markdown_path,
        error=error,
        validation=validation,
    )


def test_validate_final_output_warns_when_final_is_too_small(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 10000)
    final_md = tmp_path / "final.md"
    final_md.write_text("- [Section](#section)\n\n# Section\n", encoding="utf-8")

    chunk_path = tmp_path / "chunk-0001.md"
    chunk_path.write_text("# Heading\n\nBody\n", encoding="utf-8")
    chunk_results = [_chunk_result(1, chunk_path)]

    result = validate_final_output(
        final_md,
        source_pdf,
        chunk_results,
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert result.valid is True
    assert any("Final output ratio" in warning for warning in result.warnings)


def test_validate_final_output_fails_when_empty_chunk_failures_exceed_threshold(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    final_md = tmp_path / "final.md"
    final_md.write_text("- [Section](#section)\n\n# Section\n", encoding="utf-8")

    chunk_path = tmp_path / "chunk-0001.md"
    chunk_path.write_text("# Heading\n\nBody\n", encoding="utf-8")
    chunk_results = [
        _chunk_result(1, chunk_path, success=False, error="empty", validation_errors=("Empty output",)),
        _chunk_result(2, chunk_path, success=True),
    ]

    result = validate_final_output(
        final_md,
        source_pdf,
        chunk_results,
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert result.valid is False
    assert result.errors == ("1 empty chunks failed validation (max allowed: 0).",)


def test_validate_final_output_warns_when_toc_links_missing_near_top(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    final_md = tmp_path / "final.md"
    final_md.write_text("# Heading\n\nNo TOC links here.\n", encoding="utf-8")

    chunk_path = tmp_path / "chunk-0001.md"
    chunk_path.write_text("# Heading\n\nBody\n", encoding="utf-8")

    result = validate_final_output(
        final_md,
        source_pdf,
        [_chunk_result(1, chunk_path)],
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert result.valid is True
    assert "Final output appears to be missing a TOC section near the top" in result.warnings


def test_validate_final_output_does_not_treat_external_link_list_as_toc(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    final_md = tmp_path / "final.md"
    final_md.write_text(
        "## Resources\n\n- [Website](https://example.com)\n- [Repo](https://github.com/example/repo)\n\n# Heading\n",
        encoding="utf-8",
    )

    chunk_path = tmp_path / "chunk-0001.md"
    chunk_path.write_text("# Heading\n\nBody\n", encoding="utf-8")

    result = validate_final_output(
        final_md,
        source_pdf,
        [_chunk_result(1, chunk_path)],
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert result.valid is True
    assert "Final output appears to be missing a TOC section near the top" in result.warnings


def test_validate_final_output_accepts_star_bullet_anchor_toc(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    final_md = tmp_path / "final.md"
    final_md.write_text(
        "## Table of Contents\n\n* [Intro](#intro)\n\n# Intro\n",
        encoding="utf-8",
    )

    chunk_path = tmp_path / "chunk-0001.md"
    chunk_path.write_text("# Intro\n\nBody\n", encoding="utf-8")

    result = validate_final_output(
        final_md,
        source_pdf,
        [_chunk_result(1, chunk_path)],
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert result.valid is True
    assert "Final output appears to be missing a TOC section near the top" not in result.warnings


def test_validate_final_output_flags_duplicate_boundary_paragraph(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    final_md = tmp_path / "final.md"
    final_md.write_text("- [Section](#section)\n\n# Section\n", encoding="utf-8")

    repeated_paragraph = " ".join(["word"] * 51)
    chunk_1 = tmp_path / "chunk-0001.md"
    chunk_2 = tmp_path / "chunk-0002.md"
    chunk_1.write_text(f"# Heading\n\nIntro\n\n{repeated_paragraph}\n", encoding="utf-8")
    chunk_2.write_text(f"{repeated_paragraph}\n\nMore text\n", encoding="utf-8")

    result = validate_final_output(
        final_md,
        source_pdf,
        [_chunk_result(1, chunk_1), _chunk_result(2, chunk_2)],
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert result.valid is True
    assert result.duplicate_boundary_count == 1
    assert any("Potential duplicate boundary paragraph" in warning for warning in result.warnings)


def test_validate_final_output_reads_each_chunk_once_for_boundary_checks(tmp_path, monkeypatch):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    final_md = tmp_path / "final.md"
    final_md.write_text("- [Section](#section)\n\n# Section\n", encoding="utf-8")

    repeated_paragraph = " ".join(["word"] * 51)
    chunk_1 = tmp_path / "chunk-0001.md"
    chunk_2 = tmp_path / "chunk-0002.md"
    chunk_3 = tmp_path / "chunk-0003.md"
    chunk_1.write_text(f"# H1\n\n{repeated_paragraph}\n", encoding="utf-8")
    chunk_2.write_text(f"# H2\n\n{repeated_paragraph}\n", encoding="utf-8")
    chunk_3.write_text("# H3\n\nunique words only\n", encoding="utf-8")

    read_counts: dict[Path, int] = {chunk_1: 0, chunk_2: 0, chunk_3: 0}
    original_read_text = Path.read_text

    def _count_reads(self, *args, **kwargs):
        if self in read_counts:
            read_counts[self] += 1
        return original_read_text(self, *args, **kwargs)

    monkeypatch.setattr(Path, "read_text", _count_reads)

    validate_final_output(
        final_md,
        source_pdf,
        [_chunk_result(1, chunk_1), _chunk_result(2, chunk_2), _chunk_result(3, chunk_3)],
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert read_counts[chunk_1] == 1
    assert read_counts[chunk_2] == 1
    assert read_counts[chunk_3] == 1


def test_validate_final_output_skips_duplicate_check_across_missing_chunk_numbers(tmp_path):
    source_pdf = tmp_path / "source.pdf"
    source_pdf.write_bytes(b"%PDF-1.4\n" + b"x" * 100)
    final_md = tmp_path / "final.md"
    final_md.write_text("- [Section](#section)\n\n# Section\n", encoding="utf-8")

    repeated_paragraph = " ".join(["word"] * 51)
    chunk_1 = tmp_path / "chunk-0001.md"
    chunk_3 = tmp_path / "chunk-0003.md"
    chunk_1.write_text(f"# H1\n\n{repeated_paragraph}\n", encoding="utf-8")
    chunk_3.write_text(f"{repeated_paragraph}\n\n# H3\n", encoding="utf-8")

    result = validate_final_output(
        final_md,
        source_pdf,
        [_chunk_result(1, chunk_1), _chunk_result(3, chunk_3)],
        max_empty_chunks=0,
        logger=Mock(),
    )

    assert result.valid is True
    assert result.duplicate_boundary_count == 0
    assert not any("Potential duplicate boundary paragraph" in warning for warning in result.warnings)
