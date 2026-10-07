"""Offline, CPU-only assembly of reviewed stills and supplied narration.

This renderer never generates narration, fetches assets, or publishes anything.
Its output remains a draft awaiting human approval, including technical previews.
"""

from __future__ import annotations

from contextlib import contextmanager
from fractions import Fraction
import hashlib
import json
import math
import os
from pathlib import Path
import shutil
import subprocess
import tempfile
from typing import Iterator

import numpy as np
from PIL import Image, ImageOps

from .contracts import Episode, resolve_input
from .policy import validate_inputs


THREADS = 2
CAPTION_FONT = "Noto Sans Devanagari"
OUTPUT_NAMES = (
    "video.mp4",
    "captions.srt",
    "captions.ass",
    "thumbnail.png",
    "manifest.json",
)


def _run(command: list[str], *, cwd: Path | None = None, binary: bool = False):
    """Keep media commands noninteractive, bounded, and free of shell expansion."""
    environment = os.environ.copy()
    if cwd is not None:
        environment["XDG_CACHE_HOME"] = str(cwd / ".cache")
    try:
        result = subprocess.run(
            command,
            cwd=cwd,
            env=environment,
            stdin=subprocess.DEVNULL,
            capture_output=True,
            text=not binary,
            check=False,
            timeout=3600,
        )
    except (OSError, subprocess.TimeoutExpired) as exc:
        raise RuntimeError(f"media command could not complete: {command[0]}") from exc
    if result.returncode:
        error = result.stderr.decode("utf-8", "replace") if binary else result.stderr
        raise RuntimeError(f"media command failed: {error[-6000:]}")
    return result


def probe_media(path: Path) -> dict:
    """Return actual ffprobe stream/container information, without trusting suffixes."""
    ffprobe = shutil.which("ffprobe")
    if not ffprobe:
        raise RuntimeError("ffprobe is required; install the FFmpeg package")
    result = _run(
        [
            ffprobe,
            "-v",
            "error",
            "-show_format",
            "-show_streams",
            "-of",
            "json",
            str(path),
        ]
    )
    return json.loads(result.stdout)


def _duration(probe: dict, kind: str) -> float:
    stream = next(
        (s for s in probe.get("streams", []) if s.get("codec_type") == kind), None
    )
    if stream is None:
        raise ValueError(f"media must contain a {kind} stream")
    raw = stream.get("duration", probe.get("format", {}).get("duration"))
    try:
        value = float(raw)
    except (TypeError, ValueError) as exc:
        raise ValueError(f"cannot establish actual {kind} duration") from exc
    if not math.isfinite(value) or value <= 0:
        raise ValueError(f"actual {kind} duration must be positive and finite")
    return value


def _sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _input_inventory(episode: Episode, base_dir: Path) -> list[dict]:
    entries = [("narration", episode.audio_path)]
    entries.extend((f"asset:{asset.id}", asset.path) for asset in episode.assets)
    return [
        {
            "role": role,
            "path": relative,
            "sha256": _sha256(resolve_input(base_dir, relative)),
            "bytes": resolve_input(base_dir, relative).stat().st_size,
        }
        for role, relative in entries
    ]


@contextmanager
def _reserve_output(output_dir: Path, inputs: list[Path]) -> Iterator[Path]:
    """Refuse collisions, stale results, and concurrent renders in one directory."""
    if output_dir.is_symlink():
        raise ValueError("output directory must not be a symlink")
    destination = output_dir.resolve()
    if any(path == destination or destination in path.parents for path in inputs):
        raise ValueError(
            "output directory contains an input; choose a separate empty directory"
        )
    destination.mkdir(parents=True, exist_ok=True)
    lock = destination / ".render.lock"
    try:
        with lock.open("x", encoding="utf-8") as handle:
            handle.write(str(os.getpid()))
    except FileExistsError as exc:
        raise ValueError(
            "output directory has an active or stale render; choose a fresh directory"
        ) from exc
    try:
        if any(path != lock for path in destination.iterdir()):
            raise ValueError("output directory is not empty; choose a fresh directory")
        yield destination
    finally:
        lock.unlink(missing_ok=True)


def _caption_chunks(text: str) -> list[str]:
    """Keep text readable while preserving each scene's narration order."""
    words = " ".join(text.split()).split(" ")
    chunks: list[str] = []
    current = ""
    for word in words:
        if current and (len(current) + len(word) > 52 or len(current.split()) >= 9):
            chunks.append(current)
            current = ""
        current = f"{current} {word}".strip()
    if current:
        chunks.append(current)
    return chunks


