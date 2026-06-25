"""Model Router — Task-based routing with circuit-breaking dual model support.

Routes broadcast generation requests to a remote 70B+ model (Groq/Together)
and non-broadcast tasks (planning, selection, summarization) to the local 8B model.
Implements a circuit breaker that falls back to local-only mode when the remote
endpoint exhibits excessive errors.

Extends the pattern from circuit_breaker.py but scoped to the remote banter
endpoint rather than per-agent limits.
"""

from __future__ import annotations

import asyncio
import logging
import time
from typing import Literal, Protocol

from .types import CircuitBreakerState, RouteDecision

log = logging.getLogger("god.banter.router")


# ---------------------------------------------------------------------------
# Protocol for injectable model callable (for testing/mocking)
# ---------------------------------------------------------------------------


class ModelCallable(Protocol):
    """Protocol for an async callable that takes a prompt and returns a string."""

    async def __call__(self, prompt: str) -> str: ...


# ---------------------------------------------------------------------------
# ModelRouter
# ---------------------------------------------------------------------------


class ModelRouter:
    """Task-based routing between remote 70B+ and local 8B models.

    Routes broadcast line generation to a remote endpoint (Groq/Together)
    with a 4-second timeout. All other tasks (planning, selection,
    summarization) go to the local model with a 30-second timeout.

    When the remote endpoint is unhealthy (circuit breaker tripped),
    broadcast requests fall back to local with a stricter quality
    threshold of 10 (vs normal 8).

    Parameters
    ----------
    remote_model : ModelCallable | None
        Async callable for remote model invocation. If None, a default
        LangChain-based callable is created from environment config.
    local_model : ModelCallable | None
        Async callable for local model invocation. If None, operations
        that require local will raise ModelRouterError.
    config : dict | None
        Optional configuration overrides for circuit breaker parameters.
    """

    def __init__(
        self,
        remote_model: ModelCallable | None = None,
        local_model: ModelCallable | None = None,
        config: dict | None = None,
    ) -> None:
        self._remote_model = remote_model
        self._local_model = local_model

        # Circuit breaker state
        cfg = config or {}
        self._cb = CircuitBreakerState(
            window_start=time.time(),
            request_count=0,
            error_count=0,
            tripped=False,
            tripped_at=0.0,
            cooldown_s=cfg.get("cooldown_s", 60.0),
            window_s=cfg.get("window_s", 300.0),
            error_threshold=cfg.get("error_threshold", 0.20),
            min_requests=cfg.get("min_requests", 5),
        )

        # If no remote model provided, attempt to build one from LangChain
        if self._remote_model is None:
            self._remote_model = self._build_default_remote()

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def route(
        self,
        task_type: Literal["broadcast", "planning", "selection", "summarization"],
    ) -> RouteDecision:
        """Determine routing for a generation request.

        Parameters
        ----------
        task_type : str
            The type of generation task.

        Returns
        -------
        RouteDecision
            Contains target ("remote" or "local"), quality_threshold, and timeout_s.
        """
        if task_type == "broadcast":
            if self._cb.tripped:
                # Circuit is broken — fall back to local with stricter threshold
                return RouteDecision(target="local", quality_threshold=10, timeout_s=30.0)
            return RouteDecision(target="remote", quality_threshold=8, timeout_s=4.0)

        # All non-broadcast tasks go to local
        return RouteDecision(target="local", quality_threshold=8, timeout_s=30.0)

    async def call_remote(self, prompt: str, timeout_s: float = 4.0) -> str | None:
        """Call the remote model with timeout and circuit breaker tracking.

        Parameters
        ----------
        prompt : str
            The generation prompt.
        timeout_s : float
            Maximum time to wait for a response.

        Returns
        -------
        str | None
            The model response if successful and valid, None otherwise.
        """
        if self._remote_model is None:
            self._record_error()
            return None

        try:
            response = await asyncio.wait_for(
                self._remote_model(prompt),
                timeout=timeout_s,
            )
        except asyncio.TimeoutError:
            log.warning("Remote model call timed out (%.1fs)", timeout_s)
            self._record_error()
            return None
        except Exception as e:
            log.warning("Remote model call failed: %s", e)
            self._record_error()
            return None

        # Validate the response
        if response is None or not self.validate_response(response):
            log.debug("Remote model returned invalid response")
            self._record_error()
            return None

        self._record_success()
        return response

    def validate_response(self, response: str) -> bool:
        """Validate a model response for broadcast suitability.

        A valid response must:
        - Contain at least 1 non-whitespace character
        - Contain no control sequences (bytes < 0x20 except space and newline)
        - Be a single line (no newlines in content after stripping)

        Parameters
        ----------
        response : str
            The raw model response.

        Returns
        -------
        bool
            True if the response passes all validation checks.
        """
        # Must have at least 1 non-whitespace character
        stripped = response.strip()
        if len(stripped) == 0:
            return False

        # Check for control characters (bytes < 0x20 except space 0x20 and newline 0x0A)
        # Note: space is 0x20 so it's not < 0x20. We allow newline only at boundaries.
        for ch in response:
            code = ord(ch)
            if code < 0x20 and ch != "\n":
                return False

        # Must be a single line (no newlines in stripped content)
        if "\n" in stripped:
            return False

        return True

    def should_probe(self) -> bool:
        """Check if the circuit breaker should attempt a probe.

        Returns True if the circuit is tripped and the cooldown period
        (60s by default) has elapsed since the trip.

        Returns
        -------
        bool
            True if a probe should be attempted.
        """
        if not self._cb.tripped:
            return False
        elapsed = time.time() - self._cb.tripped_at
        return elapsed >= self._cb.cooldown_s

    async def probe_remote(self) -> bool:
        """Send a single probe request to test remote endpoint health.

        If the probe succeeds, the circuit breaker is reset and remote
        routing resumes. If it fails, the circuit remains tripped and
        the tripped_at timestamp is updated for a fresh cooldown.

        Returns
        -------
        bool
            True if the probe succeeded and the circuit is now restored.
        """
        if self._remote_model is None:
            return False

        test_prompt = "Say hello in one sentence."
        try:
            response = await asyncio.wait_for(
                self._remote_model(test_prompt),
                timeout=4.0,
            )
        except (asyncio.TimeoutError, Exception) as e:
            log.info("Probe failed: %s", e)
            # Update tripped_at to start fresh cooldown
            self._cb.tripped_at = time.time()
            return False

        if response and self.validate_response(response):
            # Probe succeeded — reset circuit breaker
            self._reset_circuit_breaker()
            log.info("Probe succeeded — restoring remote routing")
            return True

        # Invalid response counts as probe failure
        self._cb.tripped_at = time.time()
        return False

    @property
    def circuit_breaker_state(self) -> CircuitBreakerState:
        """Access the current circuit breaker state (for testing/monitoring)."""
        return self._cb

    # ------------------------------------------------------------------
    # Internal helpers
    # ------------------------------------------------------------------

    def _record_success(self) -> None:
        """Record a successful request outcome."""
        self._maybe_reset_window()
        self._cb.request_count += 1
        self._check_trip()

    def _record_error(self) -> None:
        """Record a failed request outcome and check circuit breaker."""
        self._maybe_reset_window()
        self._cb.request_count += 1
        self._cb.error_count += 1
        self._check_trip()

    def _maybe_reset_window(self) -> None:
        """Reset counters if the current window has expired."""
        now = time.time()
        if now - self._cb.window_start > self._cb.window_s:
            self._cb.window_start = now
            self._cb.request_count = 0
            self._cb.error_count = 0

    def _check_trip(self) -> None:
        """Trip the circuit breaker if conditions are met.

        Conditions for tripping:
        - At least min_requests (5) requests in the current window
        - Error rate exceeds error_threshold (20%)
        """
        if self._cb.tripped:
            return  # Already tripped

        if self._cb.request_count < self._cb.min_requests:
            return  # Not enough data

        error_rate = self._cb.error_count / self._cb.request_count
        if error_rate > self._cb.error_threshold:
            self._cb.tripped = True
            self._cb.tripped_at = time.time()
            log.warning(
                "Circuit breaker TRIPPED: %d/%d errors (%.1f%%) in window",
                self._cb.error_count,
                self._cb.request_count,
                error_rate * 100,
            )

    def _reset_circuit_breaker(self) -> None:
        """Reset the circuit breaker to healthy state."""
        self._cb.tripped = False
        self._cb.tripped_at = 0.0
        self._cb.window_start = time.time()
        self._cb.request_count = 0
        self._cb.error_count = 0

    def _build_default_remote(self) -> ModelCallable | None:
        """Attempt to build a LangChain-based remote model callable.

        Uses environment variables to determine provider (Groq or Together).
        Returns None if LangChain dependencies are not available.
        """
        import os

        provider = os.getenv("BANTER_REMOTE_PROVIDER", "groq")
        model_name = os.getenv("BANTER_REMOTE_MODEL", "llama-3.1-70b-versatile")
        api_key_env = os.getenv("BANTER_REMOTE_API_KEY", "")

        # Try to import LangChain chat model
        try:
            if provider == "groq":
                from langchain_groq import ChatGroq

                if not api_key_env:
                    api_key_env = os.getenv("GROQ_API_KEY", "")
                if not api_key_env:
                    log.debug("No Groq API key found — remote model unavailable")
                    return None

                llm = ChatGroq(
                    model=model_name,
                    api_key=api_key_env,
                    temperature=0.9,
                    max_tokens=150,
                )
            elif provider == "together":
                from langchain_together import ChatTogether

                if not api_key_env:
                    api_key_env = os.getenv("TOGETHER_API_KEY", "")
                if not api_key_env:
                    log.debug("No Together API key found — remote model unavailable")
                    return None

                llm = ChatTogether(
                    model=model_name,
                    api_key=api_key_env,
                    temperature=0.9,
                    max_tokens=150,
                )
            else:
                log.debug("Unknown remote provider '%s'", provider)
                return None

            async def _call_langchain(prompt: str) -> str:
                result = await llm.ainvoke(prompt)
                return result.content if hasattr(result, "content") else str(result)

            return _call_langchain

        except ImportError as e:
            log.debug("LangChain remote dependency not available: %s", e)
            return None
        except Exception as e:
            log.debug("Failed to initialize remote model: %s", e)
            return None
