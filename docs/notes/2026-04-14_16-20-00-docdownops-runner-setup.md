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

DOCDOWNOPS_BRANCH="${DOCDOWNOPS_BRANCH:-task/10.2-conversion-workflow}"
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
EOS

sudo chmod 640 /etc/default/docdownops-runner
sudo chown root:docdown-runner /etc/default/docdownops-runner
EOF

bash /tmp/docdownops-env-setup.sh
```

Notes:
- `DOCDOWN_JOB_EXECUTOR` must exist and be executable by `docdown-runner`.
- Current repo-managed V1 path: `/opt/docdown-ops/releases/docdownops-main/scripts/docdown-execute-manifest.sh`.
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

## 9) Current limitation to keep in mind

With current scaffold, `runner-loop.sh` updates queue/status files in the local working copy.
To make status globally visible through GitHub, ensure your operational process includes syncing these updates back to origin (for example, controlled commit/push flow or a wrapper service).

## 10) Verified state as of 2026-04-15

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
