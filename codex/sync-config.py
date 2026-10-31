# /// script
# requires-python = ">=3.11"
# dependencies = ["tomlkit==0.13.3"]
# ///
"""Merge app-writable Codex config, export to owners, or report drift.

Most keys own their entire value. Only tui and desktop split ownership by
immediate child, so portable preferences and app state can share those tables.
Unknown live keys pass through; reserved private keys export only to local.
"""

import argparse
import os
import sys
import tempfile
from collections.abc import Mapping
from copy import deepcopy
from datetime import UTC, datetime
from pathlib import Path

import tomlkit
from tomlkit.exceptions import ParseError

SPLIT_TABLES = {"tui", "desktop"}
APP_KEYS = {"model"}
LOCAL_KEYS = {
    "projects",
    "mcp_servers",
    "hooks",
    "notify",
    "marketplaces",
    "model_providers",
    "model_instructions_file",
}
LOCAL_TUI_KEYS = {"screen_reader_detection_done", "model_availability_nux"}
MISSING = object()


class ConfigError(Exception):
    pass


def read(path, optional=False):
    if not path.exists() and not path.is_symlink() and optional:
        return tomlkit.document(), None
    try:
        raw = path.read_bytes()
        doc = tomlkit.parse(raw.decode("utf-8"))
    except (ParseError, UnicodeError):
        # Parser errors can contain private keys or values. Never echo them.
        raise ConfigError(f"invalid TOML in {path.name}; file left untouched") from None
    except OSError:
        raise ConfigError(f"cannot read {path.name}; file left untouched") from None
    for key in SPLIT_TABLES & doc.keys():
        if not isinstance(doc[key], Mapping):
            raise ConfigError(f"{path.name}: {key} must be a table")
    return doc, raw


def items(doc):
    for key, value in doc.items():
        if key in SPLIT_TABLES:
            for child, child_value in value.items():
                yield (key, child), child_value
        else:
            yield (key,), value


def get(doc, path):
    value = doc
    for key in path:
        if not isinstance(value, Mapping) or key not in value:
            return MISSING
        value = value[key]
    return value


def put(doc, path, value):
    if isinstance(value, Mapping):
        # Rebuild the containing root table from plain values. Reusing dotted
        # key metadata can duplicate prefixes or put a header before root keys,
        # changing their scope. Preserve siblings when replacing a split field.
        replacement = value.unwrap()
        if len(path) == 2:
            siblings = doc[path[0]].unwrap() if path[0] in doc else {}
            replacement = {**siblings, path[1]: replacement}
        if path[0] in doc:
            del doc[path[0]]
        doc[path[0]] = tomlkit.item(replacement)
        return
    if len(path) == 2:
        if path[0] not in doc:
            doc[path[0]] = tomlkit.table()
        doc[path[0]][path[1]] = deepcopy(value)
    else:
        doc[path[0]] = deepcopy(value)


def remove(doc, path):
    if len(path) == 2:
        del doc[path[0]][path[1]]
        if not doc[path[0]]:
            del doc[path[0]]
    else:
        del doc[path[0]]


def is_private(path):
    return path[0] in LOCAL_KEYS or (path[0] == "tui" and path[1] in LOCAL_TUI_KEYS)


def ownership(sources):
    owners = {}
    for index, (file, doc, _) in enumerate(sources):
        for path, _ in items(doc):
            if path[0] in APP_KEYS:
                raise ConfigError(
                    f"{file.name}: model is app-owned; remove it from sources"
                )
            if is_private(path) and index != 2:
                raise ConfigError(
                    f"{file.name}: private settings belong in trusted.local.toml"
                )
            if path[0] == "plugins" and index != 1:
                raise ConfigError(
                    f"{file.name}: plugins belong in the selected machine file"
                )
            if path in owners:
                raise ConfigError(
                    f"duplicate ownership in {sources[owners[path]][0].name} and {file.name}"
                )
            owners[path] = index
    return owners


def serialized(doc):
    text = tomlkit.dumps(doc)
    # Valid TOML can still encode the wrong nesting. Check both syntax and the
    # intended mapping before any mutation, including exports.
    try:
        reparsed = tomlkit.parse(text)
    except ParseError:
        raise ConfigError("cannot serialize valid TOML; no files written") from None
    if reparsed.unwrap() != doc.unwrap():
        raise ConfigError("serialization changed the TOML mapping; no files written")
    return text.encode("utf-8")


def unchanged(path, expected):
    current = path.read_bytes() if path.exists() else None
    if current != expected:
        raise ConfigError(
            f"{path.name} changed during sync; retry after app writes finish"
        )


def write(path, raw, before, *, live=False, private=False):
    if before == raw and not path.is_symlink():
        return False
    path.parent.mkdir(parents=True, exist_ok=True, mode=0o700)
    unchanged(path, before)
    fd, tmp = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "wb") as stream:
            stream.write(raw)
            stream.flush()
            os.fsync(stream.fileno())
        os.chmod(tmp, 0o600 if private or live else 0o644)
        if live and before is not None:
            stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S-%f")
            backup_fd, _ = tempfile.mkstemp(
                prefix=f"{path.name}.{stamp}.", suffix=".bak", dir=path.parent
            )
            # Copy the contents through an old symlink, never the link itself.
            # mkstemp makes a unique, private backup and leaves older backups alone.
            with os.fdopen(backup_fd, "wb") as backup:
                backup.write(before)
                backup.flush()
                os.fsync(backup.fileno())
        unchanged(path, before)
        os.replace(tmp, path)
    finally:
        if os.path.exists(tmp):
            os.unlink(tmp)
    return True


