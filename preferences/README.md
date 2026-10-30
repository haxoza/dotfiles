# Preferences

`sync.py` keeps selected settings in Git. Nothing is applied automatically.

| Source | Scope | Tracked settings |
| --- | --- | --- |
| `stats` | Both Macs | Widgets, appearance, intervals and telemetry; hardware sensors, identities and screen positions stay local |
| `vscode` | Both Macs | Selected editor/Python settings; unowned values are preserved |
| `choosy` | machine-1 | Complete browser-selection rules |
| `macos` | Both Macs | Key repeat, repeat delay, preferred languages, locale and filename extensions |
| `text-input` | Both Macs | Smart punctuation, autocorrect, capitalization, predictions and double-space period |
| `finder` | Both Macs | Current-folder search, view style, path/status bars and new-window target |
| `desktop` | Both Macs | Dock size, magnification, auto-hide, recent apps and Mission Control grouping by app |
| `spotlight` | macOS 26 | Selected system-result rules and related-content choice; app rules and local state stay local |

iTerm is separate: Dotbot installs `iterm2/Profiles.symlink.json` as the `Dotfiles`
dynamic profile. Select it in iTerm when ready; it requires the Meslo Nerd Font.

## Sync between machines

Run from the repository root; replace `macos` with another source as needed:

```bash
# On the Mac where you changed settings:
python3 preferences/sync.py status macos
python3 preferences/sync.py export macos
git diff -- macos/settings.json
# Review, commit and push the desired changes.

# On the other Mac, pull those changes, then:
python3 preferences/sync.py status macos
python3 preferences/sync.py apply macos
```

You can also edit the tracked source directly and apply it on each Mac. Export
deliberate local changes before pulling; reconcile Git conflicts before applying.
Avoid automatic two-way exports, which could overwrite the other Mac's choices.

- `status` reports differing key names. `export` reads only keys already present
  in the source; missing keys stop export for review. Choosy exports all rules.
- `apply` backs up previous settings to gitignored `preferences/backups.local/`
  (mode 0600), then changes only owned keys; Choosy replaces its rules file.
- Close affected apps before applying. VS Code accepts JSONC but rewrites it as
  plain JSON; comments/formatting survive in the backup. Relaunch apps afterward.
- Choosy uses `.machine`, or pass `--machine machine-1`. Machine-2 is rejected.

## Add a source

Add an entry to [sources.json](sources.json) and create its source file:

```json
{
  "example": {
    "source": "example/settings.json",
    "backend": "defaults",
    "domain": "com.example.app"
  }
}
```

Choose `defaults` (typed per-key writes to a domain), `json` (recursive merge into
a home-relative `target`) or `plist` (whole-file replacement at a home-relative
`target`). Source paths are repo-relative. Optional `machines` limits scope;
`key_filter` restricts allowed keys with `include`, `prefixes` and `exclude`.
`list_items` manages only specified members of a string-list setting, preserving
other members on each Mac. `macos_versions` limits a source to verified OS majors.
Adding an app with an existing backend needs no Python changes. Seed its source
with only the keys you want to own, then export the current values and review.

## macOS notes

`macos/settings.json` starts with this Mac's explicit values. Press-and-hold was
unset and remains unmanaged; add `ApplePressAndHoldEnabled` deliberately if you
want to own that choice. Keyboard layouts, per-device mappings and login-window
language remain outside this baseline. Key names can change between macOS versions.

The new sources preserve current choices, except `desktop` explicitly enables
grouping windows by app, as recommended by [AeroSpace](https://nikitabobko.github.io/AeroSpace/guide#42-a-note-on-mission-control).
Spotlight uses macOS 26's `EnabledPreferenceRules`; legacy `orderedItems` and
`DisabledUTTypes` are left alone. Only configured system rules are managed.
App rules, iPhone integration, exclusions, indexes and history stay local; the
clipboard toggle and keyboard shortcut aren't managed in this pass. Verify the
Spotlight UI after applying; another OS major needs its rule format checked first.
Lock Screen, monitor/Spaces layout and screenshot defaults remain unmanaged.

The helper uses [`defaults`](https://developer.apple.com/documentation/foundation/userdefaults),
not whole-file global preference restores. Language changes may need app restarts,
signing out/in or a restart to reach the whole desktop. See
[Apple's language guidance](https://support.apple.com/en-gb/guide/mac-help/-mh26684/mac).
Use [iCloud Siri sync](https://support.apple.com/en-gb/guide/icloud/mm155e8d9577/icloud)
for Siri; use Time Machine/Migration Assistant for full recovery.

Verify UI behavior on both Macs after applying. Old Mackup snapshots remain in
Git history; the package and evaluation workflow have been removed.

## Checks

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s preferences -p 'test_*.py'
```