def _timestamp(seconds: float, *, ass: bool) -> str:
    unit = 100 if ass else 1000
    ticks = round(seconds * unit)
    hours, remainder = divmod(ticks, 3600 * unit)
    minutes, remainder = divmod(remainder, 60 * unit)
    seconds_whole, subsecond = divmod(remainder, unit)
    if ass:
        return f"{hours}:{minutes:02}:{seconds_whole:02}.{subsecond:02}"
    return f"{hours:02}:{minutes:02}:{seconds_whole:02},{subsecond:03}"


def _write_captions(episode: Episode, work_dir: Path) -> int:
    cues: list[tuple[float, float, str]] = []
    for scene in episode.scenes:
        chunks = _caption_chunks(scene.narration)
        # A readable cue needs time on screen. Group very short scene captions.
        if (scene.end_seconds - scene.start_seconds) / len(chunks) < 0.2:
            chunks = [" ".join(chunks)]
        for index, text in enumerate(chunks):
            start = scene.start_seconds + (
                scene.end_seconds - scene.start_seconds
            ) * index / len(chunks)
            end = scene.start_seconds + (scene.end_seconds - scene.start_seconds) * (
                index + 1
            ) / len(chunks)
            cues.append((start, end, text))
    srt = (
        "\n\n".join(
            f"{index}\n{_timestamp(start, ass=False)} --> {_timestamp(end, ass=False)}\n{text}"
            for index, (start, end, text) in enumerate(cues, 1)
        )
        + "\n"
    )
    (work_dir / "captions.srt").write_text(srt, encoding="utf-8")
    font_size = max(18, round(episode.height * 0.055))
    margin = max(18, round(episode.height * 0.07))
    header = (
        "[Script Info]\nScriptType: v4.00+\n"
        f"PlayResX: {episode.width}\nPlayResY: {episode.height}\n"
        "WrapStyle: 0\nScaledBorderAndShadow: yes\n\n[V4+ Styles]\n"
        "Format: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, "
        "BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, "
        "BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n"
        f"Style: Default,{CAPTION_FONT},{font_size},&H00FFFFFF,&H00FFFFFF,&H0015120F,"
        f"&H80000000,0,0,0,0,100,100,0,0,1,2,1,2,{margin},{margin},{margin},1\n\n"
        "[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n"
    )

    # Neutralize ASS override syntax; narration cannot inject typesetting commands.
    def safe_ass(text: str) -> str:
        return text.replace("\\", "＼").replace("{", "（").replace("}", "）")

    events = "\n".join(
        f"Dialogue: 0,{_timestamp(start, ass=True)},{_timestamp(end, ass=True)},Default,,0,0,0,,{safe_ass(text)}"
        for start, end, text in cues
    )
    (work_dir / "captions.ass").write_text(header + events + "\n", encoding="utf-8")
    return len(cues)


def _font_file(work_dir: Path) -> Path:
    font_match = shutil.which("fc-match")
    if not font_match:
        raise RuntimeError(
            "fontconfig and Noto Sans Devanagari are required for captions"
        )
    result = _run(
        [font_match, "--format", "%{family}\n%{file}\n", CAPTION_FONT], cwd=work_dir
    )
    lines = result.stdout.strip().splitlines()
    if len(lines) != 2 or CAPTION_FONT not in lines[0] or not Path(lines[1]).is_file():
        raise RuntimeError(
            "install Noto Sans Devanagari; a fallback font cannot validate Hindi captions"
        )
    return Path(lines[1])


