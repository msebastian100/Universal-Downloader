#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Serien-Wächter Tray-Helper (Menüleiste / System-Tray).

- Icon in der Menüleiste (macOS) bzw. System-Tray (Windows/Linux)
- Menü: laufende Downloads + Fortschritt, neue Folgen, wartende Queue
- Aktionen: Jetzt prüfen, Download abbrechen, Ordner öffnen, Hauptprogramm öffnen

Start:  python3 series_watch_tray.py
        python3 series_watch_tray.py --once
"""

from __future__ import annotations

import argparse
import os
import shutil
import subprocess
import sys
import threading
import time
from pathlib import Path
from typing import Any, Dict, List, Optional

_ROOT = Path(__file__).resolve().parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

import series_watch
from path_helper import get_app_base_path


def _log(msg: str) -> None:
    ts = time.strftime("%Y-%m-%d %H:%M:%S")
    line = f"[{ts}] {msg}"
    print(line, flush=True)
    try:
        base = get_app_base_path()
        log_dir = Path(base) / "Logs"
        log_dir.mkdir(parents=True, exist_ok=True)
        with open(log_dir / "series_watch_tray.log", "a", encoding="utf-8") as f:
            f.write(line + "\n")
    except Exception:
        pass


def _progress_bar(percent: float, width: int = 10) -> str:
    try:
        p = max(0.0, min(100.0, float(percent)))
    except (TypeError, ValueError):
        p = 0.0
    filled = int(round(width * p / 100.0))
    filled = max(0, min(width, filled))
    return "[" + ("█" * filled) + ("░" * (width - filled)) + f"] {p:.0f}%"


def _truncate(s: str, n: int = 42) -> str:
    s = (s or "").strip()
    if len(s) <= n:
        return s
    return s[: n - 1] + "…"


def _load_base_icon():
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return None
    icon_path = _ROOT / "icon.png"
    if icon_path.exists():
        try:
            return Image.open(icon_path).convert("RGBA").resize((64, 64))
        except Exception:
            pass
    img = Image.new("RGBA", (64, 64), (40, 40, 40, 255))
    d = ImageDraw.Draw(img)
    d.ellipse((8, 8, 56, 56), fill=(70, 130, 180, 255))
    return img


def _icon_with_badge(base_img, *, mode: str = "idle", percent: float = 0.0):
    """
    mode: idle | new | downloading
    Kleiner Punkt / Fortschrittsring für Menüleisten-Icon.
    """
    try:
        from PIL import Image, ImageDraw
    except Exception:
        return base_img
    if base_img is None:
        return None
    img = base_img.copy()
    draw = ImageDraw.Draw(img)
    w, h = img.size

    if mode == "downloading":
        # Fortschrittsring unten rechts
        box = (w - 28, h - 28, w - 4, h - 4)
        draw.ellipse(box, outline=(255, 255, 255, 220), width=3)
        # Näherungsweise gefüllter Bogen über Kreis+Overlay
        p = max(0.0, min(100.0, float(percent or 0)))
        if p >= 99:
            draw.ellipse((w - 26, h - 26, w - 6, h - 6), fill=(80, 200, 120, 230))
        else:
            draw.ellipse((w - 22, h - 22, w - 10, h - 10), fill=(80, 180, 255, 230))
            # Prozent-Hinweis als Balken unten
            bw = int((w - 8) * p / 100.0)
            draw.rectangle((4, h - 6, 4 + bw, h - 2), fill=(80, 180, 255, 255))
    elif mode == "new":
        # Roter Hinweis-Punkt
        draw.ellipse((w - 22, 4, w - 4, 22), fill=(220, 60, 60, 255), outline=(255, 255, 255, 255))
    return img


def _pid_running(pid: int) -> bool:
    if pid <= 0:
        return False
    if sys.platform == "win32":
        import ctypes
        PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
        STILL_ACTIVE = 259
        handle = ctypes.windll.kernel32.OpenProcess(PROCESS_QUERY_LIMITED_INFORMATION, False, int(pid))
        if not handle:
            return False
        try:
            code = ctypes.c_ulong()
            if ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code)):
                return int(code.value) == STILL_ACTIVE
            return True
        finally:
            ctypes.windll.kernel32.CloseHandle(handle)
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def try_become_tray_instance(base: Path) -> bool:
    """Nur eine Tray-Instanz pro App-Basisordner."""
    path = Path(base) / "series_watch_tray.pid"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                old = int((path.read_text(encoding="utf-8") or "0").strip().split()[0])
            except (ValueError, OSError):
                old = 0
            if old and old != os.getpid() and _pid_running(old):
                _log(f"Tray läuft bereits (PID {old}).")
                return False
        path.write_text(str(os.getpid()), encoding="utf-8")
        return True
    except Exception as e:
        _log(f"Tray-PID-Datei: {e}")
        return True


def steal_tray_instance(base: Path) -> None:
    """Beendet eine andere Tray-Instanz und übernimmt die PID-Datei."""
    path = Path(base) / "series_watch_tray.pid"
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            try:
                old = int((path.read_text(encoding="utf-8") or "0").strip().split()[0])
            except (ValueError, OSError):
                old = 0
            if old and old != os.getpid() and _pid_running(old):
                _log(f"Beende alte Tray-Instanz PID {old}")
                try:
                    if sys.platform == "win32":
                        subprocess.run(
                            ["taskkill", "/PID", str(old), "/F"],
                            capture_output=True,
                            timeout=8,
                            check=False,
                        )
                    else:
                        os.kill(old, 15)
                        time.sleep(0.4)
                        if _pid_running(old):
                            os.kill(old, 9)
                except Exception as e:
                    _log(f"Alte Instanz nicht beendet: {e}")
        path.write_text(str(os.getpid()), encoding="utf-8")
    except Exception as e:
        _log(f"steal_tray_instance: {e}")


def _windows_unique_pythonw() -> str:
    """Eigene EXE-Kopie, damit Windows 11 einen sichtbaren Infobereich-Eintrag anlegt."""
    src = Path(sys.executable)
    if src.name.lower() != "pythonw.exe":
        cand = src.with_name("pythonw.exe")
        if cand.is_file():
            src = cand
    dest_dir = Path(os.environ.get("LOCALAPPDATA") or Path.home()) / "UniversalDownloader"
    dest = dest_dir / "UniversalDownloaderTray.exe"
    try:
        dest_dir.mkdir(parents=True, exist_ok=True)
        need = (not dest.exists()) or dest.stat().st_size != src.stat().st_size
        if need:
            shutil.copy2(src, dest)
    except Exception as e:
        _log(f"Tray-EXE Kopie: {e}")
        return str(src)
    return str(dest)


def get_tray_launch_argv() -> List[str]:
    """Kommandozeile, mit der der Wächter nach dem Login startet."""
    if getattr(sys, "frozen", False):
        return [sys.executable, "--series-watch-tray"]
    script = str(_ROOT / "series_watch_tray.py")
    exe = sys.executable
    if sys.platform == "win32":
        exe = _windows_unique_pythonw()
    return [exe, script]


def _quote_argv(argv: List[str]) -> str:
    if sys.platform == "win32":
        return subprocess.list2cmdline(argv)
    parts = []
    for a in argv:
        if not a or any(c in a for c in ' \t\n"\'$'):
            parts.append("'" + a.replace("'", "'\\''") + "'")
        else:
            parts.append(a)
    return " ".join(parts)


def windows_promote_notify_icon() -> None:
    """Windows 11: Icon nicht im versteckten Infobereich lassen."""
    if sys.platform != "win32":
        return
    try:
        import winreg
    except ImportError:
        return
    needles = []
    try:
        needles.append(Path(sys.executable).name.lower())
    except Exception:
        pass
    needles.extend(
        [
            "pythonw.exe",
            "python.exe",
            "universaldownloader",
            "universal-downloader",
            "universoldownloadertray.exe",
        ]
    )
    root_path = r"Control Panel\NotifyIconSettings"
    try:
        root = winreg.OpenKey(winreg.HKEY_CURRENT_USER, root_path)
    except OSError:
        return
    i = 0
    while True:
        try:
            sub = winreg.EnumKey(root, i)
        except OSError:
            break
        i += 1
        try:
            k = winreg.OpenKey(root, sub, 0, winreg.KEY_READ | winreg.KEY_SET_VALUE)
        except OSError:
            continue
        try:
            exe, _typ = winreg.QueryValueEx(k, "ExecutablePath")
        except OSError:
            exe = ""
        blob = (exe or "").replace("/", "\\").lower()
        if any(n in blob for n in needles if n):
            try:
                winreg.SetValueEx(k, "IsPromoted", 0, winreg.REG_DWORD, 1)
            except OSError:
                pass
        try:
            winreg.CloseKey(k)
        except OSError:
            pass
    try:
        winreg.CloseKey(root)
    except OSError:
        pass
    try:
        import winreg as _wr
        expl = _wr.OpenKey(
            _wr.HKEY_CURRENT_USER,
            r"Software\Microsoft\Windows\CurrentVersion\Explorer",
            0,
            _wr.KEY_SET_VALUE,
        )
        _wr.SetValueEx(expl, "EnableAutoTray", 0, _wr.REG_DWORD, 0)
        _wr.CloseKey(expl)
    except OSError:
        pass


# --- Native Windows-Notify-Icon (Win11 zeigt pystray oft nicht an) ---
_WM_TRAYICON = 0x8000 + 21  # WM_APP + 21
_NIF_MESSAGE = 0x00000001
_NIF_ICON = 0x00000002
_NIF_TIP = 0x00000004
_NIF_SHOWTIP = 0x00000080
_NIM_ADD = 0x00000000
_NIM_MODIFY = 0x00000001
_NIM_DELETE = 0x00000002
_NIM_SETVERSION = 0x00000004
_NOTIFYICON_VERSION_4 = 4
_WM_LBUTTONUP = 0x0202
_WM_RBUTTONUP = 0x0205
_WM_LBUTTONDBLCLK = 0x0203
_WM_CONTEXTMENU = 0x007B
_NIN_SELECT = 0x0400
_NIN_KEYSELECT = 0x0401
_HWND_MESSAGE = -3


def _win_nid_class():
    import ctypes
    from ctypes import wintypes

    class NOTIFYICONDATAW(ctypes.Structure):
        _fields_ = [
            ("cbSize", wintypes.DWORD),
            ("hWnd", wintypes.HWND),
            ("uID", wintypes.UINT),
            ("uFlags", wintypes.UINT),
            ("uCallbackMessage", wintypes.UINT),
            ("hIcon", wintypes.HICON),
            ("szTip", wintypes.WCHAR * 128),
            ("dwState", wintypes.DWORD),
            ("dwStateMask", wintypes.DWORD),
            ("szInfo", wintypes.WCHAR * 256),
            ("uVersion", wintypes.UINT),
            ("szInfoTitle", wintypes.WCHAR * 64),
            ("dwInfoFlags", wintypes.DWORD),
            ("guidItem", ctypes.c_ubyte * 16),
            ("hBalloonIcon", wintypes.HICON),
        ]

    return NOTIFYICONDATAW


class WinNotifyIcon:
    """Shell_NotifyIcon auf eigenem Message-only-Fenster (ctypes 64-bit-sicher)."""

    def __init__(self, on_left_click, on_right_click):
        self.on_left_click = on_left_click
        self.on_right_click = on_right_click
        self.hwnd = None
        self.hicon = None
        self._wndproc = None
        self._class_atom = None
        self._hinstance = None
        self._added = False
        self._uid = 1

    def create(self) -> bool:
        if sys.platform != "win32":
            return False
        import ctypes
        from ctypes import wintypes

        user32 = ctypes.WinDLL("user32", use_last_error=True)
        kernel32 = ctypes.WinDLL("kernel32", use_last_error=True)
        shell32 = ctypes.WinDLL("shell32", use_last_error=True)

        LRESULT = ctypes.c_ssize_t
        WNDPROC = ctypes.WINFUNCTYPE(LRESULT, wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM)

        class WNDCLASSW(ctypes.Structure):
            _fields_ = [
                ("style", wintypes.UINT),
                ("lpfnWndProc", WNDPROC),
                ("cbClsExtra", ctypes.c_int),
                ("cbWndExtra", ctypes.c_int),
                ("hInstance", wintypes.HINSTANCE),
                ("hIcon", wintypes.HICON),
                ("hCursor", wintypes.HANDLE),
                ("hbrBackground", wintypes.HBRUSH),
                ("lpszMenuName", wintypes.LPCWSTR),
                ("lpszClassName", wintypes.LPCWSTR),
            ]

        user32.DefWindowProcW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.DefWindowProcW.restype = LRESULT
        user32.RegisterClassW.argtypes = [ctypes.POINTER(WNDCLASSW)]
        user32.RegisterClassW.restype = wintypes.ATOM
        user32.CreateWindowExW.argtypes = [
            wintypes.DWORD,
            wintypes.LPCWSTR,
            wintypes.LPCWSTR,
            wintypes.DWORD,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            wintypes.HMENU,
            wintypes.HINSTANCE,
            wintypes.LPVOID,
        ]
        user32.CreateWindowExW.restype = wintypes.HWND
        kernel32.GetModuleHandleW.argtypes = [wintypes.LPCWSTR]
        kernel32.GetModuleHandleW.restype = wintypes.HINSTANCE
        user32.LoadImageW.argtypes = [
            wintypes.HINSTANCE,
            wintypes.LPCWSTR,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.UINT,
        ]
        user32.LoadImageW.restype = wintypes.HANDLE
        shell32.Shell_NotifyIconW.argtypes = [wintypes.DWORD, ctypes.c_void_p]
        shell32.Shell_NotifyIconW.restype = wintypes.BOOL
        user32.DestroyIcon.argtypes = [wintypes.HICON]
        user32.DestroyIcon.restype = wintypes.BOOL
        user32.DestroyWindow.argtypes = [wintypes.HWND]
        user32.DestroyWindow.restype = wintypes.BOOL

        self._user32 = user32
        self._shell32 = shell32
        self._kernel32 = kernel32
        self._NOTIFYICONDATAW = _win_nid_class()

        IMAGE_ICON = 1
        LR_LOADFROMFILE = 0x0010
        LR_DEFAULTSIZE = 0x0040
        ico = _ROOT / "icon.ico"
        hicon = None
        if ico.exists():
            hicon = user32.LoadImageW(None, str(ico), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
        if not hicon:
            png = _ROOT / "icon.png"
            if png.exists():
                try:
                    from PIL import Image

                    tmp = Path(os.environ.get("TEMP") or str(_ROOT)) / "ud_series_watch.ico"
                    Image.open(png).convert("RGBA").resize((32, 32)).save(
                        str(tmp), format="ICO", sizes=[(16, 16), (32, 32)]
                    )
                    hicon = user32.LoadImageW(None, str(tmp), IMAGE_ICON, 0, 0, LR_LOADFROMFILE | LR_DEFAULTSIZE)
                except Exception as e:
                    _log(f"ICO aus PNG: {e}")
        if not hicon:
            _log("Kein Tray-Icon ladbar (icon.ico/png).")
            return False
        self.hicon = hicon

        def _wndproc(hwnd, msg, wparam, lparam):
            if msg == _WM_TRAYICON:
                event = int(lparam) & 0xFFFF
                if event in (_WM_RBUTTONUP, _WM_CONTEXTMENU):
                    try:
                        self.on_right_click()
                    except Exception as e:
                        _log(f"Tray Rechtsklick: {e}")
                    return 0
                if event in (_WM_LBUTTONUP, _WM_LBUTTONDBLCLK, _NIN_SELECT, _NIN_KEYSELECT):
                    try:
                        self.on_left_click()
                    except Exception as e:
                        _log(f"Tray Linksklick: {e}")
                    return 0
            return user32.DefWindowProcW(hwnd, msg, wparam, lparam)

        self._wndproc = WNDPROC(_wndproc)
        cls_name = "UDSeriesWatchTray"
        wc = WNDCLASSW()
        wc.style = 0
        wc.lpfnWndProc = self._wndproc
        wc.cbClsExtra = 0
        wc.cbWndExtra = 0
        wc.hInstance = kernel32.GetModuleHandleW(None)
        wc.hIcon = None
        wc.hCursor = None
        wc.hbrBackground = None
        wc.lpszMenuName = None
        wc.lpszClassName = cls_name
        self._hinstance = wc.hInstance
        atom = user32.RegisterClassW(ctypes.byref(wc))
        if not atom:
            err = ctypes.get_last_error()
            if err not in (1410,):  # already registered
                _log(f"RegisterClassW fehlgeschlagen: {err}")
                return False
        self._class_atom = atom
        WS_POPUP = 0x80000000
        hwnd = user32.CreateWindowExW(
            0,
            cls_name,
            "UD Series Watch",
            WS_POPUP,
            0,
            0,
            1,
            1,
            None,
            None,
            self._hinstance,
            None,
        )
        if not hwnd:
            _log(f"CreateWindowExW fehlgeschlagen: {ctypes.get_last_error()}")
            return False
        try:
            user32.ShowWindow.argtypes = [wintypes.HWND, ctypes.c_int]
            user32.ShowWindow.restype = wintypes.BOOL
            user32.ShowWindow(hwnd, 0)
        except Exception:
            pass
        self.hwnd = hwnd
        ok_add = self._notify(_NIM_ADD, "Serien-Wächter")
        err = ctypes.get_last_error()
        if not ok_add:
            _log(f"NIM_ADD fehlgeschlagen GetLastError={err}.")
            return False
        self._added = True
        nid = self._NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(self._NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = self._uid
        nid.uVersion = _NOTIFYICON_VERSION_4
        self._shell32.Shell_NotifyIconW(_NIM_SETVERSION, ctypes.byref(nid))
        time.sleep(0.3)
        windows_promote_notify_icon()
        _log(f"Natives Windows-Tray-Icon hinzugefügt (GetLastError={err}).")
        return True

    def _notify(self, action: int, tip: str) -> bool:
        import ctypes

        nid = self._NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(self._NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = self._uid
        nid.uFlags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP | _NIF_SHOWTIP
        nid.uCallbackMessage = _WM_TRAYICON
        nid.hIcon = self.hicon
        nid.szTip = (tip or "Serien-Wächter")[:127]
        return bool(self._shell32.Shell_NotifyIconW(action, ctypes.byref(nid)))

    def set_tooltip(self, tip: str) -> None:
        if self._added:
            try:
                self._notify(_NIM_MODIFY, tip)
            except Exception:
                pass

    def start_message_loop_background(self) -> None:
        import ctypes
        from ctypes import wintypes

        user32 = self._user32
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]

        def loop():
            msg = wintypes.MSG()
            while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
                user32.TranslateMessage(ctypes.byref(msg))
                user32.DispatchMessageW(ctypes.byref(msg))

        threading.Thread(target=loop, name="ud-tray-msg", daemon=True).start()

    def stop(self) -> None:
        if not self._added:
            return
        try:
            self._notify(_NIM_DELETE, "")
        except Exception:
            pass
        self._added = False
        try:
            if self.hwnd:
                self._user32.DestroyWindow(self.hwnd)
        except Exception:
            pass
        try:
            if self.hicon:
                self._user32.DestroyIcon(self.hicon)
        except Exception:
            pass


def install_login_autostart() -> bool:
    """Wächter beim Anmelden starten: Windows (Run), macOS (LaunchAgent), Linux (autostart.desktop)."""
    argv = get_tray_launch_argv()
    try:
        if sys.platform == "win32":
            import winreg
            cmd = _quote_argv(argv)
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            winreg.SetValueEx(key, "UniversalDownloaderSeriesWatch", 0, winreg.REG_SZ, cmd)
            winreg.CloseKey(key)
            _log(f"Autostart (Windows Run): {cmd}")
            return True
        if sys.platform == "darwin":
            agents = Path.home() / "Library" / "LaunchAgents"
            agents.mkdir(parents=True, exist_ok=True)
            plist = agents / "de.plertanix.universal-downloader.series-watch.plist"
            args_xml = "".join(f"    <string>{a}</string>\n" for a in argv)
            plist.write_text(
                '<?xml version="1.0" encoding="UTF-8"?>\n'
                '<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" '
                '"http://www.apple.com/DTDs/PropertyList-1.0.dtd">\n'
                '<plist version="1.0"><dict>\n'
                "  <key>Label</key>\n"
                "  <string>de.plertanix.universal-downloader.series-watch</string>\n"
                "  <key>RunAtLoad</key><true/>\n"
                "  <key>KeepAlive</key><false/>\n"
                "  <key>ProgramArguments</key>\n  <array>\n"
                f"{args_xml}"
                "  </array>\n</dict></plist>\n",
                encoding="utf-8",
            )
            uid = os.getuid()
            label = "de.plertanix.universal-downloader.series-watch"
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}", label],
                capture_output=True,
                timeout=5,
                check=False,
            )
            subprocess.run(
                ["launchctl", "bootstrap", f"gui/{uid}", str(plist)],
                capture_output=True,
                timeout=5,
                check=False,
            )
            _log(f"Autostart (macOS LaunchAgent): {plist}")
            return True
        # Linux / andere Unix
        from path_helper import user_home
        auto_dir = user_home() / ".config" / "autostart"
        auto_dir.mkdir(parents=True, exist_ok=True)
        desktop = auto_dir / "universal-downloader-series-watch.desktop"
        exec_cmd = _quote_argv(argv)
        icon = _ROOT / "icon.png"
        icon_line = f"Icon={icon}\n" if icon.is_file() else ""
        desktop.write_text(
            "[Desktop Entry]\n"
            "Type=Application\n"
            "Version=1.0\n"
            "Name=Universal Downloader Serien-Wächter\n"
            "Comment=Prüft Mediathek-Serien im Hintergrund\n"
            f"Exec={exec_cmd}\n"
            f"{icon_line}"
            "Terminal=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "Hidden=false\n",
            encoding="utf-8",
        )
        _log(f"Autostart (Linux .desktop): {desktop}")
        return True
    except Exception as e:
        _log(f"Autostart konnte nicht eingerichtet werden: {e}")
        return False


def remove_login_autostart() -> None:
    try:
        if sys.platform == "win32":
            import winreg
            key = winreg.OpenKey(
                winreg.HKEY_CURRENT_USER,
                r"Software\Microsoft\Windows\CurrentVersion\Run",
                0,
                winreg.KEY_SET_VALUE,
            )
            try:
                winreg.DeleteValue(key, "UniversalDownloaderSeriesWatch")
            except OSError:
                pass
            winreg.CloseKey(key)
            return
        if sys.platform == "darwin":
            plist = Path.home() / "Library" / "LaunchAgents" / "de.plertanix.universal-downloader.series-watch.plist"
            uid = os.getuid()
            subprocess.run(
                ["launchctl", "bootout", f"gui/{uid}", "de.plertanix.universal-downloader.series-watch"],
                capture_output=True,
                timeout=5,
                check=False,
            )
            if plist.exists():
                plist.unlink()
            return
        from path_helper import user_home
        desktop = user_home() / ".config" / "autostart" / "universal-downloader-series-watch.desktop"
        if desktop.exists():
            desktop.unlink()
    except Exception as e:
        _log(f"Autostart entfernen: {e}")


def run_check(base: Path, settings: Dict[str, Any]) -> List[Dict[str, Any]]:
    lock = series_watch.try_acquire_check_lock(base, "tray")
    if lock is None:
        _log("Prüfung übersprungen (Lock belegt).")
        return []
    try:
        series_watch.write_runtime_status(base, phase="checking")
        def on_err(name: str, err: str) -> None:
            _log(f"Fehler bei {name}: {err}")

        _state, notifications = series_watch.check_all(base, on_item_error=on_err)
        return notifications or []
    except Exception as e:
        _log(f"Prüfung fehlgeschlagen: {e}")
        return []
    finally:
        series_watch.release_check_lock(lock)
        st = series_watch.read_runtime_status(base)
        if st.get("phase") == "checking":
            series_watch.write_runtime_status(base, phase="idle")


class TrayApp:
    def __init__(self, base: Path, tk_root=None):
        self.base = Path(base)
        self._stop = threading.Event()
        self._last_run = 0.0
        self._icon = None
        self._win_notify: Optional[WinNotifyIcon] = None
        self._tk_root = tk_root
        self._owns_tk = False
        self._tk_menu = None
        self._check_thread: Optional[threading.Thread] = None
        self._base_icon = _load_base_icon()
        self._last_notifications: List[Dict[str, Any]] = []
        self._menu_lock = threading.Lock()
        self._pystray = None
        self._Item = None

    def _settings(self) -> Dict[str, Any]:
        return series_watch.load_app_settings(self.base)

    def _interval_seconds(self, settings: Dict[str, Any]) -> float:
        try:
            h = float(settings.get("series_watch_interval_hours", 6) or 6)
        except (TypeError, ValueError):
            h = 6.0
        return max(1.0, h) * 3600.0

    def _refresh_icon_and_menu(self) -> None:
        try:
            rt = series_watch.read_runtime_status(self.base)
            tip = self._tooltip(rt)
            if self._win_notify is not None:
                self._win_notify.set_tooltip(tip)
                return
            if not self._icon:
                return
            phase = rt.get("phase") or "idle"
            dl = rt.get("download") if isinstance(rt.get("download"), dict) else {}
            pct = float(dl.get("percent") or 0)
            has_new = bool(self._last_notifications) or bool(rt.get("new_alerts"))
            if phase == "downloading":
                mode = "downloading"
            elif has_new:
                mode = "new"
            else:
                mode = "idle"
            img = _icon_with_badge(self._base_icon, mode=mode, percent=pct)
            if img is not None:
                self._icon.icon = img
            self._icon.title = tip
            if hasattr(self._icon, "update_menu"):
                self._icon.update_menu()
        except Exception:
            pass

    def _tooltip(self, rt: Optional[Dict[str, Any]] = None) -> str:
        rt = rt or series_watch.read_runtime_status(self.base)
        phase = rt.get("phase") or "idle"
        if phase == "downloading":
            dl = rt.get("download") or {}
            title = _truncate(dl.get("title") or "Download", 36)
            pct = float(dl.get("percent") or 0)
            idx = dl.get("index") or 0
            total = dl.get("total") or 0
            return f"Serien-Wächter: {pct:.0f}% · {idx}/{total} · {title}"
        if phase == "checking":
            return "Serien-Wächter: prüft…"
        if self._last_notifications:
            n = sum(len(x.get("new_episodes") or []) for x in self._last_notifications)
            return f"Serien-Wächter: {n} neue Folge(n)"
        return "Serien-Wächter"

    def _open_folder(self, folder: Path) -> None:
        try:
            folder.mkdir(parents=True, exist_ok=True)
            if sys.platform == "darwin":
                subprocess.run(["open", str(folder)], check=False, timeout=5)
            elif sys.platform == "win32":
                os.startfile(str(folder))  # type: ignore[attr-defined]
            else:
                subprocess.run(["xdg-open", str(folder)], check=False, timeout=5)
        except Exception as e:
            _log(f"Ordner öffnen: {e}")

    def _open_video_folder(self, *_args) -> None:
        settings = self._settings()
        self._open_folder(Path(settings.get("default_video_path") or (self.base / "Video")))

    def _open_music_folder(self, *_args) -> None:
        settings = self._settings()
        self._open_folder(Path(settings.get("default_music_path") or (self.base / "Musik")))

    def open_main(self, *_args) -> None:
        ok = series_watch.open_main_app()
        if ok:
            _log("Hauptprogramm gestartet/aktiviert.")
            series_watch.desktop_notify("Serien-Wächter", "Hauptprogramm wird geöffnet…")
        else:
            _log("Hauptprogramm nicht gefunden.")
            series_watch.desktop_notify("Serien-Wächter", "Hauptprogramm nicht gefunden.")

    def cancel_download(self, *_args) -> None:
        series_watch.request_download_cancel(self.base)
        _log("Abbruch angefordert.")
        series_watch.desktop_notify("Serien-Wächter", "Download-Abbruch angefordert.")
        self._refresh_icon_and_menu()

    def clear_new_alerts(self, *_args) -> None:
        self._last_notifications = []
        series_watch.write_runtime_status(self.base, new_alerts=[])
        self._refresh_icon_and_menu()

    def do_check_now(self, *_args) -> None:
        if self._check_thread and self._check_thread.is_alive():
            _log("Prüfung/Download läuft bereits.")
            return

        def work():
            settings = self._settings()
            st = series_watch.load_state(self.base)
            if not (st.get("items") or []):
                _log("Keine überwachten Serien.")
                series_watch.desktop_notify("Serien-Wächter", "Keine Serien eingetragen.")
                return
            notifications = run_check(self.base, settings)
            self._last_run = time.time()
            self._handle_notifications(settings, notifications)
            if not notifications:
                series_watch.desktop_notify("Serien-Wächter", "Keine neuen Folgen.")
            self._refresh_icon_and_menu()

        self._check_thread = threading.Thread(target=work, daemon=True)
        self._check_thread.start()

    def _handle_notifications(self, settings: Dict[str, Any], notifications: List[Dict[str, Any]]) -> None:
        if not notifications:
            _log("Keine neuen Folgen.")
            series_watch.write_runtime_status(self.base, phase="idle", new_alerts=[])
            return

        self._last_notifications = list(notifications)
        alerts = []
        for n in notifications:
            alerts.append({
                "name": n.get("watch_name") or "",
                "count": len(n.get("new_episodes") or []),
                "is_new_season": bool(n.get("is_new_season")),
                "episodes": [
                    {"title": (ep.get("title") or "")[:80], "id": ep.get("id")}
                    for ep in (n.get("new_episodes") or [])[:12]
                ],
            })
        series_watch.write_runtime_status(self.base, new_alerts=alerts, phase="idle")
        self._refresh_icon_and_menu()

        auto_eps = series_watch.collect_auto_download_episodes(self.base, notifications, settings)
        downloaded_ok = 0
        downloaded_fail = 0

        if auto_eps:
            _log(f"Auto-Download: {len(auto_eps)} Folge(n)…")
            self._refresh_icon_and_menu()

            def on_prog(percent, status_line, meta):
                self._refresh_icon_and_menu()

            downloaded_ok, downloaded_fail = series_watch.download_episodes_headless(
                self.base,
                auto_eps,
                settings,
                log=_log,
                progress_callback=on_prog,
                should_cancel=lambda: series_watch.is_download_cancel_requested(self.base),
            )
            _log(f"Auto-Download fertig: {downloaded_ok} ok, {downloaded_fail} fehlgeschlagen.")
            # Nach Download: Alerts für erfolgreich geladene können bleiben bis Nutzer löscht
            self._refresh_icon_and_menu()

        for n in notifications:
            title, body = series_watch.format_notification_text(n)
            if auto_eps:
                n_count = len(n.get("new_episodes") or [])
                title = f"Auto-Download: {n.get('watch_name') or title}"
                body = (
                    f"{n_count} neue Folge(n) – Download: {downloaded_ok} ok / {downloaded_fail} Fehler.\n\n"
                    + body
                )
            try:
                series_watch.send_external_notifications(settings, title, body)
            except Exception as e:
                _log(f"Externe Benachrichtigung: {e}")
            if settings.get("series_notify_desktop", True):
                short = body[:400] + ("…" if len(body) > 400 else "")
                series_watch.desktop_notify(title[:120], short)
            _log(f"Meldung: {title}")

    def _loop(self) -> None:
        time.sleep(8)
        while not self._stop.is_set():
            settings = self._settings()
            # Icon/Menü bei laufendem Download aktualisieren
            rt = series_watch.read_runtime_status(self.base)
            if (rt.get("phase") or "") == "downloading":
                self._refresh_icon_and_menu()

            if settings.get("series_watch_enabled", False):
                st = series_watch.load_state(self.base)
                items = st.get("items") if isinstance(st, dict) else []
                interval = self._interval_seconds(settings)
                now = time.time()
                if items and (self._last_run <= 0 or (now - self._last_run) >= interval):
                    if not (self._check_thread and self._check_thread.is_alive()):
                        def work():
                            notifications = run_check(self.base, settings)
                            self._last_run = time.time()
                            self._handle_notifications(settings, notifications)
                            self._refresh_icon_and_menu()

                        self._check_thread = threading.Thread(target=work, daemon=True)
                        self._check_thread.start()
            self._stop.wait(5 if (rt.get("phase") == "downloading") else 30)

    def quit_app(self, icon=None, *_args) -> None:
        self._stop.set()
        try:
            series_watch.request_download_cancel(self.base)
        except Exception:
            pass
        if self._win_notify is not None:
            try:
                self._win_notify.stop()
            except Exception:
                pass
        if icon is not None:
            try:
                icon.stop()
            except Exception:
                pass
        elif self._icon is not None:
            try:
                self._icon.stop()
            except Exception:
                pass
        if self._owns_tk and self._tk_root is not None:
            try:
                self._tk_root.quit()
            except Exception:
                pass

    def _build_menu(self):
        Item = self._Item
        pystray = self._pystray
        rt = series_watch.read_runtime_status(self.base)
        phase = rt.get("phase") or "idle"
        dl = rt.get("download") if isinstance(rt.get("download"), dict) else {}
        pending = rt.get("pending") if isinstance(rt.get("pending"), list) else []
        alerts = rt.get("new_alerts") if isinstance(rt.get("new_alerts"), list) else []
        if not alerts and self._last_notifications:
            alerts = [
                {
                    "name": n.get("watch_name") or "",
                    "count": len(n.get("new_episodes") or []),
                    "is_new_season": bool(n.get("is_new_season")),
                    "episodes": [
                        {"title": (ep.get("title") or "")[:80]}
                        for ep in (n.get("new_episodes") or [])[:8]
                    ],
                }
                for n in self._last_notifications
            ]

        entries = []

        # Statuszeile
        if phase == "downloading" and dl:
            title = _truncate(dl.get("title") or "Download", 40)
            series = _truncate(dl.get("series") or "", 36)
            pct = float(dl.get("percent") or 0)
            idx = dl.get("index") or 0
            total = dl.get("total") or 0
            entries.append(Item(f"⬇ {idx}/{total}: {title}", None, enabled=False))
            if series:
                entries.append(Item(f"   Serie: {series}", None, enabled=False))
            entries.append(Item(f"   {_progress_bar(pct)}", None, enabled=False))
            entries.append(Item("⏹ Download abbrechen", self.cancel_download))
            if pending:
                entries.append(pystray.Menu.SEPARATOR)
                entries.append(Item(f"Warteschlange ({len(pending)})", None, enabled=False))
                for p in pending[:6]:
                    if not isinstance(p, dict):
                        continue
                    t = _truncate(p.get("title") or "…", 44)
                    entries.append(Item(f"  · {t}", None, enabled=False))
                if len(pending) > 6:
                    entries.append(Item(f"  … +{len(pending) - 6} weitere", None, enabled=False))
        elif phase == "checking":
            entries.append(Item("Prüfe Serien…", None, enabled=False))
        else:
            entries.append(Item("Bereit", None, enabled=False))

        # Neue Folgen
        entries.append(pystray.Menu.SEPARATOR)
        if alerts:
            entries.append(Item(f"Neue Folgen ({sum(int(a.get('count') or 0) for a in alerts if isinstance(a, dict))})", None, enabled=False))
            for a in alerts[:8]:
                if not isinstance(a, dict):
                    continue
                name = _truncate(a.get("name") or "Serie", 32)
                cnt = int(a.get("count") or 0)
                flag = "🆕 Staffel · " if a.get("is_new_season") else ""
                entries.append(Item(f"  {flag}{name} ({cnt})", None, enabled=False))
                for ep in (a.get("episodes") or [])[:3]:
                    if isinstance(ep, dict):
                        entries.append(Item(f"     · {_truncate(ep.get('title') or '', 40)}", None, enabled=False))
            entries.append(Item("Hinweise löschen", self.clear_new_alerts))
        else:
            entries.append(Item("Keine neuen Folgen", None, enabled=False))

        # Überwachte Serien (Kurzliste)
        try:
            state = series_watch.load_state(self.base)
            items = [it for it in (state.get("items") or []) if isinstance(it, dict)]
            if items:
                entries.append(pystray.Menu.SEPARATOR)
                entries.append(Item(f"Überwacht: {len(items)} Serie(n)", None, enabled=False))
                for it in items[:8]:
                    nm = _truncate((it.get("display_name") or it.get("playlist_title") or it.get("url") or "?"), 40)
                    ad = ""
                    if "auto_download" in it:
                        ad = " · Auto" if it.get("auto_download") else ""
                    elif self._settings().get("series_watch_auto_download"):
                        ad = " · Auto"
                    entries.append(Item(f"  ○ {nm}{ad}", None, enabled=False))
        except Exception:
            pass

        entries.append(pystray.Menu.SEPARATOR)
        entries.append(Item("Jetzt prüfen", self.do_check_now))
        entries.append(Item("Hauptprogramm öffnen", self.open_main))
        entries.append(Item("Video-Ordner öffnen", self._open_video_folder))
        entries.append(Item("Hörbuch-/Musik-Ordner öffnen", self._open_music_folder))
        entries.append(pystray.Menu.SEPARATOR)
        entries.append(Item("Beenden", self.quit_app))
        return entries

    def _create_icon(self) -> bool:
        if sys.platform == "win32" and self._create_windows_notify_icon():
            return True
        try:
            import pystray
            from pystray import MenuItem as Item
        except ImportError:
            _log("pystray fehlt. Installieren: pip install pystray")
            return False
        self._pystray = pystray
        self._Item = Item
        if self._base_icon is None:
            _log("Kein Icon (Pillow?).")
            return False
        menu = pystray.Menu(self._iter_menu_items)
        if sys.platform == "win32":
            try:
                import ctypes
                ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                    "UniversalDownloader.SeriesWatch.1.0"
                )
            except Exception:
                pass
        self._icon = pystray.Icon(
            "series_watch",
            _icon_with_badge(self._base_icon, mode="idle"),
            "Serien-Waechter",
            menu,
        )
        return True

    def _ensure_tk(self):
        if self._tk_root is not None:
            return self._tk_root
        import tkinter as tk

        existing = getattr(tk, "_default_root", None)
        if existing is not None:
            self._tk_root = existing
            self._owns_tk = False
            return existing
        self._tk_root = tk.Tk()
        self._tk_root.withdraw()
        self._owns_tk = True
        return self._tk_root

    def _create_windows_notify_icon(self) -> bool:
        try:
            import ctypes
            ctypes.windll.shell32.SetCurrentProcessExplicitAppUserModelID(
                "UniversalDownloader.SeriesWatch.1.0"
            )
        except Exception:
            pass
        try:
            self._ensure_tk()
        except Exception as e:
            _log(f"Tk für Tray-Menü: {e}")
        icon = WinNotifyIcon(self._on_win_left, self._on_win_right)
        if not icon.create():
            return False
        self._win_notify = icon
        icon.start_message_loop_background()
        return True

    def _on_win_left(self) -> None:
        self._schedule_tk(self.open_main)

    def _on_win_right(self) -> None:
        self._schedule_tk(self._show_tk_tray_menu)

    def _schedule_tk(self, fn) -> None:
        root = self._tk_root
        if root is not None:
            try:
                root.after(0, fn)
                return
            except Exception:
                pass
        try:
            fn()
        except Exception as e:
            _log(f"Tray-Aktion: {e}")

    def _show_tk_tray_menu(self) -> None:
        import tkinter as tk

        root = self._ensure_tk()
        if self._tk_menu is not None:
            try:
                self._tk_menu.destroy()
            except Exception:
                pass
        menu = tk.Menu(root, tearoff=0)
        self._tk_menu = menu
        rt = series_watch.read_runtime_status(self.base)
        menu.add_command(label=self._tooltip(rt), state="disabled")
        menu.add_separator()
        if rt.get("phase") == "downloading":
            menu.add_command(label="Download abbrechen", command=self.cancel_download)
            menu.add_separator()
        menu.add_command(label="Jetzt prüfen", command=self.do_check_now)
        menu.add_command(label="Hauptprogramm öffnen", command=self.open_main)
        menu.add_command(label="Video-Ordner öffnen", command=self._open_video_folder)
        menu.add_command(label="Hörbuch-/Musik-Ordner öffnen", command=self._open_music_folder)
        menu.add_separator()
        menu.add_command(label="Beenden", command=self.quit_app)
        try:
            import ctypes
            from ctypes import wintypes

            class POINT(ctypes.Structure):
                _fields_ = [("x", wintypes.LONG), ("y", wintypes.LONG)]

            pt = POINT()
            ctypes.windll.user32.GetCursorPos(ctypes.byref(pt))
            x, y = int(pt.x), int(pt.y)
        except Exception:
            x, y = 0, 0
        try:
            menu.tk_popup(x, y)
        finally:
            try:
                menu.grab_release()
            except Exception:
                pass

    def _on_icon_ready(self, icon) -> None:
        try:
            icon.visible = True
        except Exception:
            pass
        windows_promote_notify_icon()
        _log("Tray-Icon sichtbar gesetzt.")

    def run_tray(self) -> int:
        if not try_become_tray_instance(self.base):
            return 0
        if not self._create_icon():
            _log("Fallback: Hintergrund ohne Icon (Ctrl+C).")
            return self.run_headless()
        threading.Thread(target=self._loop, daemon=True).start()
        _log(f"Tray gestartet (Menüleiste/System-Tray). Basis: {self.base}")
        if self._win_notify is not None:
            if self._owns_tk and self._tk_root is not None:
                try:
                    self._tk_root.mainloop()
                except KeyboardInterrupt:
                    pass
                return 0
            try:
                while not self._stop.is_set():
                    time.sleep(0.5)
            except KeyboardInterrupt:
                pass
            return 0
        self._icon.run(setup=self._on_icon_ready)
        return 0

    def run_tray_detached(self) -> int:
        """Icon im aktuellen Prozess (GUI), ohne den Hauptthread zu blockieren."""
        if not self._create_icon():
            return 1
        threading.Thread(target=self._loop, daemon=True).start()
        _log(f"Tray (im Hauptprogramm) gestartet. Basis: {self.base}")
        if self._win_notify is not None:
            return 0
        self._icon.run_detached(setup=self._on_icon_ready)
        return 0

    def _iter_menu_items(self):
        """Für pystray: Iterable von MenuItems (wird beim Öffnen neu aufgebaut)."""
        return self._build_menu()


    def run_headless(self) -> int:
        _log(f"Headless-Modus. Basis: {self.base}")
        try:
            self._loop()
        except KeyboardInterrupt:
            _log("Beendet.")
        return 0


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description="Serien-Wächter Tray-Helper")
    parser.add_argument("--once", action="store_true", help="Einmal prüfen und beenden")
    parser.add_argument("--base", type=str, default="", help="App-Basisordner (optional)")
    parser.add_argument("--no-tray", action="store_true", help="Ohne Tray-Icon")
    parser.add_argument("--install-autostart", action="store_true", help="Beim Anmelden starten einrichten")
    parser.add_argument("--remove-autostart", action="store_true", help="Autostart entfernen")
    args = parser.parse_args(argv)

    if args.install_autostart:
        ok = install_login_autostart()
        return 0 if ok else 1
    if args.remove_autostart:
        remove_login_autostart()
        return 0

    if (
        sys.platform == "win32"
        and not getattr(sys, "frozen", False)
        and not args.once
        and not args.no_tray
    ):
        me = Path(sys.executable).name.lower()
        if me != "universoldownloadertray.exe":
            tray_exe = _windows_unique_pythonw()
            if Path(tray_exe).name.lower() == "universoldownloadertray.exe":
                new_argv = [tray_exe, str(_ROOT / "series_watch_tray.py"), *(argv or sys.argv[1:])]
                _log(f"Starte Tray über {tray_exe}")
                try:
                    subprocess.Popen(new_argv, close_fds=True)
                    return 0
                except Exception as e:
                    _log(f"Tray-EXE Start fehlgeschlagen: {e}")

    base = Path(args.base) if args.base else get_app_base_path()
    settings = series_watch.load_app_settings(base)

    if args.once:
        notifications = run_check(base, settings)
        app = TrayApp(base)
        app._handle_notifications(settings, notifications)
        return 0

    app = TrayApp(base)
    if args.no_tray or os.environ.get("SERIES_WATCH_NO_TRAY"):
        return app.run_headless()
    return app.run_tray()


if __name__ == "__main__":
    raise SystemExit(main())
