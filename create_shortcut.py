#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Erstellt Startmenü-Verknüpfungen für Windows und Linux
"""

import sys
import os
from pathlib import Path

def create_windows_shortcut():
    """Erstellt Windows .lnk Verknüpfung im Startmenü"""
    script_dir = Path(__file__).parent.absolute()
    launcher_path = script_dir / "start_launcher.vbs"
    
    if not launcher_path.exists():
        print(f"[WARNING] start_launcher.vbs nicht gefunden: {launcher_path}")
        return False
    
    try:
        import win32com.client
        shell = win32com.client.Dispatch("WScript.Shell")
        start_menu = shell.SpecialFolders("StartMenu")
        programs_folder = Path(start_menu) / "Programs"
        programs_folder.mkdir(parents=True, exist_ok=True)
        
        shortcut_path = programs_folder / "Universal Downloader.lnk"
        
        # Prüfe ob bereits existiert
        if shortcut_path.exists():
            # Prüfe ob korrekt
            existing = shell.CreateShortCut(str(shortcut_path))
            if str(launcher_path).lower() in existing.Targetpath.lower():
                print(f"[INFO] Windows-Verknüpfung existiert bereits: {shortcut_path}")
                return True
        
        # Erstelle Shortcut
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(launcher_path)
        shortcut.WorkingDirectory = str(script_dir)
        shortcut.Description = "Universal Downloader - Downloader für Musik und Videos"
        
        # Icon
        icon_paths = [script_dir / "icon.ico", script_dir / "icon.png"]
        for icon_path in icon_paths:
            if icon_path.exists():
                shortcut.IconLocation = str(icon_path)
                break
        
        shortcut.WindowStyle = 7  # Minimized
        shortcut.save()
        
        print(f"[OK] Windows-Verknüpfung erstellt: {shortcut_path}")
        return True
    except ImportError:
        # Fallback: Verwende VBScript
        try:
            vbs_script = script_dir / "create_shortcut_temp.vbs"
            
            # Erstelle VBScript temporär
            vbs_content = f'''Set WshShell = CreateObject("WScript.Shell")
Set fso = CreateObject("Scripting.FileSystemObject")

scriptPath = "{script_dir}"
startMenuPath = WshShell.SpecialFolders("StartMenu") & "\\Programs"
shortcutPath = startMenuPath & "\\Universal Downloader.lnk"
launcherPath = scriptPath & "\\start_launcher.vbs"

' Erstelle Startmenü-Ordner falls nicht vorhanden
If Not fso.FolderExists(startMenuPath) Then
    fso.CreateFolder startMenuPath
End If

' Prüfe ob bereits existiert
If fso.FileExists(shortcutPath) Then
    Set existingShortcut = WshShell.CreateShortcut(shortcutPath)
    If InStr(LCase(existingShortcut.TargetPath), "start_launcher.vbs") > 0 Then
        WScript.Echo "[INFO] Windows-Verknüpfung existiert bereits: " & shortcutPath
        WScript.Quit 0
    End If
End If

' Finde Icon
iconPath = ""
If fso.FileExists(scriptPath & "\\icon.ico") Then
    iconPath = scriptPath & "\\icon.ico"
ElseIf fso.FileExists(scriptPath & "\\icon.png") Then
    iconPath = scriptPath & "\\icon.png"
End If

' Erstelle Shortcut
Set shortcut = WshShell.CreateShortcut(shortcutPath)
shortcut.TargetPath = launcherPath
shortcut.WorkingDirectory = scriptPath
shortcut.Description = "Universal Downloader - Downloader für Musik und Videos"
If iconPath <> "" Then
    shortcut.IconLocation = iconPath & ",0"
End If
shortcut.WindowStyle = 7
shortcut.Save

WScript.Echo "[OK] Windows-Verknüpfung erstellt: " & shortcutPath
'''
            with open(vbs_script, 'w', encoding='utf-8') as f:
                f.write(vbs_content)
            
            import subprocess
            result = subprocess.run(['cscript', '//nologo', str(vbs_script)], 
                                  capture_output=True, text=True, timeout=10)
            # Lösche temporäre VBS-Datei
            try:
                vbs_script.unlink()
            except:
                pass
            
            if result.returncode == 0:
                print(result.stdout.strip())
                return True
            else:
                print(f"[WARNING] Konnte Windows-Verknüpfung nicht erstellen: {result.stderr}")
                return False
        except Exception as e:
            print(f"[WARNING] Konnte Windows-Verknüpfung nicht erstellen: {e}")
            return False
    except Exception as e:
        print(f"[WARNING] Konnte Windows-Verknüpfung nicht erstellen: {e}")
        return False
    
    try:
        script_dir = Path(__file__).parent.absolute()
        launcher_path = script_dir / "start_launcher.vbs"
        
        if not launcher_path.exists():
            print(f"[WARNING] start_launcher.vbs nicht gefunden: {launcher_path}")
            return False
        
        # Startmenü-Pfad
        shell = win32com.client.Dispatch("WScript.Shell")
        start_menu = shell.SpecialFolders("StartMenu")
        programs_folder = Path(start_menu) / "Programs"
        programs_folder.mkdir(parents=True, exist_ok=True)
        
        shortcut_path = programs_folder / "Universal Downloader.lnk"
        
        # Erstelle Shortcut
        shortcut = shell.CreateShortCut(str(shortcut_path))
        shortcut.Targetpath = str(launcher_path)
        shortcut.WorkingDirectory = str(script_dir)
        shortcut.Description = "Universal Downloader - Downloader für Musik und Videos"
        
        # Icon
        icon_paths = [script_dir / "icon.ico", script_dir / "icon.png"]
        for icon_path in icon_paths:
            if icon_path.exists():
                shortcut.IconLocation = str(icon_path)
                break
        
        shortcut.WindowStyle = 7  # Minimized
        shortcut.save()
        
        print(f"[OK] Windows-Verknüpfung erstellt: {shortcut_path}")
        return True
    except Exception as e:
        print(f"[WARNING] Konnte Windows-Verknüpfung nicht erstellen: {e}")
        return False

def create_linux_desktop():
    """Erstellt Linux .desktop Datei im Startmenü"""
    try:
        script_dir = Path(__file__).parent.absolute()
        start_script = script_dir / "start.sh"
        
        if not start_script.exists():
            print(f"[WARNING] start.sh nicht gefunden: {start_script}")
            return False
        
        # Startmenü-Pfad
        desktop_dir = Path.home() / ".local" / "share" / "applications"
        desktop_dir.mkdir(parents=True, exist_ok=True)
        
        desktop_file = desktop_dir / "universal-downloader.desktop"
        
        # Prüfe ob bereits existiert
        if desktop_file.exists():
            # Prüfe ob korrekt
            try:
                with open(desktop_file, 'r', encoding='utf-8') as f:
                    content = f.read()
                    if str(start_script) in content:
                        print(f"[INFO] Linux-Verknüpfung existiert bereits: {desktop_file}")
                        return True
            except:
                pass
        
        # Finde Icon
        icon_path = ""
        icon_paths = [script_dir / "icon.png", script_dir / "icon.ico", script_dir / "icon.svg"]
        for icon in icon_paths:
            if icon.exists():
                icon_path = str(icon)
                break
        
        # Kopiere Icon ins System-Icon-Verzeichnis falls möglich
        system_icon_path = ""
        if icon_path:
            try:
                # Versuche Icon ins lokale Icon-Verzeichnis zu kopieren
                icon_dir = Path.home() / ".local" / "share" / "icons"
                icon_dir.mkdir(parents=True, exist_ok=True)
                
                icon_file = Path(icon_path)
                if icon_file.exists():
                    # Verwende PNG für Linux (beste Unterstützung)
                    if icon_file.suffix.lower() in ['.png', '.svg']:
                        system_icon_path = str(icon_dir / "universal-downloader.png")
                        import shutil
                        shutil.copy2(icon_path, system_icon_path)
                        system_icon_path = "universal-downloader"  # Relativer Name für Icon-Theme
                    else:
                        # Konvertiere ICO zu PNG falls nötig (wird später implementiert)
                        system_icon_path = icon_path
            except Exception as e:
                # Fallback: Verwende absoluten Pfad
                system_icon_path = icon_path
        
        # Erstelle .desktop Datei
        desktop_content = f"""[Desktop Entry]
