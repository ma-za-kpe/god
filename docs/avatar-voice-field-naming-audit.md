# Avatar and Voice Field Naming Audit

Issue #92 found two data-model names that no longer describe what the current
Fish/Comfy pipeline stores.

## Current fields

- `voice_model_cid`: currently stores Fish Speech reference WAV bytes. It is not
  a standalone model checkpoint or embedding artifact.
- `rigged_avatar_cid`: currently falls back to the generated portrait CID. It is
  not guaranteed to point at a rigged VRM or animation-ready avatar.
- `avatar_cid` and `avatar_base_cid`: currently point at static portrait images.
- `vrm_avatar_url`: currently remains empty until a real rigged avatar asset is
  produced outside the portrait pipeline.

## Proposed replacements

- Add `voice_reference_audio_cid` and migrate Fish Speech reference WAV CIDs into
  that field.
- Reserve `voice_model_cid` for persistent voice model/checkpoint artifacts only.
- Add `avatar_portrait_cid` and `avatar_base_portrait_cid` for static image assets.
- Reserve `rigged_avatar_cid` for rigged avatar packages and keep `vrm_avatar_url`
  for directly fetchable VRM assets.

## Migration path

1. Add new nullable/empty-string columns while continuing to populate legacy
   fields for observer compatibility.
2. Read new fields first, then fall back to legacy fields in `/agents`,
   `/world/snapshot`, avatar planning, and voice reference lookup.
3. Backfill existing rows by copying `voice_model_cid` to
   `voice_reference_audio_cid` and `rigged_avatar_cid` to `avatar_portrait_cid`
   where the referenced asset is a static image.
4. Stop writing misleading legacy fields once observers and seed/genesis flows
   consume the replacement names.

No schema migration is included in #92; this audit documents the naming gap and
the replacement contract for the follow-up migration.
