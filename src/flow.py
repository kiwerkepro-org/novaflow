"""
NovaFlow LLM-Provider System – EIN API-Key für alles
Alle Cloud-Models laufen über OpenRouter:
- Gemini 3.1 Flash Lite (Speed)
- Claude 3.5 Sonnet (Quality)
- Qwen 3.6 Plus (Reasoning/Expert)
Lokal: Ollama

Gegenueber dem bisherigen NovaFlow ist nur die Zwischenablage- und
Einfuege-Logik geaendert: die spricht jetzt ausschliesslich mit
platforms.get_platform(), nicht mehr direkt mit win32clipboard. Die
LLM-Provider selbst sind unveraendert, die waren schon plattformunabhaengig.
"""
import time
from abc import ABC, abstractmethod

from utils.logger import logger
from utils.config import config
from utils.secure_config import secure_config
from utils.style_store import style_store
from utils.dictionary_store import dictionary_store
from utils.feedback_store import feedback_store
from text_processor import TextProcessor
from platforms import get_platform


# =============================================================================
# MAGIC PROMPT – Strikt wie im Wispr-Flow Blueprint definiert
# =============================================================================
MAGIC_PROMPT = (
    "Du korrigierst deutschen Spracherkennungstext. Antworte NUR mit dem korrigierten Text.\n\n"
    "REGELN:\n"
    "- Alle Substantive/Nomen großschreiben (deutsches Grammatikgesetz)\n"
    "- Satzanfänge großschreiben\n"
    "- Zeichensetzung korrigieren\n"
    "- Fülllaute (äh, öhm, hmm) entfernen, alle anderen Wörter behalten\n\n"
    "BEISPIELE:\n"
    "Eingabe: dies ist ein test. das system funktioniert gut.\n"
    "Ausgabe: Dies ist ein Test. Das System funktioniert gut.\n\n"
    "Eingabe: heute abend teste ich mein neues spracherkennungssystem. es soll rechtschreibung und grammatik korrigieren.\n"
    "Ausgabe: Heute Abend teste ich mein neues Spracherkennungssystem. Es soll Rechtschreibung und Grammatik korrigieren.\n\n"
    "Eingabe: die verdopplung ist weg, jetzt bleibt nur noch die groß-kleinschreibung.\n"
    "Ausgabe: Die Verdopplung ist weg, jetzt bleibt nur noch die Groß- und Kleinschreibung.\n\n"
    "Jetzt korrigiere den folgenden Text:\n"
)

MAGIC_PROMPT_EXPERT = (
    "Du korrigierst deutschen Spracherkennungstext. Antworte NUR mit dem korrigierten Text.\n\n"
    "REGELN:\n"
    "- Alle Substantive/Nomen großschreiben (deutsches Grammatikgesetz)\n"
    "- Satzanfänge großschreiben\n"
    "- Zeichensetzung korrigieren\n"
    "- Fülllaute (äh, öhm, hmm) entfernen, alle anderen Wörter behalten\n"
    "- Fachbegriffe und Eigennamen korrekt schreiben\n\n"
    "BEISPIELE:\n"
    "Eingabe: dies ist ein test. das system funktioniert gut.\n"
    "Ausgabe: Dies ist ein Test. Das System funktioniert gut.\n\n"
    "Eingabe: heute abend teste ich mein neues spracherkennungssystem. es soll rechtschreibung und grammatik korrigieren.\n"
    "Ausgabe: Heute Abend teste ich mein neues Spracherkennungssystem. Es soll Rechtschreibung und Grammatik korrigieren.\n\n"
    "Eingabe: jetzt start novaflow drücken und dann testen.\n"
    "Ausgabe: Jetzt Start NovaFlow drücken und dann testen.\n\n"
    "{vocab_hint}"
    "Jetzt korrigiere den folgenden Text:\n"
)


