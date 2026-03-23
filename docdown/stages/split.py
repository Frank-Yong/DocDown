"""Stage 1 — PDF validation and splitting helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import subprocess
import tempfile

from docdown.utils.logging import get_logger, log_tool_command


_MAX_FIXED_WIDTH_CHUNKS = 9999


@dataclass(frozen=True)
class PdfValidationResult:
    """Validation metadata extracted from qpdf before splitting."""

    page_count: int
    file_size_bytes: int


class PdfValidationError(ValueError):
    """Raised when input PDF cannot be validated for processing."""


class PdfSplitError(ValueError):
    """Raised when PDF splitting into chunk files fails."""


@dataclass(frozen=True)
class PdfSplitResult:
    """Summary of produced chunk PDFs."""

    chunk_count: int
    chunk_paths: list[Path]


def validate_pdf(input_pdf: Path, password: str | None = None, logger: logging.Logger | None = None) -> PdfValidationResult:
    """Validate PDF with qpdf and return page-count metadata."""

    input_path = Path(input_pdf)
    if not input_path.exists() or not input_path.is_file():
        raise PdfValidationError(f"Input PDF not found: {input_path}")

    active_logger = logger or get_logger()
    encrypted = _is_encrypted(input_path, password)
    if encrypted and password is None:
        raise PdfValidationError(
            "Input PDF is encrypted and requires a password. "
            "Provide a PDF password before running DocDown."
        )

    check_result = _run_qpdf(_qpdf_command("--check", input_path), password=password)
    if check_result.returncode == 2:
        diagnostics = _combined_output(check_result)
        raise PdfValidationError(f"Invalid or corrupted PDF: {diagnostics}")
    if check_result.returncode not in (0, 3):
        diagnostics = _combined_output(check_result)
        raise PdfValidationError(f"qpdf validation failed (exit {check_result.returncode}): {diagnostics}")
    if check_result.returncode == 3:
        active_logger.warning("qpdf reported warnings but PDF is usable: %s", _combined_output(check_result))

    count_result = _run_qpdf(_qpdf_command("--show-npages", input_path), password=password)
    if count_result.returncode != 0:
        diagnostics = _combined_output(count_result)
        raise PdfValidationError(f"Could not determine PDF page count: {diagnostics}")

    page_count = _parse_page_count(count_result.stdout)
    file_size = input_path.stat().st_size
    active_logger.info("Validated PDF: pages=%s size_bytes=%s", page_count, file_size)

    return PdfValidationResult(page_count=page_count, file_size_bytes=file_size)


def split_pdf(
    input_pdf: Path,
    chunks_dir: Path,
    chunk_size: int,
    total_pages: int,
    *,
    password: str | None = None,
    logger: logging.Logger | None = None,
) -> PdfSplitResult:
    """Split input PDF into chunk PDFs and validate each chunk is readable."""

    input_path = Path(input_pdf)
    output_dir = Path(chunks_dir)
    if chunk_size < 1:
        raise PdfSplitError("chunk_size must be at least 1")
    if total_pages < 1:
        raise PdfSplitError("total_pages must be at least 1")
    if not input_path.exists() or not input_path.is_file():
        raise PdfSplitError(f"Input PDF not found: {input_path}")

    active_logger = logger or get_logger()
    output_dir.mkdir(parents=True, exist_ok=True)

    ranges = _compute_chunk_ranges(total_pages=total_pages, chunk_size=chunk_size)
    expected_chunks = len(ranges)
    if expected_chunks > _MAX_FIXED_WIDTH_CHUNKS:
        raise PdfSplitError(
            f"split would produce {expected_chunks} chunks, exceeding fixed 4-digit naming limit "
            f"({_MAX_FIXED_WIDTH_CHUNKS})"
        )

    chunk_paths: list[Path] = []

    for index, (start_page, end_page) in enumerate(ranges, start=1):
        chunk_path = output_dir / _chunk_filename(index=index)
        try:
            split_result = _run_qpdf(
                _qpdf_split_command(input_path, start_page, end_page, chunk_path),
                password=password,
            )
        except PdfValidationError as exc:
            raise PdfSplitError(f"Failed to execute split command for {chunk_path.name}: {exc}") from exc
        if split_result.returncode != 0:
            raise PdfSplitError(
                f"Failed to split pages {start_page}-{end_page} into {chunk_path.name}: "
                f"{_combined_output(split_result)}"
            )
        if not chunk_path.exists() or not chunk_path.is_file():
            raise PdfSplitError(f"Split command did not produce chunk file: {chunk_path}")

        try:
            check_result = _run_qpdf(_qpdf_command("--check", chunk_path), password=password)
        except PdfValidationError as exc:
            raise PdfSplitError(f"Failed to validate chunk {chunk_path.name}: {exc}") from exc
        if check_result.returncode not in (0, 3):
            raise PdfSplitError(f"Chunk {chunk_path.name} is unreadable: {_combined_output(check_result)}")

        chunk_paths.append(chunk_path)

    if len(chunk_paths) != expected_chunks:
        raise PdfSplitError(f"Expected {expected_chunks} chunks, produced {len(chunk_paths)}")

    missing_paths = [path for path in chunk_paths if not path.exists()]
    if missing_paths:
        missing_text = ", ".join(str(path) for path in missing_paths)
        raise PdfSplitError(f"Missing expected chunk files: {missing_text}")

    active_logger.info("Split PDF into %s chunks in %s", expected_chunks, output_dir)
    return PdfSplitResult(chunk_count=expected_chunks, chunk_paths=chunk_paths)


def _is_encrypted(input_path: Path, password: str | None) -> bool:
    result = _run_qpdf(_qpdf_command("--show-encryption", input_path), password=password)
    combined = _combined_output(result).lower()

    if "not encrypted" in combined:
        return False
    if "encrypted" in combined:
        return True

    # When qpdf can't determine encryption state, keep flow strict.
    if result.returncode != 0:
        raise PdfValidationError(f"Could not determine encryption status: {_combined_output(result)}")

    return False


def _qpdf_command(flag: str, input_path: Path) -> list[str]:
    return ["qpdf", flag, str(input_path)]


def _qpdf_split_command(input_path: Path, start_page: int, end_page: int, output_path: Path) -> list[str]:
    return [
        "qpdf",
        str(input_path),
        "--pages",
        ".",
        f"{start_page}-{end_page}",
        "--",
        str(output_path),
    ]


def _run_qpdf(command: list[str], *, password: str | None = None) -> subprocess.CompletedProcess[str]:
    command_to_run, password_file = _inject_password(command, password)
    log_tool_command(_redact_command(command_to_run))
    try:
        return subprocess.run(command_to_run, capture_output=True, text=True, check=False)
    except OSError as exc:
        raise PdfValidationError(f"Failed to execute qpdf command {_redact_command(command_to_run)}: {exc}") from exc
    finally:
        _cleanup_password_file(password_file)


def _inject_password(command: list[str], password: str | None) -> tuple[list[str], Path | None]:
    """Attach password to qpdf command, preferring --password-file over argv."""

    if password is None:
        return list(command), None

    try:
        handle, path_text = tempfile.mkstemp(prefix="docdown-qpdf-", suffix=".pwd", text=True)
        with os.fdopen(handle, "w", encoding="utf-8", newline="\n") as password_file:
            password_file.write(password)
            password_file.write("\n")
        path = Path(path_text)
        return [command[0], f"--password-file={path}", *command[1:]], path
    except OSError:
        # Fallback for environments where temporary files cannot be created.
        return [command[0], f"--password={password}", *command[1:]], None


def _cleanup_password_file(password_file: Path | None) -> None:
    """Best-effort cleanup for temporary password files used by qpdf."""

    if password_file is None:
        return
    try:
        password_file.unlink(missing_ok=True)
    except OSError:
        pass


def _redact_command(command: list[str]) -> str:
    """Render command text while redacting sensitive password arguments."""

    redacted: list[str] = []
    for part in command:
        if part.startswith("--password="):
            redacted.append("--password=***")
        else:
            redacted.append(part)
    return " ".join(redacted)


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
    combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
    return combined if combined else "<no diagnostics>"


def _parse_page_count(stdout: str) -> int:
    text = stdout.strip()
    try:
        page_count = int(text)
    except ValueError as exc:
        raise PdfValidationError(f"Unexpected qpdf --show-npages output: {stdout!r}") from exc

    if page_count < 1:
        raise PdfValidationError(f"qpdf reported invalid page count: {page_count}")
    return page_count


def _compute_chunk_ranges(total_pages: int, chunk_size: int) -> list[tuple[int, int]]:
    """Return inclusive page ranges for chunk extraction."""

    ranges: list[tuple[int, int]] = []
    for start in range(1, total_pages + 1, chunk_size):
        end = min(start + chunk_size - 1, total_pages)
        ranges.append((start, end))
    return ranges


def _chunk_filename(index: int) -> str:
    """Build chunk filename using fixed 4-digit zero padding."""

    return f"chunk-{index:04d}.pdf"
