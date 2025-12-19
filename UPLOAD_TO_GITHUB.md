# Upload zu GitHub - Schnellanleitung

## ✅ Git Repository ist vorbereitet!

Ich habe das lokale Git-Repository eingerichtet. Jetzt müssen Sie nur noch:

## Schritt 1: GitHub Repository erstellen

1. Gehen Sie zu: https://github.com/new
2. Repository-Name: `Universal-Downloader`
3. Beschreibung: "Universal Downloader für Musik, Hörbücher und Videos"
4. Sichtbarkeit: **Public** (für Open Source)
5. **WICHTIG**: Wählen Sie **"MIT License"** aus
6. Klicken Sie auf **"Create repository"**

## Schritt 2: Code hochladen

Führen Sie diese Befehle aus (im Terminal im Projektverzeichnis):

```bash
cd /Users/basti/Documents/Projekte/Downloader

# Branch umbenennen
git branch -M main

# Code hochladen
git push -u origin main
```

Falls Sie nach Benutzername/Passwort gefragt werden:
- **Benutzername**: `msebastian100`
- **Passwort**: Verwenden Sie ein **Personal Access Token** (nicht Ihr GitHub-Passwort)
  - Erstellen Sie eines hier: https://github.com/settings/tokens
  - **Benötigte Scopes**: 
    - ✅ `repo` (vollständiger Zugriff auf Repositories)
    - ✅ `workflow` (optional, für GitHub Actions)
  - **Detaillierte Anleitung**: Siehe [GITHUB_TOKEN_ANLEITUNG.md](GITHUB_TOKEN_ANLEITUNG.md)

## Schritt 3: Erste Release erstellen (mit automatischen Builds!)

Nach dem Upload:

1. Gehen Sie zu: https://github.com/msebastian100/Universal-Downloader/releases/new
2. **Tag**: `v2.0.0`
3. **Titel**: `Version 2.0.0 - Initial Release`
4. **Beschreibung**:
   ```
   ## 🎉 Erstes Release!
   
   ### Features:
   - 🎵 Deezer & Spotify Download
   - 📚 Audible Integration
   - 🎬 Video Downloader (ARD, ZDF, YouTube, etc.)
   - 🔄 Auto-Updater
   - 📊 Statistiken & Historie
   - ⚙️ Umfangreiche Einstellungen
   
   ### Downloads:
   - Windows: Wird automatisch von GitHub Actions erstellt
   - Linux: Wird automatisch von GitHub Actions erstellt
   ```
5. **WICHTIG**: Aktivieren Sie **"Set as the latest release"**
6. Klicken Sie auf **"Publish release"**

## 🚀 Automatische Builds

Sobald Sie die Release erstellen, starten automatisch die GitHub Actions:
- ✅ Windows .exe wird auf einem Windows-Server erstellt
- ✅ Linux .deb wird auf einem Linux-Server erstellt
- ✅ Beide Dateien werden automatisch zum Release hinzugefügt

**Das dauert ca. 5-10 Minuten!**

## Schritt 4: Builds prüfen

1. Gehen Sie zu: https://github.com/msebastian100/Universal-Downloader/actions
2. Sie sehen die laufenden Builds
3. Nach Abschluss finden Sie die .exe und .deb Dateien im Release

## ✅ Fertig!

Nach dem ersten Release funktioniert der Auto-Updater automatisch:
- Benutzer können auf "🔄 Updates" klicken
- Die App prüft automatisch auf neue Releases
- Downloads werden direkt von GitHub bereitgestellt

## 🔄 Für zukünftige Releases

1. Version in `version.py` erhöhen (z.B. `2.0.1`)
2. Änderungen committen:
   ```bash
   git add .
   git commit -m "Version 2.0.1 - Bugfixes"
   git push
   ```
3. Neues Release erstellen:
   - Tag: `v2.0.1`
   - GitHub Actions erstellt automatisch die Builds!

## 🆘 Hilfe

Falls etwas nicht funktioniert:
- Prüfen Sie die GitHub Actions: https://github.com/msebastian100/Universal-Downloader/actions
- Prüfen Sie die Logs der fehlgeschlagenen Actions
- Erstellen Sie ein Issue im Repository
