# Task 2.2 — Chunk Splitting with qpdf

## Summary

Split the validated PDF into page-range chunks using `qpdf`.

## Dependencies

- Task 2.1 (PDF validation & page counting)

## Acceptance Criteria

- [x] PDF is split into chunks of `chunk_size` pages (configurable, default 50).
- [x] Last chunk contains the remaining pages (may be smaller than `chunk_size`).
- [x] Output files follow naming convention: `chunk-0001.pdf`, `chunk-0002.pdf`, etc.
- [x] Output files are written to `workdir/chunks/`.
- [x] Chunk count is verified: `ceil(total_pages / chunk_size)` chunks exist.
- [x] Each chunk is validated as a readable PDF.
- [x] Splitting a PDF with fewer pages than `chunk_size` produces a single chunk.
- [x] Integration test: split a multi-page PDF and verify chunk count and page ranges.

Implemented in:
- `docdown/stages/split.py`
- `tests/test_split.py`

## Implementation Notes

### Splitting logic

```python
import math, subprocess

def split_pdf(input_path, chunks_dir, chunk_size, total_pages):
    num_chunks = math.ceil(total_pages / chunk_size)
    for i in range(num_chunks):
        start = i * chunk_size + 1
        end = min((i + 1) * chunk_size, total_pages)
        output = chunks_dir / f"chunk-{i+1:04d}.pdf"
        subprocess.run([
            "qpdf", str(input_path),
            "--pages", ".", f"{start}-{end}", "--",
            str(output)
        ], check=True)
    return num_chunks
```

### Edge cases

- Single-page PDF → one chunk.
- PDF with exactly `chunk_size` pages → one chunk.
- Very large page counts (10,000+) → works as long as the resulting chunk count stays within the fixed-width naming scheme. The current 4-digit convention supports up to 9,999 chunks; if `num_chunks` can exceed that, derive the padding width from `num_chunks` instead of assuming 4 digits.

### Artifact Class Diagram

```mermaid
classDiagram
    class PdfSplitResult {
        +int chunk_count
        +list~Path~ chunk_paths
    }

    class PdfSplitError {
        <<exception>>
    }

    class SplitStageModule {
        <<module: docdown/stages/split.py>>
        +split_pdf(input_pdf, chunks_dir, chunk_size, total_pages, password, logger) PdfSplitResult
        -_compute_chunk_ranges(total_pages, chunk_size) list~tuple~int,int~~
        -_chunk_filename(index, total_chunks) str
        -_qpdf_split_command(input_path, start_page, end_page, output_path) list~str~
        -_run_qpdf(command, password) CompletedProcess
        -_qpdf_command(flag, input_path) list~str~
    }

    class WorkDir {
        <<module: docdown/workdir.py>>
        +chunk_pdf(chunk_number) Path
        +chunks_dir Path
    }

    class QpdfTool {
        <<external: qpdf>>
        +--pages . start-end -- output.pdf
        +--check chunk.pdf
    }

    class ChunkArtifacts {
        <<workdir/chunks>>
        +chunk-0001.pdf
        +chunk-0002.pdf
        +...
    }

    class LoggingModule {
        <<module: docdown/utils/logging.py>>
        +get_logger() Logger
        +log_tool_command(command, chunk_number) None
    }

    class TestSplit {
        <<tests/test_split.py>>
        +single chunk case
        +multi-range integration-style case
        +chunk readability failure case
        +invalid chunk_size case
    }

    SplitStageModule --> PdfSplitResult : returns
    SplitStageModule ..> PdfSplitError : raises
    SplitStageModule ..> QpdfTool : executes split and check
    SplitStageModule ..> LoggingModule : debug tool-command logs
    SplitStageModule ..> WorkDir : consumes chunk directory contract
    WorkDir --> ChunkArtifacts : path contract
    TestSplit ..> SplitStageModule : verifies behavior
```

## References

- [technical-design.md §5.1 — Stage 1: Split](../technical-design.md)
- [spec.md §4.1 — Stage 1: Split](../spec.md)
