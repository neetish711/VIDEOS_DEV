"""Behavioral checks for editorial/rights gates and fixture isolation."""

import copy
import json
from pathlib import Path

import pytest
from pydantic import ValidationError

from app.services.devotional.contracts import Episode, load_episode, resolve_input
from app.services.devotional.policy import validate_inputs
from app.services.devotional.state import EpisodeState, transition


@pytest.fixture
def fixture_payload(tmp_path: Path) -> dict:
    (tmp_path / "narration.wav").write_bytes(b"local narration fixture")
    (tmp_path / "still.png").write_bytes(b"local asset fixture")
    return {
        "episode_id": "reviewed-example",
        "title": "A reviewed sample",
        "language": "hinglish",
        "audio_path": "narration.wav",
        "sources": [
            {"id": "source-1", "title": "Source title", "passage": "A cited passage", "verified": True}
        ],
        "claims": [
            {"id": "claim-1", "text": "A reviewed statement", "source_ids": ["source-1"], "reviewed": True}
        ],
        "assets": [
            {
                "id": "asset-1", "path": "still.png", "source_url": "https://museum.example/item/1",
                "license": "CC0-1.0", "commercial_use": True, "reviewed": True,
            }
        ],
        "scenes": [
            {
                "id": "scene-1", "asset_id": "asset-1", "narration": "A reviewed statement",
                "claim_ids": ["claim-1"], "start_seconds": 0.0, "end_seconds": 2.0,
            }
        ],
        "editorial_reviewed": True,
    }


def test_reviewed_fixture_passes_and_json_loads(fixture_payload, tmp_path):
    path = tmp_path / "episode.json"
    path.write_text(json.dumps(fixture_payload), encoding="utf-8")
    episode = load_episode(path)
    assert episode.duration_seconds == 2.0
    assert validate_inputs(episode, tmp_path) is None


@pytest.mark.parametrize(
    ("collection", "field", "value", "message"),
    [
        (None, "editorial_reviewed", False, "editorial review"),
        (None, "budget_usd", 0.01, "budget_usd=0"),
        ("claims", "reviewed", False, "claim claim-1 requires editorial"),
        ("sources", "verified", False, "unverified source"),
        ("assets", "license", "CC-BY-NC-4.0", "unsupported rights"),
        ("assets", "license", "unknown", "unsupported rights"),
        ("assets", "commercial_use", False, "commercial use"),
        ("assets", "reviewed", False, "rights and provenance review"),
        ("assets", "source_url", "a copied image", "source URL"),
        ("assets", "sacred", True, "sacred-depiction approval"),
    ],
)
def test_review_and_rights_gates(fixture_payload, tmp_path, collection, field, value, message):
    payload = copy.deepcopy(fixture_payload)
    target = payload if collection is None else payload[collection][0]
    target[field] = value
    with pytest.raises(ValueError, match=message):
        validate_inputs(Episode.model_validate(payload), tmp_path)


def test_sacred_asset_requires_separate_approval(fixture_payload, tmp_path):
    fixture_payload["assets"][0].update(sacred=True, sacred_approved=True)
    validate_inputs(Episode.model_validate(fixture_payload), tmp_path)


@pytest.mark.parametrize(
    ("collection", "field", "value", "message"),
    [
        ("scenes", "asset_id", "missing", "unknown asset"),
        ("scenes", "claim_ids", ["missing"], "unknown claim"),
        ("claims", "source_ids", ["missing"], "unknown source"),
        ("scenes", "claim_ids", [], "reviewed sourced claim"),
    ],
)
def test_references_must_be_supported(fixture_payload, tmp_path, collection, field, value, message):
    fixture_payload[collection][0][field] = value
    with pytest.raises(ValueError, match=message):
        validate_inputs(Episode.model_validate(fixture_payload), tmp_path)


def test_technical_preview_can_be_claim_free_but_has_same_rights_gates(fixture_payload, tmp_path):
    fixture_payload.update(preview=True, sources=[], claims=[])
    fixture_payload["scenes"][0].update(claim_ids=[], narration="This is a technical render preview.")
    fixture_payload["assets"][0]["source_url"] = "urn:devotional-studio:original-demo-art"
    episode = Episode.model_validate(fixture_payload)
    validate_inputs(episode, tmp_path)
    fixture_payload["assets"][0]["reviewed"] = False
    with pytest.raises(ValueError, match="rights and provenance review"):
        validate_inputs(Episode.model_validate(fixture_payload), tmp_path)
    fixture_payload["assets"][0]["reviewed"] = True
    fixture_payload["editorial_reviewed"] = False
    with pytest.raises(ValueError, match="editorial review"):
        validate_inputs(Episode.model_validate(fixture_payload), tmp_path)


def test_preview_does_not_bypass_claim_review(fixture_payload, tmp_path):
    fixture_payload["preview"] = True
    fixture_payload["claims"][0]["reviewed"] = False
    with pytest.raises(ValueError, match="claim claim-1 requires editorial"):
        validate_inputs(Episode.model_validate(fixture_payload), tmp_path)


