# DocDownOps Runner Setup (node01 primary, node02 standby)

Purpose: run DocDownOps job processing on LAN hosts, with node01 active and node02 disabled standby.

Important:
- DocDownOps submit workflow currently runs on GitHub-hosted runner (`ubuntu-latest`).
- The "runner" here means the local `scripts/runner-loop.sh` service, not a GitHub Actions self-hosted runner.
- All command blocks are intended to be executed from an operator shell (for example `clusteradmin`), not by logging in directly as `docdown-runner`.
- Where file ownership or git operations must run as `docdown-runner`, commands already use `sudo -u docdown-runner` explicitly.

## 1) Host prerequisites (run on node01 and node02 as clusteradmin)

```bash
sudo apt-get update
sudo apt-get install -y git python3

sudo groupadd --force docdown-runner
if ! id -u docdown-runner >/dev/null 2>&1; then
  sudo useradd --create-home --shell /bin/bash --gid docdown-runner docdown-runner
fi

sudo install -d -o docdown-runner -g docdown-runner /opt/docdown-ops
sudo install -d -o docdown-runner -g docdown-runner /opt/docdown-ops/releases
```

## 2) Clone DocDownOps working tree

Run from your operator shell on each node. The block below explicitly switches to `docdown-runner`. Replace clone URL if you use SSH.

```bash
sudo -u docdown-runner -H bash -lc '
  set -euo pipefail
  cd /opt/docdown-ops
  if [ ! -d releases/docdownops-main/.git ]; then
    git clone https://github.com/Frank-Yong/DocDownOps.git releases/docdownops-main
  fi
  cd releases/docdownops-main
  git fetch origin
  git checkout main
  git pull --ff-only origin main
'
```

## 3) Configure executor command (node01 and node02)

`runner-loop.sh` requires `DOCDOWN_JOB_EXECUTOR` and will call it as:
- `<executor> <manifest_path>`

Create environment file:

```bash
sudo tee /etc/default/docdownops-runner >/dev/null <<'EOF'
DOCDOWN_JOB_EXECUTOR=/usr/local/bin/docdown-execute-manifest
EOF

sudo chmod 640 /etc/default/docdownops-runner
sudo chown root:docdown-runner /etc/default/docdownops-runner
```

Notes:
- `DOCDOWN_JOB_EXECUTOR` must exist and be executable by `docdown-runner`.
- Executor should return exit code 0 on success, non-zero on failure.
- If executor prints a URL in stdout, runner-loop captures first URL into `result_url`.

## 4) Install systemd service for runner-loop

```bash
sudo tee /etc/systemd/system/docdownops-runner.service >/dev/null <<'EOF'
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
EOF

sudo systemctl daemon-reload
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
sudo systemctl start docdownops-runner.service
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
