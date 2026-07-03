"""PKI Manager — certificate chain validation (SWR-C-020)."""
import time
from dataclasses import dataclass

from sim.csm import CSM
from sim.dem import DEM, Severity
from sim.hsm import HSM


class PKIError(Exception):
    pass


@dataclass
class SimCert:
    """Simulated certificate for testing."""
    subject: str
    issuer: str
    valid_from: float
    valid_until: float
    revoked: bool = False
    trusted_root: bool = False
    signature: bytes = b""


class PKIManager:
    """Validates certificate chains against the OEM trust anchor (SWR-C-020)."""

    TRUSTED_ROOT = "OEM_ROOT_CA"
    _REVOKED: set[str] = set()

    def __init__(self, csm: CSM, hsm: HSM, dem: DEM | None = None) -> None:
        self._csm = csm
        self._hsm = hsm
        self._dem = dem

    def validate_chain(self, chain: list[SimCert]) -> bool:
        """Validate a certificate chain for flashing authorization.

        Args:
            chain: Ordered list from leaf to root.

        Returns:
            True if valid.

        Raises:
            PKIError: On any validation failure.
        """
        now = time.time()
        for cert in chain:
            if cert.valid_until < now:
                self._log_warning(f"PKI: certificate expired: {cert.subject}")
                raise PKIError(f"expired: {cert.subject}")
            if cert.subject in self._REVOKED or cert.revoked:
                self._log_warning(f"PKI: certificate revoked: {cert.subject}")
                raise PKIError(f"revoked: {cert.subject}")

        root = chain[-1]
        if not root.trusted_root and root.issuer != self.TRUSTED_ROOT:
            self._log_warning(f"PKI: untrusted root: {root.subject}")
            raise PKIError(f"untrusted: {root.subject}")

        return True

    def build_test_chain(
        self,
        valid: bool = False,
        expired: bool = False,
        revoked: bool = False,
        untrusted_root: bool = False,
    ) -> list[SimCert]:
        """Build a simulated certificate chain for test scenarios.

        Args:
            valid: Build a passing chain.
            expired: Build a chain with an expired leaf.
            revoked: Build a chain with a revoked leaf.
            untrusted_root: Build a chain with an unknown root CA.

        Returns:
            List of SimCert from leaf to root.
        """
        now = time.time()
        if valid:
            leaf = SimCert("TESTER_MFG", self.TRUSTED_ROOT, now - 3600, now + 3600)
            root = SimCert(self.TRUSTED_ROOT, self.TRUSTED_ROOT, now - 86400, now + 86400,
                           trusted_root=True)
            return [leaf, root]
        if expired:
            leaf = SimCert("TESTER_MFG", self.TRUSTED_ROOT, now - 7200, now - 3600)
            root = SimCert(self.TRUSTED_ROOT, self.TRUSTED_ROOT, now - 86400, now + 86400,
                           trusted_root=True)
            return [leaf, root]
        if revoked:
            leaf = SimCert("REVOKED_TESTER", self.TRUSTED_ROOT, now - 3600, now + 3600,
                           revoked=True)
            root = SimCert(self.TRUSTED_ROOT, self.TRUSTED_ROOT, now - 86400, now + 86400,
                           trusted_root=True)
            return [leaf, root]
        if untrusted_root:
            leaf = SimCert("TESTER_MFG", "UNKNOWN_CA", now - 3600, now + 3600)
            root = SimCert("UNKNOWN_CA", "UNKNOWN_CA", now - 86400, now + 86400)
            return [leaf, root]
        return self.build_test_chain(valid=True)

    def _log_warning(self, message: str) -> None:
        if self._dem:
            self._dem.log("PKI_FAILURE", Severity.WARNING, message, "SWR-C-020")
