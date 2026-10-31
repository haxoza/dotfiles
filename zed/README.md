# Zed preferences

`preferences/sync.py status|export|apply zed` manages the keys present in
`settings.json`: Vim and base keymap, themes/icons, explicit font sizes/weight,
terminal font, telemetry, panel docks, tab/title-bar behavior, unified diffs,
CLI new-window behavior and the existing `disable_ai: true` choice. Unowned keys
and nested fields survive apply and are never adopted on export. UI/buffer font
families were unset and remain Zed defaults. The terminal's Meslo Nerd Font
must be installed separately (the shared Brewfile already includes it).

`zed-agents` is a separate source for the existing registry declarations:
`opencode`, `codex-acp` and `claude-acp`, each with `type: registry`. Inspection
found no commands, arguments, environment variables or credentials in those
entries. Only their `type` leaves are owned; future local paths, environment,
other agents and authentication remain app-owned. Registry installation and
agent sign-in still need verification on the second Mac. These declarations
don't enable AI or change Claude/Codex native configuration.
See [Zed's external-agent documentation](https://zed.dev/docs/ai/external-agents).

`keymap.symlink.json` owns the complete custom keymap array, including its empty
context blocks and the global `ctrl-alt-\`` terminal-focus binding. Dotbot
registers it at `~/.config/zed/keymap.json` with `create: true` and `backup: true`.
This deliberately bypasses the JSON-object merge backend; array order/context
semantics aren't suitable for recursive object merging.

Edit the tracked keymap, or edit through its installed link. If Zed replaces the
link with a regular file, reconcile that file into the tracked source before
reinstalling. Dotbot backs up an existing target before replacing it. Check the
binding on machine-2's keyboard layout before installing; the complete keymap
file is shared, not merged with additional local bindings.
See [Zed's keymap format](https://zed.dev/docs/key-bindings).

Close Zed before an explicit settings apply. JSONC comments/formatting are
normalized to JSON; the original file is saved in `preferences/backups.local/`.
Registry installation and sign-in are separate from settings capture/apply.
When testing from a worktree, follow the
[post-merge reinstall steps](../preferences/README.md#worktree-installation)
before removing that checkout.
