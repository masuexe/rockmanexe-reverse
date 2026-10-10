#!/usr/bin/env bash
set -euo pipefail
task_script_dir=$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)
source "$task_script_dir/tool-env.sh"

test -f "$GHIDRA_INSTALL_DIR/Ghidra/application.properties"
test -x "$JAVA_HOME/bin/javac"
command -v codex >/dev/null
command -v npx >/dev/null

# Repair executable bits lost when extracting the release archive.
chmod u+x "$GHIDRA_INSTALL_DIR/ghidraRun" \
  "$GHIDRA_INSTALL_DIR/support/launch.sh" \
  "$GHIDRA_INSTALL_DIR/support/analyzeHeadless" \
  "$GHIDRA_INSTALL_DIR/Ghidra/Features/Decompiler/os/linux_x86_64/decompile"
if test -f "$GHIDRA_INSTALL_DIR/Ghidra/Features/Decompiler/os/linux_x86_64/sleigh"; then
  chmod u+x "$GHIDRA_INSTALL_DIR/Ghidra/Features/Decompiler/os/linux_x86_64/sleigh"
fi

java -version
javac -version
mgba --version

# Pin the package version used for this project's initial setup.
npx --yes rea-agents@5.0.0 doctor --provider ghidra --json
npx --yes rea-agents@5.0.0 setup --client codex --dry-run
# User authorized configuration; apply only the Codex integration.
npx --yes rea-agents@5.0.0 setup --client codex --yes
npx --yes rea-agents@5.0.0 doctor --client codex --provider ghidra --json
codex mcp get rea
printf '\nConfiguration complete. Restart Codex to load REA.\n'
