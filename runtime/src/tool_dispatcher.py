"""
Retired free-text tool dispatcher.

The old keyword-matching path that turned arbitrary agent thoughts into tool
execution has been removed. Structured actions now flow through the explicit
JSON action surface in `agent_runner._execute_action()`.

This module remains as a compatibility shim so stale imports fail safely.
"""

import logging

log = logging.getLogger("god.tools")


async def maybe_dispatch_tool(agent: dict, thought: str, action_type: str) -> str | None:
    """Compatibility stub: free-text tool dispatch is disabled."""
    if agent:
        soul_id = str(agent.get("soul_id", ""))[:8]
        if soul_id:
            log.debug("free-text tool dispatch disabled for %s", soul_id)
    return None
