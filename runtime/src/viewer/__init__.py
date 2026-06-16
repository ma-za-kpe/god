"""Viewer interaction and overlay seam for Twitch-style audience prompts."""

from .engine import ViewerSurface, build_viewer_state, build_viewer_status
from .state import ViewerState

__all__ = [
    "ViewerState",
    "ViewerSurface",
    "build_viewer_state",
    "build_viewer_status",
]
