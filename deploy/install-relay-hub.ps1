# ============================================================================
# Companion relay hub — Windows setup (OPTIONAL; see deploy/README.md)
#
#   powershell -ExecutionPolicy Bypass -File deploy\install-relay-hub.ps1
#
#   -Port 8931                  hub listen port
#   -BinPath <path>             companion.exe (auto-detected next to the repo)
#   -EnvFile <path>             token file (default ~\.companion-relay\relay.env)
#   -RunNow                     start the hub in a visible window now
#   -InstallStartupTask         register a scheduled task that starts the hub
#                               at logon (Windows has no systemd; this is the
#                               equivalent of the Linux unit template)
#   -Uninstall                  remove the scheduled task + user env vars
#
# The Linux scripts (install-relay-hub.sh / setup-tunnel.sh) rely on systemd,
# journalctl and openssl and do NOT run on Windows. This script is their
# Windows counterpart for the hub itself; the TLS endpoint in front of it
# (Cloudflare Tunnel, Caddy, nginx) is a separate install on the same machine.
#
# Tokens are generated with the .NET RNG (Windows has no openssl) and stored
# in a file OUTSIDE this repository. NEVER commit them.
# ============================================================================
#Requires -Version 5.1
param(
    [int]$Port = 8931,
    [string]$BinPath,
    [string]$EnvFile,
    [switch]$RunNow,
    [switch]$InstallStartupTask,
    [switch]$Uninstall
)
$ErrorActionPreference = 'Stop'
$TaskName = 'CompanionRelayHub'

function Say($m)  { Write-Host "==> $m" }
function Ok($m)   { Write-Host " ok  $m" -ForegroundColor Green }
function Warn($m) { Write-Host " !!  $m" -ForegroundColor Yellow }

