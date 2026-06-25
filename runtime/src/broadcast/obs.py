"""OBS surface adapter with dry-run support and WebSocket v5 wiring."""

from __future__ import annotations

import logging
import os
from dataclasses import asdict, dataclass, field
from typing import Any

log = logging.getLogger("god.broadcast.obs")

try:  # pragma: no cover - runtime package import path
    from ..health_checks import probe_url
except ImportError:  # pragma: no cover - flat test path
    from health_checks import probe_url

try:  # pragma: no cover - runtime package import path
    from .captions import build_caption
    from .overlays import build_overlay
    from .scenes import SCENE_MAP, select_scene
    from .state import BroadcastCaption, BroadcastOverlay, BroadcastScene, BroadcastState
except ImportError:  # pragma: no cover - flat test path
    from captions import build_caption
    from overlays import build_overlay
    from scenes import SCENE_MAP, select_scene
    from state import BroadcastCaption, BroadcastOverlay, BroadcastScene, BroadcastState


def _env_bool(name: str, default: str = "true") -> bool:
    return os.getenv(name, default).lower() in ("1", "true", "yes", "on")


@dataclass(frozen=True)
class BroadcastCommand:
    action: str
    target: str
    value: str
    reason: str = ""
    metadata: dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class BroadcastSurface:
    """Compose stage state for the live broadcast surface."""

    def __init__(self, enabled: bool | None = None, dry_run: bool | None = None):
        self.enabled = _env_bool("BROADCAST_ENABLED", "false") if enabled is None else enabled
        self.dry_run = _env_bool("BROADCAST_DRY_RUN", "true") if dry_run is None else dry_run
        self.transport = os.getenv("BROADCAST_TRANSPORT", "dry-run")
        self.obs_scene_prefix = os.getenv("OBS_SCENE_PREFIX", "obs/")
        self.obs_browser_source = os.getenv("OBS_BROWSER_SOURCE", "god-browser")
        self.obs_browser_url = os.getenv("OBS_BROWSER_URL", "http://localhost:10517/stage")
        self.obs_browser_width = int(os.getenv("OBS_BROWSER_WIDTH", "1920"))
        self.obs_browser_height = int(os.getenv("OBS_BROWSER_HEIGHT", "1080"))
        self.obs_capture_mode = os.getenv("OBS_CAPTURE_MODE", "browser")
        self.obs_capture_source_kind = os.getenv("OBS_CAPTURE_SOURCE_KIND", "browser_source")
        self.obs_capture_window_id = os.getenv("OBS_CAPTURE_WINDOW_ID", "")
        self.obs_capture_window_class = os.getenv("OBS_CAPTURE_WINDOW_CLASS", "")
        self.obs_capture_window_name = os.getenv("OBS_CAPTURE_WINDOW_NAME", "")
        self.obs_stream_server = os.getenv("OBS_STREAM_SERVER", "")
        self.obs_stream_key = os.getenv("OBS_STREAM_KEY", "")
        self.obs_auto_start_stream = _env_bool("OBS_AUTO_START_STREAM", "false")

    def compose(self, snapshot: dict[str, Any]) -> BroadcastState:
        scene_profile = select_scene(snapshot)
        caption = build_caption(snapshot, scene_profile)
        overlay = build_overlay(snapshot, scene_profile)
        commands = self._commands(scene_profile, caption, overlay)
        return BroadcastState(
            enabled=self.enabled,
            dry_run=self.dry_run,
            scene=BroadcastScene(
                scene_id=scene_profile["scene_id"],
                scene_name=scene_profile["scene_name"],
                layout=scene_profile["layout"],
                fallback_scene=scene_profile["fallback_scene"],
                reason=scene_profile["reason"],
                mode=self.transport,
            ),
            caption=BroadcastCaption(
                headline=caption["headline"],
                subhead=caption["subhead"],
                lower_third=caption["lower_third"],
                ticker_lines=tuple(caption["ticker_lines"]),
            ),
            overlay=BroadcastOverlay(
                title=overlay["title"],
                subtitle=overlay["subtitle"],
                cards=tuple(overlay["cards"]),
                labels=tuple(overlay["labels"]),
            ),
            commands=tuple(commands),
            summary=self._summary(scene_profile, caption),
            world_id=str(snapshot.get("world_id") or ""),
            source_epoch=int(snapshot.get("epoch") or 0),
        )

    async def apply(self, snapshot: dict[str, Any]) -> dict[str, Any]:
        """Compose broadcast state and push commands to OBS via WebSocket v5.

        Dry-run: logs commands but makes no WS connection.
        Live:    connects to OBS_WEBSOCKET_URL, sends SetCurrentProgramScene +
                 text-source updates for caption/ticker, then disconnects.
        """
        state = self.compose(snapshot)
        if self.dry_run or not self.enabled:
            log.debug(
                "BroadcastSurface dry-run: scene=%s caption=%s",
                state.scene.scene_id,
                state.caption.headline[:60],
            )
            return {"dry_run": True, "summary": state.summary, "commands": list(state.commands)}

        obs_url = os.getenv("OBS_WEBSOCKET_URL", "")
        obs_password = os.getenv("OBS_WEBSOCKET_PASSWORD", "")
        if not obs_url:
            log.warning("OBS_WEBSOCKET_URL not set — broadcast commands skipped")
            return {"dry_run": False, "ok": False, "reason": "obs_url_not_set"}

        try:
            import obsws_python as obs  # type: ignore[import]
        except ImportError:
            log.warning("obsws-python not installed — OBS commands skipped")
            return {"dry_run": False, "ok": False, "reason": "obsws_python_missing"}

        results: list[dict[str, Any]] = []
        try:
            host, port_str = _parse_obs_url(obs_url)
            cl = obs.ReqClient(host=host, port=int(port_str), password=obs_password, timeout=5)

            self._ensure_browser_source(cl, results)

            # Scene change
            scene_id = state.scene.scene_id
            if scene_id:
                try:
                    cl.set_current_program_scene(scene_id)
                    results.append({"action": "set_scene", "scene": scene_id, "ok": True})
                    log.info("OBS scene → %s", scene_id)
                except Exception as exc:
                    results.append(
                        {"action": "set_scene", "scene": scene_id, "ok": False, "error": str(exc)}
                    )
                    log.warning("OBS set_scene failed: %s", exc)

            # Caption / ticker text source update
            caption_source = os.getenv("OBS_CAPTION_SOURCE", "god-caption")
            ticker_source = os.getenv("OBS_TICKER_SOURCE", "god-ticker")
            for source_name, text in [
                (caption_source, state.caption.headline),
                (ticker_source, " • ".join(state.caption.ticker_lines[:3])),
            ]:
                if source_name and text:
                    try:
                        cl.set_input_settings(
                            name=source_name,
                            settings={"text": text},
                            overlay=True,
                        )
                        results.append({"action": "set_text", "source": source_name, "ok": True})
                    except Exception as exc:
                        results.append(
                            {
                                "action": "set_text",
                                "source": source_name,
                                "ok": False,
                                "error": str(exc),
                            }
                        )
                        log.debug("OBS set_input_settings %s: %s", source_name, exc)

            # Browser mode updates a browser source URL. Window-capture mode
            # leaves the X11 source alone because the startup script owns it.
            if (
                self.obs_capture_mode == "browser"
                and self.obs_browser_source
                and self.obs_browser_url
            ):
                try:
                    cl.set_input_settings(
                        name=self.obs_browser_source,
                        settings={
                            "url": self.obs_browser_url,
                            "width": self.obs_browser_width,
                            "height": self.obs_browser_height,
                        },
                        overlay=True,
                    )
                    results.append(
                        {
                            "action": "set_browser",
                            "source": self.obs_browser_source,
                            "url": self.obs_browser_url,
                            "ok": True,
                        }
                    )
                except Exception as exc:
                    results.append(
                        {
                            "action": "set_browser",
                            "source": self.obs_browser_source,
                            "ok": False,
                            "error": str(exc),
                        }
                    )
                    log.debug("OBS browser source update %s: %s", self.obs_browser_source, exc)
            elif self.obs_capture_mode != "browser":
                results.append(
                    {
                        "action": "capture_source",
                        "mode": self.obs_capture_mode,
                        "source": self.obs_browser_source,
                        "ok": True,
                    }
                )

            if self.obs_auto_start_stream:
                self._ensure_streaming(cl, results)

            cl.base_client.ws.close()
        except Exception as exc:
            log.warning("OBS WebSocket error: %s", exc)
            return {"dry_run": False, "ok": False, "reason": str(exc), "results": results}

        return {"dry_run": False, "ok": True, "summary": state.summary, "results": results}

    def status(self) -> dict[str, Any]:
        health = probe_url(os.getenv("OBS_WEBSOCKET_URL"), timeout=1.5)
        return {
            "enabled": self.enabled,
            "dry_run": self.dry_run,
            "transport": self.transport,
            "obs_scene_prefix": self.obs_scene_prefix,
            "obs_browser_source": self.obs_browser_source,
            "obs_browser_url": self.obs_browser_url,
            "obs_stream_server": self.obs_stream_server,
            "obs_capture_mode": self.obs_capture_mode,
            "obs_capture_source_kind": self.obs_capture_source_kind,
            "obs_capture_window_id": self.obs_capture_window_id,
            "obs_auto_start_stream": self.obs_auto_start_stream,
            "health": health,
        }

    def _summary(self, scene_profile: dict[str, Any], caption: dict[str, Any]) -> str:
        return f"{scene_profile['scene_name']} / {caption['headline'][:120]}"

    def _commands(
        self,
        scene_profile: dict[str, Any],
        caption: dict[str, Any],
        overlay: dict[str, Any],
    ) -> list[dict[str, Any]]:
        commands = [
            BroadcastCommand(
                action="set_scene",
                target="obs",
                value=scene_profile["scene_id"],
                reason=scene_profile["reason"],
                metadata={"fallback": scene_profile["fallback_scene"]},
            ).to_dict(),
            BroadcastCommand(
                action="set_caption",
                target="overlay",
                value=caption["headline"],
                reason="headline",
                metadata={"subhead": caption["subhead"], "lower_third": caption["lower_third"]},
            ).to_dict(),
            BroadcastCommand(
                action="set_overlay",
                target="overlay",
                value=overlay["title"],
                reason="stage overlay",
                metadata={"labels": overlay["labels"], "cards": overlay["cards"]},
            ).to_dict(),
        ]
        if self.dry_run or not self.enabled:
            for command in commands:
                command["dry_run"] = True
                command["transport"] = self.transport
        return commands

    def _ensure_browser_source(self, cl, results: list[dict[str, Any]]) -> None:
        """Best-effort create/update the browser source in all runtime scenes."""
        if not self.obs_browser_source or not self.obs_browser_url:
            return

        scene_names = [
            profile["scene_id"] for profile in SCENE_MAP.values() if profile.get("scene_id")
        ]
        if not scene_names:
            return

        input_settings = {
            "url": self.obs_browser_url,
            "width": self.obs_browser_width,
            "height": self.obs_browser_height,
        }

        existing_inputs: set[str] = set()
        try:
            input_list = cl.get_input_list()
            inputs = (
                input_list.inputs if hasattr(input_list, "inputs") else input_list.get("inputs", [])
            )
            for item in inputs:
                if isinstance(item, dict):
                    name = item.get("inputName") or item.get("input_name") or item.get("name")
                else:
                    name = getattr(item, "inputName", None) or getattr(item, "name", None)
                if name:
                    existing_inputs.add(str(name))
        except Exception as exc:
            log.debug("OBS get_input_list unavailable while provisioning browser source: %s", exc)

        for scene_name in scene_names:
            try:
                if self.obs_browser_source not in existing_inputs:
                    cl.create_input(
                        sceneName=scene_name,
                        inputName=self.obs_browser_source,
                        inputKind="browser_source",
                        inputSettings=input_settings,
                        sceneItemEnabled=True,
                    )
                    existing_inputs.add(self.obs_browser_source)
                    results.append(
                        {
                            "action": "create_browser",
                            "scene": scene_name,
                            "source": self.obs_browser_source,
                            "url": self.obs_browser_url,
                            "ok": True,
                        }
                    )
                    log.info("OBS browser source created in %s", scene_name)
                else:
                    cl.set_input_settings(
                        name=self.obs_browser_source,
                        settings=input_settings,
                        overlay=True,
                    )
                    results.append(
                        {
                            "action": "update_browser",
                            "scene": scene_name,
                            "source": self.obs_browser_source,
                            "ok": True,
                        }
                    )
            except Exception as exc:
                results.append(
                    {
                        "action": "browser_source",
                        "scene": scene_name,
                        "source": self.obs_browser_source,
                        "ok": False,
                        "error": str(exc),
                    }
                )
                log.debug("OBS browser source provisioning failed for %s: %s", scene_name, exc)

    def _ensure_streaming(self, cl, results: list[dict[str, Any]]) -> None:
        """Best-effort configure and start YouTube streaming."""
        if not self.obs_stream_server or not self.obs_stream_key:
            return

        try:
            cl.set_stream_service_settings(
                stream_service_type="rtmp_custom",
                stream_service_settings={
                    "server": self.obs_stream_server,
                    "key": self.obs_stream_key,
                },
            )
            results.append({"action": "set_stream_service", "ok": True})
        except Exception as exc:
            results.append({"action": "set_stream_service", "ok": False, "error": str(exc)})
            log.debug("OBS stream service setup failed: %s", exc)
            return

        try:
            cl.start_stream()
            results.append({"action": "start_stream", "ok": True})
            log.info("OBS live stream started")
        except Exception as exc:
            results.append({"action": "start_stream", "ok": False, "error": str(exc)})
            log.debug("OBS start_stream failed: %s", exc)


def _parse_obs_url(url: str) -> tuple[str, str]:
    """Extract host and port from ws://host:port or wss://host:port."""
    url = url.removeprefix("wss://").removeprefix("ws://")
    if ":" in url:
        host, port = url.rsplit(":", 1)
        return host, port.split("/")[0]
    return url, "4455"


def build_broadcast_status() -> dict[str, Any]:
    return BroadcastSurface().status()
