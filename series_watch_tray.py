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


def tray_instance_running(base: Path) -> bool:
    """True, wenn bereits ein anderer Serien-Wächter-Tray läuft."""
    path = Path(base) / "series_watch_tray.pid"
    try:
        if not path.exists():
            return False
        old = int((path.read_text(encoding="utf-8") or "0").strip().split()[0])
    except (ValueError, OSError):
        return False
    return bool(old and old != os.getpid() and _pid_running(old))


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
        try:
            path.unlink()
        except OSError:
            pass
    except Exception as e:
        _log(f"steal_tray_instance: {e}")


def _windows_base_pythonw() -> Path:
    """pythonw der echten Installation – nicht Scripts\\pythonw aus dem venv (braucht pyvenv.cfg)."""
    candidates: List[Path] = []
    base = Path(getattr(sys, "base_prefix", "") or sys.prefix)
    candidates.append(base / "pythonw.exe")
    exe = Path(sys.executable)
    same_dir = exe.with_name("pythonw.exe")
    if same_dir.is_file():
        candidates.append(same_dir)
    for p in candidates:
        if not p.is_file():
            continue
        # venv-Launcher: pyvenv.cfg liegt eine Ebene über Scripts\
        if p.parent.name.lower() == "scripts" and (p.parent.parent / "pyvenv.cfg").is_file():
            continue
        return p
    return candidates[0] if candidates else exe


