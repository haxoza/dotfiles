"""Check ownership boundaries and writes using fixtures, never live preferences."""

import importlib.util
import io
import json
import plistlib
import subprocess
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

SPEC = importlib.util.spec_from_file_location(
    "preference_sync", Path(__file__).with_name("sync.py")
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class PreferenceSyncTests(unittest.TestCase):
    def setUp(self):
        self.sources = sync.load_sources()
        self.output = patch("sys.stdout", new_callable=io.StringIO).start()
        self.errors = patch("sys.stderr", new_callable=io.StringIO).start()
        self.addCleanup(patch.stopall)

    def test_jsonc_preserves_comment_like_strings_and_nested_merge(self):
        live = sync.jsonc("""{
          // VS Code comments and trailing commas
          "url": "https://example.test/a,}",
          "[python]": {"editor.tabSize": 4,}, /* keep app-owned settings */
        }""")
        result = sync.merged(
            live, {"[python]": {"editor.defaultFormatter": "charliermarsh.ruff"}}
        )
        self.assertEqual(result["url"], "https://example.test/a,}")
        self.assertEqual(result["[python]"]["editor.tabSize"], 4)
        self.assertEqual(
            sync.selected(result, {"[python]": {"editor.defaultFormatter": ""}}),
            {"[python]": {"editor.defaultFormatter": "charliermarsh.ruff"}},
        )

    def test_export_detects_missing_nested_keys(self):
        self.assertEqual(sync.missing_owned({"a": {}}, {"a": {"b": True}}), ["a.b"])

    def test_stats_rejects_identity_hardware_and_runtime_keys(self):
        for key in [
            "remote_id",
            "remote_token",
            "sensor_PSTR",
            "Sensors_hid",
            "NSStatusItem Preferred Position CPU_line_chart",
            "version",
        ]:
            with self.subTest(key=key), self.assertRaises(ValueError):
                sync.validate_defaults({key: True}, self.sources["stats"])

    def test_stats_apply_writes_only_changed_owned_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = root / "stats.json"
            source.write_text(
                json.dumps({"CPU_widget": "line_chart", "telemetry": False})
            )
            live = {
                "CPU_widget": "mini",
                "telemetry": False,
                "remote_id": "device-local",
                "sensor_PSTR": True,
            }
            calls = []

            def defaults(command, **_kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(
                    command, 0, plistlib.dumps(live), b""
                )

            with (
                patch.object(sync, "ROOT", root),
                patch.object(
                    sync,
                    "load_sources",
                    return_value={
                        "stats": {**self.sources["stats"], "source": "stats.json"},
                    },
                ),
                patch.object(sync.subprocess, "run", side_effect=defaults),
                patch("sys.argv", ["sync.py", "apply", "stats"]),
            ):
                sync.main()
            self.assertEqual(
                calls[1:],
                [
                    [
                        "/usr/bin/defaults",
                        "write",
                        self.sources["stats"]["domain"],
                        "CPU_widget",
                        "-string",
                        "line_chart",
                    ]
                ],
            )
            backups = list((root / "preferences/backups.local").iterdir())
            self.assertEqual(plistlib.loads(backups[0].read_bytes()), live)
            self.assertEqual(backups[0].stat().st_mode & 0o777, 0o600)

    def test_vscode_apply_preserves_unowned_nested_keys_and_backup(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            target = home / "Library/Application Support/Code/User/settings.json"
            target.parent.mkdir(parents=True)
            original = (
                b'{/* comment */ "[python]": {"editor.tabSize": 4}, "local": true,}'
            )
            target.write_bytes(original)
            source = root / "source.json"
            source.write_text(
                '{"[python]": {"editor.defaultFormatter": "charliermarsh.ruff"}}'
            )
            with (
                patch.object(sync, "ROOT", root),
                patch.object(
                    sync,
                    "load_sources",
                    return_value={
                        "vscode": {**self.sources["vscode"], "source": "source.json"},
                    },
                ),
                patch.object(sync.Path, "home", return_value=home),
                patch("sys.argv", ["sync.py", "apply", "vscode"]),
            ):
                sync.main()
            result = json.loads(target.read_text())
            self.assertTrue(result["local"])
            self.assertEqual(result["[python]"]["editor.tabSize"], 4)
            self.assertEqual(
                next((root / "preferences/backups.local").iterdir()).read_bytes(),
                original,
            )

    def test_choosy_is_rejected_on_machine_2_before_access(self):
        with (
            patch("sys.argv", ["sync.py", "apply", "choosy", "--machine", "machine-2"]),
            self.assertRaises(SystemExit) as error,
        ):
            sync.main()
        self.assertEqual(error.exception.code, 2)

    def test_new_source_from_config_applies_ordered_language_array(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            languages = ["en-GB", "en-US", "pl-PL"]
            (root / "languages.json").write_text(
                json.dumps({"AppleLanguages": languages})
            )
            live = {"AppleLanguages": ["fr-FR"], "unowned": True}
            definition = {
                "source": "languages.json",
                "backend": "defaults",
                "domain": "NSGlobalDomain",
            }
            calls = []

            def defaults(command, **_kwargs):
                calls.append(command)
                return subprocess.CompletedProcess(
                    command, 0, plistlib.dumps(live), b""
                )

            with (
                patch.object(sync, "ROOT", root),
                patch.object(
                    sync, "load_sources", return_value={"languages": definition}
                ),
                patch.object(sync.subprocess, "run", side_effect=defaults),
                patch("sys.argv", ["sync.py", "apply", "languages"]),
            ):
                sync.main()
            self.assertEqual(
                calls[1:],
                [
                    [
                        "/usr/bin/defaults",
                        "write",
                        "NSGlobalDomain",
                        "AppleLanguages",
                        "-array",
                        *languages,
                    ]
                ],
            )

    def test_export_new_json_source_only_includes_owned_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            (root / "source.json").write_text('{"owned": false}')
            (home / "app.json").write_text('{"owned": true, "device_id": "local"}')
            definition = {
                "source": "source.json",
                "backend": "json",
                "target": "app.json",
            }
            with (
                patch.object(sync, "ROOT", root),
                patch.object(
                    sync, "load_sources", return_value={"new-app": definition}
                ),
                patch.object(sync.Path, "home", return_value=home),
                patch("sys.argv", ["sync.py", "export", "new-app"]),
            ):
                sync.main()
            self.assertEqual(
                json.loads((root / "source.json").read_text()), {"owned": True}
            )
            self.assertEqual(
                json.loads((home / "app.json").read_text())["device_id"], "local"
            )

    def test_macos_policy_rejects_unrelated_system_settings(self):
        with self.assertRaises(ValueError):
            sync.validate_defaults(
                {"AppleInterfaceStyle": "Dark"}, self.sources["macos"]
            )

    def test_plist_export_tracks_complete_file_including_removed_keys(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            (root / "source.plist").write_bytes(plistlib.dumps({"old": True}))
            live = {"new": "current value"}
            (home / "app.plist").write_bytes(plistlib.dumps(live))
            definition = {
                "source": "source.plist",
                "backend": "plist",
                "target": "app.plist",
            }
            with (
                patch.object(sync, "ROOT", root),
                patch.object(
                    sync, "load_sources", return_value={"new-plist": definition}
                ),
                patch.object(sync.Path, "home", return_value=home),
                patch("sys.argv", ["sync.py", "export", "new-plist"]),
            ):
                sync.main()
            self.assertEqual(plistlib.loads((root / "source.plist").read_bytes()), live)

    def test_plist_export_rejects_missing_empty_or_invalid_live_file(self):
        for raw in [None, b"", b"not a plist"]:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                source = root / "source.plist"
                original = plistlib.dumps(
                    [{"predicate": "TRUEPREDICATE", "enabled": True}]
                )
                source.write_bytes(original)
                target = home / "rules.plist"
                if raw is not None:
                    target.write_bytes(raw)
                definition = {
                    **self.sources["choosy"],
                    "source": "source.plist",
                    "target": "rules.plist",
                }
                self.output.truncate(0)
                self.output.seek(0)
                with (
                    patch.object(sync, "ROOT", root),
                    patch.object(
                        sync, "load_sources", return_value={"choosy": definition}
                    ),
                    patch.object(sync.Path, "home", return_value=home),
                    patch(
                        "sys.argv",
                        ["sync.py", "export", "choosy", "--machine", "machine-1"],
                    ),
                    self.assertRaises(ValueError),
                ):
                    sync.main()
                self.assertEqual(source.read_bytes(), original)
                self.assertNotIn("Exported", self.output.getvalue())
                self.assertEqual(target.read_bytes() if target.exists() else None, raw)

    def test_plist_status_and_apply_allow_missing_or_empty_live_file(self):
        for raw in [None, b""]:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                source = root / "source.plist"
                rules = [{"predicate": "TRUEPREDICATE", "enabled": True}]
                original = plistlib.dumps(rules)
                source.write_bytes(original)
                target = home / "rules.plist"
                if raw is not None:
                    target.write_bytes(raw)
                definition = {
                    **self.sources["choosy"],
                    "source": "source.plist",
                    "target": "rules.plist",
                }
                with (
                    patch.object(sync, "ROOT", root),
                    patch.object(
                        sync, "load_sources", return_value={"choosy": definition}
                    ),
                    patch.object(sync.Path, "home", return_value=home),
                ):
                    with patch(
                        "sys.argv",
                        ["sync.py", "status", "choosy", "--machine", "machine-1"],
                    ):
                        sync.main()
                    self.assertEqual(
                        target.read_bytes() if target.exists() else None, raw
                    )
                    with patch(
                        "sys.argv",
                        ["sync.py", "apply", "choosy", "--machine", "machine-1"],
                    ):
                        sync.main()
                self.assertEqual(plistlib.loads(target.read_bytes()), rules)
                self.assertEqual(source.read_bytes(), original)

    def test_plist_export_allows_valid_empty_rules_array(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            source = root / "source.plist"
            source.write_bytes(plistlib.dumps([{"enabled": True}]))
            (home / "rules.plist").write_bytes(plistlib.dumps([]))
            definition = {
                **self.sources["choosy"],
                "source": "source.plist",
                "target": "rules.plist",
            }
            with (
                patch.object(sync, "ROOT", root),
                patch.object(sync, "load_sources", return_value={"choosy": definition}),
                patch.object(sync.Path, "home", return_value=home),
                patch(
                    "sys.argv",
                    ["sync.py", "export", "choosy", "--machine", "machine-1"],
                ),
            ):
                sync.main()
            self.assertEqual(plistlib.loads(source.read_bytes()), [])

    def test_config_paths_stay_relative(self):
        for path in ["/Library/Preferences/app.plist", "../outside.json"]:
            with self.subTest(path=path), self.assertRaises(ValueError):
                sync.relative_path(Path("/repo"), path)

    def test_spotlight_preserves_app_and_unknown_rules_on_apply(self):
        definition = self.sources["spotlight"]
        live = {
            "EnabledPreferenceRules": [
                "com.example.LocalApp",
                "System.files",
                "System.futureRule",
            ],
            "lastWindowPosition": "device-local",
        }
        view = sync.owned_view(live, definition)
        self.assertEqual(view["EnabledPreferenceRules"], ["System.files"])
        # Turning Files off and Folders on must leave local/unknown entries alone.
        result = sync.value_to_apply(
            "EnabledPreferenceRules", ["System.folders"], live, definition
        )
        self.assertEqual(
            result, ["com.example.LocalApp", "System.futureRule", "System.folders"]
        )
        self.assertEqual(live["EnabledPreferenceRules"][1], "System.files")

    def test_spotlight_policy_rejects_app_rules_and_local_state(self):
        definition = self.sources["spotlight"]
        for value in [
            {"EnabledPreferenceRules": ["com.example.LocalApp"]},
            {"lastWindowPosition": "device-local"},
            {"orderedItems": []},
        ]:
            with self.subTest(value=value), self.assertRaises(ValueError):
                sync.validate_defaults(value, definition)

    def test_spotlight_rejects_unverified_macos_before_read_or_write(self):
        with (
            patch.object(
                sync.platform, "mac_ver", return_value=("27.0", ("", "", ""), "arm64")
            ),
            patch.object(sync.subprocess, "run") as defaults,
            patch("sys.argv", ["sync.py", "apply", "spotlight"]),
            self.assertRaises(SystemExit) as error,
        ):
            sync.main()
        self.assertEqual(error.exception.code, 2)
        defaults.assert_not_called()

    def test_shared_default_sources_validate_and_do_not_overlap(self):
        owned = set()
        for definition in self.sources.values():
            if definition["backend"] != "defaults":
                continue
            source = json.loads((sync.ROOT / definition["source"]).read_text())
            sync.validate_defaults(source, definition)
            for key in source:
                identity = (definition["domain"], key)
                self.assertNotIn(identity, owned)
                owned.add(identity)


if __name__ == "__main__":
    unittest.main()
