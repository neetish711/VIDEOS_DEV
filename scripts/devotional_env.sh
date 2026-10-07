#!/usr/bin/env bash
# Source this file from Bash before running the devotional workflow.
DEVOTIONAL_ROOT="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.." && pwd)"
case "$DEVOTIONAL_ROOT" in
  /workspace/*) DEVOTIONAL_CACHE_ROOT=/workspace/.cache ;;
  *) DEVOTIONAL_CACHE_ROOT="$DEVOTIONAL_ROOT/.cache" ;;
esac
export UV_CACHE_DIR="${UV_CACHE_DIR:-$DEVOTIONAL_CACHE_ROOT/uv}"
export UV_PYTHON_INSTALL_DIR="${UV_PYTHON_INSTALL_DIR:-$DEVOTIONAL_CACHE_ROOT/uv-python}"
export UV_SYSTEM_CERTS=true
export XDG_CACHE_HOME="${XDG_CACHE_HOME:-$DEVOTIONAL_CACHE_ROOT}"
export IMAGEIO_FFMPEG_EXE="$(command -v ffmpeg)"
mkdir -p "$UV_CACHE_DIR" "$UV_PYTHON_INSTALL_DIR" "$XDG_CACHE_HOME/fontconfig"