@pytest.mark.parametrize("collection", ["sources", "claims", "assets", "scenes"])
def test_duplicate_identifiers_are_rejected(fixture_payload, collection):
    fixture_payload[collection].append(copy.deepcopy(fixture_payload[collection][0]))
    with pytest.raises(ValidationError, match="duplicate IDs"):
        Episode.model_validate(fixture_payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("start_seconds", -1), ("start_seconds", float("nan")),
        ("end_seconds", float("inf")), ("end_seconds", 0),
        ("start_seconds", 0.2),
    ],
)
def test_invalid_scene_timing_is_rejected(fixture_payload, field, value):
    fixture_payload["scenes"][0][field] = value
    with pytest.raises(ValidationError):
        Episode.model_validate(fixture_payload)


@pytest.mark.parametrize("start", [1.9, 2.1])
def test_timeline_gaps_and_overlaps_are_rejected(fixture_payload, start):
    fixture_payload["scenes"].append({
        "id": "scene-2", "asset_id": "asset-1", "narration": "Second scene",
        "claim_ids": ["claim-1"], "start_seconds": start, "end_seconds": 4.0,
    })
    with pytest.raises(ValidationError, match="ordered and contiguous"):
        Episode.model_validate(fixture_payload)


@pytest.mark.parametrize(
    ("field", "value"),
    [
        ("episode_id", "../../escape"), ("episode_id", ""), ("language", "unsupported"),
        ("width", 641), ("height", 359), ("width", 10000), ("fps", "24"),
        ("editorial_reviewed", "yes"), ("budget_usd", float("nan")),
        ("extra_option", True),
    ],
)
def test_strict_schema_rejects_unsafe_or_ambiguous_fields(fixture_payload, field, value):
    fixture_payload[field] = value
    with pytest.raises(ValidationError):
        Episode.model_validate(fixture_payload)


def test_json_duplicate_keys_are_rejected(tmp_path):
    path = tmp_path / "duplicate.json"
    path.write_text('{"episode_id":"first","episode_id":"second"}', encoding="utf-8")
    with pytest.raises(ValueError, match="duplicate key"):
        load_episode(path)


@pytest.mark.parametrize("relative", ["../outside.wav", "/etc/passwd", "C:/outside.wav", r"..\outside.wav", "missing.wav", ".", ""])
def test_input_paths_cannot_escape_or_be_missing(tmp_path, relative):
    with pytest.raises(ValueError):
        resolve_input(tmp_path, relative)


def test_symlink_escape_is_rejected_but_internal_link_is_safe(tmp_path):
    fixture = tmp_path / "fixture"
    fixture.mkdir()
    outside = tmp_path / "outside.wav"
    outside.write_bytes(b"outside")
    (fixture / "escape.wav").symlink_to(outside)
    with pytest.raises(ValueError, match="escapes"):
        resolve_input(fixture, "escape.wav")
    internal = fixture / "inside.wav"
    internal.write_bytes(b"inside")
    (fixture / "internal-link.wav").symlink_to(internal)
    assert resolve_input(fixture, "internal-link.wav") == internal.resolve()


def test_audio_file_gate_uses_same_fixture_isolation(fixture_payload, tmp_path):
    fixture_payload["audio_path"] = "../secret.wav"
    with pytest.raises(ValueError, match="parent traversal"):
        validate_inputs(Episode.model_validate(fixture_payload), tmp_path)


def test_manifest_lifecycle_reaches_approval_without_publishing():
    state = transition("SCENES_READY", "RENDERED")
    state = transition(state, EpisodeState.MEDIA_QA_PASSED)
    state = transition(state, EpisodeState.AWAITING_APPROVAL)
    assert state == EpisodeState.AWAITING_APPROVAL
    assert transition(state, EpisodeState.APPROVED) == EpisodeState.APPROVED
    with pytest.raises(ValueError, match="unknown"):
        transition(EpisodeState.APPROVED, "PUBLISHED")


@pytest.mark.parametrize(
    ("before", "after"),
    [("PICKED", "APPROVED"), ("RENDERED", "APPROVED"), ("PAUSED", "RENDERED"), ("APPROVED", "RENDERED")],
)
def test_lifecycle_cannot_skip_gates(before, after):
    with pytest.raises(ValueError, match="illegal"):
        transition(before, after)


def test_regeneration_and_failure_require_earlier_gates():
    assert transition("RENDERED", "REGENERATE_SCENE") == EpisodeState.REGENERATE_SCENE
    assert transition("REGENERATE_SCENE", "STORYBOARDED") == EpisodeState.STORYBOARDED
    assert transition("RENDERED", "REGENERATE_VOICE") == EpisodeState.REGENERATE_VOICE
    assert transition("REGENERATE_VOICE", "QA_PASSED") == EpisodeState.QA_PASSED
    assert transition("RENDERED", "FAILED") == EpisodeState.FAILED
    assert transition("FAILED", "PICKED") == EpisodeState.PICKED
