# Issue #102 Twitch Platform Boundary

Date: 2026-06-27
Parent: #91
Status: code boundary added, Twitch launch still gated

## Scope

Issue #102 says Twitch should expand only after the YouTube/avatar-life path is
stable. The current pass does not launch Twitch or make it the immediate target.
It adds the shared platform boundary needed before Twitch can safely feed the
showrunner.

## Code Contract Added

- Shared platform boundary: `runtime/src/platforms/boundary.py`
- Twitch adapter boundary wiring: `runtime/src/twitch/adapter.py`
- Boundary tests: `runtime/tests/test_platform_boundary.py`
- Expanded Twitch tests: `runtime/tests/test_twitch_adapter.py`

The boundary makes these fields explicit for platform events:

- showrunner-only routing;
- no direct avatar, voice, OBS, broadcast, or GPU effects;
- moderation result;
- rate-limit bucket metadata;
- replay key;
- bot/channel identity in Twitch status.

## Remaining Blocker

Do not close #102 until the YouTube avatar-life milestone is complete and a
real Twitch adapter pass proves EventSub/Helix behavior without regressing the
YouTube proof path.
