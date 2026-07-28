"""
NovaFlow Config – Zentrale Konfigurationsverwaltung
"""
import os
from typing import Any
from dotenv import load_dotenv

from utils.paths import get_project_root

CONFIG_DIR = get_project_root()
ENV_FILE = CONFIG_DIR / ".env"
load_dotenv(ENV_FILE)


class NovaFlowConfig:
    """Zentrale Konfiguration für NovaFlow"""

    # Standardwerte
    # WICHTIG: jeder Schluessel, der aus der .env gelesen werden soll, MUSS
    # hier stehen. _load_from_env() unten prueft os.getenv() nur fuer
    # Schluessel, die bereits in DEFAULTS vorkommen. Ein Schluessel, der nur
    # in der .env oder im .env-Template auftaucht, aber hier fehlt, wird beim
    # Start stillschweigend ignoriert (das war ein echter Bug im alten
    # NovaFlow bei STT_PROVIDER).
    DEFAULTS = {
        # STT Provider
        "STT_PROVIDER": "voxtral",  # voxtral (Cloud), whisper (Lokal)

        # Whisper Settings
        "WHISPER_MODEL_SIZE": "tiny",  # tiny, base, small, medium, large-v3
        "WHISPER_DEVICE": "auto",  # auto, cuda, cpu

        # Interface Settings
        "HOTKEY": "",  # leer = plattformtypischer Standard (siehe platforms/*)
        "SAMPLE_RATE": 16000,

        # Undo per Hotkey (JJ, 2026-07-28): schickt Strg+Z bzw. Cmd+Z ans
        # aktive Fenster, nutzt die programmeigene Undo-Funktion des
        # Zielprogramms. Leer = Funktion deaktiviert.
        "UNDO_HOTKEY": "ctrl_alt_z",

        # Stille-Erkennung (JJ, 2026-07-28): beendet eine laufende Aufnahme
        # automatisch, wenn laenger als SILENCE_TIMEOUT_SECONDS keine
        # Sprache mehr erkannt wird (Auto-Stop, kein Pausieren), genau wie
        # ein manuelles Loslassen der Aufnahmetaste, siehe interface.py.
        "SILENCE_AUTOSTOP_ENABLED": True,
        "SILENCE_TIMEOUT_SECONDS": 2.5,

        # LLM Settings
        "LLM_PROVIDER": "openrouter",  # openrouter, ollama, ionos, disabled
        "LLM_MODEL": "gemma4:e4b",  # Ollama Model
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_TIMEOUT": 30,
        "OPENROUTER_MODEL": "google/gemini-3.1-flash-lite",
        # IONOS AI Model Hub: Server in Deutschland, fuer DSGVO-bewusste
        # Nutzer als Alternative zu OpenRouter fuer die Text-Veredelung.
        "IONOS_MODEL": "mistralai/Mistral-Small-24B-Instruct",
        "LLM_WORD_THRESHOLD": 10,

        # API Keys (aus .env)
        "OPENROUTER_API_KEY": None,
        "IONOS_API_KEY": None,

        # Sprache
        "LANGUAGE": "de",  # de, en

        # Logging
        "LOG_LEVEL": "INFO",

        # Rohtext-Modus: ueberspringt den KI-Veredelungsschritt komplett
        # (siehe NovaFlowProcessor.refine_text in flow.py), Post-Processing
        # (Fuellwoerter, Woerterbuch, gesprochene Satzzeichen usw.) laeuft
        # weiterhin ganz normal. Per Tray-Schnellumschaltung in novaflow.pyw
        # umschaltbar, ohne die Einstellungen oeffnen zu muessen (JJ,
        # 2026-07-27).
        "RAW_TEXT_MODE": False,
    }

    def __init__(self):
        self.config = self.DEFAULTS.copy()
        self._load_from_env()

    # Werte, die (egal ob aus der .env oder ueber sec_config.set() zur
    # Laufzeit) als Wahrheitswert gelesen werden. Kommen als String an
    # ("true"/"false"), siehe get_bool().
    _BOOL_KEYS = {"RAW_TEXT_MODE", "SILENCE_AUTOSTOP_ENABLED"}

    def _load_from_env(self):
        """Lade Konfiguration aus Umgebungsvariablen"""
        for key in self.DEFAULTS.keys():
            env_value = os.getenv(key)
            if env_value is not None:
                if key in ("SAMPLE_RATE", "OLLAMA_TIMEOUT", "LLM_WORD_THRESHOLD"):
                    try:
                        self.config[key] = int(env_value)
                    except ValueError:
                        pass
                elif key == "SILENCE_TIMEOUT_SECONDS":
                    try:
                        self.config[key] = float(env_value)
                    except ValueError:
                        pass
                elif key in ["WHISPER_DEVICE"]:
                    self.config[key] = env_value.lower()
                else:
                    self.config[key] = env_value

    def get(self, key: str, default=None) -> Any:
        """Hole Konfigurations-Wert"""
        return self.config.get(key, default)

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Hole Konfigurations-Wert als Wahrheitswert.

        Noetig, weil ueber secure_config.set() geschriebene Werte immer als
        String in der .env landen ("true"/"false") und dann auch als String
        (nicht als bool) im in-memory Cache liegen, siehe SecureConfig._set_env
        in secure_config.py. Ein simples "if config.get(key):" waere hier ein
        Bug: der String "false" ist in Python wahr. Diese Methode normalisiert
        beide Faelle (echter bool ODER String) auf ein zuverlaessiges bool.
        """
        value = self.config.get(key, default)
        if isinstance(value, bool):
            return value
        if isinstance(value, str):
            return value.strip().lower() in ("1", "true", "yes", "on")
        return bool(value)

    def set(self, key: str, value: Any):
        """Setze Konfigurations-Wert"""
        self.config[key] = value

    @staticmethod
    def create_env_template() -> str:
        """Erstelle .env Template"""
        template = """# NovaFlow Configuration

