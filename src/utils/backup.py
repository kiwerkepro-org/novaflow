"""
NovaFlow Verschlüsseltes Backup
Buendelt die bestehenden Datendateien (Woerterbuch, Ausschnitte, Notizbuch,
Schreibstil, Verlauf, Lernschleife-Feedback sowie die .env mit den
nicht-sensiblen Einstellungen) zu einer einzigen, mit Passwort
verschluesselten Datei (JJ, 2026-07-27).

Bewusste Design-Entscheidungen:

- AES-256-GCM statt selbstgebauter Verschluesselung. Reines XOR/Hash-
  basteln aus hashlib/hmac waere zwar "nur Standardbibliothek" im
  woertlichsten Sinne, gilt aber zurecht als Security-Antipattern ("roll
  your own crypto"). Das Paket "cryptography" ist die de-facto Standard-
  bibliothek fuer Verschluesselung im Python-Oekosystem (siehe
  requirements.txt) und bietet echte, gepruefte AES-GCM-Implementierung
  inklusive Integritaetsschutz (ein manipuliertes oder falsches Passwort
  fuehrt zu einem klar erkennbaren Fehler statt zu stillschweigend falsch
  entschluesselten Daten).
- PBKDF2-HMAC-SHA256 mit zufaelligem Salt pro Backup leitet aus dem
  Nutzer-Passwort einen 256-Bit-Schluessel ab, GCM braucht dafuer keinen
  separaten Integritaets-Layer.
- Beim Wiederherstellen wird eine feste Allowlist bekannter Dateinamen
  durchgesetzt (ZIP_ALLOWLIST), das verhindert Zip-Slip/Pfad-Traversal
  durch eine manipulierte Backup-Datei (z.B. ein Eintrag "../../evil.py").
"""
import io
import json
import os
import zipfile
from pathlib import Path
from typing import Optional

from cryptography.exceptions import InvalidTag
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
from cryptography.hazmat.primitives.kdf.pbkdf2 import PBKDF2HMAC
from cryptography.hazmat.primitives import hashes

from utils.paths import get_user_data_dir, get_project_root

# Magic-Header am Anfang jeder Backup-Datei: erlaubt spaeteren Versionen,
# alte Backups zu erkennen/abzulehnen, statt bei einem Format-Wechsel mit
# einer kryptischen Fehlermeldung irgendwo mitten in der Entschluesselung
# zu scheitern.
MAGIC = b"NFBK1"

SALT_SIZE = 16
NONCE_SIZE = 12
# PBKDF2-Iterationen: 480.000 orientiert sich an den aktuellen OWASP-
# Empfehlungen fuer PBKDF2-HMAC-SHA256 (Stand 2026), bewusst kein
# niedrigerer Wert nur wegen Geschwindigkeit, ein Backup wird nicht staendig
# neu erstellt.
KDF_ITERATIONS = 480_000

# Bekannte Datendateien in ~/.novaflow, siehe die jeweiligen *_store.py.
# Bewusst eine feste Liste statt "alles im Ordner einsammeln": neue,
# unerwartete Dateien im Datenordner (z.B. vom Betriebssystem angelegte
# Metadaten) sollen nicht ungefragt mit ins Backup wandern, und beim
# Wiederherstellen dient dieselbe Liste als Allowlist gegen Zip-Slip.
DATA_FILES = [
    "dictionary.json",
    "snippets.json",
    "notes.json",
    "style.json",
    "feedback.json",
    "history.json",
]

# Die .env liegt NICHT in ~/.novaflow, sondern im Projektordner, und wird
# deshalb separat behandelt statt in DATA_FILES zu stehen. Sie enthaelt
# nicht-sensible Einstellungen (siehe SecureConfig.NON_SENSITIVE_FIELDS in
# secure_config.py), kann aber auf Systemen ohne funktionierenden
# Credential-Speicher auch API-Keys enthalten, siehe SecureConfig._set_env
# Fallback - genau deshalb landet sie in einem VERSCHLUESSELTEN statt einem
# offenen Backup.
ENV_ARCNAME = ".env"


def _derive_key(password: str, salt: bytes) -> bytes:
    kdf = PBKDF2HMAC(
        algorithm=hashes.SHA256(),
        length=32,
        salt=salt,
        iterations=KDF_ITERATIONS,
    )
    return kdf.derive(password.encode("utf-8"))


