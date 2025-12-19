# Lokale Dateien (nicht im Repository)

Diese Dateien sollten **lokal vorhanden sein**, aber **NICHT ins Repository** hochgeladen werden:

## 🔐 Konfigurationsdateien (sensibel)

Diese Dateien enthalten persönliche Daten und sollten **NIEMALS** ins Repository:

- **`.deezer_config.json`** - Enthält ARL-Token für Deezer-Login
- **`.audible_config.json`** - Enthält Audible-Credentials
- **`settings.json`** - Enthält persönliche Einstellungen und Pfade

**Status:** ✅ In `.gitignore` - werden nicht hochgeladen

## 📋 Log-Dateien

- **`Logs/`** - Alle Log-Dateien
- **`*.log`** - Einzelne Log-Dateien

**Status:** ✅ In `.gitignore` - werden nicht hochgeladen

## 🏗️ Build-Artefakte

Diese werden beim Build erstellt und sollten nicht ins Repo:

- **`build/`** - PyInstaller Build-Verzeichnis
- **`dist/`** - Erstellte .exe Dateien
- **`deb_build/`** - Erstellte .deb Pakete
- **`*.exe`** - Windows Executables
- **`*.deb`** - Linux Pakete

**Status:** ✅ In `.gitignore` - werden nicht hochgeladen

## 🐍 Python Cache

- **`__pycache__/`** - Python Bytecode Cache
- **`*.pyc`** - Kompilierte Python-Dateien
- **`*.pyo`** - Optimierte Python-Dateien

**Status:** ✅ In `.gitignore` - werden nicht hochgeladen

## 📦 Virtuelle Umgebung

- **`venv/`** - Python Virtual Environment
- **`env/`** - Alternative venv Namen
- **`.venv/`** - Alternative venv Namen

**Status:** ✅ In `.gitignore` - werden nicht hochgeladen

## 💾 Downloads (optional)

- **`Downloads/`** - Heruntergeladene Dateien (optional)

**Status:** ⚠️ In `.gitignore` auskommentiert - kann aktiviert werden falls gewünscht

## 📝 Dateien die IM Repository sein sollten

Diese Dateien **SOLLTEN** im Repository sein:

- ✅ **`UniversalDownloader.spec`** - PyInstaller Spec-Datei (wichtig für Builds)
- ✅ **`icon.png`** - App-Icon
- ✅ **`requirements.txt`** - Python-Abhängigkeiten
- ✅ Alle **`.py`** Dateien - Quellcode
- ✅ Alle **`.md`** Dateien - Dokumentation
- ✅ **`LICENSE`** - Lizenz-Datei

## ✅ Checkliste

- [x] `.deezer_config.json` in .gitignore
- [x] `.audible_config.json` in .gitignore
- [x] `settings.json` in .gitignore
- [x] `Logs/` in .gitignore
- [x] `build/`, `dist/`, `deb_build/` in .gitignore
- [x] `venv/` in .gitignore
- [x] `__pycache__/` in .gitignore
- [x] `UniversalDownloader.spec` NICHT in .gitignore (sollte im Repo sein)

## 🆘 Falls Dateien versehentlich committed wurden

Falls sensible Dateien versehentlich ins Repository gelangt sind:

1. **Token/Credentials sofort widerrufen** (siehe SICHERHEIT_WARNUNG.md)
2. **Dateien aus Git-Historie entfernen:**
   ```bash
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch .deezer_config.json .audible_config.json settings.json" \
     --prune-empty --tag-name-filter cat -- --all
   ```
3. **Force Push:**
   ```bash
   git push origin --force --all
   ```

**WICHTIG:** Nur wenn Repository noch nicht öffentlich ist oder Token bereits widerrufen wurden!
