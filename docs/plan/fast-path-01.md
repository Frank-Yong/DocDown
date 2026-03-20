# DocDown — Fast-Path Implementation Plan

## Motivation

The original plan has 25 tasks across 9 stages, ordered strictly stage-by-stage. This alternative groups them into three delivery phases. Each phase produces a working pipeline that can be tested with real PDFs. All original tasks are preserved and fully implemented — nothing is cut, only reordered.

The key changes from the original ordering:

1. **Phase 1 (MVP)** delivers a working end-to-end pipeline with 16 tasks.
2. **Phase 2 (Enrich)** adds table extraction, parallelism, and optional TOC extraction.
3. **Phase 3 (LLM)** adds the alternative LLM-assisted pipeline.
4. Within each phase, independent tasks are flagged for **parallel development** where their dependencies allow it.

---

## Phase 1 — Working End-to-End Pipeline

**Goal:** Convert a PDF to Markdown with GROBID extraction, pdfminer fallback, validation, and a generated TOC. Chunks are processed sequentially. No table extraction.

**Exit criteria:** Running `docdown input.pdf` produces `final.md` with a TOC and a run summary.

### Task order

```
1.1 Project structure
 ├─► 1.2 Configuration ──► 1.4 Workdir management ──► 2.1 PDF validation ──► 2.2 Chunk splitting
 └─► 1.3 Logging
           │
           ▼ (after 1.3 + 1.4)
     ┌─────┴─────┬───────────┐
     ▼           ▼           ▼        ← parallel development
   3.1 GROBID  3.2 pdfminer 4.1 Pandoc conversion
     │           │           │
     └─────┬─────┘           │
           ▼                 ▼
   3.3 Extraction orch.   4.2 Markdown cleanup
           │                 │
           └────────┬────────┘
                    ▼
              6.1 Chunk merging
                    │
                    ▼
              6.2 TOC generation
                    │
                    ▼
           ┌────────┴────────┐
           ▼                 ▼        ← parallel development
     8.1 Chunk validation  8.2 Final validation
                             │
                             ▼
                    8.3 Run summary
```

### Parallelism opportunities

| Parallel set | Tasks | Why independent |
|---|---|---|
| A | 1.2, 1.3 | Both depend only on 1.1 |
| B | 3.1, 3.2, 4.1 | All depend on 1.3+1.4; no cross-dependency |
| C | 8.1, 8.2 | 8.1 validates chunks (needs 4.2); 8.2 validates final (needs 6.2). Both are read-only checks. |

### Tasks included (16)

| Task | Title | Status in original plan |
|---|---|---|
| 1.1 | Initialize project structure | Unchanged |
| 1.2 | Configuration system | Unchanged |
| 1.3 | Logging framework | Unchanged |
| 1.4 | Working directory management | Unchanged |
| 2.1 | PDF validation & page counting | Unchanged |
| 2.2 | Chunk splitting with qpdf | Unchanged |
| 3.1 | GROBID integration | Unchanged |
| 3.2 | pdfminer.six fallback extraction | Unchanged |
| 3.3 | Extraction orchestration & fallback logic | Unchanged |
| 4.1 | Pandoc conversion | Unchanged |
| 4.2 | Post-conversion Markdown cleanup | Unchanged |
| 6.1 | Chunk merging | Unchanged |
| 6.2 | TOC generation | Unchanged |
| 8.1 | Per-chunk validation | Unchanged |
| 8.2 | Final output validation | Unchanged |
| 8.3 | Run summary generation | Unchanged |

### What Phase 1 skips (deferred, not removed)

| Deferred task | Why safe to defer |
|---|---|
| 5.1–5.3 (Tables) | GROBID + Pandoc already extract tables best-effort. Camelot adds quality but isn't required for a working pipeline. |
| 6.3 (Pre-split TOC) | Explicitly optional in the original plan. |
| 7.1–7.2 (Parallelism) | Sequential processing works correctly. Parallelism is a performance optimization. |
| 9.1–9.3 (LLM) | Entirely independent alternative path. |

### Integration note — failure isolation in Phase 1

Task 7.2 (failure isolation) is deferred to Phase 2 with the worker pool, but Phase 1 still needs basic error handling in the sequential chunk loop. The extraction orchestration (3.3) already tracks per-chunk success/failure and the sequential loop should skip failed chunks at merge time (6.1 already handles this via placeholder comments). No additional task is needed — 3.3 and 6.1 cover it.

---

## Phase 2 — Tables, Parallelism & Polish

**Goal:** Add Camelot table extraction, parallel chunk processing, and optional pre-split TOC extraction. After this phase, the pipeline matches the full spec minus LLM.

**Exit criteria:** Tables are extracted and merged into Markdown. Chunks process in parallel with proper failure isolation.

### Task order

```
5.1 Table detection ──► 5.2 Table-to-Markdown ──► 5.3 Table merging
                                                        │
                                                        ▼
7.1 Worker pool (depends on 3.3 + 4.2 + 5.3) ──► 7.2 Failure isolation

6.3 Pre-split TOC extraction  ← independent, can be done any time
```

### Parallelism opportunities

| Parallel set | Tasks | Why independent |
|---|---|---|
| D | 5.1, 6.3 | 5.1 depends on 1.4; 6.3 depends on 2.1. No overlap. |
| E | 7.1 (after 5.3), 6.3 (if not done in set D) | Different subsystems. |

### Tasks included (6)

| Task | Title | Status in original plan |
|---|---|---|
| 5.1 | Table detection & extraction with Camelot | Unchanged |
| 5.2 | Table-to-Markdown conversion | Unchanged |
| 5.3 | Table merging into chunk Markdown | Unchanged |
| 6.3 | Pre-split TOC extraction (optional) | Unchanged |
| 7.1 | Worker pool implementation | Unchanged |
| 7.2 | Failure isolation & reporting | Unchanged |

### Integration note — worker pool retrofit

Task 7.1 wraps the existing sequential `extract → convert → cleanup → tables` per-chunk pipeline from Phase 1 in a `ThreadPoolExecutor`. The per-chunk function (`process_single_chunk`) is already clean from Phase 1; the worker pool is purely additive. No Phase 1 code needs restructuring — only a new outer loop is needed.

---

## Phase 3 — LLM-Assisted Pipeline

**Goal:** Add the alternative LLM cleanup path for poorly-structured PDFs.

**Exit criteria:** Running `docdown input.pdf --llm-cleanup` uses PyMuPDF + LLM instead of GROBID + Pandoc.

### Task order

```
9.1 PyMuPDF extraction ──► 9.2 LLM integration ──► 9.3 Context-window chunking
```

### Tasks included (3)

| Task | Title | Status in original plan |
|---|---|---|
| 9.1 | PyMuPDF text extraction | Unchanged |
| 9.2 | LLM integration & prompt design | Unchanged |
| 9.3 | Context-window chunking & de-duplication | Unchanged |

---

## Summary comparison

| | Original plan | Fast path |
|---|---|---|
| Total tasks | 25 | 25 (same) |
| Tasks modified | — | 0 |
| Phases | 1 | 3 |
| Tasks to working E2E | 25 (all stages required) | 16 (Phase 1) |
| First testable output | After Stage 8 | After Phase 1 |
| Table extraction | Required before merge | Deferred to Phase 2 |
| Parallelism | Required before validation | Deferred to Phase 2 |
| LLM pipeline | Mixed into main plan | Isolated as Phase 3 |
