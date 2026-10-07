# Devotional AI Video Studio

This repository contains the first local rendering starter for the studio described in your [final architecture](docs/devotional/Devotional_AI_Video_Studio_Final_Architecture_v1.docx) and [research report](docs/devotional/deep-research-report.md). It combines an isolated devotional layer with the MIT-licensed [MoneyPrinterTurbo](https://github.com/harry0703/MoneyPrinterTurbo) media backbone, imported at `f20e0d602fdc73a0e5eb45a87844c301d22b5d80`. Upstream application code, dependency declarations, lockfile, and licence are retained.

The starter renders reviewed local still images against a supplied narration recording. It produces an H.264/AAC MP4, captions, a thumbnail, and a manifest without calling generation APIs. It also includes an offline technical demo. The full sourced story → Hinglish writing → English adaptation → production TTS workflow remains on the [roadmap](docs/devotional/ROADMAP.md).

## Set up and render

Use the existing checkout in the isolated cloud environment. Worktrees are unnecessary unless explicitly requested.

```bash
cd /workspace/VIDEOS_DEV
bash scripts/cloud_setup.sh
source scripts/devotional_env.sh
uv run --frozen python -m app.services.devotional.cli doctor
uv run --frozen python -m app.services.devotional.cli demo
```

Setup uses pinned Python 3.11 and `uv sync --frozen`; caches and managed Python live under `/workspace/.cache`. The host needs `uv`, FFmpeg/ffprobe, fontconfig, and Noto Sans Devanagari. FFmpeg must include `libx264`, AAC, `zoompan`, `ass`, and `loudnorm`; the demo additionally needs its `flite` filter. `doctor` checks the actual tools. No GPU, Redis server, database service, or credentials are needed for this local workflow.

Each demo gets a fresh run directory under `storage/devotional/runs/`:

```text
<run-id>/
├── inputs/episode.json
├── inputs/narration.wav
├── inputs/scene-*.png
└── render/
    ├── video.mp4
    ├── captions.srt
    ├── captions.ass
    ├── thumbnail.png
    └── manifest.json
```

The demo uses original CC0 abstract artwork and offline English `flite` speech about the production workflow. It is labelled a technical preview. It demonstrates the media pipeline; it does not establish devotional story quality, Hinglish pronunciation, or publication readiness. Every output still requires a person to watch and listen before use.

Render a portrait or HD preview with:

```bash
uv run --frozen python -m app.services.devotional.cli demo --portrait
uv run --frozen python -m app.services.devotional.cli demo --hd
```

Default output is 1280×720 at 24 fps; `--portrait` selects 720×1280. `--hd` selects 1920×1080, or 1080×1920 with `--portrait`. Use `--directory storage/devotional/runs/my-new-run` to choose a new run directory. Reusing existing inputs or nonempty output directories is rejected to preserve earlier renders.

## Supply a reviewed episode

Create an episode directory with `episode.json`, the complete recorded narration, and reviewed local still images. Narration is the timeline master: scene intervals must be ordered, contiguous, begin at zero, and match the measured audio duration within the renderer's tolerance. Each scene's `narration` must contain the words actually spoken during that interval.

This illustrates the input shape. Replace the sample text, filenames, provenance, and timings with your own reviewed materials. Set review flags to `true` only after the corresponding review has happened; the program checks these recorded assertions and does not independently verify scripture interpretation or rights.

```json
{
  "episode_id": "ep001-hinglish",
  "title": "Your reviewed episode title",
  "language": "hinglish",
  "audio_path": "audio/narration.wav",
  "sources": [
    {
      "id": "source01",
      "title": "Your reviewed source edition and passage reference",
      "passage": "The verified passage supporting the narration",
      "verified": true,
      "tradition": "The named tradition or source context"
    }
  ],
  "claims": [
    {
      "id": "claim01",
      "text": "The reviewed factual claim supported by source01",
      "source_ids": ["source01"],
      "reviewed": true
    }
  ],
  "assets": [
    {
      "id": "art01",
      "path": "assets/art01.png",
      "source_url": "https://example.org/replace-with-the-specific-rights-record",
      "license": "CC0",
      "commercial_use": true,
      "reviewed": true,
      "sacred": false,
      "sacred_approved": false
    }
  ],
  "scenes": [
    {
      "id": "scene01",
      "asset_id": "art01",
      "narration": "The exact reviewed narration in your recording",
      "claim_ids": ["claim01"],
      "start_seconds": 0.0,
      "end_seconds": 12.0
    }
  ],
  "width": 1280,
  "height": 720,
  "fps": 24,
  "budget_usd": 0,
  "editorial_reviewed": true,
  "preview": false
}
```

Paths are relative to the directory containing `episode.json`. Absolute paths, parent traversal, and symlinks escaping that directory are rejected. This starter accepts reviewed CC0/public-domain stills only. A source URL must identify the actual reproduction and rights record; original artwork can instead use a stable `urn:` provenance identifier. Sacred depictions additionally require `sacred: true` and `sacred_approved: true` after review.

Validate and render your package:

```bash
source scripts/devotional_env.sh
uv run --frozen python -m app.services.devotional.cli validate --episode storage/devotional/episodes/ep001/episode.json
uv run --frozen python -m app.services.devotional.cli render --episode storage/devotional/episodes/ep001/episode.json
```

`render` creates a new run output by default. You may provide `--output` pointing to an empty directory outside the inputs. The renderer applies still-image motion, reuses upstream concatenation, burns ASS captions, exports sidecar SRT/ASS, checks media properties, and records input/output hashes and review status in the manifest. Caption chunks are distributed within supplied scene intervals; word-level alignment is a later milestone. Listen to the finished video and check the caption timing yourself.

Each render has one language, one recording, and one timeline. Make a separate episode JSON and independently narrated English adaptation to render English; automatically translating the Hinglish story, generating TTS, and deriving timestamps are not yet implemented.

## Validate the starter

```bash
source scripts/devotional_env.sh
uv run --frozen python -m pytest test/devotional -q
```

The required starter checks are input-contract/policy tests, `doctor`, and a successful offline demo whose manifest confirms media validation. A human playback review is necessary before judging the video useful. Production TTS benchmarks, semantic editorial review, provider quotas, Telegram review, and YouTube upload are later checks tied to their corresponding roadmap milestones.

The creative rule remains **respect → factual integrity → story/retention → humor**. Humor should come from situations and observations, while reviewed source passages and named traditions support claims. Budget remains zero for the implemented workflow, and no upload or external messaging occurs.
