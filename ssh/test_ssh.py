"""Offline checks for machine selection and effective SSH authentication settings."""

import os
from pathlib import Path
import shutil
import subprocess
import tempfile
import unittest


REPO = Path(__file__).resolve().parent.parent


class InstallTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)
        self.checkout = self.root / "checkout with spaces"
        self.checkout.mkdir()
        shutil.copy2(REPO / "install", self.checkout / "install")
        (self.checkout / "ssh").mkdir()
        (self.checkout / "ssh/config.local").write_text("# restored\n")
        self.bin = self.root / "bin"
        self.bin.mkdir()
        self.log = self.root / "git.log"
        git = self.bin / "git"
        git.write_text('#!/usr/bin/env bash\nset -e\nprintf "%s\\n" "$*" >> "$TEST_GIT_LOG"\n')
        git.chmod(0o755)
        dotbot = self.checkout / "dotbot/bin/dotbot"
        dotbot.parent.mkdir(parents=True)
        dotbot.write_text('#!/usr/bin/env bash\nset -e\nprintf "selected=%s\\n" "$DOTFILES_MACHINE"\nprintf "arg=%s\\n" "$@"\n')
        dotbot.chmod(0o755)

    def invoke(self):
        return subprocess.run(
            [str(self.checkout / "install"), "--only", "link"], cwd=self.root,
            env=dict(os.environ, PATH=f"{self.bin}:{os.environ['PATH']}",
                     TEST_GIT_LOG=str(self.log), DOTFILES_MACHINE="inherited-value"),
            text=True, capture_output=True,
        )

    def test_missing_or_invalid_machine_stops_before_installing(self):
        selector = self.checkout / ".machine"
        for value in (None, "", "unknown", "machine-1\nmachine-2", "../machine-1"):
            with self.subTest(value=value):
                if value is not None:
                    selector.write_text(value)
                result = self.invoke()
                self.assertNotEqual(result.returncode, 0)
                self.assertIn(".machine", result.stderr)
                self.assertFalse(self.log.exists())

    def test_each_machine_is_exported_from_the_checkout_selector(self):
        for machine in ("machine-1", "machine-2"):
            with self.subTest(machine=machine):
                (self.checkout / ".machine").write_text(machine + "\n")
                result = self.invoke()
                self.assertEqual(result.returncode, 0, result.stderr)
                self.assertIn(f"selected={machine}", result.stdout)
                self.assertIn(f"arg={self.checkout}", result.stdout)
                self.assertIn("arg=--only\narg=link", result.stdout)

    def test_missing_private_config_stops_before_installing(self):
        (self.checkout / ".machine").write_text("machine-1\n")
        (self.checkout / "ssh/config.local").unlink()
        result = self.invoke()
        self.assertNotEqual(result.returncode, 0)
        self.assertIn("Restore ssh/config.local", result.stderr)
        self.assertFalse(self.log.exists())


