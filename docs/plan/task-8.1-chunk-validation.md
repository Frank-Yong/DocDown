# Task 8.1 — Per-Chunk Validation

## Summary

Validate each chunk's Markdown output after conversion to detect missing or corrupt content.

## Dependencies

- Task 4.2 (Markdown cleanup — chunk .md files ready)

## Acceptance Criteria

- [x] Each chunk Markdown file is checked after conversion.
- [x] Checks performed:
    - [x] Empty output (0 bytes) → marked as failed.
    - [x] Suspiciously small output (< `min_output_ratio` × chunk PDF size) → warning logged.
    - [x] Invalid UTF-8 encoding → marked as failed.
    - [x] No headings detected when chunk is expected to have structure → warning logged.
- [x] Validation results are attached to the `ChunkResult` for downstream reporting.
- [x] Validation does not modify the Markdown files.
- [x] Unit tests cover each check condition.

Implemented in:
- `docdown/stages/chunk_validation.py`
- `docdown/cli.py`
- `tests/test_chunk_validation.py`
- `tests/test_cli.py`

## Implementation Notes

### Implementation

```python
def validate_chunk(chunk_md_path, chunk_pdf_path, config):
    issues = []
    
    # Empty check
    if not chunk_md_path.exists() or chunk_md_path.stat().st_size == 0:
        return ValidationResult(valid=False, issues=["Empty output"])
    
    # Encoding check
    try:
        text = chunk_md_path.read_text(encoding="utf-8")
    except UnicodeDecodeError:
        return ValidationResult(valid=False, issues=["Invalid UTF-8 encoding"])
    
    # Size ratio check
    pdf_size = chunk_pdf_path.stat().st_size
    md_size = chunk_md_path.stat().st_size
    ratio = md_size / pdf_size if pdf_size > 0 else 0
    if ratio < config.validation.min_output_ratio:
        issues.append(f"Output ratio {ratio:.4f} below threshold {config.validation.min_output_ratio}")
    
    # Heading check
    if not re.search(r"^#{1,6} ", text, re.MULTILINE):
        issues.append("No headings detected")
    
    return ValidationResult(valid=True, issues=issues)
```

### When to run

Validation runs immediately after each chunk's conversion + cleanup, inside the per-chunk worker (before table merging). This allows early detection of problems.

## References

- [technical-design.md §8.1 — Per-Chunk Validation](../technical-design.md)
