"""Working directory management for DocDown artifacts."""

from __future__ import annotations

import json
import shutil
from pathlib import Path


_WORKDIR_SUBDIRS = ("input", "chunks", "extracted", "markdown", "tables")
_INPUT_MANIFEST_NAME = "source.manifest.json"


class WorkDirError(ValueError):
    """Raised when workdir initialization or staging fails."""


class WorkDir:
    """Helper for creating and addressing run artifacts under a workdir."""

    def __init__(self, base: Path):
        self.base = Path(base)

    @property
    def input_dir(self) -> Path:
        return self.base / "input"

    @property
    def chunks_dir(self) -> Path:
        return self.base / "chunks"

    @property
    def extracted_dir(self) -> Path:
        return self.base / "extracted"

    @property
    def markdown_dir(self) -> Path:
        return self.base / "markdown"

    @property
    def tables_dir(self) -> Path:
        return self.base / "tables"

    def ensure_structure(self) -> None:
        """Create the base workdir and required subdirectories if missing."""

        if self.base.exists() and not self.base.is_dir():
            raise WorkDirError(f"workdir must be a directory: {self.base}")

        try:
            self.base.mkdir(parents=True, exist_ok=True)
            for name in _WORKDIR_SUBDIRS:
                (self.base / name).mkdir(parents=True, exist_ok=True)
        except OSError as exc:
            raise WorkDirError(f"failed to create workdir structure at {self.base}: {exc}") from exc

    def stage_input(self, source_pdf: Path) -> Path:
        """Stage the input PDF at workdir/input/source.pdf via symlink or copy."""

        source = Path(source_pdf)
        if not source.exists() or not source.is_file():
            raise WorkDirError(f"input file not found: {source}")

        # Allow direct stage_input() calls without requiring ensure_structure() first.
        self.ensure_structure()

        target = self.input_dir / "source.pdf"
        manifest_path = self.input_dir / _INPUT_MANIFEST_NAME

        if target.exists() or target.is_symlink():
            if target.is_dir():
                raise WorkDirError(f"staged input path is a directory: {target}")
            try:
                if target.resolve() == source.resolve():
                    return target
            except OSError:
                pass
            if _copy_manifest_matches(source, target, manifest_path):
                return target
            try:
                target.unlink()
            except OSError as exc:
                raise WorkDirError(f"failed to replace staged input at {target}: {exc}") from exc

        try:
            target.symlink_to(source.resolve())
            _delete_manifest_if_exists(manifest_path)
        except OSError:
            try:
                shutil.copy2(source, target)
                _write_copy_manifest(manifest_path, source, target)
            except OSError as exc:
                raise WorkDirError(f"failed to stage input into {target}: {exc}") from exc

        return target

    def artifact_path(
        self,
        artifact_type: str,
        chunk_number: int,
        *,
        ext: str | None = None,
        table_number: int | None = None,
    ) -> Path:
        """Return artifact path by type and chunk number."""

        if chunk_number < 1:
            raise WorkDirError("chunk_number must be >= 1")

        chunk_token = f"chunk-{chunk_number:04d}"

        if artifact_type == "chunks":
            return self.chunks_dir / f"{chunk_token}.pdf"

        if artifact_type == "extracted":
            extension = _normalize_extension(ext or "xml")
            return self.extracted_dir / f"{chunk_token}.{extension}"

        if artifact_type == "markdown":
            extension = _normalize_extension(ext or "md")
            return self.markdown_dir / f"{chunk_token}.{extension}"

        if artifact_type == "tables":
            if table_number is None or table_number < 1:
                raise WorkDirError("tables artifacts require table_number >= 1")
            extension = _normalize_extension(ext or "md")
            return self.tables_dir / f"{chunk_token}-table-{table_number:03d}.{extension}"

        raise WorkDirError(f"unknown artifact_type: {artifact_type}")

    def chunk_pdf(self, chunk_number: int) -> Path:
        return self.artifact_path("chunks", chunk_number)

    def extracted(self, chunk_number: int, ext: str = "xml") -> Path:
        return self.artifact_path("extracted", chunk_number, ext=ext)

    def markdown(self, chunk_number: int, ext: str = "md") -> Path:
        return self.artifact_path("markdown", chunk_number, ext=ext)

    def table_markdown(self, chunk_number: int, table_number: int, ext: str = "md") -> Path:
        return self.artifact_path("tables", chunk_number, ext=ext, table_number=table_number)

    def merged_markdown(self) -> Path:
        return self.base / "merged.md"

    def final_markdown(self) -> Path:
        return self.base / "final.md"


def _copy_manifest_matches(source: Path, target: Path, manifest_path: Path) -> bool:
    """Return True when cached metadata says the copied input is up-to-date."""

    if not target.exists() or target.is_symlink():
        return False

    manifest = _read_manifest(manifest_path)
    if manifest is None:
        return False

    expected_source = manifest.get("source")
    expected_target = manifest.get("target")
    if not isinstance(expected_source, dict) or not isinstance(expected_target, dict):
        return False

    current_source = _source_fingerprint(source)
    current_target = _target_fingerprint(target)
    return current_source == expected_source and current_target == expected_target


def _write_copy_manifest(manifest_path: Path, source: Path, target: Path) -> None:
    """Write lightweight metadata used to skip redundant copy fallback operations."""

    manifest = {
        "source": _source_fingerprint(source),
        "target": _target_fingerprint(target),
    }
    manifest_path.write_text(json.dumps(manifest, sort_keys=True), encoding="utf-8")


def _read_manifest(manifest_path: Path) -> dict[str, object] | None:
    """Read copy manifest data and return None when unavailable or invalid."""

    try:
        raw = manifest_path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except (OSError, ValueError):
        return None
    return data if isinstance(data, dict) else None


def _delete_manifest_if_exists(manifest_path: Path) -> None:
    """Best-effort cleanup for stale copy manifests after symlink staging."""

    try:
        if manifest_path.exists():
            manifest_path.unlink()
    except OSError:
        pass


def _source_fingerprint(path: Path) -> dict[str, object]:
    """Return source metadata used to detect whether staging input changed."""

    stat = path.stat()
    try:
        resolved = str(path.resolve())
    except OSError:
        resolved = str(path.absolute())
    return {
        "path": resolved,
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _target_fingerprint(path: Path) -> dict[str, object]:
    """Return staged target metadata for copy-manifest validation."""

    stat = path.stat()
    return {
        "size": stat.st_size,
        "mtime_ns": stat.st_mtime_ns,
    }


def _normalize_extension(ext: str) -> str:
    """Normalize and validate extension tokens used in generated filenames."""

    normalized = str(ext).lstrip(".")
    if not normalized:
        raise WorkDirError("ext must not be empty.")
    if "/" in normalized or "\\" in normalized or ".." in normalized:
        raise WorkDirError("ext must not contain path separators or '..'.")
    return normalized
