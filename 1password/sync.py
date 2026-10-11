#!/usr/bin/env python3
"""Manually compare, restore, and update private dotfile Documents in 1Password."""

import argparse
import difflib
import os
from pathlib import Path, PurePosixPath
import re
import shutil
import subprocess
import sys
import tempfile


REPO = Path(__file__).resolve().parent.parent
DEFAULT_CONFIG = Path(__file__).with_name("machines.yaml")


class SyncError(Exception):
    pass


def valid_id(value, label):
    if not isinstance(value, str) or not re.fullmatch(r"[A-Za-z0-9]{26}", value):
        raise SyncError(f"Invalid {label}; expected a 26-character ID")
    return value


def mapped_files(value, label):
    if not isinstance(value, list):
        raise SyncError(f"Invalid {label}; expected a list")
    files = []
    for entry in value:
        if not isinstance(entry, dict) or set(entry) != {"path", "item_id"}:
            raise SyncError(f"Invalid {label} entry")
        name = entry["path"]
        if (not isinstance(name, str) or not name or "\\" in name or
                PurePosixPath(name).is_absolute() or
                any(part in ("", ".", "..") for part in name.split("/"))):
            raise SyncError(f"Unsafe path in {label}")
        files.append((name, valid_id(entry["item_id"], f"{label} item ID")))
    return files


def load_config(path):
    # Reuse Dotbot's parser without adding a fresh-machine pip dependency.
    sys.path.insert(0, str(REPO / "dotbot/lib/pyyaml/lib"))
    try:
        import yaml
    except ImportError as error:
        raise SyncError(
            "YAML parser unavailable; run git submodule update --init --recursive"
        ) from error
    try:
        config = yaml.safe_load(path.read_text())
    except (OSError, UnicodeError, yaml.YAMLError) as error:
        raise SyncError(f"Cannot read configuration: {path}") from error
    if not isinstance(config, dict) or set(config) != {
            "account_id", "default_machine", "shared_gpg", "machines"}:
        raise SyncError("Invalid configuration fields")
    valid_id(config["account_id"], "account ID")
    shared = config["shared_gpg"]
    if not isinstance(shared, dict) or set(shared) != {
            "vault_id", "item_id", "public_attachment_id",
            "private_attachment_id", "fingerprint_field"}:
        raise SyncError("Invalid shared_gpg configuration")
    for key in ("vault_id", "item_id", "public_attachment_id", "private_attachment_id"):
        valid_id(shared[key], f"shared_gpg {key}")
    if (not isinstance(shared["fingerprint_field"], str) or
            not re.fullmatch(r"[A-Za-z0-9_]+", shared["fingerprint_field"])):
        raise SyncError("Invalid shared_gpg fingerprint_field")
    machines = config["machines"]
    if not isinstance(machines, dict) or not machines:
        raise SyncError("Invalid machines configuration")
    if (not isinstance(config["default_machine"], str) or
            config["default_machine"] not in machines):
        raise SyncError("Default machine is not configured")
    for machine, details in machines.items():
        if not isinstance(machine, str) or not re.fullmatch(r"[A-Za-z0-9_-]+", machine):
            raise SyncError("Invalid machine selector")
        if (not isinstance(details, dict) or
                not {"vault_id", "files"} <= set(details) or
                set(details) - {"vault_id", "files", "recovery_files"}):
            raise SyncError(f"Invalid configuration for machine {machine}")
        valid_id(details["vault_id"], f"{machine} vault ID")
        files = mapped_files(details["files"], f"{machine} files")
        recovery = mapped_files(details.get("recovery_files", []), f"{machine} recovery_files")
        names = [name for name, _ in files + recovery]
        if len(names) != len(set(names)):
            raise SyncError(f"Duplicate file path for machine {machine}")
        details["files"] = files
        details["recovery_files"] = recovery
    return config


def run(command):
    try:
        return subprocess.run(command, check=True, stdout=subprocess.PIPE,
                              stderr=subprocess.PIPE).stdout
    except (subprocess.CalledProcessError, OSError) as error:
        # CLI stderr can contain document contents. Never relay it by default.
        raise SyncError(f"Command failed: {command[0]} {command[1]}") from error


def vault_document(item, destination, args):
    run(["op", "document", "get", item, "--account", args.account,
         "--vault", args.vault, "--out-file", str(destination),
         "--file-mode", "0600"])
    return read_file(destination)


