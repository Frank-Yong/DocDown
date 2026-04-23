# DocDownOps Runner Setup (node01 primary, node02 standby)

Purpose: run DocDownOps job processing on LAN hosts, with node01 active and node02 disabled standby.

Important:
- DocDownOps submit workflow currently runs on GitHub-hosted runner (`ubuntu-latest`).
- The "runner" here means the local `scripts/runner-loop.sh` service, not a GitHub Actions self-hosted runner.
- All command blocks are intended to be executed from an operator shell (for example `clusteradmin`), not by logging in directly as `docdown-runner`.
- Where file ownership or git operations must run as `docdown-runner`, commands already use `sudo -u docdown-runner` explicitly.
- Paste-safe pattern: each section writes a temporary script file and executes it to avoid broken multi-line paste in SSH terminals.

## 1) Host prerequisites (run on node01 and node02 as clusteradmin)

```bash
cat >/tmp/docdownops-host-prereq.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

sudo apt-get update
sudo apt-get install -y git python3

sudo groupadd --force docdown-runner
id -u docdown-runner >/dev/null 2>&1 || sudo useradd --create-home --shell /bin/bash --gid docdown-runner docdown-runner

sudo install -d -o docdown-runner -g docdown-runner /opt/docdown-ops
sudo install -d -o docdown-runner -g docdown-runner /opt/docdown-ops/releases
EOF

bash /tmp/docdownops-host-prereq.sh
```

## 2) Clone DocDownOps working tree

Run from your operator shell on each node. The block below explicitly switches to `docdown-runner`. Replace clone URL if you use SSH.

If the executor script and related runner changes are not merged to `main` yet, use the active delivery branch instead of `main`. Current pre-merge branch:

- `task/10.2-runner-loop`

```bash
cat >/tmp/docdownops-clone-update.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

DOCDOWNOPS_BRANCH="${DOCDOWNOPS_BRANCH:-task/10.2-runner-loop}"

sudo -u docdown-runner -H bash -lc '
  set -euo pipefail
  cd /opt/docdown-ops
  if [ ! -d releases/docdownops-main/.git ]; then
    git clone https://github.com/Frank-Yong/DocDownOps.git releases/docdownops-main
  fi
  cd releases/docdownops-main
  git fetch origin
  git checkout '"'"'${DOCDOWNOPS_BRANCH}'"'"'
  git pull --ff-only origin '"'"'${DOCDOWNOPS_BRANCH}'"'"'
'
EOF

bash /tmp/docdownops-clone-update.sh
```

Once the branch is merged, set `DOCDOWNOPS_BRANCH=main` before running the same block, or edit the default branch in the temporary script.

## 3) Configure executor command (node01 and node02)

`runner-loop.sh` requires `DOCDOWN_JOB_EXECUTOR` and will call it as:
- `<executor> <manifest_path>`

Create environment file:

```bash
cat >/tmp/docdownops-env-setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

sudo tee /etc/default/docdownops-runner >/dev/null <<'EOS'
DOCDOWN_JOB_EXECUTOR=/opt/docdown-ops/releases/docdownops-main/scripts/docdown-execute-manifest.sh
DOCDOWN_GIT_SYNC_ENABLED=true
DOCDOWN_GIT_COMMIT_NAME=DocDownOps Runner
DOCDOWN_GIT_COMMIT_EMAIL=docdownops-runner@local
EOS

sudo chmod 640 /etc/default/docdownops-runner
sudo chown root:docdown-runner /etc/default/docdownops-runner
EOF

bash /tmp/docdownops-env-setup.sh
```

Notes:
- `DOCDOWN_JOB_EXECUTOR` must exist and be executable by `docdown-runner`.
- Current repo-managed V1 path: `/opt/docdown-ops/releases/docdownops-main/scripts/docdown-execute-manifest.sh`.
- `DOCDOWN_GIT_SYNC_ENABLED=true` enables status/result writeback to origin, which the rest of this runbook assumes.
- `DOCDOWN_GIT_COMMIT_NAME` and `DOCDOWN_GIT_COMMIT_EMAIL` keep runner-authored sync commits deterministic.
- Executor should return exit code 0 on success, non-zero on failure.
- If executor prints a URL in stdout, runner-loop captures first URL into `result_url`.

## 4) Install systemd service for runner-loop

```bash
cat >/tmp/docdownops-systemd-setup.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

sudo tee /etc/systemd/system/docdownops-runner.service >/dev/null <<'EOS'
[Unit]
Description=DocDownOps Runner Loop
After=network-online.target
Wants=network-online.target

[Service]
Type=simple
User=docdown-runner
Group=docdown-runner
WorkingDirectory=/opt/docdown-ops/releases/docdownops-main
EnvironmentFile=/etc/default/docdownops-runner
ExecStart=/usr/bin/env bash scripts/runner-loop.sh --poll-interval-seconds 10
Restart=always
RestartSec=5

[Install]
WantedBy=multi-user.target
EOS

sudo systemctl daemon-reload
EOF

bash /tmp/docdownops-systemd-setup.sh
```

## 5) Node01 primary mode

