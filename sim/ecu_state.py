"""Shared ECU state machine — single source of truth for ECU lifecycle state."""
from enum import Enum


class ECUMode(str, Enum):
    DEFAULT_SESSION = "DEFAULT_SESSION"
    PROGRAMMING_SESSION = "PROGRAMMING_SESSION"
    AUTHENTICATED = "AUTHENTICATED"
    LOCKED = "LOCKED"
    BOOTING = "BOOTING"
    RUNNING = "RUNNING"
    SAFE_MODE = "SAFE_MODE"


class ECUState:
    """Holds and transitions the current ECU operational mode."""

    def __init__(self) -> None:
        self._mode = ECUMode.DEFAULT_SESSION
        self._active_role: str | None = None

    @property
    def mode(self) -> ECUMode:
        return self._mode

    @property
    def active_role(self) -> str | None:
        return self._active_role

    def transition(self, new_mode: ECUMode, role: str | None = None) -> None:
        """Transition to new_mode, optionally setting active role."""
        self._mode = new_mode
        if role is not None:
            self._active_role = role
        if new_mode in (ECUMode.DEFAULT_SESSION, ECUMode.LOCKED):
            self._active_role = None

    def to_dict(self) -> dict:
        return {"mode": self._mode.value, "active_role": self._active_role}

    def reset(self) -> None:
        self._mode = ECUMode.DEFAULT_SESSION
        self._active_role = None
