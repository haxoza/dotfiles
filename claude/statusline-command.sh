#!/usr/bin/env bash
# Claude Code status line — mirrors Starship prompt style

input=$(cat)

# Directory
cwd=$(echo "$input" | jq -r '.workspace.current_dir // .cwd // empty')
if [ -n "$cwd" ]; then
  short_dir=$(basename "$cwd")
else
  short_dir=$(basename "$(pwd)")
fi

# Git info (branch + status indicators)
git_part=""
if git -C "$cwd" rev-parse --git-dir > /dev/null 2>&1; then
  branch=$(git -C "$cwd" symbolic-ref --short HEAD 2>/dev/null || git -C "$cwd" rev-parse --short HEAD 2>/dev/null)
  if [ -n "$branch" ]; then
    status_flags=""
    git_status=$(git -C "$cwd" status --porcelain 2>/dev/null)
    staged=$(echo "$git_status" | grep -c '^[MADRC]' 2>/dev/null || echo 0)
    modified=$(echo "$git_status" | grep -c '^.[MD]' 2>/dev/null || echo 0)
    untracked=$(echo "$git_status" | grep -c '^??' 2>/dev/null || echo 0)
    [ "$staged" -gt 0 ]    && status_flags="${status_flags} +${staged}"
    [ "$modified" -gt 0 ]  && status_flags="${status_flags} !${modified}"
    [ "$untracked" -gt 0 ] && status_flags="${status_flags} ?${untracked}"
    git_part=" | ${branch}${status_flags}"
  fi
fi

# Model
model=$(echo "$input" | jq -r '.model.display_name // empty')
model=$(echo "$model" | sed 's/ (\(.*\) context)/(\1)/')
model_part=""
[ -n "$model" ] && model_part=" | ${model}"

# Context usage
used_pct=$(echo "$input" | jq -r '.context_window.used_percentage // empty')
context_part=""
if [ -n "$used_pct" ]; then
  context_part="$(printf " | ctx: %.0f%%" "$used_pct")"
fi

# Cost
cost=$(echo "$input" | jq -r '.cost.total_cost_usd // empty')
cost_part=""
if [ -n "$cost" ]; then
  cost_part="$(printf " | $%.2f" "$cost")"
fi

# Rate limits
five_h=$(echo "$input" | jq -r '.rate_limits.five_hour.used_percentage // empty')
seven_d=$(echo "$input" | jq -r '.rate_limits.seven_day.used_percentage // empty')
limits_part=""
[ -n "$five_h" ] && limits_part="$(printf " | 5h: %.0f%%" "$five_h")"
[ -n "$seven_d" ] && limits_part="$(printf "%s 7d: %.0f%%" "$limits_part" "$seven_d")"

# Update check (cached, refreshes every 30 min)
update_part=""
current_version=$(echo "$input" | jq -r '.version // empty')
if [ -n "$current_version" ]; then
  cache_file="/tmp/claude-update-check"
  cache_max_age=1800
  if [ ! -f "$cache_file" ] || [ $(($(date +%s) - $(stat -f %m "$cache_file" 2>/dev/null || stat -c %Y "$cache_file" 2>/dev/null || echo 0))) -gt $cache_max_age ]; then
    latest=$(curl -s --max-time 3 "https://registry.npmjs.org/@anthropic-ai/claude-code/latest" 2>/dev/null | jq -r '.version // empty')
    [ -n "$latest" ] && echo "$latest" > "$cache_file"
  fi
  if [ -f "$cache_file" ]; then
    latest=$(cat "$cache_file")
    [ -n "$latest" ] && [ "$latest" != "$current_version" ] && update_part=" | UPD"
  fi
fi

printf "%s%s%s%s%s%s%s" "$short_dir" "$git_part" "$model_part" "$context_part" "$cost_part" "$limits_part" "$update_part"
