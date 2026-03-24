"""Stage 3 — Markdown conversion with Pandoc."""

from __future__ import annotations

import logging
from pathlib import Path
import subprocess
import time

from docdown.utils.logging import get_logger, log_tool_command


_FORMAT_BY_SUFFIX = {
	".xml": "tei",
	# Pandoc does not support a generic "plain" input reader; treat raw text as markdown.
	".txt": "markdown",
}

LogLike = logging.Logger | logging.LoggerAdapter


class PandocError(ValueError):
	"""Raised when Pandoc is unavailable or conversion fails."""


def ensure_pandoc_available(*, logger: LogLike | None = None) -> None:
	"""Verify Pandoc is installed and executable."""

	active_logger = logger or get_logger()
	command = ["pandoc", "--version"]
	log_tool_command(command)
	try:
		result = subprocess.run(command, capture_output=True, text=True, check=False)
	except OSError as exc:
		raise PandocError(
			"Pandoc is not available on PATH. Install Pandoc to enable Markdown conversion."
		) from exc

	if result.returncode != 0:
		diagnostics = _combined_output(result)
		raise PandocError(f"Pandoc availability check failed: {diagnostics}")

	first_line = next((line for line in result.stdout.splitlines() if line.strip()), "pandoc")
	active_logger.info("Pandoc available: %s", first_line)


def convert_to_markdown(
	input_path: Path,
	output_path: Path,
	*,
	logger: LogLike | None = None,
	chunk_number: int | None = None,
) -> Path:
	"""Convert extracted XML/TXT artifact to GFM Markdown via Pandoc."""

	source = Path(input_path)
	target = Path(output_path)
	active_logger = logger or get_logger()

	if not source.exists() or not source.is_file():
		raise PandocError(f"Conversion input not found: {source}")

	source_format = _input_format_for_path(source)

	target.parent.mkdir(parents=True, exist_ok=True)
	command = [
		"pandoc",
		str(source),
		"-f",
		source_format,
		"-t",
		"gfm",
		"--wrap=none",
		"-o",
		str(target),
	]
	log_tool_command(command, chunk_number=chunk_number)

	started = time.monotonic()
	try:
		result = subprocess.run(command, capture_output=True, text=True, check=False)
	except OSError as exc:
		raise PandocError(f"Failed to execute pandoc for {source.name}: {exc}") from exc

	if result.returncode != 0:
		diagnostics = _combined_output(result)
		raise PandocError(f"Pandoc conversion failed for {source.name}: {diagnostics}")

	elapsed = time.monotonic() - started
	active_logger.info("Pandoc conversion complete for %s in %.2fs", source.name, elapsed)
	return target


def _input_format_for_path(path: Path) -> str:
	suffix = path.suffix.lower()
	if suffix not in _FORMAT_BY_SUFFIX:
		raise PandocError(
			f"Unsupported conversion input extension '{path.suffix}' for {path.name}; expected .xml or .txt"
		)
	return _FORMAT_BY_SUFFIX[suffix]


def _combined_output(result: subprocess.CompletedProcess[str]) -> str:
	combined = "\n".join(part.strip() for part in (result.stdout, result.stderr) if part and part.strip())
	return combined if combined else "<no diagnostics>"
