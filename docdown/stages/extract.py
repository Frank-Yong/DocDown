"""Stage 2 — Content extraction via GROBID and pdfminer fallback."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
import logging
from pathlib import Path
import re
import time

from pdfminer.high_level import extract_text as pdfminer_extract_text
import requests

from docdown.utils.logging import ChunkAdapter, get_chunk_logger, get_logger


_DEFAULT_TIMEOUT_SECONDS = 120
_DEFAULT_GROBID_MAX_WAIT_SECONDS = 60
_DEFAULT_GROBID_POLL_INTERVAL_SECONDS = 2
_DEFAULT_503_RETRIES = 3
_DEFAULT_503_BACKOFF_BASE_SECONDS = 5
_MAX_ERROR_BODY_EXCERPT = 300
_VALID_EXTRACTORS = {"grobid", "pdfminer"}
_CHUNK_STEM_PATTERN = re.compile(r"^chunk-(\d{4})$")

LogLike = logging.Logger | logging.LoggerAdapter


class GrobidError(ValueError):
    """Raised when GROBID health checks or extraction requests fail."""


class PdfMinerError(ValueError):
    """Raised when pdfminer fallback extraction fails."""


class ExtractorUsed(str, Enum):
    GROBID = "grobid"
    PDFMINER = "pdfminer"


@dataclass(frozen=True)
class ExtractionResult:
    chunk_number: int
    success: bool
    extractor: ExtractorUsed | None
    output_path: Path | None
    error: str | None


def wait_for_grobid(
    grobid_url: str,
    *,
    max_wait: int = _DEFAULT_GROBID_MAX_WAIT_SECONDS,
    poll_interval: int = _DEFAULT_GROBID_POLL_INTERVAL_SECONDS,
    request_timeout: int = 5,
    session: requests.Session | None = None,
    logger: LogLike | None = None,
) -> None:
    """Poll GROBID /api/isalive until ready or timeout."""

    if max_wait < 0:
        raise GrobidError(f"max_wait must be >= 0 seconds, got {max_wait}")
    if poll_interval <= 0:
        raise GrobidError(f"poll_interval must be > 0 seconds, got {poll_interval}")
    if request_timeout <= 0:
        raise GrobidError(f"request_timeout must be > 0 seconds, got {request_timeout}")

    active_logger = logger or get_logger()
    client = session or requests
    isalive_url = f"{grobid_url.rstrip('/')}/api/isalive"

    deadline = time.monotonic() + max_wait
    while time.monotonic() <= deadline:
        try:
            response = client.get(isalive_url, timeout=request_timeout)
            if response.status_code == 200 and response.text.strip().lower() == "true":
                active_logger.info("GROBID service is available at %s", grobid_url)
                return
        except requests.RequestException:
            pass
        time.sleep(poll_interval)

    raise GrobidError(
        f"GROBID service did not become ready within {max_wait}s at {isalive_url}. "
        "Start GROBID or switch to fallback extractor."
    )


def extract_grobid_chunk(
    chunk_pdf: Path,
    output_xml: Path,
    grobid_url: str,
    *,
    timeout: int = _DEFAULT_TIMEOUT_SECONDS,
    retries_on_503: int = _DEFAULT_503_RETRIES,
    backoff_base_seconds: int = _DEFAULT_503_BACKOFF_BASE_SECONDS,
    session: requests.Session | None = None,
    logger: LogLike | None = None,
    chunk_number: int | None = None,
) -> Path:
    """Submit a chunk PDF to GROBID and write TEI XML output."""

    if timeout <= 0:
        raise GrobidError(f"timeout must be > 0 seconds, got {timeout}")
    if retries_on_503 < 0:
        raise GrobidError(f"retries_on_503 must be >= 0, got {retries_on_503}")
    if backoff_base_seconds < 0:
        raise GrobidError(f"backoff_base_seconds must be >= 0, got {backoff_base_seconds}")

    chunk_path = Path(chunk_pdf)
    output_path = Path(output_xml)
    if not chunk_path.exists() or not chunk_path.is_file():
        raise GrobidError(f"Chunk PDF not found: {chunk_path}")

    active_logger = _resolve_logger(logger, chunk_number)

    client = session or requests
    endpoint = f"{grobid_url.rstrip('/')}/api/processFulltextDocument"
    started_at = time.monotonic()

    timeout_retry_used = False
    timeout_retry_pending = False
    retries_503_used = 0

    while True:
        request_timeout = timeout * 2 if timeout_retry_pending else timeout
        timeout_retry_pending = False

        try:
            with chunk_path.open("rb") as handle:
                response = client.post(
                    endpoint,
                    files={"input": (chunk_path.name, handle, "application/pdf")},
                    timeout=request_timeout,
                )
        except requests.Timeout as exc:
            if not timeout_retry_used:
                timeout_retry_used = True
                timeout_retry_pending = True
                active_logger.warning(
                    "GROBID timeout for %s at %ss; retrying once with %ss",
                    chunk_path.name,
                    timeout,
                    timeout * 2,
                )
                continue
            raise GrobidError(
                f"GROBID timed out for {chunk_path.name} after retry (timeout {request_timeout}s)."
            ) from exc
        except requests.RequestException as exc:
            raise GrobidError(f"GROBID request failed for {chunk_path.name}: {exc}") from exc

        if response.status_code == 503:
            if retries_503_used < retries_on_503:
                delay = backoff_base_seconds * (2 ** retries_503_used)
                retries_503_used += 1
                active_logger.warning(
                    "GROBID returned 503 for %s (retry %s/%s); retrying in %ss",
                    chunk_path.name,
                    retries_503_used,
                    retries_on_503,
                    delay,
                )
                time.sleep(delay)
                continue

            raise GrobidError(
                f"GROBID returned HTTP 503 for {chunk_path.name} after {retries_on_503} retries: "
                f"{_body_excerpt(response.text)}"
            )

        if response.status_code != 200:
            raise GrobidError(
                f"GROBID error for {chunk_path.name}: HTTP {response.status_code}: "
                f"{_body_excerpt(response.text)}"
            )

        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(response.text, encoding="utf-8")

        elapsed = time.monotonic() - started_at
        active_logger.info("GROBID extraction complete for %s in %.2fs", chunk_path.name, elapsed)
        return output_path


def extract_pdfminer_chunk(
    chunk_pdf: Path,
    output_text: Path,
    *,
    logger: LogLike | None = None,
    chunk_number: int | None = None,
) -> Path:
    """Extract plain text from a chunk PDF using pdfminer and write UTF-8 text output."""

    chunk_path = Path(chunk_pdf)
    output_path = Path(output_text)

    active_logger = _resolve_logger(logger, chunk_number)

    if not chunk_path.exists() or not chunk_path.is_file():
        raise PdfMinerError(f"Chunk PDF not found: {chunk_path}")

    started_at = time.monotonic()

    try:
        text = pdfminer_extract_text(str(chunk_path))
    except Exception as exc:
        active_logger.exception("pdfminer extraction failed for %s", chunk_path.name)
        raise PdfMinerError(f"pdfminer extraction failed for {chunk_path.name}: {exc}") from exc

    if not text.strip():
        active_logger.error("pdfminer produced empty output for %s", chunk_path.name)
        raise PdfMinerError(f"pdfminer produced empty output for {chunk_path.name}")

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(text, encoding="utf-8")

    elapsed = time.monotonic() - started_at
    active_logger.info("pdfminer extraction complete for %s in %.2fs", chunk_path.name, elapsed)
    return output_path


def orchestrate_extraction(
    chunk_paths: list[Path] | tuple[Path, ...],
    extracted_dir: Path,
    *,
    extractor: str = ExtractorUsed.GROBID.value,
    fallback_extractor: str = ExtractorUsed.PDFMINER.value,
    grobid_url: str = "http://localhost:8070",
    logger: LogLike | None = None,
) -> list[ExtractionResult]:
    """Run extraction for each chunk with fallback and per-chunk result tracking."""

    _validate_extractor_name(extractor, "extractor")
    _validate_extractor_name(fallback_extractor, "fallback_extractor")

    active_logger = logger or get_logger()
    output_root = Path(extracted_dir)
    output_root.mkdir(parents=True, exist_ok=True)

    grobid_required = extractor == ExtractorUsed.GROBID.value or fallback_extractor == ExtractorUsed.GROBID.value
    grobid_available = True
    grobid_unavailable_reason: str | None = None
    if grobid_required:
        try:
            wait_for_grobid(grobid_url, logger=active_logger)
        except GrobidError as exc:
            grobid_available = False
            grobid_unavailable_reason = str(exc)
            active_logger.warning(
                "GROBID unavailable; skipping all grobid extraction attempts (extractor=%s, fallback=%s): %s",
                extractor,
                fallback_extractor,
                exc,
            )

    results: list[ExtractionResult] = []

    for chunk_path in chunk_paths:
        chunk = Path(chunk_path)
        try:
            chunk_number = _chunk_number_from_path(chunk)
        except ValueError as exc:
            active_logger.error("Invalid chunk filename for extraction: %s: %s", chunk.name, exc)
            results.append(
                ExtractionResult(
                    chunk_number=0,
                    success=False,
                    extractor=None,
                    output_path=None,
                    error=str(exc),
                )
            )
            continue

        primary_extractor = extractor
        if primary_extractor == ExtractorUsed.GROBID.value and not grobid_available:
            if fallback_extractor == ExtractorUsed.GROBID.value:
                error_text = f"GROBID unavailable and no non-GROBID extractor configured: {grobid_unavailable_reason}"
                active_logger.error("Extractor '%s' failed for %s: %s", primary_extractor, chunk.name, error_text)
                results.append(
                    ExtractionResult(
                        chunk_number=chunk_number,
                        success=False,
                        extractor=None,
                        output_path=None,
                        error=error_text,
                    )
                )
                continue
            primary_extractor = fallback_extractor

        primary_result, primary_error = _run_single_extractor(
            primary_extractor,
            chunk,
            output_root,
            chunk_number,
            grobid_url,
            active_logger,
        )
        if primary_result is not None:
            results.append(primary_result)
            continue

        if primary_extractor != fallback_extractor:
            active_logger.warning(
                "Primary extractor '%s' failed for %s: %s",
                primary_extractor,
                chunk.name,
                primary_error,
            )
            if fallback_extractor == ExtractorUsed.GROBID.value and not grobid_available:
                error_text = f"GROBID unavailable for fallback extraction: {grobid_unavailable_reason}"
                active_logger.error("Fallback extractor '%s' failed for %s: %s", fallback_extractor, chunk.name, error_text)
                results.append(
                    ExtractionResult(
                        chunk_number=chunk_number,
                        success=False,
                        extractor=None,
                        output_path=None,
                        error=error_text,
                    )
                )
                continue
            fallback_result, fallback_error = _run_single_extractor(
                fallback_extractor,
                chunk,
                output_root,
                chunk_number,
                grobid_url,
                active_logger,
            )
            if fallback_result is not None:
                results.append(fallback_result)
                continue
            error_text = str(fallback_error)
            active_logger.error("Fallback extractor '%s' failed for %s: %s", fallback_extractor, chunk.name, error_text)
            results.append(
                ExtractionResult(
                    chunk_number=chunk_number,
                    success=False,
                    extractor=None,
                    output_path=None,
                    error=error_text,
                )
            )
            continue

        error_text = str(primary_error)
        active_logger.error("Extractor '%s' failed for %s: %s", primary_extractor, chunk.name, error_text)
        results.append(
            ExtractionResult(
                chunk_number=chunk_number,
                success=False,
                extractor=None,
                output_path=None,
                error=error_text,
            )
        )

    grobid_successes = sum(1 for result in results if result.extractor == ExtractorUsed.GROBID and result.success)
    pdfminer_successes = sum(1 for result in results if result.extractor == ExtractorUsed.PDFMINER and result.success)
    failures = sum(1 for result in results if not result.success)
    active_logger.info(
        "Extraction summary: %s succeeded (grobid), %s succeeded (pdfminer), %s failed",
        grobid_successes,
        pdfminer_successes,
        failures,
    )

    return results


def _body_excerpt(text: str, max_chars: int = _MAX_ERROR_BODY_EXCERPT) -> str:
    # Stream-normalize whitespace to avoid allocating all tokens for large bodies.
    normalized_chars: list[str] = []
    seen_non_whitespace = False
    pending_space = False
    exceeded_limit = False

    for char in text:
        if char.isspace():
            if seen_non_whitespace:
                pending_space = True
            continue

        if pending_space:
            normalized_chars.append(" ")
            pending_space = False

        normalized_chars.append(char)
        seen_non_whitespace = True

        if len(normalized_chars) > max_chars:
            exceeded_limit = True
            break

    if not exceeded_limit:
        return "".join(normalized_chars)

    return "".join(normalized_chars[:max_chars]) + "..."


def _resolve_logger(
    logger: LogLike | None,
    chunk_number: int | None,
) -> LogLike | ChunkAdapter:
    if chunk_number is None:
        return logger or get_logger()
    if logger is None:
        return get_chunk_logger(chunk_number)
    return ChunkAdapter(logger, {"chunk": chunk_number})


def _validate_extractor_name(value: str, field_name: str) -> None:
    if value not in _VALID_EXTRACTORS:
        raise ValueError(f"{field_name} must be one of: {sorted(_VALID_EXTRACTORS)}")


def _chunk_number_from_path(path: Path) -> int:
    match = _CHUNK_STEM_PATTERN.match(path.stem)
    if not match:
        raise ValueError(f"Chunk filename must match 'chunk-NNNN.pdf', got: {path.name}")
    chunk_number = int(match.group(1))
    if chunk_number < 1:
        raise ValueError(f"Chunk filename must use chunk number >= 0001, got: {path.name}")
    return chunk_number


def _run_single_extractor(
    extractor_name: str,
    chunk_path: Path,
    extracted_dir: Path,
    chunk_number: int,
    grobid_url: str,
    logger: LogLike,
) -> tuple[ExtractionResult | None, Exception | None]:
    try:
        if extractor_name == ExtractorUsed.GROBID.value:
            output_path = extracted_dir / f"chunk-{chunk_number:04d}.xml"
            final_path = extract_grobid_chunk(
                chunk_path,
                output_path,
                grobid_url,
                logger=logger,
                chunk_number=chunk_number,
            )
            return (
                ExtractionResult(
                    chunk_number=chunk_number,
                    success=True,
                    extractor=ExtractorUsed.GROBID,
                    output_path=final_path,
                    error=None,
                ),
                None,
            )

        output_path = extracted_dir / f"chunk-{chunk_number:04d}.txt"
        final_path = extract_pdfminer_chunk(
            chunk_path,
            output_path,
            logger=logger,
            chunk_number=chunk_number,
        )
        return (
            ExtractionResult(
                chunk_number=chunk_number,
                success=True,
                extractor=ExtractorUsed.PDFMINER,
                output_path=final_path,
                error=None,
            ),
            None,
        )
    except (GrobidError, PdfMinerError, ValueError) as exc:
        return None, exc
