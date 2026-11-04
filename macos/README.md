# macOS preferences

These profiles are opt-in. Use the [preferences workflow](../preferences/README.md#sync-between-machines)
to inspect, export or apply a source. Close System Settings before applying;
some changes require signing out and back in. Applies create local backups and
preserve unowned settings.

The JSON files define the managed values; [sources.json](../preferences/sources.json)
defines their domains, hardware scopes and supported macOS versions.

## Keyboard and shortcuts

Keep `AppleKeyboardUIMode: 3` in `settings.json`: it represents the captured
Keyboard navigation setting. Don't normalize it to `2` from other examples.

`shortcuts.json` disables previous-input-source switching (Control-Space) and
selected native Spaces shortcuts, freeing Control-Left/Right for AeroSpace.
Only selected `enabled` flags are managed; binding parameters and all other
shortcuts, including Spotlight, remain untouched.

Shortcut mappings were checked against Apple's installed KeyboardSettings
resource tables on macOS 26 and 27. After applying, verify input switching and
AeroSpace navigation in your session. The separate Spotlight profile supports
macOS 26 only.

## Trackpads

Apply only the profile matching an attached Apple trackpad. A stored preference
domain doesn't prove the device is present. The built-in and Bluetooth profiles
are separate; `trackpad-host` is an additional opt-in for host-scoped tap behavior.
They do not configure Logitech devices.

After applying, check tap-to-click, secondary click and dragging in System
Settings. Missing keys or different hardware need review before applying.

## Pointer speed

`pointer.json` captures mouse and trackpad tracking speeds separately in
`NSGlobalDomain`. Inspect with `python3 preferences/sync.py status pointer`,
export deliberate local changes with `export pointer`, and opt in on another Mac
with `apply pointer`. These are native preference values, not percentages.
Check the feel on each Mac after applying; mouse hardware and vendor software
may affect the result. Natural scrolling, acceleration and double-click speed
remain unmanaged.
