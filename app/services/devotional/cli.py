"""Local entry point for the first devotional video-engine milestone."""

from __future__ import annotations

import argparse
import importlib.metadata
import json
from pathlib import Path
import shutil
import subprocess
import sys
import uuid


def doctor() -> dict:
    """Check the actual CPU rendering tools without using external providers."""
    checks: dict = {"python": sys.version.split()[0]}
    failures = []
    if sys.version_info[:2] != (3, 11):
        failures.append("Use the pinned Python 3.11 environment: uv sync --frozen")
    for name in ("pydantic", "moviepy", "pillow", "faster-whisper", "pytest"):
        try:
            checks[name] = importlib.metadata.version(name)
        except importlib.metadata.PackageNotFoundError:
            failures.append(f"Missing dependency: {name}; run bash scripts/cloud_setup.sh")
    for name in ("ffmpeg", "ffprobe"):
        executable = shutil.which(name)
        checks[name] = executable
        if not executable:
            failures.append(f"Install {name} on the host")
    if checks.get("ffmpeg"):
        filters = subprocess.check_output(
            [checks["ffmpeg"], "-hide_banner", "-filters"], text=True
        )
        encoders = subprocess.check_output(
            [checks["ffmpeg"], "-hide_banner", "-encoders"], text=True
        )
        for name in ("zoompan", "ass", "loudnorm"):
            present = any(line.split()[1:2] == [name] for line in filters.splitlines())
            checks[f"filter_{name}"] = present
            if not present:
                failures.append(f"FFmpeg requires the {name} filter")
        checks["offline_demo_voice"] = any(
            line.split()[1:2] == ["flite"] for line in filters.splitlines()
        )
        for name in ("libx264", "aac"):
            present = any(line.split()[1:2] == [name] for line in encoders.splitlines())
            checks[f"encoder_{name}"] = present
            if not present:
                failures.append(f"FFmpeg requires the {name} encoder")
    font = shutil.which("fc-match")
    if font:
        match = subprocess.check_output(
            [font, "-f", "%{family}", "Noto Sans Devanagari"], text=True
        ).strip()
        checks["caption_font"] = match
        if "Devanagari" not in match:
            failures.append("Install Noto Sans Devanagari for Hindi captions")
    else:
        failures.append("Install fontconfig and Noto Sans Devanagari")
    checks["workflow"] = "local CPU rendering; no generation APIs or publishing"
    checks["failures"] = failures
    checks["ready"] = not failures
    checks["demo_ready"] = checks["ready"] and checks.get("offline_demo_voice", False)
    if not checks["demo_ready"] and not failures:
        checks["demo_note"] = "The recorded-audio workflow is available; the offline demo needs FFmpeg's flite filter."
    return checks


def _new_run_dir() -> Path:
    return Path("storage/devotional/runs") / uuid.uuid4().hex[:12]


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Devotional AI Video Studio — local milestone")
    subparsers = parser.add_subparsers(dest="command", required=True)
    subparsers.add_parser("doctor", help="Check the local Python and media tools")
    validate = subparsers.add_parser("validate", help="Check reviewed episode inputs")
    validate.add_argument("--episode", type=Path, required=True)
    render = subparsers.add_parser("render", help="Render a reviewed episode using supplied audio")
    render.add_argument("--episode", type=Path, required=True)
    render.add_argument("--output", type=Path)
    demo = subparsers.add_parser("demo", help="Render an offline English technical preview")
    demo.add_argument("--directory", type=Path)
    demo.add_argument("--portrait", action="store_true", help="Render 9:16 instead of 16:9")
    demo.add_argument("--hd", action="store_true", help="Use 1080p instead of 720p")
    args = parser.parse_args(argv)
    try:
        if args.command == "doctor":
            report = doctor()
            print(json.dumps(report, indent=2))
            return 0 if report["ready"] else 1
        from .contracts import load_episode
        from .policy import validate_inputs

        if args.command == "demo":
            from .demo import make_demo
            from .render import render_episode

            directory = (args.directory or _new_run_dir()).resolve()
            fixture = make_demo(directory / "inputs", portrait=args.portrait, hd=args.hd)
            episode = load_episode(fixture)
            output = render_episode(episode, fixture.parent, directory / "render")
            print(f"Technical preview: {output}")
            print("Offline English demo voice; no sacred imagery, AI generation, or publishing.")
            return 0
        fixture = args.episode.resolve()
        episode = load_episode(fixture)
        validate_inputs(episode, fixture.parent)
        if args.command == "validate":
            print(f"Reviewed input metadata and local files passed: {episode.episode_id}")
            print("This checks recorded review decisions; it does not perform an AI editorial review.")
            return 0
        from .render import render_episode

        output_dir = args.output or (_new_run_dir() / "render")
        output = render_episode(episode, fixture.parent, output_dir.resolve())
        print(f"Rendered: {output}")
        print("Human review is still required before publication.")
        return 0
    except (ValueError, OSError, RuntimeError, subprocess.SubprocessError) as exc:
        print(f"Devotional workflow failed: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
