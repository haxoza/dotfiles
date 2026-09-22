# Codex configuration

`config.toml` is generated from the tracked `common.toml` and gitignored
`trusted.local.toml`. Keep portable preferences in `common.toml`; keep project
trust, absolute paths, hook trust, and other machine-specific values in
`trusted.local.toml`.

The Codex app may write new settings to `config.toml`. Before running
`generate-config.sh` or `./install`, reconcile those changes into the source
files. The generator creates a timestamped `config.toml.*.bak` first.
