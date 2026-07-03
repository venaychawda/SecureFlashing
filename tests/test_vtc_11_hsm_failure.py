"""
VTC-11: HSM failure handling during flash
Objective: Ensure flashing aborts if HSM is unavailable or fails.
Requirements: SR-009; SR-012; SR-015
SWR-C: SWR-C-012, SWR-C-015
"""
import pytest
from sim.flash_manager import FlashError
from sim.hsm import HSMError
from sim.dem import Severity


@pytest.mark.vtc("VTC-11")
class TestVTC11HSMFailure:
    def test_hsm_failure_aborts_auth(self, hsm_stub, security_access_stub):
        """HSM failure during auth challenge must raise an error."""
        hsm_stub.simulate_failure(True)
        with pytest.raises((HSMError, Exception)):
            security_access_stub.get_challenge("manufacturing")
        hsm_stub.simulate_failure(False)

    def test_hsm_failure_aborts_flash_verify(self, hsm_stub, flash_manager_stub,
                                               valid_firmware_image, nvm_stub):
        """HSM failure during signature verify must abort flash operation."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        hsm_stub.simulate_failure(True)
        with pytest.raises((FlashError, HSMError, Exception)):
            flash_manager_stub.finalize(image_data, signature)
        hsm_stub.simulate_failure(False)

    def test_flash_pending_cleared_after_hsm_abort(self, hsm_stub, flash_manager_stub,
                                                     valid_firmware_image, nvm_stub):
        """flash_pending must be cleared even when HSM aborts."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        hsm_stub.simulate_failure(True)
        try:
            flash_manager_stub.finalize(image_data, signature)
        except Exception:
            pass
        hsm_stub.simulate_failure(False)
        assert nvm_stub.read("flash_pending") is False

    def test_critical_dem_event_on_hsm_failure(self, hsm_stub, flash_manager_stub,
                                                 valid_firmware_image, nvm_stub, dem_stub):
        """CRITICAL event must be logged when HSM failure aborts flashing."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        hsm_stub.simulate_failure(True)
        try:
            flash_manager_stub.finalize(image_data, signature)
        except Exception:
            pass
        hsm_stub.simulate_failure(False)
        events = dem_stub.get_events_by_severity(Severity.CRITICAL)
        assert len(events) >= 1
