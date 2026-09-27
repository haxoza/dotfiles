# Codex configuration

`config.toml` is generated from the tracked `common.toml` and gitignored
`trusted.local.toml`. Keep portable preferences in `common.toml`; keep project
trust, absolute paths, hook trust, and other machine-specific values in
`trusted.local.toml`.

The Codex app may write new settings to `config.toml`. Before running
`generate-config.sh` or `./install`, reconcile those changes into the source
files. The generator creates a timestamped `config.toml.*.bak` first.

`dev-update` runs `clear-homebrew-quarantine.sh` after `brew upgrade`. Homebrew
quarantines each new Codex CLI binary, which can make macOS ask for first-open
approval again. The script checks that `/opt/homebrew/bin/codex` points into the
Codex cask and verifies its OpenAI code signature before removing the quarantine
attribute from that binary only. This skips macOS's first-launch Gatekeeper check
for that Codex binary; Homebrew still verifies the cask download checksum.
