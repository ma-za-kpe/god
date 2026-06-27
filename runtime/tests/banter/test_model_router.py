"""Unit tests for Model Router with circuit-breaking dual routing.

Tests cover:
- route() decision logic for different task types
- call_remote() with timeout and error handling
- validate_response() acceptance/rejection criteria
- Circuit breaker activation and recovery
- should_probe() and probe_remote() mechanics
"""

import asyncio
import time

import pytest

from banter.model_router import ModelRouter


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_remote_success():
    """A remote model that always succeeds."""

    async def _call(prompt: str) -> str:
        return "A witty broadcast line."

    return _call


@pytest.fixture
def mock_remote_timeout():
    """A remote model that always times out."""

    async def _call(prompt: str) -> str:
        await asyncio.sleep(10)
        return "Too late."

    return _call


@pytest.fixture
def mock_remote_error():
    """A remote model that always raises an exception."""

    async def _call(prompt: str) -> str:
        raise ConnectionError("Remote endpoint unreachable")

    return _call


@pytest.fixture
def mock_remote_empty():
    """A remote model that returns empty string."""

    async def _call(prompt: str) -> str:
        return ""

    return _call


@pytest.fixture
def mock_local():
    """A local model callable."""

    async def _call(prompt: str) -> str:
        return "Local fallback line."

    return _call


@pytest.fixture
def router_healthy(mock_remote_success, mock_local):
    """A router with a healthy remote endpoint."""
    return ModelRouter(remote_model=mock_remote_success, local_model=mock_local)


@pytest.fixture
def router_no_remote(mock_local):
    """A router with no remote model."""
    return ModelRouter(remote_model=None, local_model=mock_local)


# ---------------------------------------------------------------------------
# route() tests
# ---------------------------------------------------------------------------


class TestRoute:
    """Tests for ModelRouter.route() decision logic."""

    def test_broadcast_routes_to_remote_when_healthy(self, router_healthy):
        decision = router_healthy.route("broadcast")
        assert decision.target == "remote"
        assert decision.quality_threshold == 8
        assert decision.timeout_s == 4.0

    def test_planning_routes_to_local(self, router_healthy):
        decision = router_healthy.route("planning")
        assert decision.target == "local"
        assert decision.quality_threshold == 8
        assert decision.timeout_s == 30.0

    def test_selection_routes_to_local(self, router_healthy):
        decision = router_healthy.route("selection")
        assert decision.target == "local"
        assert decision.quality_threshold == 8
        assert decision.timeout_s == 30.0

    def test_summarization_routes_to_local(self, router_healthy):
        decision = router_healthy.route("summarization")
        assert decision.target == "local"
        assert decision.quality_threshold == 8
        assert decision.timeout_s == 30.0

    def test_broadcast_routes_to_local_when_tripped(self, router_healthy):
        # Manually trip the circuit breaker
        router_healthy._cb.tripped = True
        router_healthy._cb.tripped_at = time.time()

        decision = router_healthy.route("broadcast")
        assert decision.target == "local"
        assert decision.quality_threshold == 10
        assert decision.timeout_s == 30.0

    def test_non_broadcast_unaffected_by_trip(self, router_healthy):
        router_healthy._cb.tripped = True
        router_healthy._cb.tripped_at = time.time()

        for task in ("planning", "selection", "summarization"):
            decision = router_healthy.route(task)
            assert decision.target == "local"
            assert decision.quality_threshold == 8


# ---------------------------------------------------------------------------
# call_remote() tests
# ---------------------------------------------------------------------------


class TestCallRemote:
    """Tests for ModelRouter.call_remote()."""

    @pytest.mark.asyncio
    async def test_successful_call(self, router_healthy):
        result = await router_healthy.call_remote("Generate a line.", timeout_s=4.0)
        assert result == "A witty broadcast line."
        assert router_healthy._cb.request_count == 1
        assert router_healthy._cb.error_count == 0

    @pytest.mark.asyncio
    async def test_timeout_returns_none(self, mock_remote_timeout, mock_local):
        router = ModelRouter(remote_model=mock_remote_timeout, local_model=mock_local)
        result = await router.call_remote("Generate a line.", timeout_s=0.1)
        assert result is None
        assert router._cb.error_count == 1

    @pytest.mark.asyncio
    async def test_exception_returns_none(self, mock_remote_error, mock_local):
        router = ModelRouter(remote_model=mock_remote_error, local_model=mock_local)
        result = await router.call_remote("Generate a line.", timeout_s=4.0)
        assert result is None
        assert router._cb.error_count == 1

    @pytest.mark.asyncio
    async def test_empty_response_returns_none(self, mock_remote_empty, mock_local):
        router = ModelRouter(remote_model=mock_remote_empty, local_model=mock_local)
        result = await router.call_remote("Generate a line.", timeout_s=4.0)
        assert result is None
        assert router._cb.error_count == 1

    @pytest.mark.asyncio
    async def test_no_remote_model_returns_none(self, router_no_remote):
        result = await router_no_remote.call_remote("Generate a line.", timeout_s=4.0)
        assert result is None
        assert router_no_remote._cb.error_count == 1

    @pytest.mark.asyncio
    async def test_invalid_response_returns_none(self, mock_local):
        """Remote returns a multi-line response which fails validation."""

        async def _multi_line(prompt: str) -> str:
            return "Line one.\nLine two."

        router = ModelRouter(remote_model=_multi_line, local_model=mock_local)
        result = await router.call_remote("Generate a line.", timeout_s=4.0)
        assert result is None
        assert router._cb.error_count == 1


