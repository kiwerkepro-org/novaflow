"""
NovaFlow Logger – Einheitliches Logging mit Deutsch/Englisch Support
(unveraendert gegenueber dem bisherigen NovaFlow, nur der Log-Ordner
kommt jetzt ueber die plattformsichere paths.get_project_root())
"""
import logging
import sys
from datetime import datetime

from utils.paths import get_project_root

# Logs-Verzeichnis
LOGS_DIR = get_project_root() / "logs"
LOGS_DIR.mkdir(exist_ok=True)

LOG_FILE = LOGS_DIR / f"novaflow-{datetime.now().strftime('%Y%m%d')}.log"


class NovaFlowLogger:
    """Logger für NovaFlow mit Konsolen- und Datei-Output"""

    def __init__(self, name="NovaFlow", language="de"):
        self.logger = logging.getLogger(name)
        self.logger.setLevel(logging.DEBUG)
        self.language = language

        # Verhindere doppelte Handler
        if self.logger.handlers:
            return

        # Formatter
        formatter = logging.Formatter(
            '[%(asctime)s] [%(levelname)s] %(message)s',
            datefmt='%Y-%m-%d %H:%M:%S'
        )

        # Console Handler (INFO + WARNING für User)
        console_handler = logging.StreamHandler(sys.stdout)
        console_handler.setLevel(logging.INFO)
        console_handler.setFormatter(formatter)
        self.logger.addHandler(console_handler)

        # File Handler (DEBUG für Debugging)
        file_handler = logging.FileHandler(LOG_FILE, encoding='utf-8')
        file_handler.setLevel(logging.DEBUG)
        file_handler.setFormatter(formatter)
        self.logger.addHandler(file_handler)

    def _translate(self, de_msg, en_msg):
        """Sprachunterstützung"""
        return de_msg if self.language == "de" else en_msg

    def info(self, de_msg, en_msg=None):
        self.logger.info(self._translate(de_msg, en_msg or de_msg))

    def warning(self, de_msg, en_msg=None):
        self.logger.warning(self._translate(de_msg, en_msg or de_msg))

    def error(self, de_msg, en_msg=None):
        self.logger.error(self._translate(de_msg, en_msg or de_msg))

    def debug(self, de_msg, en_msg=None):
        self.logger.debug(self._translate(de_msg, en_msg or de_msg))

    def success(self, de_msg, en_msg=None):
        """Erfolgs-Nachricht (grün, wenn möglich)"""
        self.logger.info(f"[SUCCESS] {self._translate(de_msg, en_msg or de_msg)}")


# Globale Logger-Instanz
logger = NovaFlowLogger(language="de")
