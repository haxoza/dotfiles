# SSH

Both machines support 1Password SSH agent keys and encrypted keys on disk.
Choose the key source per host in the private
`ssh/config.local`. Both wrappers select the 1Password agent; machine-2 also
keeps macOS Keychain passphrase lookup for its local keys.

`./install` uses the root `.machine` file to link the corresponding
`ssh/config.machine-*` as `~/.ssh/config` and `ssh/agent.machine-*` as the
1Password `agent.toml`. Both wrappers include `~/.ssh/config.local`, linked to
`ssh/config.local` and restored from that machine's 1Password Document:

```bash
./1password/sync.py restore --only ssh/config.local
./install
```

Skip the restore if the file already exists; sync will not overwrite it.
An existing regular `agent.toml` is preserved beside the new link as
`agent.toml.dotbot-backup.<timestamp>`.

## Choosing a key for a host

Put specific `Host` blocks in `config.local`, before the wrapper's `Host *`
defaults:

- **1Password key:** Store the private key as a native SSH Key item and enable
  the SSH agent. To restrict a host to one key, download its public key to
  `~/.ssh/` and set `IdentityFile` to that `.pub` file with `IdentitiesOnly yes`.
  `agent.machine-1` lists machine-1's active keys. `agent.machine-2` is empty for
  now, so its 1Password agent offers no keys until entries are added. On
  machine-2, set `UseKeychain no` for 1Password-only hosts.
- **Local encrypted key:** Set `IdentityFile` to the private key in `~/.ssh/`,
  `IdentitiesOnly yes`, `IdentityAgent SSH_AUTH_SOCK`, `UseKeychain yes`, and
  `AddKeysToAgent yes` for that host. This selects the agent named by
  `SSH_AUTH_SOCK` (normally the macOS agent) instead of the wrapper's 1Password
  socket, and lets Keychain unlock the key when SSH needs to add it to the agent.

There is no managed `~/.ssh/identities` link. The old public-key Documents remain
in 1Password but are not part of routine sync. Keep private keys and passphrases
out of the repo. For recovery on either machine, encrypted key Documents can be
mapped under `recovery_files` in [`machines.yaml`](../1password/machines.yaml); they are
never restored by routine sync. Keychain access for unattended jobs depends on
the login and unlock state, so verify those jobs after a reboot.

Check a host's settings with `ssh -G <host>`. Run offline tests with:

```bash
python3 -B -m unittest discover -s ssh -p 'test_*.py'
```

## Git signing with a local SSH key

Use a dedicated encrypted Ed25519 key per machine and register its public key
on GitHub as a **Signing key**, independently of SSH authentication keys.
Save its passphrase once using Apple's binary:

```bash
/usr/bin/ssh-add --apple-use-keychain ~/.ssh/git-signing-MACHINE
```

Configure the gitignored `git/gitconfig.local.symlink` on that machine:

```gitconfig
[user]
    email = YOUR_EMAIL
    signingkey = /ABSOLUTE/HOME/.ssh/git-signing-MACHINE.pub
[gpg]
    format = ssh
[gpg "ssh"]
    program = /ABSOLUTE/DOTFILES/git/ssh-sign.sh
    allowedSignersFile = /ABSOLUTE/DOTFILES/git/allowed_signers.local
```

Create the gitignored allowed-signers file with your email, `namespaces="git"`,
and the public key's type and base64 data on one line. Shared Git settings
already enable commit signing. Update absolute paths if the checkout moves.

`git/ssh-sign.sh` loads the signing key from Keychain on demand, then calls
Apple's `ssh-keygen`. Git signing does not read `~/.ssh/config`, so no SSH host
block is needed. The helper requires the standard agent via `SSH_AUTH_SOCK`
and an accessible login Keychain; it fails without prompting if the key cannot
be unlocked. Test after logout/reboot too.

Sync the per-machine Git config to 1Password after testing. Routine sync excludes
the private key and allowed-signers file. Use a separate key and local config
on the second machine.

Machine-1's encrypted key backup is listed under `recovery_files` in
[`machines.yaml`](../1password/machines.yaml), with the manual recovery path
`ssh/keys.local/git-signing-machine-1`. To recover, download it and install with
mode `0600` at the `user.signingkey` path without `.pub`. Regenerate the public
key with `ssh-keygen -y`, recreate the allowed-signers entry, and save the
passphrase in Keychain. The Document backs up the encrypted key, not its passphrase.
