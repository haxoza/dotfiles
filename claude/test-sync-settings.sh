#!/usr/bin/env bash
# Tests for sync-settings.sh. Runs against fixtures in a temp dir and never
# touches ~/.claude. Usage: claude/test-sync-settings.sh
set -e

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
sut="${script_dir}/sync-settings.sh"

pass=0
fail=0
ok() { pass=$((pass + 1)); printf 'ok   %s\n' "$1"; }
ko() { fail=$((fail + 1)); printf 'FAIL %s\n     %s\n' "$1" "$2"; }

# assert_json NAME FILE FILTER EXPECTED   (compares jq output, key order ignored)
assert_json() {
  local name="$1" file="$2" filter="$3" expected="$4" actual
  actual="$(jq -cS "$filter" "$file" 2>&1 || true)"
  expected="$(jq -cS . <<<"$expected")"
  if [ "$actual" = "$expected" ]; then ok "$name"; else ko "$name" "expected $expected, got $actual"; fi
}
assert_contains() {
  local name="$1" haystack="$2" needle="$3"
  if [[ "$haystack" == *"$needle"* ]]; then ok "$name"; else ko "$name" "expected to find '$needle' in: $haystack"; fi
}
assert_true() { if eval "$2"; then ok "$1"; else ko "$1" "condition failed: $2"; fi; }
# run SUBCOMMAND: invoke the script expecting success; a non-zero exit is a test failure, not an abort
run() { local rc=0; "$sut" "$@" >/dev/null 2>&1 || rc=$?; [ "$rc" -eq 0 ] || ko "$* exits 0" "exit code $rc"; }

ORCA_CMD='if [ -z "${HOME-}" ]; then printf "{}\n"; else /bin/sh "${HOME-}/.orca/agent-hooks/claude-hook.sh"; fi'
ORCA_EVENTS='["SessionStart","UserPromptSubmit","Stop","StopFailure","SubagentStart","SubagentStop","TeammateIdle","PreToolUse","PostToolUse","PostToolUseFailure","PermissionRequest","PostCompact"]'

