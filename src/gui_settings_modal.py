"""
NovaFlow Settings Modal (Next)

Gegenueber dem bisherigen NovaFlow ist das hier EIN gemeinsames Fenster fuer
alles, technische Einstellungen (Diktat, Spracherkennung, Sprachmodell,
API-Schluessel, Sprache & System) UND die "Bonus"-Funktionen (Woerterbuch,
Ausschnitte, Schreibstil, Notizbuch, Verlauf), die im alten NovaFlow auf
zwei getrennte Dateien (launcher_pro.py Hauptfenster + gui_settings_modal.py)
aufgeteilt waren. Das ist bewusst zusammengelegt, damit es an einer Stelle
uebersichtlich bleibt.

Design-Vorgaben (auf Wunsch): Navigationspunkte LINKSBUENDIG statt zentriert,
mit Icon, KI-WERKE Branding-Farben.
"""
import sys
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidTag

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout, QGridLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QScrollArea,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QMessageBox, QListWidget,
    QListWidgetItem, QTextEdit, QFileDialog
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont, QGuiApplication

from utils.config import config
from utils.secure_config import secure_config
from utils.icon_manager import icon_manager
from utils.dictionary_store import dictionary_store, parse_vocabulary_text
from utils.snippets_store import snippets_store
from utils.style_store import style_store, CATEGORIES, TONES
from utils.notes_store import notes_store
from utils.history_store import (
    history_store, compute_history_stats, filter_history_entries, DATE_FILTERS
)
from utils.update_checker import get_current_version
from platforms import get_platform


COLORS = {
    "deep_navy": "#0A0F1A",
    # War vorher #111827 (ein sichtbar graues Blaugrau) für Seitenleiste,
    # Eingabefelder, Listen und Auswahl-Boxen. Auf Wunsch entfernt: diese
    # Flächen sind jetzt genau wie der Hintergrund, die Abgrenzung kommt
    # nur noch von der Border-Farbe darunter, kein Grau mehr davor.
    "panel_grey": "#0A0F1A",
    "cyan_neon": "#00E0B8",
    "off_white": "#F4F5F7",
    # War #9CA3AF (Kontrast 7.55:1 zu deep_navy, technisch schon AAA-Niveau
    # nach WCAG). Auf JJs ausdruecklichen Wunsch trotzdem aufgehellt (jetzt
    # 10.37:1), damit Bildunterschriften/Hinweistexte auch subjektiv klar
    # hell genug wirken, nicht nur nach Formel (2026-07-25, vierter Audit).
    "text_muted": "#B8BFCC",
    "border": "#1F2937",
    "danger": "#F87171",
}

# Reihenfolge hier bestimmt die Reihenfolge der Seiten im QStackedWidget,
# siehe self.stacked.addWidget(...)-Aufrufe in init_ui(). "Übersicht" steht
# bewusst an erster Stelle: Start/Stop des Diktier-Motors und ein grober
# Überblick über die aktive Konfiguration sollen das Allererste sein, was
# beim Öffnen der Einstellungen zu sehen ist.
# Icon-Schluessel "mic" statt "whisper" (siehe ICON_MAP in icon_manager.py):
# "whisper" und "recording" (Diktat) zeigten beide auf dieselbe Datei
# activity.svg. JJs Kritik an den Screenshots, 2026-07-25: unterscheidbare
# Icons statt zufaelliger Wiederverwendung. "verlauf" zeigte urspruenglich
# auf einen bedeutungslosen leeren Kreis, zeigt jetzt (nach kurzem
# Zwischenstopp bei "search") auf ein echtes Lucide-"history"-Icon, das
# extra als neue SVG-Datei ergaenzt wurde (JJ, 2026-07-25).
PAGES = [
    ("Übersicht", "activity"),
    ("Diktat", "recording"),
    ("Spracherkennung", "mic"),
    ("Sprachmodell", "llm"),
    ("API-Schlüssel", "api_keys"),
    ("Sprache & System", "language"),
    ("Update", "download"),
    ("Wörterbuch", "woerterbuch"),
    ("Ausschnitte", "ausschnitte"),
    ("Schreibstil", "style"),
    ("Notizbuch", "notizblock"),
    ("Verlauf", "verlauf"),
    ("Hilfe", "help"),
]

# Zweistufige Navigation: Eintraege mit "children" sind eine Gruppe (klappt
# eine zweite Spalte mit Unterpunkten auf, siehe _build_sidebar), alle
# anderen sind direkte Blattpunkte, die sofort die passende Seite aus PAGES
# zeigen. Auf Wunsch zusammengefasst: die rein technischen Einstellungen
# (Diktat, Spracherkennung, Sprachmodell, API-Schlüssel, Sprache & System,
# Update) stehen jetzt gebündelt unter "Einstellungen", statt als sechs
# gleichrangige Punkte die "Bonus"-Funktionen zu verdrängen.
TOP_NAV = [
    ("Übersicht", "activity", None),
    ("Einstellungen", "einstellungen", [
        "Diktat", "Spracherkennung", "Sprachmodell",
        "API-Schlüssel", "Sprache & System", "Update",
    ]),
    ("Wörterbuch", "woerterbuch", None),
    ("Ausschnitte", "ausschnitte", None),
    ("Schreibstil", "style", None),
    ("Notizbuch", "notizblock", None),
    ("Verlauf", "verlauf", None),
    ("Hilfe", "help", None),
]

PAGE_INDEX = {label: i for i, (label, _icon) in enumerate(PAGES)}

# Nur diese fuenf Seiten sammeln Aenderungen in Eingabefeldern/Comboboxen und
# schreiben sie erst beim Klick auf "Speichern" weg (siehe save_settings()).
# Alle anderen Seiten wirken sofort (Hinzufuegen/Loeschen/eigener
# Uebernehmen-Knopf) und brauchen deshalb den globalen Speichern-Knopf nicht,
# siehe _select_leaf().
PAGES_WITH_BATCH_SAVE = {
    "Diktat", "Spracherkennung", "Sprachmodell", "API-Schlüssel", "Sprache & System",
}


