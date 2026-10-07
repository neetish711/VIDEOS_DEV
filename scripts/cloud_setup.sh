#!/usr/bin/env bash
set -euo pipefail
cd -- "$(dirname -- "${BASH_SOURCE[0]}")/.."
source scripts/devotional_env.sh
command -v uv >/dev/null
command -v ffmpeg >/dev/null
command -v ffprobe >/dev/null
uv python install --no-bin 3.11
uv sync --frozen --python 3.11
uv run --frozen python - <<'PY'
from pathlib import Path
import shutil
import toml

config = Path("config.toml")
if not config.exists():
    settings = {
        "project_name": "Devotional AI Video Studio",
        "listen_host": "127.0.0.1",
        "app": {
            "ffmpeg_path": shutil.which("ffmpeg"),
            "video_codec": "libx264",
            "video_clip_concurrency": 1,
            "hide_log": False,
        },
    }
    with config.open("x", encoding="utf-8") as handle:
        handle.write(toml.dumps(settings))
PY
uv run --frozen python -m app.services.devotional.cli doctor
