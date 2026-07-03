"""
VTC-10: Secure boot validation after flashing
Objective: Confirm secure boot validates the new image after programming.
Requirements: SR-007; SR-013; SR-014
SWR-C: SWR-C-010
"""
import pytest
from sim.dem import Severity


@pytest.mark.vtc("VTC-10")
class TestVTC10SecureBoot:
    def test_boot_succeeds_with_valid_image(self, bootloader_stub, nvm_stub, hsm_stub):
        """Boot must succeed when bank has a valid OEM-signed image."""
        image_data = b"VALID_APP_v2" + b"\xAA" * 256
        sig = hsm_stub.sign("oem_signing_key", image_data)
        nvm_stub.write("active_bank", "A")
        nvm_stub.write("flash_pending", False)
        nvm_stub.write("bank_A", {"image": image_data.hex(), "signature": sig.hex(), "valid": True})
        result = bootloader_stub.boot()
        assert result is True

    def test_boot_fails_with_unsigned_image(self, bootloader_stub, nvm_stub):
        """Boot must fail when active bank has no valid signature."""
        bad_sig = b"\xFF" * 64
        image_data = b"MALICIOUS_APP" + b"\xBB" * 256
        nvm_stub.write("active_bank", "A")
        nvm_stub.write("flash_pending", False)
        nvm_stub.write("bank_A", {"image": image_data.hex(), "signature": bad_sig.hex(), "valid": False})
        result = bootloader_stub.boot()
        assert result is False

    def test_secure_boot_ok_event_logged(self, bootloader_stub, nvm_stub, hsm_stub, dem_stub):
        """Successful secure boot must produce an INFO DEM event."""
        image_data = b"VALID_APP_v2" + b"\xAA" * 256
        sig = hsm_stub.sign("oem_signing_key", image_data)
        nvm_stub.write("active_bank", "A")
        nvm_stub.write("flash_pending", False)
        nvm_stub.write("bank_A", {"image": image_data.hex(), "signature": sig.hex(), "valid": True})
        bootloader_stub.boot()
        events = dem_stub.get_events_by_severity(Severity.INFO)
        assert any("boot" in e.description.lower() for e in events)

    def test_secure_boot_fail_event_logged(self, bootloader_stub, nvm_stub, dem_stub):
        """Failed secure boot must produce a CRITICAL DEM event."""
        image_data = b"BAD_APP" + b"\xCC" * 64
        nvm_stub.write("active_bank", "A")
        nvm_stub.write("flash_pending", False)
        nvm_stub.write("bank_A", {"image": image_data.hex(), "signature": (b"\xDE" * 64).hex(), "valid": False})
        bootloader_stub.boot()
        events = dem_stub.get_events_by_severity(Severity.CRITICAL)
        assert any("boot" in e.description.lower() for e in events)

    def test_full_flash_then_reboot(self, flash_manager_stub, bootloader_stub, valid_firmware_image,
                                     nvm_stub):
        """End-to-end: flash valid image then trigger_reset must succeed."""
        image_data, signature, version = valid_firmware_image
        nvm_stub.write("sw_version_counter", version - 1)
        flash_manager_stub.begin_download(0x08010000, len(image_data), "manufacturing",
                                           image_version=version)
        flash_manager_stub.transfer_block(1, image_data)
        flash_manager_stub.finalize(image_data, signature)
        result = bootloader_stub.trigger_reset()
        assert result is True