def _windows_unique_pythonw() -> str:
    """Kopie von pythonw.exe (Basis-Python), eigener Name für den Infobereich."""
    src = _windows_base_pythonw()
    if not src.is_file():
        _log(f"Kein pythonw.exe unter {src}")
        return str(sys.executable)
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
    if sys.platform == "win32":
        return [_windows_unique_pythonw(), str(_ROOT / "series_watch_tray.py")]
    wrapper = Path("/usr/bin/universal-downloader")
    if sys.platform.startswith("linux") and wrapper.is_file():
        return [str(wrapper), "--series-watch-tray"]
    return [sys.executable, str(_ROOT / "series_watch_tray.py")]


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
_WM_APP_SHOW_MENU = 0x8000 + 22
_NIF_MESSAGE = 0x00000001
_NIF_ICON = 0x00000002
_NIF_TIP = 0x00000004
_NIF_GUID = 0x00000020
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
_WM_COMMAND = 0x0111
_WM_DESTROY = 0x0002
_NIN_SELECT = 0x0400
_NIN_KEYSELECT = 0x0401
_HWND_MESSAGE = -3
_ID_CANCEL = 10
_ID_CHECK = 11
_ID_OPEN = 12
_ID_VIDEO = 13
_ID_MUSIC = 14
_ID_QUIT = 15
_ID_CLEAR = 16


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
    """Shell_NotifyIcon + natives TrackPopupMenu (kein Tk im WNDPROC)."""

    def __init__(self, app: "TrayApp"):
        self.app = app
        self.hwnd = None
        self.hicon = None
        self._wndproc = None
        self._class_atom = None
        self._hinstance = None
        self._added = False
        self._uid = 1
        self._menu_open = False
        self._guid = None

    def create(self) -> bool:
        if sys.platform != "win32":
            return False
        import ctypes
        from ctypes import wintypes
        import uuid as _uuid

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

        class POINT(ctypes.Structure):
            _fields_ = [("x", ctypes.c_long), ("y", ctypes.c_long)]

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
        user32.PostMessageW.argtypes = [wintypes.HWND, wintypes.UINT, wintypes.WPARAM, wintypes.LPARAM]
        user32.PostMessageW.restype = wintypes.BOOL
        user32.GetCursorPos.argtypes = [ctypes.POINTER(POINT)]
        user32.GetCursorPos.restype = wintypes.BOOL
        user32.SetForegroundWindow.argtypes = [wintypes.HWND]
        user32.SetForegroundWindow.restype = wintypes.BOOL
        user32.CreatePopupMenu.argtypes = []
        user32.CreatePopupMenu.restype = wintypes.HMENU
        user32.AppendMenuW.argtypes = [wintypes.HMENU, wintypes.UINT, ctypes.c_size_t, wintypes.LPCWSTR]
        user32.AppendMenuW.restype = wintypes.BOOL
        user32.TrackPopupMenu.argtypes = [
            wintypes.HMENU,
            wintypes.UINT,
            ctypes.c_int,
            ctypes.c_int,
            ctypes.c_int,
            wintypes.HWND,
            ctypes.c_void_p,
        ]
        user32.TrackPopupMenu.restype = wintypes.BOOL
        user32.DestroyMenu.argtypes = [wintypes.HMENU]
        user32.DestroyMenu.restype = wintypes.BOOL
        user32.PostQuitMessage.argtypes = [ctypes.c_int]
        user32.PostQuitMessage.restype = None

        self._user32 = user32
        self._shell32 = shell32
        self._kernel32 = kernel32
        self._NOTIFYICONDATAW = _win_nid_class()
        self._POINT = POINT
        self._guid = (ctypes.c_ubyte * 16)(*_uuid.UUID("8e7c1f3a-2d94-4b61-9c0e-5a17f8b4d2c1").bytes_le)

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
            try:
                if msg == _WM_TRAYICON:
                    event = int(lparam) & 0xFFFF
                    if event in (
                        _WM_LBUTTONUP,
                        _WM_RBUTTONUP,
                        _WM_LBUTTONDBLCLK,
                        _WM_CONTEXTMENU,
                        _NIN_SELECT,
                        _NIN_KEYSELECT,
                    ):
                        user32.PostMessageW(hwnd, _WM_APP_SHOW_MENU, 0, 0)
                        return 0
                if msg == _WM_APP_SHOW_MENU:
                    try:
                        self._show_menu()
                    except Exception as e:
                        _log(f"Tray-Menü: {e}")
                    return 0
                if msg == _WM_DESTROY:
                    user32.PostQuitMessage(0)
                    return 0
            except Exception:
                pass
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
        # Geister-Icon aus abgestürztem Prozess entfernen, dann neu anlegen
        self._notify(_NIM_DELETE, "")
        ok_add = self._notify(_NIM_ADD, "Serien-Wächter")
        err = ctypes.get_last_error()
        if not ok_add:
            time.sleep(0.25)
            self._notify(_NIM_DELETE, "")
            ok_add = self._notify(_NIM_ADD, "Serien-Wächter")
            err = ctypes.get_last_error()
        if not ok_add:
            self._notify(_NIM_DELETE, "", use_guid=False)
            ok_add = self._notify(_NIM_ADD, "Serien-Wächter", use_guid=False)
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
        if self._guid is not None:
            nid.guidItem = self._guid
        self._shell32.Shell_NotifyIconW(_NIM_SETVERSION, ctypes.byref(nid))
        time.sleep(0.3)
        windows_promote_notify_icon()
        _log(f"Natives Windows-Tray-Icon hinzugefügt (GetLastError={err}).")
        return True

    def _notify(self, action: int, tip: str, use_guid: bool = True) -> bool:
        import ctypes

        nid = self._NOTIFYICONDATAW()
        nid.cbSize = ctypes.sizeof(self._NOTIFYICONDATAW)
        nid.hWnd = self.hwnd
        nid.uID = self._uid
        flags = _NIF_MESSAGE | _NIF_ICON | _NIF_TIP | _NIF_SHOWTIP
        if use_guid and self._guid is not None:
            flags |= _NIF_GUID
            nid.guidItem = self._guid
        nid.uFlags = flags
        nid.uCallbackMessage = _WM_TRAYICON
        nid.hIcon = self.hicon
        nid.szTip = (tip or "Serien-Wächter")[:127]
        return bool(self._shell32.Shell_NotifyIconW(action, ctypes.byref(nid)))

    def _show_menu(self) -> None:
        if self._menu_open or not self.hwnd:
            return
        import ctypes

        user32 = self._user32
        MF_STRING = 0x00000000
        MF_GRAYED = 0x00000001
        MF_SEPARATOR = 0x00000800
        TPM_RIGHTBUTTON = 0x0002
        TPM_BOTTOMALIGN = 0x0020
        TPM_RETURNCMD = 0x0100
        hmenu = user32.CreatePopupMenu()
        if not hmenu:
            return
        self._menu_open = True
        try:
            app = self.app
            rt = series_watch.read_runtime_status(app.base)
            status = app._tooltip(rt) or "Serien-Wächter"
            user32.AppendMenuW(hmenu, MF_STRING | MF_GRAYED, 0, status[:80])
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            if rt.get("phase") == "downloading":
                user32.AppendMenuW(hmenu, MF_STRING, _ID_CANCEL, "Download abbrechen")
                user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, _ID_CHECK, "Jetzt prüfen")
            user32.AppendMenuW(hmenu, MF_STRING, _ID_OPEN, "Hauptprogramm öffnen")
            user32.AppendMenuW(hmenu, MF_STRING, _ID_VIDEO, "Video-Ordner öffnen")
            user32.AppendMenuW(hmenu, MF_STRING, _ID_MUSIC, "Hörbuch-/Musik-Ordner öffnen")
            user32.AppendMenuW(hmenu, MF_SEPARATOR, 0, None)
            user32.AppendMenuW(hmenu, MF_STRING, _ID_QUIT, "Beenden")
            pt = self._POINT()
            user32.GetCursorPos(ctypes.byref(pt))
            user32.SetForegroundWindow(self.hwnd)
            cmd = int(
                user32.TrackPopupMenu(
                    hmenu,
                    TPM_RIGHTBUTTON | TPM_BOTTOMALIGN | TPM_RETURNCMD,
                    int(pt.x),
                    int(pt.y),
                    0,
                    self.hwnd,
                    None,
                )
            )
            user32.PostMessageW(self.hwnd, 0, 0, 0)  # WM_NULL, Menü zuverlässig schließen
            if cmd:
                _log(f"Tray-Menü Befehl {cmd}")
                self._dispatch(cmd)
        finally:
            try:
                user32.DestroyMenu(hmenu)
            except Exception:
                pass
            self._menu_open = False

    def _dispatch(self, cmd: int) -> None:
        app = self.app
        try:
            if cmd == _ID_CANCEL:
                app.cancel_download()
            elif cmd == _ID_CHECK:
                app.do_check_now()
            elif cmd == _ID_OPEN:
                app.open_main()
            elif cmd == _ID_VIDEO:
                app._open_video_folder()
            elif cmd == _ID_MUSIC:
                app._open_music_folder()
            elif cmd == _ID_CLEAR:
                app.clear_new_alerts()
            elif cmd == _ID_QUIT:
                app.quit_app()
        except Exception as e:
            _log(f"Tray-Menü Aktion {cmd}: {e}")

    def set_tooltip(self, tip: str) -> None:
        if self._added:
            try:
                self._notify(_NIM_MODIFY, tip)
            except Exception:
                pass

    def run_loop(self) -> None:
        """Message-Pump im Tray-Prozess (Hauptthread, ohne Tk)."""
        import ctypes
        from ctypes import wintypes

        user32 = self._user32
        user32.GetMessageW.argtypes = [ctypes.POINTER(wintypes.MSG), wintypes.HWND, wintypes.UINT, wintypes.UINT]
        user32.GetMessageW.restype = ctypes.c_int
        user32.TranslateMessage.argtypes = [ctypes.POINTER(wintypes.MSG)]
        user32.DispatchMessageW.argtypes = [ctypes.POINTER(wintypes.MSG)]
        msg = wintypes.MSG()
        while user32.GetMessageW(ctypes.byref(msg), None, 0, 0) > 0:
            user32.TranslateMessage(ctypes.byref(msg))
            user32.DispatchMessageW(ctypes.byref(msg))

    def stop(self) -> None:
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
        self.hwnd = None
        try:
            if self.hicon:
                self._user32.DestroyIcon(self.hicon)
        except Exception:
            pass
        try:
            self._user32.PostQuitMessage(0)
        except Exception:
            pass


