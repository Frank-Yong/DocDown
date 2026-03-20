# DocDown - Alternatives to Python

## Purpose

This note outlines realistic alternatives to a Python implementation for DocDown. The goal is not to change the pipeline itself, but to show which parts can be implemented in other languages, with existing tools, or through external services.

In each option below, the linked tasks are the ones most directly "un-pythonized" by that approach.

## Short recommendation

If the goal is "not Python" without rewriting the whole architecture, the best option is a C# host that keeps `qpdf`, Pandoc, and GROBID as external dependencies and replaces the Python-only libraries case by case.

If the goal is the fastest delivery with the least custom extraction logic, the best option is a managed API approach.

If the goal is to stay fully self-managed without Python, a JVM-based stack is the strongest non-Python alternative because PDFBox and Tabula are mature.

## Option 1 - C# host, existing CLI tools and services

### What it is

Build the pipeline as a .NET console application and keep the existing external tools where they already make sense:

- `qpdf` for validation and splitting
- GROBID over HTTP for structured extraction
- Pandoc for Markdown conversion
- Docker only for running GROBID

This keeps the current architecture mostly intact while moving orchestration, configuration, logging, retries, file handling, and concurrency out of Python.

### Good fit for

- A Windows-heavy team
- Strong C# experience
- A desire to keep self-hosted infrastructure
- Minimal redesign of the current plan

### Suggested implementation stack

- .NET 8 console app
- `System.CommandLine` for CLI
- `Microsoft.Extensions.Configuration` for config
- `Microsoft.Extensions.Logging` or Serilog for logging
- `HttpClient` plus Polly for GROBID and LLM retries
- `Parallel.ForEachAsync` or TPL Dataflow for worker-pool behavior
- `CliWrap` or plain `ProcessStartInfo` for `qpdf` and Pandoc

### Tasks this un-pythonizes directly

- [task-1.1-project-structure.md](task-1.1-project-structure.md)
- [task-1.2-configuration.md](task-1.2-configuration.md)
- [task-1.3-logging.md](task-1.3-logging.md)
- [task-1.4-workdir-management.md](task-1.4-workdir-management.md)
- [task-2.1-pdf-validation.md](task-2.1-pdf-validation.md)
- [task-2.2-chunk-splitting.md](task-2.2-chunk-splitting.md)
- [task-3.1-grobid-integration.md](task-3.1-grobid-integration.md)
- [task-3.3-extraction-orchestration.md](task-3.3-extraction-orchestration.md)
- [task-4.1-pandoc-conversion.md](task-4.1-pandoc-conversion.md)
- [task-4.2-markdown-cleanup.md](task-4.2-markdown-cleanup.md)
- [task-6.1-chunk-merging.md](task-6.1-chunk-merging.md)
- [task-6.2-toc-generation.md](task-6.2-toc-generation.md)
- [task-6.3-pre-split-toc-extraction.md](task-6.3-pre-split-toc-extraction.md)
- [task-7.1-worker-pool.md](task-7.1-worker-pool.md)
- [task-7.2-failure-isolation.md](task-7.2-failure-isolation.md)
- [task-8.1-chunk-validation.md](task-8.1-chunk-validation.md)
- [task-8.2-final-validation.md](task-8.2-final-validation.md)
- [task-8.3-run-summary.md](task-8.3-run-summary.md)
- [task-9.2-llm-integration.md](task-9.2-llm-integration.md)
- [task-9.3-llm-chunking.md](task-9.3-llm-chunking.md)

### Python-specific tasks that still need replacement choices

- [task-3.2-pdfminer-fallback.md](task-3.2-pdfminer-fallback.md): replace `pdfminer.six` with Poppler `pdftotext`, Apache PDFBox, Apache Tika, or UglyToad.PdfPig.
- [task-5.1-table-detection.md](task-5.1-table-detection.md): replace Camelot with Tabula-java, a cloud document API, or a custom extractor.
- [task-5.2-table-to-markdown.md](task-5.2-table-to-markdown.md): implement in C# once table output is available.
- [task-9.1-pymupdf-extraction.md](task-9.1-pymupdf-extraction.md): replace PyMuPDF with PdfPig, MuPDF bindings for .NET, or PDFBox via a sidecar.

### Main trade-offs

- Lowest disruption to the current design
- Still depends on non-.NET tools like `qpdf`, Pandoc, and GROBID
- Table extraction remains the hardest gap because Camelot is a Python-native choice in the current plan

