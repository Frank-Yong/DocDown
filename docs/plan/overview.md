# DocDown — Implementation Plan

## Overview

This plan breaks the DocDown pipeline implementation into 9 stages with individual tasks. Each task has its own file with detailed acceptance criteria, dependencies, and implementation notes.

Stages are ordered by dependency — later stages build on earlier ones. Within a stage, tasks can often be worked in parallel.

---

## Stages

### Stage 1 — Project Setup & Infrastructure

Foundation: project structure, configuration, logging, and working directory management.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [1.1](task-1.1-project-structure.md) | Initialize project structure | — |
| [1.2](task-1.2-configuration.md) | Configuration system | 1.1 |
| [1.3](task-1.3-logging.md) | Logging framework | 1.1 |
| [1.4](task-1.4-workdir-management.md) | Working directory management | 1.2 |

### Stage 2 — PDF Splitting

Split large PDFs into processable chunks.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [2.1](task-2.1-pdf-validation.md) | PDF validation & page counting | 1.4 |
| [2.2](task-2.2-chunk-splitting.md) | Chunk splitting with qpdf | 2.1 |

### Stage 3 — Content Extraction

Extract structured content from each chunk.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [3.1](task-3.1-grobid-integration.md) | GROBID integration | 1.3, 1.4 |
| [3.2](task-3.2-pdfminer-fallback.md) | pdfminer.six fallback extraction | 1.3, 1.4 |
| [3.3](task-3.3-extraction-orchestration.md) | Extraction orchestration & fallback logic | 3.1, 3.2 |

### Stage 4 — Markdown Conversion

Convert intermediate formats to GFM Markdown.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [4.1](task-4.1-pandoc-conversion.md) | Pandoc conversion | 1.4 |
| [4.2](task-4.2-markdown-cleanup.md) | Post-conversion Markdown cleanup | 4.1 |

### Stage 5 — Table Extraction

Detect and extract tables, merge into Markdown output.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [5.1](task-5.1-table-detection.md) | Table detection & extraction with Camelot | 1.4 |
| [5.2](task-5.2-table-to-markdown.md) | Table-to-Markdown conversion | 5.1 |
| [5.3](task-5.3-table-merging.md) | Table merging into chunk Markdown | 4.2, 5.2 |

### Stage 6 — Merge & TOC Generation

Combine chunks and produce final output.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [6.1](task-6.1-chunk-merging.md) | Chunk merging | 4.2 |
| [6.2](task-6.2-toc-generation.md) | TOC generation | 6.1 |
| [6.3](task-6.3-pre-split-toc-extraction.md) | Pre-split TOC extraction (optional) | 2.1 |
| [6.4](task-6.4-markdown-structure-and-toc-hardening.md) | Markdown structure and TOC hardening (ad-hoc) | 4.2, 6.2 |

### Stage 7 — Parallel Processing

Add concurrency to the chunk processing pipeline.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [7.1](task-7.1-worker-pool.md) | Worker pool implementation | 3.3, 4.2, 5.3 |
| [7.2](task-7.2-failure-isolation.md) | Failure isolation & reporting | 7.1 |

### Stage 8 — Validation & Reporting

Quality checks and run summaries.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [8.1](task-8.1-chunk-validation.md) | Per-chunk validation | 4.2 |
| [8.2](task-8.2-final-validation.md) | Final output validation | 6.2 |
| [8.3](task-8.3-run-summary.md) | Run summary generation | 8.2 |

### Stage 9 — LLM-Assisted Pipeline (Optional)

Alternative pipeline using LLM for higher-quality output.

| Task | Title | Dependencies |
| ---- | ----- | ------------ |
| [9.1](task-9.1-pymupdf-extraction.md) | PyMuPDF text extraction | 1.4 |
| [9.2](task-9.2-llm-integration.md) | LLM integration & prompt design | 9.1, 1.2 |
| [9.3](task-9.3-llm-chunking.md) | Context-window chunking & de-duplication | 9.2 |

---

## Dependency Graph

```
Stage 1 (Setup)
  │
  ├──▶ Stage 2 (Split) ──▶ Stage 3 (Extract) ──┐
  │                                              │
  ├──▶ Stage 4 (Convert) ◀──────────────────────┘
  │         │
  │         ├──▶ Stage 5 (Tables) ──▶ Stage 6 (Merge)
  │         │                              │
  │         └──────────────────────────────▶│
  │                                         │
  │    Stage 7 (Parallel) ◀── Stages 3–5    │
  │                                         │
  │    Stage 8 (Validation) ◀───────────────┘
  │
  └──▶ Stage 9 (LLM — optional, independent path)
```

## Alternative Delivery Paths

- [fast-path-01.md](fast-path-01.md): quality-first MVP path that reaches a full GROBID plus pdfminer end-to-end pipeline before tables, parallelism, and the LLM option.
- [fast-path-02.md](fast-path-02.md): fallback-first baseline path that gets to a simpler pdfminer-only end-to-end pipeline even sooner, then layers GROBID, tables, and parallelism afterward.

## Execution Decision

- Selected path: [fast-path-01.md](fast-path-01.md) (Quality-First MVP).
- Current task focus: [task-1.2-configuration.md](task-1.2-configuration.md).

## Conventions

- Each task file follows a consistent template: summary, dependencies, acceptance criteria, implementation notes, and references.
- Tasks are named `task-{stage}.{number}-{slug}.md`.
- A task is complete when all acceptance criteria are met and tests pass.
