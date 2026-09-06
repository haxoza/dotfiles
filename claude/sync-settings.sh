#!/usr/bin/env bash
# Keep ~/.claude/settings.json in sync with the tracked claude/settings.json
# without owning the whole file.
#
#   sync-settings.sh merge    overlay tracked keys onto the live file (run by ./install)
#   sync-settings.sh export   pull live values of tracked keys back into the repo
#   sync-settings.sh status   report drift, unowned keys and unrecognised hooks; writes nothing
#
# Ownership rule: a top-level key present in the tracked file is repo-owned and
# its tracked value replaces the live value wholesale. Keys only in the live
# file pass through untouched. Inside "hooks", a matcher group whose command
# matches one of VENDOR_HOOK_MARKERS is vendor-owned and passes through; every
# other group is repo-owned. To start tracking a key the app added, put it in
# the tracked file with any value and run export.
#
# Env overrides (used by the tests): CLAUDE_SETTINGS_LIVE_FILE, CLAUDE_SETTINGS_TRACKED_FILE
set -e

# jq regex fragments. A hook group matching any of these belongs to a third
# party that rewrites the live file itself, so merge keeps it and export drops it.
VENDOR_HOOK_MARKERS=(
  '\.orca/agent-hooks/'   # Orca terminal status hooks; Orca reinstalls them if missing
)

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
tracked="${CLAUDE_SETTINGS_TRACKED_FILE:-${script_dir}/settings.json}"
live="${CLAUDE_SETTINGS_LIVE_FILE:-${CLAUDE_CONFIG_DIR:-${HOME}/.claude}/settings.json}"
vendor_re="$(IFS='|'; printf '%s' "${VENDOR_HOOK_MARKERS[*]}")"

die() { printf 'sync-settings: %s\n' "$*" >&2; exit 1; }
note() { printf 'sync-settings: %s\n' "$*" >&2; }
usage() { printf 'usage: %s merge|export|status\n' "$(basename "$0")" >&2; exit 2; }