## Option 2 - Full .NET implementation with selective sidecars

### What it is

Keep the application in C#, but try to replace as many Python-era dependencies as possible with .NET libraries or sidecar services.

### Likely replacements

- `pdfminer.six` -> UglyToad.PdfPig, PdfSharp-based readers, or Poppler `pdftotext`
- PyMuPDF -> PdfPig or MuPDF bindings
- Camelot -> Tabula-java sidecar or a managed API for tables
- LLM integration -> direct provider SDK or raw HTTP from C#

### Tasks this most changes

- [task-3.2-pdfminer-fallback.md](task-3.2-pdfminer-fallback.md)
- [task-5.1-table-detection.md](task-5.1-table-detection.md)
- [task-5.2-table-to-markdown.md](task-5.2-table-to-markdown.md)
- [task-5.3-table-merging.md](task-5.3-table-merging.md)
- [task-9.1-pymupdf-extraction.md](task-9.1-pymupdf-extraction.md)
- [task-9.2-llm-integration.md](task-9.2-llm-integration.md)
- [task-9.3-llm-chunking.md](task-9.3-llm-chunking.md)

### Main trade-offs

- Better long-term consistency if the team standardizes on .NET
- More engineering risk than Option 1 because the extraction stack changes materially
- You may end up with a sidecar JVM tool anyway for table extraction

## Option 3 - JVM-centric pipeline

### What it is

Build the orchestrator in Java or Kotlin and lean on the JVM PDF ecosystem.

### Why it is credible

The JVM has mature options for several hard parts of this project:

- Apache PDFBox for PDF parsing and text extraction
- Tabula-java for table extraction
- Apache Tika for document text extraction abstractions
- OkHttp or Spring WebClient for GROBID and LLM calls

### Good fit for

- Teams comfortable with Java or Kotlin
- A preference for self-managed infrastructure over vendor APIs
- A desire to avoid the Python packaging and runtime story entirely

### Tasks this un-pythonizes most cleanly

- [task-1.1-project-structure.md](task-1.1-project-structure.md)
- [task-1.2-configuration.md](task-1.2-configuration.md)
- [task-1.3-logging.md](task-1.3-logging.md)
- [task-1.4-workdir-management.md](task-1.4-workdir-management.md)
- [task-2.1-pdf-validation.md](task-2.1-pdf-validation.md)
- [task-2.2-chunk-splitting.md](task-2.2-chunk-splitting.md)
- [task-3.1-grobid-integration.md](task-3.1-grobid-integration.md)
- [task-3.2-pdfminer-fallback.md](task-3.2-pdfminer-fallback.md)
- [task-3.3-extraction-orchestration.md](task-3.3-extraction-orchestration.md)
- [task-4.1-pandoc-conversion.md](task-4.1-pandoc-conversion.md)
- [task-4.2-markdown-cleanup.md](task-4.2-markdown-cleanup.md)
- [task-5.1-table-detection.md](task-5.1-table-detection.md)
- [task-5.2-table-to-markdown.md](task-5.2-table-to-markdown.md)
- [task-5.3-table-merging.md](task-5.3-table-merging.md)
- [task-6.1-chunk-merging.md](task-6.1-chunk-merging.md)
- [task-6.2-toc-generation.md](task-6.2-toc-generation.md)
- [task-6.3-pre-split-toc-extraction.md](task-6.3-pre-split-toc-extraction.md)
- [task-7.1-worker-pool.md](task-7.1-worker-pool.md)
- [task-7.2-failure-isolation.md](task-7.2-failure-isolation.md)
- [task-8.1-chunk-validation.md](task-8.1-chunk-validation.md)
- [task-8.2-final-validation.md](task-8.2-final-validation.md)
- [task-8.3-run-summary.md](task-8.3-run-summary.md)
- [task-9.1-pymupdf-extraction.md](task-9.1-pymupdf-extraction.md)
- [task-9.2-llm-integration.md](task-9.2-llm-integration.md)
- [task-9.3-llm-chunking.md](task-9.3-llm-chunking.md)

### Main trade-offs

- Strongest fully self-managed non-Python option
- More divergence from the current task implementation notes than Option 1
- Operationally heavier than a pure C# host if your team is mostly .NET

## Option 4 - Managed document APIs

### What it is

