"""Stage 8.2 - Final markdown output validation."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import math
from pathlib import Path
import re
from typing import Iterable

from docdown.stages.chunk_validation import ChunkResult
from docdown.stages.toc import has_visible_toc_near_top
from docdown.utils.logging import get_logger


LogLike = logging.Logger | logging.LoggerAdapter


class FinalValidationError(ValueError):
    """Raised when final output validation cannot be completed."""


@dataclass(frozen=True)
class FinalValidationResult:
    """Validation outcome for the final markdown artifact."""

    valid: bool
    errors: tuple[str, ...]
    warnings: tuple[str, ...]
    failed_chunk_count: int
    toc_present: bool
    duplicate_boundary_count: int


def validate_final_output(
    final_path: Path,
    source_pdf_path: Path,
    chunk_results: Iterable[ChunkResult],
    *,
    max_empty_chunks: int,
    min_output_ratio: float = 0.01,
    logger: LogLike | None = None,
) -> FinalValidationResult:
    """Validate final markdown output and return aggregated findings."""

    if max_empty_chunks < 0:
        raise ValueError(f"max_empty_chunks must be >= 0, got {max_empty_chunks}")
    if not math.isfinite(min_output_ratio) or min_output_ratio <= 0:
        raise ValueError(f"min_output_ratio must be > 0 and finite, got {min_output_ratio}")

    active_logger = logger or get_logger()
    final_markdown = Path(final_path)
    source_pdf = Path(source_pdf_path)

    if not final_markdown.exists() or not final_markdown.is_file():
        raise FinalValidationError(f"Final markdown output not found: {final_markdown}")
    if not source_pdf.exists() or not source_pdf.is_file():
        raise FinalValidationError(f"Source PDF not found: {source_pdf}")

    try:
        final_size = final_markdown.stat().st_size
    except OSError as exc:
        raise FinalValidationError(f"Failed reading final markdown metadata: {exc}") from exc

    try:
        source_size = source_pdf.stat().st_size
    except OSError as exc:
        raise FinalValidationError(f"Failed reading source PDF metadata: {exc}") from exc

    toc_scan_lines = 120
    try:
        final_prefix = _read_top_lines(final_markdown, max_lines=toc_scan_lines)
    except OSError as exc:
        raise FinalValidationError(f"Failed reading final markdown: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FinalValidationError(f"Failed reading final markdown: invalid UTF-8 encoding ({exc})") from exc

    result_items = sorted(chunk_results, key=lambda item: item.chunk_number)

    errors: list[str] = []
    warnings: list[str] = []

    if source_size > 0:
        ratio = final_size / source_size
        if ratio < min_output_ratio:
            warnings.append(
                f"Final output ratio {ratio:.4f} below threshold {min_output_ratio:.4f}"
            )

    empty_failed_chunks = _count_empty_failed_chunks(result_items)
    if empty_failed_chunks > max_empty_chunks:
        errors.append(
            f"{empty_failed_chunks} empty chunks failed validation (max allowed: {max_empty_chunks})."
        )

    toc_present = _has_toc_near_top(final_prefix, max_scan_lines=toc_scan_lines)
    if not toc_present:
        warnings.append("Final output appears to be missing a TOC section near the top")

    duplicate_warnings = _detect_duplicate_boundaries(result_items, logger=active_logger)
    warnings.extend(duplicate_warnings)

    for issue in errors:
        active_logger.error("Final validation failed: %s", issue)
    for warning in warnings:
        active_logger.warning("Final validation warning: %s", warning)

    return FinalValidationResult(
        valid=not errors,
        errors=tuple(errors),
        warnings=tuple(warnings),
        failed_chunk_count=sum(1 for item in result_items if not item.success),
        toc_present=toc_present,
        duplicate_boundary_count=len(duplicate_warnings),
    )


def _count_empty_failed_chunks(chunk_results: Iterable[ChunkResult]) -> int:
    empty_count = 0
    for result in chunk_results:
        if result.success:
            continue
        if result.validation is not None and "Empty output" in result.validation.errors:
            empty_count += 1
    return empty_count


def _has_toc_near_top(markdown_text: str, *, max_scan_lines: int = 120) -> bool:
    return has_visible_toc_near_top(markdown_text, max_scan_lines=max_scan_lines)


def _detect_duplicate_boundaries(chunk_results: Iterable[ChunkResult], *, logger: LogLike) -> list[str]:
    warnings: list[str] = []
    chunk_list = sorted(chunk_results, key=lambda chunk: chunk.chunk_number)
    boundary_cache = {
        chunk.chunk_number: _read_chunk_boundary_paragraphs(chunk.markdown_path, logger=logger)
        for chunk in chunk_list
    }

    for left, right in zip(chunk_list, chunk_list[1:]):
        if right.chunk_number != left.chunk_number + 1:
            continue

        left_paragraph, _ = boundary_cache[left.chunk_number]
        _, right_paragraph = boundary_cache[right.chunk_number]
        if left_paragraph is None or right_paragraph is None:
            continue
        if left_paragraph == right_paragraph:
            warnings.append(
                "Potential duplicate boundary paragraph between "
                f"chunk-{left.chunk_number:04d} and chunk-{right.chunk_number:04d}"
            )
    return warnings


def _read_chunk_boundary_paragraphs(markdown_path: Path | None, *, logger: LogLike) -> tuple[str | None, str | None]:
    if markdown_path is None:
        return None, None

    path = Path(markdown_path)
    if not path.exists() or not path.is_file():
        return None, None

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Final validation skipped unreadable chunk markdown %s: %s", path, exc)
        return None, None

    paragraphs = [_normalize_paragraph(part) for part in re.split(r"\n\s*\n", text)]
    non_empty_paragraphs = [paragraph for paragraph in paragraphs if paragraph]
    if not non_empty_paragraphs:
        return None, None

    first_paragraph = non_empty_paragraphs[0]
    last_paragraph = non_empty_paragraphs[-1]

    first_boundary = first_paragraph if _word_count(first_paragraph) > 50 else None
    last_boundary = last_paragraph if _word_count(last_paragraph) > 50 else None

    return last_boundary, first_boundary


def _normalize_paragraph(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))


def _read_top_lines(markdown_path: Path, *, max_lines: int) -> str:
    if max_lines <= 0:
        return ""

    lines: list[str] = []
    with markdown_path.open("r", encoding="utf-8", newline="") as handle:
        for _ in range(max_lines):
            line = handle.readline()
            if not line:
                break
            lines.append(line)

    return "".join(lines)
