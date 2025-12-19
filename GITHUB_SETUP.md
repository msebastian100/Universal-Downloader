# GitHub Repository Setup - Anleitung

Diese Anleitung erklärt, wie Sie das Universal Downloader Projekt auf GitHub einrichten und die Lizenz integrieren.

## 📋 Schritt 1: GitHub Repository erstellen

1. Gehen Sie zu [GitHub.com](https://github.com) und melden Sie sich an
2. Klicken Sie auf "New repository" (oder "+" → "New repository")
3. Füllen Sie die Felder aus:
   - **Repository name**: `universal-downloader` (oder ein anderer Name)
   - **Description**: "Universal Downloader für Musik, Hörbücher und Videos"
   - **Visibility**: Wählen Sie "Public" für Open Source
   - **Initialize**: 
     - ✅ Add a README file (optional, Sie haben bereits eine)
     - ✅ Add .gitignore (wählen Sie "Python")
     - ✅ Choose a license → **Wählen Sie "MIT License"**
4. Klicken Sie auf "Create repository"

## 📝 Schritt 2: Lokales Repository einrichten

Falls Sie noch kein Git-Repository haben:

```bash
# Im Projektverzeichnis
cd /Users/basti/Documents/Projekte/Downloader

# Git initialisieren (falls noch nicht geschehen)
git init

# .gitignore erstellen (falls nicht vorhanden)
cat > .gitignore << 'EOF'
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
venv/
env/
ENV/

# Build-Artefakte
build/
dist/
*.spec
*.exe
*.deb
deb_build/

# IDE
.vscode/
.idea/
*.swp
*.swo

# Logs
Logs/
*.log

# Konfiguration (sensible Daten)
.deezer_config.json
.audible_config.json
settings.json

# OS
.DS_Store
Thumbs.db
EOF

# Dateien hinzufügen
git add .

# Ersten Commit erstellen
git commit -m "Initial commit: Universal Downloader v2.0.0"

# GitHub Repository als Remote hinzufügen
git remote add origin https://github.com/msebastian100/Universal-Downloader.git

# Branch umbenennen (falls nötig)
git branch -M main

# Hochladen
git push -u origin main
```

## 🔧 Schritt 3: Update-URLs konfigurieren

Öffnen Sie `version.py` und passen Sie die URLs an:

```python
GITHUB_REPO_URL = "https://github.com/msebastian100/Universal-Downloader"
UPDATE_CHECK_URL = "https://api.github.com/repos/msebastian100/Universal-Downloader/releases/latest"
```

## 📦 Schritt 4: Erste Release erstellen

1. Gehen Sie zu Ihrem GitHub Repository
2. Klicken Sie auf "Releases" → "Create a new release"
3. Füllen Sie aus:
   - **Tag version**: `v2.0.0` (muss mit `v` beginnen)
   - **Release title**: `Version 2.0.0 - Initial Release`
   - **Description**: Beschreibung der Features
4. Laden Sie die Build-Dateien hoch:
   - `dist/UniversalDownloader.exe` (Windows)
   - `deb_build/universal-downloader_2.0.0_all.deb` (Linux)
5. Klicken Sie auf "Publish release"

## 🔄 Schritt 5: Auto-Updater testen

1. Starten Sie die Anwendung
2. Klicken Sie auf "🔄 Updates" in der Toolbar
3. Der Updater sollte die neueste Version von GitHub abrufen

## 📄 Schritt 6: README.md aktualisieren

Fügen Sie am Ende der README.md hinzu:

```markdown
## 📜 Lizenz

Dieses Projekt ist unter der MIT License lizenziert. Siehe [LICENSE](LICENSE) für Details.

## 🤝 Beitragen

Beiträge sind willkommen! Bitte erstellen Sie einen Pull Request oder öffnen Sie ein Issue.

## 🔗 Links

- [GitHub Repository](https://github.com/msebastian100/Universal-Downloader)
- [Releases](https://github.com/msebastian100/Universal-Downloader/releases)
```

## ✅ Checkliste

- [ ] GitHub Repository erstellt
- [ ] MIT License ausgewählt (wird automatisch erstellt)
- [ ] Lokales Git-Repository initialisiert
- [ ] Code zu GitHub hochgeladen
- [ ] `version.py` mit korrekten URLs aktualisiert
- [ ] Erste Release erstellt mit Build-Dateien
- [ ] README.md aktualisiert
- [ ] Auto-Updater getestet

## 🎯 Wichtige Hinweise

### Versionierung
- Verwenden Sie [Semantic Versioning](https://semver.org/): `MAJOR.MINOR.PATCH`
- Beispiel: `2.0.0`, `2.1.0`, `2.1.1`
- Aktualisieren Sie `version.py` bei jeder neuen Version

### Releases
- Erstellen Sie für jede neue Version ein GitHub Release
- Tag-Name muss mit `v` beginnen: `v2.0.0`
- Laden Sie die Build-Dateien (.exe, .deb) als Assets hoch
- Der Auto-Updater erkennt automatisch die neueste Version

### .gitignore
- Stellen Sie sicher, dass sensible Daten (API-Keys, Configs) in `.gitignore` sind
- Build-Artefakte sollten nicht ins Repository

### LICENSE-Datei
- Die MIT License ist bereits in `LICENSE` enthalten
- GitHub erstellt automatisch eine LICENSE-Datei, wenn Sie "MIT License" beim Repository-Erstellen auswählen
- Falls nicht, kopieren Sie die `LICENSE`-Datei ins Repository

## 🔐 Sicherheit

**WICHTIG:** Stellen Sie sicher, dass folgende Dateien in `.gitignore` sind:
- `.deezer_config.json` (enthält ARL-Token)
- `.audible_config.json` (enthält Credentials)
- `settings.json` (kann sensible Daten enthalten)

Diese Dateien enthalten möglicherweise persönliche Informationen und sollten **niemals** ins Repository hochgeladen werden!

## 📚 Weitere Ressourcen

- [GitHub Docs: Creating a repository](https://docs.github.com/en/get-started/quickstart/create-a-repo)
- [GitHub Docs: Managing releases](https://docs.github.com/en/repositories/releasing-projects-on-github/managing-releases-in-a-repository)
- [MIT License auf Wikipedia](https://de.wikipedia.org/wiki/MIT-Lizenz)
