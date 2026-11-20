"""Lädt Plugins aus dem Projektordner und aus dem Datenordner der App."""

import importlib.util
import shutil
import sys
import traceback
from datetime import datetime
from pathlib import Path


def plugin_directories():
    """Projekt-Plugins und der beschreibbare Ordner neben den Downloads."""
    folders = []
    source = Path(__file__).resolve().parent / "plugins"
    bundled = Path(getattr(sys, "_MEIPASS", "")) / "plugins"
    for folder in (source, bundled):
        if folder.is_dir() and folder not in folders:
            folders.append(folder)
    try:
        from path_helper import get_app_base_path
        user_folder = get_app_base_path() / "plugins"
        user_folder.mkdir(parents=True, exist_ok=True)
        if user_folder not in folders:
            folders.append(user_folder)
        _copy_example(folders[0] if folders else source, user_folder)
    except Exception:
        pass
    return folders


def _copy_example(source_folder: Path, user_folder: Path):
    example = source_folder / "beispiel.py"
    target = user_folder / "beispiel.py"
    if not example.is_file():
        return
    if target.exists():
        try:
            current = target.read_text(encoding="utf-8")
        except Exception:
            return
        if 'name = "Beispiel"' not in current or "vorlage 5" in current:
            return
    shutil.copy2(example, target)


_loaded = None
_loaded_meta = []
_reports = []
_log_lines = []
_ui = {}
_log_plugin = ""
_seq = 0


def plugin_log(message: str, plugin_name: str | None = None) -> None:
    """Merkt eine Zeile für das Plugin-Fenster in den Einstellungen."""
    name = _log_plugin if plugin_name is None else plugin_name
    stamp = datetime.now().strftime("%H:%M:%S")
    _log_lines.append({"t": stamp, "plugin": name or "", "text": str(message)})
    if len(_log_lines) > 500:
        del _log_lines[:200]


def plugin_overview():
    """Liste der Plugins und das bisherige Log. Lädt die Plugins, falls noch nicht geschehen."""
    load_plugins()
    return _with_freshness(), list(_log_lines)


def _file_sig(path: Path):
    try:
        st = path.stat()
    except OSError:
        return None
    return (st.st_mtime_ns, st.st_size)


def _plugin_files():
    """Dateiname ohne Endung → die Datei, die wirklich gilt. Der Datenordner gewinnt."""
    chosen = {}
    for folder in plugin_directories():
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            chosen[path.stem] = path
    return chosen


def _with_freshness():
    """Markiert Dateien, die seit dem Laden neu, geändert oder weg sind."""
    current = _plugin_files()
    shown = []
    seen = set()
    for report in _reports:
        item = dict(report)
        path = Path(item["path"])
        winner = current.get(path.stem)
        if not path.is_file() or winner is None:
            item["anzeige"] = "entfernt"
        elif winner != path:
            item["anzeige"] = item.get("status") or "bereit"
        elif _file_sig(path) != item.get("signature"):
            item["anzeige"] = "geändert"
            item["detail"] = item.get("detail") or "Datei geändert. Neu laden übernimmt sie."
        else:
            item["anzeige"] = item.get("status") or "bereit"
        shown.append(item)
        seen.add(path.stem)
    for stem, path in current.items():
        if stem in seen:
            continue
        shown.append({
            "file": path.name,
            "path": str(path),
            "name": stem,
            "status": "neu",
            "anzeige": "neu",
            "detail": "Neue Datei. Neu laden übernimmt sie.",
            "signature": None,
        })
    return shown


def load_plugins():
    """Lädt alle Plugin-Dateien. Gleicher Name im Datenordner ersetzt die Vorlage."""
    global _loaded, _loaded_meta, _reports
    if _loaded is not None:
        return _loaded
    found = {}
    reports = []
    meta = []
    for folder in plugin_directories():
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            plugin, error = _load_file(path)
            if plugin is None:
                reports = [item for item in reports if Path(item["path"]).stem != path.stem]
                reports.append({
                    "file": path.name,
                    "path": str(path),
                    "name": path.stem,
                    "status": "fehler",
                    "detail": error or "nicht geladen",
                    "signature": _file_sig(path),
                })
                plugin_log(f"{path.name}: {error or 'nicht geladen'}", path.stem)
                continue
            found[path.stem] = plugin
            reports = [item for item in reports if Path(item["path"]).stem != path.stem]
            meta = [item for item in meta if Path(item["path"]).stem != path.stem]
            reports.append({
                "file": path.name,
                "path": str(path),
                "name": getattr(plugin, "name", path.stem),
                "status": "bereit",
                "detail": "",
                "signature": _file_sig(path),
            })
            meta.append({"plugin": plugin, "path": str(path)})
    _reports = reports
    _loaded_meta = meta
    _loaded = list(found.values())
    if not reports:
        plugin_log("Keine Plugin-Dateien gefunden.")
    return _loaded


