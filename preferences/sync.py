#!/usr/bin/env python3
"""Explicit export/apply of selected settings, preserving app-owned values."""

import argparse
import json
import os
import platform
import plistlib
import re
import subprocess
import tempfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


def load_sources():
    return json.loads((ROOT / "preferences/sources.json").read_text())


def jsonc(text):
    """Accept VS Code comments/trailing commas without touching string contents."""
    text = re.sub(
        r'"(?:\\.|[^"\\])*"|//[^\n]*|/\*[\s\S]*?\*/',
        lambda m: m[0] if m[0].startswith('"') else " ",
        text,
    )
    text = re.sub(
        r'"(?:\\.|[^"\\])*"|,\s*(?=[}\]])',
        lambda m: m[0] if m[0].startswith('"') else "",
        text,
    )
    return json.loads(text)


def selected(live, source):
    """Export only already-owned keys, including nested settings."""
    if not isinstance(live, dict):
        raise TypeError("Expected a settings object")
    return {
        k: selected(live[k], v) if isinstance(v, dict) else live[k]
        for k, v in source.items()
        if k in live
    }


def merged(live, source):
    if not isinstance(live, dict):
        raise TypeError("Expected a settings object")
    result = dict(live)
    for k, v in source.items():
        result[k] = merged(result.get(k, {}), v) if isinstance(v, dict) else v
    return result


def missing_owned(live, source, prefix=""):
    missing = []
    for key, value in source.items():
        name = f"{prefix}{key}"
        if key not in live:
            missing.append(name)
        elif isinstance(value, dict):
            if not isinstance(live[key], dict):
                raise ValueError(f"Expected an object for {name}")
            missing.extend(missing_owned(live[key], value, name + "."))
    return missing


def defaults_args(value):
    if isinstance(value, bool):
        return ["-bool", str(value).lower()]
    if isinstance(value, int):
        return ["-int", str(value)]
    if isinstance(value, float):
        return ["-float", str(value)]
    if isinstance(value, str):
        return ["-string", value]
    if isinstance(value, list) and all(isinstance(item, str) for item in value):
        return ["-array", *value]
    if isinstance(value, (dict, list)):
        # A single XML plist value preserves nested types without importing a domain.
        return [plistlib.dumps(value).decode()]
    raise ValueError("Defaults values must be scalars, lists or dictionaries")


def validate_defaults(source, definition):
    policy = definition.get("key_filter", {})
    for key, value in source.items():
        if key in policy.get("exclude", []) or (
            policy
            and key not in policy.get("include", [])
            and not key.startswith(tuple(policy.get("prefixes", [])))
        ):
            raise ValueError(f"Setting excluded by source policy: {key}")
        defaults_args(value)
        if key in definition.get("list_items", {}):
            allowed = definition["list_items"][key]
            if not isinstance(value, list) or any(
                item not in allowed for item in value
            ):
                raise ValueError(
                    f"Only configured shared list items may be tracked: {key}"
                )


def owned_view(live, definition):
    """Project shared list members without adopting app/device-specific entries."""
    result = dict(live)
    for key, allowed in definition.get("list_items", {}).items():
        if key in result:
            if not isinstance(result[key], list) or not all(
                isinstance(item, str) for item in result[key]
            ):
                raise ValueError(f"Expected a list of strings for {key}")
            result[key] = [item for item in result[key] if item in allowed]
    return result


def value_to_apply(key, value, live, definition):
    if isinstance(value, dict):
        return merged(live.get(key, {}), value)
    if key not in definition.get("list_items", {}):
        return value
    allowed = definition["list_items"][key]
    local = [item for item in live.get(key, []) if item not in allowed]
    return [*local, *value]


def defaults_command(definition, action, *arguments):
    host = ["-currentHost"] if definition.get("current_host", False) else []
    return ["/usr/bin/defaults", *host, action, definition["domain"], *arguments]


def relative_path(directory, name):
    path = Path(name)
    if path.is_absolute() or ".." in path.parts:
        raise ValueError(f"Expected a relative path without '..': {name}")
    return directory / path


