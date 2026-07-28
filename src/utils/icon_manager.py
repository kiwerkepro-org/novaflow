"""
NovaFlow Icon Manager
SVG-Icons aus assets/icons/ laden, colorieren und als QIcon ausgeben.
Nutzt QSvgRenderer fuer natives PyQt6-Rendering ohne externe Pakete.
Unveraendert gegenueber dem bisherigen NovaFlow, nur der Pfad kommt jetzt
ueber die plattformsichere paths.get_project_root().
"""
from typing import Optional
from PyQt6.QtCore import Qt, QByteArray
from PyQt6.QtGui import QIcon, QPixmap, QPainter
from PyQt6.QtSvg import QSvgRenderer

from utils.paths import find_resource

# WICHTIG: find_resource statt get_project_root. Die Icons sind mitgelieferte
# Dateien, PyInstaller legt die im gebuendelten Betrieb in den _internal-
# Unterordner und NICHT neben die NovaFlow.exe. Mit get_project_root wurden
# sie dort deshalb nie gefunden, die Menuepunkte im Einstellungsfenster
# blieben in der installierten Version komplett ohne Symbol (im normalen
# Python-Betrieb fiel das nicht auf, dort stimmt der Pfad zufaellig).
_ICONS_DIR = find_resource("assets") / "icons"

# KI-WERKE Brand Colors
# COLOR_INACTIVE muss mit COLORS["text_muted"] in gui_settings_modal.py
# synchron bleiben, sonst wirken inaktive Icons dunkler/blasser als der
# Text daneben. Am 2026-07-25 dort aufgehellt (#9CA3AF -> #B8BFCC), hier
# nachgezogen.
COLOR_ACTIVE = "#00E0B8"   # cyan_neon
COLOR_INACTIVE = "#B8BFCC"  # text_muted

# Icon-Mapping: logischer Name -> (kategorie, dateiname_ohne_extension)
ICON_MAP = {
    # Launcher Sidebar
    "recording":     ("status",     "activity"),
    # Alias: TOP_NAV/PAGES in gui_settings_modal.py referenzieren die
    # Uebersicht-Seite ueber den Schluessel "activity" direkt (nicht
    # "recording"). Ohne diesen Alias lieferte IconManager.get() dafuer
    # ein leeres QIcon zurueck (Schluessel nicht in ICON_MAP), der
    # Uebersicht-Eintrag stand dadurch ohne Symbol da und aus der Reihe
    # (JJ-Screenshot, 2026-07-25).
    "activity":      ("status",     "activity"),
    "informationen": ("system",     "info"),
    "einstellungen": ("system",     "settings"),
    "hilfe":         ("status",     "help-circle"),
    "help":          ("status",     "help-circle"),
    # Bonus-Menuepunkte
    "woerterbuch":   ("ui",         "book"),
    "ausschnitte":   ("ui",         "scissors"),
    "style":         ("ui",         "paintbrush-2"),
    "notizblock":    ("ui",         "file-text"),
    # War vorher ein bedeutungsloser leerer Kreis, jetzt das echte
    # Lucide-"history"-Icon (Uhr mit Rueckwaerts-Pfeil), extra als neue
    # SVG-Datei ergaenzt (JJ, 2026-07-25).
    "verlauf":       ("status",     "history"),
    # Settings Sidebar
    "whisper":       ("status",     "activity"),
    "llm":           ("system",     "settings"),
    "api_keys":      ("system",     "check"),
    "language":      ("navigation", "menu"),
    # Allgemeine UI-Icons
    "close":         ("system",     "x"),
    "alert":         ("system",     "alert"),
    "search":        ("ui",         "search"),
    "add":           ("ui",         "plus"),
    "delete":        ("ui",         "trash-2"),
    "edit":          ("ui",         "edit-2"),
    "download":      ("ui",         "download"),
    "upload":        ("ui",         "upload"),
    "mic":           ("ui",         "mic"),
}

_cache = {}


class IconManager:
    """Laedt SVG-Icons, ersetzt stroke-Farbe und rendert als QPixmap/QIcon."""

    @staticmethod
    def get(name: str, active: bool = False, size: int = 24,
            color_override: Optional[str] = None) -> QIcon:
        color = color_override or (COLOR_ACTIVE if active else COLOR_INACTIVE)

        if name not in ICON_MAP:
            return QIcon()

        category, filename = ICON_MAP[name]
        svg_path = _ICONS_DIR / category / f"{filename}.svg"
        cache_key = (str(svg_path), color, size)

        if cache_key in _cache:
            return _cache[cache_key]

        icon = IconManager._render_svg(svg_path, color, size)
        _cache[cache_key] = icon
        return icon

    @staticmethod
    def _render_svg(svg_path, color: str, size: int) -> QIcon:
        if not svg_path.exists():
            return QIcon()

        try:
            svg_content = svg_path.read_text(encoding="utf-8")
            colored_svg = svg_content.replace("currentColor", color)

            svg_bytes = QByteArray(colored_svg.encode("utf-8"))
            renderer = QSvgRenderer(svg_bytes)

            if not renderer.isValid():
                return QIcon()

            pixmap = QPixmap(size, size)
            pixmap.fill(Qt.GlobalColor.transparent)

            painter = QPainter(pixmap)
            painter.setRenderHint(QPainter.RenderHint.Antialiasing)
            renderer.render(painter)
            painter.end()

            return QIcon(pixmap)

        except Exception:
            return QIcon()

    @staticmethod
    def clear_cache() -> None:
        _cache.clear()


icon_manager = IconManager()
