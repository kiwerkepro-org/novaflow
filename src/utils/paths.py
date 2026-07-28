"""
NovaFlow Pfad-Hilfsfunktion.

Ermittelt den Projekt-Wurzelordner, und zwar sowohl im normalen Python-Betrieb
(python novaflow.pyw) als auch spaeter, wenn NovaFlow einmal als PyInstaller-
bzw. py2app-Anwendung gebuendelt laeuft. config.py, secure_config.py, logger.py
und die Plattform-Module nutzen ausschliesslich diese Funktion, damit .env,
logs/ und Icons in beiden Faellen am richtigen Ort gefunden werden.

Hintergrund: im alten NovaFlow (C:\\KIW-SCHMIEDE\\NOVA-FLOW) berechnet jede
Datei ihre eigene Ebenen-Kette aus Path(__file__).parent.parent..., das
funktioniert nur, solange die echten .py-Dateien am gewohnten Ort liegen.
Sobald eine Anwendung gebuendelt wird, stimmt diese Annahme nicht mehr.
Deswegen gibt es hier von Anfang an genau eine zentrale, robuste Stelle.
"""
import sys
from pathlib import Path


def get_project_root() -> Path:
    """Gibt den NovaFlow-Projektordner zurueck.

    - Normaler Python-Betrieb: drei Ebenen ueber dieser Datei
      (src/utils/paths.py -> src/utils -> src -> Projekt-Root).
    - Gebuendelte Anwendung (PyInstaller/py2app): der Ordner, in dem die
      ausfuehrbare Datei liegt (sys.executable).
    """
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent.parent


def get_resource_dir() -> Path:
    """Gibt den Ordner mit den MITGELIEFERTEN Dateien zurueck (assets, VERSION,
    .env.example).

    Das ist bewusst NICHT dasselbe wie get_project_root(). Im gebuendelten
    Betrieb gibt es zwei verschiedene Orte:

    - beschreibbare Dateien (.env, logs/) liegen neben der NovaFlow.exe,
      dafuer ist get_project_root() zustaendig
    - mitgelieferte, nur lesbare Dateien legt PyInstaller dagegen in einen
      Unterordner, standardmaessig "_internal", und macht dessen Pfad ueber
      sys._MEIPASS bekannt

    Die Spec-Datei versucht zwar ueber contents_directory="." beides an
    denselben Ort zu legen, das hat sich im echten Build aber als
    unzuverlaessig erwiesen (PyInstaller hat trotzdem einen _internal-Ordner
    angelegt). Folge war, dass die VERSION-Datei nicht gefunden wurde,
    get_current_version() auf "0.0.0" zurueckfiel und der Update-Checker
    dauerhaft ein Update gemeldet hat. Diese Funktion sucht deshalb an
    beiden Orten und funktioniert damit unabhaengig vom Layout.
    """
    if getattr(sys, "frozen", False):
        meipass = getattr(sys, "_MEIPASS", None)
        if meipass:
            return Path(meipass).resolve()
    return get_project_root()


def find_resource(name: str) -> Path:
    """Sucht eine mitgelieferte Datei an allen in Frage kommenden Orten.

    Gibt den ersten Treffer zurueck. Wird nichts gefunden, kommt der Pfad im
    Ressourcen-Ordner zurueck, damit der Aufrufer eine sinnvolle
    Fehlermeldung bauen kann.
    """
    candidates = [get_resource_dir() / name, get_project_root() / name]
    for candidate in candidates:
        if candidate.exists():
            return candidate
    return candidates[0]


def get_user_data_dir() -> Path:
    """Gibt den Ordner fuer benutzerspezifische Daten zurueck (~/.novaflow).

    Bewusst getrennt vom Projekt-Root: Woerterbuch, Ausschnitte, Verlauf usw.
    sollen ein Update oder eine Neuinstallation ueberleben. Funktioniert
    unveraendert auf Windows, Mac und Linux, da Path.home() auf allen drei
    Plattformen das richtige Home-Verzeichnis liefert.
    """
    data_dir = Path.home() / ".novaflow"
    data_dir.mkdir(parents=True, exist_ok=True)
    return data_dir
