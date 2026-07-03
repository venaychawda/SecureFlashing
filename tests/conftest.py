"""Shared pytest fixtures for all 16 VTC test files."""
import os
import tempfile
import pytest
from sim.ecu_state import ECUState
from sim.nvm import NvM
from sim.dem import DEM
from sim.hsm import HSM
from sim.cryif import CryIf
from sim.csm import CSM
from sim.pki_manager import PKIManager
from sim.version_manager import VersionManager
from sim.security_access import SecurityAccess, FlashRole
from sim.session_manager import SessionManager
from sim.flash_manager import FlashManager
from sim.bootloader import Bootloader
from sim.recovery_manager import RecoveryManager
from sim.failure_handler import FailureHandler
from sim.dcm import DCM


@pytest.fixture
def tmp_nvm_path(tmp_path):
    return str(tmp_path / "nvm_store.json")


@pytest.fixture
def nvm_stub(tmp_nvm_path):
    return NvM(path=tmp_nvm_path)


@pytest.fixture
def dem_stub():
    return DEM()


@pytest.fixture
def hsm_stub():
    hsm = HSM()
    hsm.generate_key_pair("oem_signing_key")
    hsm.generate_key_pair("tester_mfg_key")
    hsm.generate_key_pair("tester_svc_key")
    hsm.generate_key_pair("tester_eng_key")
    hsm.generate_key_pair("tester_dev_key")
    return hsm


@pytest.fixture
def cryif_stub(hsm_stub):
    return CryIf(hsm=hsm_stub)


@pytest.fixture
def csm_stub(cryif_stub):
    return CSM(cryif=cryif_stub)


@pytest.fixture
def pki_manager_stub(hsm_stub, csm_stub, dem_stub):
    return PKIManager(csm=csm_stub, hsm=hsm_stub, dem=dem_stub)


@pytest.fixture
def version_manager_stub(nvm_stub):
    return VersionManager(nvm=nvm_stub)


@pytest.fixture
def security_access_stub(csm_stub, nvm_stub, dem_stub, pki_manager_stub, hsm_stub):
    return SecurityAccess(
        csm=csm_stub,
        nvm=nvm_stub,
        dem=dem_stub,
        pki_manager=pki_manager_stub,
        hsm=hsm_stub,
    )


@pytest.fixture
def session_manager_stub(nvm_stub, dem_stub):
    return SessionManager(nvm=nvm_stub, dem=dem_stub)


@pytest.fixture
def failure_handler_stub(nvm_stub, dem_stub):
    return FailureHandler(nvm=nvm_stub, dem=dem_stub)


@pytest.fixture
def flash_manager_stub(csm_stub, nvm_stub, dem_stub, failure_handler_stub, version_manager_stub):
    return FlashManager(
        csm=csm_stub,
        nvm=nvm_stub,
        dem=dem_stub,
        failure_handler=failure_handler_stub,
        version_manager=version_manager_stub,
    )


@pytest.fixture
def bootloader_stub(csm_stub, nvm_stub, dem_stub):
    return Bootloader(csm=csm_stub, nvm=nvm_stub, dem=dem_stub)


@pytest.fixture
def recovery_manager_stub(nvm_stub, dem_stub):
    return RecoveryManager(nvm=nvm_stub, dem=dem_stub)


@pytest.fixture
def ecu_state():
    return ECUState()


@pytest.fixture
def dcm_stub(security_access_stub, session_manager_stub, flash_manager_stub,
             bootloader_stub, recovery_manager_stub, dem_stub, ecu_state):
    return DCM(
        security_access=security_access_stub,
        session_manager=session_manager_stub,
        flash_manager=flash_manager_stub,
        bootloader=bootloader_stub,
        recovery_manager=recovery_manager_stub,
        dem=dem_stub,
        ecu_state=ecu_state,
    )


@pytest.fixture
def valid_firmware_image(hsm_stub):
    """Returns (image_data, signature) signed with oem_signing_key, version=2."""
    image_data = b"VALID_FW_IMAGE_v2_" + b"\xAB" * 256
    signature = hsm_stub.sign("oem_signing_key", image_data)
    return image_data, signature, 2


@pytest.fixture
def tampered_firmware_image(hsm_stub):
    """Returns (image_data, signature) where image was modified after signing."""
    original = b"VALID_FW_IMAGE_v2_" + b"\xAB" * 256
    signature = hsm_stub.sign("oem_signing_key", original)
    tampered = original[:-4] + b"\xDE\xAD\xBE\xEF"
    return tampered, signature, 2


@pytest.fixture
def downgrade_firmware_image(hsm_stub):
    """Returns (image_data, signature) with version=1 (below current nvm counter=2)."""
    image_data = b"OLD_FW_IMAGE_v1_" + b"\xAB" * 256
    signature = hsm_stub.sign("oem_signing_key", image_data)
    return image_data, signature, 1


@pytest.fixture
def authenticated_session(dcm_stub, security_access_stub, hsm_stub):
    """Returns a DCM with an active MANUFACTURING authenticated session."""
    dcm_stub.process_request(0x10, 0x02, b"")
    challenge = security_access_stub.get_challenge(FlashRole.MANUFACTURING)
    signature = hsm_stub.sign("tester_mfg_key", challenge)
    security_access_stub._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
    security_access_stub.verify_response(FlashRole.MANUFACTURING, signature)
    return dcm_stub
