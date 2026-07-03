"""
VTC-08: Power loss during flash programming
Objective: Verify recovery from power interruption during erase/write.
Requirements: SR-006; SR-012; SR-015
SWR-C: SWR-C-009, SWR-C-015
"""
import pytest
from sim.dem import Severity


@pytest.mark.vtc("VTC-08")
class TestVTC08PowerLossRecovery:
    def test_recovery_triggered_when_flash_pending(self, recovery_manager_stub, nvm_stub):
        """RecoveryManager must detect flash_pending and activate fallback."""
        nvm_stub.write("flash_pending", True)
        nvm_stub.write("last_valid_bank", "A")
        nvm_stub.write("active_bank", "B")
        recovery_manager_stub.recover()
        assert nvm_stub.read("active_bank") == "A"

    def test_flash_pending_cleared_after_recovery(self, recovery_manager_stub, nvm_stub):
        """flash_pending must be False after recovery."""
        nvm_stub.write("flash_pending", True)
        nvm_stub.write("last_valid_bank", "A")
        recovery_manager_stub.recover()
        assert nvm_stub.read("flash_pending") is False

    def test_recovery_event_logged(self, recovery_manager_stub, nvm_stub, dem_stub):
        """Recovery must produce a WARNING DEM event."""
        nvm_stub.write("flash_pending", True)
        nvm_stub.write("last_valid_bank", "A")
        recovery_manager_stub.recover()
        events = dem_stub.get_events_by_severity(Severity.WARNING)
        assert any("recov" in e.description.lower() for e in events)

    def test_no_recovery_when_not_pending(self, recovery_manager_stub, nvm_stub, dem_stub):
        """RecoveryManager must not touch bank if flash_pending is False."""
        nvm_stub.write("flash_pending", False)
        nvm_stub.write("active_bank", "B")
        recovery_manager_stub.recover()
        assert nvm_stub.read("active_bank") == "B"

    def test_boot_succeeds_after_recovery(self, bootloader_stub, nvm_stub, hsm_stub):
        """Boot must succeed using recovered last valid bank with a valid signature."""
        image_data = b"RECOVERY_FW" + b"\xBB" * 64
        sig = hsm_stub.sign("oem_signing_key", image_data)
        nvm_stub.write("bank_A", {"image": image_data.hex(), "signature": sig.hex(), "valid": True})
        nvm_stub.write("flash_pending", True)
        nvm_stub.write("last_valid_bank", "A")
        result = bootloader_stub.trigger_reset()
        assert result is True
