"""Stage 6.2 - TOC generation for merged markdown output."""

from __future__ import annotations

from collections import Counter
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


def log_heading_diagnostics(markdown_dir: Path, merged_path: Path, *, logger: LogLike | None = None) -> None:
    """Log heading-quality diagnostics for chunk markdown and merged markdown."""

    active_logger = logger or get_logger()
    source_dir = Path(markdown_dir)
    merged = Path(merged_path)

    chunk_paths = sorted(source_dir.glob("chunk-*.md")) if source_dir.exists() and source_dir.is_dir() else []
    chunk_level_counts: Counter[int] = Counter()
    chunks_with_headings = 0
    chunks_without_headings = 0

    for chunk_path in chunk_paths:
        try:
            with chunk_path.open("r", encoding="utf-8", newline="") as handle:
                per_file_counts = _heading_level_counts(handle)
        except OSError as exc:
            active_logger.warning("Heading diagnostics skipped unreadable chunk markdown %s: %s", chunk_path, exc)
            continue

        heading_total = sum(per_file_counts.values())
        if heading_total > 0:
            chunks_with_headings += 1
            chunk_level_counts.update(per_file_counts)
        else:
            chunks_without_headings += 1

    active_logger.info(
        "Heading diagnostics (chunks): files=%s with_headings=%s without_headings=%s level_counts=%s",
        len(chunk_paths),
        chunks_with_headings,
        chunks_without_headings,
        _format_level_counts(chunk_level_counts),
    )

    if not merged.exists() or not merged.is_file():
        active_logger.warning("Heading diagnostics skipped merged markdown missing: %s", merged)
        return

    try:
        with merged.open("r", encoding="utf-8", newline="") as handle:
            merged_level_counts = _heading_level_counts(handle)
    except OSError as exc:
        active_logger.warning("Heading diagnostics skipped unreadable merged markdown %s: %s", merged, exc)
        return

    active_logger.info(
        "Heading diagnostics (merged): headings_total=%s level_counts=%s path=%s",
        sum(merged_level_counts.values()),
        _format_level_counts(merged_level_counts),
        merged,
    )


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

    entries = _collect_toc_entries(source, toc_depth)
    entry_count = len(entries)

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
        _copy_without_toc(
            source,
            target,
            active_logger,
            reason=f"pandoc unavailable: {exc}",
            entry_count=entry_count,
            toc_depth=toc_depth,
        )
        mode, emitted_entries = _ensure_visible_toc(target, entries)
        active_logger.info(
            "TOC generation complete: mode=%s entries=%s depth=%s path=%s",
            mode,
            emitted_entries,
            toc_depth,
            target,
        )
        return target

    if result.returncode != 0:
        diagnostics = _combined_output(result)
        _copy_without_toc(
            source,
            target,
            active_logger,
            reason=f"pandoc failed: {diagnostics}",
            entry_count=entry_count,
            toc_depth=toc_depth,
        )
        mode, emitted_entries = _ensure_visible_toc(target, entries)
        active_logger.info(
            "TOC generation complete: mode=%s entries=%s depth=%s path=%s",
            mode,
            emitted_entries,
            toc_depth,
            target,
        )
        return target

    mode, emitted_entries = _ensure_visible_toc(target, entries)

    active_logger.info(
        "TOC generation complete: mode=%s entries=%s depth=%s path=%s",
        mode,
        emitted_entries,
        toc_depth,
        target,
    )
    return target


def _copy_without_toc(
    source: Path,
    target: Path,
    logger: LogLike,
    *,
    reason: str,
    entry_count: int,
    toc_depth: int,
) -> None:
    """Fallback to a direct merged->final copy when pandoc TOC generation is unavailable."""

    try:
        shutil.copyfile(source, target)
    except OSError as exc:
        raise TocError(f"TOC fallback copy failed from {source} to {target}: {exc}") from exc

    logger.warning(
        "TOC generation degraded; copied merged markdown after pandoc failure and will evaluate fallback TOC injection: %s (entries=%s depth=%s)",
        reason,
        entry_count,
        toc_depth,
    )


def _count_headings_for_toc(markdown_lines: Iterable[str] | str, toc_depth: int) -> int:
    """Count ATX headings eligible for TOC inclusion up to the requested depth."""

    count = 0
    in_fenced_block = False
    lines = markdown_lines.splitlines() if isinstance(markdown_lines, str) else markdown_lines
    for line in lines:
        normalized = line.lstrip(" ")
        leading_spaces = len(line) - len(normalized)

        if leading_spaces <= 3 and (normalized.startswith("```") or normalized.startswith("~~~")):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block:
            continue

        match = re.match(r"^ {0,3}(#{1,6})[ \t]+.+$", line)
        if match is None:
            continue

        level = len(match.group(1))
        if level <= toc_depth:
            count += 1

    return count


