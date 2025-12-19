# Anleitung: Releases erstellen und Dateien hinzufügen

## Option 1: Manuelles Release erstellen (Empfohlen)

### Schritt 1: GitHub Release erstellen

1. Gehe zu deinem Repository auf GitHub: https://github.com/msebastian100/Universal-Downloader
2. Klicke auf **"Releases"** (rechts in der Seitenleiste)
3. Klicke auf **"Create a new release"** oder **"Draft a new release"**
4. Fülle die Felder aus:
   - **Tag version**: z.B. `v2.0.0` (muss mit `v` beginnen)
   - **Release title**: z.B. `Universal Downloader v2.0.0`
   - **Description**: Beschreibung der Änderungen (Changelog)
5. Wähle **"Set as the latest release"** (wenn es die neueste Version ist)
6. Klicke auf **"Publish release"**

### Schritt 2: Workflow wartet auf Release

Sobald du das Release erstellst, wird der GitHub Actions Workflow automatisch ausgelöst:
- Die `.exe` und `.deb` Dateien werden gebaut
- Die Dateien werden automatisch zum Release hinzugefügt

**Wichtig**: Du musst das Release **NACH** dem erfolgreichen Build erstellen, oder der Workflow wird beim Release-Event ausgelöst.

## Option 2: Artifacts manuell herunterladen

Falls du die Dateien vor dem Release testen möchtest:

1. Gehe zu **"Actions"** in deinem Repository
2. Wähle den erfolgreichen Workflow-Run aus
3. Scrolle nach unten zu **"Artifacts"**
4. Lade die Artifacts herunter:
   - `windows-exe` → enthält `UniversalDownloader.exe`
   - `linux-deb` → enthält die `.deb` Datei

## Option 3: Automatisches Draft-Release mit Git Tag (Empfohlen)

Der Workflow erstellt automatisch ein Draft-Release, wenn du einen Git Tag pusht:

```bash
# Versionsnummer in version.py anpassen (z.B. 2.0.0)
git add version.py
git commit -m "Bump version to 2.0.0"
git tag v2.0.0
git push origin main
git push origin v2.0.0
```

**Was passiert:**
1. Der Workflow wird durch den Tag ausgelöst
2. Beide Builds (Windows und Linux) werden ausgeführt
3. Ein Draft-Release wird automatisch erstellt
4. Beide Dateien (.exe und .deb) werden hochgeladen
5. Du kannst das Draft-Release auf GitHub prüfen und dann veröffentlichen

## Aktuelle Workflow-Konfiguration

Der Workflow wird ausgelöst bei:
- ✅ **Release erstellt** (`release: types: [created]`) → Dateien werden automatisch hochgeladen
- ✅ **Git Tag gepusht** (`tags: ['v*']`) → Draft-Release wird automatisch erstellt und Dateien hochgeladen
- ✅ **Manueller Trigger** (`workflow_dispatch`) → Dateien werden als Artifacts hochgeladen
- ✅ **Push zu main** (`push: branches: [main]`) → Dateien werden als Artifacts hochgeladen

## Empfohlener Workflow

### Methode A: Mit Git Tag (Empfohlen)

1. **Code pushen** → Build läuft automatisch, Dateien werden als Artifacts gespeichert
2. **Testen** → Lade die Artifacts herunter und teste sie
3. **Tag erstellen und pushen**:
   ```bash
   git tag v2.0.0
   git push origin v2.0.0
   ```
4. **Automatisches Draft-Release** → Workflow erstellt Draft-Release mit beiden Dateien
5. **Release prüfen und veröffentlichen** → Auf GitHub das Draft-Release prüfen und veröffentlichen

### Methode B: Manuelles Release

1. **Code pushen** → Build läuft automatisch
2. **Release auf GitHub erstellen** → Erstelle ein GitHub Release mit der Versionsnummer
3. **Automatischer Upload** → Der Workflow wird erneut ausgelöst und lädt die Dateien zum Release hoch

## Versionsnummer anpassen

Die Versionsnummer wird in `version.py` gespeichert. Stelle sicher, dass die Version vor dem Release aktualisiert wird:

```python
__version__ = "2.0.0"
```

## Tipps

- **Draft Releases**: Erstelle zuerst ein Draft-Release, teste die Dateien, und veröffentliche es dann
- **Pre-Releases**: Nutze Pre-Releases für Beta-Versionen
- **Changelog**: Füge immer einen Changelog hinzu, damit Benutzer wissen, was sich geändert hat
