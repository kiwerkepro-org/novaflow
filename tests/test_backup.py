"""Tests fuer das verschluesselte Backup (JJ, 2026-07-27)."""
import io
import json
import os
import sys
import tempfile
import zipfile
from pathlib import Path

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT + "/src")

from cryptography.exceptions import InvalidTag

from utils import backup as bk

ok = []
fail = []


def check(n, c):
    (ok if c else fail).append(n)
    print(("  OK   " if c else "  FEHL ") + n)


tmp = Path(tempfile.mkdtemp(prefix="novaflow_backup_test_"))
data_dir = tmp / "data"
data_dir.mkdir()
env_path = tmp / ".env"
backup_path = tmp / "out.nfbackup"

(data_dir / "dictionary.json").write_text(
    json.dumps({"entries": [{"id": "1", "spoken": "nowa", "correction": "Nova"}]}), encoding="utf-8"
)
(data_dir / "history.json").write_text(
    json.dumps([{"id": "1", "raw": "hallo", "text": "Hallo.", "created_at": "2026-07-27T10:00:00"}]),
    encoding="utf-8",
)
env_path.write_text("LANGUAGE=de\n", encoding="utf-8")
# snippets.json, notes.json, style.json, feedback.json bewusst NICHT
# angelegt, um das "Datei existiert nicht -> einfach ueberspringen" zu testen.

print("\n=== build_archive_bytes: nur vorhandene Dateien landen im ZIP ===")
archive = bk.build_archive_bytes(data_dir, env_path)
with zipfile.ZipFile(io.BytesIO(archive)) as zf:
    names = set(zf.namelist())
check("dictionary.json enthalten", "dictionary.json" in names)
check("history.json enthalten", "history.json" in names)
check(".env enthalten", ".env" in names)
check("fehlende Dateien (snippets.json etc.) NICHT enthalten", "snippets.json" not in names)
check("genau 3 Dateien im Archiv", len(names) == 3)

print("\n=== encrypt_bytes / decrypt_bytes: Roundtrip ===")
payload = b"geheime nutzdaten 123 \x00\xff"
enc = bk.encrypt_bytes(payload, "korrekt-pw")
dec = bk.decrypt_bytes(enc, "korrekt-pw")
check("entschluesselte Daten stimmen mit Original ueberein", dec == payload)
check("verschluesselte Datei beginnt mit MAGIC-Header", enc.startswith(bk.MAGIC))

print("\n=== decrypt_bytes: falsches Passwort ===")
try:
    bk.decrypt_bytes(enc, "falsches-pw")
    check("falsches Passwort wirft InvalidTag", False)
except InvalidTag:
    check("falsches Passwort wirft InvalidTag", True)

print("\n=== decrypt_bytes: kaputte/fremde Datei ===")
try:
    bk.decrypt_bytes(b"das ist kein NovaFlow-Backup", "irgendwas")
    check("ungueltiges Format wirft ValueError", False)
except ValueError:
    check("ungueltiges Format wirft ValueError", True)

print("\n=== create_encrypted_backup / restore_encrypted_backup: voller Roundtrip ===")
result = bk.create_encrypted_backup(backup_path, "mein-sicheres-pw", data_dir=data_dir, env_path=env_path)
check("Backup-Datei wurde angelegt", backup_path.exists())
check("included_files listet dictionary.json, history.json, .env",
      set(result["included_files"]) == {"dictionary.json", "history.json", ".env"})

restore_dir = tmp / "restored"
restore_env = tmp / "restored.env"
restore_result = bk.restore_encrypted_backup(
    backup_path, "mein-sicheres-pw", data_dir=restore_dir, env_path=restore_env
)
check("dictionary.json wiederhergestellt", (restore_dir / "dictionary.json").exists())
check("history.json wiederhergestellt", (restore_dir / "history.json").exists())
check(".env in den EXPLIZIT uebergebenen Pfad wiederhergestellt (nicht ins echte Projekt)",
      restore_env.exists() and restore_env.read_text(encoding="utf-8") == "LANGUAGE=de\n")
restored_dict = json.loads((restore_dir / "dictionary.json").read_text(encoding="utf-8"))
check("Inhalt von dictionary.json stimmt", restored_dict["entries"][0]["correction"] == "Nova")
check("restored_files enthaelt .env", ".env" in restore_result["restored_files"])

print("\n=== restore_encrypted_backup: falsches Passwort ===")
try:
    bk.restore_encrypted_backup(
        backup_path, "falsches-pw", data_dir=tmp / "restored2", env_path=tmp / "restored2.env"
    )
    check("falsches Passwort bei Restore wirft InvalidTag", False)
except InvalidTag:
    check("falsches Passwort bei Restore wirft InvalidTag", True)

print("\n=== restore_encrypted_backup: Allowlist gegen Zip-Slip ===")
evil_buffer = io.BytesIO()
with zipfile.ZipFile(evil_buffer, "w") as zf:
    zf.writestr("dictionary.json", '{"entries": []}')
    zf.writestr("../../evil.txt", "boese nutzlast")
    zf.writestr("../evil2.txt", "auch boese")
evil_encrypted = bk.encrypt_bytes(evil_buffer.getvalue(), "pw")
evil_path = tmp / "evil.nfbackup"
evil_path.write_bytes(evil_encrypted)

evil_restore_dir = tmp / "evil_restored"
evil_result = bk.restore_encrypted_backup(
    evil_path, "pw", data_dir=evil_restore_dir, env_path=tmp / "evil_restored.env"
)
check("nur erlaubte Datei wiederhergestellt", evil_result["restored_files"] == ["dictionary.json"])
check("keine Datei ausserhalb des Zielordners gelandet",
      not (tmp / "evil.txt").exists() and not (tmp / "evil2.txt").exists())

print("\n=== create_encrypted_backup: leeres Passwort abgelehnt ===")
try:
    bk.create_encrypted_backup(tmp / "should_not_exist.nfbackup", "", data_dir=data_dir, env_path=env_path)
    check("leeres Passwort wirft ValueError", False)
except ValueError:
    check("leeres Passwort wirft ValueError", True)

print("\n=== ERGEBNIS ===")
print(f"bestanden: {len(ok)}   fehlgeschlagen: {len(fail)}")
if fail:
    print("FEHLER:", fail)
    sys.exit(1)
