# Task 8.2 — Final Output Validation

## Summary

Validate the merged final Markdown output for completeness and structural integrity.

## Dependencies

- Task 6.2 (TOC generation — `final.md` must exist)

## Acceptance Criteria

- [x] `final.md` file size is checked: if < 1% of source PDF size, log a warning.
- [x] Failed chunk count is checked against `max_empty_chunks` config; if exceeded, abort.
- [x] TOC presence is verified (at least one `- [` link pattern at the top of the file).
- [x] Duplicate content detection: identical paragraphs (>50 words) in adjacent chunk boundaries are flagged.
- [x] All validation results are collected for the run summary.
- [x] Unit tests cover each check.

Implemented in:
- `docdown/stages/final_validation.py`
- `docdown/cli.py`
- `tests/test_final_validation.py`
- `tests/test_cli.py`

## Implementation Notes

### Size check

```python
def validate_final(final_path, source_pdf_path, chunk_results, config):
    issues = []
    
    final_size = final_path.stat().st_size
    source_size = source_pdf_path.stat().st_size
    if final_size / source_size < 0.01:
        issues.append(f"Final output suspiciously small: {final_size} bytes vs {source_size} bytes source")
```

### Failed chunk threshold

```python
    failed_count = sum(1 for r in chunk_results if not r.success)
    if failed_count > config.validation.max_empty_chunks:
        raise FatalPipelineError(
            f"{failed_count} chunks failed (max allowed: {config.validation.max_empty_chunks})"
        )
```

### Duplicate detection

At chunk boundaries (last ~200 chars of chunk N, first ~200 chars of chunk N+1), check for overlapping text. This catches cases where qpdf split pages that overlap or extractors duplicated boundary content.

## References

- [technical-design.md §8.2 — Final Output Validation](../technical-design.md)
