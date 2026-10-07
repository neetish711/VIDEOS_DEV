# VIDEOS_DEV


Devotional AI Video Studio — a local, zero-budget-first video engine based on MoneyPrinterTurbo and the supplied devotional architecture.

The current implementation renders reviewed stills and supplied spoken narration into captioned H.264/AAC videos. All application source, dependencies, tests, setup scripts, architecture documents, and upstream MIT licensing are included in this repository.

## Start here

- [Setup and usage guide](README_DEVOTIONAL.md)
- [Implementation roadmap and current limitations](docs/devotional/ROADMAP.md)
- [Pinned upstream source and licence](DEVOTIONAL_UPSTREAM.txt)
- [Final architecture](docs/devotional/Devotional_AI_Video_Studio_Final_Architecture_v1.docx)
- [Research report](docs/devotional/deep-research-report.md)

## Local setup

On Linux, install uv, FFmpeg/ffprobe, fontconfig, and Noto Sans Devanagari. FFmpeg needs H.264/AAC, libass, zoompan, and flite for the offline demo.

```bash
git clone https://github.com/neetish711/VIDEOS_DEV.git
cd VIDEOS_DEV
bash scripts/cloud_setup.sh
source scripts/devotional_env.sh
uv run --frozen python -m app.services.devotional.cli demo
```

The setup creates a Python 3.11 environment from the frozen lockfile. The demo generates an English technical preview with original abstract artwork. Use `demo --hd` for 1080p or `demo --portrait` for vertical output.

## Checks

```bash
source scripts/devotional_env.sh
uv run --frozen python -m pytest test/devotional test/services/test_video.py -q
```

Validated locally: 135 tests and 50 subtests, with actual landscape and portrait renders. Hosted CI runs the same selected test suites after installing the media tools and fonts.

## Implementation status

Working: strict episode/source/asset contracts, review and rights gates, zero-budget enforcement, supplied-audio timing, local still motion, upstream concatenation, captions, thumbnails, and provenance manifests.

Remaining: automated source retrieval and grounded story writing, natural English adaptation, production Hinglish TTS and word alignment, optional AI provider routing, Telegram approval, YouTube upload/scheduling, and analytics. This repository contains the complete source for the current working milestone; it does not yet implement every feature in the architecture.

Upstream application code and its original MIT licence are retained. The original upstream README is preserved at [docs/upstream/README.md](docs/upstream/README.md).
