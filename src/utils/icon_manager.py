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

from utils.paths import get_project_root

_ICONS_DIR = get_project_root() / "assets" / "icons"

# KI-WERKE Brand Colors
COLOR_ACTIVE = "#00E0B8"   # cyan_neon
COLOR_INACTIVE = "#9CA3AF"  # text_muted

# Icon-Mapping: logischer Name -> (kategorie, dateiname_ohne_extension)
ICON_MAP = {
    # Launcher Sidebar
    "recording":     ("status",     "activity"),
    "informationen": ("system",     "info"),
    "einstellungen": ("system",     "settings"),
    "hilfe":         ("status",     "help-circle"),
    # Bonus-Menuepunkte
    "woerterbuch":   ("ui",         "book"),
    "ausschnitte":   ("ui",         "scissors"),
    "style":         ("ui",         "paintbrush-2"),
    "notizblock":    ("ui",         "file-text"),
    "verlauf":       ("status",     "circle"),
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
