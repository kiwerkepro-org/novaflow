"""
NovaFlow Plattform-Fabrik.

get_platform() liefert genau EINE Instanz der passenden Plattform-Klasse
zurueck (Windows, Mac, oder der Linux-Platzhalter), abhaengig von sys.platform.
Der Rest von NovaFlow ruft ausschliesslich get_platform() auf und importiert
NIE windows.py/macos.py/linux.py direkt.
"""
import sys
from functools import lru_cache

from platforms.base import Platform


@lru_cache(maxsize=1)
def get_platform() -> Platform:
    if sys.platform == "win32":
        from platforms.windows import WindowsPlatform
        return WindowsPlatform()
    if sys.platform == "darwin":
        from platforms.macos import MacPlatform
        return MacPlatform()

    from platforms.linux import LinuxPlatform
    return LinuxPlatform()
