"""Stage 8.3 - End-of-run summary generation."""

from __future__ import annotations

from dataclasses import dataclass
import math
from pathlib import Path
from typing import Iterable

from docdown.stages.chunk_validation import ChunkResult


class RunSummaryError(ValueError):
    """Raised when run summary output cannot be generated or persisted."""


@dataclass(frozen=True)
class RunSummaryContext:
    """Inputs used to generate a parseable run summary."""

    input_path: Path
    input_size_bytes: int
    total_pages: int
    total_chunks: int
    successful_chunks: int
    failed_chunks: tuple[ChunkResult, ...]
    tables_found: int
    output_path: Path
    output_size_bytes: int
    duration_seconds: float
    warning_count: int


def generate_run_summary(context: RunSummaryContext) -> str:
    """Return a stable text summary for stderr and run.log."""

    failed_details = ""
    if context.failed_chunks:
        details = "; ".join(
            f"chunk-{item.chunk_number:04d}: {_failed_error_text(item)}"
            for item in context.failed_chunks
        )
        failed_details = f" ({details})"

    lines = [
        "DocDown Run Summary",
        "-------------------",
        (
            f"Input:          {Path(context.input_path).name} "
            f"({_format_size(context.input_size_bytes)}, {context.total_pages} pages)"
        ),
        f"Chunks:         {context.total_chunks}",
        f"Successful:     {context.successful_chunks}",
        f"Failed:         {len(context.failed_chunks)}{failed_details}",
        f"Tables found:   {context.tables_found}",
        f"Output:         {Path(context.output_path).name} ({_format_size(context.output_size_bytes)})",
        f"Duration:       {_format_duration(context.duration_seconds)}",
        f"Warnings:       {context.warning_count} (see run.log)",
    ]
    return "\n".join(lines)


def append_run_summary(run_log_path: Path, summary: str) -> None:
    """Append summary text to run.log."""

    target = Path(run_log_path)
    try:
        with target.open("a", encoding="utf-8", newline="") as handle:
            if not summary.endswith("\n"):
                summary = f"{summary}\n"
            handle.write("\n")
            handle.write(summary)
    except OSError as exc:
        raise RunSummaryError(f"Failed appending run summary to {target}: {exc}") from exc


def _failed_error_text(item: ChunkResult) -> str:
    error = item.error
    return error if error else "unknown error"


def _format_size(size_bytes: int) -> str:
    size = max(0, int(size_bytes))
    units = ["B", "KB", "MB", "GB", "TB"]
    value = float(size)
    for unit in units:
        if value < 1024.0 or unit == units[-1]:
            if unit == "B":
                return f"{int(value)} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024.0
    return "0 B"


def _format_duration(duration_seconds: float) -> str:
    if not math.isfinite(duration_seconds) or duration_seconds < 0:
        duration_seconds = 0

    total_seconds = int(round(duration_seconds))
    hours, remainder = divmod(total_seconds, 3600)
    minutes, seconds = divmod(remainder, 60)

    if hours > 0:
        return f"{hours}h {minutes}m {seconds}s"
    if minutes > 0:
        return f"{minutes}m {seconds}s"
    return f"{seconds}s"