Version=1.0
Type=Application
Name=Universal Downloader
Comment=Downloader für Musik und Videos von verschiedenen Plattformen
Exec=bash "{start_script}"
Path={script_dir}
Icon={system_icon_path if system_icon_path else icon_path}
Terminal=false
Categories=AudioVideo;Network;Utility;
Keywords=downloader;music;video;youtube;deezer;spotify;
StartupNotify=true
StartupWMClass=UniversalDownloader
WMClass=UniversalDownloader
"""
        
        with open(desktop_file, 'w', encoding='utf-8') as f:
            f.write(desktop_content)
        
        # Mache ausführbar
        os.chmod(desktop_file, 0o755)
        
        print(f"[OK] Linux-Verknüpfung erstellt: {desktop_file}")
        return True
    except Exception as e:
        print(f"[WARNING] Konnte Linux-Verknüpfung nicht erstellen: {e}")
        import traceback
        print(f"[DEBUG] Traceback: {traceback.format_exc()}")
        return False

def main():
    """Hauptfunktion"""
    platform = sys.platform
    
    print(f"[INFO] Erstelle Startmenü-Verknüpfung für {platform}...")
    
    if platform == "win32":
        success = create_windows_shortcut()
    elif platform.startswith("linux"):
        success = create_linux_desktop()
    elif platform == "darwin":
        # macOS - könnte .app Bundle erstellen, aber das ist komplexer
        print("[INFO] macOS wird derzeit nicht unterstützt für automatische Verknüpfung")
        success = False
    else:
        print(f"[INFO] Plattform {platform} wird derzeit nicht unterstützt")
        success = False
    
    if success:
        sys.exit(0)
    else:
        sys.exit(1)

if __name__ == "__main__":
    main()
