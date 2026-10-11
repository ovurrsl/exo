param(
    [Parameter(Mandatory = $true)] [string]$RuntimeDirectory,
    [Parameter(Mandatory = $true)] [string]$ModelDirectory,
    [Parameter(Mandatory = $true)] [string]$OutputDirectory,
    [string]$LargeModelShard,
    [switch]$AllowDeveloperMachine,
    [switch]$PreflightOnly
)
$ErrorActionPreference = 'Stop'
$runtime = (Resolve-Path -LiteralPath $RuntimeDirectory).Path
$models = (Resolve-Path -LiteralPath $ModelDirectory).Path
$output = [IO.Path]::GetFullPath($OutputDirectory)
function Test-Overlap([string]$first, [string]$second) {
    $first = $first.TrimEnd('\')
    $second = $second.TrimEnd('\')
    return $first.Equals($second, [StringComparison]::OrdinalIgnoreCase) -or
        $first.StartsWith($second + '\', [StringComparison]::OrdinalIgnoreCase) -or
        $second.StartsWith($first + '\', [StringComparison]::OrdinalIgnoreCase)
}
if ((Test-Overlap $output $runtime) -or (Test-Overlap $output $models)) {
    throw 'Output overlaps runtime or models'
}
if (Test-Path -LiteralPath $output) { throw 'Output directory must be new' }
foreach ($path in @($runtime, $models, $output)) {
    $ancestor = $path
    while ($ancestor) {
        if ((Test-Path -LiteralPath $ancestor) -and
            ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
            throw 'Linked acceptance paths are forbidden'
        }
        $ancestor = [IO.Path]::GetDirectoryName($ancestor)
    }
}
$executable = Join-Path $runtime 'exo.exe'
$manifestPath = Join-Path $runtime 'runtime-manifest.json'
foreach ($path in @($executable, $manifestPath)) {
    if ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) {
        throw 'Linked runtime files are forbidden'
    }
}
$manifest = Get-Content -LiteralPath $manifestPath -Raw -Encoding utf8 | ConvertFrom-Json
$engineHash = (Get-FileHash -LiteralPath $executable -Algorithm SHA256).Hash.ToLowerInvariant()
if ($manifest.schema -ne 2 -or $engineHash -ne $manifest.file_sha256.'exo.exe' -or
    $engineHash -ne $manifest.binary_sha256.'exo.exe') {
    throw 'Runtime executable hash mismatch'
}
$kitManifestPath = Join-Path $PSScriptRoot 'kit-manifest.json'
$kitIntegrityVerified = $false
if (Test-Path -LiteralPath $kitManifestPath) {
    $kitManifest = Get-Content -LiteralPath $kitManifestPath -Raw -Encoding utf8 | ConvertFrom-Json
    if ($kitManifest.schema -ne 1 -or
        ((Get-Item -LiteralPath $kitManifestPath -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Invalid acceptance kit manifest'
    }
    foreach ($name in @('check-installed-runtime.ps1','check_inference.py','validate_runtime.py','consumer-acceptance.md')) {
        $path = Join-Path $PSScriptRoot $name
        $expected = $kitManifest.file_sha256.$name
        if ($expected -notmatch '^[0-9a-f]{64}$' -or
            ((Get-Item -LiteralPath $path -Force).Attributes -band [IO.FileAttributes]::ReparsePoint) -or
            (Get-FileHash -LiteralPath $path -Algorithm SHA256).Hash.ToLowerInvariant() -ne $expected) {
            throw "Acceptance kit hash mismatch: $name"
        }
    }
    $kitIntegrityVerified = $true
} elseif (-not $PreflightOnly) {
    throw 'Acceptance kit manifest is required; run build-acceptance-kit.ps1 and use the extracted kit'
}
if (-not $PreflightOnly) {
    if (-not $LargeModelShard) { throw 'A real >2 GiB safetensors LargeModelShard is required' }
    $shard = Get-Item -LiteralPath $LargeModelShard
    if ($shard.Length -le 2GB -or $shard.Extension -ne '.safetensors' -or
        ($shard.Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'LargeModelShard must be a real >2 GiB safetensors file'
    }
}
$commands = @('python', 'python3', 'py', 'uv', 'cargo', 'rustc', 'node', 'npm', 'cl', 'nvcc')
function Test-AppInstallerAlias([string]$CommandPath, [string]$ReparseData) {
    if (-not $CommandPath -or
        [IO.Path]::GetFileName($CommandPath) -notin @('python.exe','python3.exe') -or
        -not [IO.Path]::GetDirectoryName([IO.Path]::GetFullPath($CommandPath)).Equals(
            (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'), [StringComparison]::OrdinalIgnoreCase)) {
        return $false
    }
    # fsutil's hexadecimal byte dump is stable even when field labels are localized.
    $bytes = [Collections.Generic.List[byte]]::new()
    foreach ($row in [regex]::Matches($ReparseData, '(?m)^\s*[0-9a-fA-F]{4,8}:\s*((?:[0-9a-fA-F]{2}[ \t]+)+)')) {
        foreach ($pair in [regex]::Matches($row.Groups[1].Value, '[0-9a-fA-F]{2}')) {
            $bytes.Add([Convert]::ToByte($pair.Value, 16))
        }
    }
    $identity = $ReparseData + "`n" + [Text.Encoding]::Unicode.GetString($bytes.ToArray())
    return $ReparseData -match '0x8000001b' -and
        $identity -match '(?<![\w.])Microsoft\.DesktopAppInstaller_8wekyb3d8bbwe(?![\w])'
}
function Test-DeveloperSoftwareName([string]$Name) {
    return $Name -match '\bPython\b|\bVisual Studio\b(?!\s+Code\b)|\bCUDA Toolkit\b|\bNode\.js\b|\bRust(?:up)?\b'
}
$ignoredAliases = @()
$foundTools = @(foreach ($name in $commands) {
    foreach ($command in @(Get-Command $name -All -ErrorAction SilentlyContinue)) {
        $shortcut = $false
        if ($name -in @('python','python3') -and $command.Path -and
            [IO.Path]::GetDirectoryName($command.Path).Equals(
                (Join-Path $env:LOCALAPPDATA 'Microsoft\WindowsApps'), [StringComparison]::OrdinalIgnoreCase)) {
            $previousExit = $global:LASTEXITCODE
            try {
                $data = (& (Join-Path $env:SystemRoot 'System32\fsutil.exe') reparsepoint query $command.Path 2>$null) -join "`n"
                if ($LASTEXITCODE -eq 0) { $shortcut = Test-AppInstallerAlias $command.Path $data }
            } catch { $shortcut = $false }
            finally { $global:LASTEXITCODE = $previousExit }
        }
        if ($shortcut) { $ignoredAliases += $command.Path }
        else { $name; break }
    }
})
$software = @('HKLM:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKLM:\Software\WOW6432Node\Microsoft\Windows\CurrentVersion\Uninstall\*',
    'HKCU:\Software\Microsoft\Windows\CurrentVersion\Uninstall\*')
$foundSoftware = @(Get-ItemProperty -Path $software -ErrorAction SilentlyContinue |
    Where-Object { Test-DeveloperSoftwareName $_.DisplayName } |
    Select-Object -ExpandProperty DisplayName -Unique)
$cudaEnvironmentPresent = [bool]($env:CUDA_PATH -or $env:CUDA_HOME)
$report = [ordered]@{
    schema = 1
    checked_utc = [DateTime]::UtcNow.ToString('o')
    runtime = $runtime
    engine_sha256 = $engineHash
    developer_machine_override = [bool]$AllowDeveloperMachine
    detected_tools = $foundTools
    ignored_app_installer_aliases = $ignoredAliases
    detected_software = $foundSoftware
    cuda_environment_present = $cudaEnvironmentPresent
    tool_detection_scope = 'PATH commands, uninstall registrations and CUDA environment; no whole-disk inventory'
    preflight_passed = $false
    kit_integrity_verified = $kitIntegrityVerified
    full_integrity_verified = $false
    inference_verified = $false
    passed = $false
    clean_windows_acceptance_passed = $false
    clean_windows_runtime_acceptance_passed = $false
    native_visual_dpi_keyboard_acceptance_passed = $false
    physical_mac_cluster_passed = $false
    signed_updater_acceptance_passed = $false
    release_ready = $false
}
New-Item -ItemType Directory -Path $output | Out-Null
function Save-Report {
    [IO.File]::WriteAllText((Join-Path $output 'installed-runtime.json'),
        ($report | ConvertTo-Json -Depth 30), [Text.UTF8Encoding]::new($false))
}
try {
    if (-not $AllowDeveloperMachine -and ($foundTools.Count -or $foundSoftware.Count -or $cudaEnvironmentPresent)) {
        throw 'Developer tools detected; use a clean Windows system or explicitly AllowDeveloperMachine for a local smoke test'
    }
    $report.preflight_passed = $true
    if ($PreflightOnly) { Save-Report; return }
    $report.video_controllers = @(Get-CimInstance Win32_VideoController |
        Select-Object Name, DriverVersion, PNPDeviceID)
    function Invoke-Frozen([string]$code, [string]$logName) {
        $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($code))
        & $executable -c "import base64;exec(base64.b64decode('$encoded'))" *> (Join-Path $output $logName)
        if ($LASTEXITCODE -ne 0) { throw "Frozen command failed ($LASTEXITCODE); inspect $logName" }
    }
    function Invoke-Script([string]$scriptName, [string[]]$scriptArguments, [string]$logName) {
        $path = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot $scriptName)).Path
        $argumentsJson = ConvertTo-Json -InputObject (@($path) + $scriptArguments) -Compress
        $encoded = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($argumentsJson))
        Invoke-Frozen "import sys,json,base64,runpy;sys.argv=json.loads(base64.b64decode('$encoded'));runpy.run_path(sys.argv[0],run_name='__main__')" $logName
    }
    $environmentNames = @('PATH', 'CUDA_PATH', 'CUDA_HOME', 'PYTHONUTF8', 'PYTHONHOME', 'PYTHONPATH',
        'MLX_HOSTFILE', 'MLX_RANK', 'EXO_WINDOWS_SHUTDOWN_EVENT', 'EXO_RUNTIME_DIR')
    $savedEnvironment = @{}
    foreach ($name in $environmentNames) { $savedEnvironment[$name] = [Environment]::GetEnvironmentVariable($name, 'Process') }
    try {
        foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $null, 'Process') }
        $env:PATH = Join-Path $env:SystemRoot 'System32'
        $env:PYTHONUTF8 = '1'
        Invoke-Script 'validate_runtime.py' @('--runtime', $runtime) 'integrity-before.log'
        $report.full_integrity_verified = $true
        $gateOutput = Join-Path $output 'runtime-gates.json'
        $gateArguments = @('--device', 'gpu', '--runs', '1', '--ring-sizes', '2',
            '--large-file', $shard.FullName, '--output', $gateOutput)
        $gateJson = ConvertTo-Json -InputObject $gateArguments -Compress
        $encodedGate = [Convert]::ToBase64String([Text.Encoding]::UTF8.GetBytes($gateJson))
        Invoke-Frozen "import json,base64;from check_mlx import main;raise SystemExit(main(json.loads(base64.b64decode('$encodedGate'))))" 'runtime-gates.log'
        $gates = Get-Content -LiteralPath $gateOutput -Raw -Encoding utf8 | ConvertFrom-Json
        if ($gates.passed -ne $true -or $gates.frozen -ne $true -or $gates.device -ne 'gpu') {
            throw 'Frozen GPU gates did not pass'
        }
        if (-not $gates.results -or @($gates.results | Where-Object { $_.pass -ne $true -or $_.exit_code -ne $_.expected }).Count) {
            throw 'Every individual frozen GPU gate must pass'
        }
        # Keep native logs with the evidence, independent of the temporary JIT directory.
        $nativeLogs = Join-Path $output 'native-gate-logs'
        New-Item -ItemType Directory -Path $nativeLogs | Out-Null
        $nativeWork = [IO.Path]::GetFullPath($gates.work_dir).TrimEnd('\')
        $logIndex = 0
        foreach ($gate in $gates.results) {
            if (-not $gate.log) {
                if ($gate.check -eq 'stalled-peer-idle-cpu' -and
                    $null -ne $gate.cpu_percent_of_one_core -and
                    $gate.cpu_percent_of_one_core -ge 0 -and $gate.cpu_percent_of_one_core -lt 25) {
                    continue
                }
                throw 'A native process gate is missing its log'
            }
            $sourceLog = [IO.Path]::GetFullPath($gate.log)
            if (-not $sourceLog.StartsWith($nativeWork + '\', [StringComparison]::OrdinalIgnoreCase) -or
                [IO.Path]::GetExtension($sourceLog) -ne '.log' -or
                ((Get-Item -LiteralPath $sourceLog -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                throw 'Unexpected native gate log path'
            }
            $copiedLog = Join-Path $nativeLogs ("$logIndex-" + [IO.Path]::GetFileName($sourceLog))
            Copy-Item -LiteralPath $sourceLog -Destination $copiedLog
            $originalHash = (Get-FileHash -LiteralPath $sourceLog -Algorithm SHA256).Hash
            if ((Get-FileHash -LiteralPath $copiedLog -Algorithm SHA256).Hash -ne $originalHash) {
                throw 'Native gate log changed while copying'
            }
            $gate | Add-Member -NotePropertyName original_log -NotePropertyValue $sourceLog
            $gate | Add-Member -NotePropertyName log_sha256 -NotePropertyValue $originalHash.ToLowerInvariant()
            $gate.log = $copiedLog
            $logIndex++
        }
        [IO.File]::WriteAllText($gateOutput, ($gates | ConvertTo-Json -Depth 30), [Text.UTF8Encoding]::new($false))
        $inferenceOutput = Join-Path $output 'inference'
        Invoke-Script 'check_inference.py' @('--model-dir', $models, '--runtime', $executable,
            '--output', $inferenceOutput, '--exercise-cancel') 'inference.log'
        $inference = Get-Content -LiteralPath (Join-Path $inferenceOutput 'inference.json') -Raw -Encoding utf8 | ConvertFrom-Json
        if ($inference.passed -ne $true -or $inference.exit_code -ne 0 -or -not $inference.cancel_recovery) {
            throw 'CUDA inference, cancellation and normal worker shutdown are required'
        }
        $report.inference_verified = $true
        Invoke-Script 'validate_runtime.py' @('--runtime', $runtime) 'integrity-after.log'
        $report.passed = $true
        $report.clean_windows_runtime_acceptance_passed = -not $AllowDeveloperMachine
    } finally {
        foreach ($name in $environmentNames) { [Environment]::SetEnvironmentVariable($name, $savedEnvironment[$name], 'Process') }
    }
} catch {
    $report.error = $_.Exception.Message
    Save-Report
    throw
} finally { Save-Report }
Write-Host "Frozen GPU/chat/cancellation acceptance passed. Report: $output"
Write-Host 'Desktop UI, installation/uninstallation, signatures and physical Mac cluster require separate acceptance.'
