"""
VTC-09: Rollback protection with version control
Objective: Ensure downgrade attempts are rejected.
Requirements: SR-016
SWR-C: SWR-C-019
"""
import pytest
from sim.flash_manager import FlashError
from sim.version_manager import VersionError


@pytest.mark.vtc("VTC-09")
class TestVTC09RollbackProtection:
    def test_downgrade_rejected(self, flash_manager_stub, downgrade_firmware_image, nvm_stub):
        """Image with version < NvM counter must be rejected."""
        image_data, signature, version = downgrade_firmware_image
        nvm_stub.write("sw_version_counter", 2)
        with pytest.raises(FlashError, match="downgrade"):
            flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                               image_version=version)

    def test_same_version_rejected(self, flash_manager_stub, nvm_stub, valid_firmware_image):
        """Image with version == NvM counter must also be rejected (strict >)."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version)
        with pytest.raises(FlashError, match="downgrade"):
            flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                               image_version=version)

    def test_higher_version_accepted(self, flash_manager_stub, valid_firmware_image, nvm_stub):
        """Image with version > NvM counter must be accepted."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)

    def test_version_counter_updated_after_commit(self, flash_manager_stub, valid_firmware_image,
                                                    nvm_stub):
        """NvM version counter must advance after successful flash commit."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.finalize(image_data, signature)
        assert nvm_stub.read("sw_version_counter") == version

    def test_version_manager_check_direct(self, version_manager_stub, nvm_stub):
        """VersionManager.check_version raises VersionError for downgrade."""
        nvm_stub.write("sw_version_counter", 5)
        with pytest.raises(VersionError):
            version_manager_stub.check_version(3)
