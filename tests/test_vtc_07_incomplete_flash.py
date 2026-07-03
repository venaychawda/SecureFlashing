"""
VTC-07: Incomplete flash shall not activate
Objective: Ensure partial images are never activated.
Requirements: SR-005; SR-006; SR-007; SR-014
SWR-C: SWR-C-008, SWR-C-009
"""
import pytest


@pytest.mark.vtc("VTC-07")
class TestVTC07IncompleteFlash:
    def test_flash_pending_set_during_download(self, flash_manager_stub, valid_firmware_image,
                                               nvm_stub):
        """flash_pending NvM flag must be True during active download."""
        image_data, _, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        assert nvm_stub.read("flash_pending") is True

    def test_partial_transfer_not_committed(self, flash_manager_stub, valid_firmware_image,
                                             nvm_stub, bootloader_stub):
        """Aborting mid-transfer must not change active bank."""
        image_data, _, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        initial_bank = bootloader_stub.get_active_bank()
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data[:64])
        flash_manager_stub.abort()
        assert bootloader_stub.get_active_bank() == initial_bank

    def test_boot_after_incomplete_flash_uses_previous_firmware(
            self, flash_manager_stub, valid_firmware_image, nvm_stub, bootloader_stub, hsm_stub):
        """After power-restored with flash_pending=True, boot must use last valid bank."""
        image_data, _, version = valid_firmware_image
        # Set up a valid bank A so boot succeeds
        sig = hsm_stub.sign("oem_signing_key", image_data)
        nvm_stub.write("bank_A", {"image": image_data.hex(), "signature": sig.hex(), "valid": True})
        nvm_stub.write("last_valid_bank", "A")
        nvm_stub.write("flash_pending", True)
        result = bootloader_stub.trigger_reset()
        assert result is True
        assert bootloader_stub.get_active_bank() == "A"

    def test_flash_pending_cleared_after_abort(self, flash_manager_stub, valid_firmware_image,
                                                nvm_stub):
        """flash_pending must be False after abort."""
        image_data, _, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.abort()
        assert nvm_stub.read("flash_pending") is False