def _ensure_linux_gi() -> bool:
    """venv hat oft kein PyGObject – System-gi nachladen (Cinnamon/XApp)."""
    if not sys.platform.startswith("linux"):
        return False
    try:
        import gi  # noqa: F401
        return True
    except ImportError:
        pass
    extra = [
        "/usr/lib/python3/dist-packages",
        f"/usr/lib/python{sys.version_info.major}.{sys.version_info.minor}/dist-packages",
    ]
    for p in extra:
        gi_dir = Path(p) / "gi"
        if gi_dir.is_dir() and p not in sys.path:
            sys.path.append(p)
    try:
        import gi  # noqa: F401
        return True
    except ImportError:
        return False


def _linux_icon_path() -> str:
    """Kleine PNG für Tray (1024px-icon.png blendet Cinnamon aus)."""
    for p in (
        Path("/usr/share/icons/hicolor/48x48/apps/universal-downloader.png"),
        Path("/usr/share/icons/hicolor/64x64/apps/universal-downloader.png"),
        _ROOT / "icon.png",
        Path("/usr/share/pixmaps/universal-downloader.png"),
    ):
        if p.is_file():
            try:
                from PIL import Image
                w, h = Image.open(p).size
                if max(w, h) > 128:
                    continue
            except Exception:
                pass
            return str(p)
    return ""


def _linux_icon_name() -> str:
    return "universal-downloader"


