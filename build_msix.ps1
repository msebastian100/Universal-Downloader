#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Erstellt ein MSIX-Paket aus dem Universal-Downloader-Installer per MSIX Packaging Tool CLI.
  Einmal mit der UI ein Template erzeugen, danach dieses Skript für neue Versionen nutzen.

.DESCRIPTION
  Voraussetzung:
  - MSIX Packaging Tool installiert (Microsoft Store oder winget).
  - Einmal mit der UI ein Konvertierungs-Template erstellt und als
    msix_conversion_template.xml im Projektordner gespeichert.
  - Installer bereits gebaut: dist_installer\UniversalDownloader_Setup_v<Version>.exe

  Das Skript liest die Version aus version.py, aktualisiert das Template
  (Installer-Pfad, Version, Ausgabepfad) und ruft das MSIX Packaging Tool auf.

.PARAMETER TemplatePath
  Pfad zur Template-XML. Standard: msix_conversion_template.xml im Skriptordner.

.PARAMETER Version
  Version (z.B. 2.1.9). Wenn nicht angegeben, wird version.py ausgewertet.
#>

param(
    [string] $TemplatePath = "",
    [string] $Version = ""
)

$ErrorActionPreference = "Stop"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

# Version aus version.py lesen, falls nicht übergeben
if (-not $Version) {
    try {
        $Version = (python -c "from version import __version__; print(__version__)" 2>$null)
    } catch {}
    if (-not $Version) {
        Write-Error "Version konnte nicht aus version.py gelesen werden. Bitte -Version 2.1.9 angeben."
    }
}

# Version in 4 Teile (quad) für MSIX: 2.1.9 -> 2.1.9.0
$VersionQuad = $Version
if (($VersionQuad -split "\.").Count -eq 3) {
    $VersionQuad = "$Version.0"
}

$InstallerPath = (Resolve-Path -LiteralPath (Join-Path $ScriptDir "dist_installer\UniversalDownloader_Setup_v$Version.exe") -ErrorAction SilentlyContinue).Path
if (-not $InstallerPath -or -not (Test-Path $InstallerPath)) {
    Write-Error "Installer nicht gefunden: dist_installer\UniversalDownloader_Setup_v$Version.exe - bitte zuerst build_windows.py und build_installer.py ausführen."
}

if (-not $TemplatePath) {
    $TemplatePath = Join-Path $ScriptDir "msix_conversion_template.xml"
}
if (-not (Test-Path $TemplatePath)) {
    Write-Error "Template nicht gefunden: $TemplatePath`nEinmal MSIX Packaging Tool (UI) durchlaufen und Template speichern (siehe docs/PUBLISH_MICROSOFT_STORE.md)."
}

$OutDir = Join-Path $ScriptDir "dist_msix"
$OutPath = Join-Path $OutDir "UniversalDownloader-$VersionQuad.msix"
New-Item -ItemType Directory -Force -Path $OutDir | Out-Null

# Template einlesen und Platzhalter ersetzen (falls vorhanden) bzw. typische XML-Attribute anpassen
$content = Get-Content -Path $TemplatePath -Raw -Encoding UTF8

# Nur den Installer-Pfad ersetzen (Path direkt nach <Installer)
$content = $content -replace '(?<=<Installer\s+)Path="[^"]*"', "Path=`"$($InstallerPath -replace '\\','\\')`""
# Stille Installer-Argumente (Inno Setup)
$content = $content -replace '(?<=<Installer\s+Path="[^"]*")\s*(?=\s|>)', ' Arguments="/VERYSILENT /SUPPRESSMSGBOXES /NORESTART" '

# Version im PackageInformation (4 Teile für MSIX)
$content = $content -replace '(?<=<PackageInformation[^>]*\s+)Version="[0-9.]*"', "Version=`"$VersionQuad`""

# Ausgabepfad (SaveLocation PackagePath)
$content = $content -replace '(?<=<SaveLocation[^>]*\s+)PackagePath="[^"]*"', "PackagePath=`"$($OutPath -replace '\\','\\')`""

$TempTemplate = Join-Path $env:TEMP "msix_template_$Version.xml"
$content | Set-Content -Path $TempTemplate -Encoding UTF8 -NoNewline

Write-Host "Version: $Version (MSIX: $VersionQuad)"
Write-Host "Installer: $InstallerPath"
Write-Host "Template: $TemplatePath -> $TempTemplate"
Write-Host "Ausgabe: $OutPath"
Write-Host ""

# MSIX Packaging Tool CLI (App-Alias unter Windows)
$cli = "MsixPackagingTool.exe"
$cmd = Get-Command $cli -ErrorAction SilentlyContinue
if (-not $cmd) {
    $cli = "${env:ProgramFiles(x86)}\Windows Kits\10\bin\*\x64\MsixPackagingTool.exe"
    $cmd = Get-Item $cli -ErrorAction SilentlyContinue | Select-Object -First 1
}
if (-not $cmd) {
    Write-Error "MsixPackagingTool.exe nicht gefunden. Bitte MSIX Packaging Tool aus dem Microsoft Store installieren."
}

& $cmd create-package --template $TempTemplate -v
$exitCode = $LASTEXITCODE
Remove-Item $TempTemplate -Force -ErrorAction SilentlyContinue

if ($exitCode -ne 0) {
    Write-Error "MSIX Packaging Tool ist mit Exit-Code $exitCode beendet."
}

Write-Host ""
Write-Host "MSIX erstellt: $OutPath"
