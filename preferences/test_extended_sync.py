"""Regression coverage for curated Zed settings and selective macOS captures."""

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
    "extended_preference_sync", Path(__file__).with_name("sync.py")
)
sync = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(sync)


class ExtendedSyncTests(unittest.TestCase):
    def setUp(self):
        self.sources = sync.load_sources()
        self.output = patch("sys.stdout", new_callable=io.StringIO).start()
        self.errors = patch("sys.stderr", new_callable=io.StringIO).start()
        self.addCleanup(patch.stopall)

    def invoke(self, root, definition, action):
        with (
            patch.object(sync, "ROOT", root),
            patch.object(sync, "load_sources", return_value={"fixture": definition}),
            patch.object(sync.Path, "home", return_value=root / "home"),
            patch("sys.argv", ["sync.py", action, "fixture"]),
        ):
            sync.main()

    def test_nested_defaults_merge_preserves_bindings_other_ids_and_domain(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = {
                "AppleSymbolicHotKeys": {
                    "79": {"enabled": False},
                    "81": {"enabled": False},
                }
            }
            (root / "source.json").write_text(json.dumps(source))
            definition = {
                "source": "source.json",
                "backend": "defaults",
                "domain": "fixture.domain",
            }
            binding = {"type": "standard", "parameters": [65535, 123, 8650752]}
            live = {
                "AppleSymbolicHotKeys": {
                    "79": {"enabled": True, "value": binding, "future_field": "keep"},
                    "80": {"enabled": True},
                    "999": {"future_data": b"opaque state"},
                },
                "unowned_domain_key": "keep",
            }
            before = plistlib.dumps(live)
            writes = []

            def defaults(command, **_kwargs):
                if command[1] == "write":
                    self.assertEqual(
                        command[:4],
                        [
                            "/usr/bin/defaults",
                            "write",
                            "fixture.domain",
                            "AppleSymbolicHotKeys",
                        ],
                    )
                    self.assertEqual(len(command), 5)  # one key, never a domain import
                    writes.append(command)
                    live[command[3]] = plistlib.loads(command[4].encode())
                return subprocess.CompletedProcess(
                    command, 0, plistlib.dumps(live), b""
                )

            with patch.object(sync.subprocess, "run", side_effect=defaults):
                self.invoke(root, definition, "apply")
                self.invoke(root, definition, "status")
                self.invoke(root, definition, "apply")
            self.assertEqual(len(writes), 1)
            self.assertEqual(
                live["AppleSymbolicHotKeys"]["79"],
                {"enabled": False, "value": binding, "future_field": "keep"},
            )
            self.assertEqual(live["AppleSymbolicHotKeys"]["81"], {"enabled": False})
            self.assertEqual(live["AppleSymbolicHotKeys"]["80"], {"enabled": True})
            self.assertEqual(
                live["AppleSymbolicHotKeys"]["999"]["future_data"], b"opaque state"
            )
            self.assertEqual(live["unowned_domain_key"], "keep")
            self.assertIs(
                type(live["AppleSymbolicHotKeys"]["79"]["value"]["parameters"][0]), int
            )
            self.assertIs(live["AppleSymbolicHotKeys"]["79"]["enabled"], False)
            backups = list((root / "preferences/backups.local").iterdir())
            self.assertEqual(len(backups), 1)
            self.assertEqual(backups[0].read_bytes(), before)
            self.assertIn("fixture: in sync", self.output.getvalue())

    def test_nested_export_only_captures_owned_enabled_leaf(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            source = {"AppleSymbolicHotKeys": {"79": {"enabled": True}}}
            (root / "source.json").write_text(json.dumps(source))
            live = {
                "AppleSymbolicHotKeys": {
                    "79": {"enabled": False, "value": {"parameters": [1, 2, 3]}},
                    "164": {"enabled": True},
                },
                "local": "keep",
            }
            definition = {
                "source": "source.json",
                "backend": "defaults",
                "domain": "fixture.domain",
            }
            result = subprocess.CompletedProcess([], 0, plistlib.dumps(live), b"")
            with patch.object(sync.subprocess, "run", return_value=result) as defaults:
                self.invoke(root, definition, "export")
            self.assertEqual(
                json.loads((root / "source.json").read_text()),
                {"AppleSymbolicHotKeys": {"79": {"enabled": False}}},
            )
            self.assertEqual(defaults.call_count, 1)

    def test_nested_export_rejects_missing_invalid_or_partial_data(self):
        cases = [
            (1, b""),
            (0, b""),
            (0, b"not a plist"),
            (0, plistlib.dumps([])),
            (0, plistlib.dumps({"AppleSymbolicHotKeys": "wrong type"})),
            (0, plistlib.dumps({"AppleSymbolicHotKeys": {"79": {"value": {}}}})),
        ]
        for code, raw in cases:
            with (
                self.subTest(code=code, raw=raw),
                tempfile.TemporaryDirectory() as temporary,
            ):
                root = Path(temporary)
                original = b'{"AppleSymbolicHotKeys":{"79":{"enabled":false}}}\n'
                (root / "source.json").write_bytes(original)
                definition = {
                    "source": "source.json",
                    "backend": "defaults",
                    "domain": "fixture.domain",
                }
                with (
                    patch.object(
                        sync.subprocess,
                        "run",
                        return_value=subprocess.CompletedProcess([], code, raw, b""),
                    ),
                    self.assertRaises((ValueError, TypeError)),
                ):
                    self.invoke(root, definition, "export")
                self.assertEqual((root / "source.json").read_bytes(), original)
                self.assertFalse((root / "preferences/backups.local").exists())

    def test_zed_merge_preserves_unowned_agent_state_and_nested_values(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            source = {
                "vim_mode": True,
                "telemetry": {"diagnostics": False},
                "terminal": {"font_family": "shared-font"},
            }
            (root / "source.json").write_text(json.dumps(source))
            agents = {
                "custom": {
                    "command": "/local/agent",
                    "env": {"API_TOKEN": "private-runtime-state"},
                }
            }
            live = {
                "vim_mode": False,
                "telemetry": {"diagnostics": True, "future": True},
                "terminal": {
                    "font_family": "old",
                    "working_directory": "/local/project",
                },
                "agent_servers": agents,
            }
            target = home / "zed.json"
            target.write_text(json.dumps(live))
            original = target.read_bytes()
            definition = {
                "source": "source.json",
                "backend": "json",
                "target": "zed.json",
            }
            self.invoke(root, definition, "apply")
            result = json.loads(target.read_text())
            self.assertTrue(result["vim_mode"])
            self.assertFalse(result["telemetry"]["diagnostics"])
            self.assertTrue(result["telemetry"]["future"])
            self.assertEqual(result["terminal"]["working_directory"], "/local/project")
            self.assertEqual(result["agent_servers"], agents)
            self.assertEqual(
                next((root / "preferences/backups.local").iterdir()).read_bytes(),
                original,
            )

    def test_agent_export_excludes_commands_credentials_and_other_agents(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            home = root / "home"
            home.mkdir()
            source = {"agent_servers": {"opencode": {"type": "registry"}}}
            (root / "source.json").write_text(json.dumps(source))
            live = {
                "agent_servers": {
                    "opencode": {
                        "type": "registry",
                        "command": "/local/agent",
                        "env": {"API_TOKEN": "private-runtime-state"},
                    },
                    "local-agent": {"type": "custom"},
                }
            }
            (home / "zed.json").write_text(json.dumps(live))
            definition = {
                "source": "source.json",
                "backend": "json",
                "target": "zed.json",
            }
            self.invoke(root, definition, "export")
            self.assertEqual(json.loads((root / "source.json").read_text()), source)
            self.assertEqual(json.loads((home / "zed.json").read_text()), live)

    def test_zed_export_rejects_missing_empty_invalid_array_and_missing_leaves(self):
        for raw in [None, b"", b"not json", b"[]", b"null", b'{"terminal": {}}']:
            with self.subTest(raw=raw), tempfile.TemporaryDirectory() as temporary:
                root = Path(temporary)
                home = root / "home"
                home.mkdir()
                original = b'{"terminal":{"font_family":"shared-font"}}\n'
                (root / "source.json").write_bytes(original)
                target = home / "zed.json"
                if raw is not None:
                    target.write_bytes(raw)
                definition = {
                    "source": "source.json",
                    "backend": "json",
                    "target": "zed.json",
                }
                with self.assertRaises((ValueError, TypeError)):
                    self.invoke(root, definition, "export")
                self.assertEqual((root / "source.json").read_bytes(), original)
                self.assertEqual(target.read_bytes() if target.exists() else None, raw)

    def test_current_host_scope_is_used_for_read_and_write(self):
        with tempfile.TemporaryDirectory() as temporary:
            root = Path(temporary)
            (root / "source.json").write_text('{"com.apple.mouse.tapBehavior":1}')
            definition = {
                "source": "source.json",
                "backend": "defaults",
                "domain": "NSGlobalDomain",
                "current_host": True,
            }
            calls = []
            live = {"com.apple.mouse.tapBehavior": 0, "local": True}

            def defaults(command, **_kwargs):
                calls.append(command)
                self.assertEqual(command[:2], ["/usr/bin/defaults", "-currentHost"])
                return subprocess.CompletedProcess(
                    command, 0, plistlib.dumps(live), b""
                )

            with patch.object(sync.subprocess, "run", side_effect=defaults):
                self.invoke(root, definition, "apply")
            self.assertEqual(
                calls[-1],
                [
                    "/usr/bin/defaults",
                    "-currentHost",
                    "write",
                    "NSGlobalDomain",
                    "com.apple.mouse.tapBehavior",
                    "-int",
                    "1",
                ],
            )
            self.assertEqual(
                plistlib.loads(
                    next((root / "preferences/backups.local").iterdir()).read_bytes()
                ),
                live,
            )


if __name__ == "__main__":
    unittest.main()
