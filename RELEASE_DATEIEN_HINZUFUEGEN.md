# Anleitung: Dateien zu bestehendem Release hinzufügen

## Problem
Das Release wurde manuell erstellt, bevor die Builds fertig waren. Die `.exe` und `.deb` Dateien fehlen.

## Lösung: Workflow manuell auslösen

### Schritt 1: Gehe zu GitHub Actions
1. Öffne: https://github.com/msebastian100/Universal-Downloader/actions
2. Klicke auf **"Build Releases"** (links in der Seitenleiste)
3. Klicke auf **"Run workflow"** (rechts oben, neben dem Filter)

### Schritt 2: Tag eingeben
1. Im Dropdown **"Use workflow from"** wähle **"main"**
2. Im Feld **"Tag"** gib ein: `v.2.0.0`
3. Klicke auf **"Run workflow"**

### Schritt 3: Warten
- Der Workflow baut beide Dateien (Windows .exe und Linux .deb)
- Beide Dateien werden automatisch zum Release `v.2.0.0` hinzugefügt
- Dies kann 5-10 Minuten dauern

### Schritt 4: Prüfen
1. Gehe zu: https://github.com/msebastian100/Universal-Downloader/releases
2. Öffne das Release `v.2.0.0`
3. Die Dateien sollten jetzt unter "Assets" angezeigt werden

## Alternative: Tag erneut pushen

Falls der manuelle Workflow-Trigger nicht funktioniert:

```bash
# Tag lokal löschen (falls vorhanden)
git tag -d v.2.0.0

# Tag erneut erstellen und pushen
git tag v.2.0.0
git push origin v.2.0.0 --force
```

Dies löst den Workflow automatisch aus.

## Wichtig für zukünftige Releases

**Empfohlener Workflow:**
1. **NICHT** das Release manuell auf GitHub erstellen
2. Stattdessen: Tag erstellen und pushen
3. Der Workflow erstellt automatisch das Release mit den Dateien

```bash
# Versionsnummer in version.py anpassen
git add version.py
git commit -m "Bump version to 2.0.0"
git push

# Tag erstellen und pushen
git tag v2.0.0
git push origin v2.0.0
```

Der Workflow wird automatisch ausgelöst und erstellt das Release mit beiden Dateien.
