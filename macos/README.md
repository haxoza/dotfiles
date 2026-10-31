# Captured macOS preferences

Use `preferences/sync.py status|export|apply SOURCE` explicitly. This capture
made no live preference changes, restarted no services and ran no installer.
It was inspected on macOS 26.7.1. Close System Settings before a future apply;
some settings may require signing out/in to be activated by the session.

## Keyboard navigation and Finder

`settings.json` owns `AppleKeyboardUIMode: 3`. The current value is `3` and
Keyboard navigation was verified ON in System Settings. Preserve it as-is;
don't normalize it to `2` based on examples for another macOS version.

`finder.json` adds only explicit live choices: external and removable drives
shown on the desktop, internal disks hidden, hidden files hidden. Mounted-server
visibility was unset and remains unmanaged. No paths, sidebar locations or
transient window state were adopted.

## Selected keyboard shortcuts

`shortcuts.json` owns only these `enabled: false` leaves under
`AppleSymbolicHotKeys` in `com.apple.symbolichotkeys`:

| ID | Meaning | Existing shortcut | Why preserve the override |
| --- | --- | --- | --- |
| 60 | Select the previous input source | Control-Space | Explicitly disabled; this is not Spotlight |
| 79 | Move to previous native Space | Control-Left | Disabled; AeroSpace owns Control-Left for its workspaces |
| 81 | Move to next native Space | Control-Right | Disabled; AeroSpace owns Control-Right for its workspaces |
| 118 | Switch to native Space 1 | Control-1 | Explicitly disabled; AeroSpace uses its own workspace model |
| 119 | Switch to native Space 2 | Control-2 | Same |
| 120 | Switch to native Space 3 | Control-3 | Same |
| 121 | Switch to native Space 4 | Control-4 | Same |

Meanings and keycodes were checked against Apple's installed resource tables:

```text
/System/Library/ExtensionKit/Extensions/KeyboardSettings.appex/Contents/Resources/en_GB.lproj/DefaultShortcutsTable.xml
/System/Library/ExtensionKit/Extensions/KeyboardSettings.appex/Contents/Resources/DefaultSpacesShortcuts.xml
```

The first table maps `sybmolichotkey` (Apple's spelling) to each action; the
second identifies native Space numbers. Stored arrow bindings additionally
contain the Function event flag. Binding parameters, including those flags,
remain unowned and aren't normalized or copied to another keyboard.

Spotlight ID 64 (Show Spotlight search, Command-Space) and ID 65 (Show Finder
search window, Option-Command-Space) have no explicit live entries. They remain
unmanaged, along with the absent ID 61 input-source shortcut. IDs 80/82 are the
enabled slow variants of native Space navigation and remain untouched. ID 164
is disabled but wasn't identified in these tables, so it is deliberately omitted.

Apply reads the current domain, recursively merges only owned leaves, and writes
the merged `AppleSymbolicHotKeys` value as one typed XML plist value through
`defaults write DOMAIN KEY VALUE`. It never imports/replaces the whole domain.
Other shortcut IDs, fields inside owned IDs and top-level keys survive. Export
projects only the selected `enabled` leaves. Missing leaves or malformed live
data stop export without modifying the tracked source.

Nested write persistence and type preservation were verified against a synthetic
temporary preference domain, not live shortcuts. Runtime shortcut activation
wasn't changed/tested. On machine-2, check these rows in System Settings >
Keyboard > Keyboard Shortcuts before/after an explicit apply, then check input
switching, Spotlight and AeroSpace. The source is restricted to macOS 26 until
the resource mapping and activation behavior are verified for another OS major.

## Trackpad profiles

These are separate opt-in profiles, not an assumption that the Macs have the
same pointing devices. A preference domain can exist for previously used
hardware; its existence doesn't prove that device is currently attached.

| Source | Domain/scope | Current explicit values |
| --- | --- | --- |
| `trackpad-built-in` | `com.apple.AppleMultitouchTrackpad` | `Clicking=true`, `TrackpadRightClick=true`, corner-secondary-click mode `0`, `Dragging=0`, `DragLock=0`, three-finger drag `false` |
| `trackpad-bluetooth` | `com.apple.driver.AppleBluetoothMultitouch.trackpad` | Same behavior; `Dragging`/`DragLock` are stored as booleans `false` |
| `trackpad-host` | `NSGlobalDomain`, current host | `com.apple.mouse.tapBehavior=1` |

The original value types are preserved. Host scope is addressed symbolically
with `-currentHost`; no host UUID, Bluetooth address, device ID, tracking speed,
pressure threshold or gesture-calibration state is recorded.

On machine-2, identify the actual built-in/Apple Bluetooth trackpad and inspect
its matching source with `status`. Apply only that hardware profile and, where
appropriate, the host tap setting. Check tap-to-click, two-finger secondary
click, click-and-drag and disabled three-finger dragging in Trackpad and
Accessibility > Pointer Control > Trackpad Options. Missing keys/devices need
manual review, not invented defaults. Add an explicit machine-scoped source if
the second Mac needs different behavior. Don't apply Apple profiles to a
third-party mouse or trackpad solely because its name contains “trackpad”.

References: [Apple gestures](https://support.apple.com/en-ie/102482),
[three-finger drag](https://support.apple.com/en-za/102341), and
[nix-darwin's trackpad option definitions](https://github.com/nix-darwin/nix-darwin/blob/master/modules/system/defaults/trackpad.nix).

Screenshot preferences, Ghostty, new CLI configuration and VS Code keybindings/
snippets are outside this change. Zed settings/keymap and registry declarations
are described in [zed/README.md](../zed/README.md).
