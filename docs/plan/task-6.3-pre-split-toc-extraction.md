# Task 6.3 — Pre-Split TOC Extraction (Optional)

## Summary

Extract the original PDF's bookmark tree before splitting, for reference and manual review.

## Dependencies

- Task 2.1 (PDF validation — input PDF must be validated)

## Acceptance Criteria

- [ ] PDF bookmark metadata is extracted using `pdftk dump_data`.
- [ ] Bookmark entries (title, level, page number) are parsed and saved to `workdir/original-toc.txt`.
- [ ] If the PDF has no bookmarks, an empty file or a "no bookmarks found" message is written.
- [ ] If `pdftk` is not available, skip gracefully with a log warning (this step is optional).
- [ ] This task runs independently and does not block the main pipeline.
- [ ] Unit test verifies parsing of a sample `pdftk dump_data` output.

## Implementation Notes

### Command

```bash
pdftk input.pdf dump_data | grep -E "Bookmark(Title|Level|PageNumber)"
```

### Sample output

```
BookmarkTitle: Chapter 1 - Introduction
BookmarkLevel: 1
BookmarkPageNumber: 12
BookmarkTitle: 1.1 Background
BookmarkLevel: 2
BookmarkPageNumber: 12
```

### Parsing

```python
def parse_bookmarks(dump_data_output):
    entries = []
    current = {}
    for line in dump_data_output.splitlines():
        if line.startswith("BookmarkTitle:"):
            current["title"] = line.split(":", 1)[1].strip()
        elif line.startswith("BookmarkLevel:"):
            current["level"] = int(line.split(":", 1)[1].strip())
        elif line.startswith("BookmarkPageNumber:"):
            current["page"] = int(line.split(":", 1)[1].strip())
            entries.append(current)
            current = {}
    return entries
```

### Usage

This file is informational. It is **not** used in the output but can help users verify that the converted Markdown covers all expected sections.

## References

- [technical-design.md §5.5.3 — Pre-split TOC Extraction](../technical-design.md)
- [spec.md §6.3 — Recommended Strategy](../spec.md)
