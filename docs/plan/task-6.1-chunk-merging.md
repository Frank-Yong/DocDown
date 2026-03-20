# Task 6.1 — Chunk Merging

## Summary

Concatenate all chunk Markdown files into a single merged document in correct order.

## Dependencies

- Task 4.2 (Markdown cleanup — chunk .md files ready)

## Acceptance Criteria

- [ ] All chunk Markdown files in `workdir/markdown/` are concatenated in numeric order.
- [ ] A horizontal rule (`---`) is inserted between chunks as a visual separator.
- [ ] Failed/missing chunks are skipped with a placeholder comment: `<!-- chunk-NNNN: extraction failed -->`.
- [ ] Output is written to `workdir/merged.md`.
- [ ] Total line count and file size of merged output are logged.
- [ ] Unit tests verify: correct ordering, separator insertion, missing-chunk handling.

## Implementation Notes

### Implementation

```python
def merge_chunks(markdown_dir, output_path, total_chunks):
    parts = []
    for i in range(1, total_chunks + 1):
        chunk_path = markdown_dir / f"chunk-{i:04d}.md"
        if chunk_path.exists() and chunk_path.stat().st_size > 0:
            parts.append(chunk_path.read_text(encoding="utf-8"))
        else:
            parts.append(f"<!-- chunk-{i:04d}: extraction failed -->\n")
    
    merged = "\n\n---\n\n".join(parts)
    output_path.write_text(merged, encoding="utf-8")
```

### Ordering

Rely on the `chunk-NNNN` naming convention. Sort numerically, not lexicographically (avoids `chunk-10` before `chunk-2` issues).

## References

- [technical-design.md §5.5.1 — Merge](../technical-design.md)
- [spec.md §4.5 — Stage 5: Merge & Generate TOC](../spec.md)
