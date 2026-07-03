"""SecurityAccess — ECDSA challenge-response, roles, retry counter, lockout (SWR-C-001/002/006/011)."""
from enum import Enum

from sim import config
from sim.csm import CSM
from sim.dem import DEM, Severity
from sim.hsm import HSM
from sim.nvm import NvM
from sim.pki_manager import PKIManager


class FlashRole(str, Enum):
    MANUFACTURING = "manufacturing"
    SERVICE = "service"
    ENGINEERING = "engineering"
    DEVELOPMENT = "development"


class AuthError(Exception):
    pass


class SecurityAccess:
    """Manages authentication lifecycle: challenge issuance, ECDSA verification, lockout."""

    def __init__(self, csm: CSM, nvm: NvM, dem: DEM, pki_manager: PKIManager,
                 hsm: HSM) -> None:
        self._csm = csm
        self._nvm = nvm
        self._dem = dem
        self._pki = pki_manager
        self._hsm = hsm
        self._pending_challenge: bytes | None = None
        self._pending_role: FlashRole | None = None
        self._authenticated: bool = False
        self._role: FlashRole | None = None
        self._locked: bool = False
        self._role_key_map: dict[FlashRole, str] = {
            FlashRole.MANUFACTURING: config.ROLE_KEY_MAP["manufacturing"],
            FlashRole.SERVICE:       config.ROLE_KEY_MAP["service"],
            FlashRole.ENGINEERING:   config.ROLE_KEY_MAP["engineering"],
            FlashRole.DEVELOPMENT:   config.ROLE_KEY_MAP["development"],
        }

    def _register_role_key(self, role: FlashRole, key_id: str) -> None:
        """Override the HSM key ID for a given role (used in tests)."""
        self._role_key_map[role] = key_id

    def get_challenge(self, role: FlashRole) -> bytes:
        """Issue a fresh nonce challenge for the given role.

        Args:
            role: Requested flashing role.

        Returns:
            32-byte nonce challenge.

        Raises:
            AuthError: If locked out.
        """
        if self._locked:
            raise AuthError("locked")
        self._pending_challenge = self._hsm.generate_nonce()
        self._pending_role = role
        self._authenticated = False
        return self._pending_challenge

    def verify_response(self, role: FlashRole, signature: bytes) -> bool:
        """Verify the tester's ECDSA signed response.

        Args:
            role: Claimed role.
            signature: DER-encoded ECDSA signature over the challenge.

        Returns:
            True on success; False on invalid signature.

        Raises:
            AuthError: If locked or no pending challenge.
        """
        if self._locked:
            raise AuthError("locked")
        if self._pending_challenge is None:
            raise AuthError("no_challenge")

        key_id = self._role_key_map.get(role, config.ROLE_KEY_MAP.get(role.value, ""))
        valid = self._csm.verify_signature(self._pending_challenge, signature, key_id)

        if valid:
            self._nvm.write(config.AUTH_RETRY_KEY, 0)
            self._authenticated = True
            self._role = role
            self._pending_challenge = None
            self._dem.log("AUTH_SUCCESS", Severity.INFO,
                          f"Authenticated as {role.value}", "SWR-C-001",
                          {"role": role.value})
            return True

        retry_count = self._nvm.increment_counter(config.AUTH_RETRY_KEY)
        self._dem.log("AUTH_FAILURE", Severity.WARNING,
                      f"Invalid signature for role {role.value} (attempt {retry_count})",
                      "SWR-C-011", {"retry_count": retry_count})

        if retry_count >= config.MAX_AUTH_RETRIES:
            self._locked = True
            self._dem.log("AUTH_LOCKOUT", Severity.CRITICAL,
                          f"Lockout after {retry_count} failures", "SWR-C-011")

        return False

    def is_authenticated(self) -> bool:
        """Return True if a valid session is currently authenticated."""
        return self._authenticated

    def get_role(self) -> FlashRole | None:
        """Return the current authenticated role, or None."""
        return self._role

    def is_locked(self) -> bool:
        """Return True if authentication is locked out."""
        return self._locked

    def reset(self) -> None:
        """Reset authentication state (simulates ECU reset / controlled recovery)."""
        self._authenticated = False
        self._role = None
        self._locked = False
        self._pending_challenge = None
        self._pending_role = None
        self._nvm.write(config.AUTH_RETRY_KEY, 0)
