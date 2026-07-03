"""Diagnostics router — ECU state, events, and reset endpoints."""
from fastapi import APIRouter, Request

from api.websocket import manager
from sim import config

router = APIRouter()


@router.get("/state")
async def get_ecu_state(request: Request):
    """Return current ECU state JSON."""
    sim = request.app.state.sim
    info = sim["dcm"].get_session_info()
    info["retry_count"] = sim["nvm"].get_counter(config.AUTH_RETRY_KEY)
    info["sw_version"] = sim["nvm"].read(config.SW_VERSION_KEY, 1)
    return info


@router.get("/events")
async def get_dem_events(request: Request):
    """Return all DEM events."""
    sim = request.app.state.sim
    events = sim["dem"].get_events()
    return [
        {
            "event_id": e.event_id,
            "severity": e.severity.value,
            "description": e.description,
            "swr_ref": e.swr_ref,
            "timestamp": e.timestamp,
            "data": e.data,
        }
        for e in events
    ]


@router.get("/reset")
async def ecu_reset(request: Request):
    """Simulate a power-on reset: trigger bootloader and clear session."""
    sim = request.app.state.sim
    ok = sim["bl"].trigger_reset()
    sim["dcm"].reset()
    events = sim["dem"].get_events()
    if events:
        await manager.broadcast_dem_event(events[-1])
    await manager.broadcast_ecu_state(sim["ecu"].to_dict())
    return {"boot_success": ok, "active_bank": sim["bl"].get_active_bank()}
