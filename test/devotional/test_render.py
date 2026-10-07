"""Exercise real local media assembly and its destructive/error boundaries."""

import hashlib
import json
import shutil
import subprocess

import numpy as np
from PIL import Image
import pytest

from app.services.devotional.contracts import Episode
from app.services.devotional import render


@pytest.fixture(scope="module")
def narrated_fixture(tmp_path_factory):
    if not shutil.which("ffmpeg") or not shutil.which("ffprobe"):
        pytest.skip("FFmpeg and ffprobe are required for rendering integration checks")
    base = tmp_path_factory.mktemp("supplied-narration")
    Image.new("RGB", (640, 360), (18, 50, 55)).save(base / "still.png")
    narration = base / "narration.wav"
    result = subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            "flite=text='This is a local technical preview. It makes no religious claims.':voice=slt",
            "-ar",
            "48000",
            str(narration),
        ],
        capture_output=True,
        text=True,
        check=False,
    )
    if result.returncode:
        pytest.skip(f"local FFmpeg flite voice unavailable: {result.stderr}")
    duration = render._duration(render.probe_media(narration), "audio")
    payload = {
        "episode_id": "render-test",
        "title": "Technical preview",
        "language": "hinglish",
        "audio_path": "narration.wav",
        "sources": [],
        "claims": [],
        "assets": [
            {
                "id": "original",
                "path": "still.png",
                "source_url": "urn:original:test-still",
                "license": "CC0",
                "commercial_use": True,
                "reviewed": True,
            }
        ],
        "scenes": [
            {
                "id": "opening",
                "asset_id": "original",
                "narration": "तकनीकी परीक्षण — Local technical preview",
                "claim_ids": [],
                "start_seconds": 0.0,
                "end_seconds": duration / 2,
            },
            {
                "id": "closing",
                "asset_id": "original",
                "narration": "No religious claims are made in this preview.",
                "claim_ids": [],
                "start_seconds": duration / 2,
                "end_seconds": duration,
            },
        ],
        "width": 320,
        "height": 180,
        "fps": 24,
        "budget_usd": 0.0,
        "editorial_reviewed": True,
        "preview": True,
    }
    return base, Episode.model_validate(payload)


