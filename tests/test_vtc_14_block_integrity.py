"""
VTC-14: Data integrity verification before flash commit
Objective: Ensure every flash block is validated before commit.
Requirements: SR-002; SR-005
SWR-C: SWR-C-004, SWR-C-008
"""
import pytest
from sim.flash_manager import FlashError


@pytest.mark.vtc("VTC-14")
class TestVTC14BlockIntegrity:
    def test_corrupted_block_detected(self, flash_manager_stub, valid_firmware_image, nvm_stub):
        """Corrupted block must be detected by hash verification before commit."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        corrupted = bytearray(image_data)
        corrupted[10] ^= 0xFF
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, bytes(corrupted))
        with pytest.raises(FlashError):
            flash_manager_stub.finalize(image_data, signature)

    def test_valid_multi_block_accepted(self, flash_manager_stub, hsm_stub, nvm_stub):
        """Multi-block image with valid signature must be accepted."""
        block1 = b"BLOCK1_DATA" + b"\x11" * 64
        block2 = b"BLOCK2_DATA" + b"\x22" * 64
        image_data = block1 + block2
        signature = hsm_stub.sign("oem_signing_key", image_data)
        nvm_stub.write("sw_version_counter", 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=2)
        flash_manager_stub.transfer_block(1, block1)
        flash_manager_stub.transfer_block(2, block2)
        flash_manager_stub.finalize(image_data, signature)

    def test_no_commit_on_integrity_failure(self, flash_manager_stub, valid_firmware_image,
                                              nvm_stub, bootloader_stub):
        """No bank commit must occur on integrity failure."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        initial_bank = bootloader_stub.get_active_bank()
        corrupted = bytearray(image_data)
        corrupted[5] ^= 0xAA
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, bytes(corrupted))
        with pytest.raises(FlashError):
            flash_manager_stub.finalize(image_data, signature)
        assert bootloader_stub.get_active_bank() == initial_bank
