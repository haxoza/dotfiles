# SSH

Both machines are intended to use a mix of 1Password SSH agent keys and
passphrase-encrypted keys on disk. Choose the key source per host in the private
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

Check a host's effective settings with `ssh -G <host>`. Offline tests avoid
Python bytecode and do not connect to SSH hosts:

```bash
python3 -B -m unittest discover -s ssh -p 'test_*.py'
```
