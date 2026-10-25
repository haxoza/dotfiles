"""Offline integration tests for the private settings CLI."""

import os
from pathlib import Path
import shutil
import subprocess
import sys
import tempfile
import unittest


SOURCE = Path(__file__).with_name("sync.py")
YAML_LIB = SOURCE.parent.parent / "dotbot/lib/pyyaml/lib"
sys.path.insert(0, str(YAML_LIB))
import yaml
ITEMS = {
    "git/gitconfig.local.symlink": "qrt3bycy3vf6hxfz24srel5qh4",
    "hg/hgrc.local.symlink": "2qrynbqaezijrlexobhdp5s55u",
    "pypi/pypirc.symlink": "nlxsszvskmzn75rabnr7enstza",
    "codex/trusted.local.toml": "vmv6y5vs6yyzcdepkb4v7x7x2a",
}
FINGERPRINT = "A" * 40
GPG_ITEM = "7v3nih63myunemcskekwde5lgy"
GPG_PUBLIC = "u5hmzripyqs2f6kxnu37m5426e"
GPG_PRIVATE = "bg3fhf5eiak4uvwe45kt66u7oy"
FAKE_OP = '''#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
vault = Path(os.environ["FAKE_VAULT"])
with Path(os.environ["FAKE_LOG"]).open("a") as log:
    log.write(" ".join(args[:3]) + "\\n")
if args[:2] == ["document", "get"]:
    if args[2] == os.environ.get("FAKE_FAIL_GET"):
        print("SENSITIVE_VAULT_ERROR", file=sys.stderr)
        sys.exit(1)
    Path(args[args.index("--out-file") + 1]).write_bytes((vault / args[2]).read_bytes())
elif args[:2] == ["document", "edit"]:
    if "--file-name" in args:
        with Path(os.environ["FAKE_LOG"]).open("a") as log:
            log.write("file-name " + args[args.index("--file-name") + 1] + "\\n")
    if args[2] == os.environ.get("FAKE_FAIL_EDIT"):
        print("SENSITIVE_EDIT_ERROR", file=sys.stderr)
        sys.exit(1)
    (vault / args[2]).write_bytes(Path(args[3]).read_bytes())
    if args[2] == os.environ.get("FAKE_BAD_VERIFY"):
        (vault / args[2]).write_bytes(b"changed-after-upload\\n")
elif args[:1] == ["read"]:
    ref = args[1].split("/")[-1]
    if "--out-file" in args:
        Path(args[args.index("--out-file") + 1]).write_bytes((vault / ref).read_bytes())
    else:
        sys.stdout.buffer.write((vault / ref).read_bytes())
else:
    sys.exit(2)
'''
FAKE_GIT = '''#!/usr/bin/env python3
import os
import sys
sys.stdout.write(os.environ["FAKE_FINGERPRINT"] + "\\n")
'''
FAKE_GPG = '''#!/usr/bin/env python3
import os
from pathlib import Path
import sys

args = sys.argv[1:]
with Path(os.environ["FAKE_GPG_LOG"]).open("a") as log:
    log.write(" ".join(args) + "\\n")
if "--show-keys" in args:
    fingerprint = os.environ["FAKE_FINGERPRINT"]
    if Path(args[-1]).read_bytes() == b"bad-key":
        fingerprint = "B" * 40
    kind = "sec" if Path(args[-1]).name == "private.gpg" else "pub"
    sys.stdout.write(kind + ":\\n" + "fpr:::::::::" + fingerprint + ":\\n")
elif "--import" in args or "--list-secret-keys" in args:
    pass
else:
    sys.exit(2)
'''


class SyncTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        (self.root / ".machine").write_text("machine-1\n")
        (self.root / "1password").mkdir()
        shutil.copy2(SOURCE, self.root / "1password/sync.py")
        bundled_yaml = self.root / "dotbot/lib/pyyaml/lib"
        bundled_yaml.parent.mkdir(parents=True)
        bundled_yaml.symlink_to(YAML_LIB.resolve(), target_is_directory=True)
        self.config = {
            "account_id": "A" * 26,
            "shared_gpg": {
                "vault_id": "S" * 26,
                "item_id": GPG_ITEM,
                "public_attachment_id": GPG_PUBLIC,
                "private_attachment_id": GPG_PRIVATE,
                "fingerprint_field": "signing_fingerprint",
            },
            "machines": {
                "machine-1": {
                    "vault_id": "V" * 26,
                    "files": [{"path": name, "item_id": item} for name, item in ITEMS.items()],
                    "recovery_files": [{"path": "codex/config.toml", "item_id": "R" * 26}],
                },
                "machine-2": {"vault_id": "W" * 26, "files": []},
            },
        }
        self.write_config()
        self.vault = self.root / "vault"
        self.vault.mkdir()
        for item in ITEMS.values():
            (self.vault / item).write_bytes(b"vault-secret\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        op = self.bin / "op"
        op.write_text(FAKE_OP)
        op.chmod(0o755)
        for name, contents in (("git", FAKE_GIT), ("gpg", FAKE_GPG)):
            executable = self.bin / name
            executable.write_text(contents)
            executable.chmod(0o755)
        self.log = self.root / "op.log"
        self.env = dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                        FAKE_VAULT=str(self.vault), FAKE_LOG=str(self.log),
                        FAKE_GPG_LOG=str(self.root / "gpg.log"),
                        FAKE_FINGERPRINT=FINGERPRINT)

    def write_config(self):
        (self.root / "1password/machines.yaml").write_text(yaml.safe_dump(self.config))

    def invoke(self, *args, input=None, env=None):
        return subprocess.run([sys.executable, str(self.root / "1password/sync.py"), *args],
                              input=input, text=True, capture_output=True,
                              env=env or self.env)

    def test_local_machine_selection(self):
        (self.root / ".machine").write_text("machine-2\n")
        result = self.invoke("status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Machine: machine-2", result.stdout)
        self.assertFalse(self.log.exists())

    def test_missing_machine_stops_before_vault_access(self):
        (self.root / ".machine").unlink()
        for command in ("status", "restore", "update", "restore-gpg"):
            with self.subTest(command=command):
                result = self.invoke(command, input="y\n")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Set repository .machine or pass --machine <alias>",
                              result.stderr)
                self.assertFalse(self.log.exists())
                self.assertFalse((self.root / "gpg.log").exists())
                for name in ITEMS:
                    self.assertFalse((self.root / name).exists(), name)

    def test_explicit_machine_without_local_selection(self):
        (self.root / ".machine").unlink()
        result = self.invoke("--machine", "machine-1", "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Machine: machine-1", result.stdout)
        self.assertIn("document get", self.log.read_text())

    def test_explicit_machine_overrides_local_selection(self):
        (self.root / ".machine").write_text("invalid local value\n")
        result = self.invoke("--machine", "machine-2", "status")
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertIn("Machine: machine-2", result.stdout)
        self.assertFalse(self.log.exists())

    def test_invalid_local_machine_stops_before_vault_access(self):
        for contents in ("", "machine-1\nmachine-2\n", "unknown-machine\n"):
            with self.subTest(contents=contents):
                (self.root / ".machine").write_text(contents)
                result = self.invoke("status")
                self.assertNotEqual(result.returncode, 0)
                self.assertFalse(self.log.exists())

    def test_invalid_yaml_is_rejected_without_vault_access(self):
        for contents in ("machines: [", "!!python/object:builtins.object {}"):
            with self.subTest(contents=contents):
                (self.root / "1password/machines.yaml").write_text(contents)
                result = self.invoke("status")
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Cannot read configuration", result.stderr)
                self.assertFalse(self.log.exists())

    def test_status_reports_states_without_contents(self):
        local = self.root / "git/gitconfig.local.symlink"
        local.parent.mkdir()
        local.write_bytes(b"local-secret\n")
        result = self.invoke("status")
        self.assertEqual(result.returncode, 0)
        self.assertIn("modified", result.stdout)
        self.assertIn("missing", result.stdout)
        self.assertNotIn("secret", result.stdout + result.stderr)
        self.assertIn("Machine: machine-1", result.stdout)
        explicit = self.invoke("status", "--diff")
        self.assertIn("local-secret", explicit.stdout)

    def test_failed_vault_read_cannot_trigger_update(self):
        local = self.root / "git/gitconfig.local.symlink"
        local.parent.mkdir()
        local.write_bytes(b"local-secret\n")
        env = dict(self.env, FAKE_FAIL_GET=next(iter(ITEMS.values())))
        result = self.invoke("update", input="y\n", env=env)
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("unavailable", result.stderr)
        self.assertNotIn("SENSITIVE_VAULT_ERROR", result.stderr)
        self.assertEqual((self.vault / next(iter(ITEMS.values()))).read_bytes(), b"vault-secret\n")
        self.assertNotIn("document edit", self.log.read_text())

    def test_restore_stages_all_and_refuses_overwrite(self):
        local = self.root / "git/gitconfig.local.symlink"
        local.parent.mkdir()
        local.write_bytes(b"local-secret\n")
        refused = self.invoke("restore")
        self.assertNotEqual(refused.returncode, 0)
        self.assertEqual(local.read_bytes(), b"local-secret\n")
        local.unlink()
        failed = self.invoke("restore", env=dict(self.env, FAKE_FAIL_GET=list(ITEMS.values())[-1]))
        self.assertNotEqual(failed.returncode, 0)
        self.assertFalse(local.exists())
        restored = self.invoke("restore")
        self.assertEqual(restored.returncode, 0, restored.stderr)
        self.assertEqual(local.read_bytes(), b"vault-secret\n")
        self.assertEqual(local.stat().st_mode & 0o777, 0o600)

    def test_restore_rolls_back_on_later_local_write_failure(self):
        blocked = self.root / "pypi"
        blocked.write_text("existing parent file")
        result = self.invoke("restore")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Cannot create pypi/pypirc.symlink", result.stderr)
        self.assertNotIn("Traceback", result.stderr)
        self.assertEqual(blocked.read_text(), "existing parent file")
        for name in ITEMS:
            self.assertFalse((self.root / name).exists(), name)

    def test_selective_restore_leaves_existing_unselected_files_alone(self):
        existing = self.root / "git/gitconfig.local.symlink"
        existing.parent.mkdir()
        existing.write_bytes(b"existing-private-settings\n")
        selected = ["hg/hgrc.local.symlink", "pypi/pypirc.symlink"]
        result = self.invoke("restore", "--only", selected[0], "--only", selected[1])
        self.assertEqual(result.returncode, 0, result.stderr)
        self.assertEqual(existing.read_bytes(), b"existing-private-settings\n")
        for name in selected:
            self.assertEqual((self.root / name).read_bytes(), b"vault-secret\n")
            self.assertEqual((self.root / name).stat().st_mode & 0o777, 0o600)
        self.assertNotIn(ITEMS["git/gitconfig.local.symlink"], self.log.read_text())
        self.assertNotIn(ITEMS["codex/trusted.local.toml"], self.log.read_text())

    def test_selective_restore_rejects_unknown_and_recovery_paths_before_vault_access(self):
        for name in ("unknown", "../outside", "codex/config.toml"):
            with self.subTest(name=name):
                result = self.invoke("restore", "--only", name)
                self.assertNotEqual(result.returncode, 0)
                self.assertIn("Files not configured for this machine", result.stderr)
                self.assertFalse(self.log.exists())

    def test_update_aborts_if_vault_changes_during_confirmation(self):
        name, item = next(iter(ITEMS.items()))
        local = self.root / name
        local.parent.mkdir()
        local.write_bytes(b"local-secret\n")
        process = subprocess.Popen([sys.executable, str(self.root / "1password/sync.py"),
                                    "update"], stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                   stderr=subprocess.PIPE, text=True, env=self.env)
        prompt = ""
        while not prompt.endswith("[y/N] "):
            char = process.stdout.read(1)
            self.assertTrue(char, "update exited before confirmation")
            prompt += char
        (self.vault / item).write_bytes(b"other-writer\n")
        stdout, stderr = process.communicate("y\n", timeout=10)
        self.assertNotEqual(process.returncode, 0)
        self.assertIn("Vault Document changed during review", stderr)
        self.assertEqual((self.vault / item).read_bytes(), b"other-writer\n")
        self.assertNotIn("document edit", self.log.read_text())

    def test_update_verification_mismatch_stops(self):
        name, item = next(iter(ITEMS.items()))
        local = self.root / name
        local.parent.mkdir()
        local.write_bytes(b"local-secret\n")
        result = self.invoke("update", input="y\n",
                             env=dict(self.env, FAKE_BAD_VERIFY=item))
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Verification failed", result.stderr)
        self.assertNotIn("secret", result.stdout + result.stderr)

    def test_restore_gpg_rejects_mismatched_attachment_before_import(self):
        (self.vault / "signing_fingerprint").write_text(FINGERPRINT)
        (self.vault / GPG_PUBLIC).write_bytes(b"valid-public")
        (self.vault / GPG_PRIVATE).write_bytes(b"bad-key")
        result = self.invoke("restore-gpg")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("private key attachment does not match", result.stderr)
        self.assertNotIn("--import", (self.root / "gpg.log").read_text())
        self.assertIn(self.config["shared_gpg"]["vault_id"], self.log.read_text())

    def test_empty_machine_makes_no_vault_calls(self):
        for command in ("status", "restore", "update"):
            result = self.invoke("--machine", "machine-2", command, input="y\n")
            self.assertEqual(result.returncode, 0, result.stderr)
            self.assertIn("Machine: machine-2", result.stdout)
            self.assertIn("No configured files", result.stdout)
        self.assertFalse(self.log.exists())

    def test_invalid_mapping_is_rejected_before_vault_access(self):
        self.config["machines"]["machine-1"]["files"][0]["path"] = "../outside"
        self.write_config()
        result = self.invoke("restore")
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Unsafe path", result.stderr)
        self.assertFalse(self.log.exists())

    def test_update_confirms_once_preserves_filename_and_verifies_bytes(self):
        local = self.root / "git/gitconfig.local.symlink"
        local.parent.mkdir()
        local.write_bytes(b"local-secret\n")
        cancelled = self.invoke("update", input="n\n")
        self.assertEqual(cancelled.returncode, 0)
        self.assertEqual((self.vault / next(iter(ITEMS.values()))).read_bytes(), b"vault-secret\n")
        uploaded = self.invoke("update", input="y\n")
        self.assertEqual(uploaded.returncode, 0, uploaded.stderr)
        self.assertIn("Updated and verified", uploaded.stdout)
        self.assertIn("file-name gitconfig.local.symlink\n", self.log.read_text())
        self.assertEqual((self.vault / next(iter(ITEMS.values()))).read_bytes(), b"local-secret\n")
        self.assertNotIn("secret", uploaded.stdout + uploaded.stderr)


if __name__ == "__main__":
    unittest.main()