class LinuxStatusIcon:
    """Cinnamon/Mint: XApp-Statusicon (Leiste rechts). Fallback: Ayatana AppIndicator."""

    def __init__(self, app: "TrayApp"):
        self.app = app
        self._xapp = None
        self._gtk_status = None
        self._indicator = None
        self._menu = None
        self._loop = None
        self._Gtk = None
        self._GLib = None

    def create(self) -> bool:
        if not _ensure_linux_gi():
            _log("PyGObject (gi) fehlt – kein Cinnamon-Tray.")
            return False
        import gi

        try:
            gi.require_version("Gtk", "3.0")
            from gi.repository import GLib, Gtk
        except Exception as e:
            _log(f"Gtk3 für Tray nicht ladbar: {e}")
            return False
        self._Gtk = Gtk
        self._GLib = GLib
        try:
            Gtk.init_check()
        except Exception:
            pass

        icon_path = _linux_icon_path()
        icon_name = _linux_icon_name()
        try:
            theme = Gtk.IconTheme.get_default()
            if theme is None or theme.lookup_icon(icon_name, 24, 0) is None:
                icon_name = icon_path or "video-x-generic"
        except Exception:
            icon_name = icon_path or icon_name

        # Cinnamon: XApp-Statusicon sitzt in der Infoleiste rechts (nicht Windows-Taskleiste).
        xapp_ok = False
        try:
            gi.require_version("XApp", "1.0")
            from gi.repository import XApp

            try:
                si = XApp.StatusIcon.new_with_name("UniversalDownloader")
            except Exception:
                si = XApp.StatusIcon()
            si.set_name("Serien-Wächter")
            si.set_icon_name(icon_name)
            si.set_tooltip_text("Serien-Wächter")
            si.set_visible(True)
            self._xapp = si
            self._rebuild_menu()
            xapp_ok = True
            _log(f"Linux-Tray: XApp.StatusIcon ({icon_name})")
        except Exception as e:
            _log(f"XApp.StatusIcon nicht verfügbar: {e}")

        if not xapp_ok:
            try:
                sti = Gtk.StatusIcon()
                if icon_path:
                    sti.set_from_file(icon_path)
                else:
                    sti.set_from_icon_name(icon_name)
                sti.set_title("Serien-Wächter")
                sti.set_tooltip_text("Serien-Wächter")
                sti.set_visible(True)
                sti.connect("activate", lambda *_: self.app.open_main())
                sti.connect("popup-menu", self._on_gtk_popup)
                self._gtk_status = sti
                self._loop = GLib.MainLoop()
                _log(f"Linux-Tray: Gtk.StatusIcon ({icon_path or icon_name})")
                return True
            except Exception as e:
                _log(f"Gtk.StatusIcon nicht verfügbar: {e}")

        if not xapp_ok:
            AppIndicator = None
            try:
                gi.require_version("AyatanaAppIndicator3", "0.1")
                from gi.repository import AyatanaAppIndicator3 as AppIndicator
            except Exception:
                try:
                    gi.require_version("AppIndicator3", "0.1")
                    from gi.repository import AppIndicator3 as AppIndicator
                except Exception as e:
                    _log(f"AppIndicator nicht verfügbar: {e}")
                    AppIndicator = None
            if AppIndicator is None:
                return False
            category = AppIndicator.IndicatorCategory.APPLICATION_STATUS
            if icon_path:
                ind = AppIndicator.Indicator.new_with_path(
                    "universal-downloader-series-watch",
                    Path(icon_path).stem,
                    category,
                    str(Path(icon_path).parent),
                )
            else:
                ind = AppIndicator.Indicator.new(
                    "universal-downloader-series-watch",
                    icon_name,
                    category,
                )
            ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
            ind.set_title("Serien-Wächter")
            self._indicator = ind
            self._rebuild_menu()
            _log(f"Linux-Tray: AppIndicator ({icon_path or icon_name})")

        self._loop = GLib.MainLoop()
        return True

    def _on_gtk_popup(self, icon, button, time) -> None:
        Gtk = self._Gtk
        self._rebuild_menu()
        menu = self._menu
        if menu is None or Gtk is None:
            return
        try:
            menu.popup(None, None, Gtk.StatusIcon.position_menu, icon, button, time)
        except Exception:
            try:
                menu.popup_at_pointer(None)
            except Exception as e:
                _log(f"Linux-Tray Menü: {e}")

    def _on_xapp_activate(self, *args) -> None:
        btn = 1
        if len(args) >= 2:
            try:
                btn = int(args[1])
            except (TypeError, ValueError):
                btn = 1
        if btn == 1:
            self.app.open_main()
        else:
            self._popup_menu()

    def _popup_menu(self) -> None:
        menu = self._menu
        Gtk = self._Gtk
        if menu is None or Gtk is None:
            return
        try:
            menu.popup_at_pointer(None)
        except Exception:
            try:
                menu.popup(None, None, None, None, 0, Gtk.get_current_event_time())
            except Exception as e:
                _log(f"Linux-Tray Menü: {e}")

    def _rebuild_menu(self) -> None:
        Gtk = self._Gtk
        if Gtk is None:
            return
        menu = Gtk.Menu()
        rt = series_watch.read_runtime_status(self.app.base)
        tip = self.app._tooltip(rt)
        head = Gtk.MenuItem.new_with_label(tip[:80] or "Serien-Wächter")
        head.set_sensitive(False)
        menu.append(head)
        menu.append(Gtk.SeparatorMenuItem())
        if (rt.get("phase") or "") == "downloading":
            item = Gtk.MenuItem.new_with_label("Download abbrechen")
            item.connect("activate", lambda *_: self.app.cancel_download())
            menu.append(item)
            menu.append(Gtk.SeparatorMenuItem())
        rows = (
            ("Jetzt prüfen", self.app.do_check_now),
            ("Hauptprogramm öffnen", self.app.open_main),
            ("Video-Ordner öffnen", self.app._open_video_folder),
            ("Hörbuch-/Musik-Ordner öffnen", self.app._open_music_folder),
        )
        for label, cb in rows:
            item = Gtk.MenuItem.new_with_label(label)
            item.connect("activate", lambda _w, fn=cb: fn())
            menu.append(item)
        menu.append(Gtk.SeparatorMenuItem())
        quit_item = Gtk.MenuItem.new_with_label("Beenden")
        quit_item.connect("activate", lambda *_: self.app.quit_app())
        menu.append(quit_item)
        menu.show_all()
        self._menu = menu
        if self._xapp is not None:
            try:
                self._xapp.set_primary_menu(menu)
            except Exception:
                pass
            try:
                self._xapp.set_secondary_menu(menu)
            except Exception:
                pass
        if self._indicator is not None:
            try:
                self._indicator.set_menu(menu)
            except Exception as e:
                _log(f"AppIndicator set_menu: {e}")

    def refresh(self) -> bool:
        try:
            tip = self.app._tooltip()
            if self._gtk_status is not None:
                self._gtk_status.set_tooltip_text(tip)
            if self._xapp is not None:
                self._xapp.set_tooltip_text(tip)
            self._rebuild_menu()
        except Exception as e:
            _log(f"Linux-Tray Refresh: {e}")
        return False

    def run(self) -> None:
        if self._loop is None:
            return
        try:
            self._loop.run()
        except KeyboardInterrupt:
            pass

    def stop(self) -> None:
        loop = self._loop
        glib = self._GLib
        if loop is None:
            return
        try:
            if glib is not None:
                glib.idle_add(loop.quit)
            else:
                loop.quit()
        except Exception:
            pass
        try:
            if self._gtk_status is not None:
                self._gtk_status.set_visible(False)
        except Exception:
            pass
        try:
            if self._xapp is not None:
                self._xapp.set_visible(False)
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
            "StartupNotify=false\n"
            "X-GNOME-Autostart-enabled=true\n"
            "X-GNOME-Autostart-Delay=3\n"
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
        self._linux_status: Optional[LinuxStatusIcon] = None
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
            if self._linux_status is not None:
                glib = self._linux_status._GLib
                if glib is not None:
                    glib.idle_add(self._linux_status.refresh)
                else:
                    self._linux_status.refresh()
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
        if self._linux_status is not None:
            try:
                self._linux_status.stop()
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
        if sys.platform.startswith("linux") and self._create_linux_status_icon():
            return True
        if sys.platform.startswith("linux"):
            os.environ.setdefault("PYSTRAY_BACKEND", "xorg")
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
        icon = WinNotifyIcon(self)
        if not icon.create():
            return False
        self._win_notify = icon
        return True

    def _create_linux_status_icon(self) -> bool:
        icon = LinuxStatusIcon(self)
        if not icon.create():
            return False
        self._linux_status = icon
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
            try:
                self._win_notify.run_loop()
            except KeyboardInterrupt:
                pass
            return 0
        if self._linux_status is not None:
            _log("Tray-Icon sichtbar gesetzt.")
            self._linux_status.run()
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
        if self._linux_status is not None:
            threading.Thread(target=self._linux_status.run, daemon=True).start()
            _log("Tray-Icon sichtbar gesetzt.")
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
    if not settings.get("series_watch_tray_enabled", True):
        _log("Serien-Wächter in den Einstellungen deaktiviert – kein Tray.")
        remove_login_autostart()
        return 0

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