def atomic_write(path, data):
    """Preserve the destination's mode and resolve a pre-existing symlink."""
    path = path.resolve()
    path.parent.mkdir(parents=True, exist_ok=True)
    mode = path.stat().st_mode & 0o777 if path.exists() else 0o600
    fd, temporary = tempfile.mkstemp(dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(data)
        os.chmod(temporary, mode)
        os.replace(temporary, path)
    finally:
        if os.path.exists(temporary):
            os.unlink(temporary)


def backup(app, raw):
    directory = ROOT / "preferences/backups.local"
    directory.mkdir(mode=0o700, parents=True, exist_ok=True)
    fd, name = tempfile.mkstemp(prefix=f"{app}-{time.time_ns()}-", dir=directory)
    with os.fdopen(fd, "wb") as stream:
        stream.write(raw)
    print(f"Previous settings: {name}")


def main():
    sources = load_sources()
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["status", "export", "apply"])
    parser.add_argument("app", choices=sources)
    parser.add_argument("--machine", choices=["machine-1", "machine-2"])
    args = parser.parse_args()
    definition = sources[args.app]
    if "macos_versions" in definition:
        version = platform.mac_ver()[0]
        major = int(version.split(".")[0]) if version else None
        if major not in definition["macos_versions"]:
            parser.error(
                f"{args.app} is verified only for macOS {definition['macos_versions']}"
            )
    if "machines" in definition:
        machine = args.machine
        if not machine and (ROOT / ".machine").is_file():
            machine = (ROOT / ".machine").read_text().strip()
        if machine not in definition["machines"]:
            allowed = ", ".join(definition["machines"])
            parser.error(f"{args.app} requires {allowed} (.machine or --machine)")

    backend = definition["backend"]
    if backend not in {"defaults", "json", "plist"}:
        raise ValueError(f"Unsupported settings backend: {backend}")
    source_path = relative_path(ROOT, definition["source"])
    source = (
        plistlib.loads(source_path.read_bytes())
        if backend == "plist"
        else json.loads(source_path.read_text())
    )
    if backend == "defaults":
        validate_defaults(source, definition)
        result = subprocess.run(
            defaults_command(definition, "export", "-"),
            capture_output=True,
            check=False,
        )
        if result.returncode:
            raise ValueError(f"Preferences unavailable for {args.app}")
        raw = result.stdout
        live = plistlib.loads(raw)
        if not isinstance(live, dict):
            raise TypeError(f"Expected a preference dictionary for {args.app}")
        # Keep the complete domain for backups and for preserving local list members.
        original_live = live
        live = owned_view(live, definition)
    else:
        target = relative_path(Path.home(), definition["target"])
        raw = target.read_bytes() if target.exists() else b""
        if args.action == "export" and not raw:
            raise ValueError(
                f"Cannot export {args.app}: live {backend} file is missing or empty: {target}"
            )
        live = (
            plistlib.loads(raw)
            if backend == "plist" and raw
            else jsonc(raw.decode())
            if raw
            else {}
        )

    different = (
        [k for k in source if selected(live, {k: source[k]}) != {k: source[k]}]
        if backend != "plist"
        else ([] if live == source else ["contents"])
    )
    if args.action == "status":
        print(f"{args.app}: " + (", ".join(different) if different else "in sync"))
        return
    if args.action == "export":
        result = live if backend == "plist" else selected(live, source)
        missing = missing_owned(live, source) if backend != "plist" else []
        if missing:
            raise ValueError(
                f"Missing owned keys; review before removing: {sorted(missing)}"
            )
        data = (
            plistlib.dumps(result)
            if backend == "plist"
            else (json.dumps(result, indent=2, sort_keys=True) + "\n").encode()
        )
        atomic_write(source_path, data)
        print(f"Exported {args.app}; review git diff")
        return

    if backend == "defaults":
        if not different:
            print(f"{args.app}: in sync")
            return
        backup(args.app, raw)
        for key in different:
            subprocess.run(
                defaults_command(
                    definition,
                    "write",
                    key,
                    *defaults_args(
                        value_to_apply(key, source[key], original_live, definition)
                    ),
                ),
                check=True,
            )
    else:
        result = source if backend == "plist" else merged(live, source)
        if result == live:
            print(f"{args.app}: in sync")
            return
        backup(args.app, raw)
        data = (
            plistlib.dumps(result)
            if backend == "plist"
            else (json.dumps(result, indent=2) + "\n").encode()
        )
        atomic_write(target, data)
    print(f"Applied {args.app}; relaunch apps or sign out/in if needed")


if __name__ == "__main__":
    try:
        main()
    except (OSError, ValueError, TypeError, subprocess.CalledProcessError) as error:
        raise SystemExit(str(error)) from error
