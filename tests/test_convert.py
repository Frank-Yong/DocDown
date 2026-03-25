"""Tests for Stage 3 Markdown conversion."""

from __future__ import annotations

from pathlib import Path
import subprocess

import pytest

from docdown.stages.convert import PandocError, convert_to_markdown, ensure_pandoc_available


def _cp(returncode: int, stdout: str = "", stderr: str = "") -> subprocess.CompletedProcess[str]:
    return subprocess.CompletedProcess(args=["pandoc"], returncode=returncode, stdout=stdout, stderr=stderr)


def test_ensure_pandoc_available_succeeds(monkeypatch):
    monkeypatch.setattr(
        "docdown.stages.convert.subprocess.run",
        lambda *args, **kwargs: _cp(0, stdout="pandoc 3.1.1\n"),
    )

    ensure_pandoc_available()


def test_ensure_pandoc_available_missing_binary_raises_clear_error(monkeypatch):
    def _raise_oserror(*args, **kwargs):
        raise OSError("not found")

    monkeypatch.setattr("docdown.stages.convert.subprocess.run", _raise_oserror)

    with pytest.raises(PandocError, match="Pandoc is not available on PATH"):
        ensure_pandoc_available()


def test_convert_to_markdown_uses_tei_for_xml_input(tmp_path, monkeypatch):
    source = tmp_path / "chunk-0001.xml"
    source.write_text("<TEI>ok</TEI>", encoding="utf-8")
    output = tmp_path / "markdown" / "chunk-0001.md"

    seen_commands: list[list[str]] = []

    def _fake_run(command, capture_output, text, check):
        seen_commands.append(command)
        Path(command[-1]).write_text("# converted", encoding="utf-8")
        return _cp(0)

    monkeypatch.setattr("docdown.stages.convert.subprocess.run", _fake_run)

    result = convert_to_markdown(source, output)

    assert result == output
    assert output.exists()
    command = seen_commands[0]
    assert command[0] == "pandoc"
    assert "-f" in command and command[command.index("-f") + 1] == "tei"
    assert "-t" in command and command[command.index("-t") + 1] == "gfm"
    assert "--wrap=none" in command


def test_convert_to_markdown_uses_markdown_for_txt_input(tmp_path, monkeypatch):
    source = tmp_path / "chunk-0002.txt"
    source.write_text("plain text", encoding="utf-8")
    output = tmp_path / "markdown" / "chunk-0002.md"

    seen_commands: list[list[str]] = []

    def _fake_run(command, capture_output, text, check):
        seen_commands.append(command)
        Path(command[-1]).write_text("converted", encoding="utf-8")
        return _cp(0)

    monkeypatch.setattr("docdown.stages.convert.subprocess.run", _fake_run)

    convert_to_markdown(source, output)
    command = seen_commands[0]
    assert "-f" in command and command[command.index("-f") + 1] == "markdown"


def test_convert_to_markdown_rejects_unknown_extension(tmp_path):
    source = tmp_path / "chunk-0003.json"
    source.write_text("{}", encoding="utf-8")

    with pytest.raises(PandocError, match="Unsupported conversion input extension"):
        convert_to_markdown(source, tmp_path / "out.md")


def test_convert_to_markdown_rejects_missing_input(tmp_path):
    with pytest.raises(PandocError, match="Conversion input not found"):
        convert_to_markdown(tmp_path / "missing.xml", tmp_path / "out.md")


def test_convert_to_markdown_surfaces_pandoc_stderr(tmp_path, monkeypatch):
    source = tmp_path / "chunk-0004.xml"
    source.write_text("<TEI>", encoding="utf-8")

    monkeypatch.setattr(
        "docdown.stages.convert.subprocess.run",
        lambda *args, **kwargs: _cp(2, stderr="parse failure"),
    )

    with pytest.raises(PandocError, match="parse failure"):
        convert_to_markdown(source, tmp_path / "out.md")
