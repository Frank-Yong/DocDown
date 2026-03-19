# Task 6.2 — TOC Generation

## Summary

Generate a Table of Contents from the merged Markdown headings using Pandoc.

## Dependencies

- Task 6.1 (chunk merging — `merged.md` must exist)

## Acceptance Criteria

- [ ] Pandoc generates a TOC from `merged.md` headings up to depth 3 (`#`, `##`, `###`).
- [ ] TOC is inserted at the top of the document.
- [ ] Output is written to `workdir/final.md`.
- [ ] If Pandoc fails, `merged.md` is copied to `final.md` without a TOC (degraded but usable).
- [ ] TOC depth is configurable (default: 3).
- [ ] Log the number of TOC entries generated.
- [ ] Unit test verifies TOC is present in output for a document with headings.

## Implementation Notes

### Command

```bash
pandoc merged.md -f gfm -t gfm --toc --toc-depth=3 -o final.md
```

### Alternative: Python-based TOC

If Pandoc's `--toc` for GFM output is insufficient (it may not produce GFM-compatible link anchors), implement a simple Python TOC generator:

```python
import re

def generate_toc(text, max_depth=3):
    toc_lines = []
    for match in re.finditer(r"^(#{1,6}) (.+)$", text, re.MULTILINE):
        level = len(match.group(1))
        if level > max_depth:
            continue
        title = match.group(2).strip()
        anchor = re.sub(r"[^\w\s-]", "", title.lower()).replace(" ", "-")
        indent = "  " * (level - 1)
        toc_lines.append(f"{indent}- [{title}](#{anchor})")
    return "\n".join(toc_lines)
```

Decide at implementation time which approach produces better results.

## References

- [technical-design.md §5.5.2 — TOC Generation](../technical-design.md)
- [spec.md §4.5 — Stage 5: Merge & Generate TOC](../spec.md)
