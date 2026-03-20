# DocDown — Technical Design Document

## 1. Introduction

This document provides detailed technical guidance for implementing the DocDown PDF-to-Markdown conversion pipeline. It expands on the [spec](spec.md) with concrete data flows, API usage, error handling, configuration, and implementation considerations for each pipeline stage.

## 2. System Context

```
┌──────────┐    ┌─────────────────────────────────────────────────────┐    ┌──────────┐
│          │    │                    DocDown                          │    │          │
│  Input   │───▶│  Split → Extract → Convert → Post-process → Merge  │───▶│  Output  │
│  PDF(s)  │    │                                                     │    │  .md     │
└──────────┘    └─────────────────────────────────────────────────────┘    └──────────┘
                       │              │              │
                       ▼              ▼              ▼
                  chunk PDFs     TEI XML/HTML    chunk .md files
                 (intermediate)  (intermediate)   (intermediate)
```

All intermediate artifacts are written to a working directory and retained after the run completes. This enables debugging, selective reprocessing, and auditing.

## 3. Directory & File Layout

A single run produces the following structure:

```
workdir/
├── input/
│   └── source.pdf                  # original (or symlink)
├── chunks/
│   ├── chunk-0001.pdf
│   ├── chunk-0002.pdf
│   └── ...
├── extracted/
│   ├── chunk-0001.xml              # TEI XML from GROBID
│   ├── chunk-0002.xml
│   └── ...
├── markdown/
│   ├── chunk-0001.md
│   ├── chunk-0002.md
│   └── ...
├── tables/
│   ├── chunk-0003-table-001.md     # extracted tables
│   └── ...
├── merged.md                       # concatenated output (no TOC)
├── final.md                        # merged output with generated TOC
└── run.log                         # pipeline execution log
```

## 4. Configuration

Pipeline behaviour is controlled via a configuration file or CLI flags. Defaults are shown below.

```yaml
# docdown.yaml
input: null                     # path to source PDF (required)
workdir: ./output               # working directory for all artifacts
chunk_size: 50                  # pages per chunk
parallel_workers: 4             # max concurrent chunk processing workers
extractor: grobid               # primary extractor: grobid | pdfminer
grobid_url: http://localhost:8070  # GROBID service endpoint
fallback_extractor: pdfminer    # used when primary extractor fails on a chunk
table_extraction: true          # enable Camelot table extraction
llm_cleanup: false              # enable LLM post-processing (alternative pipeline)
llm_model: null                 # model identifier when llm_cleanup is true
validation:
  min_output_ratio: 0.01        # minimum (output bytes / input bytes); below = warning
  max_empty_chunks: 0           # max chunks producing zero output before abort
```

## 5. Stage Details

### 5.1 Stage 1 — Split

**Purpose:** Divide a large PDF into chunks that downstream tools can process without memory exhaustion or crashes.

**Tool:** `qpdf` (primary), `pdftk` (fallback).

**Process:**

1. Validate the input file exists and is a valid PDF (`qpdf --check input.pdf`).
2. Determine total page count (`qpdf --show-npages input.pdf`).
3. Calculate chunk boundaries based on `chunk_size`.
4. Split:
   ```bash
   qpdf input.pdf --pages . 1-50 -- chunks/chunk-0001.pdf
   qpdf input.pdf --pages . 51-100 -- chunks/chunk-0002.pdf
   # ...
   ```
5. Verify chunk count × chunk_size ≥ total pages.

**Edge cases:**

- PDFs with fewer pages than `chunk_size` produce a single chunk.
- Encrypted PDFs: `qpdf --decrypt` first if a password is available; otherwise abort with a clear error.
- Corrupted PDFs: `qpdf --check` returns a non-zero exit code → abort and report.

**Outputs:** `chunks/chunk-NNNN.pdf`

---

### 5.2 Stage 2 — Extract Structured Content

**Purpose:** Convert each PDF chunk into a structured intermediate representation that preserves semantic information.

#### 5.2.1 GROBID Extraction (Primary)

GROBID runs as a REST service (Docker container).

**Startup:**

```bash
docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.1
```

Use a pinned version tag in production rather than `latest`.

**API call per chunk:**

```
POST http://localhost:8070/api/processFulltextDocument
Content-Type: multipart/form-data

input = @chunks/chunk-0001.pdf
```

**Response:** TEI XML document.

**Integration notes:**

- Wait for GROBID readiness before submitting (`GET /api/isalive`).
- Set a per-request timeout of 120 seconds. Large or complex chunks may take longer; retry once with a 240-second timeout before falling back.
- GROBID returns HTTP 503 when overloaded. Implement exponential backoff (max 3 retries, base delay 5 s).
- Store response as `extracted/chunk-NNNN.xml`.