Enable and start on node01:

```bash
# Run on node01
sudo systemctl enable docdownops-runner.service
sudo systemctl start docdownops-runner.service
sudo systemctl status docdownops-runner.service --no-pager
```

## 6) Node02 standby mode

Disable and stop on node02 (recommended default):

```bash
# Run on node02
sudo systemctl disable docdownops-runner.service
sudo systemctl stop docdownops-runner.service || true
sudo systemctl status docdownops-runner.service --no-pager || true
```

## 7) Failover procedure

When node01 is unavailable, activate node02:

```bash
# Run on node02
sudo systemctl enable docdownops-runner.service
sudo systemctl start docdownops-runner.service
sudo systemctl status docdownops-runner.service --no-pager
```

When node01 is recovered, return to normal posture:

```bash
# Run on node02
sudo systemctl stop docdownops-runner.service
sudo systemctl disable docdownops-runner.service

# Run on node01
sudo systemctl enable docdownops-runner.service
sudo systemctl start docdownops-runner.service
```

Operator note:
- If the checkout is behind on either node, update it as `docdown-runner` before starting the service.
- Prefer `git reset --hard origin/<branch>` over interactive `git pull` when recovering a host-local checkout to a known branch tip.

Credential-free operator maintenance commands:

```bash
# Run on node01 or node02 from the clusteradmin shell
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  scripts/git-github-app.sh fetch task/10.2-runner-loop
  git checkout task/10.2-runner-loop
  git reset --hard origin/task/10.2-runner-loop
  git rev-parse --short HEAD
'
```

For an authenticated fast-forward pull without the username/password prompt:

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  scripts/git-github-app.sh pull task/10.2-runner-loop
'
```

## 8) Basic runtime checks

```bash
# Service health
sudo systemctl status docdownops-runner.service --no-pager

# Recent logs
sudo journalctl -u docdownops-runner.service -n 100 --no-pager

# Queue/status files in working copy
sudo -u docdown-runner -H bash -lc 'cd /opt/docdown-ops/releases/docdownops-main && ls -la jobs/queued jobs/running jobs/done status'
```

## 9) Push-Conflict And Failed-Writeback Recovery

Use this procedure when `docdownops-runner.service` logs show authenticated pull/push failures, non-fast-forward errors, or repeated writeback failures after a job has already been executed locally.

1. Stabilize the active node

```bash
# Run on the active node (node01 normally, node02 during failover)
sudo systemctl stop docdownops-runner.service
sudo systemctl status docdownops-runner.service --no-pager || true
sudo journalctl -u docdownops-runner.service -n 100 --no-pager
```

2. Inspect the repo state as `docdown-runner`

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  git status --short
  git log --oneline --decorate -n 10 -- jobs status results
  git rev-parse --abbrev-ref HEAD
'
```

3. Decide which recovery path applies

- Clean checkout, service only failed during refresh:
  - run authenticated refresh and restart the service
- Dirty checkout with local `jobs/`, `status/`, or `results/` changes:
  - identify the affected `job_id`
  - compare local changes with origin before deciding whether to push or discard them
- Dirty checkout with unrelated files outside `jobs/`, `status/`, or `results/`:
  - stop and inspect manually before restarting the service

4. Recovery path A: checkout is clean, remote simply moved

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  scripts/git-github-app.sh pull task/10.2-runner-loop
'

sudo systemctl start docdownops-runner.service
```

5. Recovery path B: local writeback files exist, but origin may already have them

First compare the local job files with origin:

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  job_id=YOUR_JOB_ID
  git diff --name-status origin/task/10.2-runner-loop -- \
    jobs/done/${job_id}.json \
    status/${job_id}.json \
    status/history/${job_id}.jsonl \
    results/${job_id}
'
```

If origin already contains the same terminal files for that `job_id`, discard the local duplicates and resync:

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  scripts/git-github-app.sh fetch task/10.2-runner-loop
  git reset --hard origin/task/10.2-runner-loop
'

sudo systemctl start docdownops-runner.service
```

6. Recovery path C: local terminal files exist and origin is missing them

If the job finished locally but the terminal manifest/status/results are only present on disk in the local checkout, push them explicitly:

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  job_id=YOUR_JOB_ID
  git add \
    jobs/done/${job_id}.json \
    status/${job_id}.json \
    status/history/${job_id}.jsonl \
    results/${job_id}
  git -c user.name="${DOCDOWN_GIT_COMMIT_NAME:-DocDownOps Runner}" \
      -c user.email="${DOCDOWN_GIT_COMMIT_EMAIL:-docdownops-runner@local}" \
      commit -m "Record ${job_id} succeeded"
  scripts/git-github-app.sh pull task/10.2-runner-loop
  scripts/git-github-app.sh push HEAD:task/10.2-runner-loop
'

sudo systemctl start docdownops-runner.service
```

7. Recovery path D: terminal job files are missing locally too

- Inspect `/opt/docdown/workspace/jobs/<job_id>/summary.json` and the local logs first.
- If the job actually failed before terminal writeback was prepared, treat it as a job replay/requeue case rather than a pure git recovery case.
- Do not fabricate missing `results/` or `status/` files without first confirming the job outcome from the workspace.

