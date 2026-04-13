# Task 10.2 - Conversion Workflow Orchestration And Operations Model

## Summary

Define and implement the document-conversion operating workflow so production usage is reliable and aligned with CI/CD deployment behavior.

This task focuses on runtime operations for conversion jobs, not repository validation/deployment automation.

## Dependencies

- Task 10.1 (CI/CD pipeline and deployment workflow)

## Acceptance Criteria

- [ ] A conversion workflow model is documented (intake -> queue -> worker -> artifacts -> status).
- [ ] Job states are defined and used consistently (`queued`, `running`, `succeeded`, `failed`, `retrying`).
- [ ] Retry policy distinguishes transient failures from deterministic failures.
- [ ] Artifact storage layout is defined for traceability (input, final markdown, logs, summary per job).
- [ ] Idempotency strategy is documented (input hash + options).
- [ ] Operational limits are documented (max input size/pages, timeout policy, concurrency caps).
- [ ] A runbook exists for start/stop/restart, diagnosis, and recovery for the conversion worker/service.
- [ ] CI/CD handoff to runtime workflow is documented (what CD deploys and what it restarts).

## Implementation Notes

### Scope

The goal is to make conversion execution operationally safe in production. CI/CD should deploy and restart runtime components, while this task defines and stabilizes how conversion work is accepted, processed, and observed.

### Recommended Baseline

- Intake:
  - watched folder, API endpoint, or manual enqueue command
- Queue:
  - Redis-backed queue (or SQLite queue for low load)
- Worker:
  - isolated workdir per job
  - deterministic processing path
- Artifacts:
  - stable per-job output path with timestamps and logs
- Observability:
  - status list command/dashboard
  - queue depth, failure rate, runtime metrics

### Integration Boundary With Task 10.1

- Task 10.1 provides CI/CD pipelines and deployment mechanics.
- Task 10.2 provides runtime conversion orchestration and operations policy.
- CD should restart or reload the conversion service defined in this task.

## References

- [task-10.0-ci-cd-prerequisites.md](task-10.0-ci-cd-prerequisites.md)
- [task-10.1-ci-cd-pipeline.md](task-10.1-ci-cd-pipeline.md)
- [../technical-design.md](../technical-design.md)
