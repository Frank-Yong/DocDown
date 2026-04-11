"""Stage 8.2 - Final markdown output validation."""

from __future__ import annotations

from dataclasses import dataclass
import logging
from pathlib import Path
import re
from typing import Iterable

from docdown.stages.chunk_validation import ChunkResult
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
    logger: LogLike | None = None,
) -> FinalValidationResult:
    """Validate final markdown output and return aggregated findings."""

    if max_empty_chunks < 0:
        raise ValueError(f"max_empty_chunks must be >= 0, got {max_empty_chunks}")

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

    try:
        final_text = final_markdown.read_text(encoding="utf-8")
    except OSError as exc:
        raise FinalValidationError(f"Failed reading final markdown: {exc}") from exc
    except UnicodeDecodeError as exc:
        raise FinalValidationError(f"Failed reading final markdown: invalid UTF-8 encoding ({exc})") from exc

    result_items = sorted(chunk_results, key=lambda item: item.chunk_number)

    errors: list[str] = []
    warnings: list[str] = []

    if source_size > 0:
        ratio = final_size / source_size
        if ratio < 0.01:
            warnings.append(
                f"Final output ratio {ratio:.4f} below threshold 0.0100"
            )

    empty_failed_chunks = _count_empty_failed_chunks(result_items)
    if empty_failed_chunks > max_empty_chunks:
        errors.append(
            f"{empty_failed_chunks} empty chunks failed validation (max allowed: {max_empty_chunks})."
        )

    toc_present = _has_toc_near_top(final_text)
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
    lines = markdown_text.splitlines()[:max_scan_lines]
    toc_link_pattern = re.compile(r"^\s*-\s+\[[^\]]+\]\([^\)]+\)")
    return any(toc_link_pattern.search(line) is not None for line in lines)


def _detect_duplicate_boundaries(chunk_results: Iterable[ChunkResult], *, logger: LogLike) -> list[str]:
    warnings: list[str] = []
    chunk_list = list(chunk_results)
    for left, right in zip(chunk_list, chunk_list[1:]):
        left_paragraph = _read_boundary_paragraph(left.markdown_path, from_end=True, logger=logger)
        right_paragraph = _read_boundary_paragraph(right.markdown_path, from_end=False, logger=logger)
        if left_paragraph is None or right_paragraph is None:
            continue
        if left_paragraph == right_paragraph:
            warnings.append(
                "Potential duplicate boundary paragraph between "
                f"chunk-{left.chunk_number:04d} and chunk-{right.chunk_number:04d}"
            )
    return warnings


def _read_boundary_paragraph(
    markdown_path: Path | None,
    *,
    from_end: bool,
    logger: LogLike,
) -> str | None:
    if markdown_path is None:
        return None

    path = Path(markdown_path)
    if not path.exists() or not path.is_file():
        return None

    try:
        text = path.read_text(encoding="utf-8")
    except (OSError, UnicodeDecodeError) as exc:
        logger.warning("Final validation skipped unreadable chunk markdown %s: %s", path, exc)
        return None

    paragraphs = [_normalize_paragraph(part) for part in re.split(r"\n\s*\n", text)]
    candidates = [paragraph for paragraph in paragraphs if _word_count(paragraph) > 50]
    if not candidates:
        return None

    return candidates[-1] if from_end else candidates[0]


def _normalize_paragraph(text: str) -> str:
    collapsed = re.sub(r"\s+", " ", text.strip())
    return collapsed


def _word_count(text: str) -> int:
    return len(re.findall(r"\S+", text))
