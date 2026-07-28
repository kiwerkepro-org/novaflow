"""Alle NovaFlow-Tests nacheinander ausfuehren: python tests/run_all.py"""
import subprocess, sys, os
here = os.path.dirname(os.path.abspath(__file__))
tests = ["test_engine.py", "test_download.py", "test_modal.py", "test_flow.py",
         "test_history_copy_feedback.py", "test_dictionary_import.py",
         "test_history_stats.py", "test_history_search.py", "test_backup.py",
         "test_text_processor.py", "test_history_sensitive_data.py", "test_hotkey_parsing.py"]
bad = []
for t in tests:
    r = subprocess.run([sys.executable, os.path.join(here, t)],
                       capture_output=True, text=True)
    print(f"{t:<18} {'BESTANDEN' if r.returncode==0 else 'FEHLGESCHLAGEN'}")
    if r.returncode:
        bad.append(t); print(r.stdout[-1500:]); print(r.stderr[-1500:])
print("\n" + ("ALLE TESTS BESTANDEN" if not bad else f"FEHLER IN: {bad}"))
sys.exit(1 if bad else 0)