# A "group" below is one entry of a hooks event array: {matcher, hooks: [{type, command, ...}]}.
JQ_LIB='
def group_is_vendor($re): [.hooks[]?.command // ""] | any(test($re));
def nonempty_events: with_entries(select(.value | length > 0));
def vendor_hooks($re): (.hooks // {}) | map_values(map(select(group_is_vendor($re)))) | nonempty_events;
def repo_hooks($re):   (.hooks // {}) | map_values(map(select(group_is_vendor($re) | not))) | nonempty_events;
'

# Tracked keys overlaid on the live object; hooks get repo groups first, then vendor groups.
JQ_MERGE='
. as $live
| $live + ($tracked | del(.hooks))
| if ($tracked | has("hooks")) then
    ($live | vendor_hooks($re)) as $vendor
    | .hooks = ($tracked.hooks + ($vendor | with_entries(.value = (($tracked.hooks[.key] // []) + .value))))
  else . end
'

# Tracked file rebuilt from live values, in tracked key order, vendor groups stripped.
JQ_EXPORT='
. as $live
| reduce ($tracked | to_entries[]) as $e ({};
    if $e.key == "hooks" then
      if ($live | has("hooks")) then
        ($live | repo_hooks($re)) as $repo
        | .hooks = (($tracked.hooks | with_entries(select(.key as $k | $repo | has($k)))) + $repo)
      else . end
    elif ($live | has($e.key)) then .[$e.key] = $live[$e.key]
    else . end)
'

# {drifted: [key], unowned: [key], unrecognised: ["Event: cmd"]}
JQ_REPORT='
. as $live
| ($tracked.hooks // {} | nonempty_events) as $thooks
| {
    drifted: ([$tracked | to_entries[] | select(.key != "hooks") | .key as $k
               | select(($live | has($k) | not) or ($live[$k] != .value)) | $k]
              + (if ($tracked | has("hooks")) and (($live | repo_hooks($re)) != $thooks) then ["hooks"] else [] end)),
    unowned: [$live | keys_unsorted[] | select(. as $k | $tracked | has($k) | not)],
    unrecognised: [$live | repo_hooks($re) | to_entries[] | .key as $ev | .value[]
                   | select(. as $g | [($thooks[$ev] // [])[] | . == $g] | any | not)
                   | "\($ev): \([.hooks[]?.command // ""] | join(" ; ") | .[0:120])"]
  }
'

command -v jq >/dev/null 2>&1 || die "jq is required; install it from homebrew/Brewfile and rerun"

check_tracked() {
  [ -f "$tracked" ] || die "tracked file missing: $tracked"
  jq empty "$tracked" 2>/dev/null || die "tracked file is not valid JSON: $tracked"
  if jq -e --arg re "$vendor_re" "${JQ_LIB} vendor_hooks(\$re) | length > 0" "$tracked" >/dev/null; then
    die "tracked file contains vendor hook groups matching /${vendor_re}/; remove them (export never writes them): $tracked"
  fi
}

# Prints the live JSON, or {} when the file does not exist. Dies on invalid JSON.
read_live() {
  if [ -e "$live" ]; then
    jq empty "$live" 2>/dev/null || die "live file is not valid JSON, refusing to touch it: $live"
    cat "$live"
  else
    printf '{}\n'
  fi
}

# with_tracked FILTER: run FILTER over stdin with $tracked and $re bound.
with_tracked() { jq --indent 2 --slurpfile t "$tracked" --arg re "$vendor_re" "${JQ_LIB} \$t[0] as \$tracked | $1"; }

# write_if_changed DEST: stdin is the new content. Atomic; replaces a symlink
# with a regular file. Returns 1 (without writing) when DEST already matches.
write_if_changed() {
  local dest="$1" dir tmp
  dir="$(dirname "$dest")"
  mkdir -p "$dir"
  tmp="$(mktemp "${dir}/.$(basename "$dest").XXXXXX")"
  cat > "$tmp"
  if [ -f "$dest" ] && [ ! -L "$dest" ] && cmp -s "$tmp" "$dest"; then
    rm -f "$tmp"
    return 1
  fi
  chmod 644 "$tmp"
  if [ -L "$dest" ]; then rm -f "$dest"; fi
  mv -f "$tmp" "$dest"
}

join_or_none() { jq -r 'if length > 0 then join(", ") else "none" end'; }

cmd_merge() {
  check_tracked
  local live_json report was_link=0
  live_json="$(read_live)"
  report="$(with_tracked "$JQ_REPORT" <<<"$live_json")"
  if [ "$(jq '.drifted | length' <<<"$report")" -gt 0 ]; then
    note "resetting drifted owned keys to tracked values: $(jq .drifted <<<"$report" | join_or_none)"
  fi
  if [ "$(jq '.unrecognised | length' <<<"$report")" -gt 0 ]; then
    note "dropping hook groups that are neither tracked nor vendor-marked (run export first to keep them):"
    jq -r '.unrecognised[] | "  " + .' <<<"$report" >&2
  fi
  [ -L "$live" ] && was_link=1
  if with_tracked "$JQ_MERGE" <<<"$live_json" | write_if_changed "$live"; then
    if [ "$was_link" -eq 1 ]; then note "replaced symlink with a regular file: $live"; fi
    printf 'sync-settings: updated %s\n' "$live"
  else
    printf 'sync-settings: %s already up to date\n' "$live"
  fi
}

cmd_export() {
  check_tracked
  [ -e "$live" ] || die "live file missing, nothing to export: $live"
  local live_json report
  live_json="$(read_live)"
  report="$(with_tracked "$JQ_REPORT" <<<"$live_json")"
  if [ "$(jq '.unowned | length' <<<"$report")" -gt 0 ]; then
    note "not exported (unowned; add the key to $(basename "$tracked") to claim it): $(jq .unowned <<<"$report" | join_or_none)"
  fi
  if with_tracked "$JQ_EXPORT" <<<"$live_json" | write_if_changed "$tracked"; then
    printf 'sync-settings: updated %s; review with git diff\n' "$tracked"
  else
    printf 'sync-settings: %s already matches the live file\n' "$tracked"
  fi
}

cmd_status() {
  check_tracked
  local live_json report marker
  live_json="$(read_live)"
  report="$(with_tracked "$JQ_REPORT" <<<"$live_json")"
  printf 'tracked: %s\nlive:    %s\n' "$tracked" "$live"
  printf 'drifted owned keys (merge resets, export pulls): %s\n' "$(jq .drifted <<<"$report" | join_or_none)"
  printf 'unowned live keys (pass through, never exported): %s\n' "$(jq .unowned <<<"$report" | join_or_none)"
  printf 'vendor hook groups (pass through):\n'
  for marker in "${VENDOR_HOOK_MARKERS[@]}"; do
    printf '  %s (%s)\n' "$marker" "$(jq --arg re "$marker" "${JQ_LIB} vendor_hooks(\$re) | [.[][]] | length" <<<"$live_json")"
  done
  printf 'unrecognised hook groups (merge drops, export pulls):\n'
  if [ "$(jq '.unrecognised | length' <<<"$report")" -gt 0 ]; then
    jq -r '.unrecognised[] | "  " + .' <<<"$report"
  else
    printf '  none\n'
  fi
}

case "${1-}" in
  merge)  cmd_merge ;;
  export) cmd_export ;;
  status) cmd_status ;;
  *) usage ;;
esac
