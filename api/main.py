"""FastAPI application entry point — Secure Flashing Classic simulation backend."""
import asyncio
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware

from api.websocket import manager
from api.routers import auth, diagnostics, flashing, test_scenarios
from sim.bootloader import Bootloader
from sim.config import DEFAULT_ACTIVE_BANK
from sim.csm import CSM
from sim.cryif import CryIf
from sim.dcm import DCM
from sim.dem import DEM
from sim.ecu_state import ECUState
from sim.failure_handler import FailureHandler
from sim.flash_manager import FlashManager
from sim.hsm import HSM
from sim.nvm import NvM
from sim.pki_manager import PKIManager
from sim.recovery_manager import RecoveryManager
from sim.security_access import SecurityAccess, FlashRole
from sim.session_manager import SessionManager
from sim.version_manager import VersionManager


def build_simulation() -> dict:
    """Instantiate and wire all simulation modules."""
    hsm = HSM()
    for key_id in ("oem_signing_key", "tester_mfg_key", "tester_svc_key",
                    "tester_eng_key", "tester_dev_key"):
        hsm.generate_key_pair(key_id)

    nvm = NvM()
    dem = DEM()
    cryif = CryIf(hsm=hsm)
    csm = CSM(cryif=cryif)
    pki = PKIManager(csm=csm, hsm=hsm, dem=dem)
    vm = VersionManager(nvm=nvm)
    sa = SecurityAccess(csm=csm, nvm=nvm, dem=dem, pki_manager=pki, hsm=hsm)
    sm = SessionManager(nvm=nvm, dem=dem)
    fh = FailureHandler(nvm=nvm, dem=dem)
    fm = FlashManager(csm=csm, nvm=nvm, dem=dem, failure_handler=fh, version_manager=vm)
    bl = Bootloader(csm=csm, nvm=nvm, dem=dem)
    rm = RecoveryManager(nvm=nvm, dem=dem)
    ecu = ECUState()
    dcm = DCM(security_access=sa, session_manager=sm, flash_manager=fm,
              bootloader=bl, recovery_manager=rm, dem=dem, ecu_state=ecu)
    return {
        "hsm": hsm, "nvm": nvm, "dem": dem, "csm": csm, "pki": pki,
        "sa": sa, "sm": sm, "fm": fm, "bl": bl, "rm": rm, "ecu": ecu, "dcm": dcm,
    }


sim = build_simulation()


@asynccontextmanager
async def lifespan(app: FastAPI):
    app.state.sim = sim
    yield


app = FastAPI(title="Secure Flashing Classic", version="1.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth.router, prefix="/auth", tags=["auth"])
app.include_router(flashing.router, prefix="/flash", tags=["flash"])
app.include_router(diagnostics.router, prefix="/ecu", tags=["ecu"])
app.include_router(test_scenarios.router, prefix="/test", tags=["test"])


@app.websocket("/ws/events")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    await manager.broadcast_ecu_state(sim["ecu"].to_dict())
    try:
        while True:
            await asyncio.sleep(1)
            if not websocket.client_state.value == 3:
                await manager.broadcast_ecu_state(sim["ecu"].to_dict())
    except (WebSocketDisconnect, Exception):
        manager.disconnect(websocket)
