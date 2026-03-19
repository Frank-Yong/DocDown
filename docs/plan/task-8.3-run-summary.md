# Task 8.3 — Run Summary Generation

## Summary

Generate and display a human-readable summary of the pipeline run.

## Dependencies

- Task 8.2 (final validation — all results collected)

## Acceptance Criteria

- [ ] Summary is printed to stderr at the end of the run.
- [ ] Summary is also appended to `run.log`.
- [ ] Summary includes: input file name and size, total pages, chunk count, successful/failed chunks, tables found, output file size, total duration, and warning count.
- [ ] Failed chunks are listed with their error messages.
- [ ] Summary format is consistent and parseable.
- [ ] Unit test verifies summary format with mock data.

## Implementation Notes

### Format

```
DocDown Run Summary
───────────────────
Input:          source.pdf (342 MB, 1847 pages)
Chunks:         37
Successful:     36
Failed:         1 (chunk-023: GROBID timeout + pdfminer encoding error)
Tables found:   14
Output:         final.md (4.2 MB)
Duration:       12m 34s
Warnings:       2 (see run.log)
```

### Implementation

```python
def generate_summary(run_context):
    failed_details = ""
    if run_context.failed_chunks:
        details = "; ".join(
            f"chunk-{r.chunk_number:03d}: {r.error}"
            for r in run_context.failed_chunks
        )
        failed_details = f" ({details})"
    
    summary = f"""
DocDown Run Summary
───────────────────
Input:          {run_context.input_name} ({format_size(run_context.input_size)}, {run_context.total_pages} pages)
Chunks:         {run_context.total_chunks}
Successful:     {run_context.successful_chunks}
Failed:         {run_context.failed_chunk_count}{failed_details}
Tables found:   {run_context.tables_found}
Output:         final.md ({format_size(run_context.output_size)})
Duration:       {format_duration(run_context.duration)}
Warnings:       {run_context.warning_count} (see run.log)
"""
    return summary.strip()
```

### Timing

Record `start_time` at pipeline start. Compute duration at summary generation.

## References

- [technical-design.md §8.3 — Run Summary](../technical-design.md)
