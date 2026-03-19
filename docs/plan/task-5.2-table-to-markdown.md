# Task 5.2 — Table-to-Markdown Conversion

## Summary

Convert extracted Camelot table objects into Markdown table syntax.

## Dependencies

- Task 5.1 (table detection & extraction)

## Acceptance Criteria

- [ ] Each extracted table's DataFrame is converted to a Markdown table string.
- [ ] Markdown tables are written to `workdir/tables/chunk-NNN-table-MMM.md`.
- [ ] Empty or single-cell tables are discarded.
- [ ] Cell content is cleaned: excessive whitespace collapsed, newlines within cells replaced with `<br>`.
- [ ] Table files include a metadata comment: page number, bounding box, accuracy score.
- [ ] Unit tests verify Markdown output for simple and multi-row/column tables.

## Implementation Notes

### Conversion

```python
def table_to_markdown(table, chunk_num, table_num, tables_dir):
    df = table.df
    if df.empty or (df.shape[0] <= 1 and df.shape[1] <= 1):
        return None  # discard trivial tables
    
    # Clean cells
    df = df.map(lambda x: " ".join(str(x).split()) if isinstance(x, str) else x)
    
    md = df.to_markdown(index=False)
    
    path = tables_dir / f"chunk-{chunk_num:03d}-table-{table_num:03d}.md"
    metadata = (
        f"<!-- table: chunk={chunk_num} table={table_num} "
        f"page={table.parsing_report['page']} "
        f"accuracy={table.parsing_report['accuracy']:.1f}% -->\n"
    )
    path.write_text(metadata + md, encoding="utf-8")
    return path
```

Requires `tabulate` package for `DataFrame.to_markdown()`.

## References

- [technical-design.md §5.4.2 — Conversion to Markdown](../technical-design.md)
