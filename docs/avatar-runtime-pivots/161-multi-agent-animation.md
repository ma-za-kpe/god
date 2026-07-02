# Avatar Runtime Pivot: Multi-Agent Animation Research

Parent issue: #91
Track issue: #161
Branch: `docs/161-multi-agent-animation-pivot`
Status: research and offline proof branch

## Decision Test

This track succeeds if it turns GOD episode state into useful offline animation planning or highlight assets without pretending to solve live speech-driven embodiment.

It does not pass the original `/one` goal unless a candidate demonstrates low-latency, live, controllable avatar speech. The expected use case is asynchronous production support.

## Upstream Fit

Current animation-agent research focuses on long-form animation generation, storyboards, director/reviewer agents, candidate clip generation, and multimodal production workflows. These systems are valuable for planning and highlights, but they are not proven replacements for a live avatar renderer.

Primary references:

- https://arxiv.org/abs/2508.18781
- https://animaker-dev.github.io/
- https://github.com/hitsz-tmg/anim-director
- https://arxiv.org/abs/2602.20664
- https://github.com/ChrisChen667788/wind-comic

## Current Code Leverage

- GOD already has dialogue turns, utterance IDs, agent identities, snapshot state, and voice metadata.
- The current `/one` work provides proof discipline: generated/offline clips cannot count as live speaking proof.
- Runtime transcripts and observer snapshots can become structured input for storyboards, shot lists, emotional beats, and recap generation.
- Existing proof artifacts can be used as acceptance evidence for generated highlights, but not as substitutes for live avatar control.

## Features To Capitalize On

- Director/reviewer-agent patterns for scene planning and quality review.
- Storyboard and shot-list generation from text prompts or multimodal inputs.
- Multi-candidate clip generation and selection.
- Character consistency and visual reference workflows.
- Post-production assembly for recaps, trailers, cutaways, and highlight reels.
- Research rubrics that can improve our own showrunner evaluation loops.

## Unique Use Case

Offline show production: episode storyboards, cold opens, visual gags, trailers, recaps, generated cutaways, and post-produced highlights after a live debate event.

This is the candidate for "make the show richer after or around the live stream," not "make the mouth move live."

## Proposed Pipeline

1. Export GOD episode state:
   - transcript;
   - speaker turns;
   - agent identities;
   - emotional beats;
   - important events;
   - visual constraints;
   - available avatar assets.
2. Convert that state into a storyboard package:
   - scene summary;
   - shot list;
   - character references;
   - action beats;
   - timing targets;
   - quality rubric.
3. Run one selected research pipeline or local adapter.
4. Produce offline assets:
   - storyboard images;
   - short generated cutaways;
   - recap script;
   - highlight candidates.
5. Archive generated assets separately from live `/one` proof.

## Agent Command Contract

This track should use batch job specs rather than live avatar commands:

```json
{
  "episode_id": "alphabet-live-test-001",
  "mode": "offline_highlight",
  "inputs": {
    "transcript_path": "artifacts/episode/transcript.json",
    "agent_manifest_path": "artifacts/episode/agents.json",
    "proof_video_path": "artifacts/episode/live-proof.mp4"
  },
  "outputs": {
    "storyboard": true,
    "recap": true,
    "cutaways": 3
  },
  "guardrails": {
    "must_not_replace_live_avatar_proof": true,
    "requires_human_review_before_stream_insert": true
  }
}
```

## Implementation Plan

1. Build a candidate matrix: runnable code, license, input format, output format, GPU needs, and controllability.
2. Select one runnable open pipeline for a minimal offline proof.
3. Add a GOD transcript-to-storyboard adapter.
4. Generate one offline storyboard or highlight package from an actual `/one` transcript.
5. Document whether the candidate is implementation-ready or only research input.

## Validation

- Proof must label outputs as offline/generated.
- Live `/one` proof cannot depend on this track.
- Candidate must document runnable-code status and license.
- Generated assets must be archived with inputs and prompts for reproducibility.

## Merge Gate

Merge only as an offline production-support path. Do not merge as the primary avatar runtime unless a candidate unexpectedly demonstrates live, low-latency, controllable speech-driven avatar output with proof.