def read_file(path):
    try:
        return path.read_bytes()
    except OSError as error:
        raise SyncError(f"Cannot read {path}") from error


def local_bytes(path):
    if path.is_symlink():
        raise SyncError(f"Local path is a symlink: {path}")
    try:
        return path.read_bytes()
    except FileNotFoundError:
        return None
    except OSError as error:
        raise SyncError(f"Cannot read {path}") from error


def show_diff(name, vault, local):
    if local is None:
        return
    try:
        before = vault.decode("utf-8").splitlines(keepends=True)
        after = local.decode("utf-8").splitlines(keepends=True)
    except UnicodeDecodeError:
        print(f"{name}: binary contents; diff unavailable")
        return
    diff = difflib.unified_diff(before, after, fromfile=f"vault/{name}",
                                tofile=f"local/{name}")
    sys.stdout.writelines(diff)


def compare(args, temporary, diff=False):
    results = []
    for index, (name, item) in enumerate(args.files):
        vault_path = temporary / f"vault-{index}"
        try:
            vault = vault_document(item, vault_path, args)
        except SyncError:
            print(f"unavailable  {name} (vault read failed)", file=sys.stderr)
            results.append((name, item, None, None, "unavailable"))
            continue
        local = local_bytes(REPO / name)
        state = "missing" if local is None else "unchanged" if local == vault else "modified"
        print(f"{state:<11}{name}")
        if diff and state == "modified":
            show_diff(name, vault, local)
        results.append((name, item, vault, local, state))
    return results