class LLMProvider(ABC):
    """Abstrakte Basis-Klasse für alle LLM-Provider"""

    @abstractmethod
    def refine_text(self, raw_text: str) -> str:
        pass

    @abstractmethod
    def is_available(self) -> bool:
        pass

    @abstractmethod
    def get_name(self) -> str:
        pass

    def _get_vocabulary_hint(self) -> str:
        """Erstellt Vocabulary-Hinweis aus Dictionary für Expert-Modelle"""
        try:
            entries = dictionary_store.get_entries()
            if not entries or len(entries) == 0:
                return ""
            corrections = [e.get("correction", "") for e in entries[:20] if e.get("correction")]
            if not corrections:
                return ""
            terms_str = ", ".join(f"'{term}'" for term in corrections)
            return f"Bekannte Fachbegriffe und Eigennamen: {terms_str}.\n"
        except Exception:
            return ""

    def _get_style_hint(self) -> str:
        try:
            style = style_store.get_style()
            category = style.get("category", "work")
            tone = style.get("tone", "formal")
            category_prompts = {
                "personal": "Kontext: Persoenliche Nachricht.",
                "work": "Kontext: Berufliche Kommunikation.",
                "email": "Kontext: E-Mail.",
                "other": ""
            }
            tone_prompts = {
                "formal": "Schreibstil: Formell und professionell.",
                "casual": "Schreibstil: Locker und freundlich.",
                "excited": "Schreibstil: Enthusiastisch und begeistert."
            }
            cat_hint = category_prompts.get(category, "")
            tone_hint = tone_prompts.get(tone, "")
            parts = [p for p in [cat_hint, tone_hint] if p]
            return " ".join(parts) + "\n" if parts else ""
        except Exception:
            return ""


# =============================================================================
# OPENROUTER PROVIDER – Ein Key für alle: Gemini, Claude, Qwen
# =============================================================================
class OpenRouterProvider(LLMProvider):
    """OpenRouter API – Ein API-Key, alle Modelle"""

    BASE_URL = "https://openrouter.ai/api/v1"

    def __init__(self):
        self.api_key = secure_config.get("OPENROUTER_API_KEY")
        self.model = config.get("OPENROUTER_MODEL", "google/gemini-3.1-flash-lite")

    def is_available(self) -> bool:
        return bool(self.api_key)

    def refine_text(self, raw_text: str) -> str:
        """Verfeinert Text via OpenRouter"""
        if not self.is_available():
            return raw_text

        try:
            from openai import OpenAI

            client = OpenAI(
                api_key=self.api_key,
                base_url=self.BASE_URL,
                default_headers={
                    "HTTP-Referer": "https://novaflow.app",
                    "X-Title": "NovaFlow"
                }
            )

            active_model = self.model

            is_expert = any(kw in active_model.lower() for kw in ["qwen", "claude", "sonnet"])
            if is_expert:
                vocab_hint = self._get_vocabulary_hint()
                style_hint = self._get_style_hint()
                system_prompt = (
                    MAGIC_PROMPT_EXPERT.format(vocab_hint=vocab_hint)
                    if vocab_hint
                    else MAGIC_PROMPT + (style_hint if style_hint.strip() else "")
                )
                max_tokens = 1500
                api_timeout = 15
                logger.info(
                    f"Verfeinere Text mit OpenRouter ({active_model})...",
                    f"Refining text with OpenRouter ({active_model})..."
                )
            else:
                system_prompt = MAGIC_PROMPT
                max_tokens = 800
                api_timeout = 5
                logger.info(
                    f"Verfeinere Text mit OpenRouter ({active_model})...",
                    f"Refining text with OpenRouter ({active_model})..."
                )

            response = client.chat.completions.create(
                model=active_model,
                messages=[
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": raw_text}
                ],
                max_tokens=max_tokens,
                temperature=0.1,
                timeout=api_timeout
            )

            refined = response.choices[0].message.content.strip()

            if len(refined) > len(raw_text) * 2.5:
                logger.warning(
                    f"OpenRouter Ausgabe zu lang ({len(refined)} vs {len(raw_text)}) – Halluzination",
                    "OpenRouter output too long – hallucination detected"
                )
                return raw_text

            logger.success("Text verfeinert (OpenRouter)", "Text refined (OpenRouter)")
            return refined

        except Exception as e:
            logger.warning(f"OpenRouter Fehler: {str(e)}", f"OpenRouter error: {str(e)}")

        return raw_text

    def get_name(self) -> str:
        model_short = self.model.split('/')[-1] if '/' in self.model else self.model
        return f"OpenRouter ({model_short})"


