# Task 7.2 — Failure Isolation & Reporting

## Summary

Ensure chunk failures are isolated and do not block other chunks. Collect and report all failures at the end of processing.

## Dependencies

- Task 7.1 (worker pool)

## Acceptance Criteria

- [ ] A failed chunk does not cause other workers to stop.
- [ ] Unhandled exceptions in a worker are caught and recorded, not propagated.
- [ ] After all workers complete, a failure summary is logged.
- [ ] Failed chunks are listed with: chunk number, stage that failed, error message.
- [ ] The pipeline continues to Merge (Stage 5) even if some chunks failed.
- [ ] If **all** chunks fail, the pipeline aborts before Merge with a fatal error.
- [ ] Failure data is passed to the run summary (Task 8.3).
- [ ] Unit tests verify: single failure doesn't block others, all-fail triggers abort.

## Implementation Notes

### Data model

```python
@dataclass
class ChunkResult:
    chunk_number: int
    success: bool
    extractor_used: str | None = None
    tables_found: int = 0
    error: str | None = None
    failed_stage: str | None = None
```

### Failure summary

```python
def log_failure_summary(results):
    failed = [r for r in results if not r.success]
    if not failed:
        log.info("All chunks processed successfully.")
        return
    
    log.warning(f"{len(failed)} chunk(s) failed:")
    for r in failed:
        log.warning(f"  chunk-{r.chunk_number:04d}: {r.failed_stage} — {r.error}")
    
    if len(failed) == len(results):
        raise FatalPipelineError("All chunks failed. No output produced.")
```

## References

- [technical-design.md §7.2 — Failure Isolation](../technical-design.md)
- [technical-design.md §9.1 — Error Handling Strategy](../technical-design.md)