#### 5.2.2 pdfminer.six Extraction (Fallback)

Used when GROBID is unavailable or fails on a specific chunk.

```python
from pdfminer.high_level import extract_text

text = extract_text("chunks/chunk-0001.pdf")
with open("extracted/chunk-0001.txt", "w", encoding="utf-8") as f:
    f.write(text)
```

**Limitations:** Produces plain text only. No headings, sections, or table structure. Downstream conversion from plain text yields flat Markdown.

#### 5.2.3 Fallback Logic

```
For each chunk:
  1. Try GROBID
  2. If GROBID fails after retries → use pdfminer.six
  3. If pdfminer.six also fails → log error, mark chunk as failed, continue
```

Failed chunks are listed in `run.log` and summarised at the end of the run.

---

### 5.3 Stage 3 — Convert to Markdown

**Purpose:** Transform intermediate XML/text into GitHub-Flavored Markdown.

**Tool:** Pandoc.

**Commands:**

From TEI XML (GROBID output):

```bash
pandoc extracted/chunk-0001.xml -f tei -t gfm --wrap=none -o markdown/chunk-0001.md
```

From plain text (pdfminer fallback):

```bash
pandoc extracted/chunk-0001.txt -f plain -t gfm --wrap=none -o markdown/chunk-0001.md
```

**Pandoc flags:**

| Flag          | Purpose                                         |
| ------------- | ----------------------------------------------- |
| `--wrap=none` | Prevent hard line wrapping (preserves paragraphs) |
| `-t gfm`      | GitHub-Flavored Markdown output                 |

**Post-conversion cleanup (per chunk):**

- Strip excessive blank lines (more than 2 consecutive → 2).
- Normalise heading levels: ensure no chunk starts below `##` (since `#` is reserved for the document title).
- Remove artefact lines (e.g., page headers/footers that repeat across pages).

---

### 5.4 Stage 4 — Table Extraction & Merging

**Purpose:** Extract tables that GROBID/Pandoc miss or mangle, and merge them back into the Markdown.

**Tool:** Camelot (Python library).

#### 5.4.1 Detection

For each chunk PDF, attempt table extraction:

```python
import camelot

tables = camelot.read_pdf("chunks/chunk-0003.pdf", pages="all", flavor="lattice")
if not tables:
    tables = camelot.read_pdf("chunks/chunk-0003.pdf", pages="all", flavor="stream")
```

- Try `lattice` first (for tables with visible cell borders).
- Fall back to `stream` (for tables without borders).

#### 5.4.2 Conversion to Markdown

Each extracted table is converted to a Markdown table:

```python
for i, table in enumerate(tables):
    df = table.df
    md = df.to_markdown(index=False)
  output_path = Path("tables") / f"chunk-0003-table-{i+1:03d}.md"
  with output_path.open("w", encoding="utf-8", newline="") as f:
    f.write(md)
```

Requires `tabulate` for `DataFrame.to_markdown()`.

#### 5.4.3 Merging Strategy

Tables are inserted into the chunk Markdown based on their page location:

1. Record the page number and vertical position of each extracted table.
2. In the chunk Markdown, locate the nearest corresponding text context (paragraph before/after the table on that page).
3. Insert the Markdown table at that position.
4. If position cannot be determined, append tables at the end of the chunk with a `<!-- unplaced table -->` comment.

This step may require manual review for complex layouts.

---

### 5.5 Stage 5 — Merge & TOC Generation

**Purpose:** Combine all chunk Markdown files into a single document with a generated Table of Contents.

#### 5.5.1 Merge

Concatenation is implemented in Python (per §11.3 rule 3), not via shell `cat`:

```python
# Pseudocode — see implementation for full version
parts = []
for i in range(1, total_chunks + 1):
  chunk_path = markdown_dir / f"chunk-{i:04d}.md"
  if chunk_path.exists() and chunk_path.stat().st_size > 0:
    parts.append(chunk_path.read_text(encoding="utf-8"))
  else:
    parts.append(f"<!-- chunk-{i:04d}: extraction failed -->\n")

with output_path.open("w", encoding="utf-8", newline="") as out:
  out.write("\n\n---\n\n".join(parts))
```

Insert a horizontal rule (`---`) between chunks to preserve visual separation.

#### 5.5.2 TOC Generation

```bash
pandoc merged.md -t gfm --toc --toc-depth=3 -o final.md
```

| Parameter       | Value | Rationale                              |
| --------------- | ----- | -------------------------------------- |
| `--toc-depth`   | 3     | Include `#`, `##`, `###` in TOC        |

