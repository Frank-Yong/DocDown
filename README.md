# DocDown

PDF-to-Markdown conversion pipeline for large documents (300+ MB). Splits, extracts structure, converts to GitHub-Flavored Markdown, and reassembles with a generated table of contents.

## Status

✅ **Operational converter** — Fast-Path 01 is complete and the deterministic pipeline is running end-to-end.

## Delivery Workflow

- CI runs on every pull request (validation, tests, packaging checks).
- CD runs when changes are merged to `main`.
- CD executes on a local self-hosted GitHub Actions runner for deployment.