def _collect_toc_entries(merged_path: Path, toc_depth: int) -> list[tuple[int, str, str]]:
    """Collect TOC entries from merged markdown headings with GitHub-compatible anchors."""

    try:
        with merged_path.open("r", encoding="utf-8", newline="") as handle:
            heading_pairs = list(_iter_headings(handle, toc_depth=toc_depth))
    except OSError as exc:
        raise TocError(f"Failed reading merged markdown {merged_path}: {exc}") from exc

    seen_anchors: Counter[str] = Counter()
    entries: list[tuple[int, str, str]] = []
    for level, title in heading_pairs:
        anchor_base = _github_anchor(title)
        seen_anchors[anchor_base] += 1
        occurrence = seen_anchors[anchor_base]
        anchor = anchor_base if occurrence == 1 else f"{anchor_base}-{occurrence - 1}"
        entries.append((level, title, anchor))

    return entries


def _ensure_visible_toc(target_path: Path, entries: list[tuple[int, str, str]]) -> tuple[str, int]:
    """Ensure final output has a visible TOC near the top; inject Python TOC when missing."""

    try:
        content = target_path.read_text(encoding="utf-8")
    except OSError as exc:
        raise TocError(f"Failed reading generated markdown {target_path}: {exc}") from exc

    if _has_visible_toc_near_top(content):
        return "pandoc", len(entries)

    toc_block = _build_python_toc_block(entries)
    if not toc_block:
        return "pandoc", 0

    if content and not content.endswith("\n"):
        content = f"{content}\n"

    rewritten = f"{toc_block}\n\n{content}" if content else f"{toc_block}\n"
    try:
        target_path.write_text(rewritten, encoding="utf-8")
    except OSError as exc:
        raise TocError(f"Failed writing TOC fallback markdown {target_path}: {exc}") from exc

    return "python-fallback", len(entries)


def _has_visible_toc_near_top(markdown_text: str, *, max_scan_lines: int = 120) -> bool:
    lines = markdown_text.splitlines()[:max_scan_lines]
    toc_marker_seen = False
    for line in lines:
        stripped = line.strip()
        if re.match(r"^#{1,6}\s+table of contents\s*$", stripped, flags=re.IGNORECASE):
            toc_marker_seen = True
        elif re.match(r"^\[toc\]$", stripped, flags=re.IGNORECASE):
            toc_marker_seen = True
        elif re.search(r"<div\s+id=[\"']toc[\"']", stripped, flags=re.IGNORECASE):
            toc_marker_seen = True

        if re.match(r"^\s*[-*]\s+\[[^\]]+\]\(#[^)]+\)\s*$", line):
            return True

    return toc_marker_seen


def _build_python_toc_block(entries: list[tuple[int, str, str]]) -> str:
    if not entries:
        return ""

    lines = ["## Table of Contents", ""]
    for level, title, anchor in entries:
        indent = "  " * max(level - 1, 0)
        lines.append(f"{indent}- [{title}](#{anchor})")
    return "\n".join(lines)


def _github_anchor(title: str) -> str:
    anchor = title.strip().lower()
    anchor = re.sub(r"[^a-z0-9\-_\s]", "", anchor)
    anchor = re.sub(r"\s+", "-", anchor)
    anchor = re.sub(r"-+", "-", anchor).strip("-")
    return anchor or "section"


def _heading_level_counts(markdown_lines: Iterable[str] | str) -> Counter[int]:
    """Return heading counts per ATX level while skipping fenced code blocks."""

    levels: Counter[int] = Counter()
    for level, _ in _iter_headings(markdown_lines, toc_depth=6):
        levels[level] += 1

    return levels


def _iter_headings(markdown_lines: Iterable[str] | str, *, toc_depth: int) -> Iterable[tuple[int, str]]:
    """Yield (level, title) for ATX headings up to toc_depth, excluding fenced code blocks."""

    in_fenced_block = False
    lines = markdown_lines.splitlines() if isinstance(markdown_lines, str) else markdown_lines
    for line in lines:
        normalized = line.lstrip(" ")
        leading_spaces = len(line) - len(normalized)

        if leading_spaces <= 3 and (normalized.startswith("```") or normalized.startswith("~~~")):
            in_fenced_block = not in_fenced_block
            continue
        if in_fenced_block:
            continue

        match = re.match(r"^ {0,3}(#{1,6})[ \t]+(.+?)\s*$", line)
        if match is None:
            continue

        level = len(match.group(1))
        if level > toc_depth:
            continue

        title = match.group(2).strip()
        if not title:
            continue
        yield level, title


def _format_level_counts(level_counts: Counter[int]) -> str:
    if not level_counts:
        return "none"
    return ",".join(f"h{level}:{level_counts[level]}" for level in range(1, 7) if level_counts[level] > 0)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    return combined if combined else "<no diagnostics>"