@unittest.skipUnless(shutil.which("ssh"), "OpenSSH is required")
class SSHConfigTests(unittest.TestCase):
    def effective_config(self, machine, host):
        with tempfile.TemporaryDirectory() as directory:
            root = Path(directory)
            private = root / "config.local"
            private.write_text(
                "Host git-example\n"
                "    HostName github.com\n"
                "    User git\n"
                "    IdentityFile ~/.ssh/example.pub\n"
                "    IdentitiesOnly yes\n"
                "    UseKeychain no\n"
                "Host tunnel-example\n"
                "    HostName example.com\n"
                "    ProxyCommand cloudflared access ssh --hostname %h\n"
                "Host local-key-example\n"
                "    IdentityFile ~/.ssh/id_local\n"
                "    IdentitiesOnly yes\n"
                "    IdentityAgent SSH_AUTH_SOCK\n"
                "    UseKeychain yes\n"
                "    AddKeysToAgent yes\n"
                "Host password-key-example\n"
                "    IdentityFile ~/.ssh/id_sensitive.pub\n"
                "    IdentitiesOnly yes\n"
                '    IdentityAgent "~/Library/Group Containers/2BUA8C4S2C.com.1password/t/agent.sock"\n'
                "    UseKeychain no\n"
                "    AddKeysToAgent no\n"
            )
            wrapper = (REPO / f"ssh/config.{machine}").read_text()
            # OpenSSH resolves relative Includes in ~/.ssh, regardless of -F.
            wrapper = wrapper.replace("Include config.local", f'Include "{private}"')
            config = root / "config"
            config.write_text("IgnoreUnknown UseKeychain\n" + wrapper)
            result = subprocess.run(["ssh", "-G", "-F", str(config), host],
                                    text=True, capture_output=True)
            self.assertEqual(result.returncode, 0, result.stderr)
        values = {}
        for line in result.stdout.splitlines():
            key, value = line.split(" ", 1)
            values.setdefault(key, []).append(value)
        return values

    def test_machine_1_can_select_a_specific_agent_key_for_a_host(self):
        values = self.effective_config("machine-1", "git-example")
        self.assertEqual(values["hostname"], ["github.com"])
        self.assertEqual(values["user"], ["git"])
        self.assertIn("com.1password/t/agent.sock", values["identityagent"][0])
        self.assertEqual(values["identitiesonly"], ["yes"])
        self.assertEqual(values["addkeystoagent"], ["false"])
        self.assertEqual(values["identityfile"], ["~/.ssh/example.pub", "none"])
        if "usekeychain" in values:
            self.assertEqual(values["usekeychain"], ["no"])

    def test_machine_1_unknown_hosts_do_not_load_default_private_keys(self):
        values = self.effective_config("machine-1", "unknown-example")
        self.assertIn("com.1password/t/agent.sock", values["identityagent"][0])
        self.assertEqual(values["identityfile"], ["none"])
        self.assertEqual(values["identitiesonly"], ["no"])

    def test_machine_2_can_select_a_specific_agent_key_for_a_host(self):
        values = self.effective_config("machine-2", "git-example")
        self.assertIn("com.1password/t/agent.sock", values["identityagent"][0])
        self.assertEqual(values["addkeystoagent"], ["false"])
        self.assertEqual(values["identityfile"], ["~/.ssh/example.pub"])
        if "usekeychain" in values:
            self.assertEqual(values["usekeychain"], ["no"])

    def test_both_machines_can_use_a_local_encrypted_key_for_one_host(self):
        for machine in ("machine-1", "machine-2"):
            with self.subTest(machine=machine):
                values = self.effective_config(machine, "local-key-example")
                self.assertEqual(values["identityagent"], ["SSH_AUTH_SOCK"])
                expected_files = ["~/.ssh/id_local"]
                if machine == "machine-1":
                    expected_files.append("none")
                self.assertEqual(values["identityfile"], expected_files)
                self.assertEqual(values["identitiesonly"], ["yes"])
                self.assertEqual(values["addkeystoagent"], ["true"])
                if "usekeychain" in values:
                    self.assertEqual(values["usekeychain"], ["yes"])

    def test_machine_2_can_use_1password_for_one_host(self):
        values = self.effective_config("machine-2", "password-key-example")
        self.assertIn("com.1password/t/agent.sock", values["identityagent"][0])
        self.assertEqual(values["identityfile"], ["~/.ssh/id_sensitive.pub"])
        self.assertEqual(values["identitiesonly"], ["yes"])
        self.assertEqual(values["addkeystoagent"], ["false"])
        if "usekeychain" in values:
            self.assertEqual(values["usekeychain"], ["no"])

    def test_private_proxy_rules_survive_both_machine_wrappers(self):
        for machine in ("machine-1", "machine-2"):
            with self.subTest(machine=machine):
                values = self.effective_config(machine, "tunnel-example")
                self.assertEqual(values["proxycommand"],
                                 ["cloudflared access ssh --hostname %h"])


if __name__ == "__main__":
    unittest.main()
