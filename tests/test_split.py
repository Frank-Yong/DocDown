"""Tests for Stage 1 PDF validation and page counting."""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess

import pytest

from docdown.stages.split import PdfValidationError, validate_pdf


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
