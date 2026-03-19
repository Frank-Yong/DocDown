# Task 5.1 — Table Detection & Extraction with Camelot

## Summary

Detect and extract tables from chunk PDFs using Camelot.

## Dependencies

- Task 1.4 (working directory management)

## Acceptance Criteria

- [ ] Each chunk PDF is scanned for tables when `table_extraction` is enabled in config.
- [ ] `lattice` flavour is tried first (bordered tables); `stream` is tried as fallback (borderless).
- [ ] Extracted tables are stored as Camelot `TableList` objects for downstream conversion.
- [ ] Each table's page number and positional data (bounding box) are recorded.
- [ ] Chunks with no tables are skipped cleanly (no error).
- [ ] Camelot errors on a chunk are caught and logged; chunk processing continues.
- [ ] Number of tables found per chunk is logged.
- [ ] Unit tests mock Camelot; integration test uses a PDF with known tables.

## Implementation Notes

### Detection

```python
import camelot

def detect_tables(chunk_path):
    tables = camelot.read_pdf(str(chunk_path), pages="all", flavor="lattice")
    if not tables or all(t.parsing_report["accuracy"] < 50 for t in tables):
        tables = camelot.read_pdf(str(chunk_path), pages="all", flavor="stream")
    return tables
```

### Accuracy filtering

Camelot reports an `accuracy` score per table. Discard tables with accuracy below a threshold (e.g., 40%) to avoid garbage extractions.

### Dependencies

Camelot requires Ghostscript and OpenCV. Document these as system-level prerequisites.

## References

- [technical-design.md §5.4 — Stage 4: Table Extraction](../technical-design.md)
- [spec.md §4.4 — Stage 4: Post-process](../spec.md)
