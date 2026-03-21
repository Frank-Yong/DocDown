"""Tests for DocDown logging framework."""

import re
from pathlib import Path

import pytest

from docdown.utils.logging import (
    configure_logging,
    get_chunk_logger,
    get_logger,
    log_intermediate_path,
    log_tool_command,
)


def test_logging_writes_to_run_log_and_includes_chunk(tmp_path):
    logger = configure_logging(tmp_path, "INFO")
    logger.info("pipeline started")

    chunk_logger = get_chunk_logger(7)
    chunk_logger.info("processing chunk")

    content = (tmp_path / "run.log").read_text(encoding="utf-8")

    assert "pipeline started" in content
    assert "processing chunk" in content
    assert "[chunk-0007]" in content


def test_logging_format_includes_timestamp_level_and_chunk(tmp_path):
    logger = configure_logging(tmp_path, "INFO")
    logger.info("format check")

    first_line = (tmp_path / "run.log").read_text(encoding="utf-8").splitlines()[0]

    assert re.match(r"^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2} INFO\s+\[[^\]]+\] .+", first_line)


def test_debug_level_emits_debug_messages(tmp_path):
    logger = configure_logging(tmp_path, "DEBUG")
    logger.debug("debug detail")

    content = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "debug detail" in content


def test_debug_helpers_log_command_and_path(tmp_path):
    configure_logging(tmp_path, "DEBUG")

    log_tool_command(["qpdf", "input.pdf", "--check"], chunk_number=12)
    log_intermediate_path(Path("workdir/extracted/chunk-0012.xml"), label="intermediate", chunk_number=12)

    content = (tmp_path / "run.log").read_text(encoding="utf-8")
    assert "tool command: qpdf input.pdf --check" in content
    assert "intermediate: workdir\\extracted\\chunk-0012.xml" in content or "intermediate: workdir/extracted/chunk-0012.xml" in content
    assert "[chunk-0012]" in content


def test_get_logger_returns_central_logger(tmp_path):
    configured = configure_logging(tmp_path, "INFO")
    assert get_logger() is configured


def test_invalid_log_level_raises_error(tmp_path):
    with pytest.raises(ValueError, match="Unknown log level"):
        configure_logging(tmp_path, "VERBOSE")
