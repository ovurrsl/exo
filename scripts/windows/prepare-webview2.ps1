# Stage the reviewed Microsoft fixed runtime; never modify Windows registration.
param([string]$Archive)
$ErrorActionPreference = 'Stop'
$ExoRoot = (Resolve-Path (Join-Path $PSScriptRoot '..\..')).Path
$pin = Get-Content -LiteralPath (Join-Path $ExoRoot 'packaging\windows\webview2-runtime.json') -Raw | ConvertFrom-Json
$work = Join-Path $ExoRoot 'build\windows-runtime\webview2'
New-Item -ItemType Directory -Path $work -Force | Out-Null
if (-not $Archive) {
    $Archive = Join-Path $work ($pin.folder + '.cab')
    if (-not (Test-Path -LiteralPath $Archive)) {
        if (([uri]$pin.url).Host -ne 'msedge.sf.dl.delivery.mp.microsoft.com') { throw 'Unexpected WebView2 host' }
        Invoke-WebRequest -Uri $pin.url -OutFile $Archive -TimeoutSec 300
    }
}
$Archive = (Resolve-Path -LiteralPath $Archive).Path
if ((Get-FileHash -LiteralPath $Archive -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pin.archive_sha256) {
    throw 'WebView2 archive hash mismatch'
}
# Always extract the pinned archive anew: cached browser DLLs are not trusted.
$expanded = Join-Path $work ([guid]::NewGuid().ToString('N'))
New-Item -ItemType Directory -Path $expanded -Force | Out-Null
& (Join-Path $env:SystemRoot 'System32\expand.exe') $Archive '-F:*' $expanded > (Join-Path $work 'extract.log')
if ($LASTEXITCODE -ne 0) { throw 'WebView2 archive extraction failed' }
$source = Join-Path $expanded $pin.folder
$browser = Join-Path $source 'msedgewebview2.exe'
if ((Get-FileHash -LiteralPath $browser -Algorithm SHA256).Hash.ToLowerInvariant() -ne $pin.executable_sha256) {
    throw 'WebView2 browser hash mismatch'
}
$signature = Get-AuthenticodeSignature -LiteralPath $browser
if ($signature.Status -ne 'Valid' -or $signature.SignerCertificate.Subject -notmatch '^CN=Microsoft Corporation,') {
    throw 'WebView2 Microsoft signature validation failed'
}
$resources = [System.IO.Path]::GetFullPath((Join-Path $ExoRoot 'app\windows\src-tauri\resources'))
$destination = [System.IO.Path]::GetFullPath((Join-Path $resources 'webview2'))
if (-not $destination.StartsWith($resources + '\', [System.StringComparison]::OrdinalIgnoreCase)) {
    throw 'Refusing WebView2 staging outside desktop resources'
}
if (Test-Path -LiteralPath $destination) {
    $links = @(Get-Item -LiteralPath $destination; Get-ChildItem -LiteralPath $destination -Recurse -Force) |
        Where-Object { $_.Attributes -band [System.IO.FileAttributes]::ReparsePoint }
    if ($links) { throw 'Refusing to replace linked WebView2 resources' }
    Remove-Item -LiteralPath $destination -Recurse -Force
}
New-Item -ItemType Directory -Path $destination -Force | Out-Null
Copy-Item -Path (Join-Path $source '*') -Destination $destination -Recurse -Force
$files = @(Get-ChildItem -LiteralPath $source -Recurse -File)
$staged = @(Get-ChildItem -LiteralPath $destination -Recurse -File)
if ($files.Count -ne $staged.Count) { throw 'WebView2 staged file set differs' }
foreach ($file in $files) {
    $relative = [System.IO.Path]::GetRelativePath($source, $file.FullName)
    $copied = Join-Path $destination $relative
    if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne
        (Get-FileHash -LiteralPath $copied -Algorithm SHA256).Hash) { throw "WebView2 staged hash mismatch: $relative" }
}
Write-Host "Validated Microsoft WebView2 $($pin.version): $($files.Count) staged files"
