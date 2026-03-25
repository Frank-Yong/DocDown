# Docker + WSL + GROBID Setup (Windows)

Use this when Docker Desktop installs successfully but Linux containers fail with a `dockerDesktopLinuxEngine` 500 error.

## Symptoms

- `docker --version` works, but:
- `docker version` fails with server/API errors on `dockerDesktopLinuxEngine`.
- `wsl --status` fails or only prints help text.

## Fix Steps

Run these in an **Administrator PowerShell** window.

### 1) Install/enable WSL backend

```powershell
wsl --install --no-distribution
```

### 2) Reboot Windows

A reboot is required after enabling WSL features.

### 3) Verify WSL

```powershell
wsl --status
wsl -l -v
```

### 4) Start Docker Desktop

Open Docker Desktop and wait until it reports the engine is running.

### 5) Verify Docker server connectivity

```powershell
docker version
docker info
```

If these commands return both Client and Server sections successfully, Docker is ready.

## Troubleshooting

### Error: `WSL2 is not supported ... HCS_E_HYPERV_NOT_INSTALLED`

This means virtualization support is still missing at the host level.

Run in an **Administrator PowerShell** window:

```powershell
dism /online /enable-feature /featurename:VirtualMachinePlatform /all /norestart
dism /online /enable-feature /featurename:Microsoft-Windows-Subsystem-Linux /all /norestart
dism /online /enable-feature /featurename:HypervisorPlatform /all /norestart
bcdedit /set hypervisorlaunchtype auto
```

Then reboot and verify:

```powershell
wsl --status
wsl -l -v
docker version
```

If errors persist, enable CPU virtualization in BIOS/UEFI:

- Intel: `VT-x` (and usually `VT-d`)
- AMD: `SVM` / `AMD-V`

### Error: `0x800f080c` for `Microsoft-Hyper-V-All`

On many Windows Home systems this feature name is unavailable. This is expected.

- Do **not** rely on `Microsoft-Hyper-V-All`.
- Use `VirtualMachinePlatform`, `Microsoft-Windows-Subsystem-Linux`, and `HypervisorPlatform` instead (commands above).

To see feature names available on your machine:

```powershell
dism /online /Get-Features /Format:Table | findstr /i "Hyper-V Hypervisor VirtualMachinePlatform Subsystem-Linux"
```

## Start GROBID

```powershell
docker run -d --name grobid -p 8070:8070 lfoppiano/grobid:0.8.1
```

## Verify GROBID health

```powershell
Invoke-WebRequest http://localhost:8070/api/isalive -UseBasicParsing
```

Expected response body is `true`.

## Optional: run DocDown with GROBID primary

```powershell
docdown "<input.pdf>" --workdir "./runs/external-smoke-grobid" --extractor grobid --fallback-extractor pdfminer --log-level INFO
```
