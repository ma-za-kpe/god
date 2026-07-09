# M06 Source Check: Browser Anatomy Inspection Renderer

Date: 2026-07-08

Milestone: M06 browser anatomy inspection renderer.

## Project Sources Checked

| Source | M06 Use |
| --- | --- |
| `docs/93-anatomy-node-avatar-architecture.md` | Renderer projection must be a graph projection, not the anatomy source of truth. Every rendered/control node must map back to an anatomy node, and missing renderer support must be visible diagnostics. |
| `docs/94-anatomy-node-avatar-roadmap.md` | M06 exit requires graph-derived body/system/head/knee/toe layers, screenshot evidence, and visible degradation for missing mappings. |
| `docs/reference/anatomy/MANIFEST.md` | Confirms local OpenStax, FIPAT TA2, and Gray's Anatomy reference files are available for anatomy provenance checks. |
| `docs/reference/anatomy/openstax-anatomy-and-physiology.pdf` | Local textbook reference remains the body/system/head/limb seed source through the existing M02 graph. |
| FIPAT TA2 local PDFs | Local terminology reference remains the canonical naming source through the existing M02 graph. |

## Current Web Sources Checked

| Claim Used By M06 | Source |
| --- | --- |
| SVG can be used as the browser coordinate-system container for a composed anatomy view. | MDN `<svg>` documentation: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Element/svg |
| Grouped SVG content can be exposed as a single accessible image with `role="img"` and `aria-label`. | MDN ARIA `img` role documentation: https://developer.mozilla.org/en-US/docs/Web/Accessibility/ARIA/Reference/Roles/img_role |
| SVG `pointer-events` can keep visual overlays from becoming pointer targets. | MDN SVG `pointer-events` attribute documentation: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/pointer-events |
| SVG dashed strokes are a standard presentation attribute for diagnostic/overlay rings and graph layers. | MDN `stroke-dasharray` documentation: https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/stroke-dasharray |
| React lists rendered from graph arrays need stable keys from data, not generated keys. | React Rendering Lists documentation: https://react.dev/learn/rendering-lists |
| React conditional rendering is the supported path for visible diagnostics and layer panels. | React Conditional Rendering documentation: https://react.dev/learn/conditional-rendering |

## M06 Design Consequences

- `render_projection` is generated from the validated anatomy graph.
- React renders projection primitives generically from the asset instead of inventing node labels in JSX.
- Any primitive whose `node_id` is not present in the graph asset is dropped by the observer helper.
- Missing mappings are diagnostics with the form
  `missing_render_mapping:<layer_id>:<node_id>`.
- The first renderer projection intentionally maps a practical subset of body,
  systems, head, knee, and hallux nodes while reporting unmapped system nodes as
  degraded.
- Browser screenshots must show the projection overlay, layer coverage, and
  renderer diagnostics.
