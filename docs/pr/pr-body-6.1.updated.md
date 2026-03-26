## Summary
- implement Stage 6.1 chunk merging in the merge stage module
- merge chunk markdown files in numeric order with `---` separators
- insert placeholder comments for missing/empty chunks (`<!-- chunk-NNNN: extraction failed -->`)
- log merged output metrics (line count and file size)
- wire merge stage into CLI after conversion/cleanup
- surface merge errors through CLI as `ClickException`
- mark Task 6.1 checklist complete in planning docs

## Files Changed
- `docdown/stages/merge.py`
- `docdown/cli.py`
- `tests/test_merge.py`
- `tests/test_cli.py`
- `docs/plan/task-6.1-chunk-merging.md`
- `docs/plan/task-4.2-markdown-cleanup.md` (doc-only sync; already landed on `main`)

## Validation
- targeted: `pytest tests/test_merge.py tests/test_cli.py`
- full suite: `116 passed, 1 skipped`