def _audio_sanity(
    ffmpeg: str, audio: Path, duration: float, preview: bool, work_dir: Path
) -> dict:
    """Reject silence and steady test tones; this is not speech/content recognition."""
    windows = []
    sample_starts = sorted({0.0, max(0.0, duration / 2 - 2), max(0.0, duration - 4)})
    for start in sample_starts:
        result = _run(
            [
                ffmpeg,
                "-nostdin",
                "-v",
                "error",
                "-threads",
                str(THREADS),
                "-ss",
                str(start),
                "-i",
                str(audio),
                "-t",
                "4",
                "-map",
                "0:a:0",
                "-ac",
                "1",
                "-ar",
                "8000",
                "-f",
                "f32le",
                "pipe:1",
            ],
            cwd=work_dir,
            binary=True,
        )
        samples = np.frombuffer(result.stdout, dtype="<f4")
        for offset in range(0, len(samples) - 1023, 1024):
            window = samples[offset : offset + 1024].astype(float)
            rms = float(np.sqrt(np.mean(window * window)))
            if rms > 0.0001:
                spectrum = (
                    np.abs(np.fft.rfft((window - np.mean(window)) * np.hanning(1024)))
                    ** 2
                )
                peak = int(np.argmax(spectrum))
                band = spectrum[max(0, peak - 2) : peak + 3].sum()
                concentration = float(band / max(float(spectrum.sum()), 1e-30))
                windows.append((rms, concentration))
    if not windows:
        raise ValueError("supplied narration is silent or too short to validate")
    tone_fraction = sum(concentration > 0.985 for _, concentration in windows) / len(
        windows
    )
    if not preview and tone_fraction >= 0.95:
        raise ValueError(
            "production narration appears tone-only; supply reviewed spoken narration"
        )
    return {
        "non_silent": True,
        "tone_window_fraction": round(tone_fraction, 5),
        "method": "sampled PCM energy and spectrum; not speech recognition",
    }


def _make_still(asset: Path, destination: Path) -> None:
    """Apply EXIF orientation in a private copy without modifying supplied media."""
    try:
        with Image.open(asset) as image:
            image.load()
            if getattr(image, "n_frames", 1) != 1:
                raise ValueError(
                    "only still image assets are supported by the local renderer"
                )
            ImageOps.exif_transpose(image).convert("RGB").save(
                destination, format="PNG"
            )
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError(f"asset is not a supported still image: {asset.name}") from exc


def _concat_cpu(clip_files: list[Path], destination: Path, work_dir: Path) -> None:
    # Reuse pinned upstream concatenation, including its staging and path escaping.
    # The temporary runtime override is protected by upstream's shared config lock.
    from app.config import config
    from app.services import video

    marker = object()
    with config.runtime_config_lock():
        previous = config.app.get("video_codec", marker)
        try:
            config.app["video_codec"] = "libx264"
            video.concat_video_clips_with_ffmpeg(
                clip_files=[str(path) for path in clip_files],
                output_file=str(destination),
                threads=THREADS,
                output_dir=str(work_dir),
            )
        finally:
            if previous is marker:
                config.app.pop("video_codec", None)
            else:
                config.app["video_codec"] = previous


def _check_output(
    video: Path, episode: Episode, narration_duration: float, tolerance: float
) -> dict:
    probe = probe_media(video)
    videos = [
        stream for stream in probe["streams"] if stream.get("codec_type") == "video"
    ]
    audios = [
        stream for stream in probe["streams"] if stream.get("codec_type") == "audio"
    ]
    if len(videos) != 1 or len(audios) != 1:
        raise RuntimeError("render must contain exactly one video and one audio stream")
    visual, audio = videos[0], audios[0]
    rate = float(Fraction(visual.get("avg_frame_rate", "0/1")))
    video_duration, audio_duration = (
        _duration(probe, "video"),
        _duration(probe, "audio"),
    )
    # Check actual presentation timestamps as well as advertised frame rates.
    packet_probe = _run(
        [
            shutil.which("ffprobe"),
            "-v",
            "error",
            "-select_streams",
            "v:0",
            "-show_packets",
            "-show_entries",
            "packet=pts_time",
            "-of",
            "json",
            str(video),
        ]
    )
    packet_times = sorted(
        float(packet["pts_time"])
        for packet in json.loads(packet_probe.stdout).get("packets", [])
    )
    frame_intervals_valid = len(packet_times) >= 2 and all(
        abs((right - left) - 1 / episode.fps) < 0.00001
        for left, right in zip(packet_times, packet_times[1:])
    )
    checks = {
        "h264": visual.get("codec_name") == "h264",
        "aac": audio.get("codec_name") == "aac",
        "yuv420p": visual.get("pix_fmt") == "yuv420p",
        "resolution": (visual.get("width"), visual.get("height"))
        == (episode.width, episode.height),
        "constant_frame_rate": abs(rate - episode.fps) < 0.001
        and abs(float(Fraction(visual.get("r_frame_rate", "0/1"))) - episode.fps)
        < 0.001
        and frame_intervals_valid,
        "audio_48khz": audio.get("sample_rate") == "48000",
        "video_duration": abs(video_duration - narration_duration) <= tolerance,
        "audio_duration": abs(audio_duration - narration_duration) <= tolerance,
    }
    if not all(checks.values()):
        raise RuntimeError(f"render media validation failed: {checks}")
    return {
        "checks": checks,
        "video_codec": visual["codec_name"],
        "audio_codec": audio["codec_name"],
        "width": visual["width"],
        "height": visual["height"],
        "fps": rate,
        "audio_sample_rate": int(audio["sample_rate"]),
        "video_duration_seconds": video_duration,
        "audio_duration_seconds": audio_duration,
        "narration_duration_seconds": narration_duration,
        "duration_tolerance_seconds": tolerance,
        "video_frame_count": len(packet_times),
    }


