"""Central constants registry — all magic numbers live here (SWR-C-016)."""
from typing import Final

MAX_AUTH_RETRIES: Final[int] = 3
SESSION_TIMEOUT_S: Final[float] = 30.0
MAX_BLOCK_SIZE: Final[int] = 0x100
MAX_IMAGE_SIZE: Final[int] = 0x100000
NONCE_SIZE: Final[int] = 32

SW_VERSION_KEY: Final[str] = "sw_version_counter"
TX_COUNTER_KEY: Final[str] = "tx_counter"
AUTH_RETRY_KEY: Final[str] = "auth_retry_count"
FLASH_PENDING_KEY: Final[str] = "flash_pending"
ACTIVE_BANK_KEY: Final[str] = "active_bank"
LAST_VALID_BANK_KEY: Final[str] = "last_valid_bank"

DEFAULT_ACTIVE_BANK: Final[str] = "A"
BANKS: Final[tuple[str, ...]] = ("A", "B")

MEMORY_MAP: Final[dict] = {
    "BOOTLOADER":   {"start": 0x08000000, "end": 0x08010000, "roles": ["manufacturing"]},
    "APPLICATION":  {"start": 0x08010000, "end": 0x08110000, "roles": ["manufacturing", "service", "engineering", "development"]},
    "CALIBRATION":  {"start": 0x08110000, "end": 0x08120000, "roles": ["engineering", "manufacturing"]},
    "HSM":          {"start": 0x10000000, "end": 0x10010000, "roles": []},
}

HSM_KEY_IDS: Final[dict] = {
    "oem_signing_key":  "oem_signing_key",
    "tester_mfg_key":   "tester_mfg_key",
    "tester_svc_key":   "tester_svc_key",
    "tester_eng_key":   "tester_eng_key",
    "tester_dev_key":   "tester_dev_key",
}

ROLE_KEY_MAP: Final[dict] = {
    "manufacturing": "tester_mfg_key",
    "service":       "tester_svc_key",
    "engineering":   "tester_eng_key",
    "development":   "tester_dev_key",
}
