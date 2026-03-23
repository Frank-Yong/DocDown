"""Tests for the CLI entry point."""

from types import SimpleNamespace

from click.testing import CliRunner
from docdown import __version__
from docdown.cli import main
from docdown.stages.split import PdfValidationError


def test_cli_shows_version(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])
    assert result.exit_code == 0
    assert f"DocDown v{__version__}" in result.output
    assert "Input:" in result.output
    assert "Workdir:" in result.output

    # Startup summaries are also logged through stderr.
    assert f"DocDown v{__version__}" in result.stderr
    assert "Input:" in result.stderr
    assert "Workdir:" in result.stderr

    log_file = tmp_path / "out" / "run.log"
    assert log_file.exists()


def test_cli_rejects_file_path_for_workdir(tmp_path):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    workdir_file = tmp_path / "workdir.txt"
    workdir_file.write_text("not a directory", encoding="utf-8")

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(workdir_file)])

    assert result.exit_code != 0
    assert "--workdir" in result.output
    assert "Invalid value" in result.output


def test_cli_accepts_log_level_flag(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out"), "--log-level", "debug"])

    assert result.exit_code == 0


def test_cli_surfaces_pdf_validation_errors(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    def _raise_validation_error(*args, **kwargs):
        raise PdfValidationError("invalid pdf")

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        _raise_validation_error,
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])

    assert result.exit_code != 0
    assert "invalid pdf" in result.output
