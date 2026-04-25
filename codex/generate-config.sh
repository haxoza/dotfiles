#!/usr/bin/env bash
set -e

script_dir="$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)"
common_file="${script_dir}/common.toml"
local_file="${script_dir}/trusted.local.toml"
output_file="${script_dir}/config.toml"

cp "${common_file}" "${output_file}"

if [ -f "${local_file}" ]; then
  printf '\n' >> "${output_file}"
  cat "${local_file}" >> "${output_file}"
fi
