"""Tests for the CLI entry point."""

from click.testing import CliRunner
from docdown import __version__
from docdown.cli import main


def test_cli_shows_version(tmp_path):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])
    assert result.exit_code == 0
    assert f"DocDown v{__version__}" in result.output


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
