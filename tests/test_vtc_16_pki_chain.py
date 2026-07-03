"""
VTC-16: PKI certificate chain validation
Objective: Verify flashing authorization is accepted only when certificate validation succeeds.
Requirements: SR-017
SWR-C: SWR-C-020
"""
import pytest
from sim.pki_manager import PKIError
from sim.dem import Severity


@pytest.mark.vtc("VTC-16")
class TestVTC16PKIChain:
    def test_valid_chain_accepted(self, pki_manager_stub):
        """Valid certificate chain anchored to OEM root must be accepted."""
        chain = pki_manager_stub.build_test_chain(valid=True)
        result = pki_manager_stub.validate_chain(chain)
        assert result is True

    def test_expired_cert_rejected(self, pki_manager_stub):
        """Expired certificate must be rejected."""
        chain = pki_manager_stub.build_test_chain(expired=True)
        with pytest.raises(PKIError, match="expired"):
            pki_manager_stub.validate_chain(chain)

    def test_revoked_cert_rejected(self, pki_manager_stub):
        """Revoked certificate must be rejected."""
        chain = pki_manager_stub.build_test_chain(revoked=True)
        with pytest.raises(PKIError, match="revoked"):
            pki_manager_stub.validate_chain(chain)

    def test_untrusted_root_rejected(self, pki_manager_stub):
        """Certificate chain with untrusted root must be rejected."""
        chain = pki_manager_stub.build_test_chain(untrusted_root=True)
        with pytest.raises(PKIError, match="untrusted"):
            pki_manager_stub.validate_chain(chain)

    def test_rejection_logged_in_dem(self, pki_manager_stub, dem_stub):
        """PKI rejection must produce a WARNING DEM event."""
        chain = pki_manager_stub.build_test_chain(expired=True)
        try:
            pki_manager_stub.validate_chain(chain)
        except PKIError:
            pass
        events = dem_stub.get_events_by_severity(Severity.WARNING)
        assert any("pki" in e.description.lower() or "cert" in e.description.lower()
                   for e in events)
