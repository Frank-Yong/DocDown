# Task 10.1 - CI/CD Pipeline And Deployment Workflow

## Summary

Create the initial automation for repository validation and deployment using the selected operating model:

- Pull request = CI
- Merge to main = CD
- CD runs on a local hosted GitHub Actions runner

This task covers repository automation and deployment mechanics. Document-conversion runtime orchestration (job intake, queueing, worker lifecycle, artifact retention) is tracked in Task 10.2.

## Dependencies

- Task 10.0 (CI/CD and conversion workflow prerequisites)

## Acceptance Criteria

- [x] A CI workflow exists under `.github/workflows/ci.yml`.
- [x] CI runs on pull requests and executes repository validation checks (tests as baseline).
- [x] CI uses a GitHub-hosted Ubuntu runner and includes required system dependencies for DocDown checks.
- [x] A CD workflow exists under `.github/workflows/cd.yml`.
- [x] CD triggers on push to `main` (merge path).
- [x] CD runs on a local hosted GitHub runner.
- [x] CD performs a deploy step using a documented, repeatable command path.
- [x] A rollback strategy is documented (retain previous release and restore command/path).
- [x] Workflow docs describe required repository/environment secrets and runner prerequisites.

## Implementation Notes

### Scope

This task defines the first production-ready CI/CD baseline for DocDown. It is intentionally minimal and should prioritize deterministic execution over broad feature coverage.

### CI Baseline

- Trigger: `pull_request`
- Runner: `ubuntu-latest`
- Steps:
  - checkout
  - Python setup
  - system dependency install (`qpdf`, `pandoc`, `ghostscript`)
  - install project dependencies
  - run automated tests

### CD Baseline

- Trigger: push to `main`
- Runner: `local hosted GitHub runner` (`self-hosted` label)
- High-level flow:
  - fetch/pull deployable revision
  - install/update runtime dependencies if required
  - perform atomic release switch (or equivalent safe replace)
  - restart service/worker process
  - retain previous release for rollback

### Operational Notes

- Keep deployment idempotent.
- Keep production secrets out of repository files.
- Keep rollback simple and tested.

## References

- [task-10.0-ci-cd-prerequisites.md](task-10.0-ci-cd-prerequisites.md)
- [../spec.md](../spec.md)
- [../technical-design.md](../technical-design.md)
