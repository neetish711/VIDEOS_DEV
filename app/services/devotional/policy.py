"""Pre-render gates for reviewed local media.

The fixture records review assertions; this module checks those assertions and
references, rather than claiming to independently verify external rights or
religious interpretation. The starter supports CC0 and public-domain stills.
"""

from pathlib import Path
from urllib.parse import urlparse

from .contracts import Episode, resolve_input


_SUPPORTED_LICENSES = {"cc0", "cc0-1.0", "cc0 1.0", "public-domain", "public domain"}


def _has_provenance(value: str) -> bool:
    parsed = urlparse(value)
    if parsed.scheme in {"http", "https"}:
        return bool(parsed.netloc)
    # Original locally authored demo media can use a stable, nonsecret URN.
    return parsed.scheme == "urn" and bool(parsed.path.strip())


def validate_inputs(episode: Episode, base_dir: Path) -> None:
    """Raise ValueError if an episode cannot enter the local render workflow.

    Preview means the reviewer attests claim-free narration is only a technical
    demonstration. Preview never relaxes editorial, asset, sacred-use or budget
    gates, and the renderer must label its outputs as a technical preview.
    """
    if not episode.editorial_reviewed:
        raise ValueError("episode requires editorial review before rendering")
    if episode.budget_usd != 0:
        raise ValueError("this starter requires budget_usd=0; paid providers are not implemented")

    sources = {source.id: source for source in episode.sources}
    claims = {claim.id: claim for claim in episode.claims}
    assets = {asset.id: asset for asset in episode.assets}
    for claim in episode.claims:
        for source_id in claim.source_ids:
            if source_id not in sources:
                raise ValueError(f"claim {claim.id} cites an unknown source: {source_id}")

    # Every scene's references are checked before any media file is consumed.
    referenced_assets: set[str] = set()
    for scene in episode.scenes:
        if scene.asset_id not in assets:
            raise ValueError(f"scene {scene.id} references an unknown asset: {scene.asset_id}")
        referenced_assets.add(scene.asset_id)
        if not scene.claim_ids and not episode.preview:
            raise ValueError(f"scene {scene.id} requires at least one reviewed sourced claim")
        for claim_id in scene.claim_ids:
            if claim_id not in claims:
                raise ValueError(f"scene {scene.id} references an unknown claim: {claim_id}")
            claim = claims[claim_id]
            if not claim.reviewed:
                raise ValueError(f"claim {claim_id} requires editorial review")
            for source_id in claim.source_ids:
                if not sources[source_id].verified:
                    raise ValueError(f"claim {claim_id} cites an unverified source: {source_id}")

    for asset_id in sorted(referenced_assets):
        asset = assets[asset_id]
        if asset.license.casefold() not in _SUPPORTED_LICENSES:
            raise ValueError(f"asset {asset_id} has unsupported rights; use reviewed CC0/public-domain media")
        if not asset.commercial_use:
            raise ValueError(f"asset {asset_id} is not approved for commercial use")
        if not _has_provenance(asset.source_url):
            raise ValueError(f"asset {asset_id} requires a source URL or original-media URN")
        if not asset.reviewed:
            raise ValueError(f"asset {asset_id} requires rights and provenance review")
        if asset.sacred and not asset.sacred_approved:
            raise ValueError(f"asset {asset_id} requires sacred-depiction approval")

    resolve_input(base_dir, episode.audio_path)
    for asset_id in sorted(referenced_assets):
        resolve_input(base_dir, assets[asset_id].path)
