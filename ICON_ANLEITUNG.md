# Programm-Icon hinzufügen

Die Anwendung unterstützt jetzt ein benutzerdefiniertes Programm-Icon.

## Icon-Datei hinzufügen

1. **Erstellen Sie ein Icon-Bild** (empfohlen: PNG oder ICO Format)
   - Empfohlene Größe: 256x256 Pixel oder 512x512 Pixel
   - Für beste Qualität: PNG mit transparentem Hintergrund

2. **Benennen Sie die Datei**:
   - `icon.png` (empfohlen für macOS/Linux)
   - `icon.ico` (empfohlen für Windows)
   - `app_icon.png` (Alternative)
   - `app_icon.ico` (Alternative)

3. **Platzieren Sie die Datei** im Hauptverzeichnis des Projekts (gleicher Ordner wie `gui.py`)

## Unterstützte Formate

- **PNG**: Funktioniert auf allen Plattformen (empfohlen)
- **ICO**: Funktioniert hauptsächlich auf Windows

## Automatische Erkennung

Die Anwendung sucht automatisch nach folgenden Dateien (in dieser Reihenfolge):
1. `icon.png`
2. `icon.ico`
3. `app_icon.png`
4. `app_icon.ico`

Das erste gefundene Icon wird verwendet.

## Hinweise

- Falls kein Icon gefunden wird, verwendet die Anwendung das Standard-System-Icon
- Das Icon wird automatisch auf die richtige Größe skaliert
- Für macOS wird das Icon automatisch auf 256x256 Pixel skaliert

## Icon-Erstellung

Sie können Icons mit folgenden Tools erstellen:
- Online-Tools: [Favicon.io](https://favicon.io/), [IconGenerator](https://www.icongenerator.net/)
- Grafikprogramme: GIMP, Photoshop, Figma
- Konvertierung: Online-Konverter für PNG zu ICO
