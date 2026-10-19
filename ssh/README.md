# SSH

`./install` requires the root `.machine` selector and links `~/.ssh/config` to
`config.machine-1` or `config.machine-2`. Dotbot expands the
validated `DOTFILES_MACHINE` environment variable exported by the installer.
Changing `.machine` does not replace private files or switch a running SSH agent.
Each checkout belongs to one machine.

On an existing installation, restore just the new SSH files without overwriting
other private settings:

```bash
./1password/sync.py restore --only ssh/config.local
./install
```

Skip a restore for files that already exist; the sync refuses to overwrite them.

Both configs include `~/.ssh/config.local`, linked to the gitignored
`ssh/config.local`. This file holds host aliases, hostnames, users,
proxy commands, and identities. Each machine's entry in
[`../1password/machines.yaml`](../1password/machines.yaml) restores its own
Document to that same repository path. Private host rules precede general
defaults because SSH usually uses the first matching value. `IdentityFile`
entries accumulate; keep identities in specific `Host` blocks where possible.

## machine-1: 1Password SSH agent

Private keys live in native SSH Key items in machine-1's vault. The installer
links `agent.machine-1` to `~/.config/1Password/ssh/agent.toml`, limiting
the agent to the active key items in that vault. Other keys can remain in
1Password without being offered by the agent. The SSH config uses the app's
macOS socket directly; it does not replace `SSH_AUTH_SOCK` for unrelated tools
or other machines.

1. Import existing keys into machine-1's vault as SSH Key items. Enter their
   existing passphrases in 1Password when prompted. Compare public fingerprints
   before migrating hosts; importing preserves the existing key pair.
2. Enable **Settings > Developer > Use the SSH agent** in 1Password.
3. Restore the private config, then run `./install`. No public key files are
   needed for the current setup. To require a particular 1Password key for a
   host later, download its public key from the SSH Key item and use that `.pub`
   file as `IdentityFile`, for example:

   ```sshconfig
   Host git-example
       HostName github.com
       User git
       IdentityFile ~/.ssh/id_example.pub
       IdentitiesOnly yes
   ```

4. Check the effective config with `ssh -G git-example`, then test a read-only
   Git operation from each terminal or IDE you use. Approve the requesting app
   in 1Password. Keep encrypted local private keys during the migration until
   the relevant hosts work through the 1Password agent.

The tracked wrapper sets `IdentityFile none` to suppress default private-key
files and `IdentitiesOnly no` to offer the keys from the 1Password agent. The
private config does not need global `IdentityFile` entries. Keep a host-specific
`.pub` entry only when an alias should require a particular key;
`IdentitiesOnly yes` restricts that host to its selected key. `UseKeychain no`
and `AddKeysToAgent no` avoid loading local keys by default. The old public-key
Documents remain in 1Password, but routine sync no longer restores them. No
`~/.ssh/identities` directory is needed; an occasional `.pub` file can live
directly under `~/.ssh`. Public keys are not secret, but they can reveal
identity metadata, so keep downloaded copies outside the repo.

1Password documents [agent configuration](https://www.1password.dev/ssh/agent/config),
[key import](https://www.1password.dev/ssh/manage-keys), and
[public-key identity selection](https://www.1password.dev/ssh/agent/advanced).

## machine-2: encrypted files and macOS Keychain

Keep the existing private key files in `~/.ssh`, with mode `0600`, and the
directory with mode `0700`. Its private config points to the private key files
as before. `UseKeychain yes` retrieves stored passphrases and
`AddKeysToAgent yes` loads keys into the standard OpenSSH agent.

Keep machine-2's encrypted key files backed up as Documents in its own vault.
For repository-managed recovery, use gitignored paths under
`ssh/keys.local/`, record each Document in that machine's `recovery_files`,
and recover them manually to `~/.ssh`. Recovery files are excluded from routine
`status`, `restore`, and `update`; don't upload machine-1's keys as machine-2's.
Keep passphrases in Keychain and a private 1Password item, outside the repo.

Verify outbound Git/SSH from the agent apps, a fresh remote SSH session, and
after a reboot. Keychain access depends on the login/unlock and execution context;
enabling passphrase storage does not guarantee operation before login.

## Mixing key sources later

Choose the identity source in a specific `Host` block in `config.local`, before
the tracked `Host *` defaults. For a local encrypted key on machine-1:

```sshconfig
Host local-key-example
    IdentityFile ~/.ssh/id_example
    IdentitiesOnly yes
    IdentityAgent none
    UseKeychain yes
    AddKeysToAgent no
```

`UseKeychain yes` lets macOS retrieve the passphrase; disabling the agent for
that host avoids offering 1Password keys. On machine-2, a host that uses a
1Password key can instead specify the 1Password `IdentityAgent`, a downloaded
public-key `IdentityFile`, and `IdentitiesOnly yes`. That host also needs
`UseKeychain no` and `AddKeysToAgent no` before the machine-wide defaults.
The 1Password agent may require interactive approval, so keep unattended hosts
on suitable local keys. Add a managed public-key directory only if actual
host-specific rules make it useful.

## Offline checks

Run the SSH config and installer tests without writing Python bytecode:

```bash
python3 -B -m unittest discover -s ssh -p 'test_*.py'
```

The tests use temporary configs and fake installer dependencies. They do not
connect to SSH hosts or read private keys.
