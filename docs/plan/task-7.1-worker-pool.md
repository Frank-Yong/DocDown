# Task 7.1 — Worker Pool Implementation

## Summary

Implement parallel processing of chunks through stages 2–4 using a bounded worker pool.

## Dependencies

- Task 3.3 (extraction orchestration)
- Task 4.2 (Markdown cleanup)
- Task 5.3 (table merging)

## Acceptance Criteria

- [ ] Chunks are processed concurrently through Extract → Convert → Post-process → Tables.
- [ ] Worker count is configurable (`parallel_workers`, default: 4, max recommended: 6).
- [ ] Each worker handles one chunk end-to-end (stages 2–4) sequentially.
- [ ] Workers share the GROBID connection pool but do not contend on file I/O (each writes to its own chunk files).
- [ ] Progress is logged: "Processing chunk N/M".
- [ ] All workers complete (or fail) before Stage 5 (Merge) begins.
- [ ] Unit tests verify correct parallelism with mock stages.
- [ ] Stress test: 20+ chunks with 4 workers completes without deadlock.

## Implementation Notes

### Design

Use `concurrent.futures.ThreadPoolExecutor` (or `ProcessPoolExecutor` for CPU-bound work, but most stages are I/O-bound → threads are fine).

```python
from concurrent.futures import ThreadPoolExecutor, as_completed

def process_chunks_parallel(chunk_paths, config, workdir):
    results = []
    with ThreadPoolExecutor(max_workers=config.parallel_workers) as pool:
        futures = {
            pool.submit(process_single_chunk, path, i+1, config, workdir): i+1
            for i, path in enumerate(chunk_paths)
        }
        for future in as_completed(futures):
            chunk_num = futures[future]
            try:
                result = future.result()
                results.append(result)
            except Exception as e:
                log.error(f"[chunk-{chunk_num:04d}] Unhandled error: {e}")
                results.append(ChunkResult(chunk_num, success=False, error=str(e)))
    return sorted(results, key=lambda r: r.chunk_number)
```

### Per-chunk pipeline

```python
def process_single_chunk(chunk_path, chunk_num, config, workdir):
    # 1. Extract
    extraction = extract_chunk(chunk_path, chunk_num, config, workdir)
    if not extraction.success:
        return ChunkResult(chunk_num, success=False, ...)
    
    # 2. Convert
    convert_to_markdown(extraction.output_path, workdir.markdown(chunk_num))
    
    # 3. Cleanup
    cleanup_markdown(workdir.markdown(chunk_num))
    
    # 4. Tables (optional)
    if config.table_extraction:
        extract_and_merge_tables(chunk_path, chunk_num, workdir)
    
    return ChunkResult(chunk_num, success=True)
```

### GROBID concurrency

GROBID handles concurrent requests internally, but too many simultaneous submissions can cause 503 errors. The worker pool's bounded size (4–6) naturally limits this. The retry/backoff logic in Task 3.1 handles transient overload.

## References

- [technical-design.md §7 — Parallel Processing](../technical-design.md)
- [spec.md §7.1 — Parallelism](../spec.md)
