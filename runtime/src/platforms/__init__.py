"""Shared platform-adapter boundary contracts."""

from .boundary import PlatformAudienceEvent, build_platform_audience_event

__all__ = [
    "PlatformAudienceEvent",
    "build_platform_audience_event",
]
