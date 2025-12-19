# GitHub Personal Access Token - Anleitung

## 🔑 Benötigte Permissions (Scopes)

Für das Hochladen von Code und das Erstellen von Releases benötigen Sie folgende Berechtigungen:

### ✅ Mindestens erforderlich:

1. **`repo`** (Vollständiger Zugriff auf private Repositories)
   - ✅ `repo:status` - Zugriff auf Commit-Status
   - ✅ `repo_deployment` - Zugriff auf Deployment-Status
   - ✅ `public_repo` - Zugriff auf öffentliche Repositories
   - ✅ `repo:invite` - Zugriff auf Repository-Einladungen
   - ✅ `security_events` - Zugriff auf Security-Events

### 📝 Optional (aber empfohlen):

2. **`workflow`** (Zugriff auf GitHub Actions)
   - Benötigt, wenn Sie GitHub Actions Workflows verwenden möchten
   - Erlaubt das Anzeigen und Verwalten von Workflow-Runs

## 🚀 Schritt-für-Schritt Anleitung

### Schritt 1: Token erstellen

1. Gehen Sie zu: https://github.com/settings/tokens
2. Klicken Sie auf **"Generate new token"** → **"Generate new token (classic)"**
3. Füllen Sie aus:
   - **Note**: `Universal-Downloader-Upload` (oder ein anderer Name)
   - **Expiration**: Wählen Sie eine Ablaufzeit (z.B. "90 days" oder "No expiration")
   - **Scopes**: Aktivieren Sie:
     - ✅ **`repo`** (alle Unterpunkte werden automatisch aktiviert)
     - ✅ **`workflow`** (optional, für GitHub Actions)

### Schritt 2: Token kopieren

⚠️ **WICHTIG**: Kopieren Sie den Token sofort! Er wird nur einmal angezeigt.

Der Token sieht so aus: `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx`

### Schritt 3: Token verwenden

Beim `git push` werden Sie nach Credentials gefragt:

```
Username: msebastian100
Password: [Hier den Token einfügen, NICHT Ihr GitHub-Passwort!]
```

## 🔒 Sicherheit

### Best Practices:

1. **Token geheim halten**
   - Teilen Sie den Token niemals öffentlich
   - Fügen Sie ihn nicht in Code ein
   - Speichern Sie ihn sicher (z.B. in einem Passwort-Manager)

2. **Minimale Berechtigungen**
   - Verwenden Sie nur die nötigsten Scopes
   - Für öffentliche Repositories reicht `public_repo`

3. **Ablaufzeit setzen**
   - Setzen Sie eine Ablaufzeit für den Token
   - Erneuern Sie den Token regelmäßig

4. **Token widerrufen**
   - Wenn der Token kompromittiert wurde, widerrufen Sie ihn sofort
   - Gehen Sie zu: https://github.com/settings/tokens

## 📋 Alternative: SSH-Schlüssel (empfohlen für langfristige Nutzung)

SSH-Schlüssel sind sicherer und bequemer als Tokens:

### SSH-Schlüssel erstellen:

```bash
# SSH-Schlüssel generieren
ssh-keygen -t ed25519 -C "your_email@example.com"

# Öffentlichen Schlüssel anzeigen
cat ~/.ssh/id_ed25519.pub
```

### SSH-Schlüssel zu GitHub hinzufügen:

1. Kopieren Sie den öffentlichen Schlüssel
2. Gehen Sie zu: https://github.com/settings/keys
3. Klicken Sie auf **"New SSH key"**
4. Fügen Sie den Schlüssel ein

### Remote auf SSH umstellen:

```bash
cd /Users/basti/Documents/Projekte/Downloader
git remote set-url origin git@github.com:msebastian100/Universal-Downloader.git
```

Dann können Sie ohne Token pushen:
```bash
git push -u origin main
```

## 🆘 Troubleshooting

### Problem: "Authentication failed"

**Lösung:**
- Stellen Sie sicher, dass Sie den Token (nicht das Passwort) verwenden
- Prüfen Sie, ob der Token abgelaufen ist
- Prüfen Sie, ob die `repo` Berechtigung aktiviert ist

### Problem: "Permission denied"

**Lösung:**
- Prüfen Sie, ob Sie Zugriff auf das Repository haben
- Prüfen Sie, ob der Token die richtigen Berechtigungen hat

### Problem: "Token expired"

**Lösung:**
- Erstellen Sie einen neuen Token
- Verwenden Sie den neuen Token beim nächsten Push

## 📚 Weitere Informationen

- [GitHub Docs: Personal Access Tokens](https://docs.github.com/en/authentication/keeping-your-account-and-data-secure/creating-a-personal-access-token)
- [GitHub Docs: SSH Keys](https://docs.github.com/en/authentication/connecting-to-github-with-ssh)
