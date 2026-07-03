"""Flashing router — firmware download lifecycle endpoints."""
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.websocket import manager
from sim.flash_manager import FlashError

router = APIRouter()


class DownloadRequest(BaseModel):
    address: int = 0x08010000
    size: int = 0x100
    image_version: int = 1


class BlockRequest(BaseModel):
    seq: int
    data_hex: str


class FinalizeRequest(BaseModel):
    image_hex: str
    signature_hex: str


class SignImageRequest(BaseModel):
    image_hex: str


@router.post("/start")
async def flash_start(req: DownloadRequest, request: Request):
    """Begin firmware download sequence."""
    sim = request.app.state.sim
    if not sim["sa"].is_authenticated():
        raise HTTPException(status_code=403, detail="Not authenticated")
    try:
        role = sim["sa"].get_role().value if sim["sa"].get_role() else "manufacturing"
        sim["fm"].begin_download(req.address, req.size, role, image_version=req.image_version)
        await manager.broadcast_ecu_state(sim["ecu"].to_dict())
        return {"status": "downloading", "address": hex(req.address), "size": req.size}
    except FlashError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/block")
async def flash_block(req: BlockRequest, request: Request):
    """Upload one firmware block."""
    sim = request.app.state.sim
    try:
        data = bytes.fromhex(req.data_hex)
        sim["fm"].transfer_block(req.seq, data)
        return {"seq": req.seq, "accepted": True}
    except FlashError as exc:
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/finalize")
async def flash_finalize(req: FinalizeRequest, request: Request):
    """Trigger signature verification, programming, and commit."""
    sim = request.app.state.sim
    try:
        image = bytes.fromhex(req.image_hex)
        sig = bytes.fromhex(req.signature_hex)
        sim["fm"].finalize(image, sig)
        events = sim["dem"].get_events()
        if events:
            await manager.broadcast_dem_event(events[-1])
        await manager.broadcast_ecu_state(sim["ecu"].to_dict())
        return {"status": "committed", "flash_info": sim["fm"].get_status()}
    except FlashError as exc:
        events = sim["dem"].get_events()
        if events:
            await manager.broadcast_dem_event(events[-1])
        raise HTTPException(status_code=400, detail=str(exc))


@router.post("/sign")
async def sign_image(req: SignImageRequest, request: Request):
    """Demo helper: OEM-sign a firmware image (simulates the offline OEM signing service).

    Only the resulting signature is returned — the OEM private key never leaves the HSM.
    """
    sim = request.app.state.sim
    image = bytes.fromhex(req.image_hex)
    sig = sim["hsm"].sign("oem_signing_key", image)
    return {"signature_hex": sig.hex()}


@router.post("/abort")
async def flash_abort(request: Request):
    """Safe abort: sanitize buffers and return to IDLE."""
    sim = request.app.state.sim
    sim["fm"].abort()
    events = sim["dem"].get_events()
    if events:
        await manager.broadcast_dem_event(events[-1])
    return {"status": "aborted"}
