# Task 9.1 — PyMuPDF Text Extraction

## Summary

Extract text on a per-page basis from chunk PDFs using PyMuPDF, for use in the LLM-assisted pipeline.

## Dependencies

- Task 1.4 (working directory management)

## Acceptance Criteria

- [ ] Text is extracted per page from each chunk PDF using PyMuPDF (`fitz`).
- [ ] Output is a list of `(page_number, text)` tuples per chunk.
- [ ] Empty pages are included (with empty string) to preserve page ordering.
- [ ] Extraction handles PDFs with embedded fonts and Unicode correctly.
- [ ] Per-chunk results are available in memory for the LLM stage (no intermediate file required, but optionally saved for debugging).
- [ ] Unit tests verify extraction from a sample PDF.

## Implementation Notes

### Extraction

```python
import fitz  # PyMuPDF

def extract_pages(chunk_path):
    doc = fitz.open(str(chunk_path))
    pages = []
    for page_num, page in enumerate(doc, start=1):
        text = page.get_text("text")
        pages.append((page_num, text))
    doc.close()
    return pages
```

### When to use

This extractor is only used when `llm_cleanup: true` is set in config. It replaces GROBID/pdfminer as the extraction method in the LLM pipeline path.

### Comparison with pdfminer

PyMuPDF is faster than pdfminer.six for bulk text extraction and handles more PDF variants. However, it also produces flat text without semantic structure — the LLM provides the structure in the next stage.

## References

- [technical-design.md §6.2 — Text Extraction with PyMuPDF](../technical-design.md)
- [spec.md §5 — Alternative Pipeline](../spec.md)
