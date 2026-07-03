"""
VTC-13: Maximum authentication failure lockout
Objective: Validate brute-force protection and lockout behavior.
Requirements: SR-008; SR-011; SR-015
SWR-C: SWR-C-011, SWR-C-014
"""
import pytest
from sim.security_access import FlashRole, AuthError
from sim.dem import Severity
from sim import config


@pytest.mark.vtc("VTC-13")
class TestVTC13Lockout:
    def test_lockout_after_max_retries(self, security_access_stub):
        """SecurityAccess must lock after config.MAX_AUTH_RETRIES failures."""
        for _ in range(config.MAX_AUTH_RETRIES):
            security_access_stub.get_challenge(FlashRole.MANUFACTURING)
            security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
            security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        assert security_access_stub.is_locked()

    def test_auth_raises_when_locked(self, security_access_stub):
        """get_challenge must raise AuthError when locked."""
        for _ in range(config.MAX_AUTH_RETRIES):
            security_access_stub.get_challenge(FlashRole.MANUFACTURING)
            security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
            security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        with pytest.raises(AuthError, match="locked"):
            security_access_stub.get_challenge(FlashRole.MANUFACTURING)

    def test_flash_blocked_during_lockout(self, security_access_stub, dcm_stub):
        """0x34 must be rejected with securityAccessDenied during lockout."""
        for _ in range(config.MAX_AUTH_RETRIES):
            security_access_stub.get_challenge(FlashRole.MANUFACTURING)
            security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
            security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        dcm_stub.process_request(0x10, 0x02, b"")
        nrc, resp = dcm_stub.process_request(0x34, 0x00, b"\x00\x00\x08\x01\x00\x00\x00\x40\x00")
        assert nrc == 0x7F

    def test_lockout_event_logged(self, security_access_stub, dem_stub):
        """CRITICAL DEM event must be emitted on lockout."""
        for _ in range(config.MAX_AUTH_RETRIES):
            security_access_stub.get_challenge(FlashRole.MANUFACTURING)
            security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
            security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        events = dem_stub.get_events_by_severity(Severity.CRITICAL)
        assert any("lock" in e.description.lower() for e in events)

    def test_lockout_cleared_after_reset(self, security_access_stub):
        """reset() must clear lockout state."""
        for _ in range(config.MAX_AUTH_RETRIES):
            security_access_stub.get_challenge(FlashRole.MANUFACTURING)
            security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
            security_access_stub.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
        security_access_stub.reset()
        assert not security_access_stub.is_locked()
