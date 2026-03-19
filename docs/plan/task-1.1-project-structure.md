# Task 1.1 — Initialize Project Structure

## Summary

Set up the Python project skeleton with package layout, dependency management, and entry point.

## Dependencies

None (first task).

## Acceptance Criteria

- [ ] Python package initialized (`docdown/`) with `__init__.py`.
- [ ] `pyproject.toml` (or `setup.cfg`) with project metadata and dependency declarations.
- [ ] Entry point defined: `docdown` CLI command.
- [ ] `requirements.txt` or equivalent lockfile with all dependencies pinned.
- [ ] Basic `README.md` at project root.
- [ ] `.gitignore` configured for Python projects.
- [ ] Project installs cleanly in a fresh virtual environment (`pip install -e .`).

## Implementation Notes

### Package layout

```
docdown/
├── __init__.py
├── __main__.py          # CLI entry point
├── cli.py               # argument parsing
├── config.py            # configuration loading (Task 1.2)
├── pipeline.py          # top-level pipeline orchestration
├── stages/
│   ├── __init__.py
│   ├── split.py
│   ├── extract.py
│   ├── convert.py
│   ├── tables.py
│   └── merge.py
├── utils/
│   ├── __init__.py
│   ├── logging.py
│   └── validation.py
tests/
├── __init__.py
├── test_split.py
├── test_extract.py
├── ...
```

### Key dependencies

| Package        | Purpose              |
| -------------- | -------------------- |
| pdfminer.six   | Fallback extraction  |
| pymupdf        | LLM pipeline extraction |
| camelot-py[cv] | Table extraction     |
| tabulate       | DataFrame → Markdown |
| pyyaml         | Config file parsing  |
| click          | CLI framework        |

### CLI skeleton

```python
# docdown/cli.py
import click

@click.command()
@click.argument("input_pdf", type=click.Path(exists=True))
@click.option("--config", "-c", type=click.Path(), help="Path to docdown.yaml")
@click.option("--workdir", "-o", type=click.Path(), default="./output")
def main(input_pdf, config, workdir):
    """Convert a PDF to Markdown."""
    pass
```

## References

- [spec.md §9 — Dependencies](../spec.md)
- [technical-design.md §3 — Directory & File Layout](../technical-design.md)
