"""Stage 4.2 — Post-conversion Markdown cleanup."""

from __future__ import annotations

import logging
from pathlib import Path
import re

from docdown.utils.logging import get_logger


LogLike = logging.Logger | logging.LoggerAdapter


class CleanupError(ValueError):
    """Raised when markdown cleanup fails."""


def cleanup_markdown_file(
    markdown_path: Path,
    *,
    logger: LogLike | None = None,
    chunk_number: int | None = None,
) -> Path:
    """Apply cleanup rules in-place to a markdown chunk file."""

    path = Path(markdown_path)
    active_logger = logger or get_logger()

    if not path.exists() or not path.is_file():
        raise CleanupError(f"Markdown cleanup input not found: {path}")

    original = path.read_text(encoding="utf-8")
    cleaned = cleanup_markdown_text(original, logger=active_logger, chunk_number=chunk_number)

    if cleaned != original:
        path.write_text(cleaned, encoding="utf-8")
        active_logger.debug("Markdown cleanup updated %s", path.name)
    else:
        active_logger.debug("Markdown cleanup made no changes to %s", path.name)

    return path


def cleanup_markdown_text(
    text: str,
    *,
    logger: LogLike | None = None,
    chunk_number: int | None = None,
) -> str:
    """Apply all markdown cleanup rules and return cleaned text."""

    active_logger = logger or get_logger()
    normalized = text.replace("\r\n", "\n").replace("\r", "\n")
    trailing_newline = normalized.endswith("\n")

    cleaned = strip_trailing_whitespace(normalized)
    cleaned = remove_repeated_header_footer_lines(cleaned, logger=active_logger, chunk_number=chunk_number)
    cleaned = normalize_headings(cleaned)
    cleaned = collapse_blank_lines(cleaned)

    if trailing_newline and cleaned and not cleaned.endswith("\n"):
        cleaned = f"{cleaned}\n"

    return cleaned


def collapse_blank_lines(text: str) -> str:
    """Collapse runs of 3+ blank lines to exactly two newlines."""

    return re.sub(r"\n{3,}", "\n\n", text)


def normalize_headings(text: str) -> str:
    """Demote headings by one level when H1 headings are present."""

    if re.search(r"^# ", text, flags=re.MULTILINE):
        return re.sub(r"^(#{1,5}) ", lambda match: f"#{match.group(1)} ", text, flags=re.MULTILINE)
    return text


def strip_trailing_whitespace(text: str) -> str:
    """Trim trailing spaces/tabs from each line."""

    lines = text.split("\n")
    return "\n".join(line.rstrip(" \t") for line in lines)


def remove_repeated_header_footer_lines(
    text: str,
    *,
    logger: LogLike | None = None,
    chunk_number: int | None = None,
    edge_line_count: int = 2,
) -> str:
    """Remove repeated edge lines seen in a majority of page-equivalent blocks."""

    if edge_line_count <= 0:
        return text

    blocks = text.split("\f")
    if len(blocks) < 2:
        return text

    occurrences: dict[str, int] = {}
    considered_blocks = 0
    for block in blocks:
        lines = [line.rstrip(" \t") for line in block.split("\n")]
        non_empty = [line for line in lines if line.strip()]
        if not non_empty:
            continue
        considered_blocks += 1

        edge_candidates = non_empty[:edge_line_count] + non_empty[-edge_line_count:]
        for candidate in set(edge_candidates):
            occurrences[candidate] = occurrences.get(candidate, 0) + 1

    if not occurrences:
        return text

    if considered_blocks == 0:
        return text

    threshold = considered_blocks / 2
    repeated = {line for line, count in occurrences.items() if count > threshold}
    if not repeated:
        return text

    active_logger = logger or get_logger()
    if chunk_number is not None:
        active_logger.debug(
            "Removed repeated header/footer lines from chunk-%04d: %s",
            chunk_number,
            sorted(repeated),
        )
    else:
        active_logger.debug("Removed repeated header/footer lines: %s", sorted(repeated))

    cleaned_blocks: list[str] = []
    for block in blocks:
        lines = block.split("\n")
        kept_lines = [line for line in lines if line.rstrip(" \t") not in repeated]
        cleaned_blocks.append("\n".join(kept_lines))

    return "\f".join(cleaned_blocks)
