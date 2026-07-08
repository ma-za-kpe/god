# M07 Motion Projection Bridge Source Check

Date: 2026-07-08

Milestone: M07, motion projection bridge.

## Project Docs Checked

- `docs/93-anatomy-node-avatar-architecture.md`
- `docs/94-anatomy-node-avatar-roadmap.md`
- `docs/reference/anatomy/MANIFEST.md`

## Local Anatomy References Checked

- `docs/reference/anatomy/openstax-anatomy-and-physiology.pdf`
- `docs/reference/anatomy/fipat-ta2-part-2-musculoskeletal.pdf`
- `docs/reference/anatomy/fipat-ta2-part-4-integrating-systems-1.pdf`
- `docs/reference/anatomy/gray-anatomy-of-the-human-body-1918-full-text.txt`

These references continue to support the existing source-cited hand, knee, foot,
hallux, forehead skin, cardiovascular, respiratory, and nervous-system nodes.
M07 does not add new factual anatomy nodes; it compiles motion bridge records
only from already sourced action-bundle nodes.

## Current External Tool Sources Checked

- OpenSim Models:
  https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53088473/OpenSim+Models
  - Confirmed OpenSim models represent neuromuscular and musculoskeletal
    dynamics using reference frames, bodies, joints, constraints, forces,
    contact geometry, markers, and controllers.
  - Confirmed skeletal systems are rigid bodies connected by joints and muscles
    act through origin/insertion path points.

- OpenSim Workflows:
  https://opensimconfluence.atlassian.net/wiki/spaces/OpenSim/pages/53084226/Overview+of+OpenSim+Workflows
  - Confirmed OpenSim workflows center on musculoskeletal models with bodies,
    joints, forces, constraints, and controllers.
  - Confirmed pelvis, hip, knee, and ankle joints are normal gait-model
    articulation points, which justifies reporting missing hip/ankle depth as
    degraded M07 diagnostics instead of inventing nodes.

- OpenSim Moco:
  https://simtk.org/projects/opensim-moco
  - Confirmed Moco solves optimal control problems with OpenSim models using
    direct collocation, including motion tracking, prediction, and parameter
    optimization.

- MuSkeMo:
  https://github.com/PashavanBijlert/MuSkeMo
  - Confirmed MuSkeMo imports OpenSim models and can import simulated
    trajectories into Blender from OpenSim `.sto`, `.mot`, and CSV-like files.

- MDN SVG `d`:
  https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/d
  - Confirmed SVG path `d` strings define drawn paths and support standard
    path commands used by the browser motion cues.

- MDN SVG `stroke-linecap`:
  https://developer.mozilla.org/en-US/docs/Web/SVG/Reference/Attribute/stroke-linecap
  - Confirmed rounded line caps are a standard SVG presentation attribute for
    open stroked subpaths.

## Design Consequences

- The motion bridge emits deterministic adapter records, not physics results.
- OpenSim, OpenSim Moco, and MuSkeMo remain backend targets; M07 prepares
  source-backed hints for those adapters without reimplementing them.
- Browser SVG cues are inspection evidence only. They prove the compiled plans
  are visible, animated, and tied to real graph nodes.
- Missing shoulder, elbow, hip, pelvis, and ankle nodes are explicit degraded
  diagnostics. The bridge does not create fake nodes or controls.
- Renderer controls, simulation hints, and visual cues must carry source ids and
  must reference nodes already present in the action bundle.
