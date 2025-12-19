# ⚠️ SICHERHEITSWARNUNG - Token kompromittiert

## 🚨 WICHTIG: Token wurde in Datei eingefügt!

Ihr GitHub Personal Access Token wurde versehentlich in eine Datei eingefügt.

## ✅ Sofortige Maßnahmen:

### 1. Token widerrufen (SOFORT!)

1. Gehen Sie zu: https://github.com/settings/tokens
2. Finden Sie den betroffenen Token
3. Klicken Sie auf "Revoke" (Widerrufen)
4. Bestätigen Sie die Löschung

### 2. Neuen Token erstellen

1. Gehen Sie zu: https://github.com/settings/tokens
2. Klicken Sie auf "Generate new token" → "Generate new token (classic)"
3. Aktivieren Sie:
   - ✅ `repo`
   - ✅ `workflow` (optional)
4. Kopieren Sie den neuen Token
5. Verwenden Sie den neuen Token beim `git push`

### 3. Token sicher verwenden

**NIEMALS:**
- ❌ Token in Dateien speichern
- ❌ Token in Code committen
- ❌ Token öffentlich teilen
- ❌ Token in Screenshots zeigen

**IMMER:**
- ✅ Token nur beim `git push` eingeben
- ✅ Token in Passwort-Manager speichern
- ✅ Token regelmäßig erneuern
- ✅ Token mit Ablaufzeit erstellen

## 🔒 Best Practices

### Option 1: Token beim Push eingeben
```bash
git push -u origin main
# Username: msebastian100
# Password: [Token hier einfügen]
```

### Option 2: Git Credential Helper (empfohlen)
```bash
# Token einmalig speichern (verschlüsselt)
git config --global credential.helper osxkeychain  # macOS
# oder
git config --global credential.helper store  # Linux/Windows
```

### Option 3: SSH-Schlüssel (am sichersten)
Siehe: [GITHUB_TOKEN_ANLEITUNG.md](GITHUB_TOKEN_ANLEITUNG.md) - Abschnitt "Alternative: SSH-Schlüssel"

## 📋 Checkliste

- [ ] Token widerrufen
- [ ] Neuen Token erstellen
- [ ] Alten Token aus allen Dateien entfernt
- [ ] Neuen Token sicher gespeichert (Passwort-Manager)
- [ ] Code hochgeladen mit neuem Token

## 🆘 Falls Token bereits committed wurde

Falls der Token bereits in Git-Historie ist:

1. **Token sofort widerrufen** (siehe oben)
2. **Neuen Token erstellen**
3. **Git-Historie bereinigen** (falls Repository noch nicht öffentlich):
   ```bash
   # Nur wenn Repository noch nicht öffentlich ist!
   git filter-branch --force --index-filter \
     "git rm --cached --ignore-unmatch GITHUB_TOKEN_ANLEITUNG.md" \
     --prune-empty --tag-name-filter cat -- --all
   ```

**WICHTIG**: Wenn das Repository bereits öffentlich ist, ist der Token kompromittiert. Widerrufen Sie ihn sofort!
