#Requires -RunAsAdministrator
<#
.SYNOPSIS
  Signiert eine MSIX-Datei mit einem selbstsignierten Zertifikat und installiert das Zertifikat
  in den Vertrauensanker, damit die MSIX auf diesem PC ohne Zertifikatsfehler (0x800B010A) installiert werden kann.

.DESCRIPTION
  Nur für lokales Testen. Für den Store die unsignierte MSIX hochladen (Microsoft signiert dort).
  Der Zertifikat-Subject (Publisher) muss exakt mit dem Publisher im MSIX-Paket übereinstimmen
  (wie im MSIX Packaging Tool unter "Package information" eingetragen).

.PARAMETER MsixPath
  Pfad zur .msix-Datei (z.B. dist_msix\UniversalDownloader-2.1.9.0.msix).

.PARAMETER Publisher
  Publisher-String, muss exakt dem Eintrag im MSIX entsprechen (z.B. "CN=plertanix" oder "CN=MeinName, O=MeinName, C=DE").
  So steht er im MSIX Packaging Tool unter "Package information" -> Publisher.
#>

param(
    [Parameter(Mandatory = $true)]
    [string] $MsixPath,
    [Parameter(Mandatory = $true)]
    [string] $Publisher
)

$ErrorActionPreference = "Stop"
$ScriptDir = if ($PSScriptRoot) { $PSScriptRoot } else { Split-Path -Parent $MyInvocation.MyCommand.Path }
$MsixPath = $ExecutionContext.SessionState.Path.GetUnresolvedProviderPathFromPSPath($MsixPath)
if (-not (Test-Path -LiteralPath $MsixPath)) {
    Write-Error "MSIX-Datei nicht gefunden: $MsixPath"
}

$CertFriendlyName = "Universal Downloader – Lokaler Test"
$PfxPassword = "LocalTestSigning"
$CertStoreMy = "Cert:\CurrentUser\My"
$CertStoreRoot = "Cert:\CurrentUser\Root"

Write-Host "MSIX: $MsixPath" -ForegroundColor Cyan
Write-Host "Publisher (Zertifikat-Subject): $Publisher" -ForegroundColor Cyan

# Altes Test-Zertifikat ggf. entfernen (gleicher FriendlyName)
Get-ChildItem -Path $CertStoreMy -ErrorAction SilentlyContinue | Where-Object { $_.FriendlyName -eq $CertFriendlyName } | Remove-Item -Force -ErrorAction SilentlyContinue
Get-ChildItem -Path $CertStoreRoot -ErrorAction SilentlyContinue | Where-Object { $_.Subject -eq $Publisher } | Remove-Item -Force -ErrorAction SilentlyContinue

# Selbstsigniertes Zertifikat für Code-Signing (Subject = Publisher)
Write-Host "`nErstelle selbstsigniertes Zertifikat..." -ForegroundColor Yellow
$cert = New-SelfSignedCertificate `
    -Type Custom `
    -KeyUsage DigitalSignature `
    -KeySpec KeyExchange `
    -Subject $Publisher `
    -FriendlyName $CertFriendlyName `
    -CertStoreLocation $CertStoreMy `
    -TextExtension @("2.5.29.37={text}1.3.6.1.5.5.7.3.3", "2.5.29.19={text}") `
    -NotAfter (Get-Date).AddYears(3)

$thumbprint = $cert.Thumbprint
Write-Host "Zertifikat erstellt: $thumbprint" -ForegroundColor Green

# Zertifikat in Vertrauensanker (Trusted Root) importieren, damit Windows der Signatur vertraut
Write-Host "`nImportiere Zertifikat in Vertrauensanker (Trusted Root)..." -ForegroundColor Yellow
$certFile = Join-Path $env:TEMP "UniversalDownloader_TestRoot.cer"
Export-Certificate -Cert $cert -FilePath $certFile -Type CERT -Force | Out-Null
Import-Certificate -FilePath $certFile -CertStoreLocation $CertStoreRoot -ErrorAction Stop | Out-Null
Remove-Item -LiteralPath $certFile -Force -ErrorAction SilentlyContinue
Write-Host "Vertrauensanker aktualisiert." -ForegroundColor Green

# PFX für SignTool exportieren
$PfxPath = Join-Path $env:TEMP "UniversalDownloader_TestSign.pfx"
$secPass = ConvertTo-SecureString -String $PfxPassword -Force -AsPlainText
Export-PfxCertificate -Cert $cert -FilePath $PfxPath -Password $secPass -Force | Out-Null

# SignTool finden (Windows SDK)
$signtool = $null
$paths = @(
    "C:\Program Files (x86)\Windows Kits\10\bin\*\x64\signtool.exe",
    "C:\Program Files (x86)\Windows Kits\10\bin\*\x86\signtool.exe"
)
foreach ($pattern in $paths) {
    $found = Get-Item -Path $pattern -ErrorAction SilentlyContinue | Sort-Object { $_.FullName } -Descending | Select-Object -First 1
    if ($found) {
        $signtool = $found.FullName
        break
    }
}
if (-not $signtool) {
    Remove-Item -LiteralPath $PfxPath -Force -ErrorAction SilentlyContinue
    Write-Error "SignTool nicht gefunden. Bitte Windows SDK installieren (z.B. über Visual Studio Build Tools oder 'Windows SDK' im Installer)."
}

Write-Host "`nSigniere MSIX mit SignTool..." -ForegroundColor Yellow
& $signtool sign /fd SHA256 /a /f $PfxPath /p $PfxPassword /tr http://timestamp.digicert.com /td SHA256 $MsixPath
if ($LASTEXITCODE -ne 0) {
    Remove-Item -LiteralPath $PfxPath -Force -ErrorAction SilentlyContinue
    Write-Error "Signierung fehlgeschlagen (ExitCode $LASTEXITCODE). Prüfe ob Publisher '$Publisher' exakt dem Eintrag im MSIX entspricht."
}
Remove-Item -LiteralPath $PfxPath -Force -ErrorAction SilentlyContinue

Write-Host "`nFertig. Die MSIX ist signiert und das Zertifikat ist vertrauenswürdig." -ForegroundColor Green
Write-Host "Du kannst die Datei jetzt per Doppelklick oder 'Add-AppxPackage' installieren:" -ForegroundColor Cyan
Write-Host "  Add-AppxPackage -Path `"$MsixPath`"" -ForegroundColor White
