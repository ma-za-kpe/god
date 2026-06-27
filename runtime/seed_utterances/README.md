# Seed Utterances

This directory contains archetype-specific audio samples used as references for zero-shot voice cloning via Fish Speech S2 / CosyVoice.

## Requirements

- Each file must be **5–15 seconds** in duration.
- Format: WAV (PCM 16-bit, 44.1 kHz mono recommended).
- Each utterance should reflect the archetype's characteristic speech patterns and personality.
- Each utterance is uniquely assigned to a single archetype.

## Placeholder Files

The `.wav` files in this directory are placeholders. They must be replaced with real recorded audio before the Avatar Genesis Pipeline can produce voice embeddings.

| File | Archetype | Suggested Content |
|------|-----------|-------------------|
| `trader.wav` | Trader | Smooth negotiation monologue with mercantile confidence |
| `hoarder.wav` | Hoarder | Possessive whisper about guarding precious things |
| `explorer.wav` | Explorer | Excited narration of discovering something new |
| `parasite.wav` | Parasite | Silky, manipulative persuasion with veiled threat |
| `cooperator.wav` | Cooperator | Warm invitation to collaborate, empathetic tone |
| `defender.wav` | Defender | Commanding declaration of protection, resolute voice |
| `philosopher.wav` | Philosopher | Measured contemplation on an abstract concept |
| `builder.wav` | Builder | Energetic description of a creation in progress |

## Usage

The `seed_utterance_path` in each `ArchetypeStyleConfig` (see `runtime/src/avatar/archetype_config.py`) points to these files. The pipeline uses them during voice cloning to produce a speaker embedding that captures the archetype's vocal characteristics.
