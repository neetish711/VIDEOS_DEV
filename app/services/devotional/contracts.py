"""Strict contracts for an independently reviewed, local episode fixture."""

import json
import math
from pathlib import Path, PurePosixPath, PureWindowsPath
from typing import Annotated, Literal, Self

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


Identifier = Annotated[
    str, Field(min_length=1, max_length=80, pattern=r"^[A-Za-z0-9][A-Za-z0-9_-]*$")
]
NonemptyString = Annotated[str, Field(min_length=1)]
Seconds = Annotated[float, Field(ge=0, allow_inf_nan=False)]


class Contract(BaseModel):
    model_config = ConfigDict(
        extra="forbid", strict=True, str_strip_whitespace=True, validate_assignment=True
    )


class Source(Contract):
    id: Identifier
    title: NonemptyString
    passage: NonemptyString
    verified: bool = False
    tradition: NonemptyString = "unspecified"


class Claim(Contract):
    id: Identifier
    text: NonemptyString
    source_ids: list[Identifier] = Field(min_length=1)
    reviewed: bool = False

    @field_validator("source_ids")
    @classmethod
    def unique_sources(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("source_ids must not contain duplicates")
        return value


class Asset(Contract):
    id: Identifier
    path: NonemptyString
    source_url: NonemptyString
    license: NonemptyString
    commercial_use: bool = False
    reviewed: bool = False
    sacred: bool = False
    sacred_approved: bool = False


class Scene(Contract):
    id: Identifier
    asset_id: Identifier
    narration: NonemptyString
    claim_ids: list[Identifier]
    start_seconds: Seconds
    end_seconds: Seconds

    @field_validator("claim_ids")
    @classmethod
    def unique_claims(cls, value: list[str]) -> list[str]:
        if len(set(value)) != len(value):
            raise ValueError("claim_ids must not contain duplicates")
        return value

    @model_validator(mode="after")
    def positive_duration(self) -> Self:
        if self.end_seconds <= self.start_seconds:
            raise ValueError("scene end_seconds must be greater than start_seconds")
        return self


class Episode(Contract):
    episode_id: Identifier
    title: NonemptyString
    language: Literal["hinglish", "en"]
    audio_path: NonemptyString
    sources: list[Source]
    claims: list[Claim]
    assets: list[Asset] = Field(min_length=1)
    scenes: list[Scene] = Field(min_length=1)
    width: int = Field(default=1280, ge=320, le=3840)
    height: int = Field(default=720, ge=180, le=2160)
    fps: int = Field(default=24, ge=12, le=60)
    budget_usd: float = Field(default=0, ge=0, allow_inf_nan=False)
    editorial_reviewed: bool = False
    preview: bool = False

    @field_validator("width", "height")
    @classmethod
    def even_dimensions(cls, value: int) -> int:
        if value % 2:
            raise ValueError("video dimensions must be even for H.264 encoding")
        return value

    @model_validator(mode="after")
    def unique_ids_and_timeline(self) -> Self:
        for name in ("sources", "claims", "assets", "scenes"):
            entries = getattr(self, name)
            ids = [entry.id for entry in entries]
            if len(set(ids)) != len(ids):
                raise ValueError(f"{name} must not contain duplicate IDs")
        previous_end = 0.0
        for scene in self.scenes:
            if not math.isclose(
                scene.start_seconds, previous_end, rel_tol=0, abs_tol=1e-6
            ):
                raise ValueError(
                    "scenes must be ordered and contiguous, starting at 0 seconds"
                )
            previous_end = scene.end_seconds
        return self

    @property
    def duration_seconds(self) -> float:
        return self.scenes[-1].end_seconds


def _unique_json_object(pairs: list[tuple[str, object]]) -> dict[str, object]:
    result: dict[str, object] = {}
    for key, value in pairs:
        if key in result:
            raise ValueError(f"episode JSON contains a duplicate key: {key}")
        result[key] = value
    return result


def load_episode(path: Path) -> Episode:
    """Read UTF-8 JSON without silently accepting duplicate object keys."""
    try:
        payload = json.loads(
            path.read_text(encoding="utf-8"), object_pairs_hook=_unique_json_object
        )
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise ValueError(f"cannot read episode JSON from {path}: {exc}") from exc
    return Episode.model_validate(payload)


def resolve_input(base_dir: Path, relative: str) -> Path:
    """Resolve an existing fixture file without escaping its base directory.

    Both POSIX and Windows absolute/traversal spellings are rejected. Symlinks
    are permitted only when their final resolved target stays within base_dir.
    """
    if not isinstance(relative, str) or not relative.strip():
        raise ValueError("input path must be a nonempty relative path")
    if "\\" in relative or "\x00" in relative:
        raise ValueError("input path must use ordinary relative POSIX components")
    supplied = PurePosixPath(relative)
    if supplied.is_absolute() or PureWindowsPath(relative).is_absolute():
        raise ValueError("input path must be relative to the episode fixture")
    if ".." in supplied.parts:
        raise ValueError("input path must not contain parent traversal")
    try:
        root = base_dir.resolve(strict=True)
        resolved = (root / relative).resolve(strict=True)
    except (OSError, RuntimeError) as exc:
        raise ValueError(f"input file is unavailable: {relative}") from exc
    if not root.is_dir():
        raise ValueError("episode fixture base must be a directory")
    if not resolved.is_relative_to(root):
        raise ValueError(f"input path escapes the episode fixture: {relative}")
    if not resolved.is_file():
        raise ValueError(f"input path is not a regular file: {relative}")
    return resolved
