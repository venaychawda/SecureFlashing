"""Auth router — challenge/response endpoints."""
import os

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from api.websocket import manager
from sim import config
from sim.security_access import AuthError, FlashRole

router = APIRouter()


class ChallengeRequest(BaseModel):
    role: str = "manufacturing"


class ResponseRequest(BaseModel):
    role: str
    signature_hex: str


class SignRequest(BaseModel):
    role: str
    challenge_hex: str
    cred_type: str = "valid"  # valid | invalid | wrong_role


@router.post("/challenge")
async def get_challenge(req: ChallengeRequest, request: Request):
    """Issue a fresh ECDSA challenge nonce for the requested role."""
    sim = request.app.state.sim
    try:
        role = FlashRole(req.role)
        challenge = sim["sa"].get_challenge(role)
        await manager.broadcast_dem_event(sim["dem"].get_events()[-1] if sim["dem"].get_events() else type("E", (), {"event_id": "CHALLENGE", "severity": type("S", (), {"value": "INFO"})(), "description": "challenge issued", "swr_ref": "", "timestamp": 0, "data": {}})())
        return {"challenge_hex": challenge.hex(), "role": req.role}
    except AuthError as exc:
        raise HTTPException(status_code=403, detail=str(exc))


@router.post("/response")
async def verify_response(req: ResponseRequest, request: Request):
    """Submit signed challenge response; returns authenticated=true on success."""
    sim = request.app.state.sim
    try:
        role = FlashRole(req.role)
        sig = bytes.fromhex(req.signature_hex)
        ok = sim["sa"].verify_response(role, sig)
        events = sim["dem"].get_events()
        if events:
            await manager.broadcast_dem_event(events[-1])
        await manager.broadcast_ecu_state(sim["ecu"].to_dict())
        return {"authenticated": ok, "role": req.role if ok else None}
    except AuthError as exc:
        raise HTTPException(status_code=403, detail=str(exc))
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=f"Invalid hex: {exc}")


@router.post("/sign")
async def sign_challenge(req: SignRequest, request: Request):
    """Demo helper: produce a tester signature for the dashboard's credential picker.

    Key bytes never leave the HSM — only a DER signature is returned, mirroring
    how an external tester device would hold its own key and sign locally.
    """
    sim = request.app.state.sim
    hsm = sim["hsm"]
    challenge = bytes.fromhex(req.challenge_hex)

    if req.cred_type == "invalid":
        return {"signature_hex": os.urandom(64).hex()}

    if req.cred_type == "wrong_role":
        other_role = next(r for r in config.ROLE_KEY_MAP if r != req.role)
        sig = hsm.sign(config.ROLE_KEY_MAP[other_role], challenge)
        return {"signature_hex": sig.hex()}

    key_id = config.ROLE_KEY_MAP.get(req.role)
    if key_id is None:
        raise HTTPException(status_code=400, detail=f"Unknown role: {req.role}")
    sig = hsm.sign(key_id, challenge)
    return {"signature_hex": sig.hex()}
