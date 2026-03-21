"""Central logging setup for DocDown."""

from __future__ import annotations

import logging
import sys
from pathlib import Path
from typing import Any


LOGGER_NAME = "docdown"
LOG_FORMAT = "%(asctime)s %(levelname)-5s [%(chunk)s] %(message)s"
LOG_DATE_FORMAT = "%Y-%m-%dT%H:%M:%S"


class _ChunkFieldFilter(logging.Filter):
    """Ensure all log records include a chunk field for formatter stability."""

    def filter(self, record: logging.LogRecord) -> bool:
        if not hasattr(record, "chunk"):
            record.chunk = "-"
        return True


class ChunkAdapter(logging.LoggerAdapter):
    """Logger adapter that injects a normalized chunk identifier."""

    def process(self, msg: str, kwargs: dict[str, Any]) -> tuple[str, dict[str, Any]]:
        extra = kwargs.get("extra", {})
        chunk = extra.get("chunk", self.extra.get("chunk"))
        extra["chunk"] = _normalize_chunk(chunk)
        kwargs["extra"] = extra
        return msg, kwargs


def configure_logging(workdir: Path, level: str = "INFO") -> logging.Logger:
    """Configure the central logger to write to stderr and workdir/run.log."""

    log_dir = Path(workdir)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / "run.log"

    logger = logging.getLogger(LOGGER_NAME)
    logger.handlers.clear()
    logger.propagate = False
    logger.setLevel(_normalize_level(level))

    formatter = logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT)
    chunk_filter = _ChunkFieldFilter()

    stream_handler = logging.StreamHandler(sys.stderr)
    stream_handler.setFormatter(formatter)
    stream_handler.addFilter(chunk_filter)

    file_handler = logging.FileHandler(log_file, mode="a", encoding="utf-8")
    file_handler.setFormatter(formatter)
    file_handler.addFilter(chunk_filter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)

    logger.debug("Configured logging level=%s run_log=%s", logger.level, log_file)
    return logger


def get_logger() -> logging.Logger:
    """Return the central DocDown logger."""

    return logging.getLogger(LOGGER_NAME)


def get_chunk_logger(chunk_number: int | str) -> ChunkAdapter:
    """Return a chunk-aware logger adapter for chunk-scoped log messages."""

    return ChunkAdapter(get_logger(), {"chunk": _normalize_chunk(chunk_number)})


def log_tool_command(command: list[str] | tuple[str, ...] | str, chunk_number: int | str | None = None) -> None:
    """Emit a standardized DEBUG message for subprocess command execution."""

    logger: logging.Logger | ChunkAdapter
    logger = get_logger() if chunk_number is None else get_chunk_logger(chunk_number)
    if isinstance(command, (list, tuple)):
        command_text = " ".join(str(part) for part in command)
    else:
        command_text = str(command)
    logger.debug("tool command: %s", command_text)


def log_intermediate_path(path: Path, label: str | None = None, chunk_number: int | str | None = None) -> None:
    """Emit a standardized DEBUG message for intermediate artifact paths."""

    logger: logging.Logger | ChunkAdapter
    logger = get_logger() if chunk_number is None else get_chunk_logger(chunk_number)
    prefix = f"{label}: " if label else ""
    logger.debug("%s%s", prefix, path)


def _normalize_level(level: str) -> int:
    upper = str(level).upper()
    if upper == "WARN":
        upper = "WARNING"
    return getattr(logging, upper, logging.INFO)


def _normalize_chunk(chunk: int | str | None) -> str:
    if chunk is None:
        return "-"
    if isinstance(chunk, int):
        return f"chunk-{chunk:04d}"
    chunk_text = str(chunk)
    return chunk_text if chunk_text.startswith("chunk-") else f"chunk-{chunk_text}"
