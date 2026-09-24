# Erstellt unsignierte MSIX-Pakete für den Microsoft Store (x64 und/oder arm64).
# Der Store signiert das Paket nach dem Hochladen selbst. Ein eigenes CA-Zertifikat ist dafür nicht nötig.
# Publisher und IdentityName kommen aus dem Partner Center (Produktidentität) und müssen exakt übernommen werden.

param(
    [ValidateSet("x64", "arm64")]
    [string] $Architecture = "",
    [string] $Version = "",
    [string] $IdentityName = "Plertanix.Universal-Downloader",
    [string] $Publisher = "CN=62BCE772-F1CD-411C-A42F-EE7E7B569487",
    [string] $PublisherDisplayName = "Plertanix",
    [string] $SourceDir = ""
)

$ErrorActionPreference = "Stop"
$Root = Split-Path -Parent (Split-Path -Parent $PSScriptRoot)
Set-Location $Root

if (-not $Architecture) {
    $Architecture = if ($env:PROCESSOR_ARCHITECTURE -eq "ARM64") { "arm64" } else { "x64" }
}

if (-not $Version) {
    $Version = python -c "from version import __version__; print(__version__)"
}
$parts = $Version.Split(".")
while ($parts.Count -lt 4) { $parts += "0" }
$VersionQuad = ($parts[0..3] -join ".")

if (-not $SourceDir) {
    $SourceDir = Join-Path $Root "dist\UniversalDownloader"
}
if (-not (Test-Path (Join-Path $SourceDir "UniversalDownloader.exe"))) {
    Write-Error "UniversalDownloader.exe fehlt in $SourceDir. Zuerst build_windows.py ausführen."
}

$makeappx = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin" -Recurse -Filter makeappx.exe -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) {
    Write-Error "makeappx.exe nicht gefunden. Windows SDK installieren."
}

$manifestTemplate = Get-Content (Join-Path $PSScriptRoot "AppxManifest.xml") -Raw -Encoding UTF8
$assetDir = Join-Path $PSScriptRoot "Assets"
$outDir = Join-Path $Root "dist_msix"
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

function New-Package([string] $Arch) {
    $layout = Join-Path $env:TEMP "ud-msix-$Arch"
    if (Test-Path $layout) { Remove-Item $layout -Recurse -Force }
    New-Item -ItemType Directory -Force -Path $layout | Out-Null
    Copy-Item -Path (Join-Path $SourceDir "*") -Destination $layout -Recurse -Force
    Copy-Item -Path $assetDir -Destination (Join-Path $layout "Assets") -Recurse -Force
    $xml = $manifestTemplate.
        Replace("__IDENTITY_NAME__", $IdentityName).
        Replace("__PUBLISHER__", $Publisher).
        Replace("__PUBLISHER_DISPLAY__", $PublisherDisplayName).
        Replace("__VERSION__", $VersionQuad).
        Replace("__ARCH__", $Arch)
    Set-Content -Path (Join-Path $layout "AppxManifest.xml") -Value $xml -Encoding UTF8
    $out = Join-Path $outDir "UniversalDownloader-$VersionQuad-$Arch.msix"
    & $makeappx.FullName pack /d $layout /p $out /o
    if ($LASTEXITCODE -ne 0) { Write-Error "makeappx pack für $Arch fehlgeschlagen." }
    Remove-Item $layout -Recurse -Force
    Write-Host "Paket: $out"
    return $out
}

New-Package $Architecture | Out-Null

$x64 = Join-Path $outDir "UniversalDownloader-$VersionQuad-x64.msix"
$arm = Join-Path $outDir "UniversalDownloader-$VersionQuad-arm64.msix"
if ((Test-Path $x64) -and (Test-Path $arm)) {
    $bundle = Join-Path $outDir "UniversalDownloader-$VersionQuad.msixbundle"
    $map = Join-Path $env:TEMP "ud-bundle-map.txt"
    "[Files]" | Set-Content $map -Encoding ASCII
    '"' + $x64 + '"' | Add-Content $map -Encoding ASCII
    '"' + $arm + '"' | Add-Content $map -Encoding ASCII
    & $makeappx.FullName bundle /f $map /p $bundle /o
    if ($LASTEXITCODE -ne 0) { Write-Error "makeappx bundle fehlgeschlagen." }
    Write-Host "Bundle: $bundle"
}

Write-Host "Unsigniert. Für den Store so hochladen. Publisher muss die Produktidentität aus dem Partner Center sein."
