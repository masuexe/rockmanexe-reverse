#!/usr/bin/env bash
# Source this file to configure tools for the current terminal.
export GHIDRA_INSTALL_DIR=/home/harp/tools/ghidra_12.1.4_PUBLIC
export JAVA_HOME=/usr/lib/jvm/java-21-openjdk-amd64
export REA_ANALYSIS_PROVIDER=ghidra
export GHIDRA_HEADLESS_MAXMEM=2G
export PATH="$JAVA_HOME/bin:$GHIDRA_INSTALL_DIR:/usr/games:$PATH"

# Private inputs and runtime artifacts live outside the public project.
export EXE_REVERSE_LOCAL_DIR="${EXE_REVERSE_LOCAL_DIR:-/home/harp/projects/exe-reverse}"
