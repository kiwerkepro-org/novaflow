"""
NovaFlow Text Processor – Post-Processing für bessere Text-Qualität
Entfernt Grundlaute, normalisiert Abstände, filtert Duplikate.
Reine Textlogik, keine Betriebssystem-Abhaengigkeit – unveraendert
gegenueber dem bisherigen NovaFlow uebernommen.
"""
import re
from utils.logger import logger


class TextProcessor:
    """Verbessert Whisper-Output durch Post-Processing"""

    BUILTIN_CORRECTIONS = {
        'flubar': 'Flowbar',
        'flow bären': 'Flowbar',
        'flow bär': 'Flowbar',
        'flo bar': 'Flowbar',
        'nawa flo': 'Nova Flow',
        'nawa flow': 'Nova Flow',
        'nowa flow': 'Nova Flow',
        'nöwa flow': 'Nova Flow',
        'no wa flow': 'Nova Flow',
        'no va flow': 'Nova Flow',
        'no flow': 'Nova Flow',
        'nova flo': 'Nova Flow',
        'nova flaw': 'Nova Flow',
        'nova flow': 'Nova Flow',
        'nova': 'Nova',
        'nöwa': 'Nova',
        'nawa': 'Nova',
        'wispr': 'Wispr',
        'wispr flow': 'Wispr Flow',
        'wisper flow': 'Wispr Flow',
        'wisper': 'Wispr',
        'wisperflow': 'Wispr Flow',
        'wisper_flow': 'Wispr Flow',
        'k i': 'KI',
        'llm': 'LLM',
        'api': 'API',
        'sdk': 'SDK',
        'url': 'URL',
        'ide': 'IDE',
        'gui': 'GUI',
        'sla': 'SLA',
        'crm': 'CRM',
        'prompt': 'Prompt',
        'prompting': 'Prompting',
        'prompten': 'Prompten',
    }

    FILLER_WORDS_DE = {
        'äh', 'ähm', 'ähh', 'ähem', 'ää', 'öhm', 'öh',
        'hmm', 'hm', 'mm', 'mhm',
        'hä', 'uh',
    }

    FILLER_WORDS_EN = {
        'um', 'uh', 'uhm', 'err', 'erm',
    }

    SPOKEN_PUNCTUATION_DE = [
        (r'\bdrei\s+punkte\b',            '...'),
        (r'\bauslassungspunkte\b',         '...'),
        (r'\bpunkt\b',                     '.'),
        (r'\bkomma\b',                     ','),
        (r'\bfragezeichen\b',              '?'),
        (r'\bausrufezeichen\b',            '!'),
        (r'\bdoppelpunkt\b',               ':'),
        (r'\bsemikolon\b',                 ';'),
        (r'\bstrichpunkt\b',               ';'),
        (r'\bbindestrich\b',               '-'),
        (r'\bklammer\s+auf\b',             '('),
        (r'\bklammer\s+zu\b',              ')'),
        (r'\banf(?:ü|ue)hrungszeichen\b',  '"'),
        (r'\bneu(?:e|en|er)?\s+zeile\b',   '\n'),
        (r'\bneu(?:e|en|er)?\s+absatz\b',  '\n\n'),
        (r'\bunderstrich\b',               '_'),
        (r'\bunterstrich\b',               '_'),
        (r'\bschr(?:ä|ae)gstrich\b',       '/'),
        (r'\bgedankenstrich\b',            '-'),
        (r'\bminuszeichen\b',              '-'),
        (r'\bstrich\b',                    '-'),
        (r'\bprozent\b',                   '%'),
        (r'\beuro\b',                      '€'),
        (r'\bat-zeichen\b',               '@'),
        (r'\bparagraf\b',                  '§'),
    ]

    def __init__(self, language: str = "de"):
        """
        Initialisiert Text Processor

        Args:
            language: "de" oder "en"
        """
        self.language = language
        self.filler_words = (
            self.FILLER_WORDS_DE if language == "de" else self.FILLER_WORDS_EN
        )

    HALLUCINATION_PREFIXES = [
        "this is dante's",
        "thank you for watching",
        "thank you.",
        "thanks for watching",
        "please subscribe",
        "this is a test",
        "this is the",
        "this is a",
        "this video",
        "subtitles by",
        "transcribed by",
        "www.",
        "http",
    ]

    def strip_hallucinations(self, text: str) -> str:
        """Entfernt bekannte Whisper-Halluzinationen am Textanfang"""
        if not text:
            return text

        lower = text.lower().strip()
        for prefix in self.HALLUCINATION_PREFIXES:
            if lower.startswith(prefix):
                rest = text[len(prefix):].lstrip(" .,")
                if rest:
                    return rest
                return text

        return text

    def remove_filler_words(self, text: str) -> str:
        """Entfernt Grundlaute und Filler Words (Groß-/Kleinschreibung wird beibehalten)"""
        if not text:
            return text

        words = text.split()
        filtered_words = []

        for word in words:
            clean_word = re.sub(r'[.,!?;:]', '', word).lower()
            if clean_word not in self.filler_words and clean_word.strip():
                filtered_words.append(word)

        return " ".join(filtered_words)

    def remove_duplicates(self, text: str, window: int = 8) -> str:
        """Entfernt wiederholte Wort-Sequenzen (auch über Kommas hinweg)"""
        if not text:
            return text

        words = text.split()
        result = []
        last_clean_word = None

        for word in words:
            clean_word = re.sub(r'[.,!?;:]', '', word).lower()

            if not clean_word:
                result.append(word)
                continue

            if clean_word == last_clean_word:
                continue

            result.append(word)
            last_clean_word = clean_word

        return " ".join(result)

    def normalize_spacing(self, text: str) -> str:
        """Normalisiert Abstände und Satzzeichen"""
        if not text:
            return text

        text = re.sub(r'[ \t]+', ' ', text)
        text = re.sub(r'[ \t]+([.,!?;:])', r'\1', text)
        text = re.sub(r',([^\s.,!?;:])', r', \1', text)
        text = re.sub(r'([.!?;:])([^\s.,!?;:])', r'\1 \2', text)
        text = re.sub(r'([.,!?;:])\1+', r'\1', text)
        text = re.sub(r',\s*\.', '.', text)
        text = re.sub(r'\(\s+', '(', text)
        text = re.sub(r'\s+\)', ')', text)
        text = re.sub(r'[ \t]*\n[ \t]*', '\n', text)

        return text.strip()

    # Nach jeweils 5 bzw. 6 Saetzen ein Absatz, abwechselnd (JJ, 2026-07-28),
    # statt starr immer bei derselben Zahl - wirkt dadurch weniger
    # mechanisch als ein fester Wert.
    _SENTENCE_SPLIT_RE = re.compile(r'(?<=[.!?])\s+')

    def insert_paragraph_breaks(self, text: str) -> str:
        """Fuegt bei laengeren Diktaten nach etwa 5 bis 6 Saetzen einen
        Absatz ein, damit ein langes Diktat nicht als eine einzige, lange
        durchgehende "Wurscht" erscheint (JJ, 2026-07-28).

        Greift bewusst NICHT ein, wenn der Text bereits einen Zeilenumbruch
        enthaelt: hat der Nutzer selbst schon "neue Zeile" oder "neuer
        Absatz" gesprochen (siehe SPOKEN_PUNCTUATION_DE), soll diese
        bewusste Formatierung nicht durch eine automatische ueberschrieben
        oder verdoppelt werden. Ebenso bei zu kurzen Texten (weniger als
        sechs Saetze): dort braucht es keine zusaetzliche Gliederung.
        """
        if not text or "\n" in text:
            return text

        sentences = [s for s in self._SENTENCE_SPLIT_RE.split(text.strip()) if s]
        if len(sentences) < 6:
            return text

        out = []
        count = 0
        target = 5
        last_index = len(sentences) - 1
        for idx, sentence in enumerate(sentences):
            out.append(sentence)
            count += 1
            if idx == last_index:
                continue
            if count >= target:
                out.append("\n\n")
                count = 0
                target = 6 if target == 5 else 5
            else:
                out.append(" ")

        return "".join(out)

    def capitalize_sentences(self, text: str) -> str:
        """Großschreibung nach Satzzeichen und am Zeilenanfang"""
        if not text:
            return text

        text = text[0].upper() + text[1:] if text else text
        text = re.sub(r'([.!?]\s+)([a-zäöü])', lambda m: m.group(1) + m.group(2).upper(), text)
        text = re.sub(r'(\n\s*)([a-zäöü])', lambda m: m.group(1) + m.group(2).upper(), text)

        return text

    def remove_repeated_chars(self, text: str) -> str:
        """Entfernt wiederholte Buchstaben (z.B. 'jaaaa' -> 'ja')"""
        if not text:
            return text

        text = re.sub(r'(\w)\1{2,}', r'\1\1', text)
        return text

    def apply_builtin_corrections(self, text: str) -> str:
        """Korrigiert eingebaute Falsch-Erkennungen (Domain-spezifisch)"""
        if not text:
            return text

        for spoken, correction in self.BUILTIN_CORRECTIONS.items():
            pattern = r'\b' + re.escape(spoken) + r'\b'
            text = re.sub(pattern, correction, text, flags=re.IGNORECASE)

        return text

    def apply_dictionary(self, text: str) -> str:
        """Substituiert bekannte Falsch-Erkennungen via Dictionary (user + builtin)"""
        if not text:
            return text

        text = self.apply_builtin_corrections(text)

        try:
            from utils.dictionary_store import dictionary_store
            substitutions = dictionary_store.get_substitutions()
            if not substitutions:
                return text

            for spoken, correction in substitutions.items():
                pattern = r'\b' + re.escape(spoken) + r'\b'
                text = re.sub(pattern, correction, text, flags=re.IGNORECASE)

            return text
        except Exception as e:
            logger.warning(f"Fehler in apply_dictionary: {e}")
            return text

    def apply_snippets(self, text: str) -> str:
        """Expandiert Trigger-Wörter zu vollständigen Texten via Snippets"""
        if not text:
            return text

        try:
            from utils.snippets_store import snippets_store
            expansions = snippets_store.get_expansions()
            if not expansions:
                return text

            for trigger, expansion in expansions.items():
                pattern = r'\b' + re.escape(trigger) + r'\b'
                text = re.sub(pattern, lambda m: expansion, text, flags=re.IGNORECASE)

            return text
        except Exception as e:
            logger.warning(f"Fehler in apply_snippets: {e}")
            return text

    def replace_spoken_punctuation(self, text: str) -> str:
        """Ersetzt gesprochene Satzzeichen durch Symbole (z.B. 'Punkt' → '.')"""
        if not text:
            return text

        for pattern, replacement in self.SPOKEN_PUNCTUATION_DE:
            text = re.sub(pattern, replacement, text, flags=re.IGNORECASE)

        text = re.sub(r'[ \t]+([.,!?:;])', r'\1', text)

        return text

    def process(self, text: str, verbose: bool = False) -> str:
        """
        Führt alle Post-Processing-Schritte aus

        Args:
            text: Roher Text von Whisper
            verbose: Zeige Debug-Info

        Returns:
            Verarbeiteter Text
        """
        if not text or not text.strip():
            return text

        original = text

        text = self.strip_hallucinations(text)
        text = self.remove_filler_words(text)
        text = self.remove_repeated_chars(text)
        text = self.remove_duplicates(text)
        text = self.apply_dictionary(text)
        text = self.apply_snippets(text)
        text = self.replace_spoken_punctuation(text)
        text = self.normalize_spacing(text)
        text = self.capitalize_sentences(text)

        if verbose:
            logger.debug(f"Original: {original[:100]}...", f"Original: {original[:100]}...")
            logger.debug(f"Verarbeitet: {text[:100]}...", f"Processed: {text[:100]}...")

        return text
