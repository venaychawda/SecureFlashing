"""Recovery Manager — detects incomplete flash and restores last valid bank (SWR-C-009)."""
from sim import config
from sim.dem import DEM, Severity
from sim.nvm import NvM


class RecoveryManager:
    """Handles power-loss recovery by checking flash_pending and rolling back active bank."""

    def __init__(self, nvm: NvM, dem: DEM) -> None:
        self._nvm = nvm
        self._dem = dem

    def recover(self) -> str | None:
        """Check flash_pending flag and roll back to last valid bank if set.

        Returns:
            The bank rolled back to, or None if no recovery was needed.
        """
        if not self._nvm.read(config.FLASH_PENDING_KEY, False):
            return None

        fallback = self._nvm.read(config.LAST_VALID_BANK_KEY, config.DEFAULT_ACTIVE_BANK)
        self._nvm.write(config.ACTIVE_BANK_KEY, fallback)
        self._nvm.write(config.FLASH_PENDING_KEY, False)
        self._dem.log(
            "RECOVERY_ACTIVATED",
            Severity.WARNING,
            f"Power-loss recovery: rolled back to bank {fallback}",
            "SWR-C-009",
            {"recovered_bank": fallback},
        )
        return fallback
