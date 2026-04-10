"""Stage 8.1 - Per-chunk Markdown validation."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
import stat as stat_types

from docdown.utils.logging import get_chunk_logger, get_logger


LogLike = logging.Logger | logging.LoggerAdapter


@dataclass(frozen=True)
class ChunkValidationResult:
    """Validation outcome for one chunk markdown artifact."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]


@dataclass(frozen=True)
class ChunkResult:
    """Per-chunk processing result used for downstream reporting."""

    chunk_number: int
    success: bool
    markdown_path: Path | None
    error: str | None
    validation: ChunkValidationResult | None


def validate_chunk(
    chunk_md_path: Path,
    chunk_pdf_path: Path,
    *,
    min_output_ratio: float,
    expect_headings: bool,
    logger: LogLike | None = None,
    chunk_number: int | None = None,
) -> ChunkValidationResult:
    """Validate one chunk markdown file without mutating it."""

    if min_output_ratio <= 0:
        raise ValueError(f"min_output_ratio must be > 0, got {min_output_ratio}")

    md_path = Path(chunk_md_path)
    pdf_path = Path(chunk_pdf_path)
    active_logger = _resolve_logger(logger, chunk_number)

    errors: list[str] = []
    warnings: list[str] = []

    try:
        md_stat = md_path.stat()
    except FileNotFoundError:
        errors.append("Empty output")
        _log_errors(active_logger, errors, chunk_number)
        return ChunkValidationResult(valid=False, errors=tuple(errors), warnings=tuple(warnings))
    except OSError as exc:
        errors.append(f"Failed reading markdown output metadata: {exc}")
        _log_errors(active_logger, errors, chunk_number)
        return ChunkValidationResult(valid=False, errors=tuple(errors), warnings=tuple(warnings))

    if not stat_types.S_ISREG(md_stat.st_mode):
        errors.append("Markdown output is not a file")
        _log_errors(active_logger, errors, chunk_number)
        return ChunkValidationResult(valid=False, errors=tuple(errors), warnings=tuple(warnings))

    if md_stat.st_size == 0:
        errors.append("Empty output")
        _log_errors(active_logger, errors, chunk_number)
        return ChunkValidationResult(valid=False, errors=tuple(errors), warnings=tuple(warnings))

    try:
        text = md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        errors.append("Invalid UTF-8 encoding")
        _log_errors(active_logger, errors, chunk_number)
        return ChunkValidationResult(valid=False, errors=tuple(errors), warnings=tuple(warnings))
    except OSError as exc:
        errors.append(f"Failed reading markdown output: {exc}")
        _log_errors(active_logger, errors, chunk_number)
        return ChunkValidationResult(valid=False, errors=tuple(errors), warnings=tuple(warnings))

    if not text.strip():
        errors.append("Empty output")
        _log_errors(active_logger, errors, chunk_number)
        return ChunkValidationResult(valid=False, errors=tuple(errors), warnings=tuple(warnings))

    md_size = md_stat.st_size
    try:
        pdf_stat = pdf_path.stat()
    except OSError:
        pdf_stat = None

    if pdf_stat is not None and stat_types.S_ISREG(pdf_stat.st_mode) and pdf_stat.st_size > 0:
        ratio = md_size / pdf_stat.st_size
        if ratio < min_output_ratio:
            warnings.append(
                f"Output ratio {ratio:.4f} below threshold {min_output_ratio:.4f}"
            )

    if expect_headings and not re.search(r"^#{1,6}[ \t]+\S", text, re.MULTILINE):
        warnings.append("No headings detected")

    for warning in warnings:
        if chunk_number is None:
            active_logger.warning("Chunk validation warning: %s", warning)
        else:
            active_logger.warning("Chunk-%04d validation warning: %s", chunk_number, warning)

    return ChunkValidationResult(valid=True, errors=tuple(errors), warnings=tuple(warnings))


def _resolve_logger(logger: LogLike | None, chunk_number: int | None) -> LogLike:
    if logger is not None:
        return logger
    if chunk_number is None:
        return get_logger()
    return get_chunk_logger(chunk_number)


def _log_errors(logger: LogLike, errors: list[str], chunk_number: int | None) -> None:
    for error in errors:
        if chunk_number is None:
            logger.error("Chunk validation failed: %s", error)
        else:
            logger.error("Chunk-%04d validation failed: %s", chunk_number, error)
