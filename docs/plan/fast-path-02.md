# DocDown — Fast-Path 02 (Fallback-First Baseline)

## Motivation

This alternative optimizes for the shortest route to a testable end-to-end pipeline. It reaches first output sooner than Fast-Path 01 by using the simpler pdfminer-based extraction path before introducing GROBID and extraction orchestration.

All original tasks are still preserved and fully implemented. Nothing is removed. The difference is only delivery order.

The key changes from the original ordering:

1. **Phase 1 (Baseline)** delivers a working end-to-end pipeline with 14 tasks and no Docker dependency.
2. **Phase 2 (Upgrade Extraction)** adds GROBID and the full primary-plus-fallback orchestration.
3. **Phase 3 (Enrich)** adds tables, parallelism, and optional pre-split TOC extraction.
4. **Phase 4 (LLM)** adds the alternative LLM-assisted pipeline.

---

## Phase 1 — Baseline End-to-End Pipeline

**Goal:** Convert a PDF to Markdown with pdfminer extraction, Pandoc conversion, cleanup, merge, validation, and a generated TOC. Chunks are processed sequentially. No GROBID, no tables, no parallelism.

**Exit criteria:** Running `docdown input.pdf` produces `final.md` with a TOC and a run summary, using the pdfminer extraction path only.

### Task order

```
1.1 Project structure
 ├─► 1.2 Configuration ──► 1.4 Workdir management ──► 2.1 PDF validation ──► 2.2 Chunk splitting
 └─► 1.3 Logging
                                               │
                                               ▼
                                      3.2 pdfminer extraction
                                               │
                                               ▼
                                      4.1 Pandoc conversion
                                               │
                                               ▼
                                      4.2 Markdown cleanup
                                               │
                                               ▼
                                         6.1 Chunk merging
                                               │
                                               ▼
                                         6.2 TOC generation
                                               │
                                               ▼
                                  ┌────────────┴────────────┐
                                  ▼                         ▼
                            8.1 Chunk validation      8.2 Final validation
                                                            │
                                                            ▼
                                                   8.3 Run summary
```

### Parallelism opportunities

| Parallel set | Tasks | Why independent |
|---|---|---|
| A | 1.2, 1.3 | Both depend only on 1.1. |
| B | 8.1, 8.2 | 8.1 inspects chunk outputs; 8.2 inspects final output after 6.2. Both are read-only checks. |

### Tasks included (14)

| Task | Title | Status in original plan |
|---|---|---|
| 1.1 | Initialize project structure | Unchanged |
| 1.2 | Configuration system | Unchanged |
| 1.3 | Logging framework | Unchanged |
| 1.4 | Working directory management | Unchanged |
| 2.1 | PDF validation & page counting | Unchanged |
| 2.2 | Chunk splitting with qpdf | Unchanged |
| 3.2 | pdfminer.six fallback extraction | Unchanged |
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
| 3.1 (GROBID) | The baseline can ship using the existing pdfminer extraction task first. |
| 3.3 (Extraction orchestration) | Not needed until both primary and fallback extractors exist in the runnable pipeline. |
| 5.1–5.3 (Tables) | Table quality improves later, but the pipeline is still testable without Camelot. |
| 6.3 (Pre-split TOC) | Explicitly optional in the original plan. |
| 7.1–7.2 (Parallelism) | Sequential execution is sufficient for correctness. |
| 9.1–9.3 (LLM) | Entirely independent alternative path. |

### Integration note — baseline extraction path

Phase 1 wires the chunk loop directly to task 3.2's plain-text extraction output. That keeps downstream interfaces simple because task 4.1 already accepts plain-text input. When tasks 3.1 and 3.3 are added later, the direct extractor call is replaced by the orchestrator without changing stages 4, 6, or 8.

---

## Phase 2 — Upgrade Extraction Quality

**Goal:** Switch the default pipeline from pdfminer-only extraction to GROBID-first extraction with pdfminer fallback.

**Exit criteria:** Running `docdown input.pdf` uses GROBID when available, falls back to pdfminer when needed, and preserves the same downstream Markdown, validation, and reporting flow from Phase 1.

### Task order

```
3.1 GROBID integration ──► 3.3 Extraction orchestration

6.3 Pre-split TOC extraction  ← independent, can be done any time after 2.1
```

### Tasks included (3)

| Task | Title | Status in original plan |
|---|---|---|
| 3.1 | GROBID integration | Unchanged |
| 3.3 | Extraction orchestration & fallback logic | Unchanged |
| 6.3 | Pre-split TOC extraction (optional) | Unchanged |

### Integration note — orchestrator retrofit

Task 3.3 becomes the only entry point for extraction. The Phase 1 pdfminer path remains intact as the fallback branch, so no earlier work is discarded.

---

## Phase 3 — Tables, Parallelism & Polish

**Goal:** Add table extraction, table reinsertion, and parallel chunk processing.

**Exit criteria:** Tables are extracted and merged into chunk Markdown, and chunks process in parallel with proper failure isolation.

### Task order

```
5.1 Table detection ──► 5.2 Table-to-Markdown ──► 5.3 Table merging
                                                        │
                                                        ▼
7.1 Worker pool (depends on 3.3 + 4.2 + 5.3) ──► 7.2 Failure isolation
```

### Tasks included (5)

| Task | Title | Status in original plan |
|---|---|---|
| 5.1 | Table detection & extraction with Camelot | Unchanged |
| 5.2 | Table-to-Markdown conversion | Unchanged |
| 5.3 | Table merging into chunk Markdown | Unchanged |
| 7.1 | Worker pool implementation | Unchanged |
| 7.2 | Failure isolation & reporting | Unchanged |

---

## Phase 4 — LLM-Assisted Pipeline

**Goal:** Add the optional LLM-assisted path for poorly structured PDFs.

**Exit criteria:** Running `docdown input.pdf --llm-cleanup` uses PyMuPDF + LLM chunk processing as an alternative pipeline.

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

| | Original plan | Fast path 01 | Fast path 02 |
|---|---|---|---|
| Total tasks | 25 | 25 (same) | 25 (same) |
| Tasks modified | — | 0 | 0 |
| Phases | 1 | 3 | 4 |
| Tasks to working E2E | 25 (all stages required) | 16 | 14 |
| First testable output | After Stage 8 | GROBID + pdfminer sequential pipeline | pdfminer-only sequential pipeline |
| Early external dependencies | Docker + GROBID expected early | Docker + GROBID expected in Phase 1 | No Docker required for Phase 1 |
| Best use case | Strict stage-by-stage execution | Earlier high-quality extraction | Fastest baseline delivery |

## Trade-off summary

- Choose this path when speed of first output matters more than early Markdown quality.
- This is the lowest-friction route for local development on Windows because Phase 1 does not depend on Docker.
- Fast-Path 01 is still the better option if early validation must reflect the intended GROBID-first architecture.