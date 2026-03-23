"""Tests for Stage 1 PDF validation and page counting."""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess

import pytest

from docdown.stages.split import PdfSplitError, PdfValidationError, split_pdf, validate_pdf


def _cp(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["qpdf"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_validate_pdf_valid_input_logs_page_count_and_size(tmp_path, monkeypatch, caplog):
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\ncontent")

    responses = iter(
        [
            _cp(0, stdout="File is not encrypted"),
            _cp(0, stdout="checking passed"),
            _cp(0, stdout="12\n"),
        ]
    )

    def _fake_run(command, capture_output, text, check):
        return next(responses)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)
    test_logger = logging.getLogger("tests.split")

    with caplog.at_level(logging.INFO, logger="tests.split"):
        result = validate_pdf(input_pdf, logger=test_logger)

    assert result.page_count == 12
    assert result.file_size_bytes == input_pdf.stat().st_size
    assert "Validated PDF: pages=12" in caplog.text


def test_validate_pdf_missing_file_raises_clear_error(tmp_path):
    missing = tmp_path / "missing.pdf"

    with pytest.raises(PdfValidationError, match="Input PDF not found"):
        validate_pdf(missing)


def test_validate_pdf_corrupted_file_raises_with_qpdf_diagnostics(tmp_path, monkeypatch):
    input_pdf = tmp_path / "broken.pdf"
    input_pdf.write_bytes(b"not a real pdf")

    responses = iter(
        [
            _cp(0, stdout="File is not encrypted"),
            _cp(2, stderr="file is damaged"),
        ]
    )

    def _fake_run(command, capture_output, text, check):
        return next(responses)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    with pytest.raises(PdfValidationError, match="Invalid or corrupted PDF: file is damaged"):
        validate_pdf(input_pdf)


def test_validate_pdf_encrypted_without_password_aborts(tmp_path, monkeypatch):
    input_pdf = tmp_path / "secret.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    def _fake_run(command, capture_output, text, check):
        return _cp(0, stdout="File is encrypted")

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    with pytest.raises(PdfValidationError, match="requires a password"):
        validate_pdf(input_pdf, password=None)


def test_validate_pdf_encrypted_with_empty_password_is_allowed(tmp_path, monkeypatch):
    input_pdf = tmp_path / "secret.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    responses = iter(
        [
            _cp(0, stdout="File is encrypted"),
            _cp(0, stdout="checking passed"),
            _cp(0, stdout="3\n"),
        ]
    )
    seen_commands: list[list[str]] = []

    def _fake_run(command, capture_output, text, check):
        seen_commands.append(command)
        return next(responses)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    result = validate_pdf(input_pdf, password="")

    assert result.page_count == 3
    assert any(
        any(arg.startswith("--password-file=") or arg == "--password=" for arg in cmd)
        for cmd in seen_commands
    )


def test_validate_pdf_page_count_parse_failure_raises_clear_error(tmp_path, monkeypatch):
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    responses = iter(
        [
            _cp(0, stdout="File is not encrypted"),
            _cp(0, stdout="checking passed"),
            _cp(0, stdout="not-a-number\n"),
        ]
    )

    def _fake_run(command, capture_output, text, check):
        return next(responses)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    with pytest.raises(PdfValidationError, match="Unexpected qpdf --show-npages output"):
        validate_pdf(input_pdf)


def test_validate_pdf_redacts_password_in_qpdf_execution_error(tmp_path, monkeypatch):
    input_pdf = tmp_path / "secret.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    def _raise_oserror(command, capture_output, text, check):
        raise OSError("qpdf not found")

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _raise_oserror)

    with pytest.raises(PdfValidationError) as exc_info:
        validate_pdf(input_pdf, password="top-secret")

    error_text = str(exc_info.value)
    assert "top-secret" not in error_text
    assert "--password-file=" in error_text or "--password=***" in error_text


def test_validate_pdf_logs_redacted_qpdf_commands(tmp_path, monkeypatch):
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\ncontent")

    responses = iter(
        [
            _cp(0, stdout="File is not encrypted"),
            _cp(0, stdout="checking passed"),
            _cp(0, stdout="7\n"),
        ]
    )
    logged_commands: list[str] = []

    def _fake_run(command, capture_output, text, check):
        return next(responses)

    def _capture_tool_command(command, chunk_number=None):
        logged_commands.append(str(command))

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)
    monkeypatch.setattr("docdown.stages.split.log_tool_command", _capture_tool_command)

    validate_pdf(input_pdf, password="super-secret")

    assert len(logged_commands) == 3
    assert all("--password-file=" in cmd or "--password=***" in cmd for cmd in logged_commands)
    assert all("super-secret" not in cmd for cmd in logged_commands)


