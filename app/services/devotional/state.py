"""Deterministic local lifecycle; publication stages are intentionally absent."""

from enum import Enum


class EpisodeState(str, Enum):
    PICKED = "PICKED"
    RESEARCHED = "RESEARCHED"
    SCRIPTED = "SCRIPTED"
    QA_PASSED = "QA_PASSED"
    NARRATED = "NARRATED"
    STORYBOARDED = "STORYBOARDED"
    ASSETS_READY = "ASSETS_READY"
    SCENES_READY = "SCENES_READY"
    RENDERED = "RENDERED"
    MEDIA_QA_PASSED = "MEDIA_QA_PASSED"
    AWAITING_APPROVAL = "AWAITING_APPROVAL"
    APPROVED = "APPROVED"
    REJECTED = "REJECTED"
    REGENERATE_SCENE = "REGENERATE_SCENE"
    REGENERATE_VOICE = "REGENERATE_VOICE"
    FAILED = "FAILED"
    PAUSED = "PAUSED"


Stage = EpisodeState

_FORWARD = (
    EpisodeState.PICKED,
    EpisodeState.RESEARCHED,
    EpisodeState.SCRIPTED,
    EpisodeState.QA_PASSED,
    EpisodeState.NARRATED,
    EpisodeState.STORYBOARDED,
    EpisodeState.ASSETS_READY,
    EpisodeState.SCENES_READY,
    EpisodeState.RENDERED,
    EpisodeState.MEDIA_QA_PASSED,
    EpisodeState.AWAITING_APPROVAL,
    EpisodeState.APPROVED,
)

_ALLOWED: dict[EpisodeState, set[EpisodeState]] = {
    current: {following} for current, following in zip(_FORWARD, _FORWARD[1:])
}
for _state in _FORWARD[:-1]:
    _ALLOWED[_state].update({EpisodeState.FAILED, EpisodeState.PAUSED})
for _state in (
    EpisodeState.SCENES_READY,
    EpisodeState.RENDERED,
    EpisodeState.MEDIA_QA_PASSED,
    EpisodeState.AWAITING_APPROVAL,
):
    _ALLOWED[_state].add(EpisodeState.REGENERATE_SCENE)
for _state in _FORWARD[4:-1]:
    _ALLOWED[_state].add(EpisodeState.REGENERATE_VOICE)
_ALLOWED[EpisodeState.AWAITING_APPROVAL].add(EpisodeState.REJECTED)
_ALLOWED[EpisodeState.REJECTED] = {EpisodeState.PICKED, EpisodeState.SCRIPTED}
_ALLOWED[EpisodeState.REGENERATE_SCENE] = {EpisodeState.STORYBOARDED, EpisodeState.FAILED}
_ALLOWED[EpisodeState.REGENERATE_VOICE] = {EpisodeState.QA_PASSED, EpisodeState.FAILED}
# Resuming without persisted previous-stage evidence restarts every gate.
_ALLOWED[EpisodeState.FAILED] = {EpisodeState.PICKED}
_ALLOWED[EpisodeState.PAUSED] = {EpisodeState.PICKED}
_ALLOWED[EpisodeState.APPROVED] = set()


def transition(current: EpisodeState | str, target: EpisodeState | str) -> EpisodeState:
    """Validate a stage change; callers persist the returned state explicitly."""
    try:
        before, after = EpisodeState(current), EpisodeState(target)
    except ValueError as exc:
        raise ValueError("unknown episode lifecycle state") from exc
    if after not in _ALLOWED[before]:
        raise ValueError(f"illegal episode transition: {before.value} -> {after.value}")
    return after