def _load_file(path: Path):
    global _seq
    _seq += 1
    try:
        spec = importlib.util.spec_from_file_location(f"ud_plugin_{path.stem}_{_seq}", path)
        if spec is None or spec.loader is None:
            return None, "Python konnte die Datei nicht lesen"
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin_type = getattr(module, "Plugin", None)
        if not isinstance(plugin_type, type):
            return None, "keine Klasse Plugin"
        plugin = plugin_type()
        has_hook = any(callable(getattr(plugin, name, None)) for name in ("setup", "matches", "download"))
        if not has_hook:
            return None, "keine Funktion setup, matches oder download"
        return plugin, ""
    except Exception as exc:
        detail = "".join(traceback.format_exception_only(type(exc), exc)).strip()
        return None, detail or str(exc)


class PluginHost:
    """Was ein Plugin am fertigen Programm ändern darf."""

    def __init__(self, app):
        self.app = app
        self._current_path = ""

    def _track(self, widget):
        path = self._current_path
        if not path or widget is None:
            return
        _ui.setdefault(path, {"widgets": [], "wraps": []})["widgets"].append(widget)

    def places(self):
        """Namen der Stellen, an denen Knöpfe sitzen. Zum Beispiel kopf und audible."""
        return list(getattr(self.app, "plugin_areas", {}))

    def _place(self, place):
        if place is None:
            return getattr(self.app, "header_buttons", None)
        areas = getattr(self.app, "plugin_areas", {})
        if place in areas:
            return areas[place]
        if hasattr(place, "winfo_children"):
            return place
        return None

    def add_button(self, text, command, place="kopf"):
        """Neuer Knopf. place ist kopf, audible oder audible_aktionen."""
        import tkinter.ttk as ttk
        target = self._place(place)
        if target is None:
            self.meldung(f"Plugin-Knopf „{text}“: die Stelle „{place}“ gibt es nicht.")
            return None
        def safe_command():
            try:
                command()
            except Exception as exc:
                self.meldung(f"Plugin-Knopf „{text}“: {exc}")

        button = ttk.Button(target, text=text, command=safe_command)
        self._track(button)
        plugin_log(f"Knopf „{text}“ an der Stelle „{place}“.")
        if place == "audible_aktionen":
            button.pack(fill="x", pady=(0, 6))
        else:
            button.pack(side="left", padx=2)
        return button

    def remove_button(self, text, place=None):
        """Entfernt einen Knopf mit diesem Text. Ohne place in allen Stellen."""
        if place is None:
            frames = list(getattr(self.app, "plugin_areas", {}).values())
        else:
            found = self._place(place)
            frames = [found] if found is not None else []
        removed = 0
        for frame in frames:
            for child in list(frame.winfo_children()):
                try:
                    if str(child.cget("text")) == text:
                        child.destroy()
                        removed += 1
                except Exception:
                    continue
        return removed

    def add_tab(self, title, after=None):
        """Neuer Tab. after ist ein Stück vom Namen eines vorhandenen Tabs, zum Beispiel Video."""
        import tkinter.ttk as ttk
        frame = ttk.Frame(self.app.notebook, padding=10)
        self.app.notebook.add(frame, text=title)
        self._track(frame)
        if not after:
            return frame
        tabs = list(self.app.notebook.tabs())
        for index, tab_id in enumerate(tabs):
            label = self.app.notebook.tab(tab_id, "text")
            if after.lower() in label.lower() and tab_id != str(frame):
                self.app.notebook.insert(index + 1, frame)
                break
        return frame

    def wrap(self, method_name, wrapper):
        """Ersetzt eine vorhandene Funktion. wrapper bekommt die alte Funktion und deren Argumente."""
        original = getattr(self.app, method_name)

        def wrapped(*args, **kwargs):
            return wrapper(original, *args, **kwargs)

        setattr(self.app, method_name, wrapped)
        path = self._current_path
        if path:
            bucket = _ui.setdefault(path, {"widgets": [], "wraps": []})
            if not any(name == method_name for name, _old in bucket["wraps"]):
                bucket["wraps"].append((method_name, original))
        return original

    def style(self):
        import tkinter.ttk as ttk
        return ttk.Style(self.app.root)

    def login(self, service):
        """Prüft genau diesen Login. service ist der Name des Dienstes.

        Zum Beispiel login("audible"), login("youtube"), login("orf") oder login("deezer").
        True heißt: dieser Dienst ist angemeldet.
        """
        status = self.app.account_status(service)
        return bool(status.get("signed_in"))

    def signed_in(self, service):
        """Gleicher Check wie login(service)."""
        return self.login(service)

    def function(self, name):
        """True, wenn ein Plugin diese Funktion hinterlegt hat.

        Zum Beispiel function("activation_bytes") vor einem Audible-Download.
        """
        for plugin in load_plugins():
            method = getattr(plugin, name, None)
            if callable(method):
                return True
        return False

    def audible_books_loaded(self):
        """True, wenn die Audible-Bücher in dieser Sitzung schon geladen sind."""
        status = self.app.account_status("audible")
        return bool(status.get("books_loaded"))

    def meldung(self, message):
        """Schreibt eine Zeile ins Programmfenster und ins Plugin-Log."""
        text = str(message)
        plugin_log(text)
        if hasattr(self.app, "log"):
            self.app.log(text)

    def log(self, message):
        self.meldung(message)


