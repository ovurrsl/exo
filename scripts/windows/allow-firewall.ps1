# Allow inbound traffic so other LAN nodes (e.g. macOS nodes) can join this exo node.
#
# UDP 52413   = peer discovery (IPv6 multicast ff12::e0a1:de89)
# TCP 52414   = zenoh (cluster messaging)
# TCP 52415   = API / dashboard (also used by peers to probe reachability)
# TCP random  = MLX ring backend. The master picks a random port in 49152-65535 (utils/ports.py)
#               per instance, so this is allowed per program: the base Python
#               interpreter that the uv venv launcher (.venv\Scripts\python.exe)
#               hands off to.
#
# Rules apply to Private and Domain networks only; mark your LAN as Private.

#Requires -RunAsAdministrator

$ErrorActionPreference = 'Stop'
$Root = Resolve-Path (Join-Path $PSScriptRoot '..\..')
$TcpRuleName = 'exo local cluster TCP'
$UdpRuleName = 'exo local cluster UDP'
$RingRuleName = 'exo MLX ring (python)'

$VenvPython = Join-Path $Root '.venv\Scripts\python.exe'
if (-not (Test-Path -LiteralPath $VenvPython)) {
    Write-Error "No venv at $VenvPython - run 'uv sync --extra mlx-cpu' first."
}
$BasePython = (& $VenvPython -c 'import sys; print(sys._base_executable)').Trim()

foreach ($name in @($TcpRuleName, $UdpRuleName, $RingRuleName)) {
    if (Get-NetFirewallRule -DisplayName $name -ErrorAction SilentlyContinue) {
        Remove-NetFirewallRule -DisplayName $name
    }
}

New-NetFirewallRule -DisplayName $TcpRuleName -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort 52414,52415 -Profile Private,Domain | Out-Null
New-NetFirewallRule -DisplayName $UdpRuleName -Direction Inbound -Action Allow `
    -Protocol UDP -LocalPort 52413 -Profile Private,Domain | Out-Null
New-NetFirewallRule -DisplayName $RingRuleName -Direction Inbound -Action Allow `
    -Protocol TCP -LocalPort 49152-65535 -Program $BasePython -Profile Private,Domain | Out-Null

Write-Host "Allowed inbound TCP 52414-52415, UDP 52413, and TCP 49152-65535 for $BasePython (Private/Domain)."
