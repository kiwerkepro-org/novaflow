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

        # LLM Settings
        "LLM_PROVIDER": "openrouter",  # openrouter, ollama, disabled
        "LLM_MODEL": "gemma4:e4b",  # Ollama Model
        "OLLAMA_BASE_URL": "http://localhost:11434",
        "OLLAMA_TIMEOUT": 30,
        "OPENROUTER_MODEL": "google/gemini-3.1-flash-lite",
        "LLM_WORD_THRESHOLD": 10,

        # API Keys (aus .env)
        "OPENROUTER_API_KEY": None,

        # Sprache
        "LANGUAGE": "de",  # de, en

        # Logging
        "LOG_LEVEL": "INFO",
    }

    def __init__(self):
        self.config = self.DEFAULTS.copy()
        self._load_from_env()

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
                elif key in ["WHISPER_DEVICE"]:
                    self.config[key] = env_value.lower()
                else:
                    self.config[key] = env_value

    def get(self, key: str, default=None) -> Any:
        """Hole Konfigurations-Wert"""
        return self.config.get(key, default)

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

# LLM Provider: openrouter, ollama, disabled
LLM_PROVIDER=openrouter
LLM_MODEL=gemma4:e4b

# Ollama Settings (lokal)
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_TIMEOUT=30

# OpenRouter API Key (ein Key fuer alle: Gemini, Claude, Qwen)
# Key holen: https://openrouter.ai/keys
OPENROUTER_API_KEY=
OPENROUTER_MODEL=google/gemini-3.1-flash-lite

# Kurze Texte unterhalb dieser Wortanzahl ueberspringen den LLM-Schritt
LLM_WORD_THRESHOLD=10

# Language: de, en
LANGUAGE=de

# Logging Level
LOG_LEVEL=INFO
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
