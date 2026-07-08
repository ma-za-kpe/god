# Avatar Lab Gap Tracker

Date: 2026-07-08
Branch: `feat/local-browser-avatar-lab`

## Prime Goal

Build a local browser-first pipeline for continuous LLM-directed avatar video.
Code owns schema validation, clamps, adapters, diagnostics, and safe
degradation. The LLM owns dialogue, camera/framing, mood, gesture, gaze,
full-body pose, hair, face, hands/fingers, wardrobe/body presentation, stage,
lighting, and every exposed renderer node.

## Tracker

| ID | Gap | Status | Current Action |
| --- | --- | --- | --- |
| G01 | Continuous mode can be disabled by one-shot URLs such as `auto=0`, so the lab may look static even when the target is continuous LLM control. | in progress | Default scripts use Auto; live browser verification still has to prove multiple LLM beats. |
| G02 | The prompt does not strongly require visible framing for hand, body, wardrobe, and node changes, so the LLM can choose upper/head framing while changing hands. | completed | Prompt now requires full/mid framing when hand, finger, wardrobe, or body controls matter. |
| G03 | Hand/fist control can silently miss visible output if direct `handFistLeft/Right` pseudo-morphs are not discovered or if the camera hides hands. | completed | Pseudo-morph discovery is explicit and finger bone overlays compile from LLM hand intent. |
| G04 | Semantic controls must be full-body, not finger-only. The LLM needs a safe route into head, neck, spine, hips, arms, hands, and legs whenever the renderer exposes those nodes. | completed | `motion`, `gesture`, `gaze`, `hair`, and `hands` compile into full-body bone overlays. |
| G05 | Adapter diagnostics can say a semantic node was applied even when the underlying morph call failed. | completed | Semantic diagnostics now require at least one concrete renderer write before reporting applied/degraded. |
| G06 | Adapter option node calls for mood, pose, gesture, camera, and lighting can throw and stop a beat instead of degrading cleanly. | completed | Option-node renderer calls are wrapped and reported through diagnostics. |
| G07 | Material controls report unsupported when emissive is absent, even when color tint can be used as a visible fallback. | completed | Material controls now fall back to color tint before reporting unsupported. |
| G08 | Hair/dynamic-bone controls are only proxy motion for the default GLB; true dynamic bones are not guaranteed. | tracked | Keep explicit degraded diagnostics and prefer assets with dynamic bones later. |
| G09 | Lip sync currently uses text-derived viseme sampling instead of real TTS phoneme timestamps. | tracked | Replace with Kokoro/HeadTTS timestamps after the visual control path is stable. |
| G10 | Audio is browser speech fallback, not Kokoro, so timing and voice quality are only a proof. | tracked | Add Kokoro/HeadTTS local path after renderer control is green. |
| G11 | There was no observer lint command guarding the new avatar modules. | completed | Added ESLint config and `npm run lint --prefix observer` with zero warnings. |
| G12 | Live diagnostics accumulate old unsupported entries, making it harder to distinguish current failures from stale failures. | open | Keep current-frame diagnostics clear and use live reload for green checks. |
| G13 | Local browser launches can leave old Chrome processes open and overload the machine. | completed | `scripts/start-local-avatar-lab.ps1 -OpenBrowser` closes existing Chrome before launch. |
| G14 | No single local monitor script yet checks Vite, Ollama, avatar asset, console errors, audio state, and renderer diagnostics. | tracked | Add after the core renderer gaps are closed. |

## Definition Of Green

- `npm run lint --prefix observer` exits with zero warnings.
- `npm test --prefix observer` passes.
- `npm run build --prefix observer` passes without warnings.
- Relevant Python static tests pass.
- Browser diagnostics show renderer `ready`, Ollama intent source, audio
  speaking or ended cleanly, varying lip visemes while speaking, no current
  unsupported renderer controls, and node application covering camera, stage,
  face, lips, full-body bones, hands/fingers, hair proxy, gesture/pose, and
  wardrobe/material fallback.
