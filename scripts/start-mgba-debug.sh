#!/usr/bin/env bash
set -euo pipefail
task_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$task_script_dir/tool-env.sh"
task_rom_path=${1:-"$EXE_REVERSE_LOCAL_DIR/roms/exe6f.gba"}
if ! test -f "$task_rom_path"; then
  printf 'ROM not found: %s\n' "$task_rom_path" >&2
  exit 1
fi
exec mgba -d "$task_rom_path"
