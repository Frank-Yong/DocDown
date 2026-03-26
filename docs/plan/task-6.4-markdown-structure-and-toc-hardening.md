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

- [x] Add heading-coverage diagnostics for chunk markdown and merged markdown (for example: heading counts by level, chunks without headings).
- [x] Improve cleanup heading reconstruction heuristics so section-like lines are promoted to headings where safe.
- [x] Keep current Pandoc TOC path, but add a guaranteed-visible TOC insertion fallback when no TOC block is emitted.
- [x] Ensure fallback TOC links are GitHub-anchor compatible and respect configured depth.
- [x] Add tests that cover:
  - [x] low-heading external-like markdown input
  - [x] Pandoc success without visible TOC output
  - [x] guaranteed fallback insertion at document top
- [x] Re-run at least two external documents and verify `final.md` contains a visible TOC section.
- [x] Update run logging to distinguish:
  - [x] heading candidates detected
  - [x] TOC entries emitted
  - [x] TOC mode used (`pandoc` or `python-fallback`)

Implemented in:
- `docdown/stages/toc.py`
- `docdown/stages/cleanup.py`
- `docdown/cli.py`
- `docdown/config.py`
- `tests/test_toc.py`
- `tests/test_cleanup.py`
- `tests/test_cli.py`
- `tests/test_config.py`

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

- `runs/external-toc-6.4-final-001/final.md`
- `runs/external-toc-6.4-final-002/final.md`
- `runs/external-toc-6.4-final-001/run.log`
- `runs/external-toc-6.4-final-002/run.log`

## Out of Scope

- Replacing the extraction engine.
- Building a semantic section classifier with LLMs.
- Large-format redesign of merged markdown output.

## References

- [technical-design.md §5.3 — Post-conversion cleanup](../technical-design.md)
- [technical-design.md §5.5.2 — TOC Generation](../technical-design.md)
- [spec.md §4.5 — Stage 5: Merge & Generate TOC](../spec.md)