# ---------------------------------------------------------------------------
# validate_response() tests
# ---------------------------------------------------------------------------


class TestValidateResponse:
    """Tests for ModelRouter.validate_response()."""

    def test_valid_single_line(self, router_healthy):
        assert router_healthy.validate_response("A sharp comeback.") is True

    def test_valid_with_leading_trailing_whitespace(self, router_healthy):
        assert router_healthy.validate_response("  Hello world.  ") is True

    def test_valid_single_character(self, router_healthy):
        assert router_healthy.validate_response("X") is True

    def test_rejects_empty_string(self, router_healthy):
        assert router_healthy.validate_response("") is False

    def test_rejects_whitespace_only(self, router_healthy):
        assert router_healthy.validate_response("   \t  ") is False

    def test_rejects_multiline(self, router_healthy):
        assert router_healthy.validate_response("Line one.\nLine two.") is False

    def test_rejects_control_characters(self, router_healthy):
        # Tab character (0x09)
        assert router_healthy.validate_response("Hello\tworld") is False
        # Bell character (0x07)
        assert router_healthy.validate_response("Hello\x07world") is False
        # Null byte (0x00)
        assert router_healthy.validate_response("Hello\x00world") is False

    def test_accepts_newline_only_at_boundaries(self, router_healthy):
        # Newline at end only (stripped it becomes single line)
        assert router_healthy.validate_response("Hello world.\n") is True

    def test_rejects_carriage_return(self, router_healthy):
        # CR is 0x0D, which is < 0x20 and not \n
        assert router_healthy.validate_response("Hello\rworld") is False


# ---------------------------------------------------------------------------
# Circuit breaker tests
# ---------------------------------------------------------------------------


