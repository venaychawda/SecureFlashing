"""DEM — Diagnostic Event Manager simulation (SWR-C-014)."""
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any


class Severity(str, Enum):
    INFO = "INFO"
    WARNING = "WARNING"
    CRITICAL = "CRITICAL"


@dataclass
class DemEvent:
    event_id: str
    timestamp: float
    severity: Severity
    description: str
    swr_ref: str
    data: dict = field(default_factory=dict)


class DEM:
    """Records security events for audit and forensic traceability."""

    def __init__(self) -> None:
        self._events: list[DemEvent] = []
        self._counter: int = 0

    def log(self, event_id: str, severity: Severity, description: str,
            swr_ref: str = "", data: dict[str, Any] | None = None) -> DemEvent:
        """Record a security event.

        Args:
            event_id: Short event type identifier (e.g. "AUTH_FAILURE").
            severity: INFO | WARNING | CRITICAL.
            description: Human-readable description.
            swr_ref: Associated SWR-C requirement ID.
            data: Optional context dict.

        Returns:
            The created DemEvent.
        """
        self._counter += 1
        evt = DemEvent(
            event_id=f"DEM-{self._counter:04d}-{event_id}",
            timestamp=time.monotonic(),
            severity=severity,
            description=description,
            swr_ref=swr_ref,
            data=data or {},
        )
        self._events.append(evt)
        return evt

    def get_events(self) -> list[DemEvent]:
        """Return all recorded events."""
        return list(self._events)

    def get_events_by_severity(self, severity: Severity) -> list[DemEvent]:
        """Return events filtered by severity level.

        Args:
            severity: Severity level to filter on.

        Returns:
            List of matching DemEvents.
        """
        return [e for e in self._events if e.severity == severity]

    def clear(self) -> None:
        """Clear all events (test use only)."""
        self._events.clear()
        self._counter = 0
