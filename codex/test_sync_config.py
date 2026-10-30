# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3"]
# ///
"""Run with make -C codex test; all config state lives in temp fixtures."""

import importlib.util
import os
import stat
import subprocess
import sys
import tempfile
import tomllib
import unittest
from pathlib import Path
from unittest.mock import patch

SCRIPT_DIR = Path(__file__).resolve().parent
SUT = SCRIPT_DIR / "sync-config.py"
sys.dont_write_bytecode = True
spec = importlib.util.spec_from_file_location("sync_config", SUT)
sync_config = importlib.util.module_from_spec(spec)
spec.loader.exec_module(sync_config)
SHARED = """# Keep shared policy comments.
approval_policy = "on-request"
model_reasoning_effort = "high"
tui.status_line = ["project-name", "model-with-reasoning"]
[sandbox_workspace_write]
network_access = true
writable_roots = ["~/.npm/_cacache"]
"""
MACHINE = """# Keep machine comments.
[desktop]
followUpQueueMode = "queue"
[plugins."portable@example"]
enabled = true
"""
LOCAL = """# Keep private comments.
notify = ["/private/notify", "a quoted argument"]
[projects."/private/project"]
trust_level = "trusted"
[tui]
screen_reader_detection_done = true
"""
LIVE = """# The app's header.
model = "app-selected-model"
model_reasoning_effort = "low"
approval_policy = "never"
notify = ["/private/app-notify"]
new_app_field = { nested = "leave me alone" }
[sandbox_workspace_write]
network_access = false
writable_roots = ["/private/cache"]
[desktop]
followUpQueueMode = "steer"
new_app_state = { shown = true }
[tui]
status_line = ["git-branch"]
screen_reader_detection_done = false
unknown_state = { seen = 3 }
[tui.model_availability_nux]
"some.model" = 4
[plugins."app-plugin@example"]
enabled = false
[projects."/private/app-project"]
trust_level = "trusted"
[mcp_servers.private]
command = "/private/mcp"
[mcp_servers.private.env]
SECRET = "fixture-secret"
[hooks]
[[hooks.SessionStart]]
matcher = ""
[[hooks.SessionStart.hooks]]
type = "command"
command = "/private/hook fixture-secret"
[marketplaces.private]
source = { path = "/private/marketplace" }
"""


class SyncConfigTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory(prefix="codex-sync-test-")
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.source = self.root / "repo/codex"
        self.source.mkdir(parents=True)
        self.shared = self.source / "common.toml"
        self.machine = self.source / "config.machine-1.toml"
        self.other = self.source / "config.machine-2.toml"
        self.local = self.source / "trusted.local.toml"
        self.live = self.root / "home/.codex/config.toml"
        self.live.parent.mkdir(parents=True)
        self.shared.write_text(SHARED)
        self.machine.write_text(MACHINE)
        self.other.write_text('[desktop]\nfollowUpQueueMode="other"\n[plugins]\n')
        self.local.write_text(LOCAL)
        self.live.write_text(LIVE)
        self.env = dict(
            os.environ,
            DOTFILES_MACHINE="machine-1",
            CODEX_CONFIG_SOURCE_DIR=str(self.source),
            CODEX_HOME=str(self.live.parent),
            HOME=str(self.root / "home"),
        )
        self.env.pop("CODEX_CONFIG_LIVE_FILE", None)

    def run_sync(self, command, *, success=True):
        argv = [sys.executable, str(SUT), command]
        result = subprocess.run(
            argv, check=False, env=self.env, text=True, capture_output=True
        )
        if success:
            self.assertEqual(result.returncode, 0, result.stderr)
        else:
            self.assertNotEqual(result.returncode, 0, result.stdout)
        return result.stdout + result.stderr

    def load(self, file):
        return tomllib.loads(file.read_text())

    def snapshot(self):
        return {
            p: (p.read_bytes(), p.stat().st_ino)
            for p in self.root.rglob("*")
            if p.is_file()
        }

    def backups(self):
        return list(self.live.parent.glob("config.toml.*.bak"))

    def test_merge_ownership_and_tui_coexistence(self):
        self.run_sync("merge")
        live = self.load(self.live)
        self.assertEqual(live["approval_policy"], "on-request")
        self.assertEqual(
            live["sandbox_workspace_write"],
            self.load(self.shared)["sandbox_workspace_write"],
        )
        self.assertEqual(live["plugins"], self.load(self.machine)["plugins"])
        self.assertEqual(live["projects"], self.load(self.local)["projects"])
        self.assertEqual(live["model"], "app-selected-model")
        self.assertEqual(
            live["desktop"],
            {"followUpQueueMode": "queue", "new_app_state": {"shown": True}},
        )
        self.assertEqual(
            live["tui"],
            {
                "status_line": ["project-name", "model-with-reasoning"],
                "screen_reader_detection_done": True,
                "unknown_state": {"seen": 3},
                "model_availability_nux": {"some.model": 4},
            },
        )
        self.assertEqual(live["new_app_field"], {"nested": "leave me alone"})
        self.assertEqual(
            live["mcp_servers"]["private"]["env"]["SECRET"], "fixture-secret"
        )

    def test_symlink_migration_backs_up_contents_and_keeps_old_target_and_backups(self):
        target = self.source / "config.toml"
        self.live.rename(target)
        self.live.symlink_to(target)
        old_backup = self.source / "config.toml.old.bak"
        old_backup.write_text("old generated backup")
        before = target.read_bytes()
        self.run_sync("merge")
        self.assertFalse(self.live.is_symlink())
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(old_backup.read_text(), "old generated backup")
        self.assertEqual(len(self.backups()), 1)
        backup = self.backups()[0]
        self.assertFalse(backup.is_symlink())
        self.assertEqual(backup.read_bytes(), before)
        self.assertEqual(stat.S_IMODE(backup.stat().st_mode), 0o600)
        self.assertEqual(stat.S_IMODE(self.live.stat().st_mode), 0o600)

    def test_noop_symlink_still_migrates_with_byte_exact_backup(self):
        self.run_sync("merge")
        target = self.source / "config.toml"
        self.live.rename(target)
        self.live.symlink_to(target)
        before = target.read_bytes()
        self.run_sync("merge")
        self.assertFalse(self.live.is_symlink())
        self.assertEqual(self.live.read_bytes(), before)
        self.assertIn(before, [b.read_bytes() for b in self.backups()])

    def test_merge_idempotence_preserves_app_formatting_without_extra_backup(self):
        self.run_sync("merge")
        self.live.write_text(self.live.read_text() + "\n# App formatting retained.\n")
        before = self.snapshot()
        self.run_sync("merge")
        self.assertEqual(self.snapshot(), before)
        self.assertEqual(len(self.backups()), 1)

    def test_each_regular_replacement_gets_a_unique_backup(self):
        self.run_sync("merge")
        before = self.live.read_bytes()
        self.shared.write_text(SHARED.replace('"high"', '"medium"'))
        self.run_sync("merge")
        self.assertEqual(len(self.backups()), 2)
        self.assertIn(before, [b.read_bytes() for b in self.backups()])

    def test_missing_local_passes_private_live_state_through(self):
        self.local.unlink()
        self.run_sync("merge")
        live = self.load(self.live)
        original = tomllib.loads(LIVE)
        for key in ("projects", "mcp_servers", "hooks", "notify", "marketplaces"):
            self.assertEqual(live[key], original[key])
        self.assertFalse(self.local.exists())

    def test_fresh_install_creates_regular_file_and_does_not_select_a_model(self):
        self.live.unlink()
        self.live.parent.rmdir()
        self.run_sync("merge")
        self.assertFalse(self.live.is_symlink())
        self.assertNotIn("model", self.load(self.live))
        self.assertEqual(self.backups(), [])

    def test_export_routes_changes_and_new_private_tables_to_owners(self):
        before_live = self.live.read_bytes()
        before_other = self.other.read_bytes()
        out = self.run_sync("export")
        shared, machine, local = map(self.load, (self.shared, self.machine, self.local))
        self.assertEqual(shared["approval_policy"], "never")
        self.assertEqual(shared["tui"], {"status_line": ["git-branch"]})
        self.assertEqual(machine["plugins"], self.load(self.live)["plugins"])
        self.assertEqual(machine["desktop"], {"followUpQueueMode": "steer"})
        self.assertEqual(local["projects"], self.load(self.live)["projects"])
        self.assertEqual(
            local["tui"],
            {
                "screen_reader_detection_done": False,
                "model_availability_nux": {"some.model": 4},
            },
        )
        for key in ("mcp_servers", "hooks", "marketplaces", "notify"):
            self.assertEqual(local[key], self.load(self.live)[key])
            self.assertNotIn(key, shared)
            self.assertNotIn(key, machine)
        for key in ("model", "new_app_field"):
            for doc in (shared, machine, local):
                self.assertNotIn(key, doc)
        self.assertNotIn("fixture-secret", out)
        self.assertNotIn("/private/", out)
        self.assertEqual(self.live.read_bytes(), before_live)
        self.assertEqual(self.other.read_bytes(), before_other)
        self.assertIn("# Keep shared policy comments.", self.shared.read_text())
        self.assertIn("# Keep machine comments.", self.machine.read_text())
        self.assertIn("# Keep private comments.", self.local.read_text())
        self.assertEqual(stat.S_IMODE(self.local.stat().st_mode), 0o600)

    def test_export_creates_missing_local_only_from_live_private_settings(self):
        self.local.unlink()
        self.run_sync("export")
        local = self.load(self.local)
        self.assertEqual(
            set(local),
            {"projects", "mcp_servers", "hooks", "notify", "marketplaces", "tui"},
        )
        self.assertNotIn("status_line", local["tui"])
        self.assertNotIn("unknown_state", local["tui"])

    def test_export_does_not_copy_live_comments_into_public_sources(self):
        text = LIVE.replace(
            '[plugins."app-plugin@example"]',
            '[plugins."app-plugin@example"] # fixture-secret /private/comment',
        )
        self.live.write_text(text)
        self.run_sync("export")
        self.assertNotIn("fixture-secret", self.machine.read_text())
        self.assertNotIn("/private/comment", self.machine.read_text())

    def test_export_idempotence_and_merge_export_round_trip(self):
        self.run_sync("export")
        before = self.snapshot()
        self.assertIn("sources already match", self.run_sync("export"))
        self.assertEqual(self.snapshot(), before)
        self.run_sync("merge")
        self.assertIn("sources already match", self.run_sync("export"))
        self.assertEqual(self.snapshot(), before)

    def test_export_reads_old_symlink_without_migrating_it(self):
        target = self.source / "config.toml"
        self.live.rename(target)
        self.live.symlink_to(target)
        before = target.read_bytes()
        self.run_sync("export")
        self.assertTrue(self.live.is_symlink())
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(self.backups(), [])

    def test_missing_owned_scalars_are_removed_but_table_ownership_is_retained(self):
        self.live.write_text('model="app-selected-model"\n')
        self.run_sync("export")
        self.assertNotIn("approval_policy", self.load(self.shared))
        self.assertNotIn("tui", self.load(self.shared))
        self.assertEqual(self.load(self.machine)["plugins"], {})
        self.assertEqual(self.load(self.local)["projects"], {})
        before = self.snapshot()
        self.run_sync("export")
        self.assertEqual(self.snapshot(), before)

    def test_empty_plugin_map_removes_stale_plugins(self):
        self.machine.write_text("[plugins]\n")
        self.run_sync("merge")
        self.assertEqual(self.load(self.live)["plugins"], {})

    def test_status_reports_owners_without_writing_or_exposing_private_content(self):
        before = self.snapshot()
        out = self.run_sync("status")
        self.assertIn("common.toml; merge resets, export pulls): approval_policy", out)
        self.assertIn(
            "config.machine-1.toml; merge resets, export pulls): desktop.followUpQueueMode, plugins",
            out,
        )
        self.assertIn(
            "trusted.local.toml; merge resets, export pulls): 3 changed, 4 live-only",
            out,
        )
        self.assertIn("new_app_field", out)
        self.assertIn("tui.unknown_state", out)
        self.assertIn("desktop.new_app_state", out)
        self.assertNotIn("fixture-secret", out)
        self.assertNotIn("/private/", out)
        self.assertEqual(self.snapshot(), before)

    def test_duplicate_ownership_rejected_before_any_writes(self):
        for file, content in [
            (self.machine, 'approval_policy="never"\n' + MACHINE),
            (self.local, LOCAL.replace("[tui]\n", '[tui]\nstatus_line=["other"]\n')),
        ]:
            with self.subTest(file=file.name):
                original = file.read_text()
                file.write_text(content)
                before = self.snapshot()
                out = self.run_sync("merge", success=False)
                self.assertIn("duplicate ownership", out)
                self.assertEqual(self.snapshot(), before)
                file.write_text(original)

    def test_reserved_ownership_cannot_be_claimed_by_public_sources(self):
        for name, content, message in [
            ("common.toml", 'model="forbidden"\n', "model is app-owned"),
            ("trusted.local.toml", 'model="forbidden"\n', "model is app-owned"),
            (
                "config.machine-1.toml",
                '[projects."/private"]\ntrust_level="trusted"\n',
                "private settings",
            ),
            ("common.toml", "[plugins]\n", "plugins belong"),
            (
                "common.toml",
                "[tui]\nscreen_reader_detection_done=true\n",
                "private settings",
            ),
        ]:
            with self.subTest(name=name, message=message):
                file = self.source / name
                original = file.read_text()
                file.write_text(content)
                before = self.snapshot()
                self.assertIn(message, self.run_sync("export", success=False))
                self.assertEqual(self.snapshot(), before)
                file.write_text(original)

    def test_machine_file_fallback_and_environment_override(self):
        (self.source.parent / ".machine").write_text("machine-2\n")
        self.env.pop("DOTFILES_MACHINE")
        self.run_sync("merge")
        self.assertEqual(self.load(self.live)["desktop"]["followUpQueueMode"], "other")
        self.assertEqual(self.load(self.live)["plugins"], {})
        self.env["DOTFILES_MACHINE"] = "machine-1"
        self.run_sync("merge")
        self.assertEqual(self.load(self.live)["desktop"]["followUpQueueMode"], "queue")

    def test_missing_or_invalid_machine_never_guesses(self):
        for selection in (None, "machine-3"):
            with self.subTest(selection=selection):
                self.env.pop("DOTFILES_MACHINE", None)
                if selection:
                    self.env["DOTFILES_MACHINE"] = selection
                before = self.snapshot()
                self.assertIn(
                    "must select machine-1 or machine-2",
                    self.run_sync("merge", success=False),
                )
                self.assertEqual(self.snapshot(), before)

    def test_invalid_toml_is_rejected_without_printing_parser_content(self):
        for file in (self.live, self.shared, self.machine, self.local):
            with self.subTest(file=file.name):
                original = file.read_text()
                file.write_text('secret="fixture-secret"\nsecret="duplicate"\n')
                before = self.snapshot()
                out = self.run_sync("merge", success=False)
                self.assertIn("invalid TOML", out)
                self.assertNotIn("fixture-secret", out)
                self.assertEqual(self.snapshot(), before)
                file.write_text(original)

    def test_non_table_tui_and_desktop_rejected_without_overwriting_unknown_values(
        self,
    ):
        for key in ("tui", "desktop"):
            self.live.write_text(f'{key}="fixture-secret"\n')
            before = self.snapshot()
            out = self.run_sync("merge", success=False)
            self.assertIn(f"{key} must be a table", out)
            self.assertNotIn("fixture-secret", out)
            self.assertEqual(self.snapshot(), before)

    def test_missing_required_source_and_missing_live_export(self):
        self.machine.unlink()
        before = self.snapshot()
        self.run_sync("merge", success=False)
        self.assertEqual(self.snapshot(), before)
        self.machine.write_text(MACHINE)
        self.live.unlink()
        before = self.snapshot()
        self.assertIn("nothing to export", self.run_sync("export", success=False))
        self.assertEqual(self.snapshot(), before)

    def test_broken_live_symlink_is_not_silently_replaced(self):
        self.live.unlink()
        self.live.symlink_to(self.source / "missing.toml")
        self.run_sync("merge", success=False)
        self.assertTrue(self.live.is_symlink())
        self.assertEqual(self.backups(), [])

    def test_failed_backup_leaves_symlink_and_target_untouched(self):
        target = self.source / "config.toml"
        self.live.rename(target)
        self.live.symlink_to(target)
        before = target.read_bytes()
        mkstemp = tempfile.mkstemp

        def fail_backup(*args, **kwargs):
            if kwargs.get("suffix") == ".bak":
                raise OSError("fixture backup failure")
            return mkstemp(*args, **kwargs)

        with (
            patch.object(sync_config.tempfile, "mkstemp", side_effect=fail_backup),
            self.assertRaises(OSError),
        ):
            sync_config.write(self.live, b'model="new"\n', before, live=True)
        self.assertTrue(self.live.is_symlink())
        self.assertEqual(target.read_bytes(), before)
        self.assertEqual(list(self.live.parent.glob(".config.toml.*")), [])

    def test_concurrent_live_edit_is_not_overwritten(self):
        before = self.live.read_bytes()
        self.live.write_text('model="new-app-choice"\n')
        current = self.live.read_bytes()
        with self.assertRaises(sync_config.ConfigError):
            sync_config.write(self.live, b'model="stale"\n', before, live=True)
        self.assertEqual(self.live.read_bytes(), current)
        self.assertEqual(self.backups(), [])

    def test_source_symlinks_are_rejected_before_export(self):
        target = self.source / "private-source.toml"
        self.local.rename(target)
        self.local.symlink_to(target)
        before = self.snapshot()
        self.assertIn(
            "source trusted.local.toml must be a regular file",
            self.run_sync("export", success=False),
        )
        self.assertEqual(self.snapshot(), before)

    def test_quoted_keys_multiline_strings_arrays_of_tables_and_dates_round_trip(self):
        with self.live.open("a") as live:
            live.write('''
[unknown."quoted.key"]
text = """First line
Second line with 'quotes' and \\t tabs"""
date = 2026-10-30T10:20:30Z
[[unknown.items]]
"key.with.dots" = ["a", "b"]
''')
        unknown = self.load(self.live)["unknown"]
        self.run_sync("merge")
        self.assertEqual(self.load(self.live)["unknown"], unknown)
        self.run_sync("export")
        self.assertNotIn("unknown", self.load(self.shared))
        self.assertNotIn("unknown", self.load(self.local))

    def test_live_override_and_make_entrypoints(self):
        # uv can populate its cache even for read-only status; keep it outside
        # the config fixture snapshot and the user's home.
        cache = tempfile.TemporaryDirectory(prefix="codex-test-uv-cache-")
        self.addCleanup(cache.cleanup)
        self.env["UV_CACHE_DIR"] = cache.name
        alternate = self.root / "alternate.toml"
        alternate.write_text(LIVE)
        self.env["CODEX_CONFIG_LIVE_FILE"] = str(alternate)
        before = self.live.read_bytes()
        make = ["make", "--no-print-directory", "-C", str(SCRIPT_DIR)]
        snapshot = self.snapshot()
        result = subprocess.run(
            make, check=False, env=self.env, text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("drifted owned keys", result.stdout)
        self.assertEqual(self.snapshot(), snapshot)
        result = subprocess.run(
            [*make, "merge"], check=False, env=self.env, text=True, capture_output=True
        )
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(self.live.read_bytes(), before)
        self.assertEqual(self.load(alternate)["model"], "app-selected-model")
        self.assertFalse((self.source / "config.toml").exists())


if __name__ == "__main__":
    unittest.main(verbosity=2)
