# Task 1.4 — Working Directory Management

## Summary

Create and manage the working directory structure where all intermediate and output files are stored.

## Dependencies

- Task 1.2 (configuration — needs `workdir` path)

## Acceptance Criteria

- [x] Working directory is created at the configured `workdir` path.
- [x] Subdirectories are created: `input/`, `chunks/`, `extracted/`, `markdown/`, `tables/`.
- [x] If `workdir` already exists, pipeline resumes without deleting previous files (allows reprocessing).
- [x] Input PDF is copied or symlinked into `input/`.
- [x] A helper function returns the path for any artifact given its type and chunk number.
- [x] Unit tests verify directory creation and path generation.

Implemented in:
- `docdown/workdir.py`
- `docdown/cli.py`
- `tests/test_workdir.py`

## Implementation Notes

### Directory structure

```
workdir/
├── input/
├── chunks/
├── extracted/
├── markdown/
├── tables/
├── merged.md
├── final.md
└── run.log
```

### Path helper

```python
class WorkDir:
    def __init__(self, base: Path):
        self.base = base
    
    def chunk_pdf(self, n: int) -> Path:
        return self.base / "chunks" / f"chunk-{n:04d}.pdf"
    
    def extracted(self, n: int, ext: str = "xml") -> Path:
        return self.base / "extracted" / f"chunk-{n:04d}.{ext}"
    
    def markdown(self, n: int) -> Path:
        return self.base / "markdown" / f"chunk-{n:04d}.md"
    
    # etc.
```

### Artifact Class Diagram

```mermaid
classDiagram
    class WorkDirError {
        <<exception>>
    }

    class WorkDir {
        +Path base
        +Path input_dir
        +Path chunks_dir
        +Path extracted_dir
        +Path markdown_dir
        +Path tables_dir
        +ensure_structure() None
        +stage_input(source_pdf) Path
        +artifact_path(artifact_type, chunk_number, ext, table_number) Path
        +chunk_pdf(chunk_number) Path
        +extracted(chunk_number, ext) Path
        +markdown(chunk_number, ext) Path
        +table_markdown(chunk_number, table_number, ext) Path
        +merged_markdown() Path
        +final_markdown() Path
    }

    class WorkdirModule {
        <<module: docdown/workdir.py>>
        +_copy_manifest_matches(source, target, manifest_path) bool
        +_write_copy_manifest(manifest_path, source, target) None
        +_read_manifest(manifest_path) dict?
        +_delete_manifest_if_exists(manifest_path) None
        +_normalize_extension(ext) str
    }

    class CliMain {
        <<module: docdown/cli.py>>
        +main(..., workdir) None
    }

    class SplitStage {
        <<module: docdown/stages/split.py>>
        +validate_pdf(input_pdf, password, logger) PdfValidationResult
    }

    class InputArtifacts {
        <<workdir/input>>
        +source.pdf
        +source.manifest.json
    }

    class OutputArtifacts {
        <<workdir outputs>>
        +chunks/chunk-NNNN.pdf
        +extracted/chunk-NNNN.xml
        +markdown/chunk-NNNN.md
        +tables/chunk-NNNN-table-NNN.md
        +merged.md
        +final.md
        +run.log
    }

    class TestWorkDir {
        <<tests/test_workdir.py>>
        +structure/staging/path/error coverage
    }

    WorkdirModule --> WorkDir : defines
    WorkdirModule ..> WorkDirError : raises
    CliMain ..> WorkDir : initializes/stages input
    SplitStage ..> WorkDir : consumes staged input layout
    WorkDir --> InputArtifacts : manages
    WorkDir --> OutputArtifacts : generates paths
    TestWorkDir ..> WorkdirModule : verifies behavior
```

## References

- [technical-design.md §3 — Directory & File Layout](../technical-design.md)
