"""
VTC-01: Secure authentication before flashing
Objective: Verify flashing is allowed only after successful secure authentication.
Requirements: SR-001; SR-004; SR-010; SR-011; SR-013; SR-014
SWR-C: SWR-C-001, SWR-C-002, SWR-C-006, SWR-C-013
"""
import pytest
from sim.security_access import FlashRole
from sim.dem import Severity


@pytest.mark.vtc("VTC-01")
class TestVTC01AuthBeforeFlash:
    def test_flash_rejected_without_auth(self, dcm_stub):
        """Flash start must be rejected before any authentication."""
        dcm_stub.process_request(0x10, 0x02, b"")
        nrc, resp = dcm_stub.process_request(0x34, 0x00, b"\x08\x01\x00\x00\x00\x00\x04\x00\x00\x02")
        assert nrc == 0x7F
        assert resp[1] == 0x33  # securityAccessDenied

    def test_programming_session_required(self, dcm_stub):
        """0x34 RequestDownload must be rejected outside programming session."""
        nrc, resp = dcm_stub.process_request(0x34, 0x00, b"\x08\x01\x00\x00\x00\x00\x04\x00\x00\x02")
        assert nrc == 0x7F

    def test_challenge_issued_in_programming_session(self, dcm_stub, security_access_stub):
        """Seed request in programming session issues a non-empty challenge."""
        dcm_stub.process_request(0x10, 0x02, b"")
        challenge = security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        assert len(challenge) == 32

    def test_valid_auth_grants_access(self, dcm_stub, security_access_stub, hsm_stub):
        """Valid ECDSA response transitions ECU to authenticated state."""
        dcm_stub.process_request(0x10, 0x02, b"")
        challenge = security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
        sig = hsm_stub.sign("tester_mfg_key", challenge)
        result = security_access_stub.verify_response(FlashRole.MANUFACTURING, sig)
        assert result is True
        assert security_access_stub.is_authenticated()

    def test_flash_allowed_after_auth(self, authenticated_session, valid_firmware_image):
        """After authentication, 0x34 RequestDownload is accepted."""
        image_data, signature, version = valid_firmware_image
        # addr=0x08010000 (4B) | size=0x00000400 (4B) | version=0x0002 (2B)
        nrc, resp = authenticated_session.process_request(
            0x34, 0x00, b"\x08\x01\x00\x00\x00\x00\x04\x00\x00\x02"
        )
        assert nrc == 0x74

    def test_auth_event_logged(self, security_access_stub, hsm_stub, dem_stub):
        """Successful authentication produces an INFO DEM event."""
        challenge = security_access_stub.get_challenge(FlashRole.MANUFACTURING)
        security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
        sig = hsm_stub.sign("tester_mfg_key", challenge)
        security_access_stub.verify_response(FlashRole.MANUFACTURING, sig)
        events = dem_stub.get_events_by_severity(Severity.INFO)
        assert any("AUTH" in e.event_id or "auth" in e.description.lower() for e in events)
