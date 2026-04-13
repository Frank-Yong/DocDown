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
  - v1 default: direct git pull on runner
  - alternative: artifact handoff
  - use artifact handoff when signed artifacts, strict reproducibility, or multi-environment promotion are required
  - record decision gates: reproducibility requirement, compliance/signing requirement, operational complexity tolerance, rollback speed target
2. Release layout:
  - v1 default: symlink-based release switch
  - alternative: in-place overwrite
  - prefer symlink-based switching for faster rollback and safer cutover
  - use in-place overwrite only when filesystem or hosting constraints prevent symlink usage
3. Local hosted runner details:
  - primary runner host: node01
  - fallback runner host: node02
  - node01 profile:
    - Ubuntu Server 24.04 LTS minimal (UEFI)
    - interface `eno1`, DHCP reserved `192.168.1.x`
    - 4c/8t Xeon E3-1245 v2, 15 GiB RAM, 119.2G SSD
    - preferred for CI/CD execution due to higher RAM and SSD storage
  - node02 profile:
    - Ubuntu Server 24.04 LTS minimal (Legacy/CSM)
    - interface `ens5`, DHCP reserved `192.168.1.x`
    - 4c/8t Xeon W3550, 7.7 GiB RAM, 465.8G HDD
    - kept as standby/failover runner
  - both hosts:
    - NIC speed 1GbE
    - NVIDIA driver not installed (`nouveau` in use, `nvidia-smi` unavailable)
    - GPU acceleration is out of scope for v1 runner setup
  - define runner labels (minimum: `self-hosted`, `linux`, `x64`, `docdown`)
  - service account (both nodes): `docdown-runner`
  - required permissions:
    - read/write under deployment root (`/opt/docdown`)
    - execute a scoped release-activation wrapper that switches `/opt/docdown/current`
    - restart DocDown services via `systemctl` (worker/api)
    - no unrestricted root shell access
  - provisioning baseline (run as root on each node):
    - `useradd --create-home --shell /bin/bash docdown-runner`
    - `install -d -o docdown-runner -g docdown-runner /opt/docdown`
    - install root-owned wrapper `/usr/local/bin/docdown-activate-release` that:
      - accepts exactly one release path argument
      - verifies path is under `/opt/docdown/releases/`
      - runs `ln -sfn <validated-release> /opt/docdown/current`
    - create `/etc/sudoers.d/docdown-runner` with:
      - `docdown-runner ALL=(root) NOPASSWD: /usr/local/bin/docdown-activate-release, /usr/bin/systemctl restart docdown-worker, /usr/bin/systemctl restart docdown-api`
    - `chmod 440 /etc/sudoers.d/docdown-runner`
    - `visudo -cf /etc/sudoers.d/docdown-runner`
  - deployment working directory and release paths (v1):
    - deploy root: `/opt/docdown`
    - releases: `/opt/docdown/releases/<timestamp-or-sha>`
    - active symlink: `/opt/docdown/current`
    - shared runtime data: `/opt/docdown/shared`
    - runner workspace checkout (temp/build): `/opt/docdown/workspace`
4. Conversion runtime model:
  - v1 default: queue + worker (SQLite-backed queue)
  - intake mode for v1: manual enqueue CLI (watched folder/API deferred)
  - rationale: keeps operations job-based without introducing Redis or API complexity in first rollout
  - defer to later phase:
    - Redis queue backend
    - watched-folder intake
    - API submission endpoint
5. Secrets and environment inventory:
  - CI/CD repository/environment secrets (v1):
    - `DOCDOWN_DEPLOY_HOST` (if remote orchestration is introduced)
    - `DOCDOWN_DEPLOY_SSH_KEY` (if remote orchestration is introduced)
    - no mandatory additional secret for local self-hosted in-place deployment baseline
  - runtime service environment variables (v1):
    - `DOCDOWN_ENV=production`
    - `DOCDOWN_CONFIG_PATH=/opt/docdown/shared/docdown.yaml`
    - `DOCDOWN_WORK_ROOT=/opt/docdown/shared/runs`
    - `DOCDOWN_LOG_LEVEL=INFO`
    - `DOCDOWN_QUEUE_DB=/opt/docdown/shared/queue/jobs.sqlite3`
  - ownership:
    - DevOps owns secret provisioning and rotation
    - App owners own runtime config values in shared config
6. Recovery and verification:
  - rollback command/path (v1):
    - relink active release: `sudo /usr/local/bin/docdown-activate-release /opt/docdown/releases/<previous-release>`
    - restart worker: `sudo systemctl restart docdown-worker`
    - restart API: `sudo systemctl restart docdown-api`
  - post-deploy smoke conversion command (v1):
    - `/opt/docdown/current/.venv/bin/docdown /opt/docdown/shared/smoke/input.pdf -o /opt/docdown/shared/smoke/output --log-level INFO`
  - smoke success criteria:
    - command exit code `0`
    - `/opt/docdown/shared/smoke/output/final.md` exists and is non-empty
    - run summary is present in stderr and appended to `run.log`

### Sequence

- Task 10.0 -> Task 10.1 -> Task 10.2

## References

- [../notes/2026-04-07_20-53-00.md](../notes/2026-04-07_20-53-00.md)
- [task-10.1-ci-cd-pipeline.md](task-10.1-ci-cd-pipeline.md)
- [task-10.2-conversion-workflow.md](task-10.2-conversion-workflow.md)