#### 5.5.3 Optional: Pre-split TOC Extraction

Before Stage 1, extract the PDF's bookmark tree for reference:

```bash
pdftk input.pdf dump_data | grep -E "Bookmark(Title|Level|PageNumber)"
```

Store as `workdir/original-toc.txt`. This is informational only — it is not used in the output but can guide manual review.

---

## 6. LLM-Assisted Pipeline (Alternative)

For PDFs where traditional extraction produces poor results (complex layouts, inconsistent formatting), an LLM can clean up extracted text.

### 6.1 Flow

```
chunk PDF → PyMuPDF (text per page) → LLM cleanup → chunk .md → Merge
```

### 6.2 Text Extraction with PyMuPDF

```python
import fitz  # PyMuPDF

doc = fitz.open("chunks/chunk-0001.pdf")
pages = []
for page in doc:
    pages.append(page.get_text("text"))
```

### 6.3 LLM Prompt Design

Each chunk (or sub-chunk of ~4000 tokens) is sent with the following system prompt:

```
You are a document formatting assistant. Convert the following extracted PDF
text into clean GitHub-Flavored Markdown. Rules:
- Preserve all headings as Markdown headings (# ## ### etc.)
- Preserve bullet and numbered lists
- Format tables as Markdown tables
- Remove page headers, footers, and page numbers
- Do not add, remove, or rephrase content
- Output only the Markdown, no commentary
```

### 6.4 Chunking for LLM Context

- Split extracted text into segments that fit within the model's context window minus prompt overhead.
- Overlap segments by ~200 tokens to avoid losing content at boundaries.
- After LLM processing, de-duplicate overlapping regions.

### 6.5 Cost & Rate Considerations

- Estimate token count before submission to predict cost.
- Respect model rate limits; use a semaphore to limit concurrent LLM calls.
- Log token usage per chunk for cost tracking.

---

## 7. Parallel Processing

### 7.1 Worker Pool

Stages 2–4 operate on independent chunks and are parallelised using a worker pool.

```
┌────────┐   ┌────────┐   ┌────────┐   ┌────────┐
│Worker 1│   │Worker 2│   │Worker 3│   │Worker 4│
│chunk-01│   │chunk-02│   │chunk-03│   │chunk-04│
└───┬────┘   └───┬────┘   └───┬────┘   └───┬────┘
    │            │            │            │
    ▼            ▼            ▼            ▼
         Stage 5: Merge (sequential)
```

- Default: 4 workers.
- Maximum recommended: 6 workers (limited by GROBID throughput and memory).
- Each worker processes one chunk through stages 2 → 3 → 4 sequentially.

### 7.2 Failure Isolation

A failing chunk does not block other workers. Failures are collected and reported at the end. The merge step skips failed chunks and logs warnings.

---

## 8. Validation & Quality Checks

### 8.1 Per-Chunk Validation

After each chunk is converted to Markdown:

| Check                    | Condition                                                | Action       |
| ------------------------ | -------------------------------------------------------- | ------------ |
| Empty output             | Markdown file is 0 bytes                                 | Mark failed  |
| Suspiciously small       | Output < `min_output_ratio` × chunk PDF size             | Log warning  |
| Encoding                 | Output is not valid UTF-8                                | Mark failed  |
| Heading structure        | No headings detected in a chunk expected to have them    | Log warning  |

### 8.2 Final Output Validation

| Check                    | Condition                                                | Action       |
| ------------------------ | -------------------------------------------------------- | ------------ |
| Total size               | `final.md` < 1% of source PDF size                      | Log warning  |
| Failed chunk count       | Exceeds `max_empty_chunks`                               | Abort        |
| TOC present              | `final.md` contains a generated TOC section              | Log warning if missing |
| Duplicate content        | Identical paragraphs across adjacent chunks (overlap artefact) | Log warning  |

### 8.3 Run Summary

At the end of each run, output a summary:

```
DocDown Run Summary
───────────────────
Input:          source.pdf (342 MB, 1847 pages)
Chunks:         37
Successful:     36
Failed:         1 (chunk-0023: GROBID timeout + pdfminer encoding error)
Tables found:   14
Output:         final.md (4.2 MB)
Duration:       12m 34s
Warnings:       2 (see run.log)
```

---

## 9. Error Handling

### 9.1 Strategy

All errors are categorised as **recoverable** or **fatal**.