def render_episode(episode: Episode, base_dir: Path, output_dir: Path) -> Path:
    """Render a validated draft using local files; return its reviewed-media MP4 path."""
    base_dir, output_dir = Path(base_dir).resolve(), Path(output_dir)
    # Policy rejection happens before probing, decoding, creating outputs, or importing upstream media.
    # Nested lists/models may have been mutated since the caller first parsed JSON.
    episode = Episode.model_validate(episode.model_dump(mode="python"))
    validate_inputs(episode, base_dir)
    input_inventory = _input_inventory(episode, base_dir)
    audio = resolve_input(base_dir, episode.audio_path)
    assets = {asset.id: resolve_input(base_dir, asset.path) for asset in episode.assets}
    ffmpeg = os.environ.get("IMAGEIO_FFMPEG_EXE") or shutil.which("ffmpeg")
    if not ffmpeg:
        raise RuntimeError("FFmpeg is required for local rendering")
    narration_duration = _duration(probe_media(audio), "audio")
    tolerance = 1 / episode.fps + 0.06  # One video frame plus AAC/container rounding.
    if abs(episode.scenes[-1].end_seconds - narration_duration) > tolerance:
        raise ValueError(
            "scene timeline must match actual supplied narration duration within one frame plus codec tolerance"
        )
    frames = [
        round(scene.end_seconds * episode.fps)
        - round(scene.start_seconds * episode.fps)
        for scene in episode.scenes
    ]
    if any(count < 1 for count in frames):
        raise ValueError("every scene must occupy at least one video frame")

    with _reserve_output(output_dir, [audio, *assets.values()]) as destination:
        with tempfile.TemporaryDirectory(prefix=".render-", dir=destination) as scratch:
            work_dir = Path(scratch)
            font_file = _font_file(work_dir)
            audio_checks = _audio_sanity(
                ffmpeg, audio, narration_duration, episode.preview, work_dir
            )
            cue_count = _write_captions(episode, work_dir)
            clips: list[Path] = []
            for index, (scene, count) in enumerate(zip(episode.scenes, frames)):
                still = work_dir / f"still-{index:04}.png"
                _make_still(assets[scene.asset_id], still)
                clip = work_dir / f"scene-{index:04}.mp4"
                filters = (
                    f"scale={episode.width * 2}:{episode.height * 2}:force_original_aspect_ratio=increase,"
                    f"crop={episode.width * 2}:{episode.height * 2},"
                    f"zoompan=z='1.02+0.06*on/{max(1, count - 1)}':"
                    f"x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':d=1:"
                    f"s={episode.width}x{episode.height}:fps={episode.fps},format=yuv420p"
                )
                _run(
                    [
                        ffmpeg,
                        "-nostdin",
                        "-v",
                        "error",
                        "-n",
                        "-threads",
                        str(THREADS),
                        "-loop",
                        "1",
                        "-framerate",
                        str(episode.fps),
                        "-i",
                        str(still),
                        "-filter_threads",
                        str(THREADS),
                        "-vf",
                        filters,
                        "-frames:v",
                        str(count),
                        "-an",
                        "-c:v",
                        "libx264",
                        "-preset",
                        "veryfast",
                        "-crf",
                        "20",
                        "-threads",
                        str(THREADS),
                        "-pix_fmt",
                        "yuv420p",
                        "-r",
                        str(episode.fps),
                        "-map_metadata",
                        "-1",
                        str(clip),
                    ],
                    cwd=work_dir,
                )
                clips.append(clip)
            joined = work_dir / "joined.mp4"
            _concat_cpu(clips, joined, work_dir)
            # Use simple relative filter paths; user paths never enter FFmpeg's filter language.
            # Copy the explicit font privately, so fontsdir cannot contain injected punctuation.
            local_fonts = work_dir / "fonts"
            local_fonts.mkdir()
            shutil.copyfile(font_file, local_fonts / "NotoSansDevanagari-Regular.ttf")
            final = work_dir / "video.mp4"
            _run(
                [
                    ffmpeg,
                    "-nostdin",
                    "-v",
                    "error",
                    "-n",
                    "-threads",
                    str(THREADS),
                    "-i",
                    str(joined),
                    "-threads",
                    str(THREADS),
                    "-i",
                    str(audio),
                    "-map",
                    "0:v:0",
                    "-map",
                    "1:a:0",
                    "-filter_threads",
                    str(THREADS),
                    "-vf",
                    "tpad=stop_mode=clone:stop_duration=0.2,ass=captions.ass:fontsdir=fonts",
                    "-t",
                    f"{narration_duration:.6f}",
                    "-r",
                    str(episode.fps),
                    "-fps_mode",
                    "cfr",
                    "-c:v",
                    "libx264",
                    "-preset",
                    "veryfast",
                    "-crf",
                    "20",
                    "-threads",
                    str(THREADS),
                    "-pix_fmt",
                    "yuv420p",
                    "-c:a",
                    "aac",
                    "-ar",
                    "48000",
                    "-b:a",
                    "192k",
                    "-map_metadata",
                    "-1",
                    "-movflags",
                    "+faststart",
                    str(final),
                ],
                cwd=work_dir,
            )
            media_checks = _check_output(final, episode, narration_duration, tolerance)
            for name in ("captions.srt", "captions.ass"):
                if not (work_dir / name).read_text(encoding="utf-8").strip():
                    raise RuntimeError(f"missing caption sidecar: {name}")
            _run(
                [
                    ffmpeg,
                    "-nostdin",
                    "-v",
                    "error",
                    "-n",
                    "-threads",
                    str(THREADS),
                    "-i",
                    str(final),
                    "-frames:v",
                    "1",
                    "-vf",
                    "scale=640:-2",
                    "-filter_threads",
                    str(THREADS),
                    "-threads",
                    str(THREADS),
                    str(work_dir / "thumbnail.png"),
                ],
                cwd=work_dir,
            )
            with Image.open(work_dir / "thumbnail.png") as thumbnail:
                thumbnail.verify()
            # Inputs are immutable: detect edits that occurred during a render.
            if _input_inventory(episode, base_dir) != input_inventory:
                raise RuntimeError(
                    "an input changed during rendering; discard this draft and retry"
                )
            manifest = {
                "schema_version": 1,
                "episode_id": episode.episode_id,
                "title": episode.title,
                "language": episode.language,
                "preview": episode.preview,
                "state": "AWAITING_APPROVAL",
                "human_approved": False,
                "state_history": [
                    "SCENES_READY",
                    "RENDERED",
                    "MEDIA_QA_PASSED",
                    "AWAITING_APPROVAL",
                ],
                "spend_usd": 0,
                "network_calls": 0,
                "cpu_threads": THREADS,
                "inputs": input_inventory,
                "episode_sha256": hashlib.sha256(
                    json.dumps(
                        episode.model_dump(mode="json"),
                        sort_keys=True,
                        ensure_ascii=False,
                    ).encode("utf-8")
                ).hexdigest(),
                "outputs": {
                    name: {
                        "sha256": _sha256(work_dir / name),
                        "bytes": (work_dir / name).stat().st_size,
                    }
                    for name in OUTPUT_NAMES
                    if name != "manifest.json"
                },
                "media": media_checks,
                "narration_checks": audio_checks,
                "captions": {
                    "font": CAPTION_FONT,
                    "cue_count": cue_count,
                    "burned_in": True,
                    "sidecars_verified": True,
                    "timing": "proportional scene text chunks; human review required",
                },
                "claims": [claim.model_dump(mode="json") for claim in episode.claims],
                "sources": [
                    source.model_dump(mode="json") for source in episode.sources
                ],
                "assets": [asset.model_dump(mode="json") for asset in episode.assets],
                "scenes": [scene.model_dump(mode="json") for scene in episode.scenes],
            }
            (work_dir / "manifest.json").write_text(
                json.dumps(manifest, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            # Hard-link publication refuses overwrite, including a concurrent unexpected file.
            published: list[Path] = []
            try:
                for name in OUTPUT_NAMES:
                    target = destination / name
                    os.link(work_dir / name, target)
                    published.append(target)
            except OSError:
                for target in published:
                    target.unlink(missing_ok=True)
                raise
    return destination / "video.mp4"
