"""Stage 1 — PDF validation and splitting helpers."""

from __future__ import annotations

from dataclasses import dataclass
import logging
import os
from pathlib import Path
import subprocess
import tempfile

from docdown.utils.logging import get_logger, log_tool_command


@dataclass(frozen=True)
class PdfValidationResult:
    """Validation metadata extracted from qpdf before splitting."""

    page_count: int
    file_size_bytes: int


class PdfValidationError(ValueError):
    """Raised when input PDF cannot be validated for processing."""


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
