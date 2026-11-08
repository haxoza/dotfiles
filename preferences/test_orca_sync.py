"""Exercise Orca's database updates and admission gate using temporary profiles."""

import hashlib
import importlib.util
import io
import json
import sqlite3
import tempfile
import unittest
from contextlib import closing
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "preference_sync", Path(__file__).with_name("sync.py")
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class OrcaSyncTests(unittest.TestCase):
    def setUp(self):
        temporary = tempfile.TemporaryDirectory()
        self.addCleanup(temporary.cleanup)
        self.root = Path(temporary.name)
        self.home = self.root / "home"
        self.definition = sync.load_sources()["orca"]
        self.target = self.home / self.definition["target"]
        self.target.parent.mkdir(parents=True)
        self.access = self.target.parents[2] / ".profile-state-access"
        (self.access / "participants").mkdir(parents=True)
        (self.access / "candidates").mkdir()
        self.live = {"theme": "system", "terminalFontFamily": "SF Mono",
                     "terminalFontSize": 13, "editorFontSize": 14,
                     "local": {"keep": True, "text": "Łódź 🐳"}}
        self.raw = json.dumps(self.live)
        with closing(sqlite3.connect(self.target)) as db, db:
            db.executescript("""
                PRAGMA user_version = 3;
                CREATE TABLE profile_state_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL);
                INSERT INTO profile_state_meta VALUES ('revision', '7'), ('profile_id', 'local-default');
                CREATE TABLE profile_state_documents (
                    domain TEXT PRIMARY KEY, payload TEXT NOT NULL, domain_version INTEGER NOT NULL,
                    revision INTEGER NOT NULL, updated_at INTEGER NOT NULL, content_hash TEXT NOT NULL);
            """)
            for domain, payload in [("settings", self.raw), ("repos", "[]")]:
                db.execute("INSERT INTO profile_state_documents VALUES (?, ?, 1, 7, 100, ?)",
                           (domain, payload, hashlib.sha256(payload.encode()).hexdigest()))
        (self.root / "orca").mkdir()
        (self.root / "orca/settings.json").write_text(json.dumps({
            "theme": "dark", "terminalFontFamily": "JetBrains Mono", "terminalFontSize": 14,
        }))
        for mock in [patch.object(sync, "ROOT", self.root),
                     patch.object(sync.Path, "home", return_value=self.home),
                     patch.object(sync, "load_sources", return_value={"orca": self.definition}),
                     patch("sys.stdout", new_callable=io.StringIO)]:
            mock.start()
            self.addCleanup(mock.stop)

    def run_sync(self, action):
        with patch("sys.argv", ["sync.py", action, "orca"]):
            sync.main()

    def test_apply_preserves_other_settings_and_domains_and_updates_metadata(self):
        self.run_sync("apply")
        _, live = sync.read_orca(self.target)  # Also verifies the new checksum.
        self.assertEqual(live, {**self.live, "theme": "dark",
                               "terminalFontFamily": "JetBrains Mono", "terminalFontSize": 14})
        with closing(sqlite3.connect(self.target)) as db, db:
            self.assertEqual(db.execute("SELECT value FROM profile_state_meta WHERE key='revision'").fetchone(), ("8",))
            self.assertEqual(db.execute("SELECT revision, updated_at FROM profile_state_documents WHERE domain='repos'").fetchone(), (7, 100))
            self.assertEqual(db.execute("SELECT revision FROM profile_state_documents WHERE domain='settings'").fetchone(), (8,))
        saved = list((self.root / "preferences/backups.local").iterdir())
        self.assertEqual(len(saved), 1)
        self.assertEqual(saved[0].read_text(), self.raw)
        self.assertEqual(saved[0].stat().st_mode & 0o777, 0o600)
        self.assertFalse((self.access / "maintenance").exists())
        self.run_sync("apply")
        self.assertEqual(len(list(saved[0].parent.iterdir())), 1)

    def test_status_and_export_work_while_running_and_export_only_owned_keys(self):
        (self.access / "participants/runtime").mkdir()
        self.run_sync("status")
        self.run_sync("export")
        self.assertEqual(json.loads((self.root / "orca/settings.json").read_text()), {
            "theme": "system", "terminalFontFamily": "SF Mono", "terminalFontSize": 13,
        })
        self.assertEqual(sync.read_orca(self.target)[1], self.live)

    def test_apply_refuses_running_orca_and_cleans_own_gate(self):
        (self.access / "participants/runtime").mkdir()
        with self.assertRaisesRegex(ValueError, "Quit Orca"):
            self.run_sync("apply")
        self.assertFalse((self.access / "maintenance").exists())
        self.assertEqual(sync.read_orca(self.target)[1], self.live)

    def test_existing_maintenance_owner_is_untouched(self):
        maintenance = self.access / "maintenance"
        maintenance.mkdir()
        (maintenance / "existing.owner").write_text("keep")
        with self.assertRaisesRegex(ValueError, "already active"):
            self.run_sync("apply")
        self.assertEqual((maintenance / "existing.owner").read_text(), "keep")
        self.assertEqual(list((self.access / "candidates").iterdir()), [])

    def test_backup_failure_rolls_back_and_releases_gate(self):
        with patch.object(sync, "backup", side_effect=OSError("backup failed")):
            with self.assertRaisesRegex(OSError, "backup failed"):
                self.run_sync("apply")
        self.assertEqual(sync.read_orca(self.target)[1], self.live)
        self.assertFalse((self.access / "maintenance").exists())

    def test_rejects_unknown_schema_corruption_and_mixed_storage(self):
        with closing(sqlite3.connect(self.target)) as db, db:
            db.execute("PRAGMA user_version = 4")
        with self.assertRaisesRegex(ValueError, "version"):
            self.run_sync("status")
        with closing(sqlite3.connect(self.target)) as db, db:
            db.execute("PRAGMA user_version = 3")
            db.execute("UPDATE profile_state_documents SET content_hash='bad' WHERE domain='settings'")
        with self.assertRaisesRegex(ValueError, "checksum"):
            self.run_sync("export")
        with closing(sqlite3.connect(self.target)) as db, db:
            db.execute("UPDATE profile_state_documents SET content_hash=? WHERE domain='settings'",
                       (hashlib.sha256(self.raw.encode()).hexdigest(),))
        self.target.with_name("orca-data.json").write_text("{}")
        with self.assertRaisesRegex(ValueError, "Mixed"):
            self.run_sync("apply")

    def test_rejects_unowned_settings_and_invalid_values(self):
        for source in [{"editorFontSize": 14}, {"terminalFontSize": True},
                       {"theme": "unknown"}, {"terminalFontFamily": ""}]:
            with self.subTest(source=source), self.assertRaises(ValueError):
                sync.validate_orca(source)


if __name__ == "__main__":
    unittest.main()
