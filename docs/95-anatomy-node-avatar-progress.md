# Anatomy Node Avatar Progress

Status: active progress log.

This document records completed anatomy-avatar milestones, validation evidence,
and the next implementation gates. The roadmap remains in
`docs/94-anatomy-node-avatar-roadmap.md`; this file captures what actually
landed and what must be verified before moving forward.

## Standing Rule

Code owns schemas, clamps, validation, diagnostics, and renderer capability
projection. The LLM owns dialogue, mood, gesture, gaze, hair, face, hand, body,
wardrobe, and movement intent through bounded source-backed node handles. Test
fixtures may hardcode values only as temporary proof scaffolding before they are
replaced by LLM-authored structured output.

## 2026-07-09 - M08 Right-Hand Digit Graph

Branch: `feat/local-browser-avatar-lab`.

Goal: start from the pinky placement problem and expand it into a source-backed
right-hand digit graph that the LLM can query and control without fake renderer
nodes.

Completed:

- Added the right upper limb parent path for the hand.
- Modeled thumb, index, middle, ring, and little finger as right-hand digit
  nodes.
- Added all five metacarpals.
- Added all fourteen right-hand phalanges: two for the thumb and three for each
  non-thumb finger.
- Added explicit CMC, MCP, thumb IP, and PIP/DIP joint nodes.
- Added graph edges proving each phalanx belongs to its digit and each joint
  connects the correct upstream/downstream bones.
- Added LLM-visible control channels for opposition, flexion/extension,
  abduction/adduction, circumduction proxies, finger curl, and palm cupping.
- Added a focused browser render projection for the right hand so M08 reports
  only the hand digit inspection layer.
- Exported `observer/public/assets/anatomy/m08-graph.json` and updated
  `observer/public/assets/anatomy/latest-graph.json`.
- Updated the browser readout to show `hand digits 5/5` and
  `hand phalanges 14/14`.
- Preserved an intentional fake-phalanx rejection in the control contract to
  prove invented anatomy nodes are rejected.

Verification:

- Python graph contract: `python -m pytest runtime/tests/test_anatomy_graph_contract.py -q`
  passed with 35 tests.
- Python lint: `.venv\Scripts\ruff.exe check runtime/src/anatomy runtime/tests/test_anatomy_graph_contract.py scripts/export-anatomy-milestone-assets.py`
  passed.
- Observer tests: `npm test` passed with 31 tests.
- Observer lint: `npm run lint` passed.
- Observer build: `npm run build` passed.
- Docker route: `god-observer` served `http://127.0.0.1:3000/anatomy-lab`
  with 200 responses for the app bundle and anatomy graph asset.

M08 payload:

- `100` nodes.
- `165` edges.
- `55` LLM handles.
- `49` focus nodes.
- `49` nodes in the right-hand digit action bundle.
- `8` accepted controls.
- `1` intentional rejected fake control.
- `1` render layer.
- `48/48` hand render nodes mapped.
- `0` missing render mappings.

Visual evidence:

- `artifacts/m08-right-hand-digit-skeleton-green.png` is the final green
  screenshot.
- Earlier pinky placement captures remain in `artifacts/` as audit history.

## Next Gates

M09 must move from static graph projection to continuous LLM-directed anatomy
avatar behavior. Before implementation, re-check the roadmap, source notes,
local graph export, and current tool/library docs.

Required next work:

- Add graph-backed action plans for natural hand poses: relaxed hand, fist,
  finger spread, point, pinch, wave, grip, and palm cup.
- Add deterministic pose projection that maps digit/joint controls to visible
  finger bends instead of only static inspection lines.
- Use LLM-authored structured control plans for the hand actions; code may only
  validate, clamp, and diagnose.
- Add browser screenshot gates that compare the hand before/after each action.
- Keep unsupported renderer controls explicit as diagnostics rather than
  pretending a mesh or bone moved.
