# Avatar Workflows

These ComfyUI workflow templates are consumed by the avatar genesis pipeline.

## Files

- `flux_portrait.json` - canonical portrait generation using Flux + IP-Adapter FaceID
- `flux_expression.json` - expression variant generation from a portrait reference
- `controlnet_evolution.json` - portrait evolution and scar-layer inpainting
- `ltx_image_to_video_loop.json` - background-only LTX image-to-video loop template for avatar live-loop assets

## Notes

- The workflows are templates, not ready-made graph exports.
- Runtime code fills the placeholder tokens before submission.
- Required custom nodes are listed in each file's `_meta.required_custom_nodes` block.
- The `controlnet_evolution.json` workflow is used for betrayal scars, reconciliation softening, and prestige marks.
- The LTX workflow must run through the GPU job queue as background work and should remain disabled during live mode unless explicitly allowed.