function New-HexToken {
    $b = New-Object byte[] 32
    [System.Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($b)
    return (($b | ForEach-Object { $_.ToString('x2') }) -join '')
}

# ── Uninstall ────────────────────────────────────────────────────────────────
if ($Uninstall) {
    if (Get-ScheduledTask -TaskName $TaskName -ErrorAction SilentlyContinue) {
        Unregister-ScheduledTask -TaskName $TaskName -Confirm:$false
        Ok "removed scheduled task $TaskName"
    } else { Ok "no scheduled task found" }
    foreach ($v in 'COMPANION_RELAY_DEVICES_TOKEN', 'COMPANION_RELAY_AGENTS_TOKEN') {
        if ([Environment]::GetEnvironmentVariable($v, 'User')) {
            [Environment]::SetEnvironmentVariable($v, $null, 'User')
            Ok "cleared user env var $v"
        }
    }
    if ($EnvFile -and (Test-Path $EnvFile)) {
        Ok "note: token file still exists at $EnvFile - delete it manually"
    }
    return
}

# ── Binary detection (same candidates the IDE auto-detects) ──────────────────
if (-not $BinPath) {
    $candidates = @(
        (Join-Path $PSScriptRoot '..\companion-cli\companion.exe'),
        (Join-Path (Split-Path -Parent $PSScriptRoot) 'companion-cli\companion.exe'),
        'companion.exe'
    )
    foreach ($c in $candidates) { if (Test-Path $c) { $BinPath = $c; break } }
}
if (-not $BinPath -or -not (Test-Path $BinPath)) {
    throw "companion.exe not found. Pass -BinPath, or build it: cd companion-cli; go build -o companion.exe ."
}
Ok "hub binary: $BinPath"

# ── Tokens ───────────────────────────────────────────────────────────────────
if (-not $EnvFile) { $EnvFile = Join-Path $env:USERPROFILE '.companion-relay\relay.env' }
$Dir = Split-Path -Parent $EnvFile
if (-not (Test-Path $EnvFile)) {
    Say "no token file at $EnvFile - generating one"
    New-Item -ItemType Directory -Force -Path $Dir | Out-Null
    $Dev = New-HexToken
    $Agt = New-HexToken
    @"
COMPANION_RELAY_DEVICES_TOKEN=$Dev
COMPANION_RELAY_AGENTS_TOKEN=$Agt
"@ | Out-File -FilePath $EnvFile -Encoding ascii -NoNewline
    Ok "tokens written -> $EnvFile"
    Write-Host ""
    Write-Host "  Put this in the board's config.local.h:" -ForegroundColor Cyan
    Write-Host "    #define DEVICE_TOKEN  `"$Dev`""
    Write-Host "  Agent token (keep secret, never commit):" -ForegroundColor Cyan
    Write-Host "    $Agt"
    Write-Host ""
} else {
    Ok "using existing token file $EnvFile"
    if ((Get-Content $EnvFile -Raw) -match 'replace-with-openssl') {
        Warn "the file still contains template placeholders - replace them"
    }
}

# Load tokens into this session (foreground run) and, for the startup task,
# into the user's environment so the task inherits them at logon.
$Tokens = @{}
foreach ($line in (Get-Content $EnvFile)) {
    $f = $line -split '=', 2
    if ($f.Count -eq 2) { $Tokens[$f[0].Trim()] = $f[1].Trim() }
}
foreach ($k in 'COMPANION_RELAY_DEVICES_TOKEN', 'COMPANION_RELAY_AGENTS_TOKEN') {
    if (-not $Tokens[$k]) { throw "$EnvFile is missing $k" }
    Set-Item -Path "env:$k" -Value $Tokens[$k]
}
if ($InstallStartupTask) {
    foreach ($k in $Tokens.Keys) {
        [Environment]::SetEnvironmentVariable($k, $Tokens[$k], 'User')
    }
    Ok "tokens exported at user scope (the logon task inherits them)"
}

# ── Scheduled task (the Windows equivalent of the systemd unit) ──────────────
if ($InstallStartupTask) {
    $action    = New-ScheduledTaskAction -Execute $BinPath -Argument "relay hub --listen :$Port"
    $trigger   = New-ScheduledTaskTrigger -AtLogOn
    $principal = New-ScheduledTaskPrincipal -UserId $env:USERNAME -LogonType Interactive -RunLevel Limited
    Register-ScheduledTask -TaskName $TaskName -Action $action -Trigger $trigger -Principal $principal -Force | Out-Null
    Ok "scheduled task $TaskName registered (starts at logon, hidden)"
    Start-ScheduledTask -TaskName $TaskName
    Start-Sleep -Seconds 4
} elseif ($RunNow) {
    Say "starting the hub in a visible window (close it to stop)"
    Start-Process -FilePath $BinPath -ArgumentList 'relay', 'hub', "--listen`:$Port"
    Start-Sleep -Seconds 4
}

# ── Verify ───────────────────────────────────────────────────────────────────
try {
    $h = Invoke-RestMethod -Uri "http://127.0.0.1:$Port/health?token=$($Tokens['COMPANION_RELAY_AGENTS_TOKEN'])" -TimeoutSec 8
    if ($h.ok) {
        Ok "hub answering on 127.0.0.1:$Port"
        if ($h.devices) {
            $h.devices | ForEach-Object {
                Write-Host "        $($_.id)  v$($_.version)  $(if ($_.busy) {'busy'} else {'idle'})"
            }
        }
    } else { Warn "hub answered but rejected the token" }
} catch {
    Warn "hub did not answer on 127.0.0.1:$Port - check the window/task output"
}

Write-Host ""
Write-Host "Next steps:"
Write-Host "  1. Expose :$Port over TLS (Cloudflare Tunnel / Caddy) and note the wss:// host"
Write-Host "  2. Set RELAY_HOST / RELAY_TLS=true / DEVICE_TOKEN in the board's config.local.h"
Write-Host "  3. companion ota upload <device-id> --ota-mode remote --relay-hub wss://<host>"
Write-Host ""
Write-Host "Uninstall: powershell -ExecutionPolicy Bypass -File deploy\install-relay-hub.ps1 -Uninstall"