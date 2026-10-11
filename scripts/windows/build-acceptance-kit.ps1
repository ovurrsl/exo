# Portable gates use the installed EXO runtime as their Python interpreter.
param([Parameter(Mandatory = $true)] [string]$OutputDirectory)
$ErrorActionPreference = 'Stop'
$output = [IO.Path]::GetFullPath($OutputDirectory)
if (Test-Path -LiteralPath $output) { throw 'Acceptance kit output must be new' }
$ancestor = [IO.Path]::GetDirectoryName($output)
while ($ancestor) {
    if ((Test-Path -LiteralPath $ancestor) -and
        ((Get-Item -LiteralPath $ancestor -Force).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        throw 'Acceptance kit output cannot use linked paths'
    }
    $ancestor = [IO.Path]::GetDirectoryName($ancestor)
}
New-Item -ItemType Directory -Path $output | Out-Null
$files = @('check-installed-runtime.ps1', 'check_inference.py', 'validate_runtime.py', 'consumer-acceptance.md')
$hashes = [ordered]@{}
foreach ($name in $files) {
    $source = Join-Path $PSScriptRoot $name
    $destination = Join-Path $output $name
    Copy-Item -LiteralPath $source -Destination $destination
    $hashes[$name] = (Get-FileHash -LiteralPath $destination -Algorithm SHA256).Hash.ToLowerInvariant()
}
$manifest = @{schema=1; created_utc=[DateTime]::UtcNow.ToString('o'); file_sha256=$hashes; includes_models=$false; release_ready=$false}
[IO.File]::WriteAllText((Join-Path $output 'kit-manifest.json'), ($manifest | ConvertTo-Json -Depth 5), [Text.UTF8Encoding]::new($false))
$archive = Join-Path $output 'exo-windows-acceptance-kit.zip'
Compress-Archive -LiteralPath (@($files | ForEach-Object { Join-Path $output $_ }) + @(Join-Path $output 'kit-manifest.json')) -DestinationPath $archive
Write-Host "Acceptance kit: $archive"
Write-Host "SHA-256: $((Get-FileHash -LiteralPath $archive -Algorithm SHA256).Hash.ToLowerInvariant())"