tracked_fixture() {
  jq --indent 2 . <<'JSON'
{
  "permissions": {
    "allow": ["Bash(git status*)", "WebSearch"],
    "deny": ["Read(~/.ssh/**)"],
    "defaultMode": "auto"
  },
  "model": "opus[1m]",
  "hooks": {
    "SessionStart": [
      {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/caffeinate-manage.sh start", "timeout": 5}]}
    ],
    "SessionEnd": [
      {"matcher": "", "hooks": [{"type": "command", "command": "bash ~/.claude/caffeinate-manage.sh stop", "timeout": 5}]}
    ]
  },
  "statusLine": {"type": "command", "command": "bash ~/.claude/statusline-command.sh"},
  "tui": "fullscreen"
}
JSON
}

# Live file as Orca and Claude Code would leave it: tracked content plus one
# Orca group appended to each of 12 events, an app-owned key, and a model change.
live_fixture() {
  tracked_fixture | jq --indent 2 --arg cmd "$ORCA_CMD" --argjson events "$ORCA_EVENTS" '
    {matcher: "", hooks: [{type: "command", command: $cmd}]} as $orca
    | reduce $events[] as $ev (.; .hooks[$ev] = ((.hooks[$ev] // []) + [$orca]))
    | .feedbackSurveyState = {lastShownTime: 1}
    | .model = "claude-fable-5-1[1m]"'
}

count_orca_groups() { jq --arg cmd "$ORCA_CMD" '[.hooks[][] | select(.hooks[].command == $cmd)] | length' "$1"; }

setup() {
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/sync-settings-test.XXXXXX")"
  live="${tmp}/home/.claude/settings.json"
  tracked="${tmp}/repo/settings.json"
  mkdir -p "${tmp}/home/.claude" "${tmp}/repo"
  tracked_fixture > "$tracked"
  live_fixture > "$live"
  export CLAUDE_SETTINGS_LIVE_FILE="$live" CLAUDE_SETTINGS_TRACKED_FILE="$tracked"
}
teardown() { rm -rf "$tmp"; }

# --- merge -------------------------------------------------------------------

test_merge_replaces_symlink_with_real_file() {
  setup
  mv "$live" "${tmp}/repo/old-symlink-target.json"
  ln -s "${tmp}/repo/old-symlink-target.json" "$live"
  run merge
  assert_true "merge: live becomes a regular file" '[ -f "$live" ] && ! [ -L "$live" ]'
  assert_json "merge: content came through the old link" "$live" '.feedbackSurveyState' '{"lastShownTime":1}'
  assert_json "merge: old link target untouched" "${tmp}/repo/old-symlink-target.json" '.model' '"claude-fable-5-1[1m]"'
  teardown
}

test_merge_overlays_owned_keys_wholesale() {
  setup
  jq '.permissions.allow += ["Bash(rm -rf *)"]' "$live" > "${live}.new" && mv "${live}.new" "$live"
  run merge
  assert_json "merge: owned scalar replaced" "$live" '.model' '"opus[1m]"'
  assert_json "merge: owned object replaced wholesale, not merged" "$live" '.permissions.allow' '["Bash(git status*)","WebSearch"]'
  teardown
}

test_merge_passes_through_unowned_keys() {
  setup
  run merge
  assert_json "merge: unowned key survives" "$live" '.feedbackSurveyState' '{"lastShownTime":1}'
  teardown
}

test_merge_keeps_vendor_hook_groups() {
  setup
  run merge
  assert_json "merge: all 12 Orca groups survive" "$live" "[.hooks[][] | select(.hooks[].command | test(\"orca/agent-hooks\"))] | length" '12'
  assert_json "merge: repo group first, vendor group after in shared event" "$live" \
    '.hooks.SessionStart | map(.hooks[0].command | test("orca") )' '[false,true]'
  teardown
}

test_merge_replaces_repo_hook_groups_and_drops_unrecognised() {
  setup
  jq '.hooks.SessionStart[0].hooks[0].timeout = 10' "$tracked" > "${tracked}.new" && mv "${tracked}.new" "$tracked"
  jq '.hooks.Notification = [{matcher: "", hooks: [{type: "command", command: "say hi"}]}]' "$live" > "${live}.new" && mv "${live}.new" "$live"
  run merge
  assert_json "merge: edited repo hook replaces stale copy" "$live" '.hooks.SessionStart | map(.hooks[0].timeout)' '[10,null]'
  assert_json "merge: unrecognised non-vendor group dropped" "$live" '.hooks | has("Notification")' 'false'
  teardown
}

test_merge_is_idempotent_and_skips_rewrite() {
  setup
  run merge
  local first_inode first_content
  first_inode="$(stat -f %i "$live")"; first_content="$(cat "$live")"
  run merge
  assert_true "merge: second run leaves content identical" '[ "$(cat "$live")" = "$first_content" ]'
  assert_true "merge: second run does not rewrite the file" '[ "$(stat -f %i "$live")" = "$first_inode" ]'
  teardown
}

test_merge_creates_live_from_tracked_when_missing() {
  setup
  rm -rf "${tmp}/home"
  run merge
  assert_true "merge: creates missing parent dir and file" '[ -f "$live" ]'
  assert_json "merge: fresh file equals tracked" "$live" '.' "$(cat "$tracked")"
  teardown
}

test_merge_reports_drifted_keys_on_stderr() {
  setup
  local err
  err="$("$sut" merge 2>&1 >/dev/null || true)"
  assert_contains "merge: drifted owned key named on stderr" "$err" "model"
  teardown
}

test_merge_refuses_invalid_live_json() {
  setup
  printf '{ not json' > "$live"
  local rc=0 err
  err="$("$sut" merge 2>&1 >/dev/null)" || rc=$?
  assert_true "merge: invalid live JSON exits non-zero" '[ "$rc" -ne 0 ]'
  assert_contains "merge: invalid live JSON explained on stderr" "$err" "not valid JSON"
  assert_true "merge: invalid live file left untouched" '[ "$(cat "$live")" = "{ not json" ]'
  teardown
}

test_merge_refuses_tracked_with_vendor_group() {
  setup
  live_fixture > "$tracked"
  local before rc=0 err
  before="$(cat "$live")"
  err="$("$sut" merge 2>&1 >/dev/null)" || rc=$?
  assert_true "merge: vendor group inside tracked file exits non-zero" '[ "$rc" -ne 0 ]'
  assert_contains "merge: vendor group inside tracked file explained on stderr" "$err" "vendor"
  assert_true "merge: live untouched when tracked is invalid" '[ "$(cat "$live")" = "$before" ]'
  teardown
}

# --- export ------------------------------------------------------------------

test_export_round_trips_after_merge() {
  setup
  cp "$tracked" "${tmp}/tracked.orig"
  run merge
  run export
  assert_true "export: reproduces tracked file byte for byte after merge" 'cmp -s "$tracked" "${tmp}/tracked.orig"'
  teardown
}

test_export_pulls_owned_changes_and_preserves_key_order() {
  setup
  jq 'del(.tui) | .permissions.allow += ["Bash(make *)"]' "$live" > "${live}.new" && mv "${live}.new" "$live"
  run export
  assert_json "export: live model pulled in" "$tracked" '.model' '"claude-fable-5-1[1m]"'
  assert_json "export: approved permission appended at end" "$tracked" '.permissions.allow' '["Bash(git status*)","WebSearch","Bash(make *)"]'
  assert_json "export: key deleted in live is dropped" "$tracked" 'has("tui")' 'false'
  assert_json "export: tracked key order kept" "$tracked" 'keys_unsorted' '["permissions","model","hooks","statusLine"]'
  assert_json "export: unowned key not exported" "$tracked" 'has("feedbackSurveyState")' 'false'
  teardown
}

test_export_strips_vendor_hooks() {
  setup
  local orig_hooks
  orig_hooks="$(jq -c .hooks "$tracked")"
  run export
  assert_json "export: hooks equal tracked hooks with vendor groups removed" "$tracked" '.hooks' "$orig_hooks"
  teardown
}

test_export_lists_unowned_keys_on_stderr() {
  setup
  local err
  err="$("$sut" export 2>&1 >/dev/null || true)"
  assert_contains "export: unowned live key named on stderr" "$err" "feedbackSurveyState"
  teardown
}

# --- status ------------------------------------------------------------------

test_status_reports_without_writing() {
  setup
  jq '.hooks.Notification = [{matcher: "", hooks: [{type: "command", command: "say hi"}]}]' "$live" > "${live}.new" && mv "${live}.new" "$live"
  local before_live before_tracked out
  before_live="$(cat "$live")"; before_tracked="$(cat "$tracked")"
  out="$("$sut" status 2>&1 || true)"
  assert_contains "status: names drifted owned key" "$out" "model"
  assert_contains "status: names unowned live key" "$out" "feedbackSurveyState"
  assert_contains "status: counts vendor groups per marker" "$out" "orca/agent-hooks/ (12)"
  assert_contains "status: lists unrecognised hook group with event" "$out" "Notification"
  assert_contains "status: lists unrecognised hook group command" "$out" "say hi"
  assert_true "status: live untouched" '[ "$(cat "$live")" = "$before_live" ]'
  assert_true "status: tracked untouched" '[ "$(cat "$tracked")" = "$before_tracked" ]'
  teardown
}

for t in $(declare -F | awk '{print $3}' | grep '^test_'); do "$t"; done

printf '\n%d passed, %d failed\n' "$pass" "$fail"
[ "$fail" -eq 0 ]
