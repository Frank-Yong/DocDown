# DocDown — PDF-to-Markdown Conversion Pipeline Specification

## 1. Overview

DocDown is a pipeline for converting large PDF documents (300+ MB) into clean, structured Markdown. The system must handle large files reliably, preserve document structure, and produce usable Markdown output with minimal manual cleanup.

## 2. Goals

- Convert large PDF documents to GitHub-Flavored Markdown (GFM).
- Preserve document structure: headings, sections, lists, and tables.
- Remain memory-stable during processing (streaming/chunking).
- Avoid silent content corruption or data loss.
- Produce a navigable Table of Contents derived from extracted headings.

## 3. Non-Goals

- OCR-based extraction (only needed for scanned documents; excluded from default pipeline).
- Preservation of original PDF page numbers or bookmark-based TOC.
- GUI-based tooling.

## 4. Platform

### 4.1 Target Environments

| Environment       | Priority  | Purpose                          |
| ----------------- | --------- | -------------------------------- |
| Linux (local)     | Primary   | Development and production use   |
| GitHub Actions    | Primary   | CI/CD — automated runs on push   |
| Windows (local)   | Secondary | Debugging and development        |

### 4.2 Runtime Requirements

- **Python:** 3.10+
- **Docker:** Required for GROBID (Linux & GitHub Actions). On Windows, Docker Desktop or WSL2-based Docker.
- **Shell:** All pipeline commands are executed via Python's `subprocess` module — no dependency on bash. Shell examples in documentation use bash syntax for readability.

### 4.3 Cross-Platform Considerations

- All file paths use `pathlib.Path` (no hardcoded `/` or `\` separators).
- Shell commands (`qpdf`, `pandoc`, `pdftk`) are invoked via `subprocess`, not shell scripts.
- File merging and concatenation are implemented in Python, not via `cat` or other shell utilities.
- GROBID is accessed over HTTP — platform-agnostic.
- CI environment assumes `ubuntu-latest` GitHub Actions runner with Docker support.

## 5. Architecture

The pipeline consists of five sequential stages:

```
PDF Input → Split → Extract → Convert → Post-process → Merged Markdown Output
```

### 5.1 Stage 1 — Split

Split the input PDF into manageable chunks to prevent converter crashes and memory exhaustion.

| Property       | Value                        |
| -------------- | ---------------------------- |
| Tool           | `qpdf` (preferred), `pdftk`  |
| Chunk size     | ~50 pages                    |
| Output         | `chunk-NNN.pdf`              |

Example:

```bash
qpdf input.pdf --split-pages=50 chunk-%03d.pdf
```

### 5.2 Stage 2 — Extract Structured Content

Extract document structure from each chunk into a structured intermediate format.

**Primary method — GROBID:**

| Property     | Value                                              |
| ------------ | -------------------------------------------------- |
| Tool         | GROBID (Docker: `lfoppiano/grobid:latest`)         |
| Input        | Chunk PDFs                                         |
| Output       | TEI XML per chunk                                  |
| Capabilities | Sections, headings, references, semantic structure |

```bash
docker run -p 8070:8070 lfoppiano/grobid:latest
```

**Fallback method — pdfminer.six:**

| Property     | Value                                      |
| ------------ | ------------------------------------------ |
| Tool         | `pdfminer.six`                             |
| Input        | Chunk PDFs                                 |
| Output       | Plain text (ordered)                       |
| Limitations  | No semantic structure; weak table/image support |

### 5.3 Stage 3 — Convert to Markdown

Convert the intermediate format to GitHub-Flavored Markdown using Pandoc.

| Property | Value                          |
| -------- | ------------------------------ |
| Tool     | Pandoc                         |
| Input    | TEI XML (primary) or HTML      |
| Output   | GFM Markdown per chunk         |

From TEI XML:

```bash
pandoc input.xml -f tei -t gfm -o output.md
```

From HTML:

```bash
pandoc input.html -t gfm -o output.md
```

### 5.4 Stage 4 — Post-process (Tables & Layouts)

Handle complex layout elements that core extraction misses.

| Element  | Tool                        |
| -------- | --------------------------- |
| Tables   | Camelot (preferred), Tabula |
| Columns  | Camelot                     |
| Forms    | Camelot                     |

Table output is merged into the corresponding Markdown chunk.

### 5.5 Stage 5 — Merge & Generate TOC

Concatenate all chunk Markdown files and generate a Table of Contents from headings.

```bash
cat chunk-*.md > merged.md
pandoc merged.md --toc -o final.md
```

The original PDF index/TOC is **not** preserved. A new TOC is rebuilt from extracted headings, which produces a more usable result in Markdown.

## 6. Alternative Pipeline — LLM-Assisted

An optional higher-quality pipeline for messy or poorly structured PDFs.

| Stage | Description                                          |
| ----- | ---------------------------------------------------- |
| 1     | Extract text per page using PyMuPDF                  |
| 2     | Send chunks to LLM with prompt: *"Convert to clean Markdown. Preserve headings, lists, tables."* |
| 3     | Merge LLM-cleaned chunks                             |

Trade-offs: higher output quality, slower processing, LLM cost.

## 7. Index & TOC Handling

### 7.1 Logical TOC (Bookmarks)

Internal PDF bookmarks are **lost** during split and text extraction. These are not recoverable in the Markdown output.

### 7.2 Printed TOC / Index Pages

Printed TOC text survives extraction but loses meaning:

- Page numbers become invalid after conversion.
- Layout (dot-leaders, columns) is mangled by most converters.
- Multi-column A–Z indexes typically merge into unreadable single lines.

### 7.3 Recommended Strategy

1. Ignore the original index.
2. Optionally extract TOC metadata before splitting via `pdftk dump_data | grep Bookmark`.
3. Rebuild TOC from Markdown headings using Pandoc `--toc`.

## 8. Operational Requirements

### 8.1 Parallelism

- Process chunks in parallel, limited to 4–6 concurrent workers.

### 8.2 Intermediate Files

- Retain all intermediate files (XML, HTML) for debugging and reprocessing.

### 8.3 Validation

- After conversion, validate that output size is proportional to input size.
- Flag chunks where output is unexpectedly small (indicates missing content).

## 9. Constraints

| Constraint                                  | Rationale                                   |
| ------------------------------------------- | ------------------------------------------- |
| No single-step PDF → Markdown conversion    | Fails or produces garbage at 300+ MB        |
| No GUI-only tools                           | Crash or hang on large files                |
| No OCR unless explicitly required           | Massive overhead for already-digital PDFs   |

## 10. Dependencies

| Tool/Library   | Purpose                     | Install                                |
| -------------- | --------------------------- | -------------------------------------- |
| qpdf           | PDF splitting               | Package manager / CLI                  |
| GROBID         | Structured extraction       | Docker (`lfoppiano/grobid:latest`)     |
| pdfminer.six   | Fallback text extraction    | `pip install pdfminer.six`             |
| Pandoc         | Format conversion           | Package manager / CLI                  |
| Camelot        | Table extraction            | `pip install camelot-py[cv]`           |
| PyMuPDF        | Page-level text extraction  | `pip install pymupdf`                  |
