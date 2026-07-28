"""
NovaFlow Update-Check.

Fragt die oeffentliche GitHub-Releases-API ab (kein Login noetig, da das
Repository oeffentlich ist) und vergleicht die dort neueste Version mit der
lokal installierten (VERSION-Datei). Plattformunabhaengig, nutzt nur
requests, das NovaFlow ohnehin schon fuer die LLM-Provider mitbringt.

Bewusst nur EIN Vergleich pro Aufruf, keine Hintergrund-Threads hier drin,
das uebernimmt der Aufrufer (z.B. ein QTimer in novaflow.pyw), damit dieses
Modul einfach und leicht testbar bleibt.
"""
import requests

from utils.paths import find_resource
from utils.logger import logger

REPO = "kiwerkepro-org/novaflow"
LATEST_RELEASE_URL = f"https://api.github.com/repos/{REPO}/releases/latest"


def get_current_version() -> str:
    """Liest die lokal installierte Version aus der VERSION-Datei.

    Gibt "0.0.0" zurueck, falls die Datei fehlt (z.B. bei einem sehr alten
    Build ohne VERSION-Datei), damit ein Update dann garantiert als
    verfuegbar erkannt wird, statt den Check stillschweigend zu verschlucken.
    """
    version_file = find_resource("VERSION")
    if not version_file.exists():
        # Sichtbar machen statt still auf 0.0.0 zu fallen: genau dieser Fall
        # hat dazu gefuehrt, dass jede Version als veraltet galt und der
        # Nutzer dauerhaft eine Update-Meldung bekam.
        logger.warning(
            f"VERSION-Datei nicht gefunden (gesucht: {version_file}). "
            "Update-Prüfung wird übersprungen.",
            f"VERSION file not found (looked in: {version_file}). "
            "Skipping update check.",
        )
        return ""
    return version_file.read_text(encoding="utf-8").strip()


def _parse_version(version: str) -> tuple:
    """Wandelt "0.5.1" in (0, 5, 1) um, fuer einen echten Zahlenvergleich
    statt eines Text-Vergleichs (der bei z.B. "0.10.0" vs "0.9.0" sonst
    falsch liegen wuerde)."""
    parts = []
    for piece in version.strip().lstrip("v").split("."):
        try:
            parts.append(int(piece))
        except ValueError:
            parts.append(0)
    return tuple(parts)


def check_for_update(timeout: int = 5) -> dict:
    """Prueft, ob auf GitHub eine neuere Version veroeffentlicht ist.

    Returns:
        dict mit:
          available (bool):       True, wenn eine neuere Version existiert
          current_version (str):  lokal installierte Version
          latest_version (str):   neueste Version auf GitHub (ohne "v")
          download_url (str):     Direktlink zur passenden Setup-Datei
                                   (Windows: .exe, Mac: .dmg), leer wenn
                                   nicht gefunden
          release_url (str):      Link zur Release-Seite auf GitHub
          error (str|None):       Fehlermeldung, falls der Check fehlschlug
                                   (z.B. kein Internet) - available ist dann
                                   immer False, NICHT True, damit ein
                                   Netzwerkfehler nie faelschlich als Update
                                   angezeigt wird.
    """
    result = {
        "available": False,
        "current_version": get_current_version(),
        "latest_version": None,
        "download_url": "",
        "release_url": f"https://github.com/{REPO}/releases/latest",
        "error": None,
    }

    # Ohne bekannte eigene Version darf NICHT verglichen werden. Sonst gilt
    # jede veroeffentlichte Version als neuer und der Nutzer bekommt endlos
    # Update-Meldungen fuer etwas, das er laengst installiert hat.
    if not result["current_version"]:
        result["error"] = "Eigene Version unbekannt (VERSION-Datei fehlt)"
        return result

    try:
        response = requests.get(LATEST_RELEASE_URL, timeout=timeout)
        response.raise_for_status()
        data = response.json()
    except Exception as e:
        result["error"] = str(e)
        logger.debug(f"Update-Check fehlgeschlagen: {e}", f"Update check failed: {e}")
        return result

    latest_tag = data.get("tag_name", "")
    latest_version = latest_tag.lstrip("v")
    result["latest_version"] = latest_version
    result["release_url"] = data.get("html_url", result["release_url"])

    import sys
    wanted_suffix = ".dmg" if sys.platform == "darwin" else ".exe"
    for asset in data.get("assets", []):
        if asset.get("name", "").endswith(wanted_suffix):
            result["download_url"] = asset.get("browser_download_url", "")
            break

    if _parse_version(latest_version) > _parse_version(result["current_version"]):
        result["available"] = True
        logger.info(
            f"Update verfuegbar: {result['current_version']} -> {latest_version}",
            f"Update available: {result['current_version']} -> {latest_version}",
        )

    return result
