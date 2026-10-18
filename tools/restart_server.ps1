# Restart the official game server with a given map (and optional settings).
# Usage: powershell -File tools/restart_server.ps1 -Map tools\probe_maps\probe1.xml [-MaxPlays 200] [-AutoRestart False]
# NOTE: this rewrites VampiresVSWerewolvesGameServer.exe.config (keep a backup / `git checkout` it after).
param(
    [Parameter(Mandatory = $true)][string]$Map,
    [string]$MaxPlays = "200",
    [string]$MaxGameDuration = "00:05:00",
    [string]$MaxPlayDuration = "00:00:05",
    [string]$AutoRestart = "False"
)
$root = Split-Path -Parent (Split-Path -Parent $MyInvocation.MyCommand.Path)
$cfg = Join-Path $root "VampiresVSWerewolvesGameServer.exe.config"
$mapPath = (Resolve-Path (Join-Path $root $Map)).Path

Get-Process VampiresVSWerewolvesGameServer -ErrorAction SilentlyContinue | Stop-Process -Force
Start-Sleep -Milliseconds 500

$c = [IO.File]::ReadAllText($cfg, [Text.Encoding]::UTF8)
$c = $c -replace '<add key="Map" value="[^"]*"/>', ('<add key="Map" value="' + $mapPath + '"/>')
$c = $c -replace '<add key="MaxPlays" value="[^"]*"/>', ('<add key="MaxPlays" value="' + $MaxPlays + '"/>')
$c = $c -replace '<add key="MaxGameDuration" value="[^"]*"/>', ('<add key="MaxGameDuration" value="' + $MaxGameDuration + '"/>')
$c = $c -replace '<add key="MaxPlayDuration" value="[^"]*"/>', ('<add key="MaxPlayDuration" value="' + $MaxPlayDuration + '"/>')
$c = $c -replace '<add key="AutoRestart" value="[^"]*"/>', ('<add key="AutoRestart" value="' + $AutoRestart + '"/>')
[IO.File]::WriteAllText($cfg, $c, (New-Object Text.UTF8Encoding($true)))

$p = Start-Process -FilePath (Join-Path $root "VampiresVSWerewolvesGameServer.exe") -WorkingDirectory $root -PassThru
for ($i = 0; $i -lt 40; $i++) {
    Start-Sleep -Milliseconds 250
    if (Get-NetTCPConnection -LocalPort 5555 -State Listen -ErrorAction SilentlyContinue) { break }
}
Write-Output "server pid=$($p.Id) map=$mapPath maxPlays=$MaxPlays autoRestart=$AutoRestart listening=$([bool](Get-NetTCPConnection -LocalPort 5555 -State Listen -ErrorAction SilentlyContinue))"
