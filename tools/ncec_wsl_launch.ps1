<#
  NCEC ROM Map Editor launcher for WSL2(WSLg) / socketcan  (CLI-free start).
  Called by NCEC_Editor_WSL.bat. Requires the one-time setup (setup_ncec_wsl.ps1).

  Steps (all idempotent):
    1. derive the project path from this script's own location (no hardcoded user/path)
    2. find the SH-C30L (VID:PID 1d50:606f) busid, then: usbipd attach --wsl
    3. bring up can0 at 500k (wsl -u root -- /usr/local/sbin/ncec-can0-up)
    4. launch the editor: wsl -- NCEC_CAN=socketcan:can0 python3 ncec_editor.py

  -Check : print busid / attach state / can0 state only (no side effects, no launch).

  NOTE: messages are ASCII on purpose (Windows PowerShell 5.1 reads a non-BOM UTF-8
  .ps1 as the system codepage, which would corrupt non-ASCII text). Japanese lives in
  the GUI and docs/setup_wsl_ja.md.
#>
[CmdletBinding()]
param([switch]$Check)

$ErrorActionPreference = 'Continue'
$env:WSL_UTF8 = '1'

function Info($m){ Write-Host "[launch] $m" -ForegroundColor Cyan }
function Warn($m){ Write-Host "[launch] $m" -ForegroundColor Yellow }
function Err ($m){ Write-Host "[launch] $m" -ForegroundColor Red }

# Windows path -> WSL path (/mnt/<drive>/...). Avoids wslpath arg-quoting pitfalls.
function ConvertTo-WslPath([string]$p) {
    $full = (Resolve-Path -LiteralPath $p).Path
    $drive = $full.Substring(0,1).ToLower()
    $rest = $full.Substring(2) -replace '\\','/'
    return "/mnt/$drive$rest"
}

# Run wsl.exe with a Windows-side timeout. A wedged usbip/can0 makes the in-WSL
# command block in uninterruptible (D) state, which a WSL-side 'timeout' cannot
# kill; only killing the wsl.exe process here lets the launcher move on. Returns
# a hashtable @{ TimedOut; Output; Code }.
function Invoke-WslTimed([string[]]$wslArgs, [int]$timeoutSec) {
    $out = New-TemporaryFile
    $err = New-TemporaryFile
    try {
        $p = Start-Process -FilePath 'wsl.exe' -ArgumentList $wslArgs -NoNewWindow -PassThru `
             -RedirectStandardOutput $out.FullName -RedirectStandardError $err.FullName
        if (-not $p.WaitForExit($timeoutSec * 1000)) {
            try { $p.Kill() } catch {}
            return @{ TimedOut = $true; Output = ''; Code = $null }
        }
        $text = @()
        $text += (Get-Content -Raw -ErrorAction SilentlyContinue $out.FullName)
        $text += (Get-Content -Raw -ErrorAction SilentlyContinue $err.FullName)
        return @{ TimedOut = $false; Output = ($text -join "`n"); Code = $p.ExitCode }
    } finally {
        Remove-Item -ErrorAction SilentlyContinue $out.FullName, $err.FullName
    }
}

if (-not (Get-Command wsl.exe -ErrorAction SilentlyContinue)) {
    Err "WSL not found. Run one-time setup first: tools\setup_ncec_wsl.ps1 (as Administrator)."
    return
}
if (-not (Get-Command usbipd -ErrorAction SilentlyContinue)) {
    Err "usbipd not found. Run one-time setup first: tools\setup_ncec_wsl.ps1 (as Administrator)."
    return
}

# 1) project path (this script lives in tools\; project is its parent)
$projDir = Split-Path -Parent $PSScriptRoot
$projWsl = ConvertTo-WslPath $projDir
Info "project = $projDir"
Info "  (WSL) = $projWsl"

