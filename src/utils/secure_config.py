"""
NovaFlow Secure Config – Nutzt den plattformeigenen Credential-Speicher fuer API-Keys
(Windows Credential Manager, macOS Schluesselbund, Linux Secret Service via keyring)
Sensitive Daten: Credential-Speicher
Non-sensitive Daten: .env Datei
"""
import sys
from pathlib import Path
from typing import Optional

try:
    import keyring
    KEYRING_AVAILABLE = True
except ImportError:
    KEYRING_AVAILABLE = False

from utils.config import config as dot_env_config
from utils.paths import get_project_root


class SecureConfig:
    """
    Sichere Konfiguration für NovaFlow
    - Sensitive Daten (API-Keys) -> plattformeigener Credential-Speicher (keyring)
    - Non-sensitive Daten -> .env Datei

    keyring waehlt automatisch das passende Backend: Windows Credential Manager
    unter Windows, Schluesselbund unter macOS, Secret Service (z.B. GNOME
    Keyring) unter Linux. Ist kein Backend verfuegbar, faellt alles auf die
    .env Datei zurueck, das ist weniger sicher, aber funktioniert ueberall.
    """

    # Sensitive Felder die im Credential-Speicher gespeichert werden
    SENSITIVE_FIELDS = {
        "OPENROUTER_API_KEY",
    }

    # Non-sensitive Felder die in .env bleiben
    NON_SENSITIVE_FIELDS = {
        "HOTKEY",
        "SAMPLE_RATE",
        "STT_PROVIDER",
        "WHISPER_MODEL_SIZE",
        "WHISPER_DEVICE",
        "LLM_PROVIDER",
        "LLM_MODEL",
        "OLLAMA_BASE_URL",
        "OLLAMA_TIMEOUT",
        "LLM_WORD_THRESHOLD",
        "LANGUAGE",
        "LOG_LEVEL",
    }

    SERVICE_NAME = "NovaFlow"

    @staticmethod
    def get(key: str, default=None):
        """
        Liest einen Konfigurationswert
        - Sensitive Felder aus dem Credential-Speicher
        - Andere aus .env
        """
        if key in SecureConfig.SENSITIVE_FIELDS:
            return SecureConfig._get_credential(key, default)
        return dot_env_config.get(key, default)

    @staticmethod
    def set(key: str, value: str) -> bool:
        """
        Speichert einen Konfigurationswert
        - Sensitive Felder im Credential-Speicher
        - Andere in .env
        """
        if key in SecureConfig.SENSITIVE_FIELDS:
            return SecureConfig._set_credential(key, value)
        else:
            return SecureConfig._set_env(key, value)

    @staticmethod
    def _get_credential(key: str, default=None) -> Optional[str]:
        """Liest Credential aus dem Credential-Speicher oder direkt aus .env"""
        if not KEYRING_AVAILABLE:
            return SecureConfig._read_from_env_file(key, default)

        try:
            credential = keyring.get_password(SecureConfig.SERVICE_NAME, key)
            if credential:
                return credential
            # Noch nichts im Credential-Speicher hinterlegt (z.B. weil der Key
            # nur von Hand in die .env eingetragen wurde, nie über die
            # Einstellungen gespeichert) -> dort nachschauen statt sofort
            # auf den Default zurueckzufallen.
            return SecureConfig._read_from_env_file(key, default)
        except Exception as e:
            print(f"[Warning] Fehler beim Lesen aus dem Credential-Speicher: {e}")
            return SecureConfig._read_from_env_file(key, default)

    @staticmethod
    def _read_from_env_file(key: str, default=None) -> Optional[str]:
        """Liest Wert direkt aus .env Datei (umgeht In-Memory-Cache)"""
        import re
        env_file = get_project_root() / ".env"
        if not env_file.exists():
            return default
        try:
            content = env_file.read_text()
            match = re.search(rf"^{re.escape(key)}=(.*)$", content, re.MULTILINE)
            if match:
                value = match.group(1).strip()
                return value if value else default
        except Exception:
            pass
        return default

    @staticmethod
    def _set_credential(key: str, value: str) -> bool:
        """Speichert Credential im Credential-Speicher"""
        if not KEYRING_AVAILABLE:
            return SecureConfig._set_env(key, value)

        try:
            keyring.set_password(SecureConfig.SERVICE_NAME, key, value)
            return True
        except Exception as e:
            print(f"[Error] Fehler beim Speichern im Credential-Speicher: {e}")
            return False

    @staticmethod
    def _set_env(key: str, value: str) -> bool:
        """Speichert Wert in .env Datei"""
        import re

        env_file = get_project_root() / ".env"

        if env_file.exists():
            content = env_file.read_text()
        else:
            content = ""

        pattern = f"^{key}=.*$"
        if re.search(pattern, content, re.MULTILINE):
            content = re.sub(pattern, f"{key}={value}", content, flags=re.MULTILINE)
        else:
            content += f"\n{key}={value}"

        try:
            env_file.write_text(content)
            dot_env_config.set(key, value)
            return True
        except Exception as e:
            print(f"[Error] Fehler beim Speichern in .env: {e}")
            return False

    @staticmethod
    def delete(key: str) -> bool:
        """Löscht einen Konfigurationswert"""
        if key in SecureConfig.SENSITIVE_FIELDS and KEYRING_AVAILABLE:
            try:
                keyring.delete_password(SecureConfig.SERVICE_NAME, key)
                return True
            except Exception as e:
                print(f"[Warning] Konnte Credential nicht löschen: {e}")
                return False
        return True

    @staticmethod
    def is_sensitive(key: str) -> bool:
        """Prüft ob ein Feld sensitiv ist"""
        return key in SecureConfig.SENSITIVE_FIELDS

    @staticmethod
    def get_credential_status() -> dict:
        """Zeigt Status der Credential-Speicher Integration"""
        return {
            "credential_manager_available": KEYRING_AVAILABLE,
            "platform": sys.platform,
            "service_name": SecureConfig.SERVICE_NAME,
        }


# Globale Instanz
secure_config = SecureConfig()
