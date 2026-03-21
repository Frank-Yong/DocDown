"""Working directory management for DocDown artifacts."""

from __future__ import annotations

import shutil
from pathlib import Path


_WORKDIR_SUBDIRS = ("input", "chunks", "extracted", "markdown", "tables")


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
        """Place the input PDF in workdir/input as a symlink or copied file."""

        source = Path(source_pdf)
        if not source.exists() or not source.is_file():
            raise WorkDirError(f"input file not found: {source}")

        target = self.input_dir / "source.pdf"

        if target.exists() or target.is_symlink():
            if target.is_dir():
                raise WorkDirError(f"staged input path is a directory: {target}")
            try:
                if target.resolve() == source.resolve():
                    return target
            except OSError:
                pass
            try:
                target.unlink()
            except OSError as exc:
                raise WorkDirError(f"failed to replace staged input at {target}: {exc}") from exc

        try:
            target.symlink_to(source.resolve())
        except OSError:
            try:
                shutil.copy2(source, target)
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
            extension = ext or "xml"
            return self.extracted_dir / f"{chunk_token}.{extension}"

        if artifact_type == "markdown":
            extension = ext or "md"
            return self.markdown_dir / f"{chunk_token}.{extension}"

        if artifact_type == "tables":
            if table_number is None or table_number < 1:
                raise WorkDirError("tables artifacts require table_number >= 1")
            extension = ext or "md"
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
