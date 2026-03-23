# Task 2.1 — PDF Validation & Page Counting

## Summary

Validate the input PDF and determine its total page count before splitting.

## Dependencies

- Task 1.4 (working directory management)

## Acceptance Criteria

- [x] Input file existence is verified; clear error if missing.
- [x] Input file is validated as a valid PDF (`qpdf --check`).
- [x] Corrupted PDFs produce a clear fatal error with the `qpdf` diagnostic output.
- [x] Encrypted PDFs are detected; if a password is not provided, abort with a message.
- [x] Total page count is extracted (`qpdf --show-npages`).
- [x] Page count and file size are logged at `INFO` level.
- [x] Unit tests cover: valid PDF, missing file, corrupted file, encrypted file, page-count parsing failure.

Implemented in:
- `docdown/stages/split.py`
- `tests/test_split.py`

## Implementation Notes

### Commands

```bash
# Validate
qpdf --check input.pdf

# Page count
qpdf --show-npages input.pdf
```

### Encrypted PDF handling

```bash
qpdf --decrypt --password=PASS input.pdf decrypted.pdf
```

If no password is configured, abort. Do not attempt empty-password decryption by default (could mask issues).

### Error mapping

| qpdf exit code | Meaning            | Pipeline action |
| -------------- | ------------------ | --------------- |
| 0              | Valid              | Continue        |
| 2              | Errors found       | Fatal abort     |
| 3              | Warnings (usable)  | Log warning, continue |

### Artifact Class Diagram

```mermaid
classDiagram
	class PdfValidationResult {
		+int page_count
		+int file_size_bytes
	}

	class PdfValidationError {
		<<exception>>
	}

	class SplitStageModule {
		<<module: docdown/stages/split.py>>
		+validate_pdf(input_pdf, password, logger) PdfValidationResult
		-_is_encrypted(input_path, password) bool
		-_qpdf_command(flag, input_path) list~str~
		-_run_qpdf(command, password) CompletedProcess
		-_inject_password(command, password) tuple~list~str~, Path?~
		-_cleanup_password_file(password_file) None
		-_redact_command(command) str
		-_combined_output(result) str
		-_parse_page_count(stdout) int
	}

	class CliMain {
		<<module: docdown/cli.py>>
		+main(...) None
	}

	class LoggingModule {
		<<module: docdown/utils/logging.py>>
		+get_logger() Logger
		+log_tool_command(command, chunk_number) None
	}

	class WorkDir {
		<<module: docdown/workdir.py>>
		+stage_input(source_pdf) Path
	}

	class QpdfTool {
		<<external: qpdf>>
		+--show-encryption
		+--check
		+--show-npages
		+--password-file=...
	}

	class PasswordTempFile {
		<<temp file>>
		+docdown-qpdf-*.pwd
	}

	class TestSplit {
		<<tests/test_split.py>>
		+valid/missing/corrupted/encrypted
		+empty-password and parse-failure coverage
		+password redaction/logging coverage
	}

	class TestCli {
		<<tests/test_cli.py>>
		+validation wiring and error surfacing
	}

	CliMain ..> WorkDir : stages input PDF
	CliMain ..> SplitStageModule : calls validate_pdf
	SplitStageModule --> PdfValidationResult : returns
	SplitStageModule ..> PdfValidationError : raises
	SplitStageModule ..> LoggingModule : logger + tool command logs
	SplitStageModule ..> QpdfTool : executes commands
	SplitStageModule ..> PasswordTempFile : creates/cleans when password provided
	TestSplit ..> SplitStageModule : verifies behavior
	TestCli ..> CliMain : verifies integration
```

## References

- [technical-design.md §5.1 — Stage 1: Split](../technical-design.md)
- [spec.md §4.1 — Stage 1: Split](../spec.md)
