"""
VTC-03: Anti-replay protection during flashing
Objective: Ensure replayed secure messages do not authorize flashing.
Requirements: SR-003; SR-010; SR-011; SR-015
SWR-C: SWR-C-005, SWR-C-013
"""
import pytest
from sim.session_manager import SessionError


@pytest.mark.vtc("VTC-03")
class TestVTC03ReplayProtection:
    def test_replay_same_counter_rejected(self, session_manager_stub, nvm_stub):
        """Re-using same transaction counter must be rejected."""
        session_manager_stub.create_session()
        tx = nvm_stub.get_counter("tx_counter")
        with pytest.raises(SessionError, match="replay"):
            session_manager_stub.validate_freshness(tx)

    def test_old_counter_rejected(self, session_manager_stub, nvm_stub):
        """Counter value below stored value must be rejected."""
        session_manager_stub.create_session()
        nvm_stub.increment_counter("tx_counter")
        old_tx = nvm_stub.get_counter("tx_counter") - 2
        with pytest.raises(SessionError, match="replay"):
            session_manager_stub.validate_freshness(old_tx)

    def test_new_counter_accepted(self, session_manager_stub, nvm_stub):
        """Counter strictly greater than stored must be accepted."""
        session_manager_stub.create_session()
        current = nvm_stub.get_counter("tx_counter")
        session_manager_stub.validate_freshness(current + 1)

    def test_second_replay_of_same_msg_rejected(self, session_manager_stub, nvm_stub):
        """Replaying a previously accepted counter must be rejected."""
        session_manager_stub.create_session()
        current = nvm_stub.get_counter("tx_counter")
        session_manager_stub.validate_freshness(current + 1)
        with pytest.raises(SessionError, match="replay"):
            session_manager_stub.validate_freshness(current + 1)
