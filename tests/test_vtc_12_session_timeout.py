"""
VTC-12: Secure session timeout during flashing
Objective: Verify idle session timeout relocks access.
Requirements: SR-003; SR-011
SWR-C: SWR-C-005
"""
import pytest
from sim.session_manager import SessionError


@pytest.mark.vtc("VTC-12")
class TestVTC12SessionTimeout:
    def test_active_session_valid(self, session_manager_stub):
        """Freshly created session must be active."""
        session_manager_stub.create_session()
        assert session_manager_stub.is_active()

    def test_session_expires_after_timeout(self, session_manager_stub, monkeypatch):
        """Session must expire after inactivity timeout."""
        import time
        session_manager_stub.create_session()
        future = time.monotonic() + 9999
        monkeypatch.setattr(time, "monotonic", lambda: future)
        assert not session_manager_stub.is_active()

    def test_flash_rejected_after_timeout(self, session_manager_stub, monkeypatch):
        """Session validation must raise after timeout."""
        import time
        session_manager_stub.create_session()
        future = time.monotonic() + 9999
        monkeypatch.setattr(time, "monotonic", lambda: future)
        with pytest.raises(SessionError, match="timeout"):
            session_manager_stub.validate_active()

    def test_reauthentication_restores_session(self, session_manager_stub, monkeypatch):
        """New create_session() after timeout must create a valid session."""
        import time
        session_manager_stub.create_session()
        future = time.monotonic() + 9999
        monkeypatch.setattr(time, "monotonic", lambda: future)
        monkeypatch.undo()
        session_manager_stub.create_session()
        assert session_manager_stub.is_active()
