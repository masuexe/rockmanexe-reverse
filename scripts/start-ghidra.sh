#!/usr/bin/env bash
set -euo pipefail
task_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$task_script_dir/tool-env.sh"
exec "$GHIDRA_INSTALL_DIR/ghidraRun" "$@"
