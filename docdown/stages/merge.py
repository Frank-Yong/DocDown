"""Stage 6.1 — Chunk merging."""

from __future__ import annotations

import logging
from pathlib import Path
import stat as stat_types

from docdown.utils.logging import get_logger


LogLike = logging.Logger | logging.LoggerAdapter


class MergeError(ValueError):
    """Raised when chunk merge inputs are invalid or merge output cannot be written."""


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

    parts: list[str] = []
    for chunk_number in range(1, total_chunks + 1):
        chunk_path = source_dir / f"chunk-{chunk_number:04d}.md"
        try:
            chunk_stat = chunk_path.stat()
        except FileNotFoundError:
            parts.append(_normalize_merge_part(f"<!-- chunk-{chunk_number:04d}: extraction failed -->"))
            continue
        except OSError as exc:
            raise MergeError(f"Failed reading chunk markdown {chunk_path}: {exc}") from exc

        if not stat_types.S_ISREG(chunk_stat.st_mode):
            raise MergeError(f"Chunk markdown path is not a file: {chunk_path}")

        if chunk_stat.st_size == 0:
            parts.append(_normalize_merge_part(f"<!-- chunk-{chunk_number:04d}: extraction failed -->"))
            continue

        try:
            parts.append(_normalize_merge_part(chunk_path.read_text(encoding="utf-8")))
        except OSError as exc:
            raise MergeError(f"Failed reading chunk markdown {chunk_path}: {exc}") from exc

    merged_text = "\n\n---\n\n".join(parts)
    try:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(merged_text, encoding="utf-8", newline="")
        file_size = target.stat().st_size
    except OSError as exc:
        raise MergeError(f"Failed writing merged markdown to {target}: {exc}") from exc

    line_count = merged_text.count("\n") + (1 if merged_text else 0)
    active_logger.info("Merged markdown output: lines=%s size_bytes=%s path=%s", line_count, file_size, target)
    return target


def _normalize_merge_part(text: str) -> str:
    return text.rstrip("\r\n")
