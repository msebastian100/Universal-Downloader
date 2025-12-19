# Quick Start Guide

## Schnellstart

### 1. Abhängigkeiten installieren

```bash
# Automatisch (empfohlen)
chmod +x install.sh
./install.sh

# Oder manuell
python3 -m venv venv
source venv/bin/activate
pip install -r requirements.txt
```

### 2. Abhängigkeiten prüfen

```bash
python3 check_dependencies.py
```

### 3. Anwendung starten

```bash
# Mit virtuelle Umgebung
source venv/bin/activate
python3 start.py

# Oder direkt (wenn venv aktiviert ist)
python3 start.py
```

## Wichtige Hinweise

- **Auf macOS/Linux**: Verwenden Sie immer `python3` statt `python`
- **Virtuelle Umgebung**: Aktivieren Sie die venv vor dem Start: `source venv/bin/activate`
- **ffmpeg**: Wird für MP3-Konvertierung benötigt. Installieren mit: `brew install ffmpeg` (macOS)

## Fehlerbehebung

### "command not found: python"
→ Verwenden Sie `python3` statt `python`

### "ModuleNotFoundError"
→ Aktivieren Sie die virtuelle Umgebung: `source venv/bin/activate`
→ Installieren Sie Abhängigkeiten: `pip install -r requirements.txt`

### "ffmpeg not found"
→ Installieren Sie ffmpeg:
  - macOS: `brew install ffmpeg`
  - Linux: `sudo apt-get install ffmpeg`
