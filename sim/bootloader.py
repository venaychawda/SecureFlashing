"""Bootloader — A/B bank model with secure boot signature validation (SWR-C-009/010)."""
from sim import config
from sim.csm import CSM
from sim.dem import DEM, Severity
from sim.nvm import NvM


class BootError(Exception):
    pass


class Bootloader:
    """Manages A/B banks and performs signature verification at every boot."""

    def __init__(self, csm: CSM, nvm: NvM, dem: DEM) -> None:
        self._csm = csm
        self._nvm = nvm
        self._dem = dem
        if self._nvm.read(config.ACTIVE_BANK_KEY) is None:
            self._nvm.write(config.ACTIVE_BANK_KEY, config.DEFAULT_ACTIVE_BANK)
        if self._nvm.read(config.LAST_VALID_BANK_KEY) is None:
            self._nvm.write(config.LAST_VALID_BANK_KEY, config.DEFAULT_ACTIVE_BANK)

    def commit_bank(self, bank: str, image_hash: bytes) -> None:
        """Record a newly programmed bank as pending activation.

        Args:
            bank: Bank identifier ("A" or "B").
            image_hash: SHA-256 hash of the programmed image.

        Raises:
            BootError: If bank identifier is invalid.
        """
        if bank not in config.BANKS:
            raise BootError("unknown_bank")
        self._nvm.write(f"bank_{bank}_hash", image_hash.hex())
        self._nvm.write("pending_bank", bank)

    def boot(self) -> bool:
        """Perform secure boot: verify active bank signature.

        Returns:
            True if boot succeeded with a valid image, False otherwise.
        """
        if self._nvm.read(config.FLASH_PENDING_KEY, False):
            self._recover_pending()

        active = self._nvm.read(config.ACTIVE_BANK_KEY, config.DEFAULT_ACTIVE_BANK)
        bank_data = self._nvm.read(f"bank_{active}")

        if not bank_data:
            self._dem.log("SECURE_BOOT_FAIL", Severity.CRITICAL,
                          f"No image in bank {active}", "SWR-C-010")
            return False

        try:
            image_bytes = bytes.fromhex(bank_data["image"])
            sig_bytes = bytes.fromhex(bank_data["signature"])
        except (KeyError, ValueError):
            self._dem.log("SECURE_BOOT_FAIL", Severity.CRITICAL,
                          f"Bank {active} data corrupt", "SWR-C-010")
            return False

        valid = self._csm.verify_signature(image_bytes, sig_bytes, "oem_signing_key")
        if valid:
            self._nvm.write(config.LAST_VALID_BANK_KEY, active)
            self._dem.log("SECURE_BOOT_OK", Severity.INFO,
                          f"Secure boot succeeded on bank {active}", "SWR-C-010")
            return True

        self._dem.log("SECURE_BOOT_FAIL", Severity.CRITICAL,
                      f"Secure boot failed: signature invalid on bank {active}", "SWR-C-010")
        return False

    def trigger_reset(self) -> bool:
        """Simulate an ECU reset + secure boot sequence.

        Returns:
            True if boot succeeds.
        """
        return self.boot()

    def get_active_bank(self) -> str:
        """Return the currently active bank identifier."""
        return self._nvm.read(config.ACTIVE_BANK_KEY, config.DEFAULT_ACTIVE_BANK)

    def get_bank_info(self) -> dict:
        """Return dict of bank states from NvM."""
        return {
            "active_bank": self.get_active_bank(),
            "last_valid_bank": self._nvm.read(config.LAST_VALID_BANK_KEY, config.DEFAULT_ACTIVE_BANK),
            "flash_pending": self._nvm.read(config.FLASH_PENDING_KEY, False),
        }

    def _recover_pending(self) -> None:
        """Fall back to last valid bank when flash_pending is set."""
        fallback = self._nvm.read(config.LAST_VALID_BANK_KEY, config.DEFAULT_ACTIVE_BANK)
        self._nvm.write(config.ACTIVE_BANK_KEY, fallback)
        self._nvm.write(config.FLASH_PENDING_KEY, False)
        self._dem.log("RECOVERY_ACTIVATED", Severity.WARNING,
                      f"flash_pending detected at boot; rolled back to bank {fallback}",
                      "SWR-C-009")
