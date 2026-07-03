"""Flash Manager — Program-Verify-Commit with memory boundary enforcement (SWR-C-003/004/007/008/017)."""
import uuid
from enum import Enum

from sim import config
from sim.csm import CSM
from sim.dem import DEM, Severity
from sim.failure_handler import FailureHandler
from sim.nvm import NvM
from sim.version_manager import VersionError, VersionManager


class FlashState(str, Enum):
    IDLE = "IDLE"
    DOWNLOADING = "DOWNLOADING"
    VERIFYING = "VERIFYING"
    PROGRAMMING = "PROGRAMMING"
    COMMITTING = "COMMITTING"
    ABORTED = "ABORTED"


class FlashError(Exception):
    pass


class FlashManager:
    """Implements block-wise secure flashing: download → verify → program → commit."""

    def __init__(self, csm: CSM, nvm: NvM, dem: DEM,
                 failure_handler: FailureHandler, version_manager: VersionManager) -> None:
        self._csm = csm
        self._nvm = nvm
        self._dem = dem
        self._fh = failure_handler
        self._vm = version_manager
        self._staging_buffer: dict[int, bytes] = {}
        self._state = FlashState.IDLE
        self._target_address: int = 0
        self._target_size: int = 0
        self._role: str = ""
        self._hash_ctx: str = ""
        self._flash_store: dict[int, bytes] = {}
        self._pending_version: int = 0

    def begin_download(self, address: int, size: int, role: str,
                       image_version: int = 1) -> None:
        """Start a new download session after validating address and version.

        Args:
            address: Target flash start address.
            size: Total image size in bytes.
            role: Flashing role string.
            image_version: Version number from image header.

        Raises:
            FlashError: On address out of range or downgrade attempt.
        """
        self._validate_address(address, size, role)
        try:
            self._vm.check_version(image_version)
        except VersionError as exc:
            raise FlashError(f"downgrade rejected: {exc}") from exc

        self._target_address = address
        self._target_size = size
        self._role = role
        self._pending_version = image_version
        self._staging_buffer = {}
        self._hash_ctx = str(uuid.uuid4())
        self._state = FlashState.DOWNLOADING
        self._nvm.write(config.FLASH_PENDING_KEY, True)
        self._dem.log("FLASH_START", Severity.INFO,
                      f"Download started: addr=0x{address:08X} size={size} role={role}",
                      "SWR-C-008")

    def transfer_block(self, seq: int, data: bytes) -> None:
        """Accept one firmware block and accumulate into staging buffer.

        Args:
            seq: Block sequence number (1-based).
            data: Raw block data.

        Raises:
            FlashError: If not in DOWNLOADING state.
        """
        if self._state != FlashState.DOWNLOADING:
            raise FlashError("sequence_error")
        self._staging_buffer[seq] = data
        self._csm.hash_update(self._hash_ctx, data)

    def finalize(self, full_image: bytes, image_signature: bytes) -> None:
        """Verify signature and hash, then program and commit.

        Args:
            full_image: Complete image bytes (used for signature verification).
            image_signature: OEM ECDSA signature over full_image.

        Raises:
            FlashError: On any verification failure (staging buffer is sanitized).
        """
        self._state = FlashState.VERIFYING
        staging_bytearray = bytearray(b"".join(v for _, v in sorted(self._staging_buffer.items())))
        context = {"staging_buffer": staging_bytearray, "reason": ""}

        try:
            sig_valid = self._csm.verify_signature(full_image, image_signature, "oem_signing_key")
        except Exception as exc:
            context["reason"] = "hsm_failure"
            self._state = FlashState.ABORTED
            self._fh.abort_and_sanitize(context)
            self._staging_buffer = {}
            raise FlashError("hsm_failure") from exc

        if not sig_valid:
            context["reason"] = "signature_invalid"
            self._state = FlashState.ABORTED
            self._fh.abort_and_sanitize(context)
            self._staging_buffer = {}
            raise FlashError("signature_invalid")

        computed_hash = self._csm.hash_finish(self._hash_ctx)
        expected_hash = self._csm.compute_hash(full_image)
        if computed_hash != expected_hash:
            context["reason"] = "hash_mismatch"
            self._state = FlashState.ABORTED
            self._fh.abort_and_sanitize(context)
            self._staging_buffer = {}
            raise FlashError("hash_mismatch")

        self._state = FlashState.PROGRAMMING
        for seq in sorted(self._staging_buffer):
            self._flash_store[seq] = self._staging_buffer[seq]

        self._state = FlashState.COMMITTING
        image_hash = self._csm.compute_hash(full_image)
        self._nvm.write("pending_bank_hash", image_hash.hex())
        self._nvm.write("pending_bank_signature", image_signature.hex())

        active = self._nvm.read(config.ACTIVE_BANK_KEY, config.DEFAULT_ACTIVE_BANK)
        new_bank = "B" if active == "A" else "A"
        self._nvm.write(config.ACTIVE_BANK_KEY, new_bank)
        self._nvm.write(config.LAST_VALID_BANK_KEY, new_bank)
        self._nvm.write(f"bank_{new_bank}",
                        {"image": full_image.hex(), "signature": image_signature.hex(), "valid": True})
        self._vm.commit_version(self._pending_version)
        self._nvm.write(config.FLASH_PENDING_KEY, False)
        self._staging_buffer = {}
        self._state = FlashState.IDLE
        self._dem.log("FLASH_SUCCESS", Severity.INFO,
                      f"Flash committed to bank {new_bank}", "SWR-C-008")

    def abort(self) -> None:
        """Safe abort: sanitize buffers and reset state."""
        context = {
            "staging_buffer": bytearray(b"".join(self._staging_buffer.values())),
            "reason": "manual_abort",
        }
        self._fh.abort_and_sanitize(context)
        self._staging_buffer = {}
        self._state = FlashState.IDLE

    def get_status(self) -> dict:
        """Return current FlashManager status dict."""
        return {
            "state": self._state.value,
            "staging_buffer_size": sum(len(v) for v in self._staging_buffer.values()),
            "target_address": self._target_address,
        }

    def _validate_address(self, address: int, size: int, role: str) -> None:
        for region, meta in config.MEMORY_MAP.items():
            if meta["start"] <= address < meta["end"]:
                if role not in meta["roles"]:
                    raise FlashError(
                        f"address_out_of_range: role '{role}' not allowed in {region}"
                    )
                if address + size > meta["end"]:
                    raise FlashError(
                        f"address_out_of_range: range 0x{address:08X}+{size} exceeds {region}"
                    )
                return
        raise FlashError(f"address_out_of_range: 0x{address:08X} not in any region")
