#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erstellt den Windows-Installer mit Inno Setup.
- Baut zuerst die .exe mit build_windows.py (oder nutzt vorhandene)
- Setzt die Version aus version.py in installer.iss
- Kompiliert installer.iss zu einer Setup.exe

Voraussetzungen:
- Windows mit installiertem Inno Setup 6 (https://jrsoftware.org/isinfo.php)
- iscc.exe im PATH oder unter "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe"
"""
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

# Encoding-Fix für Windows (wie in build_windows.py)
if sys.platform == "win32" or os.getenv("GITHUB_ACTIONS") == "true":
    import io
    try:
        if hasattr(sys.stdout, "buffer"):
            sys.stdout = io.TextIOWrapper(
                sys.stdout.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
        if hasattr(sys.stderr, "buffer"):
            sys.stderr = io.TextIOWrapper(
                sys.stderr.buffer, encoding="utf-8", errors="replace", line_buffering=True
            )
    except Exception:
        pass


def get_version():
    """Liest die Versionsnummer aus version.py"""
    try:
        version_file = Path(__file__).parent / "version.py"
        if version_file.exists():
            content = version_file.read_text(encoding="utf-8")
            match = re.search(r'__version__\s*=\s*["\']([^"\']+)["\']', content)
            if match:
                return match.group(1)
    except Exception as e:
        print(f"[WARNING] Versionsnummer nicht lesbar: {e}")
    return "0.0.0"


def find_iscc():
    """Sucht die Inno Setup Kommandozeile (iscc.exe)."""
    # 1) Im PATH
    iscc = shutil.which("iscc.exe")
    if iscc:
        return iscc
    # 2) Typische Installationspfade
    for base in [
        os.environ.get("ProgramFiles(x86)", "C:\\Program Files (x86)"),
        os.environ.get("ProgramFiles", "C:\\Program Files"),
    ]:
        if not base:
            continue
        path = Path(base) / "Inno Setup 6" / "ISCC.exe"
        if path.exists():
            return str(path)
    return None


def ensure_exe():
    """
    Stellt sicher, dass dist/UniversalDownloader.exe existiert.
    Entweder durch Build (build_windows.py) oder durch Kopie der versionierten exe.
    """
    dist = Path("dist")
    universal = dist / "UniversalDownloader.exe"
    if universal.exists():
        print("[OK] dist/UniversalDownloader.exe vorhanden.")
        return True
    # Suche versionierte exe (z. B. universal-downloader_v2.1.7.exe)
    versioned = list(dist.glob("universal-downloader_v*.exe"))
    if versioned:
        shutil.copy2(versioned[0], universal)
        print(f"[OK] {versioned[0].name} -> UniversalDownloader.exe kopiert.")
        return True
    # Exe bauen
    print("Keine .exe gefunden. Starte build_windows.py ...")
    r = subprocess.run([sys.executable, "build_windows.py"], cwd=Path(__file__).parent)
    if r.returncode != 0:
        print("[FEHLER] build_windows.py ist fehlgeschlagen.")
        return False
    if not universal.exists():
        # build_windows benennt in universal-downloader_vX.exe um
        versioned = list(dist.glob("universal-downloader_v*.exe"))
        if versioned:
            shutil.copy2(versioned[0], universal)
        else:
            print("[FEHLER] Nach dem Build wurde keine .exe in dist/ gefunden.")
            return False
    return True


# Python-Version für gebündeltes Embeddable (Windows)
PYTHON_EMBED_VERSION = "3.12.8"


def ensure_python_embed(root: Path) -> bool:
    """
    Lädt das Windows-embeddable-Python, aktiviert pip und installiert yt-dlp.
    Ergebnis in dist/python_embed/ (wird vom Installer nach {app}/python/ kopiert).
    """
    import zipfile
    import urllib.request

    embed_dir = root / "dist" / "python_embed"
    python_exe = embed_dir / "python.exe"
    if python_exe.exists():
        # Prüfen ob yt-dlp vorhanden (Lib/site-packages/yt_dlp)
        site_packages = embed_dir / "Lib" / "site-packages"
        if (site_packages / "yt_dlp").exists() or (site_packages / "yt_dlp").with_suffix(".py").exists():
            print("[OK] Gebündeltes Python (mit yt-dlp) für Installer bereits vorhanden.")
            return True
        print("[INFO] Gebündeltes Python vorhanden, aber yt-dlp fehlt – installiere nach...")

    dist_dir = root / "dist"
    dist_dir.mkdir(parents=True, exist_ok=True)
    zip_name = f"python-{PYTHON_EMBED_VERSION}-embed-amd64.zip"
    zip_path = root / "dist" / zip_name
    if not zip_path.exists():
        print(f"Lade Windows-embeddable Python {PYTHON_EMBED_VERSION}...")
        url = f"https://www.python.org/ftp/python/{PYTHON_EMBED_VERSION}/{zip_name}"
        try:
            req = urllib.request.Request(url, headers={"User-Agent": "UniversalDownloader-Build/1.0"})
            with urllib.request.urlopen(req, timeout=120) as resp:
                zip_path.write_bytes(resp.read())
        except Exception as e:
            print(f"[WARNING] Python-Embed-Download fehlgeschlagen: {e}")
            return False

    if not python_exe.exists():
        print("Entpacke Python-Embeddable...")
        embed_dir.mkdir(parents=True, exist_ok=True)
        with zipfile.ZipFile(zip_path, "r") as z:
            z.extractall(embed_dir)
        # import site in ._pth aktivieren (für pip/site-packages)
        for pth in embed_dir.glob("python*._pth"):
            text = pth.read_text(encoding="utf-8")
            if "# import site" in text:
                text = text.replace("# import site", "import site")
                pth.write_text(text, encoding="utf-8")
            break

    env = os.environ.copy()
    env["PYTHONPATH"] = ""
    site_packages = embed_dir / "Lib" / "site-packages"
    has_pip = (site_packages / "pip").exists() or (embed_dir / "Scripts" / "pip.exe").exists()

    if not has_pip:
        get_pip = embed_dir / "get-pip.py"
        if not get_pip.exists():
            print("Lade get-pip.py...")
            try:
                req = urllib.request.Request(
                    "https://bootstrap.pypa.io/get-pip.py",
                    headers={"User-Agent": "UniversalDownloader-Build/1.0"},
                )
                with urllib.request.urlopen(req, timeout=30) as resp:
                    get_pip.write_bytes(resp.read())
            except Exception as e:
                print(f"[WARNING] get-pip.py-Download fehlgeschlagen: {e}")
                return False
        print("Installiere pip ins gebündelte Python...")
        try:
            subprocess.run(
                [str(python_exe), str(get_pip), "--no-warn-script-location", "--quiet"],
                cwd=str(embed_dir),
                env=env,
                timeout=120,
                check=True,
            )
            if get_pip.exists():
                get_pip.unlink(missing_ok=True)
        except subprocess.CalledProcessError as e:
            print(f"[WARNING] pip-Installation im Embed-Python fehlgeschlagen: {e}")
            return False
        except Exception as e:
            print(f"[WARNING] pip-Installation: {e}")
            return False

    print("Installiere yt-dlp ins gebündelte Python...")
    try:
        subprocess.run(
            [str(python_exe), "-m", "pip", "install", "yt-dlp", "--no-warn-script-location", "--quiet", "--disable-pip-version-check"],
            cwd=str(embed_dir),
            env=env,
            timeout=180,
            check=True,
        )
    except Exception as e:
        print(f"[WARNING] yt-dlp-Installation im Embed-Python fehlgeschlagen: {e}")
        return False

    print("[OK] Gebündeltes Python (mit yt-dlp) für Installer bereit.")
    return True


def update_installer_version(version: str):
    """Ersetzt die Platzhalter-Version in installer.iss."""
    iss = Path(__file__).parent / "installer.iss"
    if not iss.exists():
        print("[FEHLER] installer.iss nicht gefunden.")
        return False
    text = iss.read_text(encoding="utf-8")
    # Ersetze #define MyAppVersion "0.0.0" (oder aktuelle Version)
    new_text = re.sub(
        r'(#define\s+MyAppVersion\s+")[^"]*(")',
        r'\g<1>' + version + r'\2',
        text,
    )
    if new_text == text:
        print("[WARNING] MyAppVersion in installer.iss wurde nicht geändert.")
    else:
        iss.write_text(new_text, encoding="utf-8")
        print(f"[OK] installer.iss: Version auf {version} gesetzt.")
    return True


def main():
    root = Path(__file__).parent
    os.chdir(root)

    if sys.platform != "win32" and os.getenv("GITHUB_ACTIONS") != "true":
        print("[WARNING] Installer wird nur unter Windows gebaut. Inno Setup läuft nur auf Windows.")
        print("Unter anderen Systemen kann nur die Version in installer.iss gesetzt werden.")
        ans = input("Trotzdem fortfahren (Version setzen, kein iscc)? (j/n): ")
        if ans.lower() != "j":
            sys.exit(0)
        version = get_version()
        update_installer_version(version)
        sys.exit(0)

    version = get_version()
    print(f"Version: {version}")

    if not (root / "icon.ico").exists():
        print("[Hinweis] icon.ico nicht gefunden – Installer und EXE nutzen ggf. Standard-Icon.")
        print("          Für eigenes Icon: icon.ico im Projektordner anlegen (z.B. aus icon.png konvertieren).")

    if not update_installer_version(version):
        sys.exit(1)

    # Unter Windows: exe sicherstellen, ffmpeg für Installer-Bundle laden, dann Inno ausführen
    if sys.platform == "win32":
        if not ensure_exe():
            sys.exit(1)
        # ffmpeg in dist/ffmpeg für Installer (wird mit ausgeliefert, Nutzer braucht nichts nachzuinstallieren)
        ffmpeg_bin = root / "dist" / "ffmpeg" / "bin" / "ffmpeg.exe"
        if not ffmpeg_bin.exists():
            print("Lade ffmpeg für Installer-Bundle (wird mit ausgeliefert)...")
            try:
                from auto_install_dependencies import download_ffmpeg_windows_to
                if download_ffmpeg_windows_to(root / "dist" / "ffmpeg"):
                    print("[OK] ffmpeg für Installer bereit.")
                else:
                    print("[WARNING] ffmpeg-Download fehlgeschlagen – Installer wird ohne ffmpeg erstellt.")
            except Exception as e:
                print(f"[WARNING] ffmpeg konnte nicht geladen werden: {e} – Installer wird ohne ffmpeg erstellt.")
        else:
            print("[OK] ffmpeg für Installer bereits vorhanden.")

        # yt-dlp.exe in dist/ für Installer (Standalone-EXE, kein System-Python nötig – z. B. Sandbox)
        dist_dir = root / "dist"
        ytdlp_exe = dist_dir / "yt-dlp.exe"
        if not ytdlp_exe.exists():
            print("Lade yt-dlp.exe für Installer-Bundle (damit Download auch ohne Python funktioniert)...")
            try:
                import urllib.request
                url = "https://github.com/yt-dlp/yt-dlp/releases/latest/download/yt-dlp.exe"
                req = urllib.request.Request(url, headers={"User-Agent": "UniversalDownloader-Build/1.0"})
                with urllib.request.urlopen(req, timeout=60) as resp:
                    data = resp.read()
                dist_dir.mkdir(parents=True, exist_ok=True)
                ytdlp_exe.write_bytes(data)
                print("[OK] yt-dlp.exe für Installer bereit.")
            except Exception as e:
                print(f"[WARNING] yt-dlp.exe-Download fehlgeschlagen: {e} – Installer wird ohne yt-dlp.exe erstellt (App nutzt dann eingebettetes Modul).")
        else:
            print("[OK] yt-dlp.exe für Installer bereits vorhanden.")

        # Optional: Gebündeltes Python (Embeddable + yt-dlp) für Installer – läuft auch ohne System-Python
        if not ensure_python_embed(root):
            print("[Hinweis] Installer wird ohne gebündeltes Python erstellt (yt-dlp.exe oder System-Python wird genutzt).")

        iscc = find_iscc()
        if not iscc:
            print("[FEHLER] Inno Setup nicht gefunden. Bitte installieren:")
            print("  https://jrsoftware.org/isinfo.php")
            print("  und iscc.exe in den PATH legen oder unter")
            print('  "C:\\Program Files (x86)\\Inno Setup 6\\ISCC.exe" installieren.')
            sys.exit(1)
        print(f"Kompiliere Installer mit: {iscc}")
        dist_installer = root / "dist_installer"
        dist_installer.mkdir(exist_ok=True)
        r = subprocess.run([iscc, "installer.iss"], cwd=root)
        if r.returncode != 0:
            print("[FEHLER] Inno Setup Kompilierung fehlgeschlagen.")
            sys.exit(1)
        setup_name = f"UniversalDownloader_Setup_v{version}.exe"
        setup_path = dist_installer / setup_name
        if setup_path.exists():
            print("=" * 60)
            print("[OK] Installer erstellt:")
            print(f"    {setup_path.absolute()}")
            print("=" * 60)
        sys.exit(0 if r.returncode == 0 else 1)

    sys.exit(0)


if __name__ == "__main__":
    main()