def test_actual_render_codecs_captions_hashes_and_no_approval(
    narrated_fixture, tmp_path
):
    base, episode = narrated_fixture
    before = {
        name: hashlib.sha256((base / name).read_bytes()).hexdigest()
        for name in ("narration.wav", "still.png")
    }
    video = render.render_episode(episode, base, tmp_path / "result")
    manifest = json.loads((video.parent / "manifest.json").read_text(encoding="utf-8"))
    assert video.name == "video.mp4"
    assert manifest["media"]["video_codec"] == "h264"
    assert manifest["media"]["audio_codec"] == "aac"
    assert manifest["media"]["audio_sample_rate"] == 48000
    assert manifest["media"]["fps"] == 24
    assert all(manifest["media"]["checks"].values())
    assert manifest["preview"] is True
    assert manifest["human_approved"] is False
    assert manifest["state"] == "AWAITING_APPROVAL"
    assert manifest["spend_usd"] == 0
    assert manifest["cpu_threads"] <= 2
    assert manifest["assets"][0]["license"] == "CC0"
    assert manifest["assets"][0]["source_url"] == "urn:original:test-still"
    assert manifest["scenes"][0]["asset_id"] == "original"
    assert (
        manifest["outputs"]["video.mp4"]["sha256"]
        == hashlib.sha256(video.read_bytes()).hexdigest()
    )
    assert "तकनीकी परीक्षण" in (video.parent / "captions.srt").read_text(
        encoding="utf-8"
    )
    assert "Noto Sans Devanagari" in (video.parent / "captions.ass").read_text(
        encoding="utf-8"
    )
    assert set(path.name for path in video.parent.iterdir()) == set(render.OUTPUT_NAMES)
    for name, digest in before.items():
        assert hashlib.sha256((base / name).read_bytes()).hexdigest() == digest
    # Source pixels are dark everywhere. Bright bottom pixels prove captions were
    # actually burned into the video, rather than only creating a sidecar file.
    with Image.open(video.parent / "thumbnail.png") as thumbnail:
        bottom = np.asarray(thumbnail.convert("RGB"))[thumbnail.height // 2 :]
        assert np.count_nonzero(np.all(bottom > 210, axis=2)) > 20


def test_policy_rejection_precedes_media_commands(
    narrated_fixture, tmp_path, monkeypatch
):
    base, episode = narrated_fixture
    bad = episode.model_copy(update={"editorial_reviewed": False})

    def unexpected_probe(*args, **kwargs):
        pytest.fail("media was probed before policy validation")

    monkeypatch.setattr(render, "probe_media", unexpected_probe)
    with pytest.raises(ValueError, match="editorial review"):
        render.render_episode(bad, base, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_duration_mismatch_does_not_render(narrated_fixture, tmp_path):
    base, episode = narrated_fixture
    payload = episode.model_dump()
    payload["scenes"][-1]["end_seconds"] += 2
    bad = Episode.model_validate(payload)
    with pytest.raises(ValueError, match="actual supplied narration duration"):
        render.render_episode(bad, base, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_nested_mutation_is_revalidated_before_media(
    narrated_fixture, tmp_path, monkeypatch
):
    base, original = narrated_fixture
    episode = original.model_copy(deep=True)
    episode.scenes.append(episode.scenes[0].model_copy(deep=True))

    def unexpected_probe(*args, **kwargs):
        pytest.fail("media was probed before validating a mutated model")

    monkeypatch.setattr(render, "probe_media", unexpected_probe)
    with pytest.raises(ValueError, match="duplicate IDs"):
        render.render_episode(episode, base, tmp_path / "result")
    assert not (tmp_path / "result").exists()


def test_stale_output_and_input_collisions_preserve_files(narrated_fixture, tmp_path):
    base, episode = narrated_fixture
    stale = tmp_path / "stale"
    stale.mkdir()
    sentinel = stale / "video.mp4"
    sentinel.write_bytes(b"existing user video")
    with pytest.raises(ValueError, match="not empty"):
        render.render_episode(episode, base, stale)
    assert sentinel.read_bytes() == b"existing user video"
    assert not (stale / ".render.lock").exists()
    with pytest.raises(ValueError, match="contains an input"):
        render.render_episode(episode, base, base)
    assert (base / "narration.wav").exists()


@pytest.mark.parametrize("kind,preview", [("silence", True), ("tone", False)])
def test_silent_or_tone_only_narration_is_not_production(
    narrated_fixture, tmp_path, kind, preview
):
    base, episode = narrated_fixture
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    shutil.copyfile(base / "still.png", fixture / "still.png")
    audio_filter = (
        "anullsrc=r=48000:cl=mono"
        if kind == "silence"
        else "sine=frequency=440:sample_rate=48000"
    )
    subprocess.run(
        [
            "ffmpeg",
            "-nostdin",
            "-v",
            "error",
            "-n",
            "-f",
            "lavfi",
            "-i",
            audio_filter,
            "-t",
            str(episode.duration_seconds),
            str(fixture / "narration.wav"),
        ],
        check=True,
        capture_output=True,
    )
    payload = episode.model_dump()
    payload["preview"] = preview
    if not preview:
        payload["sources"] = [
            {
                "id": "s1",
                "title": "Reviewed test passage",
                "passage": "Fixture text.",
                "verified": True,
            }
        ]
        payload["claims"] = [
            {
                "id": "c1",
                "text": "Fixture text.",
                "source_ids": ["s1"],
                "reviewed": True,
            }
        ]
        for scene in payload["scenes"]:
            scene["claim_ids"] = ["c1"]
    supplied = Episode.model_validate(payload)
    with pytest.raises(ValueError, match="silent|tone-only"):
        render.render_episode(supplied, fixture, tmp_path / "output")
    assert list((tmp_path / "output").iterdir()) == []


def test_failed_media_build_leaves_no_partial_deliverables(
    narrated_fixture, tmp_path, monkeypatch
):
    base, episode = narrated_fixture

    def failing_concat(*args, **kwargs):
        raise RuntimeError("diagnosed concat failure")

    monkeypatch.setattr(render, "_concat_cpu", failing_concat)
    with pytest.raises(RuntimeError, match="diagnosed concat failure"):
        render.render_episode(episode, base, tmp_path / "output")
    assert list((tmp_path / "output").iterdir()) == []
