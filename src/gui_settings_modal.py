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

from PyQt6.QtWidgets import (
    QDialog, QWidget, QVBoxLayout, QHBoxLayout,
    QPushButton, QLabel, QFrame, QStackedWidget, QScrollArea,
    QLineEdit, QComboBox, QSpinBox, QCheckBox, QMessageBox, QListWidget,
    QListWidgetItem, QTextEdit
)
from PyQt6.QtCore import Qt, QSize, QTimer
from PyQt6.QtGui import QFont

from utils.config import config
from utils.secure_config import secure_config
from utils.icon_manager import icon_manager
from utils.dictionary_store import dictionary_store
from utils.snippets_store import snippets_store
from utils.style_store import style_store, CATEGORIES, TONES
from utils.notes_store import notes_store
from utils.history_store import history_store
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
    "text_muted": "#9CA3AF",
    "border": "#1F2937",
    "danger": "#F87171",
}

NAV_ITEMS = [
    # (Seiten-Index, Label, Icon-Name)
    ("Diktat", "recording"),
    ("Spracherkennung", "whisper"),
    ("Sprachmodell", "llm"),
    ("API-Schlüssel", "api_keys"),
    ("Wörterbuch", "woerterbuch"),
    ("Ausschnitte", "ausschnitte"),
    ("Schreibstil", "style"),
    ("Notizbuch", "notizblock"),
    ("Verlauf", "verlauf"),
    ("Sprache & System", "language"),
]


