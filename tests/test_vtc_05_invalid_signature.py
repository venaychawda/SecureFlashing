"""
VTC-05: Invalid signature prevents programming
Objective: Ensure corrupted or tampered images are rejected.
Requirements: SR-002; SR-011; SR-012; SR-015
SWR-C: SWR-C-003, SWR-C-014, SWR-C-015
"""
import pytest
from sim.flash_manager import FlashError, FlashState
from sim.dem import Severity


@pytest.mark.vtc("VTC-05")
class TestVTC05InvalidSignature:
    def test_tampered_image_rejected(self, flash_manager_stub, tampered_firmware_image, nvm_stub):
        """Image tampered after signing must be rejected."""
        tampered_data, signature, version = tampered_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(tampered_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, tampered_data)
        with pytest.raises(FlashError):
            flash_manager_stub.finalize(tampered_data, signature)

    def test_no_commit_on_invalid_signature(self, flash_manager_stub, tampered_firmware_image,
                                             nvm_stub, bootloader_stub):
        """No bank commit must occur when signature is invalid."""
        tampered_data, signature, version = tampered_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        initial_bank = bootloader_stub.get_active_bank()
        flash_manager_stub.begin_download(0x08010000, len(tampered_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, tampered_data)
        with pytest.raises(FlashError):
            flash_manager_stub.finalize(tampered_data, signature)
        assert bootloader_stub.get_active_bank() == initial_bank

    def test_staging_buffer_cleared_after_abort(self, flash_manager_stub, tampered_firmware_image,
                                                  nvm_stub):
        """Staging buffer must be zeroed after abort."""
        tampered_data, signature, version = tampered_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(tampered_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, tampered_data)
        with pytest.raises(FlashError):
            flash_manager_stub.finalize(tampered_data, signature)
        assert flash_manager_stub.get_status()["staging_buffer_size"] == 0

    def test_critical_event_logged_on_abort(self, flash_manager_stub, tampered_firmware_image,
                                             nvm_stub, dem_stub):
        """CRITICAL DEM event must be emitted on flash abort."""
        tampered_data, signature, version = tampered_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(tampered_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, tampered_data)
        with pytest.raises(FlashError):
            flash_manager_stub.finalize(tampered_data, signature)
        events = dem_stub.get_events_by_severity(Severity.CRITICAL)
        assert len(events) >= 1