| Error                          | Category    | Behaviour                                           |
| ------------------------------ | ----------- | --------------------------------------------------- |
| GROBID timeout on a chunk      | Recoverable | Retry once, then fallback to pdfminer               |
| GROBID service down            | Recoverable | Wait up to 60 s for recovery, then fallback all     |
| pdfminer failure on a chunk    | Recoverable | Skip chunk, log, continue                           |
| Pandoc crash on a chunk        | Recoverable | Skip chunk, log, continue                           |
| qpdf split failure             | Fatal       | Abort pipeline with error message                   |
| Input file not found           | Fatal       | Abort immediately                                   |
| All chunks failed              | Fatal       | Abort, no output produced                           |
| Disk full                      | Fatal       | Abort with clear error                              |

### 9.2 Logging

- All log output goes to `run.log` and stderr.
- Log levels: `DEBUG`, `INFO`, `WARN`, `ERROR`.
- Default level: `INFO`.
- Each log entry includes a timestamp and the chunk identifier where applicable.

---

## 10. Performance Characteristics

Estimated processing times (on a 4-core machine, SSD storage):

| Stage          | Per-chunk estimate | Notes                                |
| -------------- | ------------------ | ------------------------------------ |
| Split          | ~5 s total         | Single pass, I/O bound              |
| GROBID extract | 10–60 s            | Depends on chunk complexity          |
| Pandoc convert | 1–5 s              | Fast; CPU bound                      |
| Table extract  | 5–30 s             | Only chunks with detected tables     |
| Merge + TOC    | 1–3 s total        | Single pass                          |

Memory usage is bounded by the chunk size. A 50-page chunk typically requires < 500 MB of working memory for GROBID.

---

## 11. Platform & Cross-Platform

### 11.1 Target Environments

| Environment       | Priority  | Notes                                                        |
| ----------------- | --------- | ------------------------------------------------------------ |
| Linux (local)     | Primary   | Ubuntu 22.04+ recommended. All tools available via apt/pip.  |
| GitHub Actions    | Primary   | `ubuntu-latest` runner. GROBID via Docker service container. |
| Windows (local)   | Secondary | For debugging. Requires Docker Desktop or WSL2 for GROBID.   |

### 11.2 Python Version

Python 3.10+ (for `match` statements, `|` union types in type hints, and `pathlib` improvements).

### 11.3 Cross-Platform Implementation Rules

1. **Paths:** Use `pathlib.Path` everywhere. Never concatenate paths with string `/` or `\`.
2. **Subprocess calls:** Invoke all external tools (`qpdf`, `pandoc`, `pdftk`) via `subprocess.run()` with list arguments (not shell strings). This avoids shell-escaping issues across platforms.
3. **File merging:** Implement chunk concatenation in Python (`open` / `write`), not via shell `cat`.
4. **Line endings:** Write all output files with `\n` (Unix-style). Use `newline=""` or explicit encoding when writing.
5. **Docker:** GROBID is accessed over HTTP (`localhost:8070`). Docker availability is checked at startup; if unavailable, the pipeline falls back to pdfminer for all chunks.
6. **Temp files:** Use `tempfile` module or the working directory — never hardcode `/tmp`.

### 11.4 GitHub Actions CI

Minimal workflow structure:

```yaml
# .github/workflows/ci.yml
name: CI
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    services:
      grobid:
        image: lfoppiano/grobid:0.8.1
        ports:
          - 8070:8070
    steps:
      - uses: actions/checkout@v4
      - name: Install system deps
        run: sudo apt-get install -y qpdf pandoc ghostscript
      - uses: actions/setup-python@v5
        with:
          python-version: "3.12"
      - name: Install Python deps
        run: pip install -e ".[dev]"
      - name: Run tests
        run: pytest
```

### 11.5 Windows Development Notes

- Install `qpdf` and `pandoc` via [Scoop](https://scoop.sh), [Chocolatey](https://chocolatey.org), or direct installers.
- GROBID: use Docker Desktop, or skip GROBID tests and rely on pdfminer fallback during local debugging.
- Camelot requires Ghostscript for Windows — install from the [official site](https://ghostscript.com) and ensure `gswin64c` is on PATH.
- Run tests with `pytest` as on Linux; no platform-specific test configuration needed.

---

## 12. Future Considerations

These items are explicitly out of scope for the initial implementation but are documented for future reference.

- **OCR support:** Add Tesseract as a pre-processing step for scanned PDFs. Would slot in before Stage 2.
- **Image extraction:** Extract embedded images and reference them in Markdown. Requires `pdfimages` or PyMuPDF image extraction.
- **Incremental processing:** Re-process only changed/failed chunks instead of the full pipeline.
- **Web UI:** Lightweight interface for uploading PDFs and monitoring pipeline progress.
- **Output formats beyond Markdown:** DOCX, HTML, EPUB via Pandoc's output format support.
