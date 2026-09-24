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
$PSNativeCommandUseErrorActionPreference = $false
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

$makeappx = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\makeappx.exe" -ErrorAction SilentlyContinue |
    Sort-Object FullName -Descending | Select-Object -First 1
if (-not $makeappx) {
    $makeappx = Get-ChildItem "C:\Program Files (x86)\Windows Kits\10\bin\*\arm64\makeappx.exe" -ErrorAction SilentlyContinue |
        Sort-Object FullName -Descending | Select-Object -First 1
}
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
    # makeappx lehnt +, *.rels und [Content_Types].xml unterhalb der Wurzel ab.
    # Die Word-Vorlagen enthalten genau solche Namen und werden zum Lesen von docx nicht gebraucht.
    $docxTemplates = Join-Path $layout "_internal\docx\templates"
    if (Test-Path $docxTemplates) { Remove-Item $docxTemplates -Recurse -Force }
    Get-ChildItem -LiteralPath $layout -Recurse -Force -File | Where-Object {
        $_.Name -match '\+' -or $_.Name -like '*.rels' -or ($_.Name -eq '[Content_Types].xml' -and $_.DirectoryName -ne $layout)
    } | Remove-Item -Force
    $xml = $manifestTemplate.
        Replace("__IDENTITY_NAME__", $IdentityName).
        Replace("__PUBLISHER__", $Publisher).
        Replace("__PUBLISHER_DISPLAY__", $PublisherDisplayName).
        Replace("__VERSION__", $VersionQuad).
        Replace("__ARCH__", $Arch)
    $manifestPath = Join-Path $layout "AppxManifest.xml"
    [System.IO.File]::WriteAllText($manifestPath, $xml.TrimStart([char]0xFEFF))
    $out = Join-Path $outDir "UniversalDownloader-$VersionQuad-$Arch.msix"
    $log = Join-Path $env:TEMP "makeappx-$Arch.log"
    $err = "$log.err"
    Write-Host "makeappx: $($makeappx.FullName)"
    function Invoke-Pack([string] $Dir) {
        if (Test-Path $log) { Remove-Item $log -Force }
        if (Test-Path $err) { Remove-Item $err -Force }
        $proc = Start-Process -FilePath $makeappx.FullName -ArgumentList @("pack", "/h", "SHA256", "/d", $Dir, "/p", $out, "/o") -Wait -PassThru -NoNewWindow -RedirectStandardOutput $log -RedirectStandardError $err
        return $proc.ExitCode
    }
    $code = Invoke-Pack $layout
    if ($code -ne 0) {
        Write-Host "Packen fehlgeschlagen, suche die störende Datei."
        $layoutFull = [System.IO.Path]::GetFullPath($layout).TrimEnd('\')
        $rels = @(Get-ChildItem -LiteralPath $layout -Recurse -Force -File | ForEach-Object {
            $full = $_.FullName
            if ($full.StartsWith('\\?\')) { $full = $full.Substring(4) }
            $full = [System.IO.Path]::GetFullPath($full)
            if ($full -eq $manifestPath) { return }
            $relPath = $full.Substring($layoutFull.Length).TrimStart('\')
            if ($relPath -like 'Assets\*' -or $relPath -eq 'UniversalDownloader.exe') { return }
            $relPath
        } | Where-Object { $_ })
        $removed = @()
        for ($round = 0; $round -lt 12 -and $code -ne 0; $round++) {
            $list = @($rels)
            while ($list.Count -gt 1) {
                $mid = [Math]::Floor($list.Count / 2)
                $probeDir = Join-Path $env:TEMP "ud-probe-$Arch"
                if (Test-Path $probeDir) { Remove-Item $probeDir -Recurse -Force }
                New-Item -ItemType Directory -Force -Path $probeDir | Out-Null
                Copy-Item $manifestPath (Join-Path $probeDir "AppxManifest.xml")
                Copy-Item (Join-Path $layout "Assets") (Join-Path $probeDir "Assets") -Recurse -Force
                $exe = Join-Path $layout "UniversalDownloader.exe"
                if (Test-Path $exe) { Copy-Item $exe (Join-Path $probeDir "UniversalDownloader.exe") }
                foreach ($rel in $list[0..($mid - 1)]) {
                    $dest = Join-Path $probeDir $rel
                    New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
                    Copy-Item -LiteralPath (Join-Path $layout $rel) -Destination $dest
                }
                $probeCode = Invoke-Pack $probeDir
                Remove-Item $probeDir -Recurse -Force
                $right = @($list[$mid..($list.Count - 1)])
                if ($probeCode -ne 0) {
                    $list = @($list[0..($mid - 1)])
                } else {
                    $rightDir = Join-Path $env:TEMP "ud-probe-r-$Arch"
                    if (Test-Path $rightDir) { Remove-Item $rightDir -Recurse -Force }
                    New-Item -ItemType Directory -Force -Path $rightDir | Out-Null
                    Copy-Item $manifestPath (Join-Path $rightDir "AppxManifest.xml")
                    Copy-Item (Join-Path $layout "Assets") (Join-Path $rightDir "Assets") -Recurse -Force
                    if (Test-Path $exe) { Copy-Item $exe (Join-Path $rightDir "UniversalDownloader.exe") }
                    foreach ($rel in $right) {
                        $dest = Join-Path $rightDir $rel
                        New-Item -ItemType Directory -Force -Path (Split-Path $dest) | Out-Null
                        Copy-Item -LiteralPath (Join-Path $layout $rel) -Destination $dest
                    }
                    $rightCode = Invoke-Pack $rightDir
                    Remove-Item $rightDir -Recurse -Force
                    if ($rightCode -ne 0) { $list = $right } else { Write-Error "Beide Hälften lassen sich packen, das Gesamtverzeichnis nicht."; return }
                }
            }
            $bad = $list[0]
            Write-Host "Störende Datei: $bad"
            Remove-Item -LiteralPath (Join-Path $layout $bad) -Force
            $removed += $bad
            $rels = @($rels | Where-Object { $_ -ne $bad })
            $code = Invoke-Pack $layout
        }
        if ($removed.Count -gt 0) { Write-Host ("Entfernt: " + ($removed -join ", ")) }
        if ($code -ne 0) {
            if (Test-Path $err) { Get-Content $err | Write-Host }
            Write-Error "makeappx pack für $Arch fehlgeschlagen (Exit $code)."
        }
    }
    Remove-Item $layout -Recurse -Force
    Write-Host "Paket: $out"
    return $out
}

New-Package $Architecture | Out-Null
Write-Host "Paket für $Architecture erzeugt."

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
