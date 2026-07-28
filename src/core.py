"""
NovaFlow Core – Audio Transcription Module
Unterstuetzt lokales Whisper und Cloud-basiertes Voxtral via OpenRouter.
Plattformunabhaengig (Windows/Mac/Linux) – keine Aenderung gegenueber dem
bisherigen NovaFlow noetig, faster-whisper und die OpenRouter-API sind
bereits auf allen drei Plattformen lauffaehig.
"""
from pathlib import Path
from typing import Optional
from faster_whisper import WhisperModel

from utils.logger import logger
from utils.config import config
from utils.secure_config import secure_config


class WhisperCore:
    """Whisper-Transkriptions-Engine mit Error-Handling"""

    def __init__(self, model_size: Optional[str] = None):
        """
        Initialisiert das Whisper-Modell

        Args:
            model_size: "tiny", "base", "small", "medium" oder "large-v3"
                       Falls None, wird Wert aus Config verwendet
        """
        self.model_size = model_size or config.get("WHISPER_MODEL_SIZE", "base")
        self.device = config.get("WHISPER_DEVICE", "auto")
        self.model = None
        # Siehe gleichnamige Erklaerung bei VoxtralCore.
        self.last_error = None
        self._load_model()

    def _load_model(self):
        """Laedt Whisper-Modell in den RAM"""
        try:
            logger.info(
                f"Lade Whisper-Modell '{self.model_size}'...",
                f"Loading Whisper model '{self.model_size}'..."
            )

            self.model = WhisperModel(
                self.model_size,
                device=self.device,
                compute_type="default"
            )

            logger.success(
                f"Whisper-Modell geladen ({self.device})",
                f"Whisper model loaded ({self.device})"
            )

        except Exception as e:
            logger.error(
                f"Fehler beim Laden des Modells: {str(e)}",
                f"Error loading model: {str(e)}"
            )
            raise

    def transcribe_audio(self, audio_filepath: str) -> str:
        """
        Transkribiert Audiodatei zu Text

        Args:
            audio_filepath: Pfad zur Audiodatei (WAV, MP3, etc.)

        Returns:
            Transkribierter Text
        """
        self.last_error = None

        if not self.model:
            self.last_error = "Whisper-Modell ist nicht geladen"
            logger.error("Modell nicht geladen", "Model not loaded")
            return ""

        audio_path = Path(audio_filepath)
        if not audio_path.exists():
            self.last_error = "Aufnahmedatei nicht gefunden"
            logger.error(
                f"Audiodatei nicht gefunden: {audio_filepath}",
                f"Audio file not found: {audio_filepath}"
            )
            return ""

        try:
            logger.info(
                f"Transkribiere Datei: {audio_path.name}...",
                f"Transcribing file: {audio_path.name}..."
            )

            segments, info = self.model.transcribe(
                str(audio_filepath),
                beam_size=5,
                language="de"
            )

            transcribed_text = " ".join([segment.text for segment in segments])

            if transcribed_text.strip():
                logger.success(
                    f"Transkription erfolgreich ({len(transcribed_text)} Zeichen)",
                    f"Transcription successful ({len(transcribed_text)} chars)"
                )
            else:
                logger.warning("Keine Sprache erkannt", "No speech detected")

            return transcribed_text.strip()

        except Exception as e:
            self.last_error = f"Whisper-Transkription fehlgeschlagen: {str(e)}"
            logger.error(
                f"Transkriptions-Fehler: {str(e)}",
                f"Transcription error: {str(e)}"
            )
            return ""

    def get_model_info(self) -> dict:
        """Gibt Informationen ueber das geladene Modell"""
        return {
            "model_size": self.model_size,
            "device": self.device,
            "status": "loaded" if self.model else "not_loaded"
        }


class VoxtralCore:
    """Voxtral-Transkriptions-Engine via OpenRouter API"""

    MODEL = "mistralai/voxtral-mini-transcribe"
    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self):
        self.api_key = secure_config.get("OPENROUTER_API_KEY")
        self.language = config.get("LANGUAGE", "de")
        # Merkt sich, ob der letzte Versuch an einem echten Fehler gescheitert
        # ist (Netzwerk, API) oder ob schlicht keine Sprache erkannt wurde.
        # Beides liefert einen leeren Text zurueck, fuehlt sich fuer den
        # Nutzer aber voellig unterschiedlich an: "Bitte lauter sprechen" ist
        # bei einem Verbindungsabbruch schlicht falsch und schickt ihn auf
        # die Suche nach einem Problem, das gar nicht existiert.
        self.last_error = None

    def is_available(self) -> bool:
        return bool(self.api_key)

    def transcribe_audio(self, audio_filepath: str) -> str:
        """
        Transkribiert Audiodatei via Voxtral Mini (OpenRouter)

        Args:
            audio_filepath: Pfad zur Audiodatei (WAV, MP3, etc.)

        Returns:
            Transkribierter Text
        """
        self.last_error = None

        if not self.is_available():
            self.last_error = "Kein OpenRouter API-Schlüssel hinterlegt"
            logger.error(
                "OPENROUTER_API_KEY nicht gesetzt – Voxtral nicht verfuegbar",
                "OPENROUTER_API_KEY not set – Voxtral unavailable"
            )
            return ""

        audio_path = Path(audio_filepath)
        if not audio_path.exists():
            self.last_error = "Aufnahmedatei nicht gefunden"
            logger.error(
                f"Audiodatei nicht gefunden: {audio_filepath}",
                f"Audio file not found: {audio_filepath}"
            )
            return ""

        try:
            logger.info("Transkribiere via Voxtral (OpenRouter)...", "Transcribing via Voxtral (OpenRouter)...")
            import base64
            import requests

            with open(str(audio_filepath), "rb") as audio_file:
                audio_data = base64.b64encode(audio_file.read()).decode("utf-8")

            response = requests.post(
                f"{self.BASE_URL}/audio/transcriptions",
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                    "HTTP-Referer": "https://novaflow.app",
                    "X-OpenRouter-Title": "NovaFlow"
                },
                json={
                    "model": self.MODEL,
                    "language": self.language,
                    "input_audio": {
                        "data": audio_data,
                        "format": "wav"
                    }
                },
                timeout=30
            )

            if response.status_code != 200:
                raise Exception(f"HTTP {response.status_code}: {response.text}")

            text = response.json().get("text", "").strip()

            if text:
                logger.success(
                    f"Voxtral-Transkription erfolgreich ({len(text)} Zeichen)",
                    f"Voxtral transcription successful ({len(text)} chars)"
                )
            else:
                logger.warning("Keine Sprache erkannt", "No speech detected")

            return text

        except Exception as e:
            text = str(e)
            if "timed out" in text.lower() or "timeout" in text.lower():
                self.last_error = (
                    "Zeitüberschreitung beim Hochladen der Aufnahme. Die Internetverbindung "
                    "war zu langsam oder ausgelastet, das Diktat konnte nicht übertragen werden."
                )
            else:
                self.last_error = f"Übertragung an OpenRouter fehlgeschlagen: {text}"
            logger.error(f"Voxtral-Fehler: {text}", f"Voxtral error: {text}")
            return ""

    def get_model_info(self) -> dict:
        """Gibt Informationen ueber den Voxtral-Provider"""
        return {
            "model": self.MODEL,
            "provider": "OpenRouter",
            "language": self.language,
            "status": "bereit" if self.is_available() else "kein API-Key"
        }
