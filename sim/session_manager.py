"""Session Manager — freshness, replay protection, inactivity timeout (SWR-C-005)."""
import time

from sim import config
from sim.dem import DEM, Severity
from sim.nvm import NvM


class SessionError(Exception):
    pass


class SessionManager:
    """Manages session freshness, transaction counter replay window, and timeout."""

    def __init__(self, nvm: NvM, dem: DEM) -> None:
        self._nvm = nvm
        self._dem = dem
        self._session_start: float | None = None
        self._last_activity: float | None = None

    def create_session(self) -> None:
        """Start a new session, reset inactivity timer, increment transaction counter."""
        now = time.monotonic()
        self._session_start = now
        self._last_activity = now
        self._nvm.increment_counter(config.TX_COUNTER_KEY)

    def is_active(self) -> bool:
        """Return True if a session exists and has not exceeded the inactivity timeout."""
        if self._last_activity is None:
            return False
        elapsed = time.monotonic() - self._last_activity
        return elapsed < config.SESSION_TIMEOUT_S

    def validate_active(self) -> None:
        """Assert that the current session is still active.

        Raises:
            SessionError: If no session or session has timed out.
        """
        if self._last_activity is None:
            raise SessionError("no_session")
        elapsed = time.monotonic() - self._last_activity
        if elapsed >= config.SESSION_TIMEOUT_S:
            self._dem.log("SESSION_TIMEOUT", Severity.WARNING,
                          "Session timed out due to inactivity", "SWR-C-005",
                          {"elapsed_s": elapsed})
            raise SessionError("timeout")

    def validate_freshness(self, received_counter: int) -> None:
        """Check that received_counter is strictly greater than stored value.

        Args:
            received_counter: Transaction counter value from incoming message.

        Raises:
            SessionError: If replay detected.
        """
        stored = self._nvm.get_counter(config.TX_COUNTER_KEY)
        if received_counter <= stored:
            self._dem.log("REPLAY_DETECTED", Severity.WARNING,
                          f"Replay: received={received_counter} stored={stored}",
                          "SWR-C-005")
            raise SessionError("replay")
        self._nvm.write(config.TX_COUNTER_KEY, received_counter)
        if self._last_activity is not None:
            self._last_activity = time.monotonic()

    def touch(self) -> None:
        """Update last activity timestamp to prevent timeout."""
        self._last_activity = time.monotonic()

    def destroy(self) -> None:
        """Invalidate the current session."""
        self._session_start = None
        self._last_activity = None
