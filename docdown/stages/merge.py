"""Stage 6.1 — Chunk merging."""

from __future__ import annotations

import logging
from pathlib import Path
import stat as stat_types

from docdown.utils.logging import get_logger


LogLike = logging.Logger | logging.LoggerAdapter


class MergeError(ValueError):
    """Raised when chunk merge inputs are invalid or chunk/output filesystem operations fail."""


def merge_chunks(
    markdown_dir: Path,
    output_path: Path,
    total_chunks: int,
    *,
    logger: LogLike | None = None,
) -> Path:
    """Merge chunk markdown files into one document with separators and placeholders."""

    if total_chunks < 1:
        raise MergeError(f"total_chunks must be >= 1, got {total_chunks}")

    source_dir = Path(markdown_dir)
    target = Path(output_path)
    active_logger = logger or get_logger()

    if not source_dir.exists():
        raise MergeError(f"Markdown directory not found: {source_dir}")
    if not source_dir.is_dir():
        raise MergeError(f"Markdown path is not a directory: {source_dir}")

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        newline_count = 0
        wrote_any = False
        with target.open("w", encoding="utf-8", newline="") as handle:
            for chunk_number in range(1, total_chunks + 1):
                part = _chunk_part(source_dir, chunk_number)
                if wrote_any:
                    separator = "\n\n---\n\n"
                    handle.write(separator)
                    newline_count += separator.count("\n")
                handle.write(part)
                newline_count += part.count("\n")
                wrote_any = True

        file_size = target.stat().st_size
    except OSError as exc:
        raise MergeError(f"Failed writing merged markdown to {target}: {exc}") from exc

    line_count = newline_count + (1 if wrote_any else 0)
    active_logger.info("Merged markdown output: lines=%s size_bytes=%s path=%s", line_count, file_size, target)
    return target


def _normalize_merge_part(text: str) -> str:
    return text.rstrip("\r\n")


def _chunk_part(source_dir: Path, chunk_number: int) -> str:
    chunk_path = source_dir / f"chunk-{chunk_number:04d}.md"
    try:
        chunk_stat = chunk_path.stat()
    except FileNotFoundError:
        return _normalize_merge_part(f"<!-- chunk-{chunk_number:04d}: extraction failed -->")
    except OSError as exc:
        raise MergeError(f"Failed reading chunk markdown {chunk_path}: {exc}") from exc

    if not stat_types.S_ISREG(chunk_stat.st_mode):
        raise MergeError(f"Chunk markdown path is not a file: {chunk_path}")

    if chunk_stat.st_size == 0:
        return _normalize_merge_part(f"<!-- chunk-{chunk_number:04d}: extraction failed -->")

    try:
        normalized = _normalize_merge_part(chunk_path.read_text(encoding="utf-8"))
        if not normalized.strip():
            return _normalize_merge_part(f"<!-- chunk-{chunk_number:04d}: extraction failed -->")
        return normalized
    except OSError as exc:
        raise MergeError(f"Failed reading chunk markdown {chunk_path}: {exc}") from exc
