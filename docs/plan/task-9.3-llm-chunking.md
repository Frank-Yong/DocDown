# Task 9.3 — Context-Window Chunking & De-duplication

## Summary

Split extracted text into segments that fit within the LLM's context window, with overlap to prevent content loss at boundaries, and de-duplicate the overlapping regions after processing.

## Dependencies

- Task 9.2 (LLM integration)

## Acceptance Criteria

- [ ] Extracted text is split into segments sized for the LLM's context window minus prompt overhead.
- [ ] Adjacent segments overlap by ~200 tokens to avoid losing content at boundaries.
- [ ] Overlap size is configurable.
- [ ] After LLM processing, overlapping regions in adjacent outputs are detected and de-duplicated.
- [ ] De-duplication does not remove intentionally repeated content (e.g., repeated headings across sections).
- [ ] Segment count and token estimates per segment are logged.
- [ ] Unit tests cover: splitting, overlap, de-duplication with known input.

## Implementation Notes

### Splitting

```python
def split_into_segments(text, max_tokens, overlap_tokens=200):
    # Approximate: 1 token ≈ 4 characters
    max_chars = max_tokens * 4
    overlap_chars = overlap_tokens * 4
    
    segments = []
    start = 0
    while start < len(text):
        end = start + max_chars
        segments.append(text[start:end])
        start = end - overlap_chars
    return segments
```

### Smarter split points

Instead of splitting mid-sentence, find the nearest paragraph break (`\n\n`) within a tolerance window (±500 chars from the calculated split point).

### De-duplication

After LLM processing, compare the tail of segment N's output with the head of segment N+1's output:

```python
def deduplicate_overlap(segment_a, segment_b, overlap_chars=800):
    tail = segment_a[-overlap_chars:]
    head = segment_b[:overlap_chars]
    
    # Find longest common substring
    # Remove the duplicate from segment_b's start
    ...
```

Use `difflib.SequenceMatcher` for fuzzy matching (LLM may have slightly reformatted the overlapping text).

### Edge cases

- Very short chunks may not need splitting (text fits in one segment).
- Segments that are entirely whitespace after extraction should be skipped.

## References

- [technical-design.md §6.4 — Chunking for LLM Context](../technical-design.md)