# 2) find busid by VID:PID
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
$offline = $false
if (-not $busid) {
    if ($Check) {
        Err "SH-C30L (1d50:606f) not found. Plug in the adapter and retry."
        & usbipd list | Out-Host
        return
    }
    # No adapter: do NOT abort. Launch the editor anyway for offline map editing.
    Warn "SH-C30L (1d50:606f) not found - launching the editor in OFFLINE (map-edit only) mode."
    Warn "Plug in the adapter, then use the GUI 'Settings -> CAN connection -> Reconnect' for Live/ECU functions."
    $offline = $true
} else {
    Info "SH-C30L busid = $busid"
}

if ($Check) {
    Info "=== usbipd list ==="
    & usbipd list | Out-Host
    Info "=== can0 (WSL) ==="
    $r = Invoke-WslTimed @('--','ip','link','show','can0') 8
    if ($r.TimedOut) {
        Warn "can0 query timed out - adapter/usbip link wedged (replug + 'wsl --shutdown')."
    } else {
        $r.Output.Trim() | Out-Host
    }
    Info "(-Check: not launching)"
    return
}

if (-not $offline) {
    # 2a) a WSL2 distro must be RUNNING before 'usbipd attach --wsl', otherwise it fails
    #     with "There is no WSL 2 distribution running". Booting is idempotent and fast
    #     (if already up, 'true' just returns); the distro then stays alive for the attach.
    Info "Starting WSL (if not already running)..."
    & wsl.exe -- true 2>&1 | Out-Null

    # 2b) attach to WSL
    $attachOut = (& usbipd attach --wsl --busid $busid) 2>&1 | Out-String
    if ($LASTEXITCODE -ne 0) {
        if ($attachOut -match 'already attached') {
            Info "Already attached to WSL."
        } elseif ($attachOut -match 'not shared|bind') {
            # Adapter present but not bound: launch offline rather than abort (map editing still works).
            Warn "Adapter not bound yet - launching OFFLINE. Run one-time setup tools\setup_ncec_wsl.ps1 (as Administrator) for Live/ECU."
            $offline = $true
        } else {
            Warn ("attach warning: " + $attachOut.Trim())
        }
    } else {
        Info "Attached to WSL (busid $busid)."
    }
}

if (-not $offline) {
    # 3) bring up can0 (retry: small lag right after attach). Each attempt is
    #    time-boxed from Windows: a wedged usbip/can0 makes 'ip' block in D-state,
    #    which no WSL-side timeout can clear. If it never responds, the adapter or
    #    usbip link is stuck and only a replug + 'wsl --shutdown' recovers it.
    $up = $false
    $timedOut = $false
    $canOut = ''
    for ($i = 0; $i -lt 3; $i++) {
        $r = Invoke-WslTimed @('-u','root','--','/usr/local/sbin/ncec-can0-up') 12
        if ($r.TimedOut) { $timedOut = $true; break }
        $canOut = $r.Output
        if ($canOut -match 'state UP' -or $canOut -match '<[^>]*\bUP\b') { $up = $true; break }
        Start-Sleep -Milliseconds 700
    }
    if ($up) {
        Info "can0 is up at 500 kbps."
    } elseif ($timedOut) {
        # Do NOT abort: launch the editor so map editing still works. CAN stays unusable until recovered.
        Err "can0 did not respond in time - the adapter / usbip link is wedged (kernel D-state)."
        Err "Recovery: 1) replug the SH-C30L  2) run: wsl --shutdown  3) start NCEC_Editor_WSL.bat again"
        Warn "Launching the editor OFFLINE (map-edit only) for now."
    } else {
        Warn "Could not confirm can0 up. You can also recover from the GUI: Settings -> CAN connection -> Reconnect."
        Warn ("detail: " + $canOut.Trim())
    }
}

# 4) launch editor (WSLg). NCEC_CAN=socketcan:can0 is passed even when offline so the
#    GUI's 'Settings -> CAN connection -> Reconnect' targets can0 once an adapter appears;
#    Live/ECU simply show a graceful error until then.
if ($offline) {
    Info "Launching editor in WSL (OFFLINE / map-edit; Live will error until an adapter is connected)..."
} else {
    Info "Launching editor in WSL (socketcan)..."
}
$cmd = "cd '$projWsl' && NCEC_CAN=socketcan:can0 python3 ncec_editor.py"
& wsl.exe -- bash -lc $cmd
