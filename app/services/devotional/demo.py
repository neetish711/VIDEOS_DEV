"""Generate original artwork and local speech for an explicit technical preview."""

from __future__ import annotations

import json
from pathlib import Path
import subprocess
import wave

from PIL import Image, ImageDraw


def make_demo(directory: Path, *, portrait: bool = False, hd: bool = False) -> Path:
    if directory.exists():
        raise ValueError(f"Demo inputs already exist; choose a new directory: {directory}")
    directory.mkdir(parents=True)
    width, height = ((1080, 1920) if portrait else (1920, 1080)) if hd else (
        (720, 1280) if portrait else (1280, 720)
    )
    lines = [
        "A story begins with trusted sources, and a clear point of view.",
        "Reviewed artwork becomes a moving scene, timed to the narrator.",
        "Captions and audio come together. A person reviews the finished video.",
    ]
    palettes = [(28, 53, 68), (64, 41, 75), (38, 65, 52)]
    assets, scenes, audio = [], [], []
    current_time = 0.0
    params = None
    for index, (narration, palette) in enumerate(zip(lines, palettes), 1):
        name = f"scene-{index:02d}"
        text_path = directory / f"{name}.txt"
        text_path.write_text(narration, encoding="utf-8")
        audio_path = directory / f"{name}.wav"
        command = [
            "ffmpeg", "-hide_banner", "-loglevel", "error", "-nostdin",
            "-f", "lavfi", "-i", f"flite=textfile={text_path.name}:voice=slt",
            "-ar", "48000", "-ac", "1", "-c:a", "pcm_s16le", audio_path.name,
        ]
        result = subprocess.run(command, cwd=directory, capture_output=True, text=True, timeout=60)
        if result.returncode:
            raise RuntimeError(f"Offline demo speech requires FFmpeg's flite filter: {result.stderr[-1500:]}")
        with wave.open(str(audio_path), "rb") as reader:
            if params is None:
                params = reader.getparams()
            frames = reader.readframes(reader.getnframes())
            duration = reader.getnframes() / reader.getframerate()
            audio.append(frames)
        image = Image.new("RGB", (width, height), palette)
        draw = ImageDraw.Draw(image)
        for ring in range(7):
            radius = min(width, height) * (0.12 + ring * 0.08)
            center_x, center_y = width * 0.65, height * 0.35
            color = tuple(min(255, component + ring * 12 + 30) for component in palette)
            draw.ellipse((center_x-radius, center_y-radius, center_x+radius, center_y+radius), outline=color, width=3)
        draw.rounded_rectangle((width*.08, height*.17, width*.4, height*.65), radius=24, fill=(226, 185, 115))
        for stripe in range(4):
            y = height * (.27 + stripe * .075)
            draw.line((width*.12, y, width*.35, y), fill=palette, width=8)
        draw.text((width*.08, height*.76), f"DEVOTIONAL STUDIO / TECHNICAL PREVIEW / {index:02d}", fill=(255, 240, 216))
        image.save(directory / f"{name}.png")
        assets.append({
            "id": name, "path": f"{name}.png",
            "source_url": f"urn:devotional-studio:demo:original-art:{index}",
            "license": "CC0", "commercial_use": True, "reviewed": True,
            "sacred": False, "sacred_approved": False,
        })
        scenes.append({
            "id": name, "asset_id": name, "narration": narration, "claim_ids": [],
            "start_seconds": current_time, "end_seconds": current_time + duration,
        })
        current_time += duration
    assert params is not None
    with wave.open(str(directory / "narration.wav"), "wb") as writer:
        writer.setnchannels(params.nchannels)
        writer.setsampwidth(params.sampwidth)
        writer.setframerate(params.framerate)
        for frames in audio:
            writer.writeframes(frames)
    fixture = {
        "episode_id": "technical-preview-portrait" if portrait else "technical-preview",
        "title": "Devotional studio technical preview", "language": "en",
        "audio_path": "narration.wav", "sources": [], "claims": [],
        "assets": assets, "scenes": scenes, "width": width, "height": height,
        "fps": 24, "budget_usd": 0, "editorial_reviewed": True, "preview": True,
    }
    output = directory / "episode.json"
    output.write_text(json.dumps(fixture, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return output