def report(sources, live, owners):
    for index, (file, doc, _) in enumerate(sources):
        drift = [path for path, value in items(doc) if get(live, path) != value]
        if index == 2:
            # Include private app additions not present in this checkout's source.
            additions = [
                path
                for path, _ in items(live)
                if is_private(path) and path not in owners
            ]
            detail = f"{len(drift)} changed, {len(additions)} live-only (values hidden)"
        else:
            detail = ", ".join(".".join(path) for path in drift) or "none"
        print(f"drifted owned keys ({file.name}; merge resets, export pulls): {detail}")
    unowned = [
        ".".join(path)
        for path, _ in items(live)
        if path not in owners and not is_private(path) and path[0] not in APP_KEYS
    ]
    print(
        "unowned live keys (pass through, never exported): "
        + (", ".join(unowned) or "none")
    )
    print("app-owned keys (pass through, never exported): model")


def sync(command):
    script_dir = Path(__file__).resolve().parent
    source_dir = Path(os.environ.get("CODEX_CONFIG_SOURCE_DIR", script_dir))
    machine = os.environ.get("DOTFILES_MACHINE")
    if not machine:
        machine_file = source_dir.parent / ".machine"
        machine = machine_file.read_text().strip() if machine_file.exists() else None
    if machine not in {"machine-1", "machine-2"}:
        raise ConfigError(
            "DOTFILES_MACHINE or repository .machine must select machine-1 or machine-2"
        )
    live_path = Path(
        os.environ.get(
            "CODEX_CONFIG_LIVE_FILE",
            str(
                Path(os.environ.get("CODEX_HOME", Path.home() / ".codex"))
                / "config.toml"
            ),
        )
    )
    paths = [
        source_dir / "common.toml",
        source_dir / f"config.{machine}.toml",
        source_dir / "trusted.local.toml",
    ]
    sources = []
    for index, path in enumerate(paths):
        if path.is_symlink():
            raise ConfigError(f"source {path.name} must be a regular file")
        doc, raw = read(path, optional=index == 2)
        sources.append((path, doc, raw))
    owners = ownership(sources)
    live, live_raw = read(live_path, optional=True)
    if command == "status":
        print(
            f"machine: {machine}; live: {'symlink (merge migrates)' if live_path.is_symlink() else 'regular file' if live_raw is not None else 'missing'}"
        )
        report(sources, live, owners)
        return
    if command == "merge":
        merged = deepcopy(live)
        for _, doc, _ in sources:
            for path, value in items(doc):
                if get(merged, path) != value:
                    put(merged, path, value)
        # Semantic no-ops retain the app's formatting and avoid extra backups.
        raw = (
            live_raw if merged == live and live_raw is not None else serialized(merged)
        )
        changed = write(live_path, raw, live_raw, live=True)
        print(
            "sync-config: updated live config (previous contents backed up when present)"
            if changed
            else "sync-config: live config already up to date"
        )
        return
    if live_raw is None:
        raise ConfigError("live config missing; nothing to export")
    exported = [deepcopy(doc) for _, doc, _ in sources]
    for path, index in owners.items():
        value = get(live, path)
        if value is MISSING:
            if isinstance(get(exported[index], path), Mapping):
                # Keep table ownership, including an intentionally empty plugin map.
                put(exported[index], path, tomlkit.table())
            else:
                remove(exported[index], path)
        elif get(exported[index], path) != value:
            if index != 2:
                # Don't import live comments that might mention private paths.
                value = tomlkit.item(
                    value.unwrap() if hasattr(value, "unwrap") else value
                )
            put(exported[index], path, value)
    for path, value in items(live):
        if is_private(path) and path not in owners:
            put(exported[2], path, value)
    pending = []
    for (file, doc, raw), updated in zip(sources, exported):
        # TOMLKit documents inherit dict.__ne__, which can disagree with __eq__
        # for nested tables. Compare plain values to detect semantic no-ops.
        if updated.unwrap() != doc.unwrap():
            pending.append((file, serialized(updated), raw))
    # Check all inputs again before starting an export; never write through live.
    unchanged(live_path, live_raw)
    for file, _, raw in sources:
        unchanged(file, raw)
    changed = False
    for file, raw, before in pending:
        if write(file, raw, before, private=file == paths[2]):
            changed = True
            print(f"sync-config: updated {file.name}; review source changes")
    if not changed:
        print("sync-config: sources already match live owned values")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("command", choices=("merge", "export", "status"))
    args = parser.parse_args()
    try:
        sync(args.command)
    except (ConfigError, OSError) as error:
        print(
            f"sync-config: {error if isinstance(error, ConfigError) else 'filesystem operation failed; no private details logged'}",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
