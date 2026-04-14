# Node01 Primary CD Runner Setup (DocDown)

Purpose: set up `node01` as the active DocDown CD runner, while keeping `node02` as standby fallback.

Run these commands on `node01` as `clusteradmin`.

## 1) Create service account and directories

```bash
sudo groupadd --force docdown-runner
if ! id -u docdown-runner >/dev/null 2>&1; then
  sudo useradd --create-home --shell /bin/bash --gid docdown-runner docdown-runner
fi

sudo install -d -o docdown-runner -g docdown-runner /opt/docdown
sudo install -d -o docdown-runner -g docdown-runner /opt/docdown/releases
sudo install -d -o docdown-runner -g docdown-runner /opt/docdown/shared
sudo install -d -o docdown-runner -g docdown-runner /opt/docdown/workspace
sudo install -d -o docdown-runner -g docdown-runner /opt/docdown/shared/smoke
```

## 2) Install host dependencies

```bash
sudo apt-get update
sudo apt-get install -y ca-certificates curl git python3 python3-venv qpdf pandoc ghostscript

python3 -c 'import sys; raise SystemExit(0 if sys.version_info >= (3, 10) else 1)' || {
  echo "python3 must be >= 3.10" >&2
  python3 --version >&2
  exit 1
}
```

## 3) Install GitHub Actions runner

```bash
sudo rm -rf /home/docdown-runner/actions-runner
sudo -u docdown-runner -H mkdir -p /home/docdown-runner/actions-runner

cat >/tmp/docdown-install-runner.sh <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

cd /home/docdown-runner/actions-runner
curl -fL -o actions-runner-linux-x64-2.333.1.tar.gz https://github.com/actions/runner/releases/download/v2.333.1/actions-runner-linux-x64-2.333.1.tar.gz
echo "18f8f68ed1892854ff2ab1bab4fcaa2f5abeedc98093b6cb13638991725cab74  actions-runner-linux-x64-2.333.1.tar.gz" | sha256sum -c
tar xzf ./actions-runner-linux-x64-2.333.1.tar.gz
EOF

sudo chown docdown-runner:docdown-runner /tmp/docdown-install-runner.sh
sudo chmod 700 /tmp/docdown-install-runner.sh
sudo -u docdown-runner -H bash /tmp/docdown-install-runner.sh
sudo rm -f /tmp/docdown-install-runner.sh
```

## 4) Register runner as node01

In GitHub: Repo -> Settings -> Actions -> Runners -> New self-hosted runner -> copy one-time token.

```bash
while true; do
  IFS= read -r -s -p "Runner token: " RUNNER_TOKEN </dev/tty
  echo
  if [ -n "${RUNNER_TOKEN}" ]; then
    break
  fi
  echo "Runner token cannot be empty." >&2
done

sudo -u docdown-runner -H bash -lc "
  cd ~/actions-runner
  ./config.sh \
    --url https://github.com/Frank-Yong/DocDown \
    --token \"$RUNNER_TOKEN\" \
    --name docdown-node01 \
    --labels docdown,docdown-primary \
    --unattended
"
unset RUNNER_TOKEN
```

Notes:
- GitHub auto-adds: `self-hosted`, `linux`, `x64`
- We add: `docdown`, `docdown-primary`
- Current CD workflow matches `docdown`, so node01 is eligible immediately.

## 5) Install and start runner service

```bash
sudo bash -lc '
  cd /home/docdown-runner/actions-runner
  ./svc.sh install docdown-runner
  ./svc.sh start
  ./svc.sh status
'
```

## 6) Verify runner and prerequisites

```bash
sudo -u docdown-runner -H bash -lc 'ls -la ~/actions-runner'
sudo -u docdown-runner -H bash -lc 'find ~ -maxdepth 3 -type f -name svc.sh'

command -v qpdf
command -v pandoc
command -v gs
```

In GitHub runner UI, verify runner `docdown-node01` is `Idle` and has labels:
- `self-hosted`
- `linux`
- `x64`
- `docdown`
- `docdown-primary`

## 7) Install release activation wrapper (required)

CD deploy expects `/usr/local/bin/docdown-activate-release` to exist on the runner host.

```bash
sudo tee /usr/local/bin/docdown-activate-release >/dev/null <<'EOF'
#!/usr/bin/env bash
set -euo pipefail

release_dir="${1:-}"
if [ -z "${release_dir}" ]; then
  echo "Usage: docdown-activate-release <release-path>" >&2
  exit 2
fi

if [ ! -d "${release_dir}" ]; then
  echo "Release path does not exist or is not a directory: ${release_dir}" >&2
  exit 1
fi

ln -sfn "${release_dir}" /opt/docdown/current
EOF

sudo chmod 755 /usr/local/bin/docdown-activate-release
sudo chown root:root /usr/local/bin/docdown-activate-release
```

## 8) Configure passwordless sudo for CD deploy (required)

CD runs as `docdown-runner` and uses non-interactive sudo (`sudo -n`) for release activation and service restarts.

```bash
sudo tee /etc/sudoers.d/docdown-runner >/dev/null <<'EOF'
Defaults:docdown-runner !requiretty
docdown-runner ALL=(root) NOPASSWD: /usr/local/bin/docdown-activate-release *
docdown-runner ALL=(root) NOPASSWD: /usr/bin/systemctl restart docdown-worker
docdown-runner ALL=(root) NOPASSWD: /usr/bin/systemctl restart docdown-api
EOF

sudo chmod 440 /etc/sudoers.d/docdown-runner
sudo visudo -cf /etc/sudoers.d/docdown-runner

# Verify non-interactive sudo works for all required commands
latest_release="$(ls -1dt /opt/docdown/releases/* 2>/dev/null | head -n 1 || true)"
if [ -n "${latest_release}" ]; then
  sudo -u docdown-runner -H sudo -n /usr/local/bin/docdown-activate-release "${latest_release}"
else
  echo "No release directory exists yet under /opt/docdown/releases; skipping activate-release functional check."
  sudo -u docdown-runner -H sudo -n /usr/local/bin/docdown-activate-release || true
fi

for svc in docdown-worker docdown-api; do
  if sudo -n /usr/bin/systemctl cat "${svc}" >/dev/null 2>&1; then
    sudo -u docdown-runner -H sudo -n /usr/bin/systemctl restart "${svc}"
  else
    echo "${svc}.service not installed yet on node01; restart check skipped."
  fi
done
```

## 9) Keep node02 as standby fallback (optional but recommended)

If both node01 and node02 are online with `docdown` label, CD can land on either host.

To keep node02 as true standby, stop/disable node02 runner service until needed:

```bash
# Run on node02
sudo bash -lc 'cd /home/docdown-runner/actions-runner && ./svc.sh stop'
sudo systemctl disable actions.runner.Frank-Yong-DocDown.docdown-node02.service
```

When failover is needed, re-enable/start on node02:

```bash
# Run on node02
sudo systemctl enable actions.runner.Frank-Yong-DocDown.docdown-node02.service
sudo bash -lc 'cd /home/docdown-runner/actions-runner && ./svc.sh start'
sudo bash -lc 'cd /home/docdown-runner/actions-runner && ./svc.sh status'
```

## 10) Smoke test CD

```bash
# From local workstation with repo checkout
git checkout main
git pull --ff-only

git commit --allow-empty -m "chore: smoke test node01 CD runner"
git push origin main
```

Then confirm in GitHub Actions that CD runs on `docdown-node01`.
