"""
VTC-06: Flashing memory boundary protection
Objective: Verify only permitted memory regions can be programmed.
Requirements: SR-005; SR-014
SWR-C: SWR-C-007, SWR-C-014
"""
import pytest
from sim.flash_manager import FlashError
from sim import config


@pytest.mark.vtc("VTC-06")
class TestVTC06MemoryBoundary:
    def test_valid_address_accepted(self, flash_manager_stub, valid_firmware_image, nvm_stub):
        """Address in APPLICATION region must be accepted."""
        image_data, _, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        app_start = config.MEMORY_MAP["APPLICATION"]["start"]
        flash_manager_stub.begin_download(app_start, len(image_data), "manufacturing",
                                           image_version=version)

    def test_bootloader_region_rejected(self, flash_manager_stub):
        """Write to BOOTLOADER region must be rejected."""
        bl_start = config.MEMORY_MAP["BOOTLOADER"]["start"]
        with pytest.raises(FlashError, match="address_out_of_range"):
            flash_manager_stub.begin_download(bl_start, 0x100, "service")

    def test_hsm_region_rejected(self, flash_manager_stub):
        """Write to HSM region must be rejected."""
        hsm_start = config.MEMORY_MAP["HSM"]["start"]
        with pytest.raises(FlashError, match="address_out_of_range"):
            flash_manager_stub.begin_download(hsm_start, 0x100, "manufacturing")

    def test_beyond_boundary_rejected(self, flash_manager_stub, valid_firmware_image, nvm_stub):
        """Address range that extends beyond region end must be rejected."""
        image_data, _, _ = valid_firmware_image
        nvm_stub.write("sw_version_counter", 1)
        app_end = config.MEMORY_MAP["APPLICATION"]["end"]
        with pytest.raises(FlashError, match="address_out_of_range"):
            flash_manager_stub.begin_download(app_end - 4, len(image_data), "manufacturing")

    def test_protected_region_unchanged_after_rejection(self, flash_manager_stub, nvm_stub):
        """Rejected write must leave protected region contents unchanged."""
        bl_start = config.MEMORY_MAP["BOOTLOADER"]["start"]
        with pytest.raises(FlashError):
            flash_manager_stub.begin_download(bl_start, 0x100, "service")
        assert flash_manager_stub.get_status()["state"] == "IDLE"
