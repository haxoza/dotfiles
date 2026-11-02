# AeroSpace

Each machine has a complete config:

- `aerospace.machine-1.toml`
- `aerospace.machine-2.toml`

`./install` uses the repository's `.machine` selector to link the matching file
to `~/.aerospace.toml`. Edit that profile directly; AeroSpace reloads it
automatically. There is no generation step.

Only these sections may differ:

- `[workspace-to-monitor-force-assignment]`: workspace-to-monitor mapping.
- `[gaps]`: spacing for each display setup.
- `persistent-workspaces` and the corresponding numbered workspace/move bindings.
- The `[[on-window-detected]]` callbacks below `# Machine-specific app placement.`:
  app matching and placement when a window is detected. Callback order matters.

Keep everything else identical, including directional and service keybindings,
layout defaults, and the shared floating-window rules for Finder dialogs,
Slack huddles, and Zoom. Apply shared changes to both files.

Review differences with:

```bash
diff -u aerospace/aerospace.machine-{1,2}.toml
```