# =============================================================================
# OLLAMA PROVIDER – Lokal & Offline
# =============================================================================
class OllamaProvider(LLMProvider):
    """Lokales Ollama LLM (Privacy/Offline)"""

    def __init__(self):
        self.base_url = config.get("OLLAMA_BASE_URL")
        self.model = config.get("LLM_MODEL", "gemma4:e4b")
        self.timeout = config.get("OLLAMA_TIMEOUT", 30)
        self._available = None

    def is_available(self) -> bool:
        if self._available is not None:
            return self._available
        try:
            import requests
            response = requests.get(f"{self.base_url}/api/tags", timeout=5)
            self._available = response.status_code == 200
            return self._available
        except Exception:
            self._available = False
            return False

    def refine_text(self, raw_text: str) -> str:
        if not self.is_available():
            return raw_text
        try:
            import requests
            logger.info(
                f"Verfeinere Text mit Ollama ({self.model})...",
                f"Refining text with Ollama ({self.model})..."
            )

            vocab_hint = self._get_vocabulary_hint()
            style_hint = self._get_style_hint()
            hints = (vocab_hint + style_hint).strip()
            system_prompt = MAGIC_PROMPT + ("\n" + hints if hints else "")

            correction_count = feedback_store.get_correction_count()
            few_shot_prompt = ""
            if correction_count >= 5:
                best_examples = feedback_store.get_best_examples(n=3)
                if best_examples:
                    few_shot_prompt = "\n\nGelernte Korrektionen (Beispiele):\n"
                    for ex in best_examples:
                        whisper = ex.get("whisper_raw", "")
                        correction = ex.get("user_correction", "")
                        if whisper and correction:
                            few_shot_prompt += f'Input: "{whisper}" → Ausgabe: "{correction}"\n'
                    system_prompt += few_shot_prompt
                    logger.info(f"Few-Shot: {len(best_examples)} Beispiele injiziert")

            response = requests.post(
                f"{self.base_url}/api/chat",
                json={
                    "model": self.model,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": raw_text}
                    ],
                    "stream": False,
                    "options": {"temperature": 0.0, "top_p": 0.1}
                },
                timeout=self.timeout
            )
            if response.status_code == 200:
                refined = response.json()["message"]["content"].strip()
                if len(refined) > len(raw_text) * 2.5:
                    logger.warning("Ollama Ausgabe zu lang – Halluzination")
                    return raw_text
                logger.success("Text verfeinert (Ollama)", "Text refined (Ollama)")
                return refined
        except Exception as e:
            logger.warning(f"Ollama Fehler: {str(e)}")
        return raw_text

    def get_name(self) -> str:
        return f"Ollama ({self.model})"


# =============================================================================
# DISABLED PROVIDER
# =============================================================================
class DisabledProvider(LLMProvider):
    """Keine KI – nur Transkription"""

    def is_available(self) -> bool:
        return True

    def refine_text(self, raw_text: str) -> str:
        logger.warning(
            "Keine KI-Veredelung aktiviert. Transkription wird direkt injiziert.",
            "No AI refinement enabled. Transcript will be injected directly."
        )
        return raw_text

    def get_name(self) -> str:
        return "Disabled"


