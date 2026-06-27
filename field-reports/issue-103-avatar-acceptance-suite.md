# Issue #103 Avatar Acceptance Suite

Date: 2026-06-27
Parent: #91
Status: acceptance matrix implemented

## Scope

Issue #103 requires each live-avatar persona and use case to have an automated
test, a manual VOD checklist, or benchmark/field-report evidence path. It also
requires failure paths to be represented and linked from the audit.

## Code Contract Added

- Acceptance matrix: `runtime/src/avatar/acceptance_suite.py`
- Runtime exports: `runtime/src/avatar/__init__.py`
- Contract tests: `runtime/tests/test_avatar_acceptance_suite.py`
- Audit link: `docs/90-fish-comfyui-integration-audit.md#issue-103-avatar-acceptance-suite`

## Personas Covered

- Live Speaker
- Listener
- Emotional Reactor
- Cinematic Cutaway
- Highlight Producer
- Operator

## Failure Paths Covered

- Fish failure / silence risk.
- Comfy or video failure with visual fallback.
- Background asset job does not block Fish.
- Observer source switching across procedural, loop, cinematic, and static fallback.

## Validation

The matrix validator reports no gaps when run against the shipped suite. The
manual VOD checklists remain evidence requirements for the later live stream
field runs, but the persona/use-case acceptance suite itself is now defined.
