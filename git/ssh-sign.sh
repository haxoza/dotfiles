#!/usr/bin/env bash
set -e

# Git's SSH signer does not read ~/.ssh/config. Load only the requested signing
# key from macOS Keychain when necessary; verification never loads keys.
operation=
key=
previous=
for argument in "$@"; do
    case "$previous" in
        -Y) operation="$argument" ;;
        -f) key="$argument" ;;
    esac
    previous="$argument"
done

if [[ "$operation" == sign && "$key" == *.pub ]]; then
    if ! /usr/bin/ssh-add -T "$key" >/dev/null 2>&1; then
        # Fail instead of prompting an unattended caller if Keychain cannot
        # unlock the key. Seed Keychain interactively with --apple-use-keychain.
        if ! SSH_ASKPASS_REQUIRE=force SSH_ASKPASS=/usr/bin/false \
            DISPLAY=dotfiles /usr/bin/ssh-add -q --apple-use-keychain "${key%.pub}"; then
            echo "Cannot load signing key. Run /usr/bin/ssh-add --apple-use-keychain with its private-key path in a terminal." >&2
            exit 1
        fi
    fi
fi

exec /usr/bin/ssh-keygen "$@"
