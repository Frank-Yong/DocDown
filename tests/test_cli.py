"""Tests for the CLI entry point."""

from pathlib import Path
from types import SimpleNamespace

from click.testing import CliRunner
from docdown import __version__
from docdown.cli import main
from docdown.stages.convert import PandocError
from docdown.stages.merge import MergeError
from docdown.stages.split import PdfSplitError
from docdown.stages.split import PdfValidationError
from docdown.stages.toc import TocError


def test_cli_shows_version(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
    extracted_path = tmp_path / "out" / "extracted" / "chunk-0001.xml"

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [
            SimpleNamespace(
                chunk_number=1,
                success=True,
                output_path=extracted_path,
            )
        ],
    )
    monkeypatch.setattr("docdown.cli.ensure_pandoc_available", lambda *args, **kwargs: None)

    def _fake_convert(input_path, output_path, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("# ok", encoding="utf-8")
        return Path(output_path)

    monkeypatch.setattr("docdown.cli.convert_to_markdown", _fake_convert)
    monkeypatch.setattr("docdown.cli.generate_toc", lambda *args, **kwargs: Path(args[1]))

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
    extracted_path = tmp_path / "out" / "extracted" / "chunk-0001.xml"

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [
            SimpleNamespace(
                chunk_number=1,
                success=True,
                output_path=extracted_path,
            )
        ],
    )
    monkeypatch.setattr("docdown.cli.ensure_pandoc_available", lambda *args, **kwargs: None)

    def _fake_convert(input_path, output_path, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("# ok", encoding="utf-8")
        return Path(output_path)

    monkeypatch.setattr("docdown.cli.convert_to_markdown", _fake_convert)
    monkeypatch.setattr("docdown.cli.generate_toc", lambda *args, **kwargs: Path(args[1]))

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out"), "--log-level", "debug"])

    assert result.exit_code == 0


def test_cli_rejects_invalid_toc_depth_value(tmp_path):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out"), "--toc-depth", "0"])

    assert result.exit_code != 0
    assert "--toc-depth" in result.output
    assert "Invalid value" in result.output


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


def test_cli_surfaces_pdf_split_errors(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=5, file_size_bytes=dummy_pdf.stat().st_size),
    )

    def _raise_split_error(*args, **kwargs):
        raise PdfSplitError("split failed")

    monkeypatch.setattr("docdown.cli.split_pdf", _raise_split_error)

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])

    assert result.exit_code != 0
    assert "split failed" in result.output


def test_cli_fails_when_all_extractions_fail(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [SimpleNamespace(chunk_number=1, success=False, output_path=None)],
    )

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])

    assert result.exit_code != 0
    assert "Extraction failed for all chunks" in result.output


def test_cli_fails_when_all_conversion_or_cleanup_steps_fail(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
    extracted_path = tmp_path / "out" / "extracted" / "chunk-0001.xml"

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [SimpleNamespace(chunk_number=1, success=True, output_path=extracted_path)],
    )
    monkeypatch.setattr("docdown.cli.ensure_pandoc_available", lambda *args, **kwargs: None)

    def _raise_pandoc_error(*args, **kwargs):
        raise PandocError("pandoc broke")

    monkeypatch.setattr("docdown.cli.convert_to_markdown", _raise_pandoc_error)

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])

    assert result.exit_code != 0
    assert "Markdown conversion/cleanup failed for all extracted chunks" in result.output


def test_cli_surfaces_merge_errors(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
    extracted_path = tmp_path / "out" / "extracted" / "chunk-0001.xml"

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [SimpleNamespace(chunk_number=1, success=True, output_path=extracted_path)],
    )
    monkeypatch.setattr("docdown.cli.ensure_pandoc_available", lambda *args, **kwargs: None)

    def _fake_convert(input_path, output_path, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("# ok", encoding="utf-8")
        return Path(output_path)

    monkeypatch.setattr("docdown.cli.convert_to_markdown", _fake_convert)

    def _raise_merge_error(*args, **kwargs):
        raise MergeError("merge failed")

    monkeypatch.setattr("docdown.cli.merge_chunks", _raise_merge_error)

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])

    assert result.exit_code != 0
    assert "merge failed" in result.output


def test_cli_surfaces_toc_generation_errors(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
    extracted_path = tmp_path / "out" / "extracted" / "chunk-0001.xml"

    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [SimpleNamespace(chunk_number=1, success=True, output_path=extracted_path)],
    )
    monkeypatch.setattr("docdown.cli.ensure_pandoc_available", lambda *args, **kwargs: None)

    def _fake_convert(input_path, output_path, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("# ok", encoding="utf-8")
        return Path(output_path)

    monkeypatch.setattr("docdown.cli.convert_to_markdown", _fake_convert)

    def _raise_toc_error(*args, **kwargs):
        raise TocError("toc failed")

    monkeypatch.setattr("docdown.cli.generate_toc", _raise_toc_error)

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])

    assert result.exit_code != 0
    assert "toc failed" in result.output