def ask_plugins(app, method_name):
    """Fragt jedes Plugin, das die Methode hat. Rückgabe ist die Liste der Antworten."""
    answers = []
    for plugin in load_plugins():
        method = getattr(plugin, method_name, None)
        if not callable(method):
            continue
        try:
            answers.append(method(app))
        except Exception as exc:
            name = getattr(plugin, "name", plugin.__class__.__name__)
            detail = traceback.format_exc().strip()
            plugin_log(f"{name}.{method_name}:\n{detail}")
            _mark(plugin, "fehler", str(exc))
    return answers


def activate_plugins(app):
    host = PluginHost(app)
    app.plugin_host = host
    load_plugins()
    _start_loaded(host)


def reload_plugins(app):
    """Liest die Plugin-Dateien neu und baut ihre Knöpfe neu auf. Die App bleibt offen."""
    host = getattr(app, "plugin_host", None) or PluginHost(app)
    app.plugin_host = host
    _drop_all_ui(app)
    global _loaded
    _loaded = None
    plugin_log("Plugins werden neu geladen.", "")
    load_plugins()
    _start_loaded(host)
    plugin_log("Neu laden fertig.", "")
    return plugin_overview()


def _start_loaded(host):
    global _log_plugin
    for item in _loaded_meta:
        plugin = item["plugin"]
        path = item["path"]
        setup = getattr(plugin, "setup", None)
        name = getattr(plugin, "name", plugin.__class__.__name__)
        if not callable(setup):
            _mark(plugin, "aktiv", "")
            continue
        host._current_path = path
        _log_plugin = name
        try:
            setup(host)
            _mark(plugin, "aktiv", "")
            host.meldung(f"Plugin aktiv: {name}")
        except Exception as exc:
            detail = traceback.format_exc().strip()
            _mark(plugin, "fehler", str(exc))
            plugin_log(f"Plugin {name} konnte nicht starten:\n{detail}", name)
            if hasattr(host.app, "log"):
                host.app.log(f"Plugin {name} konnte nicht starten: {exc}")
        finally:
            host._current_path = ""
            _log_plugin = ""


def _drop_all_ui(app):
    for path in reversed(list(_ui)):
        bucket = _ui.pop(path, None)
        if not bucket:
            continue
        for name, original in reversed(bucket.get("wraps") or []):
            try:
                setattr(app, name, original)
            except Exception:
                pass
        for widget in bucket.get("widgets") or []:
            _drop_widget(app, widget)


def _drop_widget(app, widget):
    notebook = getattr(app, "notebook", None)
    if notebook is not None:
        try:
            if str(widget) in notebook.tabs():
                notebook.forget(widget)
        except Exception:
            pass
    try:
        widget.destroy()
    except Exception:
        pass


def _mark(plugin, status: str, detail: str) -> None:
    name = getattr(plugin, "name", plugin.__class__.__name__)
    for report in _reports:
        if report.get("name") == name and report.get("status") != "fehler":
            report["status"] = status
            report["detail"] = detail
            return
    for report in _reports:
        if report.get("name") == name:
            report["status"] = status
            report["detail"] = detail
            return


def plugin_for_url(url: str):
    text = (url or "").strip()
    if not text:
        return None
    for plugin in load_plugins():
        try:
            matches = getattr(plugin, "matches", None)
            if callable(matches) and matches(text):
                return plugin
        except Exception as exc:
            name = getattr(plugin, "name", plugin.__class__.__name__)
            plugin_log(f"{name}.matches: {exc}")
            continue
    return None
