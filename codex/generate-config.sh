#!/usr/bin/env bash
set -e

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
common_file="${script_dir}/common.toml"
local_file="${script_dir}/trusted.local.toml"
output_file="${script_dir}/config.toml"
timestamp="$(date +%Y%m%d-%H%M%S)"
temp_file="$(mktemp "${output_file}.tmp.XXXXXX")"

trap 'rm -f "${temp_file}"' EXIT

if [ -f "${output_file}" ]; then
  cp -p "${output_file}" "${output_file}.${timestamp}.bak"
fi

# TOML root keys must precede tables. Merge each source in two passes so local
# root settings such as `notify` remain valid without tracking machine paths.
awk '/^\[/{exit} {print}' "${common_file}" > "${temp_file}"
if [ -f "${local_file}" ]; then
  awk '/^\[/{exit} {print}' "${local_file}" >> "${temp_file}"
fi
awk 'found || /^\[/{found=1; print}' "${common_file}" >> "${temp_file}"
if [ -f "${local_file}" ]; then
  awk 'found || /^\[/{found=1; print}' "${local_file}" >> "${temp_file}"
fi

mv "${temp_file}" "${output_file}"
trap - EXIT
