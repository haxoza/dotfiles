# Preferences

`sync.py` keeps selected settings in Git. Nothing is applied automatically.

| Source | Scope | Tracked settings |
| --- | --- | --- |
| `stats` | Both Macs | Widgets, appearance, intervals and telemetry; hardware sensors, identities and screen positions stay local |
| `vscode` | Both Macs | Selected editor/Python settings; unowned values are preserved |
| `zed` | Both Macs | Vim, theme/fonts, telemetry and deliberate editor/panel/tab behavior |
| `zed-agents` | Both Macs | Registry declarations only; commands, environment and authentication stay local |
| `choosy` | machine-1 | Complete browser-selection rules |
| `macos` | Both Macs | Key repeat, keyboard navigation, preferred languages, locale and filename extensions |
| `text-input` | Both Macs | Smart punctuation, autocorrect, capitalization, predictions and double-space period |
| `finder` | Both Macs | Search/view behavior, path/status bars, desktop drives and hidden-file visibility |
| `desktop` | Both Macs | Dock size, magnification, auto-hide, recent apps and Mission Control grouping by app |
| `spotlight` | macOS 26 | Selected system-result rules and related-content choice; app rules and local state stay local |
| `shortcuts` | macOS 26 | Seven verified, explicit disabled shortcuts; only selected `enabled` leaves are owned |
| `trackpad-built-in`, `trackpad-bluetooth` | Matching hardware only | Separate tap/secondary-click and dragging profiles; apply only the relevant one |
| `trackpad-host` | Opt-in, current host | Host-scoped tap behavior; no host/device identifiers are tracked |

iTerm is separate: Dotbot installs `iterm2/Profiles.symlink.json` as the `Dotfiles`
dynamic profile. Select it in iTerm when ready; it requires the Meslo Nerd Font.
Zed's array-based keymap is also [Dotbot-managed](../zed/README.md), with backup
enabled for an existing file.

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

- `status` reports differing key names. `export` reads only owned leaves; missing
  keys or missing/invalid files stop export without changing the source. Choosy
  exports all rules.
- `apply` backs up previous settings to gitignored `preferences/backups.local/`
  (mode 0600), then changes only owned keys; Choosy replaces its rules file.
- Close affected apps/System Settings before applying. JSON sources accept JSONC but rewrite it as
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
Nested defaults dictionaries merge recursively; sibling entries and unowned
fields survive, and exports include only source-owned leaves. `current_host`
uses `defaults -currentHost` for both reads and writes without recording a UUID.
The JSON backend requires objects; use a separate managed file for an entire array.
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

See [macOS capture notes](../macos/README.md) for shortcut identities, preserved
keyboard-navigation value `3`, trackpad hardware scopes and second-Mac checks.
See [Zed notes](../zed/README.md) for keymap ownership and agent-server boundaries.

The helper uses [`defaults`](https://developer.apple.com/documentation/foundation/userdefaults),
not whole-file global preference restores. Language changes may need app restarts,
signing out/in or a restart to reach the whole desktop. See
[Apple's language guidance](https://support.apple.com/en-gb/guide/mac-help/-mh26684/mac).
Use [iCloud Siri sync](https://support.apple.com/en-gb/guide/icloud/mm155e8d9577/icloud)
for Siri; use Time Machine/Migration Assistant for full recovery.

Verify UI behavior on both Macs after applying. Old Mackup snapshots remain in
Git history; the package and evaluation workflow have been removed.

## Worktree installation

Dotbot links resolve into the checkout used for installation. Keep a trial
worktree until those links have been reinstalled from the main worktree.
The Zed keymap and iTerm profile are links; merged settings and macOS defaults
contain copied values and don't depend on the checkout's path.

After the PR is merged, switch the main worktree to the default branch and
reinstall there (reconcile generated/app-written settings as required by
[AGENTS.md](../AGENTS.md) before running the full installer):

```bash
cd ~/dev/projects/dotfiles
git switch master
git pull --ff-only
./install
```

Verify `~/.config/zed/keymap.json` and
`~/Library/Application Support/iTerm2/DynamicProfiles/Dotfiles.json` resolve into
the main checkout before removing the trial worktree.

## Checks

```bash
PYTHONDONTWRITEBYTECODE=1 python3 -m unittest discover -s preferences -p 'test_*.py'
```
