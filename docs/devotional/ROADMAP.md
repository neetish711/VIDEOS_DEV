# Devotional AI Video Studio roadmap

The [final architecture](Devotional_AI_Video_Studio_Final_Architecture_v1.docx) sets the product direction; the [research report](deep-research-report.md) recommends the MoneyPrinterTurbo foundation and details implementation options. Attached proposals describe intended product behavior, rather than commands to execute automatically. Provider allowances, commercial output rights, and external API requirements must be verified when those integrations are built.

## Current starter

The repository now includes MoneyPrinterTurbo at commit `f20e0d602fdc73a0e5eb45a87844c301d22b5d80`, preserved upstream, plus a separate `app/services/devotional/` package and cloud setup scripts. The local workflow uses Python 3.11, frozen dependency installation, FFmpeg, and Noto Sans Devanagari. Normal rendering requires CPU compute only.

Implemented capabilities:

- Strict episode JSON contracts, contiguous scene timings, and fixture-relative path validation.
- Recorded review gates for source/claim references, CC0/public-domain asset provenance, commercial use, sacred depictions, and zero budget.
- Supplied narration as the master timeline; still-image motion, upstream concatenation, captions, thumbnail, deterministic media checks, and a hashed manifest.
- A fresh-run offline technical demo with original abstract artwork and English `flite` narration; 16:9 and 9:16, at 720p or 1080p.
- Local lifecycle transition rules and focused contract/policy tests.

These capabilities establish a local render foundation. They do not complete M1 from the architecture or the report's dual-language acceptance test. The starter records reviewers' assertions; it does not perform semantic religious/editorial review, legal rights verification, speech recognition, or a production voice benchmark. The current CLI exposes `doctor`, `validate`, `render`, and `demo`; the proposed `create --topic ... --languages hinglish,en` command is a future deliverable.

## Build the first watchable devotional episode

| Next milestone | Deliverable | Acceptance evidence |
|---|---|---|
| Curated source corpus and evidence pack | Passage retrieval with edition, tradition, provenance, and claim IDs | Every factual narration claim maps to a reviewed supporting passage; differing traditions are labelled |
| Writer and editorial pass | Story angle, natural Hinglish, respectful situational humor, separate English adaptation | A reviewer checks source meaning, tone, hook, pacing, and ending in both languages |
| Production narration adapter | Voice provider interface, pronunciation dictionary, audio cache, and benchmark harness | A blind 30–45-second Hinglish test checks switching, names, emotion, pauses, and comic timing; commercial output terms are documented |
| Narration timing | Sentence/word alignment from approved recordings, with faster-whisper as an alignment aid or fallback | Scene intervals and captions follow measured narration; a human verifies representative hard passages |
| External asset adapters | Curated CC0/public-domain ingestion with per-reproduction rights metadata | Every selected asset has provenance, permitted commercial use, and sacred-style review when applicable |
| First complete episode | Approximately 90–150 seconds, 12–20 scenes, reviewed narration, local motion, captions, and optional licensed audio bed | A viewer finds the Hinglish episode watchable at zero video-generation spend; an English version is separately authored and narrated |

Use the creative hierarchy **respect → factual integrity → story/retention → humor** at each stage. Never invent a religious fact for a joke. Keep revered figures dignified and prefer reviewed traditional art for sacred depictions. Fix writing, narration, and pacing before expanding automation.

The zero-budget default concerns direct provider expenditure. Existing compute, storage, connectivity, and electricity still have costs. Optional paid TTS requires an explicit budget choice supported by the voice benchmark; paid video generation and automatic top-ups remain disabled by default.

## Extend only after the local episode works

| Later milestone | Deliverable | Acceptance evidence |
|---|---|---|
| Optional scene-provider router | Local motion fallback, bounded free-provider usage, per-scene cost ledger, and optional Wan backend | Exhausted quotas, provider errors, or unavailable GPU never prevent completion; legitimate account allowances and publishability are checked before use |
| Targeted regeneration | Input hashes and cached scene/voice outputs with dependency-aware invalidation | Replacing one scene preserves unrelated audio and scene outputs; retries do not duplicate paid work |
| Telegram review | Preview, title, thumbnail, sources, cost, approve/reject, and scoped regeneration controls | Approval identifies the exact content hash; editing content invalidates approval; messaging happens only when integration is explicitly authorized |
| YouTube private upload and scheduling | Official API integration with secure OAuth, durable publish jobs, and duplicate-upload prevention | No upload without explicit human approval bound to the rendered content; scheduling and disclosure settings are checked against current API requirements |
| Independent Shorts | Fresh hooks and narration units using reviewed research/assets, reframed for 9:16 | Each Short works as its own story and readable portrait edit, rather than an arbitrary long-form crop |
| Weekly metrics | SQLite or file-based collection of topic, hook, retention, and thumbnail outcomes | A weekly report identifies specific changes to try before increasing channel count or output volume |

GPU models and external services are optional. Wan requires a compatible separately provisioned machine and verified model/licence terms; it is not installed by the starter. Ollama is an optional local writing backend. Redis, PostgreSQL, Kubernetes, and an always-on server are not required for the planned pilot. Keep credentials out of repository files, manifests, generated instructions, and LLM inputs.

## Review gates before publishing

Publication remains an explicit human decision during the pilot. A render succeeding establishes technical properties, rather than the quality or meaning of its content. Before approving a devotional episode, check its source support and traditions, respect and humor, rights/provenance, sacred depictions, pronunciation, pacing, captions, final playback, title, and thumbnail.

The starter has no Telegram or YouTube integration and does not publish. Future integrations should preserve this authority and bind approval to the exact content being sent or uploaded.
