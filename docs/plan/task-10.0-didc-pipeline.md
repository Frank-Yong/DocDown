# Task 10.0 - CI/CD And Conversion Workflow Prerequisites

## Summary

Capture and lock the implementation decisions required before Stage 10 execution.

This task establishes the decision baseline that Task 10.1 (CI/CD pipeline) and Task 10.2 (conversion workflow operations) will implement.

## Dependencies

- Task 8.3 (run summary generation)

## Acceptance Criteria

- [ ] Deploy target contract is selected and documented.
- [ ] Release layout strategy is selected and documented.
- [ ] Local hosted GitHub runner details are documented (labels, OS user, working directory, required permissions).
- [ ] Runtime conversion operating mode is selected for initial rollout.
- [ ] Required secrets and environment variables are listed with ownership.
- [ ] Rollback command/path and post-deploy smoke check command/pass criteria are documented.
- [ ] Task 10.1 and Task 10.2 acceptance criteria are reviewed and aligned with these decisions.

## Implementation Notes

### Required Decisions

1. Deploy target contract:
  - artifact handoff vs direct git pull on runner
2. Release layout:
  - symlink-based release switch vs in-place overwrite
3. Local hosted runner details:
  - runner labels
  - service account and permissions
  - deployment working directory
4. Conversion runtime model:
  - watched folder only, or
  - queue + worker (SQLite or Redis), or
  - manual enqueue CLI
5. Secrets and environment inventory:
  - CI/CD repository/environment secrets
  - runtime service environment variables
6. Recovery and verification:
  - one rollback command/path
  - one post-deploy smoke conversion command and success criteria

### Sequence

- Task 10.0 -> Task 10.1 -> Task 10.2

## References

- [../notes/2026-04-07_20-53-00.md](../notes/2026-04-07_20-53-00.md)
- [task-10.1-ci-cd-pipeline.md](task-10.1-ci-cd-pipeline.md)
- [task-10.2-conversion-workflow.md](task-10.2-conversion-workflow.md)