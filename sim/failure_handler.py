"""Failure Handler — safe abort and buffer sanitization (SWR-C-015)."""
from sim import config
from sim.dem import DEM, Severity
from sim.nvm import NvM


class FailureHandler:
    """Executes safe abort: zeroes staging buffers and emits CRITICAL DEM event."""

    def __init__(self, nvm: NvM, dem: DEM) -> None:
        self._nvm = nvm
        self._dem = dem

    def abort_and_sanitize(self, context: dict) -> None:
        """Zero all staging buffers, clear flash_pending, log CRITICAL event.

        Args:
            context: Dict that may contain 'staging_buffer' (bytearray) and other state.
                     Modified in-place: staging_buffer is zeroed.
        """
        buf = context.get("staging_buffer")
        if isinstance(buf, (bytearray, memoryview)):
            for i in range(len(buf)):
                buf[i] = 0

        self._nvm.write(config.FLASH_PENDING_KEY, False)

        self._dem.log(
            "FLASH_ABORT",
            Severity.CRITICAL,
            "Flash aborted: temporary buffers sanitized",
            "SWR-C-015",
            {"reason": context.get("reason", "unspecified")},
        )
