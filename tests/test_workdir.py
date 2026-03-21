"""Tests for workdir management helpers."""

from pathlib import Path

import pytest

from docdown.workdir import WorkDir, WorkDirError


def test_workdir_creates_expected_subdirectories(tmp_path):
    workdir = WorkDir(tmp_path / "output")
    workdir.ensure_structure()

    assert workdir.base.exists()
    assert workdir.input_dir.is_dir()
    assert workdir.chunks_dir.is_dir()
    assert workdir.extracted_dir.is_dir()
    assert workdir.markdown_dir.is_dir()
    assert workdir.tables_dir.is_dir()


def test_workdir_resume_keeps_existing_files(tmp_path):
    workdir = WorkDir(tmp_path / "output")
    workdir.ensure_structure()

    marker = workdir.markdown_dir / "keep.md"
    marker.write_text("existing", encoding="utf-8")

    workdir.ensure_structure()

    assert marker.exists()
    assert marker.read_text(encoding="utf-8") == "existing"


def test_stage_input_symlink_or_copy_into_input_directory(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    workdir = WorkDir(tmp_path / "output")
    workdir.ensure_structure()

    staged = workdir.stage_input(source)

    assert staged == workdir.input_dir / "source.pdf"
    assert staged.exists()
    assert staged.read_bytes() == source.read_bytes()


def test_stage_input_creates_structure_when_missing(tmp_path):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    workdir = WorkDir(tmp_path / "output")
    staged = workdir.stage_input(source)

    assert workdir.input_dir.is_dir()
    assert staged == workdir.input_dir / "source.pdf"
    assert staged.exists()


def test_artifact_path_generation_for_chunk_outputs(tmp_path):
    workdir = WorkDir(tmp_path / "output")

    assert workdir.chunk_pdf(3) == workdir.base / "chunks" / "chunk-0003.pdf"
    assert workdir.extracted(3) == workdir.base / "extracted" / "chunk-0003.xml"
    assert workdir.markdown(3) == workdir.base / "markdown" / "chunk-0003.md"
    assert workdir.table_markdown(3, 2) == workdir.base / "tables" / "chunk-0003-table-002.md"
    assert workdir.merged_markdown() == workdir.base / "merged.md"
    assert workdir.final_markdown() == workdir.base / "final.md"


def test_artifact_path_rejects_invalid_inputs(tmp_path):
    workdir = WorkDir(tmp_path / "output")

    with pytest.raises(WorkDirError, match="chunk_number must be >= 1"):
        workdir.artifact_path("chunks", 0)

    with pytest.raises(WorkDirError, match="require table_number"):
        workdir.artifact_path("tables", 1)

    with pytest.raises(WorkDirError, match="unknown artifact_type"):
        workdir.artifact_path("unknown", 1)


def test_stage_input_replaces_previous_staged_file(tmp_path):
    source_a = tmp_path / "a.pdf"
    source_b = tmp_path / "b.pdf"
    source_a.write_bytes(b"%PDF-1.4 A\n")
    source_b.write_bytes(b"%PDF-1.4 B\n")

    workdir = WorkDir(tmp_path / "output")
    workdir.ensure_structure()

    first = workdir.stage_input(source_a)
    second = workdir.stage_input(source_b)

    assert first == second
    assert second.read_bytes() == source_b.read_bytes()


def test_ensure_structure_rejects_file_as_workdir(tmp_path):
    not_dir = tmp_path / "not-dir"
    not_dir.write_text("x", encoding="utf-8")

    with pytest.raises(WorkDirError, match="workdir must be a directory"):
        WorkDir(not_dir).ensure_structure()


def test_ensure_structure_wraps_oserror(tmp_path, monkeypatch):
    workdir = WorkDir(tmp_path / "output")
    original_mkdir = Path.mkdir

    def _failing_mkdir(self, *args, **kwargs):
        if self == workdir.base:
            raise PermissionError("permission denied")
        return original_mkdir(self, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", _failing_mkdir)

    with pytest.raises(WorkDirError, match="failed to create workdir structure"):
        workdir.ensure_structure()


def test_stage_input_wraps_unlink_oserror(tmp_path, monkeypatch):
    source_a = tmp_path / "a.pdf"
    source_b = tmp_path / "b.pdf"
    source_a.write_bytes(b"%PDF-1.4 A\n")
    source_b.write_bytes(b"%PDF-1.4 B\n")

    workdir = WorkDir(tmp_path / "output")
    workdir.ensure_structure()
    workdir.stage_input(source_a)

    original_unlink = Path.unlink

    def _failing_unlink(self, *args, **kwargs):
        if self == workdir.input_dir / "source.pdf":
            raise PermissionError("cannot remove")
        return original_unlink(self, *args, **kwargs)

    monkeypatch.setattr(Path, "unlink", _failing_unlink)

    with pytest.raises(WorkDirError, match="failed to replace staged input"):
        workdir.stage_input(source_b)


def test_stage_input_wraps_copy_oserror(tmp_path, monkeypatch):
    source = tmp_path / "source.pdf"
    source.write_bytes(b"%PDF-1.4\n")

    workdir = WorkDir(tmp_path / "output")
    workdir.ensure_structure()

    def _failing_symlink(self, target):
        raise OSError("symlink disabled")

    def _failing_copy(src, dst, *, follow_symlinks=True):
        raise OSError("copy failed")

    monkeypatch.setattr(Path, "symlink_to", _failing_symlink)
    monkeypatch.setattr("docdown.workdir.shutil.copy2", _failing_copy)

    with pytest.raises(WorkDirError, match="failed to stage input into"):
        workdir.stage_input(source)
