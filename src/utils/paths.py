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
