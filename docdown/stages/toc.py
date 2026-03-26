"""Stage 6.2 - TOC generation for merged markdown output."""

from __future__ import annotations

import logging
from pathlib import Path
import re
import shutil
import subprocess
from typing import Iterable

from docdown.utils.logging import get_logger, log_tool_command


LogLike = logging.Logger | logging.LoggerAdapter


class TocError(ValueError):
    """Raised when TOC generation inputs are invalid or fallback copy fails."""


def generate_toc(
    merged_path: Path,
    final_path: Path,
    *,
    toc_depth: int = 3,
    logger: LogLike | None = None,
) -> Path:
    """Generate a TOC-enhanced markdown output via Pandoc, with copy fallback on tool failure."""

    source = Path(merged_path)
    target = Path(final_path)
    active_logger = logger or get_logger()

    if toc_depth < 1 or toc_depth > 6:
        raise TocError(f"toc_depth must be between 1 and 6, got {toc_depth}")

    if not source.exists() or not source.is_file():
        raise TocError(f"Merged markdown input not found: {source}")

    try:
        with source.open("r", encoding="utf-8", newline="") as handle:
            entry_count = _count_headings_for_toc(handle, toc_depth)
    except OSError as exc:
        raise TocError(f"Failed reading merged markdown {source}: {exc}") from exc

    try:
        target.parent.mkdir(parents=True, exist_ok=True)
    except OSError as exc:
        raise TocError(f"Failed preparing final markdown output path {target}: {exc}") from exc

    command = [
        "pandoc",
        str(source),
        "-f",
        "gfm",
        "-t",
        "gfm",
        "--wrap=none",
        "--toc",
        f"--toc-depth={toc_depth}",
        "-o",
        str(target),
    ]
    log_tool_command(command)

    try:
        result = subprocess.run(command, capture_output=True, text=True, check=False)
    except OSError as exc:
        _copy_without_toc(source, target, active_logger, reason=f"pandoc unavailable: {exc}")
        return target

    if result.returncode != 0:
        diagnostics = _combined_output(result)
        _copy_without_toc(source, target, active_logger, reason=f"pandoc failed: {diagnostics}")
        return target

    active_logger.info(
        "TOC generation complete: entries=%s depth=%s path=%s",
        entry_count,
        toc_depth,
        target,
    )
    return target


def _copy_without_toc(source: Path, target: Path, logger: LogLike, *, reason: str) -> None:
    """Fallback to a direct merged->final copy when pandoc TOC generation is unavailable."""

    try:
        shutil.copyfile(source, target)
    except OSError as exc:
        raise TocError(f"TOC fallback copy failed from {source} to {target}: {exc}") from exc

    logger.warning("TOC generation degraded; copied merged markdown without TOC: %s", reason)
    logger.info("TOC generation complete: entries=%s depth=%s path=%s", 0, "-", target)


def _count_headings_for_toc(markdown_lines: Iterable[str] | str, toc_depth: int) -> int:
    """Count ATX headings eligible for TOC inclusion up to the requested depth."""

    count = 0
    in_fenced_block = False
    lines = markdown_lines.splitlines() if isinstance(markdown_lines, str) else markdown_lines
    for line in lines:
        if line.startswith("```") or line.startswith("~~~"):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block:
            continue

        match = re.match(r"^(#{1,6})[ \t]+.+$", line)
        if match is None:
            continue

        level = len(match.group(1))
        if level <= toc_depth:
            count += 1

    return count


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    return combined if combined else "<no diagnostics>"
