"""
VTC-02: Authentication failure blocks flashing
Objective: Confirm invalid credentials do not permit flashing.
Requirements: SR-001; SR-008; SR-011; SR-015
SWR-C: SWR-C-001, SWR-C-011, SWR-C-014
"""
import pytest
from sim.security_access import FlashRole, AuthError
from sim.dem import Severity


@pytest.mark.vtc("VTC-02")
class TestVTC02AuthFailure:
    def test_invalid_signature_rejected(self, security_access_stub):
        """Wrong signature must be rejected."""
        security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
        bad_sig = b"\xFF" * 64
        result = security_access_stub.verify_response(FlashRole.MANUFACTURING, bad_sig)
        assert result is False

    def test_ecu_remains_locked_after_failure(self, security_access_stub):
        """ECU must not be authenticated after failed response."""
        security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
        security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        assert not security_access_stub.is_authenticated()

    def test_flash_blocked_after_failure(self, dcm_stub, security_access_stub):
        """0x34 must still return securityAccessDenied after failed auth."""
        dcm_stub.process_request(0x10, 0x02, b"")
        security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
        security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        nrc, resp = dcm_stub.process_request(0x34, 0x00, b"\x00\x00\x08\x01\x00\x00\x00\x40\x00")
        assert nrc == 0x7F
        assert resp[1] == 0x33

    def test_failure_event_logged(self, security_access_stub, dem_stub):
        """Failed auth must produce a WARNING DEM event."""
        security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
        security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        events = dem_stub.get_events_by_severity(Severity.WARNING)
        assert len(events) >= 1

    def test_retry_counter_incremented(self, security_access_stub, nvm_stub):
        """NvM auth retry counter increments on each failure."""
        security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
        security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        count = nvm_stub.get_counter("auth_retry_count")
        assert count >= 1