def build_archive_bytes(data_dir: Path, env_path: Optional[Path] = None) -> bytes:
    """Buendelt alle vorhandenen Datendateien (+ optional .env) zu einem
    ZIP im Arbeitsspeicher. Fehlende Dateien werden stillschweigend
    uebersprungen (z.B. wurde noch nie ein Wörterbuch-Eintrag angelegt),
    das ist kein Fehlerfall."""
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as zf:
        for filename in DATA_FILES:
            path = data_dir / filename
            if path.exists():
                zf.writestr(filename, path.read_bytes())
        if env_path and env_path.exists():
            zf.writestr(ENV_ARCNAME, env_path.read_bytes())
    return buffer.getvalue()


def encrypt_bytes(data: bytes, password: str) -> bytes:
    """Verschluesselt beliebige Bytes mit einem aus dem Passwort
    abgeleiteten AES-256-GCM-Schluessel. Aufbau der Ausgabe:
    MAGIC (5) + Salt (16) + Nonce (12) + Ciphertext-mit-Auth-Tag."""
    salt = os.urandom(SALT_SIZE)
    nonce = os.urandom(NONCE_SIZE)
    key = _derive_key(password, salt)
    ciphertext = AESGCM(key).encrypt(nonce, data, associated_data=MAGIC)
    return MAGIC + salt + nonce + ciphertext


def decrypt_bytes(blob: bytes, password: str) -> bytes:
    """Entschluesselt eine mit encrypt_bytes() erzeugte Datei.

    Wirft ValueError bei falschem Format (kein NovaFlow-Backup bzw. zu
    kurz, um gueltig zu sein) und InvalidTag (aus cryptography), wenn das
    Passwort falsch ist ODER die Datei beschaedigt/manipuliert wurde. Der
    Aufrufer sollte beide Faelle dem Nutzer als "falsches Passwort oder
    beschaedigte Datei" praesentieren, GCM kann diese beiden Faelle nicht
    zuverlaessig unterscheiden.
    """
    header_len = len(MAGIC) + SALT_SIZE + NONCE_SIZE
    if len(blob) < header_len or blob[: len(MAGIC)] != MAGIC:
        raise ValueError("Keine gültige NovaFlow-Backup-Datei.")

    offset = len(MAGIC)
    salt = blob[offset: offset + SALT_SIZE]
    offset += SALT_SIZE
    nonce = blob[offset: offset + NONCE_SIZE]
    offset += NONCE_SIZE
    ciphertext = blob[offset:]

    key = _derive_key(password, salt)
    return AESGCM(key).decrypt(nonce, ciphertext, associated_data=MAGIC)


def create_encrypted_backup(
    dest_path: Path,
    password: str,
    data_dir: Optional[Path] = None,
    env_path: Optional[Path] = None,
) -> dict:
    """Erstellt eine verschluesselte Backup-Datei unter dest_path.

    Gibt eine kleine Zusammenfassung zurueck (welche Dateien enthalten
    waren), die die Oberflaeche direkt anzeigen kann.
    """
    if not password:
        raise ValueError("Ohne Passwort kein verschlüsseltes Backup.")

    data_dir = data_dir or get_user_data_dir()
    env_path = env_path if env_path is not None else (get_project_root() / ".env")

    included = [f for f in DATA_FILES if (data_dir / f).exists()]
    if env_path.exists():
        included.append(ENV_ARCNAME)

    archive = build_archive_bytes(data_dir, env_path)
    encrypted = encrypt_bytes(archive, password)

    dest_path = Path(dest_path)
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_bytes(encrypted)

    return {
        "path": str(dest_path),
        "included_files": included,
        "size_bytes": len(encrypted),
    }


def restore_encrypted_backup(
    src_path: Path,
    password: str,
    data_dir: Optional[Path] = None,
    env_path: Optional[Path] = None,
) -> dict:
    """Stellt ein mit create_encrypted_backup() erzeugtes Backup wieder her.

    Extrahiert NUR Eintraege, deren Name in DATA_FILES oder ENV_ARCNAME
    vorkommt (Allowlist gegen Zip-Slip/Pfad-Traversal durch eine
    manipulierte Datei), alles andere im Archiv wird ignoriert statt
    geschrieben.
    """
    data_dir = data_dir or get_user_data_dir()
    data_dir.mkdir(parents=True, exist_ok=True)
    env_path = env_path if env_path is not None else (get_project_root() / ".env")

    blob = Path(src_path).read_bytes()
    archive_bytes = decrypt_bytes(blob, password)

    allowlist = set(DATA_FILES) | {ENV_ARCNAME}
    restored = []
    with zipfile.ZipFile(io.BytesIO(archive_bytes)) as zf:
        for name in zf.namelist():
            if name not in allowlist:
                continue
            content = zf.read(name)
            target = env_path if name == ENV_ARCNAME else (data_dir / name)
            target.write_bytes(content)
            restored.append(name)

    return {"restored_files": restored}