class TestCircuitBreaker:
    """Tests for circuit breaker activation and state management."""

    @pytest.mark.asyncio
    async def test_no_trip_under_min_requests(self, mock_local):
        """Circuit breaker should NOT trip with fewer than 5 requests even at 100% errors."""

        async def _fail(prompt: str) -> str:
            raise ConnectionError("fail")

        router = ModelRouter(remote_model=_fail, local_model=mock_local)

        # Make 4 failing requests (under min_requests=5)
        for _ in range(4):
            await router.call_remote("test", timeout_s=1.0)

        assert router._cb.tripped is False
        assert router._cb.request_count == 4
        assert router._cb.error_count == 4

    @pytest.mark.asyncio
    async def test_trips_at_threshold(self, mock_local):
        """Circuit breaker trips at 5 requests with >20% error rate."""

        call_count = 0

        async def _sometimes_fail(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count <= 4:
                raise ConnectionError("fail")
            return "Success line."

        router = ModelRouter(remote_model=_sometimes_fail, local_model=mock_local)

        # 4 errors then 1 success = 5 requests, 80% error rate
        for _ in range(5):
            await router.call_remote("test", timeout_s=1.0)

        assert router._cb.tripped is True
        assert router._cb.request_count == 5
        assert router._cb.error_count == 4

    @pytest.mark.asyncio
    async def test_no_trip_below_threshold(self, mock_local):
        """Circuit breaker does NOT trip at exactly 20% error rate (needs >20%)."""

        call_count = 0

        async def _one_fail(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if call_count == 1:
                raise ConnectionError("fail")
            return "Success line."

        router = ModelRouter(remote_model=_one_fail, local_model=mock_local)

        # 1 error in 5 requests = exactly 20% — should NOT trip
        for _ in range(5):
            await router.call_remote("test", timeout_s=1.0)

        assert router._cb.tripped is False

    @pytest.mark.asyncio
    async def test_window_reset(self, mock_local):
        """Errors in expired window don't count toward trip."""

        async def _fail(prompt: str) -> str:
            raise ConnectionError("fail")

        router = ModelRouter(
            remote_model=_fail,
            local_model=mock_local,
            config={"window_s": 0.1},  # Very short window for testing
        )

        # Make some errors
        for _ in range(3):
            await router.call_remote("test", timeout_s=1.0)

        # Wait for window to expire
        await asyncio.sleep(0.15)

        # Make more errors — counter should be reset
        await router.call_remote("test", timeout_s=1.0)
        assert router._cb.request_count == 1  # Window was reset


# ---------------------------------------------------------------------------
# should_probe() and probe_remote() tests
# ---------------------------------------------------------------------------


class TestProbing:
    """Tests for circuit breaker recovery via probing."""

    def test_should_probe_false_when_not_tripped(self, router_healthy):
        assert router_healthy.should_probe() is False

    def test_should_probe_false_when_cooldown_not_elapsed(self, router_healthy):
        router_healthy._cb.tripped = True
        router_healthy._cb.tripped_at = time.time()
        assert router_healthy.should_probe() is False

    def test_should_probe_true_after_cooldown(self, router_healthy):
        router_healthy._cb.tripped = True
        router_healthy._cb.tripped_at = time.time() - 61  # 61s ago, cooldown is 60s
        assert router_healthy.should_probe() is True

    @pytest.mark.asyncio
    async def test_probe_success_restores_circuit(self, mock_remote_success, mock_local):
        router = ModelRouter(remote_model=mock_remote_success, local_model=mock_local)
        router._cb.tripped = True
        router._cb.tripped_at = time.time() - 61

        result = await router.probe_remote()
        assert result is True
        assert router._cb.tripped is False
        assert router._cb.request_count == 0
        assert router._cb.error_count == 0

    @pytest.mark.asyncio
    async def test_probe_failure_keeps_circuit_tripped(self, mock_remote_error, mock_local):
        router = ModelRouter(remote_model=mock_remote_error, local_model=mock_local)
        router._cb.tripped = True
        old_tripped_at = time.time() - 61
        router._cb.tripped_at = old_tripped_at

        result = await router.probe_remote()
        assert result is False
        assert router._cb.tripped is True
        # tripped_at should be updated for fresh cooldown
        assert router._cb.tripped_at > old_tripped_at

    @pytest.mark.asyncio
    async def test_probe_no_remote_model(self, router_no_remote):
        router_no_remote._cb.tripped = True
        router_no_remote._cb.tripped_at = time.time() - 61

        result = await router_no_remote.probe_remote()
        assert result is False

    @pytest.mark.asyncio
    async def test_probe_invalid_response(self, mock_local):
        """Probe that gets an invalid response keeps circuit tripped."""

        async def _invalid(prompt: str) -> str:
            return ""

        router = ModelRouter(remote_model=_invalid, local_model=mock_local)
        router._cb.tripped = True
        router._cb.tripped_at = time.time() - 61

        result = await router.probe_remote()
        assert result is False
        assert router._cb.tripped is True


# ---------------------------------------------------------------------------
# Integration-style test: full lifecycle
# ---------------------------------------------------------------------------


class TestLifecycle:
    """End-to-end lifecycle tests for the model router."""

    @pytest.mark.asyncio
    async def test_healthy_trip_probe_recover(self, mock_local):
        """Full cycle: healthy → errors → trip → cooldown → probe → recover."""

        call_count = 0
        should_fail = True

        async def _controllable(prompt: str) -> str:
            nonlocal call_count
            call_count += 1
            if should_fail:
                raise ConnectionError("fail")
            return "Recovered line."

        router = ModelRouter(
            remote_model=_controllable,
            local_model=mock_local,
            config={"cooldown_s": 0.1, "min_requests": 5},
        )

        # 1. Start healthy
        assert router.route("broadcast").target == "remote"

        # 2. Accumulate errors to trip
        for _ in range(6):
            await router.call_remote("test", timeout_s=1.0)

        assert router._cb.tripped is True
        assert router.route("broadcast").target == "local"
        assert router.route("broadcast").quality_threshold == 10

        # 3. Wait for cooldown
        router._cb.tripped_at = time.time() - 1  # Pretend cooldown elapsed
        assert router.should_probe() is True

        # 4. Fix the remote and probe
        should_fail = False
        success = await router.probe_remote()
        assert success is True

        # 5. Circuit is restored
        assert router._cb.tripped is False
        assert router.route("broadcast").target == "remote"


# ---------------------------------------------------------------------------
# Property-Based Tests (Hypothesis)
# ---------------------------------------------------------------------------

from hypothesis import given, settings
from hypothesis import strategies as st

from conftest import st_request_outcomes


class TestProperty16CircuitBreakerActivation:
    """**Property 16: Circuit Breaker Activation Conditions**

    Circuit breaker activates iff ≥5 requests AND >20% error rate in 5-min window.

    **Validates: Requirements 6.6**
    """

    @given(
        outcomes=st_request_outcomes(min_size=1, max_size=50),
    )
    @settings(max_examples=200)
    def test_circuit_breaker_activation_iff_conditions_met(self, outcomes: list[bool]):
        """CB activates iff at any point ≥5 requests AND >20% error rate."""

        async def _succeed(prompt: str) -> str:
            return "Success line."

        async def _fail(prompt: str) -> str:
            raise ConnectionError("fail")

        router = ModelRouter(remote_model=_succeed, local_model=_succeed)

        # Track whether trip conditions were met at any point during processing
        should_have_tripped = False
        running_total = 0
        running_errors = 0

        for success in outcomes:
            running_total += 1
            if not success:
                running_errors += 1

            # Check if conditions met at this point
            if running_total >= 5 and running_errors / running_total > 0.20:
                should_have_tripped = True

            if success:
                router._record_success()
            else:
                router._record_error()

        if should_have_tripped:
            assert router._cb.tripped is True, (
                "CB should be tripped: conditions were met during sequence"
            )
        else:
            assert router._cb.tripped is False, (
                "CB should NOT be tripped: conditions never met during sequence"
            )

    @given(
        num_errors=st.integers(min_value=0, max_value=4),
    )
    @settings(max_examples=20)
    def test_never_trips_under_5_requests(self, num_errors: int):
        """CB never trips with fewer than 5 total requests."""

        async def _succeed(prompt: str) -> str:
            return "Success."

        router = ModelRouter(remote_model=_succeed, local_model=_succeed)

        for _ in range(num_errors):
            router._record_error()

        assert router._cb.tripped is False
        assert router._cb.request_count == num_errors


class TestProperty17ResponseValidation:
    """**Property 17: Response Validation**

    Accept iff ≥1 non-whitespace, no control chars, single line.

    **Validates: Requirements 6.4**
    """

    @given(
        text=st.text(
            min_size=1,
            max_size=200,
            alphabet=st.characters(
                whitelist_categories=("L", "N", "P", "S", "Z"),
                blacklist_characters="\n\r\t\x00\x01\x02\x03\x04\x05\x06\x07\x08\x0b\x0c\x0e\x0f",
            ),
        ),
    )
    @settings(max_examples=200)
    def test_valid_single_line_text_accepted(self, text: str):
        """Single-line text with printable chars and ≥1 non-whitespace is accepted."""

        async def _noop(prompt: str) -> str:
            return ""

        router = ModelRouter(remote_model=_noop, local_model=_noop)

        # Only accept if it has at least one non-whitespace character
        has_content = len(text.strip()) > 0
        has_newline = "\n" in text.strip()

        if has_content and not has_newline:
            assert router.validate_response(text) is True, f"Should accept valid text: {repr(text)}"

    @given(
        text=st.text(min_size=0, max_size=100),
    )
    @settings(max_examples=200)
    def test_validation_consistency(self, text: str):
        """validate_response never crashes and returns a bool."""

        async def _noop(prompt: str) -> str:
            return ""

        router = ModelRouter(remote_model=_noop, local_model=_noop)

        result = router.validate_response(text)
        assert isinstance(result, bool)

        # If accepted, verify the three conditions hold
        if result:
            stripped = text.strip()
            assert len(stripped) > 0, "Accepted empty text"
            assert "\n" not in stripped, "Accepted multi-line text"
            for ch in text:
                code = ord(ch)
                assert code >= 0x20 or ch == "\n", (
                    f"Accepted control char {repr(ch)} (0x{code:02x})"
                )

    @given(
        base=st.text(
            min_size=1,
            max_size=50,
            alphabet=st.characters(whitelist_categories=("L", "N", "P", "S")),
        ).filter(lambda t: len(t.strip()) > 0),
        control_char=st.sampled_from(
            [chr(i) for i in range(0x00, 0x20) if chr(i) not in ("\n", " ")]
        ),
    )
    @settings(max_examples=100)
    def test_control_chars_always_rejected(self, base: str, control_char: str):
        """Any string containing control characters (not space/newline) is rejected."""

        async def _noop(prompt: str) -> str:
            return ""

        router = ModelRouter(remote_model=_noop, local_model=_noop)
        # Insert control char in the middle
        injected = base[: len(base) // 2] + control_char + base[len(base) // 2 :]
        assert router.validate_response(injected) is False, (
            f"Should reject text with control char {repr(control_char)}: {repr(injected)}"
        )
