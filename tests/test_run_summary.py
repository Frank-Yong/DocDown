"""Tests for Stage 8.3 run summary generation."""

from __future__ import annotations

from pathlib import Path

from docdown.stages.chunk_validation import ChunkResult, ChunkValidationResult
from docdown.stages.run_summary import RunSummaryContext, append_run_summary, generate_run_summary


def _chunk_result(chunk_number: int, *, success: bool, error: str | None) -> ChunkResult:
    return ChunkResult(
        chunk_number=chunk_number,
        success=success,
        markdown_path=Path(f"chunk-{chunk_number:04d}.md"),
        error=error,
        validation=ChunkValidationResult(valid=success, errors=(), warnings=()),
    )


def test_generate_run_summary_format_includes_required_fields():
    context = RunSummaryContext(
        input_path=Path("workdir/input/source.pdf"),
        input_size_bytes=350_000_000,
        total_pages=1847,
        total_chunks=37,
        successful_chunks=36,
        failed_chunks=(
            _chunk_result(23, success=False, error="GROBID timeout + pdfminer encoding error"),
        ),
        tables_found=14,
        output_path=Path("workdir/final.md"),
        output_size_bytes=4_200_000,
        duration_seconds=754,
        warning_count=2,
    )

    summary = generate_run_summary(context)

    assert summary.startswith("DocDown Run Summary\n-------------------\n")
    assert "Input:          source.pdf (333.8 MB, 1847 pages)" in summary
    assert "Chunks:         37" in summary
    assert "Successful:     36" in summary
    assert "Failed:         1 (chunk-0023: GROBID timeout + pdfminer encoding error)" in summary
    assert "Tables found:   14" in summary
    assert "Output:         final.md (4.0 MB)" in summary
    assert "Duration:       12m 34s" in summary
    assert "Warnings:       2 (see run.log)" in summary


def test_append_run_summary_writes_to_log(tmp_path):
    run_log = tmp_path / "run.log"
    run_log.write_text("existing\n", encoding="utf-8")

    append_run_summary(run_log, "DocDown Run Summary\nline")

    content = run_log.read_text(encoding="utf-8")
    assert "existing\n" in content
    assert "DocDown Run Summary\nline\n" in content