def test_split_pdf_single_chunk_when_total_pages_below_chunk_size(tmp_path, monkeypatch):
    input_pdf = tmp_path / "input.pdf"
    chunks_dir = tmp_path / "chunks"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    def _fake_run(command, capture_output, text, check):
        if "--pages" in command:
            Path(command[-1]).write_bytes(b"%PDF-1.4 chunk\n")
            return _cp(0, stdout="split ok")
        if "--check" in command:
            return _cp(0, stdout="check ok")
        return _cp(0)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    result = split_pdf(input_pdf, chunks_dir, chunk_size=50, total_pages=1)

    assert result.chunk_count == 1
    assert result.chunk_paths == [chunks_dir / "chunk-0001.pdf"]
    assert (chunks_dir / "chunk-0001.pdf").exists()


def test_split_pdf_multi_chunk_ranges_and_naming(tmp_path, monkeypatch):
    input_pdf = tmp_path / "input.pdf"
    chunks_dir = tmp_path / "chunks"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    page_ranges: list[str] = []

    def _fake_run(command, capture_output, text, check):
        if "--pages" in command:
            range_arg = command[command.index(".") + 1]
            page_ranges.append(range_arg)
            Path(command[-1]).write_bytes(b"%PDF-1.4 chunk\n")
            return _cp(0, stdout="split ok")
        if "--check" in command:
            return _cp(0, stdout="check ok")
        return _cp(0)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    result = split_pdf(input_pdf, chunks_dir, chunk_size=3, total_pages=8)

    assert result.chunk_count == 3
    assert page_ranges == ["1-3", "4-6", "7-8"]
    assert result.chunk_paths == [
        chunks_dir / "chunk-0001.pdf",
        chunks_dir / "chunk-0002.pdf",
        chunks_dir / "chunk-0003.pdf",
    ]


def test_split_pdf_raises_when_chunk_check_fails(tmp_path, monkeypatch):
    input_pdf = tmp_path / "input.pdf"
    chunks_dir = tmp_path / "chunks"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    def _fake_run(command, capture_output, text, check):
        if "--pages" in command:
            Path(command[-1]).write_bytes(b"%PDF-1.4 chunk\n")
            return _cp(0, stdout="split ok")
        if "--check" in command:
            return _cp(2, stderr="chunk broken")
        return _cp(0)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    with pytest.raises(PdfSplitError, match="unreadable"):
        split_pdf(input_pdf, chunks_dir, chunk_size=2, total_pages=2)


def test_split_pdf_rejects_invalid_chunk_size(tmp_path):
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(PdfSplitError, match="chunk_size must be at least 1"):
        split_pdf(input_pdf, tmp_path / "chunks", chunk_size=0, total_pages=10)


def test_split_pdf_ignores_stale_chunk_files_in_directory(tmp_path, monkeypatch):
    input_pdf = tmp_path / "input.pdf"
    chunks_dir = tmp_path / "chunks"
    input_pdf.write_bytes(b"%PDF-1.4\n")
    chunks_dir.mkdir(parents=True, exist_ok=True)
    stale_chunk = chunks_dir / "chunk-9999.pdf"
    stale_chunk.write_bytes(b"stale")

    def _fake_run(command, capture_output, text, check):
        if "--pages" in command:
            Path(command[-1]).write_bytes(b"%PDF-1.4 chunk\n")
            return _cp(0, stdout="split ok")
        if "--check" in command:
            return _cp(0, stdout="check ok")
        return _cp(0)

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _fake_run)

    result = split_pdf(input_pdf, chunks_dir, chunk_size=2, total_pages=3)

    assert result.chunk_count == 2
    assert [path.name for path in result.chunk_paths] == ["chunk-0001.pdf", "chunk-0002.pdf"]
    assert stale_chunk.exists()


def test_split_pdf_rejects_chunk_counts_above_fixed_width_limit(tmp_path):
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    with pytest.raises(PdfSplitError, match="exceeding fixed 4-digit naming limit"):
        split_pdf(input_pdf, tmp_path / "chunks", chunk_size=1, total_pages=10000)


def test_split_pdf_wraps_qpdf_execution_errors_as_split_error(tmp_path, monkeypatch):
    input_pdf = tmp_path / "input.pdf"
    input_pdf.write_bytes(b"%PDF-1.4\n")

    def _raise_oserror(command, capture_output, text, check):
        raise OSError("qpdf not found")

    monkeypatch.setattr("docdown.stages.split.subprocess.run", _raise_oserror)

    with pytest.raises(PdfSplitError, match="Failed to execute split command"):
        split_pdf(input_pdf, tmp_path / "chunks", chunk_size=2, total_pages=2)
