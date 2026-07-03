"""
VTC-04: Valid cryptographic signature allows programming
Objective: Verify that a correctly signed image is accepted.
Requirements: SR-002; SR-013; SR-014
SWR-C: SWR-C-003, SWR-C-017
"""
import pytest
from sim.flash_manager import FlashState


@pytest.mark.vtc("VTC-04")
class TestVTC04ValidSignature:
    def test_valid_image_accepted(self, flash_manager_stub, valid_firmware_image, nvm_stub):
        """Correctly signed image must be accepted without error."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.finalize(image_data, signature)

    def test_flash_state_idle_after_commit(self, flash_manager_stub, valid_firmware_image, nvm_stub):
        """FlashManager returns to IDLE after successful commit."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.finalize(image_data, signature)
        assert flash_manager_stub.get_status()["state"] == FlashState.IDLE.value

    def test_flash_pending_cleared(self, flash_manager_stub, valid_firmware_image, nvm_stub):
        """NvM flash_pending flag must be False after successful commit."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.finalize(image_data, signature)
        assert nvm_stub.read("flash_pending") is False

    def test_success_event_logged(self, flash_manager_stub, valid_firmware_image, nvm_stub, dem_stub):
        """Successful flash must produce an INFO DEM event."""
        from sim.dem import Severity
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.finalize(image_data, signature)
        events = dem_stub.get_events_by_severity(Severity.INFO)
        assert any("flash" in e.description.lower() for e in events)
