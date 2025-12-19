# Audible Browser-Anmeldung - Anleitung

## Problem: 2FA-Unterstützung

Da Audible/Amazon 2FA (Zwei-Faktor-Authentifizierung) verwendet, funktioniert die direkte Email/Passwort-Anmeldung nicht.

## Lösung: Browser-Anmeldung

### Methode 1: Browser-Anmeldung (GUI)

1. Öffnen Sie die GUI
2. Gehen Sie zum "Audible"-Tab
3. Klicken Sie auf "Audible anmelden"
4. Wählen Sie "🌐 Browser-Anmeldung (empfohlen für 2FA)"
5. Ein Browser öffnet sich mit: `https://www.audible.de/sign-in`
6. Melden Sie sich normal an (inkl. 2FA)
7. Gehen Sie nach erfolgreicher Anmeldung zu: `https://www.audible.de/library`
8. Kehren Sie zur GUI zurück
9. Die Cookies werden automatisch extrahiert

### Methode 2: Cookie-Anmeldung (manuell)

1. Öffnen Sie Audible.de in Ihrem Browser (eingeloggt)
2. Öffnen Sie die Entwicklertools (F12)
3. Gehen Sie zu: **Application** → **Cookies** → **www.audible.de**
4. Kopieren Sie die folgenden Cookie-Werte:
   - `session-id`
   - `session-id-time`
   - `ubid-main`
   - `at-main`
   - `sess-at-main`
5. In der GUI: "Cookie-Anmeldung (manuell)" wählen
6. Cookies einfügen und anmelden

## Wichtige URLs

- **Anmeldung**: `https://www.audible.de/sign-in`
- **Bibliothek**: `https://www.audible.de/library`

Die alte URL `/ap/signin` funktioniert nicht mehr!

