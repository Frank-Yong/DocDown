# Task 5.3 — Table Merging into Chunk Markdown

## Summary

Insert extracted Markdown tables into their corresponding chunk Markdown files at the correct position.

## Dependencies

- Task 4.2 (Markdown cleanup — chunk .md files must exist)
- Task 5.2 (table-to-Markdown conversion)

## Acceptance Criteria

- [ ] Each extracted table is inserted into the corresponding chunk Markdown near its original location.
- [ ] Table placement uses page number and surrounding text context to determine insertion point.
- [ ] Tables that cannot be placed are appended at the end of the chunk with a `<!-- unplaced table -->` comment.
- [ ] Original (mangled) table text in the Markdown is not duplicated — if a matching region is found, it is replaced.
- [ ] Chunk Markdown is updated in place.
- [ ] A log entry records each table placement (placed vs. unplaced).
- [ ] Unit tests cover: placed table, unplaced table, multiple tables in one chunk.

## Implementation Notes

### Placement strategy

1. For each table, approximate its position within the chunk:
   - Table is on page P of the chunk.
   - Each chunk has `chunk_size` pages. Page P maps to roughly `P / chunk_size` of the way through the Markdown.
2. Search the surrounding region of the Markdown for text that overlaps with the table's first row or header.
3. If a matching context paragraph is found, insert the Markdown table after it.
4. If no match → append at end with comment.

### Avoiding duplication

Pandoc may have produced a garbled version of the table. If the table's first-row text matches a nearby text block, replace that block with the clean Markdown table.

### Complexity note

This is the most heuristic-heavy task in the pipeline. Expect need for iteration and manual review of edge cases. Keep the logic simple for v1 and improve in later iterations.

## References

- [technical-design.md §5.4.3 — Merging Strategy](../technical-design.md)
