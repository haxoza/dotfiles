# Private settings

`sync.py` manages manual 1Password snapshots of gitignored settings files.
Install Python 3 (available through Homebrew) and the `1password-cli` cask, then
unlock 1Password and enable its CLI integration. GnuPG and Git are also needed to
restore the signing key. YAML parsing uses PyYAML bundled with Dotbot; initialize
submodules with `git submodule update --init --recursive` after cloning.

Run from the repository root:

```bash
./1password/sync.py status
./1password/sync.py restore
./1password/sync.py update
./1password/sync.py restore-gpg
./1password/sync.py --machine machine-1 status
```

The script also works by full path from any directory. It selects the default
machine alias in `machines.yaml` unless you pass `--machine <alias>` before the
command. Every file command prints its selected alias. `status` compares bytes
and reports `unchanged`, `modified`, or `missing` locally. If a vault read fails,
it reports `unavailable` and exits unsuccessfully. No file contents appear unless
you add `--diff` to `status` or `update`; that option can print secrets to your
terminal. `update` previews the changed paths, asks once, uploads private
snapshots of modified local files, and downloads each Document to verify exact
byte equality. Before uploading, it checks that both local files and their vault
Documents still match the reviewed snapshots. Missing local files are not
uploaded. The commands do not run automatically.

`restore` downloads every Document into a private temporary directory before
writing anything. It refuses to overwrite any existing local file, creates
new files with mode `0600`, and removes files it created if a later local write
fails. Review paths, trust, and permissions before running `./install`.

The versioned `machines.yaml` maps machine aliases to vaults and routine files.
The aliases are intentionally neutral for public privacy; vault names in
1Password may be more meaningful. The alias-to-machine mapping is in secure note
`m35uopv2vqark6pcnuah5x4r5y`, in the same vault as shared GPG (`shared_gpg.vault_id`).
An alias with an empty `files` list reports that no files are configured and
makes no vault changes. `recovery_files` are recorded for manual recovery and
are never processed by `status`, `restore`, or `update`.

The account ID is in `machines.yaml`. Override it with `--account <account-id>`
**before** the command. For offline tests or a different map, pass
`--config <path>` before the command. Find IDs using
`op account list --format=json` (`account_uuid`) and
`op vault list --account <account-id> --format=json` (`id`). Document IDs
are read from the selected machine entry.

The generated `codex/config.toml` is not backed up in 1Password. Its sources are
`codex/common.toml` and `codex/trusted.local.toml`. Reconcile app-written changes
into those sources before regeneration; keep local generated backups.

After restoring settings, run `./1password/sync.py restore-gpg` to import the
shared signing key. It always reads the shared GPG vault in `machines.yaml`,
regardless of the selected machine alias. The expected fingerprint comes from
the configured vault field and must match `user.signingkey` in the local Git
config. Both attachments are checked in a temporary keyring before import. The
routine `update` command never changes the GPG item or its attachments. The GPG
passphrase is stored in the same vault item if prompted.
