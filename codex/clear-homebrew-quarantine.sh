#!/usr/bin/env bash
set -e

prefix="${HOMEBREW_PREFIX:-/opt/homebrew}"
link="$prefix/bin/codex"

[[ -L "$link" ]] || exit 0
binary="$(readlink "$link")"
case "$binary" in
  "$prefix"/Caskroom/codex/*/bin/codex) ;;
  *)
    echo "Codex does not point to the expected Homebrew cask binary; quarantine was kept." >&2
    exit 1
    ;;
esac

/usr/bin/xattr -p com.apple.quarantine "$binary" >/dev/null 2>&1 || exit 0

if ! /usr/bin/codesign --verify --strict "$binary" 2>/dev/null; then
  echo "Codex signature verification failed; quarantine was kept." >&2
  exit 1
fi
signature="$(/usr/bin/codesign -dv --verbose=2 "$binary" 2>&1)"
if [[ "$signature" != *"TeamIdentifier=2DC432GLL2"* ]]; then
  echo "Codex signer changed; quarantine was kept." >&2
  exit 1
fi

/usr/bin/xattr -d com.apple.quarantine "$binary"