class NovaFlowSettingsModal(QDialog):
    """Ein gemeinsames Einstellungsfenster für Technik + Bonus-Funktionen"""

    def __init__(self, parent=None):
        super().__init__(parent)
        self.setWindowTitle("NovaFlow – Einstellungen")
        self.setMinimumSize(1300, 860)
        self.setStyleSheet(f"QDialog {{ background-color: {COLORS['deep_navy']}; }}")
        self.setModal(True)
        self.platform = get_platform()

        if parent:
            pr = parent.frameGeometry()
            self.move(pr.left() + (pr.width() - self.width()) // 2,
                      pr.top() + (pr.height() - self.height()) // 2)

        self.nav_buttons = []
        self.init_ui()
        self.load_settings()

        # Verlauf soll sich aktualisieren, solange die Seite offen ist
        self._history_timer = QTimer(self)
        self._history_timer.timeout.connect(self._refresh_history_if_visible)
        self._history_timer.start(2000)

    # ------------------------------------------------------------------
    # Grundgerüst
    # ------------------------------------------------------------------
    def init_ui(self):
        main_layout = QHBoxLayout()
        main_layout.setContentsMargins(0, 0, 0, 0)
        main_layout.setSpacing(0)

        sidebar = QFrame()
        sidebar.setStyleSheet(f"""
            QFrame {{
                background-color: {COLORS['panel_grey']};
                border-right: 1px solid {COLORS['border']};
            }}
        """)
        sidebar.setMaximumWidth(260)
        sidebar.setMinimumWidth(260)

        sidebar_layout = QVBoxLayout()
        sidebar_layout.setContentsMargins(0, 0, 0, 0)
        sidebar_layout.setSpacing(0)

        logo = QLabel("NovaFlow")
        font = QFont()
        font.setPointSize(20)
        font.setBold(True)
        logo.setFont(font)
        logo.setStyleSheet(f"color: {COLORS['cyan_neon']}; padding: 20px 20px 4px 20px;")
        sidebar_layout.addWidget(logo)

        sub = QLabel("Einstellungen")
        sub.setStyleSheet(f"color: {COLORS['text_muted']}; padding: 0 20px 16px 20px; font-size: 12px;")
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

        for index, (label, icon_name) in enumerate(NAV_ITEMS):
            btn = self._create_nav_button(label, icon_name)
            btn.clicked.connect(lambda checked=False, i=index: self.switch_page(i))
            nav_container_layout.addWidget(btn)
            self.nav_buttons.append(btn)

        nav_container_layout.addStretch()
        nav_container.setLayout(nav_container_layout)
        nav_scroll.setWidget(nav_container)
        sidebar_layout.addWidget(nav_scroll, 1)
        sidebar.setLayout(sidebar_layout)
        main_layout.addWidget(sidebar)

        # CONTENT
        content = QWidget()
        content_layout = QVBoxLayout()
        content_layout.setContentsMargins(32, 32, 32, 32)
        content_layout.setSpacing(20)

        self.stacked = QStackedWidget()
        self.stacked.setStyleSheet(f"QStackedWidget {{ background-color: {COLORS['deep_navy']}; }}")

        self.stacked.addWidget(self._create_recording_page())
        self.stacked.addWidget(self._create_stt_page())
        self.stacked.addWidget(self._create_llm_page())
        self.stacked.addWidget(self._create_api_page())
        self.stacked.addWidget(self._create_dictionary_page())
        self.stacked.addWidget(self._create_snippets_page())
        self.stacked.addWidget(self._create_style_page())
        self.stacked.addWidget(self._create_notes_page())
        self.stacked.addWidget(self._create_history_page())
        self.stacked.addWidget(self._create_lang_page())

        content_layout.addWidget(self.stacked)

        btn_layout = QHBoxLayout()
        btn_layout.addStretch()

        save_btn = QPushButton("Speichern")
        save_btn.setMinimumHeight(48)
        save_btn.setMinimumWidth(160)
        bf = QFont()
        bf.setPointSize(15)
        bf.setBold(True)
        save_btn.setFont(bf)
        save_btn.clicked.connect(self.save_settings)
        save_btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['cyan_neon']};
                color: {COLORS['deep_navy']};
                border: none;
                border-radius: 10px;
                padding: 12px 28px;
                font-weight: bold;
            }}
        """)
        btn_layout.addWidget(save_btn)

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
        self.activate_nav_button(0)

    def _create_nav_button(self, text: str, icon_name: str = "") -> QPushButton:
        """Linksbündiger Nav-Button mit Icon (statt zentriert)"""
        btn = QPushButton(f"  {text}")
        font = QFont()
        font.setPointSize(15)
        font.setBold(True)
        btn.setFont(font)
        btn.setMinimumHeight(50)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)

        if icon_name:
            btn.setIcon(icon_manager.get(icon_name, active=False))
            btn.setIconSize(QSize(20, 20))
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

    def activate_nav_button(self, active_index: int) -> None:
        for i, btn in enumerate(self.nav_buttons):
            is_active = (i == active_index)
            color = COLORS["cyan_neon"] if is_active else COLORS["text_muted"]
            border = COLORS["cyan_neon"] if is_active else "transparent"
            bg = "rgba(0, 224, 184, 0.15)" if is_active else "transparent"

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
                btn.setIcon(icon_manager.get(icon_name, active=is_active))

    def switch_page(self, index: int):
        self.stacked.setCurrentIndex(index)
        self.activate_nav_button(index)
        if NAV_ITEMS[index][0] == "Verlauf":
            self._load_history()

    # ------------------------------------------------------------------
    # Technische Einstellungen (config / secure_config)
    # ------------------------------------------------------------------
    def _create_recording_page(self) -> QWidget:
        default_hotkey = self.platform.default_hotkey()
        hotkey_items = ["", "ctrl_win", "ctrl_cmd", "ctrl", "alt", "shift", "f8", "f9", "f10"]
        return self._create_settings_page("Diktat", [
            (f"Hotkey (leer = automatisch: {default_hotkey}):",
             self._create_combo(hotkey_items), 'hotkey_combo'),
            ("Sample Rate:", self._create_spinbox(8000, 48000, 16000), 'sample_rate'),
        ])

    def _create_stt_page(self) -> QWidget:
        return self._create_settings_page("Spracherkennung", [
            ("STT Provider:", self._create_combo(["voxtral", "whisper"]), 'stt_provider'),
            ("Whisper Model Size:", self._create_combo(["tiny", "base", "small", "medium", "large-v3"]), 'whisper_model'),
            ("Whisper Device:", self._create_combo(["auto", "cuda", "cpu"]), 'whisper_device'),
        ])

    def _create_llm_page(self) -> QWidget:
        return self._create_settings_page("Sprachmodell", [
            ("Provider:", self._create_combo(["openrouter", "ollama", "disabled"]), 'llm_provider'),
            ("OpenRouter Modell:", self._create_input("google/gemini-3.1-flash-lite"), 'openrouter_model'),
            ("Ollama Modell:", self._create_combo(["gemma4:e2b", "gemma4:e4b", "gemma3:4b", "mistral", "llama2"]), 'llm_model'),
            ("Ollama URL:", self._create_input("http://localhost:11434"), 'ollama_url'),
            ("Wortschwelle (kurze Texte überspringen LLM):", self._create_spinbox(0, 100, 10), 'word_threshold'),
        ])

    def _create_api_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(20)

        title = self._page_title("API-Schlüssel")
        layout.addWidget(title)

        lbl = QLabel("OpenRouter API Key:")
        lbl.setFont(self._label_font())
        lbl.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.addWidget(lbl)

        row = QHBoxLayout()
        self.openrouter_key = QLineEdit()
        self.openrouter_key.setEchoMode(QLineEdit.EchoMode.Password)
        self.openrouter_key.setPlaceholderText("sk-or-...")
        self.openrouter_key.setMinimumHeight(46)
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
        info.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        info.setWordWrap(True)
        layout.addWidget(info)

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
        af.setPointSize(14)
        self.autostart_check.setFont(af)
        self.autostart_check.setStyleSheet(f"color: {COLORS['off_white']};")
        layout.insertWidget(layout.count() - 1, self.autostart_check)
        return page

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

        for field_label, field_widget, attr_name in fields:
            lbl = QLabel(field_label)
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
        hint = QLabel("Korrigiert häufige Fehlerkennungen automatisch, bevor die KI-Veredelung läuft.")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        layout.addWidget(hint)

        self.dict_list = QListWidget()
        self.dict_list.setStyleSheet(self._list_style())
        layout.addWidget(self.dict_list, 1)

        form = QHBoxLayout()
        self.dict_spoken_input = QLineEdit()
        self.dict_spoken_input.setPlaceholderText("Falsch erkannt (z.B. 'nowa flow')")
        self.dict_spoken_input.setStyleSheet(self._input_style())
        self.dict_spoken_input.setMinimumHeight(44)
        self.dict_correction_input = QLineEdit()
        self.dict_correction_input.setPlaceholderText("Korrektur (z.B. 'NovaFlow')")
        self.dict_correction_input.setStyleSheet(self._input_style())
        self.dict_correction_input.setMinimumHeight(44)
        add_btn = self._icon_button("add", "Hinzufügen")
        add_btn.clicked.connect(self._add_dictionary_entry)
        form.addWidget(self.dict_spoken_input, 1)
        form.addWidget(self.dict_correction_input, 1)
        form.addWidget(add_btn)
        layout.addLayout(form)

        del_btn = self._icon_button("delete", "Ausgewählten Eintrag löschen")
        del_btn.clicked.connect(self._delete_dictionary_entry)
        layout.addWidget(del_btn)

        page.setLayout(layout)
        return page

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
        hint = QLabel("Trigger-Wörter werden beim Diktat automatisch zu vollständigen Textbausteinen erweitert.")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        layout.addWidget(hint)

        self.snippets_list = QListWidget()
        self.snippets_list.setStyleSheet(self._list_style())
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
        hint = QLabel("Kategorie und Ton fließen als Kontext-Hinweis in die KI-Veredelung ein.")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        layout.addWidget(hint)

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
        QMessageBox.information(self, "Gespeichert", "Schreibstil wurde gespeichert.", QMessageBox.StandardButton.Ok)

    def _create_notes_page(self) -> QWidget:
        page = QWidget()
        layout = QVBoxLayout()
        layout.setSpacing(16)
        layout.addWidget(self._page_title("Notizbuch"))

        self.notes_list = QListWidget()
        self.notes_list.setStyleSheet(self._list_style())
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
        hint = QLabel("Die letzten Diktate. Aktualisiert sich automatisch, solange diese Seite offen ist.")
        hint.setStyleSheet(f"color: {COLORS['text_muted']}; font-size: 13px;")
        layout.addWidget(hint)

        self.history_list = QListWidget()
        self.history_list.setStyleSheet(self._list_style())
        layout.addWidget(self.history_list, 1)

        btn_row = QHBoxLayout()
        copy_btn = self._icon_button("download", "In Zwischenablage kopieren")
        copy_btn.clicked.connect(self._copy_history_entry)
        clear_btn = self._icon_button("delete", "Verlauf leeren")
        clear_btn.clicked.connect(self._clear_history)
        btn_row.addWidget(copy_btn)
        btn_row.addWidget(clear_btn)
        layout.addLayout(btn_row)

        page.setLayout(layout)
        self._history_cache_len = -1
        return page

    def _load_history(self):
        entries = history_store.get_all()
        self._history_cache_len = len(entries)
        self.history_list.clear()
        for entry in entries:
            preview = entry["text"][:90] + ("…" if len(entry["text"]) > 90 else "")
            item = QListWidgetItem(f"[{entry['created_at'][:16].replace('T', ' ')}] {preview}")
            item.setData(Qt.ItemDataRole.UserRole, entry["text"])
            self.history_list.addItem(item)

    def _refresh_history_if_visible(self):
        if NAV_ITEMS[self.stacked.currentIndex()][0] != "Verlauf":
            return
        if len(history_store.get_all()) != self._history_cache_len:
            self._load_history()

    def _copy_history_entry(self):
        item = self.history_list.currentItem()
        if not item:
            return
        text = item.data(Qt.ItemDataRole.UserRole)
        self.platform.clipboard.write_text(text)

    def _clear_history(self):
        history_store.clear()
        self._load_history()

    # ------------------------------------------------------------------
    # Kleine Hilfsfunktionen für einheitliches Aussehen
    # ------------------------------------------------------------------
    def _page_title(self, text: str) -> QLabel:
        lbl = QLabel(text)
        font = QFont()
        font.setPointSize(22)
        font.setBold(True)
        lbl.setFont(font)
        lbl.setStyleSheet(f"color: {COLORS['off_white']};")
        return lbl

    def _label_font(self) -> QFont:
        font = QFont()
        font.setPointSize(14)
        font.setBold(True)
        return font

    def _input_style(self) -> str:
        return f"""
            QLineEdit, QTextEdit {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 10px 14px;
                selection-background-color: {COLORS['cyan_neon']};
                selection-color: {COLORS['deep_navy']};
            }}
            QLineEdit:focus, QTextEdit:focus {{
                border: 1px solid {COLORS['cyan_neon']};
            }}
        """

    def _list_style(self) -> str:
        return f"""
            QListWidget {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 4px;
            }}
            QListWidget::item {{
                padding: 8px;
                border-radius: 6px;
            }}
            QListWidget::item:selected {{
                background-color: rgba(0, 224, 184, 0.2);
                color: {COLORS['cyan_neon']};
            }}
        """

    def _icon_button(self, icon_name: str, text: str) -> QPushButton:
        btn = QPushButton(f"  {text}")
        btn.setIcon(icon_manager.get(icon_name, active=False))
        btn.setIconSize(QSize(18, 18))
        btn.setMinimumHeight(42)
        btn.setCursor(Qt.CursorShape.PointingHandCursor)
        btn.setStyleSheet(f"""
            QPushButton {{
                background-color: {COLORS['panel_grey']};
                color: {COLORS['off_white']};
                border: 1px solid {COLORS['border']};
                border-radius: 8px;
                padding: 8px 16px;
                text-align: left;
            }}
            QPushButton:hover {{
                border: 1px solid {COLORS['cyan_neon']};
                color: {COLORS['cyan_neon']};
            }}
        """)
        return btn

    def _create_combo(self, items: list) -> QComboBox:
        combo = QComboBox()
        combo.addItems(items)
        combo.setMinimumHeight(42)
        font = QFont()
        font.setPointSize(14)
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
        font = QFont()
        font.setPointSize(14)
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
        font = QFont()
        font.setPointSize(14)
        inp.setFont(font)
        inp.setStyleSheet(self._input_style())
        return inp

    # ------------------------------------------------------------------
    # Laden / Speichern
    # ------------------------------------------------------------------
    def load_settings(self):
        self.hotkey_combo.setCurrentText(secure_config.get("HOTKEY", ""))
        self.sample_rate.setValue(int(secure_config.get("SAMPLE_RATE", "16000")))

        self.stt_provider.setCurrentText(secure_config.get("STT_PROVIDER", "voxtral"))
        self.whisper_model.setCurrentText(secure_config.get("WHISPER_MODEL_SIZE", "tiny"))
        self.whisper_device.setCurrentText(secure_config.get("WHISPER_DEVICE", "auto"))

        self.llm_provider.setCurrentText(secure_config.get("LLM_PROVIDER", "openrouter"))
        self.openrouter_model.setText(secure_config.get("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite"))
        self.llm_model.setCurrentText(secure_config.get("LLM_MODEL", "gemma4:e4b"))
        self.ollama_url.setText(secure_config.get("OLLAMA_BASE_URL", "http://localhost:11434"))
        self.word_threshold.setValue(int(secure_config.get("LLM_WORD_THRESHOLD", "10")))

        self.openrouter_key.setText(secure_config.get("OPENROUTER_API_KEY", "") or "")

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
            "SAMPLE_RATE": str(self.sample_rate.value()),
            "STT_PROVIDER": self.stt_provider.currentText(),
            "WHISPER_MODEL_SIZE": self.whisper_model.currentText(),
            "WHISPER_DEVICE": self.whisper_device.currentText(),
            "LLM_PROVIDER": self.llm_provider.currentText(),
            "OPENROUTER_MODEL": self.openrouter_model.text().strip(),
            "LLM_MODEL": self.llm_model.currentText(),
            "OLLAMA_BASE_URL": self.ollama_url.text().strip(),
            "LLM_WORD_THRESHOLD": str(self.word_threshold.value()),
            "LANGUAGE": self.language.currentText(),
            "LOG_LEVEL": self.log_level.currentText(),
        }

        failed = []
        for key, value in settings.items():
            if not secure_config.set(key, value):
                failed.append(key)

        if self.openrouter_key.text().strip():
            if not secure_config.set("OPENROUTER_API_KEY", self.openrouter_key.text().strip()):
                failed.append("OPENROUTER_API_KEY")

        if self.autostart_check.isChecked():
            self.platform.autostart.enable()
        else:
            self.platform.autostart.disable()

        if failed:
            QMessageBox.warning(
                self, "Fehler",
                f"Folgende Einstellungen konnten nicht gespeichert werden:\n{', '.join(failed)}",
                QMessageBox.StandardButton.Ok
            )
        else:
            QMessageBox.information(
                self, "Gespeichert",
                "Einstellungen wurden gespeichert. Ein Neustart von NovaFlow übernimmt sie vollständig.",
                QMessageBox.StandardButton.Ok
            )
