# Activation Bytes - Schritt für Schritt Anleitung

## Methode 1: audible-activator (Terminal)

### Schritt 1: Terminal öffnen
Öffne ein Terminal und navigiere zum audible-activator Ordner:

```bash
cd /Users/basti/Documents/Projekte/Downloader/audible-activator
```

### Schritt 2: audible-activator starten
Führe diesen Befehl aus:

```bash
/Users/basti/Documents/Projekte/Downloader/venv/bin/python3 audible-activator.py -l de
```

### Schritt 3: Login-Daten eingeben
- **Username:** `basti-unterwegs@mallach.de`
- **Password:** (dein Audible-Password)

### Schritt 4: Browser öffnet sich
- Ein Chrome-Browser-Fenster öffnet sich automatisch
- **WICHTIG:** Melde dich **manuell** im Browser an (inkl. 2FA falls aktiviert)
- Warte, bis du bei Audible eingeloggt bist

### Schritt 5: Warten auf playerToken
- Das Skript wartet automatisch bis zu 60 Sekunden
- Es sucht nach dem `playerToken` in der URL
- Du siehst Fortschrittsmeldungen alle 5 Sekunden

### Schritt 6: Falls playerToken nicht automatisch gefunden wird
Wenn das Skript sagt "playerToken nicht automatisch gefunden":

1. **Im Browser:**
   - Gehe zu: `https://www.audible.de/library`
   - Warte, bis die Library-Seite vollständig geladen ist
   - Kopiere diese URL in die Adressleiste:
     ```
     https://www.audible.de/player-auth-token?playerType=software&bp_ua=y&playerModel=Desktop&playerId=2jmj7l5rSw0yVb/vlWAYkK/YBwk=&playerManufacturer=Audible&serial=
     ```
   - Drücke Enter
   - Warte, bis die URL sich ändert und `playerToken=eyJ...` enthält
   - Der playerToken beginnt normalerweise mit `eyJ`

2. **Im Terminal:**
   - Drücke Enter, wenn der playerToken in der URL ist

### Schritt 7: Activation Bytes erhalten
- Das Skript extrahiert die Activation Bytes
- Sie werden im Terminal angezeigt, z.B.: `activation_bytes: a1b2c3d4`
- **Kopiere diese Bytes!**

### Schritt 8: Activation Bytes in GUI eingeben
1. Öffne die GUI
2. Gehe zum Tab "Activation Bytes"
3. Füge die Activation Bytes ein (z.B. `a1b2c3d4`)
4. Klicke auf "Speichern"

## Methode 2: Manuelle Eingabe (wenn du die Bytes bereits hast)

1. Öffne die GUI
2. Gehe zum Tab "Activation Bytes"
3. Gib die Activation Bytes ein (Format: Hex-String, z.B. `12345678`)
4. Klicke auf "Speichern"

## Tipps

- **Falls der Browser sich nicht öffnet:** Stelle sicher, dass Chrome installiert ist
- **Falls das Login-Formular nicht gefunden wird:** Das Skript wechselt automatisch in den Debug-Modus
- **Falls der playerToken nicht gefunden wird:** Folge den Anweisungen in Schritt 6
- **Die Activation Bytes sind einmalig:** Einmal extrahiert, kannst du sie immer wieder verwenden

## Hilfe

Falls etwas nicht funktioniert:
1. Prüfe, ob du bei Audible eingeloggt bist
2. Stelle sicher, dass der Browser nicht blockiert wird
3. Versuche es erneut - manchmal braucht der OpenID-Flow mehrere Versuche