class NovaFlowSettingsModal(QDialog):
    """Ein gemeinsames Einstellungsfenster für Technik + Bonus-Funktionen"""

    def __init__(self, parent=None, engine_api=None):
        super().__init__(parent)
        self.setWindowTitle("NovaFlow – Einstellungen")

        # engine_api ist ein EngineController (siehe novaflow.pyw), darüber
        # startet/stoppt die Übersicht-Seite den Diktier-Motor und liest
        # dessen Status. None ist ein gültiger Wert (z.B. bei einem Aufruf
        # ohne den Tray-Kontext), die Übersicht-Seite blendet Start/Stop
        # dann einfach aus, statt abzustürzen.
        self.engine_api = engine_api

        self.setMinimumSize(1300, 860)
        # Auf Wunsch (JJ, 2026-07-28): das Fenster nutzt von Anfang an die
        # komplette verfuegbare Bildschirmflaeche (100%) statt nur 85% davon
        # wie vorher, es gibt keinen Grund, Platz zu verschenken. Bleibt
        # trotzdem ein normales, verschiebbares/verkleinerbares Fenster.
        screen = QGuiApplication.primaryScreen()
        if screen:
            avail = screen.availableGeometry()
            self.resize(avail.width(), avail.height())
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['deep_navy']}; }}")
        self.setModal(True)
        self.platform = get_platform()

        if parent:
            pr = parent.frameGeometry()
            self.move(pr.left() + (pr.width() - self.width()) // 2,
                      pr.top() + (pr.height() - self.height()) // 2)
        elif screen:
            avail = screen.availableGeometry()
            self.move(avail.left(), avail.top())

        self.nav_buttons = {}       # Label -> QPushButton (Hauptspalte)
        self.sub_nav_buttons = {}   # Label -> QPushButton (Unterspalte)
        self.current_group = None  # aktuell aufgeklappte Gruppe, z.B. "Einstellungen"
        self.init_ui()
        self.load_settings()

        # Zusaetzlich echt maximiert (Vollbild-Fenstermodus, nicht nur
        # gleich gross wie der Bildschirm): erst NACHDEM init_ui() das
        # komplette Layout aufgebaut hat, damit beim ersten Anzeigen nicht
        # kurz ein leeres Fenster aufscheint.
        if screen:
            self.showMaximized()

        # Verlauf soll sich aktualisieren, solange die Seite offen ist
        self._history_timer = QTimer(self)
        self._history_timer.timeout.connect(self._refresh_history_if_visible)
        self._history_timer.start(2000)

        # Übersicht-Seite (Motor-Status) staendig aktuell halten, solange
        # das Fenster offen ist.
        self._status_timer = QTimer(self)
        self._status_timer.timeout.connect(self._refresh_overview_status)
        self._status_timer.start(1000)

    # ------------------------------------------------------------------
    # Grundgerüst
    # ------------------------------------------------------------------
    def init_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        # ---------------- Spalte 1: Hauptnavigation ----------------
        sidebar = QFrame()
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel_grey']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        # 260px passte zur alten, kleineren Nav-Schrift. Seit dem
        # Schriftgroessen-Audit (2026-07-25) laufen Nav-Buttons auf 24px
        # fett, "Sprache & System" schnitt bei 260px am Rand ab (JJs
        # Screenshot). 320px reicht auch fuer das laengste Wort mit Icon.
        sidebar.setMaximumWidth(320)
        sidebar.setMinimumWidth(320)

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        logo = QLabel("NovaFlow")
        font = QFont()
        font.setPixelSize(32)
        font.setBold(True)
        logo.setFont(font)
        logo.setStyleSheet(f"color: {COLORS['cyan_neon']}; padding: 20px 20px 4px 20px;")
        sidebar_layout.addWidget(logo)

        # Versionsnummer direkt unter dem Namen, damit man auf einen Blick
        # sieht, welcher Stand laeuft, ohne dafuer in die Systemsteuerung
        # oder in den Update-Menuepunkt wechseln zu muessen.
        installed = get_current_version()
        sub = QLabel(f"Einstellungen  ·  Version {installed}" if installed else "Einstellungen")
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 0 20px 16px 20px; font-size: 18px;")
        # Absicherung: bei einer laengeren Versionsnummer in Zukunft lieber
        # zweizeilig als am Spaltenrand abgeschnitten.
        sub.setWordWrap(True)
        sidebar_layout.addWidget(sub)

        nav_scroll = QScrollArea()
        nav_scroll.setWidgetResizable(True)
        nav_scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {COLORS['panel_grey']}; }}")
        nav_scroll.viewport().setStyleSheet(f"background-color: {COLORS['panel_grey']};")
        nav_container = QWidget()
        nav_container.setStyleSheet(f"background-color: {COLORS['panel_grey']};")
        nav_container_layout = QVBoxLayout()
        nav_container_layout.setContentsMargins(0, 0, 0, 0)
        nav_container_layout.setSpacing(0)

        for label, icon_name, children in TOP_NAV:
            btn = self._create_nav_button(label, icon_name)
            if children:
                btn.clicked.connect(lambda checked=False, lbl=label: self._open_group(lbl))
            else:
                btn.clicked.connect(lambda checked=False, lbl=label: self._select_leaf(lbl))
            nav_container_layout.addWidget(btn)
            self.nav_buttons[label] = btn

        nav_container_layout.addStretch()
        nav_container.setLayout(nav_container_layout)
        nav_scroll.setWidget(nav_container)
        sidebar_layout.addWidget(nav_scroll, 1)
        sidebar.setLayout(sidebar_layout)
        main_layout.addWidget(sidebar)

        # ---------------- Spalte 2: Unterpunkte einer Gruppe ----------------
        # Nur sichtbar, solange eine Gruppe (aktuell nur "Einstellungen")
        # aufgeklappt ist. So bleibt die Hauptspalte kurz und uebersichtlich,
        # trotzdem sind die technischen Einstellungen klar als
        # zusammengehoerig erkennbar, statt sechs gleichrangige Punkte
        # zwischen den Bonus-Funktionen zu verstreuen.
        self.subnav_frame = QFrame()
        self.subnav_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['deep_navy']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        # 220px, dann 260px schnitten laengere Eintraege ab
        # ("Spracherkennung", "Sprache & System"), zuletzt wieder sichtbar
        # nach dem Schriftgroessen-Audit (24px fett statt vorher 15pt),
        # siehe JJs Screenshot vom 2026-07-25. 320px, synchron mit der
        # Hauptspalte, reicht auch fuer das laengste Wort mit Icon.
        self.subnav_frame.setMaximumWidth(320)
        self.subnav_frame.setMinimumWidth(320)
        subnav_layout = QVBoxLayout()
        subnav_layout.setContentsMargins(0, 0, 0, 0)
        subnav_layout.setSpacing(0)

        subnav_title = QLabel("Einstellungen")
        subnav_title.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 24px 20px 8px 20px; font-size: 18px;")
        subnav_layout.addWidget(subnav_title)

        self._group_children = {}
        for label, _icon, children in TOP_NAV:
            if not children:
                continue
            self._group_children[label] = children
            for child_label in children:
                child_icon = dict((p_label, p_icon) for p_label, p_icon in PAGES)[child_label]
                btn = self._create_nav_button(child_label, child_icon)
                btn.clicked.connect(lambda checked=False, lbl=child_label: self._select_leaf(lbl))
                subnav_layout.addWidget(btn)
                self.sub_nav_buttons[child_label] = btn

        subnav_layout.addStretch()
        self.subnav_frame.setLayout(subnav_layout)
        self.subnav_frame.setVisible(False)
        main_layout.addWidget(self.subnav_frame)

        # ---------------- Spalte 3: Inhalt ----------------
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(20)

        self.stacked = QStackedWidget()
        self.stacked.setStyleSheet(f"QStackedWidget {{ background-color: {COLORS['deep_navy']}; }}")

        # Reihenfolge MUSS exakt der PAGES-Liste oben entsprechen, da
        # switch_page()/PAGE_INDEX ueber den Namen den Index nachschlagen.
        self.stacked.addWidget(self._create_overview_page())
        self.stacked.addWidget(self._create_recording_page())
        self.stacked.addWidget(self._create_stt_page())
        self.stacked.addWidget(self._create_llm_page())
        self.stacked.addWidget(self._create_api_page())
        self.stacked.addWidget(self._create_lang_page())
        self.stacked.addWidget(self._create_update_page())
        self.stacked.addWidget(self._create_dictionary_page())
        self.stacked.addWidget(self._create_snippets_page())
        self.stacked.addWidget(self._create_style_page())
        self.stacked.addWidget(self._create_notes_page())
        self.stacked.addWidget(self._create_history_page())
        self.stacked.addWidget(self._create_help_page())

        content_layout.addWidget(self.stacked)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        self.save_btn = QPushButton("Speichern")
        self.save_btn.setMinimumHeight(48)
        self.save_btn.setMinimumWidth(160)
        bf = QFont()
        bf.setPixelSize(24)
        bf.setBold(True)
        self.save_btn.setFont(bf)
        self.save_btn.clicked.connect(self.save_settings)
        self.save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['cyan_neon']};
                color: {COLORS['deep_navy']};
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
                font-weight: bold;
            }}
        """)
        # Sichtbarkeit wird in _select_leaf() pro Seite gesetzt (siehe
        # PAGES_WITH_BATCH_SAVE oben): nur die fuenf echten Einstellungsseiten
        # sammeln Aenderungen und brauchen einen Speichern-Knopf. Ueberall
        # sonst (Woerterbuch, Ausschnitte, Notizbuch, Verlauf, Uebersicht,
        # Update, Schreibstil, Hilfe) wirken Aenderungen schon sofort ueber
        # eigene Hinzufuegen-/Loeschen-/Uebernehmen-Knoepfe, ein zusaetzlicher
        # globaler Speichern-Knopf dort waere irrefuehrend, "doppelt gemoppelt"
        # (JJs Worte, 2026-07-25): sieht nach noetiger Bestaetigung aus, tut
        # aber nichts.
        btn_layout.addWidget(self.save_btn)

        close_btn = QPushButton("Schließen")
        close_btn.setMinimumHeight(48)
        close_btn.setMinimumWidth(160)
        close_btn.setFont(bf)
        close_btn.clicked.connect(self.close)
        close_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px 28px;
            }}
        """)
        btn_layout.addWidget(close_btn)

        content_layout.addLayout(btn_layout)
        content.setLayout(content_layout)
        main_layout.addWidget(content, 1)

        self.setLayout(main_layout)
        self._select_leaf("Übersicht")

    def _create_nav_button(self, text: str, icon_name: str = "") -> QPushButton:
        """Linksbündiger Nav-Button mit Icon (statt zentriert)

        WICHTIG: "&" im Text escapen (zu "&&"). QPushButton interpretiert ein
        einzelnes "&" als Tastenkuerzel-Mnemonic und frisst es beim Rendern,
        aus "Sprache & System" wurde dadurch "Sprache _System" mit
        unterstrichenem S statt des sichtbaren Und-Zeichens (JJ, 2026-07-25).
        """
        btn = QPushButton(f"  {text}".replace("&", "&&"))
        font = QFont()
        font.setPixelSize(24)
        font.setBold(True)
        btn.setFont(font)
        btn.setMinimumHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if icon_name:
            btn.setIcon(icon_manager.get(icon_name, active=False))
            btn.setIconSize(QSize(24, 24))
            btn.setProperty("icon_name", icon_name)

        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: transparent;
                color: {COLORS['text_muted']};
                border: none;
                border-left: 3px solid transparent;
                padding: 10px 20px;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {COLORS['off_white']};
                background-color: rgba(0, 224, 184, 0.1);
            }}
        """)
        return btn

    def _style_nav_button(self, btn: QPushButton, is_active: bool, is_parent: bool = False) -> None:
        """is_parent=True: Gruppen-Button einer aufgeklappten Gruppe (z.B.
        "Einstellungen"), waehrend eines ihrer Kinder das eigentlich offene
        Blatt ist. Bekommt bewusst eine SCHWAECHERE Markierung (nur die
        Textfarbe wechselt) als das echte offene Blatt (voller Balken plus
        Hintergrund), sonst konkurrieren zwei gleich starke "aktiv"-Zustaende
        um Aufmerksamkeit, ohne dass die Ueber-/Unterordnung erkennbar wird
        (JJs Kritik an den Screenshots, 2026-07-25)."""
        if is_active and is_parent:
            color = COLORS["cyan_neon"]
            border = "transparent"
            bg = "transparent"
            icon_active = False
        else:
            color = COLORS["cyan_neon"] if is_active else COLORS["text_muted"]
            border = COLORS["cyan_neon"] if is_active else "transparent"
            bg = "rgba(0, 224, 184, 0.15)" if is_active else "transparent"
            icon_active = is_active
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {bg};
                color: {color};
                border: none;
                border-left: 3px solid {border};
                padding: 10px 20px;
                text-align: left;
            }}
            QPushButton:hover {{
                color: {COLORS['off_white']};
                background-color: rgba(0, 224, 184, 0.1);
            }}
        """)
        icon_name = btn.property("icon_name") or ""
        if icon_name:
            btn.setIcon(icon_manager.get(icon_name, active=icon_active))

    def _open_group(self, group_label: str) -> None:
        """Klappt die Unterpunkte einer Gruppe (z.B. "Einstellungen") auf.

        Wechselt dabei gleich auf deren ERSTEN Unterpunkt, damit ein Klick
        auf die Gruppe nie ins Leere fuehrt (die Gruppe selbst hat keine
        eigene Seite im QStackedWidget).
        """
        # Die eigentliche Faerbung uebernimmt gleich _select_leaf() fuer den
        # ersten Kind-Eintrag vollstaendig (inklusive korrektem is_parent),
        # ein eigener Durchlauf hier waere nur redundant.
        first_child = self._group_children[group_label][0]
        self._select_leaf(first_child)

    def _select_leaf(self, label: str) -> None:
        """Zeigt die Seite zu `label` und pflegt die Hervorhebung in beiden
        Navigationsspalten nach."""
        # Gehoert die Seite zu einer Gruppe, gilt die Gruppe (nicht die
        # einzelne Unterseite) als aktiv in der Hauptspalte.
        owning_group = None
        for grp_label, children in getattr(self, "_group_children", {}).items():
            if label in children:
                owning_group = grp_label
                break

        if owning_group:
            self.current_group = owning_group
            self.subnav_frame.setVisible(True)
        else:
            self.current_group = None
            self.subnav_frame.setVisible(False)

        for lbl, btn in self.nav_buttons.items():
            active = (lbl == label) or (lbl == owning_group)
            self._style_nav_button(btn, is_active=active, is_parent=(lbl == owning_group))
        for lbl, btn in self.sub_nav_buttons.items():
            self._style_nav_button(btn, is_active=(lbl == label))

        self.stacked.setCurrentIndex(PAGE_INDEX[label])
        self.save_btn.setVisible(label in PAGES_WITH_BATCH_SAVE)
        if label == "Verlauf":
            self._load_history()
        if label == "Übersicht":
            self._refresh_overview_status()

    # ------------------------------------------------------------------
    # Übersicht: Motor Start/Stop + Status, als Erstes sichtbar
    # ------------------------------------------------------------------
    def _create_overview_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.addWidget(self._page_title("Übersicht"))

        self.overview_status_label = QLabel("Status wird geladen...")
        sf = QFont()
        sf.setPixelSize(28)
        sf.setBold(True)
        self.overview_status_label.setFont(sf)
        self.overview_status_label.setStyleSheet(f"color: {COLORS['cyan_neon']};")
        layout.addWidget(self.overview_status_label)

        bf = QFont()
        bf.setPixelSize(24)
        bf.setBold(True)

        btn_row = QHBoxLayout()
        self.overview_start_btn = QPushButton("Motor starten")
        self.overview_start_btn.setFont(bf)
        self.overview_start_btn.setMinimumHeight(48)
        self.overview_start_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.overview_start_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['cyan_neon']};
                color: {COLORS['deep_navy']};
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_muted']};
            }}
        """)
        self.overview_start_btn.clicked.connect(self._start_engine_clicked)
        btn_row.addWidget(self.overview_start_btn)

        self.overview_stop_btn = QPushButton("Motor stoppen")
        self.overview_stop_btn.setFont(bf)
        self.overview_stop_btn.setMinimumHeight(48)
        self.overview_stop_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        # KEINE Gefahrenfarbe (mehr): Stoppen ist jederzeit reversibel, ein
        # Klick auf "Motor starten" macht es sofort wieder rueckgaengig. Rot
        # sollte fuer die tatsaechlich unwiderrufliche Aktion reserviert
        # bleiben ("Verlauf leeren", siehe dort), nicht fuer einen normalen,
        # haeufig genutzten Zustandswechsel (JJs Kritik, 2026-07-25).
        self.overview_stop_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px 28px;
            }}
            QPushButton:hover {{
                border: 1px solid {COLORS['cyan_neon']};
                color: {COLORS['cyan_neon']};
            }}
            QPushButton:disabled {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
            }}
        """)
        self.overview_stop_btn.clicked.connect(self._stop_engine_clicked)
        btn_row.addWidget(self.overview_stop_btn)
        # Ohne diesen Stretch verteilt Qt den kompletten Restplatz der Zeile
        # auf die beiden Buttons, sie zogen sich dadurch fast ueber die
        # gesamte Fensterbreite (JJ-Screenshot, 2026-07-25).
        btn_row.addStretch()
        layout.addLayout(btn_row)

        if self.engine_api is None:
            self.overview_start_btn.setVisible(False)
            self.overview_stop_btn.setVisible(False)
            note = QLabel("Start/Stop ist in diesem Kontext nicht verfügbar.")
            note.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 18px;")
            layout.addWidget(note)

        layout.addSpacing(8)
        summary_title = QLabel("Aktive Konfiguration")
        summary_title.setFont(self._label_font())
        summary_title.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.addWidget(summary_title)

        # War vorher EINE einzelne, kleine, blasse Zeile mit Mittelpunkten als
        # Trenner, ausgerechnet die eigentliche Kerninfo der Seite war damit
        # das unauffaelligste Element im ganzen Fenster (JJs Kritik an den
        # Screenshots, 2026-07-25). Jetzt als kleines Raster mit klar
        # lesbaren Werten (off_white, 16px) unter kleinen, gedaempften
        # Beschriftungen, auf einen Blick erfassbar statt in einer Zeile
        # zusammengequetscht.
        grid = QGridLayout()
        grid.setHorizontalSpacing(48)
        grid.setVerticalSpacing(4)

        def _summary_cell(row: int, col: int, caption: str) -> QLabel:
            cap = QLabel(caption)
            cap.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 18px;")
            value = QLabel("–")
            value.setStyleSheet(f"color: {COLORS['off_white']}; font-size: 24px; font-weight: bold;")
            cell_layout = QVBoxLayout()
            cell_layout.setSpacing(2)
            cell_layout.addWidget(cap)
            cell_layout.addWidget(value)
            grid.addLayout(cell_layout, row, col)
            return value

        self.overview_stt_value = _summary_cell(0, 0, "Spracherkennung")
        self.overview_llm_value = _summary_cell(0, 1, "Sprachmodell")
        self.overview_hotkey_value = _summary_cell(1, 0, "Hotkey")
        self.overview_autostart_value = _summary_cell(1, 1, "Autostart")
        grid.setColumnStretch(2, 1)

        layout.addLayout(grid)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _start_engine_clicked(self):
        if not self.engine_api:
            return
        if not self.engine_api.start():
            self._show_message("NovaFlow", "Der Motor läuft bereits.")
        self._refresh_overview_status()

    def _stop_engine_clicked(self):
        if not self.engine_api:
            return
        if not self.engine_api.stop():
            self._show_message("NovaFlow", "Der Motor läuft gerade nicht.")
        self._refresh_overview_status()

    def _refresh_overview_status(self):
        """Alle Sekunde aufgerufen (siehe self._status_timer), solange das
        Fenster offen ist, damit Status und Start/Stop-Knöpfe nie veraltet
        sind, egal ob der Motor über das Tray oder hier gesteuert wurde."""
        if not hasattr(self, "overview_status_label"):
            return
        # Nur aktualisieren, solange die Seite tatsaechlich sichtbar ist,
        # spart unnoetige Datei-/Registry-Zugriffe (autostart.is_enabled())
        # jede Sekunde im Hintergrund, waehrend eine andere Seite offen ist.
        if PAGES[self.stacked.currentIndex()][0] != "Übersicht":
            return

        if self.engine_api is None:
            self.overview_status_label.setText("Status nicht verfügbar")
            return

        running = self.engine_api.is_running()
        self.overview_status_label.setText(f"Motor: {self.engine_api.status_text}")
        self.overview_status_label.setStyleSheet(
            f"color: {COLORS['cyan_neon'] if running else COLORS['danger']};"
        )
        self.overview_start_btn.setEnabled(not running)
        self.overview_stop_btn.setEnabled(running)

        self.overview_stt_value.setText(secure_config.get("STT_PROVIDER", "voxtral"))
        self.overview_llm_value.setText(secure_config.get("LLM_PROVIDER", "openrouter"))
        self.overview_hotkey_value.setText(
            secure_config.get("HOTKEY", "") or self.platform.default_hotkey()
        )
        self.overview_autostart_value.setText(
            "an" if self.platform.autostart.is_enabled() else "aus"
        )

    # Fragen/Antworten fuer die aufklappbaren Hilfe-Felder (JJ, 2026-07-28:
    # "Menuepunkt Hilfe erweitern, sodass wir Dropdown-Felder haben, wo wir
    # bestimmte Dinge noch einmal erklaeren"). Reihenfolge = Anzeigereihenfolge.
    HELP_TOPICS = [
        (
            "Wie funktioniert das Update?",
            "NovaFlow prüft automatisch alle sechs Stunden auf eine neuere Version "
            "(siehe Seite \"Update\", auch von Hand über \"Jetzt nach Updates suchen\" "
            "oder über das Tray-Menü). Unter Windows lädt ein gefundenes Update sich im "
            "Hintergrund herunter und installiert sich beim Klick auf \"Update "
            "verfügbar\" leise selbst, NovaFlow beendet sich dafür kurz und startet "
            "danach automatisch mit der neuen Version neu. Unter macOS öffnet sich "
            "stattdessen die Release-Seite im Browser zum manuellen Download.",
        ),
        (
            "Wie kann ich einen Verlaufseintrag kopieren?",
            "Auf der Seite \"Verlauf\" den gewünschten Eintrag in der Liste auswählen, "
            "dann auf \"In Zwischenablage kopieren\" klicken. Eine kurze Rückmeldung "
            "bestätigt, dass es geklappt hat. Der Text steht danach in der "
            "Zwischenablage bereit, mit Strg+V (bzw. Cmd+V) an beliebiger Stelle "
            "einfügbar.",
        ),
        (
            "Was macht der Hotkey, was der Undo-Hotkey?",
            "Der Hotkey (Seite \"Diktat\") startet die Aufnahme, solange er gedrückt "
            "gehalten wird, und beendet sie beim Loslassen. Der Undo-Hotkey ist eine "
            "davon komplett unabhängige, zweite Tastenkombination: ein kurzer Druck "
            "schickt sofort Rückgängig (Strg+Z bzw. Cmd+Z) ans aktuell aktive Fenster, "
            "falls ein eingefügtes Diktat danebenliegt. Beide lassen sich auf der Seite "
            "\"Diktat\" einstellen, leer lassen deaktiviert die jeweilige Funktion.",
        ),
        (
            "Was ist die Flowbar?",
            "Eine schmale, randlose Anzeige unten am Bildschirmrand, die erscheint, "
            "sobald der Hotkey gedrückt wird, und den aktuellen Sprechpegel zeigt. "
            "Sie verschwindet automatisch, sobald der fertige Text eingefügt wurde. "
            "Reine Rückmeldung, reagiert auf keine Klicks.",
        ),
        (
            "Was macht \"Aufnahme bei Stille automatisch beenden\"?",
            "Ist dieses Kästchen auf der Seite \"Diktat\" aktiviert, beendet NovaFlow "
            "eine laufende Aufnahme automatisch, wenn länger als der eingestellte "
            "Stille-Timeout keine Sprache mehr erkannt wird, und verarbeitet das "
            "Diktat sofort - genau wie ein manuelles Loslassen des Hotkeys. Praktisch, "
            "wenn man den Hotkey aus Versehen zu lange gedrückt hält.",
        ),
        (
            "Was ist der Rohtext-Modus?",
            "Überspringt ausschließlich den KI-Veredelungsschritt (Grammatik-/"
            "Rechtschreibkorrektur). Die mechanische Aufbereitung (Füllwörter "
            "entfernen, Wörterbuch, gesprochene Satzzeichen, Großschreibung) läuft "
            "trotzdem ganz normal weiter. Umschaltbar über die Seite \"Diktat\" oder "
            "direkt im Tray-Menü.",
        ),
        (
            "Was machen Wörterbuch, Ausschnitte, Schreibstil, Notizbuch und Verlauf?",
            "Wörterbuch: eigene Korrekturen für häufig falsch erkannte Wörter/Namen. "
            "Ausschnitte: Trigger-Wörter, die automatisch zu vollständigen Textbausteinen "
            "erweitert werden (z.B. Grußformeln). Schreibstil: Kategorie und Ton, die als "
            "Kontext-Hinweis in jede KI-Veredelung einfließen. Notizbuch: freie kurze "
            "Notizen, unabhängig vom Diktat-Verlauf. Verlauf: die letzten 50 Diktate mit "
            "Rohtext und veredelter Fassung, durchsuchbar und nach Datum filterbar.",
        ),
    ]

    def _accordion_item(self, question: str, answer: str) -> QWidget:
        """Ein einzelnes aufklappbares Hilfe-Feld (Frage als Knopf, Antwort
        darunter zunaechst eingeklappt). Reines Qt-Widget-Paar, keine
        eigene Qt-Komponente noetig."""
        container = QWidget()
        outer = QVBoxLayout()
        outer.setContentsMargins(0, 0, 0, 0)
        outer.setSpacing(0)

        toggle = QPushButton(f"▸  {question}")
        toggle.setCheckable(True)
        toggle.setCursor(Qt.CursorShape.PointingHandCursor)
        qf = QFont()
        qf.setPixelSize(22)
        qf.setBold(True)
        toggle.setFont(qf)
        toggle.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 12px 16px;
                text-align: left;
            }}
            QPushButton:hover {{
                border: 1px solid {COLORS['cyan_neon']};
            }}
        """)

        answer_label = QLabel(answer)
        answer_label.setWordWrap(True)
        af = QFont()
        af.setPixelSize(20)
        answer_label.setFont(af)
        answer_label.setStyleSheet(
            f"color: {COLORS['text_muted']}; padding: 12px 16px;"
        )
        answer_label.setVisible(False)

        def on_toggled(checked: bool):
            answer_label.setVisible(checked)
            toggle.setText(f"{'▾' if checked else '▸'}  {question}")

        toggle.toggled.connect(on_toggled)

        outer.addWidget(toggle)
        outer.addWidget(answer_label)
        container.setLayout(outer)
        return container

    def _create_help_page(self) -> QWidget:
        page = QWidget()
        outer_layout = QVBoxLayout()
        outer_layout.setSpacing(16)
        outer_layout.addWidget(self._page_title("Hilfe"))

        text = QLabel(
            "So funktioniert NovaFlow:\n\n"
            "1. Tastenkombination gedrückt halten (siehe Übersicht) und sprechen.\n"
            "2. Beim Loslassen wird das Gesagte in Text umgewandelt, sprachlich "
            "veredelt und in das gerade aktive Fenster eingefügt.\n\n"
            "Reagiert die Tastenkombination einmal nicht mehr: Rechtsklick auf das "
            "Tray-Symbol, dann \"Hotkey neu starten\" wählen. Das behebt das meist, "
            "ohne dass NovaFlow komplett neu gestartet werden muss.\n\n"
            "Läuft gar nichts mehr: hier auf der Übersicht-Seite \"Motor stoppen\" "
            "und danach \"Motor starten\" klicken."
        )
        text.setWordWrap(True)
        tf = QFont()
        tf.setPixelSize(22)
        text.setFont(tf)
        text.setStyleSheet(f"color: {COLORS['off_white']};")
        outer_layout.addWidget(text)

        # Aufklappbare Themen (JJ, 2026-07-28): stehen im Content-Bereich
        # dieser Seite, also auf der rechten Seite des Fensters (die
        # Navigation liegt links, siehe _build_sidebar), wie gewünscht.
        topics_title = QLabel("Weitere Themen")
        ttf = QFont()
        ttf.setPixelSize(22)
        ttf.setBold(True)
        topics_title.setFont(ttf)
        topics_title.setStyleSheet(f"color: {COLORS['off_white']};")
        outer_layout.addWidget(topics_title)

        topics_scroll = QScrollArea()
        topics_scroll.setWidgetResizable(True)
        topics_scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {COLORS['deep_navy']}; }}")
        topics_scroll.viewport().setStyleSheet(f"background-color: {COLORS['deep_navy']};")
        topics_content = QWidget()
        topics_content.setStyleSheet(f"background-color: {COLORS['deep_navy']};")
        topics_layout = QVBoxLayout()
        topics_layout.setSpacing(8)
        for question, answer in self.HELP_TOPICS:
            topics_layout.addWidget(self._accordion_item(question, answer))
        topics_layout.addStretch()
        topics_content.setLayout(topics_layout)
        topics_scroll.setWidget(topics_content)
        outer_layout.addWidget(topics_scroll, 1)

        link_btn = QPushButton("GitHub-Seite öffnen (Neuigkeiten, Downloads)")
        bf = QFont()
        bf.setPixelSize(24)
        bf.setBold(True)
        link_btn.setFont(bf)
        link_btn.setMinimumHeight(48)
        link_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        link_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px 28px;
            }}
        """)
        link_btn.clicked.connect(
            lambda: __import__("webbrowser").open("https://github.com/kiwerkepro-org/novaflow")
        )
        outer_layout.addWidget(link_btn)

        page.setLayout(outer_layout)
        return page

    # ------------------------------------------------------------------
    # Technische Einstellungen (config / secure_config)
    # ------------------------------------------------------------------
    def _create_recording_page(self) -> QWidget:
        default_hotkey = self.platform.default_hotkey()
        hotkey_items = ["", "ctrl_win", "ctrl_cmd", "ctrl", "alt", "shift", "f8", "f9", "f10"]
        # Undo-Hotkey (JJ, 2026-07-28): eigene, von der Aufnahme-Kombination
        # unabhaengige Tastenkombination, schickt Strg+Z/Cmd+Z ans aktive
        # Fenster, siehe interface.py _send_undo(). Leer = Funktion aus.
        undo_items = ["", "ctrl_alt_z", "ctrl_shift_z", "alt_z", "f6"]
        page = self._create_settings_page("Diktat", [
            (f"Hotkey (leer = automatisch: {default_hotkey}):",
             self._create_combo(hotkey_items), 'hotkey_combo'),
            ("Undo-Hotkey (schickt Rückgängig ans aktive Fenster, leer = aus):",
             self._create_combo(undo_items), 'undo_hotkey_combo'),
            ("Stille-Timeout in Sekunden (Auto-Stop, siehe Kästchen unten):",
             self._create_spinbox(1, 10, 3), 'silence_timeout', True),
            # secondary=True: praktisch niemand muss das je anfassen, stand
            # bisher aber genauso prominent da wie der Hotkey (JJs Kritik,
            # 2026-07-25).
            ("Sample Rate (nur bei Aufnahmeproblemen ändern):",
             self._create_spinbox(8000, 48000, 16000), 'sample_rate', True),
        ])

        # Rohtext-Modus auch hier in den Einstellungen, nicht nur ueber die
        # Tray-Schnellumschaltung (JJ, 2026-07-27: "Wozu habe ich denn die
        # Einstellungen? Das muss da drin funktionieren."). Gleiches Feld,
        # gleicher Speicherort (RAW_TEXT_MODE), Aenderung greift wie bei
        # allen anderen Feldern dieser Seite erst nach "Speichern", siehe
        # save_settings() weiter unten. Die Tray-Schnellumschaltung bleibt
        # zusaetzlich bestehen, beide schreiben denselben Wert. Einfuegen
        # in die AEUSSERE Seiten-Layout (nicht die scrollbare Feldliste),
        # exakt dasselbe Muster wie autostart_check auf der Seite
        # "Sprache & System" weiter unten.
        layout = page.layout()
        self.raw_text_mode_check = QCheckBox("Rohtext-Modus (KI-Veredelung überspringen)")
        rtf = QFont()
        rtf.setPixelSize(22)
        self.raw_text_mode_check.setFont(rtf)
        self.raw_text_mode_check.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.insertWidget(layout.count(), self.raw_text_mode_check)

        # Stille-Erkennung / Auto-Stop (JJ, 2026-07-28): beendet eine
        # laufende Aufnahme automatisch nach laengerer Sprechpause, siehe
        # interface.py _evaluate_silence(). Gleiches Muster wie
        # raw_text_mode_check direkt darueber.
        self.silence_autostop_check = QCheckBox(
            "Aufnahme bei Stille automatisch beenden und verarbeiten"
        )
        self.silence_autostop_check.setFont(rtf)
        self.silence_autostop_check.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.insertWidget(layout.count(), self.silence_autostop_check)

        layout.addLayout(self._hint_row(
            "Hotkey gedrückt halten und sprechen, beim Loslassen wird verarbeitet.",
            "Hotkey: die Tastenkombination zum Diktieren, gedrückt halten während des "
            "Sprechens. Undo-Hotkey: eine ZWEITE, unabhängige Kombination, die sofort "
            "Rückgängig (Strg+Z bzw. Cmd+Z) ans aktive Fenster schickt, falls ein Diktat "
            "danebenliegt - nutzt die Undo-Funktion des Zielprogramms selbst. Stille-Timeout: "
            "wie lange NovaFlow bei einer Sprechpause wartet, bevor die Aufnahme automatisch "
            "beendet und verarbeitet wird (nur wenn das Kästchen darüber aktiviert ist). "
            "Änderungen auf dieser Seite wirken erst nach einem Neustart von NovaFlow "
            "vollständig.",
        ))

        return page

    def _create_stt_page(self) -> QWidget:
        return self._create_settings_page("Spracherkennung", [
            ("STT Provider:", self._create_combo(["voxtral", "whisper"]), 'stt_provider'),
            ("Whisper Model Size:", self._create_combo(["tiny", "base", "small", "medium", "large-v3"]), 'whisper_model'),
            ("Whisper Device:", self._create_combo(["auto", "cuda", "cpu"]), 'whisper_device'),
        ])

    def _create_llm_page(self) -> QWidget:
        ionos_model_combo = self._create_combo([
            "mistralai/Mistral-Small-24B-Instruct",
            "meta-llama/Llama-3.3-70B-Instruct",
            "mistralai/Mistral-Nemo-Instruct-2407",
            "meta-llama/Meta-Llama-3.1-8B-Instruct",
            "mistralai/Mistral-7B-Instruct-v0.3",
        ])
        ionos_model_combo.setEditable(True)
        return self._create_settings_page("Sprachmodell", [
            ("Provider:", self._create_combo(["openrouter", "ollama", "ionos", "disabled"]), 'llm_provider'),
            ("OpenRouter Modell:", self._create_input("google/gemini-3.1-flash-lite"), 'openrouter_model'),
            ("Ollama Modell:", self._create_combo(["gemma4:e2b", "gemma4:e4b", "gemma3:4b", "mistral", "llama2"]), 'llm_model'),
            ("Ollama URL:", self._create_input("http://localhost:11434"), 'ollama_url'),
            ("IONOS Modell (Server in Deutschland, DSGVO):", ionos_model_combo, 'ionos_model'),
            ("Wortschwelle (kurze Texte überspringen LLM):", self._create_spinbox(0, 100, 10), 'word_threshold'),
        ])

    def _create_api_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)

        title = self._page_title("API-Schlüssel")
        layout.addWidget(title)
        layout.addLayout(self._hint_row(
            "Werden sicher im Credential-Speicher des Betriebssystems abgelegt, nicht im Klartext.",
            "OpenRouter-Key holen: https://openrouter.ai/keys (ein Key für Transkription "
            "über Voxtral UND für die KI-Veredelung über Gemini/Claude/Qwen). IONOS-Key "
            "holen: https://cloud.ionos.com (AI Model Hub, nur für die Text-Veredelung, "
            "Server stehen in Deutschland). Ohne Key fällt NovaFlow automatisch auf den "
            "nächsten verfügbaren Anbieter zurück (siehe Sprachmodell-Seite).",
        ))

        lbl = QLabel("OpenRouter API Key:")
        lbl.setFont(self._label_font())
        lbl.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.addWidget(lbl)

        row = QHBoxLayout()
        self.openrouter_key = QLineEdit()
        self.openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_key.setPlaceholderText("sk-or-...")
        self.openrouter_key.setMinimumHeight(46)
        self.openrouter_key.setMaximumWidth(560)
        self.openrouter_key.setStyleSheet(self._input_style())
        row.addWidget(self.openrouter_key, 1)

        toggle_btn = QPushButton("Zeigen")
        toggle_btn.setCheckable(True)
        toggle_btn.setMinimumHeight(46)
        toggle_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 22px;
            }}
            QPushButton:checked {{
                background-color: rgba(0, 224, 184, 0.15);
                color: {COLORS['cyan_neon']};
                border: 1px solid {COLORS['cyan_neon']};
            }}
        """)

        def toggle(checked):
            self.openrouter_key.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            toggle_btn.setText("Verbergen" if checked else "Zeigen")

        toggle_btn.toggled.connect(toggle)
        row.addWidget(toggle_btn)
        layout.addLayout(row)

        info = QLabel("Kostenloser Key auf openrouter.ai. Wird sicher im Zugangsdaten-Speicher des Systems abgelegt.")
        info.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 22px;")
        info.setWordWrap(True)
        layout.addWidget(info)

        lbl_ionos = QLabel("IONOS API Key (Server in Deutschland, DSGVO):")
        lbl_ionos.setFont(self._label_font())
        lbl_ionos.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.addWidget(lbl_ionos)

        row_ionos = QHBoxLayout()
        self.ionos_key = QLineEdit()
        self.ionos_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.ionos_key.setPlaceholderText("IONOS AI Model Hub Token...")
        self.ionos_key.setMinimumHeight(46)
        self.ionos_key.setMaximumWidth(560)
        self.ionos_key.setStyleSheet(self._input_style())
        row_ionos.addWidget(self.ionos_key, 1)

        toggle_ionos_btn = QPushButton("Zeigen")
        toggle_ionos_btn.setCheckable(True)
        toggle_ionos_btn.setMinimumHeight(46)
        toggle_ionos_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['text_muted']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 16px;
                font-size: 22px;
            }}
            QPushButton:checked {{
                background-color: rgba(0, 224, 184, 0.15);
                color: {COLORS['cyan_neon']};
                border: 1px solid {COLORS['cyan_neon']};
            }}
        """)

        def toggle_ionos(checked):
            self.ionos_key.setEchoMode(
                QLineEdit.EchoMode.Normal if checked else QLineEdit.EchoMode.Password
            )
            toggle_ionos_btn.setText("Verbergen" if checked else "Zeigen")

        toggle_ionos_btn.toggled.connect(toggle_ionos)
        row_ionos.addWidget(toggle_ionos_btn)
        layout.addLayout(row_ionos)

        info_ionos = QLabel(
            "Nur nötig, wenn als Sprachmodell-Provider \"ionos\" gewählt ist. "
            "Betrifft nur die Text-Veredelung nach der Transkription, "
            "gehostet im IONOS AI Model Hub in Deutschland. "
            "Key holen auf cloud.ionos.com."
        )
        info_ionos.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 22px;")
        info_ionos.setWordWrap(True)
        layout.addWidget(info_ionos)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _create_lang_page(self) -> QWidget:
        page = self._create_settings_page("Sprache & System", [
            ("Sprache:", self._create_combo(["de", "en"]), 'language'),
            ("Log-Level:", self._create_combo(["DEBUG", "INFO", "WARNING", "ERROR"]), 'log_level'),
        ])
        layout = page.layout()
        self.autostart_check = QCheckBox("Automatisch mit dem System starten")
        af = QFont()
        af.setPixelSize(22)
        self.autostart_check.setFont(af)
        self.autostart_check.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.insertWidget(layout.count() - 1, self.autostart_check)

        # Verschlüsseltes Backup (JJ, 2026-07-27): buendelt Woerterbuch,
        # Ausschnitte, Notizbuch, Schreibstil, Verlauf und die .env zu einer
        # einzigen, passwortgeschuetzten Datei, siehe utils/backup.py.
        backup_title = QLabel("Verschlüsseltes Backup")
        btf = QFont()
        btf.setPixelSize(24)
        btf.setBold(True)
        backup_title.setFont(btf)
        backup_title.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.insertWidget(layout.count() - 1, backup_title)

        backup_hint = QLabel(
            "Sichert Wörterbuch, Ausschnitte, Notizbuch, Schreibstil und Verlauf "
            "als eine einzige, mit deinem Passwort verschlüsselte Datei."
        )
        backup_hint.setWordWrap(True)
        backup_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 20px;")
        layout.insertWidget(layout.count() - 1, backup_hint)

        backup_row = QHBoxLayout()
        backup_create_btn = self._icon_button("download", "Backup erstellen...")
        backup_create_btn.clicked.connect(self._create_backup_clicked)
        backup_restore_btn = self._icon_button("upload", "Backup wiederherstellen...")
        backup_restore_btn.clicked.connect(self._restore_backup_clicked)
        backup_row.addWidget(backup_create_btn)
        backup_row.addWidget(backup_restore_btn)
        layout.insertLayout(layout.count() - 1, backup_row)

        return page

    def _prompt_password(self, title: str, label: str, confirm: bool = False) -> Optional[str]:
        """Fragt ein Passwort in einem zum App-Design passenden Dialog ab
        (KEIN QInputDialog, siehe Begruendung bei _show_message: ungestylte
        Systemdialoge sind hier bewusst nicht erwuenscht).

        confirm=True verlangt eine zweite, identische Eingabe (beim
        Erstellen eines Backups), das verhindert ein Backup, das sich der
        Nutzer durch einen Tippfehler selbst unbrauchbar macht. Gibt None
        zurueck, wenn abgebrochen oder (bei confirm=True) die beiden
        Eingaben nicht uebereinstimmen.
        """
        dialog = QDialog(self)
        dialog.setWindowTitle(title)
        dialog.setStyleSheet(f"QDialog {{ background-color: {COLORS['deep_navy']}; }}")
        layout = QVBoxLayout()

        lbl = QLabel(label)
        lbl.setWordWrap(True)
        lbl.setStyleSheet(f"color: {COLORS['off_white']}; font-size: 20px;")
        layout.addWidget(lbl)

        pw_input = QLineEdit()
        pw_input.setEchoMode(QLineEdit.EchoMode.Password)
        pw_input.setStyleSheet(self._input_style())
        pw_input.setMinimumHeight(44)
        layout.addWidget(pw_input)

        pw_confirm_input = None
        if confirm:
            pw_confirm_input = QLineEdit()
            pw_confirm_input.setEchoMode(QLineEdit.EchoMode.Password)
            pw_confirm_input.setPlaceholderText("Passwort wiederholen")
            pw_confirm_input.setStyleSheet(self._input_style())
            pw_confirm_input.setMinimumHeight(44)
            layout.addWidget(pw_confirm_input)

        error_label = QLabel("")
        error_label.setStyleSheet(f"color: {COLORS['danger']}; font-size: 18px;")
        error_label.setWordWrap(True)
        layout.addWidget(error_label)

        btn_row = QHBoxLayout()
        ok_btn = QPushButton("OK")
        cancel_btn = QPushButton("Abbrechen")
        for b in (ok_btn, cancel_btn):
            b.setMinimumHeight(40)
            b.setCursor(Qt.CursorShape.PointingHandCursor)
            b.setStyleSheet(f"""
                QPushButton {{
                    background-color: transparent;
                    color: {COLORS['cyan_neon']};
                    border: 1px solid {COLORS['cyan_neon']};
                    border-radius: 6px;
                    padding: 6px 18px;
                    font-size: 18px;
                }}
                QPushButton:hover {{ background-color: rgba(0, 224, 184, 0.15); }}
            """)
        btn_row.addWidget(ok_btn)
        btn_row.addWidget(cancel_btn)
        layout.addLayout(btn_row)

        dialog.setLayout(layout)

        result: dict = {"password": None}

        def accept():
            pw = pw_input.text()
            if not pw:
                error_label.setText("Bitte ein Passwort eingeben.")
                return
            if confirm and pw != pw_confirm_input.text():
                error_label.setText("Die beiden Passwörter stimmen nicht überein.")
                return
            result["password"] = pw
            dialog.accept()

        ok_btn.clicked.connect(accept)
        cancel_btn.clicked.connect(dialog.reject)
        pw_input.returnPressed.connect(accept)

        dialog.exec()
        return result["password"]

    def _create_backup_clicked(self):
        password = self._prompt_password(
            "Backup erstellen",
            "Passwort für das verschlüsselte Backup festlegen. Ohne dieses "
            "Passwort lässt sich das Backup später nicht mehr entschlüsseln, "
            "es gibt keine Wiederherstellung ohne Passwort.",
            confirm=True,
        )
        if not password:
            return

        path, _ = QFileDialog.getSaveFileName(
            self, "Backup speichern unter", "novaflow-backup.nfbackup",
            "NovaFlow-Backup (*.nfbackup);;Alle Dateien (*)",
        )
        if not path:
            return

        try:
            from utils.backup import create_encrypted_backup
            result = create_encrypted_backup(Path(path), password)
        except Exception as e:
            self._show_message("Backup fehlgeschlagen", f"Backup konnte nicht erstellt werden: {e}", warning=True)
            return

        if result["included_files"]:
            included = ", ".join(result["included_files"])
        else:
            included = "keine (Wörterbuch, Verlauf usw. sind noch leer)"
        self._show_message(
            "Backup erstellt",
            f"Verschlüsseltes Backup gespeichert:\n{result['path']}\n\nEnthalten: {included}",
        )

    def _restore_backup_clicked(self):
        path, _ = QFileDialog.getOpenFileName(
            self, "Backup auswählen", "",
            "NovaFlow-Backup (*.nfbackup);;Alle Dateien (*)",
        )
        if not path:
            return

        password = self._prompt_password("Backup wiederherstellen", "Passwort des Backups eingeben:")
        if not password:
            return

        confirmed = self._confirm(
            "Backup wiederherstellen",
            "Das überschreibt Wörterbuch, Ausschnitte, Notizbuch, Schreibstil und "
            "Verlauf mit dem Stand aus dem Backup. Der aktuelle Stand geht dabei "
            "verloren. Fortfahren?",
        )
        if not confirmed:
            return

        try:
            from utils.backup import restore_encrypted_backup
            result = restore_encrypted_backup(Path(path), password)
        except InvalidTag:
            self._show_message(
                "Wiederherstellung fehlgeschlagen",
                "Falsches Passwort oder eine beschädigte Backup-Datei.",
                warning=True,
            )
            return
        except Exception as e:
            self._show_message("Wiederherstellung fehlgeschlagen", f"{e}", warning=True)
            return

        self.load_settings()
        restored = ", ".join(result["restored_files"]) if result["restored_files"] else "keine Dateien"
        note = ""
        if ".env" in result["restored_files"]:
            note = "\n\nHinweis: Änderungen aus der .env (z.B. API-Schlüssel-Konfiguration) werden erst nach einem Neustart von NovaFlow wirksam."
        self._show_message("Wiederherstellung abgeschlossen", f"Wiederhergestellt: {restored}{note}")

    def _confirm(self, title: str, text: str) -> bool:
        """Ja/Nein-Rueckfrage im App-Design, fuer Aktionen, die bestehende
        Daten unwiderruflich ueberschreiben (siehe _show_message fuer die
        Begruendung gegen unschoene System-Standarddialoge)."""
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Warning)
        box.setStandardButtons(QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No)
        box.setDefaultButton(QMessageBox.StandardButton.No)
        box.setStyleSheet(f"""
            QMessageBox {{ background-color: {COLORS['deep_navy']}; }}
            QMessageBox QLabel {{ color: {COLORS['off_white']}; font-size: 22px; }}
            QPushButton {{
                background-color: transparent;
                color: {COLORS['danger']};
                border: 1px solid {COLORS['danger']};
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 20px;
                min-width: 60px;
            }}
            QPushButton:hover {{ background-color: rgba(248, 113, 113, 0.15); }}
        """)
        return box.exec() == QMessageBox.StandardButton.Yes

    def _create_update_page(self) -> QWidget:
        """Zeigt die installierte Version und erlaubt eine Prüfung von Hand.

        Bewusst als eigener Menuepunkt und nicht nur im Tray-Menue: die
        automatische Pruefung laeuft nur alle sechs Stunden, ein in dieser
        Zeit veroeffentlichtes Update wuerde man sonst erst verspaetet sehen.
        Ausserdem gehoert die Versionsnummer sichtbar in die Oberflaeche, statt
        dass man dafuer in die Systemsteuerung schauen muss.
        """
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)
        layout.addWidget(self._page_title("Update"))
        layout.addLayout(self._hint_row(
            "NovaFlow prüft automatisch alle sechs Stunden auf eine neuere Version.",
            "Unter Windows lädt ein gefundenes Update sich im Hintergrund herunter und "
            "installiert sich beim Klick auf \"Update verfügbar\" leise selbst, NovaFlow "
            "beendet sich dafür kurz und startet mit der neuen Version neu. Unter macOS "
            "öffnet sich stattdessen die Release-Seite im Browser, dort lädst und "
            "installierst du die neue Version von Hand (macOS-Installer sind aktuell nicht "
            "signiert, siehe NOTES.md).",
        ))

        version = get_current_version() or "unbekannt"
        self.installed_version_label = QLabel(f"Installierte Version:  {version}")
        vf = QFont()
        vf.setPixelSize(24)
        vf.setBold(True)
        self.installed_version_label.setFont(vf)
        self.installed_version_label.setStyleSheet(f"color: {COLORS['cyan_neon']};")
        layout.addWidget(self.installed_version_label)

        self.update_status_label = QLabel(
            "Noch nicht geprüft. NovaFlow schaut automatisch alle sechs Stunden nach, "
            "mit dem Knopf unten kannst du jederzeit sofort nachsehen."
        )
        sf = QFont()
        sf.setPixelSize(22)
        self.update_status_label.setFont(sf)
        self.update_status_label.setWordWrap(True)
        self.update_status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        layout.addWidget(self.update_status_label)

        self.check_update_btn = QPushButton("Jetzt nach Updates suchen")
        bf = QFont()
        bf.setPixelSize(24)
        bf.setBold(True)
        self.check_update_btn.setFont(bf)
        self.check_update_btn.setMinimumHeight(48)
        self.check_update_btn.setMaximumWidth(520)
        self.check_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.check_update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['cyan_neon']};
                color: {COLORS['deep_navy']};
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_muted']};
            }}
        """)
        self.check_update_btn.clicked.connect(self._check_for_update_clicked)
        layout.addWidget(self.check_update_btn)

        # Erscheint erst, wenn eine Pruefung tatsaechlich ein Update gefunden
        # hat. Vorher musste man dafuer immer erst das Einstellungsfenster
        # schliessen und im Tray-Menue auf "Update verfuegbar" klicken, das
        # war unnoetig umstaendlich (JJ, 2026-07-25).
        self.install_update_btn = QPushButton("Update installieren")
        self.install_update_btn.setFont(bf)
        self.install_update_btn.setMinimumHeight(48)
        self.install_update_btn.setMaximumWidth(520)
        self.install_update_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.install_update_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['cyan_neon']};
                color: {COLORS['deep_navy']};
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
            }}
            QPushButton:disabled {{
                background-color: {COLORS['border']};
                color: {COLORS['text_muted']};
            }}
        """)
        self.install_update_btn.clicked.connect(self._install_update_clicked)
        self.install_update_btn.setVisible(False)
        layout.addWidget(self.install_update_btn)

        self.open_release_btn = QPushButton("Download-Seite im Browser öffnen")
        self.open_release_btn.setFont(bf)
        self.open_release_btn.setMinimumHeight(48)
        self.open_release_btn.setMaximumWidth(520)
        self.open_release_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.open_release_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
                padding: 12px 28px;
            }}
        """)
        self.open_release_btn.clicked.connect(self._open_release_page)
        layout.addWidget(self.open_release_btn)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _open_release_page(self):
        import webbrowser
        url = getattr(self, "_release_url", None) or \
            "https://github.com/kiwerkepro-org/novaflow/releases/latest"
        webbrowser.open(url)

    def _check_for_update_clicked(self):
        """Prüft sofort und meldet IMMER ein Ergebnis zurück.

        Anders als die automatische Prüfung im Hintergrund, die bei
        "nichts Neues" bewusst schweigt: wer hier selbst klickt, will eine
        Rueckmeldung sehen, auch wenn alles aktuell ist.

        WICHTIG: die Pruefung selbst laeuft NICHT hier im GUI-Thread,
        sondern ueber engine_api.check_for_update_async() in einem
        Hintergrund-Thread (siehe EngineController in novaflow.pyw). Vorher
        rief diese Methode check_for_update() direkt und blockierend auf,
        das liess das ganze Fenster fuer die Dauer der Netzwerkabfrage
        einfrieren und Windows zeigte "Keine Rückmeldung" im Titel an
        (JJ, 2026-07-25) - genau die gleiche Ursache wie beim fruehreren
        Tray-Einfrieren.
        """
        if self.engine_api is None:
            self.update_status_label.setStyleSheet(f"color: {COLORS['danger']};")
            self.update_status_label.setText(
                "Update-Prüfung gerade nicht verfügbar (keine Verbindung zur Engine)."
            )
            return

        self.check_update_btn.setEnabled(False)
        self.check_update_btn.setText("Suche nach Updates...")
        self.install_update_btn.setVisible(False)
        self.update_status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.update_status_label.setText("Frage GitHub ab, einen Moment bitte...")

        self.engine_api.check_for_update_async(True, self._on_update_check_result)

    def _on_update_check_result(self, info: dict, manual: bool):
        """Wird ueber QueuedConnection im GUI-Thread aufgerufen, sobald der
        Hintergrund-Check fertig ist (siehe EngineController.check_for_update_async)."""
        self.check_update_btn.setEnabled(True)
        self.check_update_btn.setText("Jetzt nach Updates suchen")
        self._release_url = info.get("release_url") or None

        current = info.get("current_version") or "unbekannt"
        self.installed_version_label.setText(f"Installierte Version:  {current}")

        if info.get("error"):
            self.install_update_btn.setVisible(False)
            self.update_status_label.setStyleSheet(f"color: {COLORS['danger']};")
            self.update_status_label.setText(
                f"Prüfung fehlgeschlagen: {info['error']}\n"
                "Besteht eine Internetverbindung?"
            )
            return

        if info.get("available"):
            latest = info.get("latest_version", "?")
            self.update_status_label.setStyleSheet(f"color: {COLORS['cyan_neon']};")
            self.update_status_label.setText(
                f"Version {latest} steht bereit. Direkt hier auf "
                "\"Update installieren\" klicken, oder unten die "
                "Download-Seite öffnen."
            )
            self.install_update_btn.setText(f"Update installieren (v{latest})")
            self.install_update_btn.setEnabled(True)
            self.install_update_btn.setVisible(True)
            return

        self.install_update_btn.setVisible(False)
        self.update_status_label.setStyleSheet(f"color: {COLORS['off_white']};")
        self.update_status_label.setText(
            f"NovaFlow ist aktuell. Es gibt keine neuere Version als {current}."
        )

    def _install_update_clicked(self):
        """Laedt das gefundene Update herunter und installiert es, direkt
        aus dem Einstellungsfenster heraus, ohne Umweg ueber das Tray-Menü.

        Download laeuft in EngineController.install_update() in einem
        Hintergrund-Thread, blockiert also auch hier nicht die Oberflaeche.
        NovaFlow beendet sich danach komplett, damit der Installer die
        Programmdateien ersetzen kann, das Fenster schliesst sich dabei
        einfach mit.
        """
        if self.engine_api is None or not getattr(self.engine_api, "pending_update", None):
            return

        self.install_update_btn.setEnabled(False)
        self.check_update_btn.setEnabled(False)
        self.update_status_label.setStyleSheet(f"color: {COLORS['text_muted']};")
        self.update_status_label.setText("Update wird heruntergeladen...")

        def _on_error(error):
            self.install_update_btn.setEnabled(True)
            self.check_update_btn.setEnabled(True)
            self.update_status_label.setStyleSheet(f"color: {COLORS['danger']};")
            self.update_status_label.setText(
                f"Download fehlgeschlagen: {error}\nBitte manuell von GitHub laden."
            )

        self.engine_api.install_update(
            self.engine_api.pending_update,
            on_progress=lambda msg: self.update_status_label.setText(msg),
            on_error=_on_error,
        )

    def _create_settings_page(self, title: str, fields: list) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)

        layout.addWidget(self._page_title(title))

        scroll = QScrollArea()
        scroll.setWidgetResizable(True)
        scroll.setStyleSheet(f"QScrollArea {{ border: none; background-color: {COLORS['deep_navy']}; }}")
        scroll.viewport().setStyleSheet(f"background-color: {COLORS['deep_navy']};")

        content = QWidget()
        content.setStyleSheet(f"background-color: {COLORS['deep_navy']};")
        content_layout = QVBoxLayout()
        content_layout.setSpacing(18)

        for field in fields:
            # Optionales 4. Element "secondary=True" stuft ein Feld sichtbar
            # zurueck (kleinere, gedaempfte Beschriftung statt der normalen
            # fetten 14pt), fuer Werte, die praktisch niemand anfasst (z.B.
            # Sample Rate), aber trotzdem irgendwo zugaenglich sein sollen,
            # ohne mit den tatsaechlich wichtigen Feldern gleichrangig zu
            # wirken (JJs Kritik an den Screenshots, 2026-07-25).
            field_label, field_widget, attr_name = field[0], field[1], field[2]
            secondary = field[3] if len(field) > 3 else False
            lbl = QLabel(field_label)
            if secondary:
                lbl.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 18px;")
            else:
                lbl.setFont(self._label_font())
                lbl.setStyleSheet(f"color: {COLORS['off_white']};")
            content_layout.addWidget(lbl)
            content_layout.addWidget(field_widget)
            setattr(self, attr_name, field_widget)

        content_layout.addStretch()
        content.setLayout(content_layout)
        scroll.setWidget(content)

        layout.addWidget(scroll)
        page.setLayout(layout)
        return page

    # ------------------------------------------------------------------
    # Bonus-Funktionen (Stores)
    # ------------------------------------------------------------------
    def _create_dictionary_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.addWidget(self._page_title("Wörterbuch"))
        layout.addLayout(self._hint_row(
            "Korrigiert häufige Fehlerkennungen automatisch, bevor die KI-Veredelung läuft.",
            "Links steht, was Whisper/Voxtral fälschlich erkennt (z.B. 'nowa flow'), rechts "
            "die gewünschte Schreibweise (z.B. 'NovaFlow'). Über \"Vokabular importieren...\" "
            "lässt sich eine Textdatei einlesen: eine Zeile pro Fachbegriff erzwingt dessen "
            "exakte Schreibweise, eine Zeile im Format \"falsch=richtig\" legt stattdessen "
            "eine Korrektur an. Kommentarzeilen (beginnend mit #) und Leerzeilen werden "
            "beim Import übersprungen.",
        ))

        self.dict_list = QListWidget()
        self.dict_list.setStyleSheet(self._list_style())
        # Wachsen bis zu dieser Deckelhoehe, statt bei wenigen Eintraegen
        # unnoetig viel Leerflaeche ueber einem gequetschten Formular zu
        # zeigen (JJs Kritik an den Screenshots, 2026-07-25). Darueber
        # hinaus wird ganz normal gescrollt.
        self.dict_list.setMinimumHeight(200)
        self.dict_list.setMaximumHeight(360)
        layout.addWidget(self.dict_list, 1)

        # Eingaben und Aktionen in getrennten Zeilen, dasselbe Muster wie bei
        # Ausschnitte/Notizbuch: vorher stand "Hinzufügen" hier inline in der
        # Eingabezeile, "Löschen" dagegen als eigene Zeile darunter, obwohl
        # beide Seiten dieselbe Schluessel-Wert-Zuordnung sind (JJs Kritik an
        # den Screenshots, 2026-07-25).
        form = QHBoxLayout()
        self.dict_spoken_input = QLineEdit()
        self.dict_spoken_input.setPlaceholderText("Falsch erkannt (z.B. 'nowa flow')")
        self.dict_spoken_input.setStyleSheet(self._input_style())
        self.dict_spoken_input.setMinimumHeight(44)
        self.dict_correction_input = QLineEdit()
        self.dict_correction_input.setPlaceholderText("Korrektur (z.B. 'NovaFlow')")
        self.dict_correction_input.setStyleSheet(self._input_style())
        self.dict_correction_input.setMinimumHeight(44)
        form.addWidget(self.dict_spoken_input, 1)
        form.addWidget(self.dict_correction_input, 1)
        layout.addLayout(form)

        btn_row = QHBoxLayout()
        add_btn = self._icon_button("add", "Hinzufügen")
        add_btn.clicked.connect(self._add_dictionary_entry)
        del_btn = self._icon_button("delete", "Ausgewählten Eintrag löschen")
        del_btn.clicked.connect(self._delete_dictionary_entry)
        import_btn = self._icon_button("upload", "Vokabular importieren...")
        import_btn.clicked.connect(self._import_dictionary_file)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        btn_row.addWidget(import_btn)
        layout.addLayout(btn_row)

        import_hint = QLabel(
            "Import liest eine Textdatei ein: ein Fachbegriff pro Zeile "
            "(z.B. \"TensorFlow\") erzwingt die exakte Schreibweise, eine "
            "Zeile mit \"falsch=richtig\" legt eine Korrektur an."
        )
        import_hint.setWordWrap(True)
        import_hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 18px;")
        layout.addWidget(import_hint)

        # Faengt die Deckelhoehe der Liste oben ab: Restplatz landet hier als
        # Leerflaeche statt die Liste ueber die Deckelhoehe hinauszuzwingen.
        layout.addStretch()

        page.setLayout(layout)
        return page

    def _import_dictionary_file(self):
        """Importiert Vokabular/Korrekturen aus einer vom Nutzer gewaehlten
        Textdatei in das bestehende Woerterbuch (JJ, 2026-07-27). Die
        eigentliche Zeilen-Logik steckt bewusst NICHT hier, sondern in der
        reinen, UI-unabhaengigen Funktion parse_vocabulary_text() in
        utils/dictionary_store.py, damit sie sich ohne PyQt6 testen laesst."""
        path, _ = QFileDialog.getOpenFileName(
            self,
            "Vokabular importieren",
            "",
            "Textdateien (*.txt *.csv);;Alle Dateien (*)",
        )
        if not path:
            return

        try:
            raw_bytes = Path(path).read_bytes()
        except Exception as e:
            self._show_message("Import fehlgeschlagen", f"Datei konnte nicht gelesen werden: {e}", warning=True)
            return

        # Robust gegen Dateien, die nicht in UTF-8 gespeichert wurden (z.B.
        # aus Excel oder Notepad exportierte Listen landen unter Windows
        # oft in CP1252/Latin-1). Erst UTF-8 versuchen, bei Fehlschlag mit
        # der Windows-Standardkodierung weiterlesen, statt den ganzen
        # Import an einem einzigen falschen Byte scheitern zu lassen.
        try:
            text = raw_bytes.decode("utf-8")
        except UnicodeDecodeError:
            text = raw_bytes.decode("cp1252", errors="replace")

        pairs = parse_vocabulary_text(text)
        if not pairs:
            self._show_message(
                "Import", "In der Datei wurden keine verwertbaren Zeilen gefunden.", warning=True
            )
            return

        result = dictionary_store.import_entries(pairs)
        self._reload_dictionary_list()

        parts = [f"{result['added']} neue Einträge übernommen."]
        if result["skipped"]:
            parts.append(f"{result['skipped']} bereits vorhanden, übersprungen.")
        self._show_message("Import abgeschlossen", " ".join(parts))

    def _reload_dictionary_list(self):
        self.dict_list.clear()
        for entry in dictionary_store.get_entries():
            item = QListWidgetItem(f"{entry['spoken']}  →  {entry['correction']}")
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self.dict_list.addItem(item)

    def _add_dictionary_entry(self):
        spoken = self.dict_spoken_input.text().strip()
        correction = self.dict_correction_input.text().strip()
        if not spoken or not correction:
            return
        dictionary_store.add_entry(spoken, correction)
        self.dict_spoken_input.clear()
        self.dict_correction_input.clear()
        self._reload_dictionary_list()

    def _delete_dictionary_entry(self):
        item = self.dict_list.currentItem()
        if not item:
            return
        dictionary_store.delete_entry(item.data(Qt.ItemDataRole.UserRole))
        self._reload_dictionary_list()

    def _create_snippets_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.addWidget(self._page_title("Ausschnitte"))
        layout.addLayout(self._hint_row(
            "Trigger-Wörter werden beim Diktat automatisch zu vollständigen Textbausteinen erweitert.",
            "Beispiel: Trigger-Wort 'mfg' mit Text 'Mit freundlichen Grüßen' hinterlegen - "
            "sobald 'mfg' in einem Diktat vorkommt, wird es automatisch durch den vollen Text "
            "ersetzt. Praktisch für wiederkehrende Grußformeln, Signaturen oder Textbausteine, "
            "die sonst jedes Mal von Hand geschrieben werden müssten.",
        ))

        self.snippets_list = QListWidget()
        self.snippets_list.setStyleSheet(self._list_style())
        self.snippets_list.setMinimumHeight(200)
        self.snippets_list.setMaximumHeight(360)
        layout.addWidget(self.snippets_list, 1)

        form = QVBoxLayout()
        self.snippet_trigger_input = QLineEdit()
        self.snippet_trigger_input.setPlaceholderText("Trigger-Wort (z.B. 'mfg')")
        self.snippet_trigger_input.setStyleSheet(self._input_style())
        self.snippet_trigger_input.setMinimumHeight(44)
        self.snippet_expansion_input = QTextEdit()
        self.snippet_expansion_input.setPlaceholderText("Ausgeschriebener Text (z.B. 'Mit freundlichen Grüßen')")
        self.snippet_expansion_input.setStyleSheet(self._input_style())
        self.snippet_expansion_input.setMaximumHeight(80)
        form.addWidget(self.snippet_trigger_input)
        form.addWidget(self.snippet_expansion_input)

        btn_row = QHBoxLayout()
        add_btn = self._icon_button("add", "Hinzufügen")
        add_btn.clicked.connect(self._add_snippet_entry)
        del_btn = self._icon_button("delete", "Ausgewählten Eintrag löschen")
        del_btn.clicked.connect(self._delete_snippet_entry)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        form.addLayout(btn_row)

        layout.addLayout(form)
        layout.addStretch()
        page.setLayout(layout)
        return page

    def _reload_snippets_list(self):
        self.snippets_list.clear()
        for entry in snippets_store.get_entries():
            preview = entry["expansion"][:60] + ("…" if len(entry["expansion"]) > 60 else "")
            item = QListWidgetItem(f"{entry['trigger']}  →  {preview}")
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self.snippets_list.addItem(item)

    def _add_snippet_entry(self):
        trigger = self.snippet_trigger_input.text().strip()
        expansion = self.snippet_expansion_input.toPlainText().strip()
        if not trigger or not expansion:
            return
        snippets_store.add_entry(trigger, expansion)
        self.snippet_trigger_input.clear()
        self.snippet_expansion_input.clear()
        self._reload_snippets_list()

    def _delete_snippet_entry(self):
        item = self.snippets_list.currentItem()
        if not item:
            return
        snippets_store.delete_entry(item.data(Qt.ItemDataRole.UserRole))
        self._reload_snippets_list()

    def _create_style_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(18)
        layout.addWidget(self._page_title("Schreibstil"))
        layout.addLayout(self._hint_row(
            "Kategorie und Ton fließen als Kontext-Hinweis in die KI-Veredelung ein.",
            "Wirkt auf JEDES Diktat, nicht nur auf einzelne - die KI bekommt Kategorie und "
            "Ton als zusätzlichen Hinweis mitgegeben (z.B. 'Kontext: E-Mail' und 'Schreibstil: "
            "Formell und professionell'). Für unterschiedliche Kontexte (mal locker, mal "
            "formell) gibt es aktuell nur diese eine globale Einstellung, kein Umschalten "
            "je Programm.",
        ))

        cat_lbl = QLabel("Kategorie:")
        cat_lbl.setFont(self._label_font())
        cat_lbl.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.addWidget(cat_lbl)
        self.style_category = self._create_combo(CATEGORIES)
        layout.addWidget(self.style_category)

        tone_lbl = QLabel("Ton:")
        tone_lbl.setFont(self._label_font())
        tone_lbl.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.addWidget(tone_lbl)
        self.style_tone = self._create_combo(TONES)
        layout.addWidget(self.style_tone)

        save_style_btn = QPushButton("Schreibstil speichern")
        save_style_btn.setMinimumHeight(44)
        save_style_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['cyan_neon']};
                color: {COLORS['deep_navy']};
                border: none;
                border-radius: 8px;
                padding: 10px 20px;
                font-size: 24px;
                font-weight: bold;
            }}
        """)
        save_style_btn.clicked.connect(self._save_style)
        layout.addWidget(save_style_btn)

        layout.addStretch()
        page.setLayout(layout)
        return page

    def _save_style(self):
        style_store.set_style(
            category=self.style_category.currentText(),
            tone=self.style_tone.currentText(),
        )
        self._show_message("Gespeichert", "Schreibstil wurde gespeichert.")

    def _create_notes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.addWidget(self._page_title("Notizbuch"))

        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet(self._list_style())
        self.notes_list.setMinimumHeight(200)
        self.notes_list.setMaximumHeight(360)
        layout.addWidget(self.notes_list, 1)

        self.note_input = QTextEdit()
        self.note_input.setPlaceholderText("Neue Notiz...")
        self.note_input.setMaximumHeight(80)
        self.note_input.setStyleSheet(self._input_style())
        layout.addWidget(self.note_input)

        btn_row = QHBoxLayout()
        add_btn = self._icon_button("add", "Hinzufügen")
        add_btn.clicked.connect(self._add_note)
        del_btn = self._icon_button("delete", "Ausgewählte Notiz löschen")
        del_btn.clicked.connect(self._delete_note)
        btn_row.addWidget(add_btn)
        btn_row.addWidget(del_btn)
        layout.addLayout(btn_row)
        layout.addStretch()

        page.setLayout(layout)
        return page

    def _reload_notes_list(self):
        self.notes_list.clear()
        for entry in notes_store.get_entries():
            preview = entry["text"][:80] + ("…" if len(entry["text"]) > 80 else "")
            item = QListWidgetItem(f"[{entry['created_at'][:16].replace('T', ' ')}] {preview}")
            item.setData(Qt.ItemDataRole.UserRole, entry["id"])
            self.notes_list.addItem(item)

    def _add_note(self):
        text = self.note_input.toPlainText().strip()
        if not text:
            return
        notes_store.add_entry(text)
        self.note_input.clear()
        self._reload_notes_list()

    def _delete_note(self):
        item = self.notes_list.currentItem()
        if not item:
            return
        notes_store.delete_entry(item.data(Qt.ItemDataRole.UserRole))
        self._reload_notes_list()

    def _create_history_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.addWidget(self._page_title("Verlauf"))
        layout.addLayout(self._hint_row(
            "Die letzten Diktate. Aktualisiert sich automatisch, solange diese Seite offen ist.",
            "Zeigt die letzten 50 Diktate mit Rohtext und veredelter Fassung. Lange "
            "Ziffernfolgen (z.B. eine versehentlich diktierte Kontonummer) werden vor dem "
            "Speichern automatisch maskiert (nur die letzten zwei Ziffern bleiben sichtbar) - "
            "das betrifft NUR den gespeicherten Verlauf, nicht den tatsächlich eingefügten "
            "Text. Die Suche durchsucht Rohtext UND veredelten Text gleichzeitig.",
        ))

        # Statistik-Kachel (JJ, 2026-07-27): die Rohdaten (raw/text/created_at
        # je Diktat) liegen dank history_store.add() laengst vollstaendig
        # vor, hier wird nur noch ausgewertet und angezeigt, siehe
        # compute_history_stats() in utils/history_store.py. Rechnet
        # ausschliesslich mit dem, was aktuell im Verlauf steht (also
        # hoechstens die letzten MAX_ENTRIES Diktate), exakt derselbe
        # Datenstand, den die Liste darunter ohnehin zeigt.
        self.history_stats_frame = QFrame()
        self.history_stats_frame.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel_grey']};
                border: 1px solid {COLORS['border']};
                border-radius: 10px;
            }}
        """)
        stats_layout = QVBoxLayout()
        stats_layout.setContentsMargins(16, 12, 16, 12)
        stats_layout.setSpacing(4)
        self.history_stats_label = QLabel("")
        self.history_stats_label.setWordWrap(True)
        self.history_stats_label.setStyleSheet(
            f"color: {COLORS['off_white']}; font-size: 20px; border: none;"
        )
        stats_layout.addWidget(self.history_stats_label)
        self.history_stats_frame.setLayout(stats_layout)
        layout.addWidget(self.history_stats_frame)

        # Volltextsuche + Datumsfilter (JJ, 2026-07-27): durchsucht Rohtext
        # UND veredelten Text (siehe filter_history_entries() in
        # utils/history_store.py), damit ein Diktat auch dann gefunden wird,
        # wenn der gesuchte Begriff nur in der unveredelten Version steckt.
        search_row = QHBoxLayout()
        self.history_search_input = QLineEdit()
        self.history_search_input.setPlaceholderText("Verlauf durchsuchen...")
        self.history_search_input.setStyleSheet(self._input_style())
        self.history_search_input.setMinimumHeight(44)
        self.history_search_input.textChanged.connect(self._apply_history_filter)
        search_row.addWidget(self.history_search_input, 1)

        self.history_date_filter = self._create_combo(
            ["Alle", "Heute", "Letzte 7 Tage", "Letzte 30 Tage"]
        )
        # Reihenfolge MUSS zu DATE_FILTERS in utils/history_store.py passen,
        # der Index der Combobox waehlt direkt den Eintrag dort aus.
        self.history_date_filter.currentIndexChanged.connect(self._apply_history_filter)
        search_row.addWidget(self.history_date_filter)
        layout.addLayout(search_row)

        self.history_no_results_label = QLabel("Keine Treffer für diese Suche/diesen Filter.")
        self.history_no_results_label.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 20px;")
        self.history_no_results_label.setVisible(False)
        layout.addWidget(self.history_no_results_label)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet(self._list_style())
        self.history_list.setMinimumHeight(200)
        self.history_list.setMaximumHeight(360)
        layout.addWidget(self.history_list, 1)

        btn_row = QHBoxLayout()
        copy_btn = self._icon_button("download", "In Zwischenablage kopieren")
        copy_btn.clicked.connect(self._copy_history_entry)
        clear_btn = self._icon_button("delete", "Verlauf leeren", danger=True)
        clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        # Stille Rueckmeldung nach dem Kopieren (JJ, 2026-07-27): vorher
        # passierte beim Klick auf "In Zwischenablage kopieren" sichtbar gar
        # nichts, ohne Bestaetigung war nicht erkennbar, ob der Klick
        # ueberhaupt etwas bewirkt hat. Bewusst KEIN QMessageBox (siehe
        # _show_message) - das wuerde fuer eine derart nebensaechliche
        # Aktion einen Klick auf "Ok" erzwingen. Stattdessen ein Hinweistext
        # unter den Knoepfen, der nach kurzer Zeit von selbst wieder
        # verschwindet.
        self.history_copy_feedback = QLabel("")
        self.history_copy_feedback.setStyleSheet(
            f"color: {COLORS['cyan_neon']}; font-size: 20px;"
        )
        layout.addWidget(self.history_copy_feedback)

        layout.addStretch()

        page.setLayout(layout)
        self._history_cache_len = -1
        return page

    def _load_history(self):
        """Holt den aktuellen Stand aus dem Store. Statistik rechnet immer
        mit ALLEN Eintraegen (siehe compute_history_stats), unabhaengig von
        einer evtl. aktiven Suche/einem Filter, sonst waere "Statistik
        aendert sich beim Tippen in die Suche" verwirrend. Die Liste selbst
        respektiert dagegen den aktuellen Filter, siehe _apply_history_filter."""
        entries = history_store.get_all()
        self._history_cache_len = len(entries)
        self._history_all_entries = entries
        self.history_stats_label.setText(self._format_history_stats(compute_history_stats(entries)))
        self._apply_history_filter()

    def _apply_history_filter(self, *_args):
        """Wendet Suchtext + Datumsfilter auf den zwischengespeicherten
        Verlauf an und rendert die Liste neu. Reine Anzeige-Funktion, die
        eigentliche Such-/Filterlogik steckt in filter_history_entries()
        (utils/history_store.py), damit sie ohne PyQt6 testbar bleibt."""
        entries = getattr(self, "_history_all_entries", None)
        if entries is None:
            return

        query = self.history_search_input.text()
        filter_index = self.history_date_filter.currentIndex()
        date_filter = DATE_FILTERS[filter_index] if 0 <= filter_index < len(DATE_FILTERS) else "all"

        filtered = filter_history_entries(entries, query=query, date_filter=date_filter)

        self.history_list.clear()
        for entry in filtered:
            preview = entry["text"][:90] + ("…" if len(entry["text"]) > 90 else "")
            item = QListWidgetItem(f"[{entry['created_at'][:16].replace('T', ' ')}] {preview}")
            item.setData(Qt.ItemDataRole.UserRole, entry["text"])
            self.history_list.addItem(item)

        # Unterscheidet "Verlauf ist komplett leer" (Liste einfach leer) von
        # "es gibt Eintraege, aber keiner passt zur Suche" (expliziter
        # Hinweis, sonst wirkt eine leere Liste wie ein Fehler statt wie
        # eine erwartbare Folge des eigenen Suchbegriffs).
        no_results = bool(entries) and not filtered
        self.history_no_results_label.setVisible(no_results)

    def _format_history_stats(self, stats: dict) -> str:
        """Formatiert das Ergebnis von compute_history_stats() als lesbaren,
        mehrzeiligen Text fuer die Statistik-Kachel. Getrennt von
        compute_history_stats() gehalten, damit die reine Auswertung ohne
        Qt testbar bleibt (siehe tests/test_history_stats.py)."""
        if stats["count"] == 0:
            return "Noch keine Diktate im Verlauf."

        def de_decimal(value: float) -> str:
            return f"{value:.1f}".replace(".", ",")

        lines = [
            f"{stats['count']} Diktate im Verlauf  •  {stats['total_words']} Wörter insgesamt  •  "
            f"Ø {de_decimal(stats['avg_words'])} Wörter pro Diktat",
            f"Längstes Diktat: {stats['longest_words']} Wörter  •  "
            f"Kürzestes: {stats['shortest_words']} Wörter",
            f"Heute: {stats['today_count']}  •  Letzte 7 Tage: {stats['last_7_days_count']}",
        ]

        delta = stats["avg_refinement_word_delta"]
        if abs(delta) >= 0.05:
            richtung = "mehr" if delta > 0 else "weniger"
            lines.append(
                f"KI-Veredelung ergibt im Schnitt {de_decimal(abs(delta))} Wörter {richtung} pro Diktat"
            )

        return "\n".join(lines)

    def _refresh_history_if_visible(self):
        if PAGES[self.stacked.currentIndex()][0] != "Verlauf":
            return
        if len(history_store.get_all()) != self._history_cache_len:
            self._load_history()

    def _copy_history_entry(self):
        item = self.history_list.currentItem()
        if not item:
            self._flash_history_feedback(
                "Bitte zuerst einen Eintrag in der Liste auswaehlen.", warning=True
            )
            return
        text = item.data(Qt.ItemDataRole.UserRole)
        self.platform.clipboard.write_text(text)
        self._flash_history_feedback("In die Zwischenablage kopiert")

    def _flash_history_feedback(self, text: str, warning: bool = False) -> None:
        """Zeigt kurz eine Rueckmeldung unter den Verlauf-Knoepfen an und
        blendet sie nach 2,5s wieder aus. Ein neuer Aufruf ersetzt lediglich
        den Text/Timer, es sammeln sich also keine ueberlappenden Timer an."""
        color = COLORS["danger"] if warning else COLORS["cyan_neon"]
        self.history_copy_feedback.setStyleSheet(f"color: {color}; font-size: 20px;")
        self.history_copy_feedback.setText(text)
        QTimer.singleShot(2500, lambda: self.history_copy_feedback.setText(""))

    def _clear_history(self):
        history_store.clear()
        self._load_history()

    # ------------------------------------------------------------------
    # Kleine Hilfsfunktionen für einheitliches Aussehen
    # ------------------------------------------------------------------
    def _page_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        font = QFont()
        font.setPixelSize(36)
        font.setBold(True)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color: {COLORS['off_white']};")
        return lbl

    def _show_message(self, title: str, text: str, warning: bool = False) -> None:
        """Ersatz fuer QMessageBox.information()/.warning() mit direktem
        Standardaufruf: ungestylt uebernehmen diese Systemdialoge NICHT das
        dunkle App-Design und laufen auf der winzigen Windows-Standardschrift,
        voellig losgeloest vom Rest des Fensters (JJs Kritik an den
        Screenshots, 2026-07-25: "Das kann doch keine Sau lesen. Was soll
        denn diese Scheiße?"). Baut stattdessen eine im App-Design gehaltene
        Box mit garantiert lesbarer Schrift (15px) und Zeilenumbruch fuer
        laengere Texte.
        """
        box = QMessageBox(self)
        box.setWindowTitle(title)
        box.setText(text)
        box.setIcon(QMessageBox.Icon.Warning if warning else QMessageBox.Icon.Information)
        box.setStandardButtons(QMessageBox.StandardButton.Ok)
        accent = COLORS["danger"] if warning else COLORS["cyan_neon"]
        box.setStyleSheet(f"""
            QMessageBox {{
                background-color: {COLORS['deep_navy']};
            }}
            QMessageBox QLabel {{
                color: {COLORS['off_white']};
                font-size: 22px;
            }}
            QPushButton {{
                background-color: transparent;
                color: {accent};
                border: 1px solid {accent};
                border-radius: 6px;
                padding: 6px 18px;
                font-size: 20px;
                min-width: 60px;
            }}
            QPushButton:hover {{
                background-color: rgba(0, 224, 184, 0.15);
            }}
        """)
        box.exec()

    def _label_font(self) -> QFont:
        font = QFont()
        font.setPixelSize(24)
        font.setBold(True)
        return font

    def _input_style(self) -> str:
        # font-size hier deckt auch die Eingabefelder ab, die OHNE die
        # _create_input()-Fabrik direkt als QLineEdit/QTextEdit angelegt
        # werden (Woerterbuch, Ausschnitte, Notizbuch) - die hatten bisher
        # ueberhaupt keine Schriftgroesse und fielen auf den winzigen
        # Systemstandard zurueck, siehe auch _list_style() oben.
        return f"""
            QLineEdit, QTextEdit {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
                font-size: 22px;
                selection-background-color: {COLORS['cyan_neon']};
                selection-color: {COLORS['deep_navy']};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {COLORS['cyan_neon']};
            }}
        """

    def _list_style(self) -> str:
        # WICHTIG: font-size hier ist bewusst gesetzt (15px, KEIN bold).
        # Ohne diese Zeile bekamen Woerterbuch/Ausschnitte/Notizbuch/Verlauf
        # ueberhaupt keine Schriftgroesse zugewiesen und fielen auf den sehr
        # kleinen Qt/Windows-Systemstandard zurueck, ausgerechnet dort, wo
        # der Nutzer tatsaechlich lesen muss (JJ traegt Brille, 2026-07-25:
        # "wer soll denn das lesen"). Ausdruecklich NICHT fett, JJs Wunsch
        # war Groesse statt Gewicht.
        return f"""
            QListWidget {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
                font-size: 22px;
            }}
            QListWidget::item {{
                padding: 10px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(0, 224, 184, 0.2);
                color: {COLORS['cyan_neon']};
            }}
        """

    def _info_icon(self, text: str) -> QPushButton:
        """Info-Icon (i im Kreis) fuer kontextuelle Hilfe (JJ, 2026-07-28):
        beim Drüberfahren erscheint sofort ein Tooltip mit der Erklärung,
        ein Klick öffnet zusätzlich dasselbe als Popup-Fenster - für alle,
        die den Mauszeiger nicht bewusst ruhig halten oder lieber klicken.
        Gedacht zum Einfügen NEBEN dem Feld/Bereich, den es erklärt, siehe
        z.B. _hint_row() direkt darunter."""
        btn = QPushButton()
        btn.setIcon(icon_manager.get("informationen", active=False))
        btn.setIconSize(QSize(18, 18))
        btn.setFixedSize(28, 28)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setToolTip(text)
        btn.setFlat(True)
        btn.setStyleSheet(f"""
            QPushButton {{
                background: transparent;
                border: 1px solid {COLORS['border']};
                border-radius: 14px;
            }}
            QPushButton:hover {{
                border: 1px solid {COLORS['cyan_neon']};
                background-color: rgba(0, 224, 184, 30);
            }}
        """)
        btn.clicked.connect(lambda: self._show_message("Hilfe", text))
        return btn

    def _hint_row(self, hint_text: str, info_text: Optional[str] = None) -> QHBoxLayout:
        """Baut die gedaempfte Hinweiszeile, die viele Seiten oben haben,
        optional ergaenzt um ein Info-Icon mit ausfuehrlicherer Erklaerung
        (JJ, 2026-07-28: Hilfefunktionen sollen sich durch die komplette
        App ziehen statt nur an einer einzelnen Stelle zu stehen)."""
        row = QHBoxLayout()
        hint = QLabel(hint_text)
        hint.setWordWrap(True)
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 22px;")
        row.addWidget(hint, 1)
        if info_text:
            row.addWidget(self._info_icon(info_text))
        return row

    def _icon_button(self, icon_name: str, text: str, danger: bool = False) -> QPushButton:
        """danger=True: fuer unwiderrufliche Aktionen (z.B. "Verlauf
        leeren"), die sich optisch klar von harmlosen Aktionen wie "In
        Zwischenablage kopieren" abheben sollen muessen, statt identisch
        auszusehen (JJs Kritik an den Screenshots, 2026-07-25)."""
        btn = QPushButton(f"  {text}".replace("&", "&&"))
        btn.setIcon(icon_manager.get(icon_name, active=False))
        btn.setIconSize(QSize(22, 22))
        btn.setMinimumHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        text_color = COLORS["danger"] if danger else COLORS["off_white"]
        border_color = COLORS["danger"] if danger else COLORS["border"]
        hover_color = COLORS["danger"] if danger else COLORS["cyan_neon"]
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {text_color};
                border: 1px solid {border_color};
                border-radius: 8px;
                padding: 8px 16px;
                text-align: left;
                font-size: 22px;
            }}
            QPushButton:hover {{
                border: 1px solid {hover_color};
                color: {hover_color};
            }}
        """)
        return btn

    def _create_combo(self, items: list) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.setMinimumHeight(42)
        # Ohne Maximalbreite zieht sich das Feld ueber die volle
        # Fensterbreite (bei einer Zahl wie "16000" oder einem Wort wie
        # "auto" wirkte das wie ein leeres, unfertiges Formular, siehe
        # JJ-Screenshot vom 2026-07-25).
        combo.setMaximumWidth(560)
        font = QFont()
        font.setPixelSize(22)
        combo.setFont(font)
        combo.setStyleSheet(f"""
            QComboBox {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
            }}
            QComboBox::drop-down {{
                border: none;
                background-color: transparent;
                width: 28px;
            }}
            QComboBox QAbstractItemView {{
                background-color: {COLORS['deep_navy']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                selection-background-color: rgba(0, 224, 184, 0.25);
                selection-color: {COLORS['cyan_neon']};
                outline: none;
            }}
        """)
        return combo

    def _create_spinbox(self, min_val: int, max_val: int, default: int) -> QSpinBox:
        spin = QSpinBox()
        spin.setMinimum(min_val)
        spin.setMaximum(max_val)
        spin.setValue(default)
        spin.setMinimumHeight(42)
        spin.setMaximumWidth(220)
        font = QFont()
        font.setPixelSize(22)
        spin.setFont(font)
        spin.setStyleSheet(f"""
            QSpinBox {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
            }}
            QSpinBox::up-button, QSpinBox::down-button {{
                background-color: transparent;
                border: none;
                width: 20px;
            }}
            QSpinBox::up-arrow, QSpinBox::down-arrow {{
                width: 8px;
                height: 8px;
            }}
        """)
        return spin

    def _create_input(self, placeholder: str = "") -> QLineEdit:
        inp = QLineEdit()
        inp.setPlaceholderText(placeholder)
        inp.setMinimumHeight(42)
        inp.setMaximumWidth(560)
        font = QFont()
        font.setPixelSize(22)
        inp.setFont(font)
        inp.setStyleSheet(self._input_style())
        return inp

    # ------------------------------------------------------------------
    # Laden / Speichern
    # ------------------------------------------------------------------
    def load_settings(self):
        self.hotkey_combo.setCurrentText(secure_config.get("HOTKEY", ""))
        self.undo_hotkey_combo.setCurrentText(secure_config.get("UNDO_HOTKEY", "ctrl_alt_z"))
        self.sample_rate.setValue(int(secure_config.get("SAMPLE_RATE", "16000")))
        self.raw_text_mode_check.setChecked(config.get_bool("RAW_TEXT_MODE", False))
        self.silence_autostop_check.setChecked(config.get_bool("SILENCE_AUTOSTOP_ENABLED", True))
        try:
            self.silence_timeout.setValue(round(float(secure_config.get("SILENCE_TIMEOUT_SECONDS", "2.5"))))
        except (TypeError, ValueError):
            self.silence_timeout.setValue(3)

        self.stt_provider.setCurrentText(secure_config.get("STT_PROVIDER", "voxtral"))
        self.whisper_model.setCurrentText(secure_config.get("WHISPER_MODEL_SIZE", "tiny"))
        self.whisper_device.setCurrentText(secure_config.get("WHISPER_DEVICE", "auto"))

        self.llm_provider.setCurrentText(secure_config.get("LLM_PROVIDER", "openrouter"))
        self.openrouter_model.setText(secure_config.get("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite"))
        self.llm_model.setCurrentText(secure_config.get("LLM_MODEL", "gemma4:e4b"))
        self.ollama_url.setText(secure_config.get("OLLAMA_BASE_URL", "http://localhost:11434"))
        self.ionos_model.setCurrentText(secure_config.get("IONOS_MODEL", "mistralai/Mistral-Small-24B-Instruct"))
        self.word_threshold.setValue(int(secure_config.get("LLM_WORD_THRESHOLD", "10")))

        self.openrouter_key.setText(secure_config.get("OPENROUTER_API_KEY", "") or "")
        self.ionos_key.setText(secure_config.get("IONOS_API_KEY", "") or "")

        self.language.setCurrentText(secure_config.get("LANGUAGE", "de"))
        self.log_level.setCurrentText(secure_config.get("LOG_LEVEL", "INFO"))
        self.autostart_check.setChecked(self.platform.autostart.is_enabled())

        style = style_store.get_style()
        self.style_category.setCurrentText(style["category"])
        self.style_tone.setCurrentText(style["tone"])

        self._reload_dictionary_list()
        self._reload_snippets_list()
        self._reload_notes_list()
        self._load_history()

    def save_settings(self):
        settings = {
            "HOTKEY": self.hotkey_combo.currentText(),
            "UNDO_HOTKEY": self.undo_hotkey_combo.currentText(),
            "SAMPLE_RATE": str(self.sample_rate.value()),
            "SILENCE_AUTOSTOP_ENABLED": "true" if self.silence_autostop_check.isChecked() else "false",
            "SILENCE_TIMEOUT_SECONDS": str(self.silence_timeout.value()),
            "STT_PROVIDER": self.stt_provider.currentText(),
            "WHISPER_MODEL_SIZE": self.whisper_model.currentText(),
            "WHISPER_DEVICE": self.whisper_device.currentText(),
            "LLM_PROVIDER": self.llm_provider.currentText(),
            "OPENROUTER_MODEL": self.openrouter_model.text().strip(),
            "LLM_MODEL": self.llm_model.currentText(),
            "OLLAMA_BASE_URL": self.ollama_url.text().strip(),
            "IONOS_MODEL": self.ionos_model.currentText().strip(),
            "LLM_WORD_THRESHOLD": str(self.word_threshold.value()),
            "LANGUAGE": self.language.currentText(),
            "LOG_LEVEL": self.log_level.currentText(),
            "RAW_TEXT_MODE": "true" if self.raw_text_mode_check.isChecked() else "false",
        }

        failed = []
        for key, value in settings.items():
            if not secure_config.set(key, value):
                failed.append(key)

        if self.openrouter_key.text().strip():
            if not secure_config.set("OPENROUTER_API_KEY", self.openrouter_key.text().strip()):
                failed.append("OPENROUTER_API_KEY")

        if self.ionos_key.text().strip():
            if not secure_config.set("IONOS_API_KEY", self.ionos_key.text().strip()):
                failed.append("IONOS_API_KEY")

        if self.autostart_check.isChecked():
            self.platform.autostart.enable()
        else:
            self.platform.autostart.disable()

        # Tray-Checkbox synchron halten: sonst zeigt das Tray-Menue nach
        # einer Aenderung hier in den Einstellungen bis zum naechsten
        # Neustart noch den alten Zustand (JJ, 2026-07-27).
        raw_text_action = getattr(self.engine_api, "raw_text_action", None) if self.engine_api else None
        if raw_text_action is not None:
            raw_text_action.setChecked(self.raw_text_mode_check.isChecked())

        if failed:
            self._show_message(
                "Fehler",
                f"Folgende Einstellungen konnten nicht gespeichert werden:\n{', '.join(failed)}",
                warning=True,
            )
        else:
            self._show_message(
                "Gespeichert",
                "Einstellungen wurden gespeichert. Ein Neustart von NovaFlow übernimmt sie vollständig.",
            )