Use a thin orchestrator in C#, Node.js, Go, or any other language, but outsource extraction-heavy stages to cloud APIs.

### Typical providers

- Azure AI Document Intelligence
- Google Document AI
- AWS Textract
- Mathpix or similar document-conversion APIs
- Unstructured API or similar hosted parsing platforms

### Tasks this can replace almost entirely

- [task-3.1-grobid-integration.md](task-3.1-grobid-integration.md)
- [task-3.2-pdfminer-fallback.md](task-3.2-pdfminer-fallback.md)
- [task-3.3-extraction-orchestration.md](task-3.3-extraction-orchestration.md)
- [task-5.1-table-detection.md](task-5.1-table-detection.md)
- [task-5.2-table-to-markdown.md](task-5.2-table-to-markdown.md)
- [task-5.3-table-merging.md](task-5.3-table-merging.md)
- [task-9.1-pymupdf-extraction.md](task-9.1-pymupdf-extraction.md)
- [task-9.2-llm-integration.md](task-9.2-llm-integration.md)
- [task-9.3-llm-chunking.md](task-9.3-llm-chunking.md)

### Tasks still needed locally

- [task-1.2-configuration.md](task-1.2-configuration.md)
- [task-1.3-logging.md](task-1.3-logging.md)
- [task-1.4-workdir-management.md](task-1.4-workdir-management.md)
- [task-2.1-pdf-validation.md](task-2.1-pdf-validation.md)
- [task-2.2-chunk-splitting.md](task-2.2-chunk-splitting.md)
- [task-4.1-pandoc-conversion.md](task-4.1-pandoc-conversion.md) if the provider does not already return Markdown
- [task-4.2-markdown-cleanup.md](task-4.2-markdown-cleanup.md)
- [task-6.1-chunk-merging.md](task-6.1-chunk-merging.md)
- [task-6.2-toc-generation.md](task-6.2-toc-generation.md)
- [task-7.1-worker-pool.md](task-7.1-worker-pool.md)
- [task-7.2-failure-isolation.md](task-7.2-failure-isolation.md)
- [task-8.1-chunk-validation.md](task-8.1-chunk-validation.md)
- [task-8.2-final-validation.md](task-8.2-final-validation.md)
- [task-8.3-run-summary.md](task-8.3-run-summary.md)

### Main trade-offs

- Fastest path to acceptable extraction quality
- Best option if tables are important early
- Highest recurring cost and strongest data-governance implications
- Greater vendor lock-in than the self-hosted options

## Option 5 - Keep Python out of the runtime, not necessarily the toolchain

### What it is

Treat Python-only capabilities as isolated build-time or sidecar tools, while the main application is written in C# or another language.

Examples:

- Run Camelot as a separate worker service and call it over HTTP
- Run a small Python extraction helper process only for table detection
- Keep the core CLI, orchestration, logging, and packaging in C#

### Tasks this isolates rather than rewrites

- [task-3.2-pdfminer-fallback.md](task-3.2-pdfminer-fallback.md)
- [task-5.1-table-detection.md](task-5.1-table-detection.md)
- [task-5.2-table-to-markdown.md](task-5.2-table-to-markdown.md)
- [task-9.1-pymupdf-extraction.md](task-9.1-pymupdf-extraction.md)

### Main trade-offs

- Pragmatic if "no Python in the main app" is enough
- Lower rewrite risk than replacing every Python-oriented tool
- Still leaves Python somewhere in deployment and operations

## Best-fit summary

| Goal | Best option |
|---|---|
| Minimal redesign, non-Python app | Option 1 - C# host plus existing tools |
| Deep .NET ownership | Option 2 - Full .NET with selective sidecars |
| Strongest self-managed non-Python stack | Option 3 - JVM-centric pipeline |
| Fastest delivery and best early extraction quality | Option 4 - Managed document APIs |
| Keep Python out of the main runtime only | Option 5 - Sidecar isolation |

## Practical recommendation for this repo

If you want a serious non-Python path without throwing away the current planning work, use this sequence:

1. Recast the host application and orchestration tasks in C#.
2. Keep `qpdf`, Pandoc, and GROBID as external dependencies.
3. Replace `pdfminer.six` with PDFBox, Poppler `pdftotext`, or PdfPig.
4. Replace Camelot with Tabula-java or a managed document API.
5. Keep the LLM path language-agnostic and implement it directly against the provider API.

That preserves most of the current architecture while removing Python from the core implementation.