def test_cli_autoloads_repo_config_when_flag_omitted(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
    extracted_path = tmp_path / "out" / "extracted" / "chunk-0001.xml"
    captured: dict[str, object] = {}

    monkeypatch.chdir(tmp_path)
    (tmp_path / "docdown.yaml").write_text("log_level: INFO\n", encoding="utf-8")

    def _fake_load_config(config_path=None, cli_overrides=None):
        captured["config_path"] = config_path
        return SimpleNamespace(
            input=dummy_pdf,
            workdir=tmp_path / "out",
            chunk_size=50,
            extractor="pdfminer",
            fallback_extractor="pdfminer",
            grobid_url="http://localhost:8070",
            heuristic_numbered_headings=True,
            heuristic_titlecase_headings=False,
            heuristic_allcaps_headings=False,
            toc_depth=3,
            log_level="INFO",
            validation=SimpleNamespace(min_output_ratio=0.01, max_empty_chunks=0),
        )

    monkeypatch.setattr("docdown.cli.load_config", _fake_load_config)
    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [SimpleNamespace(chunk_number=1, success=True, output_path=extracted_path)],
    )
    monkeypatch.setattr("docdown.cli.ensure_pandoc_available", lambda *args, **kwargs: None)

    def _fake_convert(input_path, output_path, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("# ok", encoding="utf-8")
        return Path(output_path)

    monkeypatch.setattr("docdown.cli.convert_to_markdown", _fake_convert)
    monkeypatch.setattr("docdown.cli.generate_toc", lambda *args, **kwargs: Path(args[1]))

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out")])

    assert result.exit_code == 0
    assert captured["config_path"] == Path("docdown.yaml")


def test_cli_uses_explicit_config_path_when_provided(tmp_path, monkeypatch):
    dummy_pdf = tmp_path / "test.pdf"
    dummy_pdf.write_bytes(b"%PDF-1.4 dummy")
    extracted_path = tmp_path / "out" / "extracted" / "chunk-0001.xml"
    explicit_config = tmp_path / "custom.yaml"
    explicit_config.write_text("log_level: INFO\n", encoding="utf-8")
    captured: dict[str, object] = {}

    def _fake_load_config(config_path=None, cli_overrides=None):
        captured["config_path"] = config_path
        return SimpleNamespace(
            input=dummy_pdf,
            workdir=tmp_path / "out",
            chunk_size=50,
            extractor="pdfminer",
            fallback_extractor="pdfminer",
            grobid_url="http://localhost:8070",
            heuristic_numbered_headings=True,
            heuristic_titlecase_headings=False,
            heuristic_allcaps_headings=False,
            toc_depth=3,
            log_level="INFO",
            validation=SimpleNamespace(min_output_ratio=0.01, max_empty_chunks=0),
        )

    monkeypatch.setattr("docdown.cli.load_config", _fake_load_config)
    monkeypatch.setattr(
        "docdown.cli.validate_pdf",
        lambda *args, **kwargs: SimpleNamespace(page_count=1, file_size_bytes=dummy_pdf.stat().st_size),
    )
    monkeypatch.setattr(
        "docdown.cli.split_pdf",
        lambda *args, **kwargs: SimpleNamespace(chunk_count=1, chunk_paths=(tmp_path / "out" / "chunks" / "chunk-0001.pdf",)),
    )
    monkeypatch.setattr(
        "docdown.cli.orchestrate_extraction",
        lambda *args, **kwargs: [SimpleNamespace(chunk_number=1, success=True, output_path=extracted_path)],
    )
    monkeypatch.setattr("docdown.cli.ensure_pandoc_available", lambda *args, **kwargs: None)

    def _fake_convert(input_path, output_path, **kwargs):
        Path(output_path).parent.mkdir(parents=True, exist_ok=True)
        Path(output_path).write_text("# ok", encoding="utf-8")
        return Path(output_path)

    monkeypatch.setattr("docdown.cli.convert_to_markdown", _fake_convert)
    monkeypatch.setattr("docdown.cli.generate_toc", lambda *args, **kwargs: Path(args[1]))

    runner = CliRunner()
    result = runner.invoke(main, [str(dummy_pdf), "-o", str(tmp_path / "out"), "--config", str(explicit_config)])

    assert result.exit_code == 0
    assert captured["config_path"] == explicit_config