# STT Provider: voxtral (Cloud), whisper (Lokal)
STT_PROVIDER=voxtral

# Whisper Settings (lokal, greift wenn STT_PROVIDER=whisper)
WHISPER_MODEL_SIZE=tiny
WHISPER_DEVICE=auto

# Interface Settings
# Leer lassen = plattformtypischer Standard (Windows: ctrl_win, Mac: ctrl_cmd)
HOTKEY=
SAMPLE_RATE=16000

# Undo per Hotkey: schickt Strg+Z/Cmd+Z ans aktive Fenster. Leer = aus.
UNDO_HOTKEY=ctrl_alt_z

# Stille-Erkennung: Aufnahme automatisch beenden nach so vielen Sekunden
# ohne erkannte Sprache (Auto-Stop, kein Pausieren).
SILENCE_AUTOSTOP_ENABLED=true
SILENCE_TIMEOUT_SECONDS=2.5

# LLM Provider: openrouter, ollama, ionos, disabled
LLM_PROVIDER=openrouter
LLM_MODEL=gemma4:e4b

# Ollama Settings (lokal)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=30

# OpenRouter API Key (ein Key fuer alle: Gemini, Claude, Qwen)
# Key holen: https://openrouter.ai/keys
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemini-3.1-flash-lite

# IONOS AI Model Hub (Server in Deutschland, DSGVO-konform)
# Nur fuer die Text-Veredelung, nicht fuer die Transkription selbst.
# Key holen: https://cloud.ionos.com (AI Model Hub)
IONOS_API_KEY=
IONOS_MODEL=mistralai/Mistral-Small-24B-Instruct

# Kurze Texte unterhalb dieser Wortanzahl ueberspringen den LLM-Schritt
LLM_WORD_THRESHOLD=10

# Language: de, en
LANGUAGE=de

# Logging Level
LOG_LEVEL=INFO

# Rohtext-Modus: true ueberspringt die KI-Text-Veredelung komplett, nur
# Transkription + Post-Processing (Fuellwoerter, Woerterbuch, Satzzeichen).
# Ueblicherweise per Tray-Schnellumschaltung gesetzt, nicht von Hand.
RAW_TEXT_MODE=false
"""
        return template

    @staticmethod
    def init_env_file():
        """Erstelle .env Datei falls nicht vorhanden"""
        env_file = CONFIG_DIR / ".env"
        if not env_file.exists():
            env_file.write_text(NovaFlowConfig.create_env_template())
            print(f"[OK] .env erstellt: {env_file}")


# Globale Config-Instanz
config = NovaFlowConfig()
