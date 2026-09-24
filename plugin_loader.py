"""Lädt Plugins aus dem Projektordner und aus dem Datenordner der App."""

import importlib.util
import shutil
import sys
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


def load_plugins():
    """Lädt alle Plugin-Dateien. Gleicher Name im Datenordner ersetzt die Vorlage."""
    global _loaded
    if _loaded is not None:
        return _loaded
    found = {}
    for folder in plugin_directories():
        for path in sorted(folder.glob("*.py")):
            if path.name.startswith("_"):
                continue
            plugin = _load_file(path)
            if plugin is not None:
                found[path.stem] = plugin
    _loaded = list(found.values())
    return _loaded


def _load_file(path: Path):
    try:
        spec = importlib.util.spec_from_file_location(f"ud_plugin_{path.stem}", path)
        if spec is None or spec.loader is None:
            return None
        module = importlib.util.module_from_spec(spec)
        spec.loader.exec_module(module)
        plugin_type = getattr(module, "Plugin", None)
        if not isinstance(plugin_type, type):
            return None
        plugin = plugin_type()
        has_hook = any(callable(getattr(plugin, name, None)) for name in ("setup", "matches", "download"))
        if not has_hook:
            return None
        return plugin
    except Exception:
        return None


class PluginHost:
    """Was ein Plugin am fertigen Programm ändern darf."""

    def __init__(self, app):
        self.app = app

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
        """Schreibt eine Zeile ins Programmfenster. Das ist keine Logdatei und kein Login."""
        if hasattr(self.app, "log"):
            self.app.log(str(message))

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
            print(f"Plugin {name}.{method_name}: {exc}")
    return answers


def activate_plugins(app):
    host = PluginHost(app)
    app.plugin_host = host
    for plugin in load_plugins():
        setup = getattr(plugin, "setup", None)
        if not callable(setup):
            continue
        name = getattr(plugin, "name", plugin.__class__.__name__)
        try:
            setup(host)
            host.meldung(f"Plugin geladen: {name}")
        except Exception as exc:
            print(f"Plugin {name} konnte nicht starten: {exc}")
            host.meldung(f"Plugin {name} konnte nicht starten: {exc}")


def plugin_for_url(url: str):
    text = (url or "").strip()
    if not text:
        return None
    for plugin in load_plugins():
        try:
            matches = getattr(plugin, "matches", None)
            if callable(matches) and matches(text):
                return plugin
        except Exception:
            continue
    return None
