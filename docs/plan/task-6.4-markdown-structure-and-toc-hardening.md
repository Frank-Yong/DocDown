# Task 6.4 — Markdown Structure and TOC Hardening (Ad-hoc)

## Summary

Improve upstream Markdown structure quality and guarantee a visible TOC block in final output for external documents.

## Why This Ad-hoc Task Exists

External validation runs completed successfully, but generated `final.md` files did not contain a visible TOC block despite successful TOC-stage execution. This indicates a quality gap between extracted/cleaned Markdown structure and TOC rendering behavior.

## Dependencies

- Task 4.2 (Markdown cleanup)
- Task 6.1 (chunk merging)
- Task 6.2 (TOC generation)

## Acceptance Criteria

- [ ] Add heading-coverage diagnostics for chunk markdown and merged markdown (for example: heading counts by level, chunks without headings).
- [ ] Improve cleanup heading reconstruction heuristics so section-like lines are promoted to headings where safe.
- [ ] Keep current Pandoc TOC path, but add a guaranteed-visible TOC insertion fallback when no TOC block is emitted.
- [ ] Ensure fallback TOC links are GitHub-anchor compatible and respect configured depth.
- [ ] Add tests that cover:
  - [ ] low-heading external-like markdown input
  - [ ] Pandoc success without visible TOC output
  - [ ] guaranteed fallback insertion at document top
- [ ] Re-run at least two external documents and verify `final.md` contains a visible TOC section.
- [ ] Update run logging to distinguish:
  - [ ] heading candidates detected
  - [ ] TOC entries emitted
  - [ ] TOC mode used (`pandoc` or `python-fallback`)

## Proposed Scope

### 1. Diagnose current markdown structure quality

- Add lightweight heading-quality metrics before TOC generation.
- Surface summary in logs so quality regressions are visible.

### 2. Improve heading reconstruction in cleanup stage

- Extend cleanup heuristics to detect probable section headers from extracted plain text.
- Preserve conservative behavior to avoid over-heading body text.

### 3. Guarantee TOC visibility in final output

- Continue attempting Pandoc TOC generation first.
- If resulting output has no detectable TOC block near the top, prepend a Python-generated TOC built from headings.

## Implementation Notes

Potential files:

- `docdown/stages/cleanup.py`
- `docdown/stages/toc.py`
- `docdown/cli.py`
- `tests/test_cleanup.py`
- `tests/test_toc.py`
- `tests/test_cli.py`

Validation artifacts:

- `runs/external-toc-001/final.md`
- `runs/external-toc-002/final.md`

## Out of Scope

- Replacing the extraction engine.
- Building a semantic section classifier with LLMs.
- Large-format redesign of merged markdown output.

## References

- [technical-design.md §5.3 — Post-conversion cleanup](../technical-design.md)
- [technical-design.md §5.5.2 — TOC Generation](../technical-design.md)
- [spec.md §4.5 — Stage 5: Merge & Generate TOC](../spec.md)