8. Post-recovery verification

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  git status --short
  git log --oneline --decorate -n 5 -- jobs status results
'

sudo systemctl status docdownops-runner.service --no-pager
sudo journalctl -u docdownops-runner.service -n 50 --no-pager
```

Expected healthy end state:
- working tree is clean
- branch is on `task/10.2-runner-loop` (or the current active delivery branch)
- service is active and returns to `No queued jobs available to claim.` while idle

## 10) Replay Failed Job By Job Id

Use this when a failed job should be replayed with the same manifest after fixing environment/config/runtime conditions.

1. Verify terminal failed state and identify target job id

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  job_id=YOUR_JOB_ID
  cat status/${job_id}.json
  test -f jobs/done/${job_id}.json
'
```

Expected precondition:
- `status/<job_id>.json` shows `"state": "failed"`
- `jobs/done/<job_id>.json` exists
- no same-id manifest under `jobs/queued/` or `jobs/running/`

2. Replay the job back to queue

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  job_id=YOUR_JOB_ID
  bash scripts/replay-job.sh ${job_id}
'
```

Optional override (non-failed state only when intentionally required):

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  job_id=YOUR_JOB_ID
  bash scripts/replay-job.sh ${job_id} --force
'
```

3. Verify replay writeback and reprocessing

```bash
sudo -u docdown-runner -H bash -lc '
  cd /opt/docdown-ops/releases/docdownops-main
  job_id=YOUR_JOB_ID
  ls -la jobs/queued/${job_id}.json
  tail -n 3 status/history/${job_id}.jsonl
'

sudo systemctl status docdownops-runner.service --no-pager
sudo journalctl -u docdownops-runner.service -n 50 --no-pager
```

Expected behavior:
- replay helper appends a new `queued` transition with message `Manual replay requested for job_id <job_id>`
- next runner claim progresses state through `running -> succeeded|failed`
- if sync is enabled, replay helper commits and pushes the queue/status update

## 11) Alert Threshold Configuration And Checks

Use these settings to surface queue pressure and repeated sync failures in `docdownops-runner.service` logs.

Suggested baseline in `/etc/default/docdownops-runner`:

```bash
cat >/tmp/docdownops-alert-thresholds.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

sudo tee -a /etc/default/docdownops-runner >/dev/null <<'EOS'
DOCDOWN_ALERT_QUEUE_DEPTH_THRESHOLD=10
DOCDOWN_ALERT_QUEUED_AGE_SECONDS_THRESHOLD=900
DOCDOWN_ALERT_SYNC_FAILURE_THRESHOLD=3
DOCDOWN_ALERT_CHECK_INTERVAL_SECONDS=60
EOS

sudo systemctl restart docdownops-runner.service
EOF

bash /tmp/docdownops-alert-thresholds.sh
```

Verification commands:

```bash
sudo systemctl status docdownops-runner.service --no-pager
sudo journalctl -u docdownops-runner.service -n 200 --no-pager | grep 'ALERT:' || true
```

Expected behavior:
- queue depth alert: `ALERT: queue depth ... exceeds threshold ...`
- queue age alert: `ALERT: oldest queued job age ... exceeds threshold ...`
- sync failure alert: `ALERT: sync failures reached ... during refresh|writeback`

## 12) Current limitation to keep in mind

With current scaffold, `runner-loop.sh` updates queue/status files in the local working copy.
To make status globally visible through GitHub, ensure your operational process includes syncing these updates back to origin (for example, controlled commit/push flow or a wrapper service).

## 13) Verified state as of 2026-04-15

- node01:
  - `/etc/default/docdownops-runner` exists.
  - `/opt/docdown-ops/releases/docdownops-main/scripts/docdown-execute-manifest.sh` is present and executable.
  - `docdownops-runner.service` was validated as the primary active runner and can be returned to that posture after failover tests.
  - Healthy idle behavior is periodic `No queued jobs available to claim.` log entries while the service remains active.
- node02:
  - `/etc/default/docdownops-runner` exists.
  - `/opt/docdown-ops/releases/docdownops-main/scripts/docdown-execute-manifest.sh` is present and executable.
  - `docdownops-runner.service` remains disabled and inactive as standby default outside failover tests, but was validated successfully as the active runner during the 2026-04-15 failover exercise.

Validated failover result:
- node01 was stopped/disabled, node02 was enabled/started, and workflow-dispatched job `20260415102641-543c64` completed successfully through node02.
- Remote writeback preserved the same behavior under failover:
  - commit `c79da5f` enqueued the job
  - commit `2433b52` marked it running
  - commit `0ec5b17` recorded success
  - `status/20260415102641-543c64.json` includes `result_url = https://github.com/Frank-Yong/DocDownOps/tree/task/10.2-runner-loop/results/20260415102641-543c64`
  - `results/20260415102641-543c64/final.md` exists in the repo

Note:
- If logs show `No queued jobs available to claim.` while the service stays active, that is normal idle polling behavior, not a fault condition.
