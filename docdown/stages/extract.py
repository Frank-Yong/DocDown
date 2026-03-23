"""Stage 2 — Content extraction via GROBID."""

from __future__ import annotations

import logging
from pathlib import Path
import time
from typing import Any

import requests

from docdown.utils.logging import get_chunk_logger, get_logger


_DEFAULT_TIMEOUT_SECONDS = 120
_DEFAULT_GROBID_MAX_WAIT_SECONDS = 60
_DEFAULT_GROBID_POLL_INTERVAL_SECONDS = 2
_DEFAULT_503_RETRIES = 3
_DEFAULT_503_BACKOFF_BASE_SECONDS = 5
_MAX_ERROR_BODY_EXCERPT = 300


class GrobidError(ValueError):
	"""Raised when GROBID health checks or extraction requests fail."""


def wait_for_grobid(
	grobid_url: str,
	*,
	max_wait: int = _DEFAULT_GROBID_MAX_WAIT_SECONDS,
	poll_interval: int = _DEFAULT_GROBID_POLL_INTERVAL_SECONDS,
	request_timeout: int = 5,
	session: requests.Session | None = None,
	logger: logging.Logger | None = None,
) -> None:
	"""Poll GROBID /api/isalive until ready or timeout."""

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
	logger: logging.Logger | None = None,
	chunk_number: int | None = None,
) -> Path:
	"""Submit a chunk PDF to GROBID and write TEI XML output."""

	chunk_path = Path(chunk_pdf)
	output_path = Path(output_xml)
	if not chunk_path.exists() or not chunk_path.is_file():
		raise GrobidError(f"Chunk PDF not found: {chunk_path}")

	if chunk_number is not None:
		active_logger = get_chunk_logger(chunk_number)
	else:
		active_logger = logger or get_logger()

	client = session or requests
	endpoint = f"{grobid_url.rstrip('/')}/api/processFulltextDocument"
	started_at = time.monotonic()

	timeout_retry_used = False
	retries_503_used = 0

	while True:
		request_timeout = timeout * 2 if timeout_retry_used else timeout

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
				active_logger.warning(
					"GROBID timeout for %s at %ss; retrying once with %ss",
					chunk_path.name,
					timeout,
					timeout * 2,
				)
				continue
			raise GrobidError(
				f"GROBID timed out for {chunk_path.name} after retry (timeout {timeout * 2}s)."
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

	raise GrobidError(f"GROBID extraction failed for {chunk_path.name}")


def _body_excerpt(text: str, max_chars: int = _MAX_ERROR_BODY_EXCERPT) -> str:
	collapsed = " ".join(text.split())
	if len(collapsed) <= max_chars:
		return collapsed
	return collapsed[:max_chars] + "..."
