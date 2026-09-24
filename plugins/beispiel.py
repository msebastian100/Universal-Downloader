# vorlage 5
"""Beispiel, wie ein Plugin mit dem Programm spricht.

Datei hier ablegen oder in
~/Downloads/Universal Downloader/plugins/

Die Klasse muss Plugin heißen.
setup läuft einmal, wenn das Fenster fertig ist.
can_load_books wird gefragt, bevor die Audible-Bücher geladen werden.
"""

from pathlib import Path


class Plugin:
    name = "Beispiel"

    def setup(self, app):
        # Knopf neben „Audible anmelden“:
        # app.add_button("Mein Knopf", lambda: app.meldung("gedrückt"), place="audible")

        # Neuer Tab direkt nach dem Video-Downloader:
        # frame = app.add_tab("Mein Downloader", after="Video")
        # import tkinter.ttk as ttk
        # ttk.Label(frame, text="Hier kommt der Inhalt hin.").pack(anchor="w")
        return None

    def can_load_books(self, app):
        """Wird beim Laden der Audible-Bücher gefragt. False bricht das Laden ab."""
        # login("…") prüft genau diesen Dienst. Das ist kein Log und keine Logdatei.
        if not app.login("audible"):
            app.meldung("Plugin: Audible ist nicht angemeldet, die Bücher können nicht geladen werden.")
            return False
        # Dieselbe Prüfung für die anderen Logins:
        # app.login("youtube")
        # app.login("orf")
        # app.login("deezer")

        # function("…") prüft, ob irgendein Plugin diese Funktion hinterlegt hat.
        # if app.function("activation_bytes"):
        #     app.meldung("Plugin: Für Activation Bytes ist eine Funktion hinterlegt.")

        if app.audible_books_loaded():
            app.meldung("Plugin: Audible ist angemeldet, die Bücher sind schon da und werden neu geladen.")
        else:
            app.meldung("Plugin: Audible ist angemeldet, die Bücher können geladen werden.")
        return True

    # Platzhalter, noch nicht aktiv. Kommentarzeichen entfernen,
    # dann meldet function("activation_bytes") True.
    #
    # def activation_bytes(self, app):
    #     if not app.login("audible"):
    #         return "Zuerst bei Audible anmelden."
    #     return "Hier kommt der eigene Code für Activation Bytes hin."

    def matches(self, url: str) -> bool:
        return False

    def download(self, url: str, output_dir: Path) -> bool:
        output_dir = Path(output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)
        return False