def restore(args, temporary):
    existing = [name for name, _ in args.files if (REPO / name).exists()
                or (REPO / name).is_symlink()]
    if existing:
        raise SyncError("Existing local files; review before restoring: " + ", ".join(existing))
    staged = []
    for index, (name, item) in enumerate(args.files):
        source = temporary / f"vault-{index}"
        vault_document(item, source, args)
        staged.append((name, source))
    created = []
    try:
        for name, source in staged:
            destination = REPO / name
            try:
                destination.parent.mkdir(parents=True, exist_ok=True)
                descriptor = os.open(destination, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
            except OSError as error:
                raise SyncError(f"Cannot create {name}; existing files were not overwritten") from error
            created.append((name, destination, os.fstat(descriptor).st_ino))
            try:
                with os.fdopen(descriptor, "wb") as target, source.open("rb") as staged_file:
                    shutil.copyfileobj(staged_file, target)
            except OSError as error:
                raise SyncError(f"Cannot restore {name}") from error
    except SyncError as error:
        remaining = []
        for name, destination, inode in reversed(created):
            try:
                if destination.lstat().st_ino == inode:
                    destination.unlink()
                else:
                    remaining.append(name)
            except FileNotFoundError:
                pass
            except OSError:
                remaining.append(name)
        if remaining:
            raise SyncError(f"{error}; could not roll back: {', '.join(remaining)}") from error
        raise
    for name, _ in staged:
        print(f"Restored {name}")
    print("Review local paths, trust, and permissions before running ./install.")


def update(args, temporary):
    results = compare(args, temporary, args.diff)
    if any(state == "unavailable" for _, _, _, _, state in results):
        raise SyncError("Vault comparison failed; no Documents were updated")
    changed = [(name, item, vault, local) for name, item, vault, local, state in results
               if state == "modified"]
    if not changed:
        print("No modified local files to upload.")
        return
    print("Update these Documents: " + ", ".join(name for name, _, _, _ in changed))
    try:
        answer = input("Upload these local files to 1Password? [y/N] ")
    except EOFError:
        answer = ""
    if answer.strip().lower() not in ("y", "yes"):
        print("Cancelled; no Documents were updated.")
        return
    # Check every source again before the first upload, then upload private snapshots.
    for name, _, _, snapshot in changed:
        if local_bytes(REPO / name) != snapshot:
            raise SyncError(f"Local file changed during review: {name}")
    for index, (name, item, vault_snapshot, _) in enumerate(changed):
        if vault_document(item, temporary / f"recheck-{index}", args) != vault_snapshot:
            raise SyncError(f"Vault Document changed during review: {name}")
    for index, (name, item, _, snapshot) in enumerate(changed):
        source = temporary / f"upload-{index}"
        source.write_bytes(snapshot)
        source.chmod(0o600)
        run(["op", "document", "edit", item, str(source), "--account", args.account,
             "--vault", args.vault])
        verified = vault_document(item, temporary / f"verify-{index}", args)
        if verified != snapshot:
            raise SyncError(f"Verification failed for {name}; stop and inspect the vault item")
        print(f"Updated and verified {name}")


def primary_fingerprints(records):
    fingerprints = []
    primary = False
    has_secret = False
    for line in records.decode("utf-8", errors="replace").splitlines():
        fields = line.split(":")
        kind = fields[0]
        if kind in ("pub", "sec"):
            primary = True
            has_secret |= kind == "sec"
        elif kind == "fpr" and primary:
            fingerprints.append(fields[9] if len(fields) > 9 else "")
            primary = False
    return fingerprints, has_secret


def restore_gpg(args, temporary):
    shared = args.shared_gpg
    fingerprint = run(["op", "read", f"op://{shared['vault_id']}/{shared['item_id']}/{shared['fingerprint_field']}",
                       "--account", args.account]).decode("utf-8", errors="replace").strip()
    if not re.fullmatch(r"[A-F0-9]{40}", fingerprint):
        raise SyncError("The vault signing fingerprint is missing or invalid")
    local_key = run(["git", "config", "--file", str(REPO / "git/gitconfig.local.symlink"),
                     "--get", "user.signingkey"]).decode("utf-8", errors="replace").strip()
    if local_key != fingerprint:
        raise SyncError("Restore settings first; local Git signingkey must match the vault fingerprint")
    key_check = temporary / "key-check"
    key_check.mkdir(mode=0o700)
    attachments = []
    for kind, attachment in (("public", shared["public_attachment_id"]),
                             ("private", shared["private_attachment_id"])):
        path = temporary / f"{kind}.gpg"
        run(["op", "read", f"op://{shared['vault_id']}/{shared['item_id']}/{attachment}",
             "--account", args.account, "--out-file", str(path), "--file-mode", "0600"])
        records = run(["gpg", "--homedir", str(key_check), "--batch", "--with-colons",
                       "--show-keys", str(path)])
        fingerprints, has_secret = primary_fingerprints(records)
        if fingerprints != [fingerprint] or (kind == "private" and not has_secret):
            raise SyncError(f"The {kind} key attachment does not match the vault fingerprint")
        attachments.append(str(path))
    run(["gpg", "--import", *attachments])
    run(["gpg", "--list-secret-keys", "--fingerprint", fingerprint])
    print("Imported and verified the configured GPG signing key.")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--config", type=Path, default=DEFAULT_CONFIG, metavar="PATH")
    parser.add_argument("--account", metavar="ID")
    parser.add_argument("--machine", metavar="ALIAS")
    subparsers = parser.add_subparsers(dest="command", required=True)
    for command in ("status", "restore", "update", "restore-gpg"):
        sub = subparsers.add_parser(command)
        if command in ("status", "update"):
            sub.add_argument("--diff", action="store_true",
                             help="print file contents in a unified diff")
    args = parser.parse_args()
    try:
        config = load_config(args.config)
        args.account = valid_id(args.account or config["account_id"], "account ID")
        args.machine = args.machine or config["default_machine"]
        if args.machine not in config["machines"]:
            raise SyncError(f"Unknown machine alias: {args.machine}")
        args.vault = config["machines"][args.machine]["vault_id"]
        args.files = config["machines"][args.machine]["files"]
        args.shared_gpg = config["shared_gpg"]
    except SyncError as error:
        parser.error(str(error))
    required = ("op", "git", "gpg") if args.command == "restore-gpg" else ("op",)
    for command in required:
        if shutil.which(command) is None:
            parser.error(f"{command} is required")
    try:
        with tempfile.TemporaryDirectory(prefix="dotfiles-1password-") as directory:
            temporary = Path(directory)
            if args.command != "restore-gpg":
                print(f"Machine: {args.machine}")
                if not args.files:
                    print("No configured files for this machine.")
                    return 0
            if args.command == "status":
                results = compare(args, temporary, args.diff)
                if any(state == "unavailable" for _, _, _, _, state in results):
                    return 1
            elif args.command == "restore":
                restore(args, temporary)
            elif args.command == "update":
                update(args, temporary)
            else:
                restore_gpg(args, temporary)
    except SyncError as error:
        print(f"Error: {error}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
