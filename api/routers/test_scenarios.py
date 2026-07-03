"""Test scenarios router — execute VTC scenarios via REST (SWR-C-018)."""
import traceback
from fastapi import APIRouter, HTTPException, Request

from api.websocket import manager
from sim.security_access import FlashRole

router = APIRouter()

_results: dict[str, dict] = {}


async def _run_vtc(vtc_id: str, sim: dict) -> dict:
    """Execute a named VTC scenario end-to-end and return pass/fail + evidence."""
    hsm = sim["hsm"]
    sa = sim["sa"]
    fm = sim["fm"]
    dem = sim["dem"]
    nvm = sim["nvm"]
    bl = sim["bl"]
    sm = sim["sm"]
    rm = sim["rm"]

    dem.clear()
    sa.reset()
    sm.destroy()
    nvm.write("sw_version_counter", 1)
    nvm.write("flash_pending", False)
    nvm.write("active_bank", "A")
    nvm.write("last_valid_bank", "A")

    image_data = b"TEST_FW_v2_" + b"\xAB" * 128
    valid_sig = hsm.sign("oem_signing_key", image_data)

    try:
        if vtc_id == "VTC-01":
            sm.create_session()
            challenge = sa.get_challenge(FlashRole.MANUFACTURING)
            sa._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
            sig = hsm.sign("tester_mfg_key", challenge)
            ok = sa.verify_response(FlashRole.MANUFACTURING, sig)
            assert ok, "Auth failed"
            fm.begin_download(0x08010000, len(image_data), "manufacturing", image_version=2)
            fm.transfer_block(1, image_data)
            fm.finalize(image_data, valid_sig)
            return {"passed": True, "evidence": "Auth succeeded; flash committed"}

        elif vtc_id == "VTC-02":
            sa.get_challenge(FlashRole.MANUFACTURING)
            sa._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
            result = sa.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
            assert not result, "Should have failed"
            assert not sa.is_authenticated()
            return {"passed": True, "evidence": "Invalid sig rejected; ECU locked"}

        elif vtc_id == "VTC-03":
            sm.create_session()
            from sim.session_manager import SessionError
            tx = nvm.get_counter("tx_counter")
            try:
                sm.validate_freshness(tx)
                return {"passed": False, "evidence": "Replay was not detected"}
            except SessionError:
                return {"passed": True, "evidence": "Replay counter correctly rejected"}

        elif vtc_id == "VTC-04":
            nvm.write("sw_version_counter", 1)
            fm.begin_download(0x08010000, len(image_data), "manufacturing", image_version=2)
            fm.transfer_block(1, image_data)
            fm.finalize(image_data, valid_sig)
            return {"passed": True, "evidence": "Valid signature accepted; flash committed"}

        elif vtc_id == "VTC-05":
            from sim.flash_manager import FlashError
            tampered = bytearray(image_data); tampered[0] ^= 0xFF
            nvm.write("sw_version_counter", 1)
            fm.begin_download(0x08010000, len(image_data), "manufacturing", image_version=2)
            fm.transfer_block(1, bytes(tampered))
            try:
                fm.finalize(bytes(tampered), valid_sig)
                return {"passed": False, "evidence": "Tampered image not rejected"}
            except FlashError:
                return {"passed": True, "evidence": "Tampered image rejected; abort logged"}

        elif vtc_id == "VTC-06":
            from sim.flash_manager import FlashError
            from sim import config
            try:
                fm.begin_download(config.MEMORY_MAP["BOOTLOADER"]["start"], 0x100, "service")
                return {"passed": False, "evidence": "Bootloader region not protected"}
            except FlashError:
                return {"passed": True, "evidence": "Bootloader region correctly rejected"}

        elif vtc_id == "VTC-07":
            nvm.write("sw_version_counter", 1)
            fm.begin_download(0x08010000, len(image_data), "manufacturing", image_version=2)
            assert nvm.read("flash_pending") is True
            fm.abort()
            assert nvm.read("flash_pending") is False
            return {"passed": True, "evidence": "Incomplete flash aborted; pending cleared"}

        elif vtc_id == "VTC-08":
            nvm.write("flash_pending", True)
            nvm.write("last_valid_bank", "A")
            nvm.write("active_bank", "B")
            rm.recover()
            assert nvm.read("active_bank") == "A"
            return {"passed": True, "evidence": "Recovery restored last valid bank A"}

        elif vtc_id == "VTC-09":
            from sim.flash_manager import FlashError
            nvm.write("sw_version_counter", 3)
            try:
                fm.begin_download(0x08010000, 64, "manufacturing", image_version=2)
                return {"passed": False, "evidence": "Downgrade not rejected"}
            except FlashError:
                return {"passed": True, "evidence": "Downgrade v2 < stored=3 rejected"}

        elif vtc_id == "VTC-10":
            nvm.write("bank_A", {"image": image_data.hex(), "signature": valid_sig.hex(), "valid": True})
            nvm.write("active_bank", "A")
            nvm.write("flash_pending", False)
            ok = bl.boot()
            assert ok
            return {"passed": True, "evidence": "Secure boot passed with valid OEM signature"}

        elif vtc_id == "VTC-11":
            from sim.flash_manager import FlashError
            nvm.write("sw_version_counter", 1)
            fm.begin_download(0x08010000, len(image_data), "manufacturing", image_version=2)
            fm.transfer_block(1, image_data)
            hsm.simulate_failure(True)
            try:
                fm.finalize(image_data, valid_sig)
                hsm.simulate_failure(False)
                return {"passed": False, "evidence": "HSM failure not handled"}
            except Exception:
                hsm.simulate_failure(False)
                assert nvm.read("flash_pending") is False
                return {"passed": True, "evidence": "HSM failure aborted flash safely"}

        elif vtc_id == "VTC-12":
            import time
            sm.create_session()
            assert sm.is_active()
            sm._last_activity = time.monotonic() - 9999
            assert not sm.is_active()
            return {"passed": True, "evidence": "Session timed out correctly"}

        elif vtc_id == "VTC-13":
            from sim import config as cfg
            for _ in range(cfg.MAX_AUTH_RETRIES):
                sa.get_challenge(FlashRole.MANUFACTURING)
                sa._register_role_key(FlashRole.MANUFACTURING, "tester_mfg_key")
                sa.verify_response(FlashRole.MANUFACTURING, b"\xFF" * 64)
            assert sa.is_locked()
            return {"passed": True, "evidence": f"Lockout after {cfg.MAX_AUTH_RETRIES} failures"}

        elif vtc_id == "VTC-14":
            from sim.flash_manager import FlashError
            nvm.write("sw_version_counter", 1)
            corrupted = bytearray(image_data); corrupted[5] ^= 0xAA
            fm.begin_download(0x08010000, len(image_data), "manufacturing", image_version=2)
            fm.transfer_block(1, bytes(corrupted))
            try:
                fm.finalize(image_data, valid_sig)
                return {"passed": False, "evidence": "Corrupted block not detected"}
            except FlashError:
                return {"passed": True, "evidence": "Block integrity failure detected before commit"}

        elif vtc_id == "VTC-15":
            nvm.write("sw_version_counter", 1)
            fm.begin_download(0x08010000, len(image_data), "manufacturing", image_version=2)
            fm.transfer_block(1, image_data)
            fm.abort()
            assert fm.get_status()["staging_buffer_size"] == 0
            return {"passed": True, "evidence": "Staging buffer sanitized after abort"}

        elif vtc_id == "VTC-16":
            from sim.pki_manager import PKIError
            pki = sim["pki"]
            valid_chain = pki.build_test_chain(valid=True)
            assert pki.validate_chain(valid_chain)
            exp_chain = pki.build_test_chain(expired=True)
            try:
                pki.validate_chain(exp_chain)
                return {"passed": False, "evidence": "Expired cert not rejected"}
            except PKIError:
                return {"passed": True, "evidence": "PKI chain validated; expired cert rejected"}

        else:
            return {"passed": False, "evidence": f"Unknown VTC: {vtc_id}"}

    except AssertionError as exc:
        return {"passed": False, "evidence": f"Assertion failed: {exc}"}
    except Exception as exc:
        return {"passed": False, "evidence": f"Exception: {exc}\n{traceback.format_exc()}"}


@router.post("/{vtc_id}/run")
async def run_vtc(vtc_id: str, request: Request):
    """Execute a named VTC scenario end-to-end."""
    sim = request.app.state.sim
    result = await _run_vtc(vtc_id.upper(), sim)
    result["vtc_id"] = vtc_id.upper()
    _results[vtc_id.upper()] = result
    await manager.broadcast({"type": "vtc_result", **result})
    return result


@router.get("/{vtc_id}/result")
async def get_vtc_result(vtc_id: str):
    """Return the last result for a VTC scenario."""
    key = vtc_id.upper()
    if key not in _results:
        raise HTTPException(status_code=404, detail=f"No result for {key}")
    return _results[key]


@router.get("/all/results")
async def get_all_results():
    """Return all stored VTC results."""
    return _results
