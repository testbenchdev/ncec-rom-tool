<#
  NCEC: one-time setup to run NCEC ROM Map Editor on WSL2 + socketcan.
  Reproducible on any PC (no hardcoded username/path).

  Does:
    1. self-elevate to Administrator (needed for usbipd bind)
    2. check WSL2 + distro(v2), run wsl --update (CAN/gs_usb ships in 6.x kernels)
    3. ensure usbipd-win (winget install if missing)
    4. find SH-C30L (VID:PID 1d50:606f) busid, then usbipd bind (share, once)
    5. run the WSL-side setup (python3-tk/can, can0-up wrapper, NOPASSWD sudoers)
  After this, just double-click NCEC_Editor_WSL.bat.

  Usage: right-click tools\setup_ncec_wsl.ps1 -> Run with PowerShell (auto-elevates).

  NOTE: messages are ASCII on purpose (PS 5.1 reads a non-BOM UTF-8 .ps1 as the system
  codepage). Japanese lives in the GUI and docs/setup_wsl_ja.md.
#>
[CmdletBinding()]
param()

$ErrorActionPreference = 'Stop'
$env:WSL_UTF8 = '1'

function Info($m){ Write-Host "[setup] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[setup] $m" -ForegroundColor Yellow }
function Err ($m){ Write-Host "[setup] $m" -ForegroundColor Red }

function ConvertTo-WslPath([string]$p) {
    $full = (Resolve-Path -LiteralPath $p).Path
    $drive = $full.Substring(0,1).ToLower()
    $rest = $full.Substring(2) -replace '\\','/'
    return "/mnt/$drive$rest"
}

# 1) elevate
$principal = New-Object Security.Principal.WindowsPrincipal([Security.Principal.WindowsIdentity]::GetCurrent())
if (-not $principal.IsInRole([Security.Principal.WindowsBuiltInRole]::Administrator)) {
    Info "Administrator rights required; relaunching elevated..."
    Start-Process powershell -Verb RunAs -ArgumentList @(
        '-NoExit','-ExecutionPolicy','Bypass','-File',"`"$PSCommandPath`""
    )
    return
}

$toolsDir = Split-Path -Parent $PSCommandPath
Info "tools dir = $toolsDir"

# 2) WSL2
Info "Checking WSL..."
$wslOk = $false
try { $null = & wsl.exe --status 2>&1; $wslOk = $true } catch { $wslOk = $false }
if (-not $wslOk) {
    Err "WSL not found. In an admin PowerShell run, then reboot:  wsl --install -d Ubuntu-24.04"
    return
}
$distros = (& wsl.exe -l -q) | Where-Object { $_ -and $_.Trim() -ne '' }
if (-not $distros -or $distros.Count -eq 0) {
    Err "No WSL distro. Install Ubuntu:  wsl --install -d Ubuntu-24.04"
    return
}
Info ("distros: " + ($distros -join ', '))
Info "Updating WSL kernel (CAN/gs_usb ships in 6.x)..."
try { & wsl.exe --update | Out-Host } catch { Warn "wsl --update skipped: $_" }

# 3) usbipd
function Test-Usbipd { [bool](Get-Command usbipd -ErrorAction SilentlyContinue) }
if (-not (Test-Usbipd)) {
    Info "Installing usbipd-win via winget..."
    try {
        & winget install --id dorssel.usbipd-win -e --source winget `
            --accept-source-agreements --accept-package-agreements | Out-Host
    } catch { Warn "winget warning: $_" }
    $env:Path = [System.Environment]::GetEnvironmentVariable('Path','Machine') + ';' +
                [System.Environment]::GetEnvironmentVariable('Path','User')
}
if (-not (Test-Usbipd)) {
    Err "usbipd still not found. Reopen PowerShell and re-run this script."
    Err "(or install the msi from https://github.com/dorssel/usbipd-win/releases)"
    return
}

# 4) find busid + bind
function Get-NcecBusid {
    $out = (& usbipd list) 2>&1
    foreach ($line in $out) {
        if ("$line" -match '1d50:606f') {
            $tok = ("$line" -split '\s+') | Where-Object { $_ -ne '' }
            if ($tok.Count -ge 1 -and $tok[0] -match '^\d+-\d+$') { return $tok[0] }
        }
    }
    return $null
}
$busid = Get-NcecBusid
if (-not $busid) {
    Err "SH-C30L (1d50:606f) not found in usbipd list. Plug in the USB and re-run."
    return
}
Info "SH-C30L busid = $busid ; binding (share, once)..."
try { & usbipd bind --busid $busid | Out-Host } catch { Warn "bind warning (harmless if already bound): $_" }

# 5) WSL-side setup (root). /mnt/c scripts may be CRLF -> run a CR-stripped temp copy.
$wslUser = (& wsl.exe -- whoami).Trim()
Info "WSL default user = $wslUser"
$toolsWsl = ConvertTo-WslPath $toolsDir
Info "tools (WSL) = $toolsWsl"
$bashCmd = "export NCEC_SRC_DIR='$toolsWsl'; tr -d '\r' < '$toolsWsl/setup_ncec_wsl.sh' > /tmp/ncec_setup.sh && bash /tmp/ncec_setup.sh '$wslUser'"
Info "Running WSL-side setup (root): deps, can0-up, sudoers..."
& wsl.exe -u root -- bash -lc $bashCmd | Out-Host

Write-Host ""
Info "Done. From now on, just double-click NCEC_Editor_WSL.bat"
Info "(it auto re-attaches the adapter after re-plugging)."