# =============================================================================
# MAIN PROCESSOR
# =============================================================================
class NovaFlowProcessor:
    """NovaFlow Flow-Modul – LLM-Verarbeitung + Text-Injektion"""

    def __init__(self):
        self.providers = [
            OpenRouterProvider(),       # 0: Cloud via OpenRouter
            OllamaProvider(),           # 1: Offline/Lokal
            DisabledProvider(),         # 2: Nur Whisper
        ]
        self.active_provider = self._select_provider()
        language = config.get("LANGUAGE", "de")
        self.text_processor = TextProcessor(language=language)
        self.word_threshold = config.get("LLM_WORD_THRESHOLD", 10)
        logger.success(
            f"NovaFlow bereit – LLM: {self.active_provider.get_name()}",
            f"NovaFlow ready – LLM: {self.active_provider.get_name()}"
        )

    def _select_provider(self) -> LLMProvider:
        preferred = config.get("LLM_PROVIDER", "openrouter").lower()
        provider_map = {
            "openrouter": self.providers[0],
            "ollama": self.providers[1],
            "disabled": self.providers[2],
        }
        if preferred in provider_map:
            p = provider_map[preferred]
            if p.is_available():
                logger.info(f"Provider: {p.get_name()} (konfiguriert)")
                return p
            logger.warning(f"Gewünschter Provider '{preferred}' nicht verfügbar")
        for provider in self.providers:
            if provider.is_available():
                logger.info(f"Fallback Provider: {provider.get_name()}")
                return provider
        return DisabledProvider()

    def refine_text(self, raw_text: str) -> str:
        if not raw_text or not raw_text.strip():
            return raw_text
        processed_text = self.text_processor.process(raw_text)

        # Kurze Texte (z.B. einzelne Kommandos) ueberspringen den LLM-Schritt,
        # das spart Wartezeit, wenn ohnehin kaum etwas zu korrigieren ist.
        word_count = len(processed_text.split())
        if self.word_threshold and word_count < self.word_threshold:
            logger.debug(
                f"Text unter Wortschwelle ({word_count} < {self.word_threshold}) – LLM übersprungen",
                f"Text below word threshold ({word_count} < {self.word_threshold}) – LLM skipped"
            )
            return processed_text

        refined_text = self.active_provider.refine_text(processed_text)
        return refined_text

    def inject_text(self, text: str, interface=None):
        """
        Injiziert Text in aktives Fenster - NUR EINMAL

        Args:
            text: Der zu injizierende Text
            interface: FlowInterface-Instanz (für Overlay-Steuerung + Hotkey-Freigabe)
        """
        if not text:
            logger.warning("Kein Text zum Injizieren")
            if interface:
                interface.unblock_hotkey()
            return
        try:
            logger.info("Injiziere Text in aktives Fenster...")
            time.sleep(0.2)
            from pynput.keyboard import Controller

            platform = get_platform()
            clipboard = platform.clipboard
            text_with_space = text + " "

            # 1. Zwischenablage des Nutzers sichern (Text UND, wo unterstuetzt, Bilder)
            clipboard_backup = clipboard.backup()

            # 2. Diktierten Text zuverlaessig in die Zwischenablage legen
            clipboard.write_text(text_with_space)

            # 3. Einfuegen (Ctrl+V unter Windows/Linux, Cmd+V unter Mac)
            controller = Controller()
            modifier = platform.paste_key()
            controller.press(modifier)
            controller.press('v')
            controller.release('v')
            controller.release(modifier)

            # 4. Warten, bis das Zielfenster den Einfuegevorgang verarbeitet hat
            time.sleep(0.2)

            # 5. Inhalt des Nutzers wiederherstellen, ABER nur wenn er nicht selbst
            #    zwischenzeitlich etwas Neues kopiert hat.
            still_ours = False
            try:
                still_ours = (clipboard.read_text() == text_with_space)
            except Exception:
                still_ours = False
            if still_ours:
                clipboard.restore(clipboard_backup)

            logger.success("Text injiziert, Zwischenablage gesichert")

            if interface:
                interface.hide_overlay()
        except Exception as e:
            logger.error(f"Fehler beim Injizieren: {str(e)}")
            if interface:
                interface.hide_overlay()
        finally:
            if interface:
                interface.unblock_hotkey()
