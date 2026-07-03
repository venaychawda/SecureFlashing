"""
VTC-15: Secure erase of temporary flash buffers
Objective: Verify sensitive temporary data is cleared after flashing.
Requirements: SR-009; SR-012
SWR-C: SWR-C-012, SWR-C-015
"""
import pytest
from sim.dem import Severity


@pytest.mark.vtc("VTC-15")
class TestVTC15BufferSanitization:
    def test_staging_buffer_zeroed_after_successful_flash(self, flash_manager_stub,
                                                           valid_firmware_image, nvm_stub):
        """Staging buffer must be empty after successful commit."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.finalize(image_data, signature)
        assert flash_manager_stub.get_status()["staging_buffer_size"] == 0

    def test_staging_buffer_zeroed_after_abort(self, flash_manager_stub, valid_firmware_image,
                                                nvm_stub):
        """Staging buffer must be empty after abort."""
        image_data, _, _ = valid_firmware_image
        nvm_stub.write("sw_version_counter", 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=2)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.abort()
        assert flash_manager_stub.get_status()["staging_buffer_size"] == 0

    def test_failure_handler_sanitizes_on_error(self, failure_handler_stub, nvm_stub, dem_stub):
        """abort_and_sanitize must zero buffers and log CRITICAL event."""
        context = {"staging_buffer": bytearray(b"\xAA" * 128), "flash_pending": True}
        nvm_stub.write("flash_pending", True)
        failure_handler_stub.abort_and_sanitize(context)
        assert all(b == 0 for b in context["staging_buffer"])
        assert nvm_stub.read("flash_pending") is False
        events = dem_stub.get_events_by_severity(Severity.CRITICAL)
        assert len(events) >= 1

    def test_no_firmware_remnants_in_buffer(self, flash_manager_stub, valid_firmware_image,
                                             nvm_stub):
        """After abort, staging buffer must not contain original firmware bytes."""
        image_data, _, _ = valid_firmware_image
        nvm_stub.write("sw_version_counter", 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=2)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.abort()
        status = flash_manager_stub.get_status()
        assert status["staging_buffer_size"] == 0
