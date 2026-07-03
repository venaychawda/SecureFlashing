"""DCM — UDS service dispatcher (SWR-C-001/005/006/013)."""
import struct

from sim.bootloader import Bootloader
from sim.dem import DEM, Severity
from sim.ecu_state import ECUMode, ECUState
from sim.flash_manager import FlashError, FlashManager
from sim.recovery_manager import RecoveryManager
from sim.security_access import AuthError, FlashRole, SecurityAccess
from sim.session_manager import SessionError, SessionManager


class DCM:
    """Dispatches UDS service requests to the appropriate simulation module.

    Supported services:
        0x10 DiagnosticSessionControl
        0x27 SecurityAccess
        0x34 RequestDownload
        0x36 TransferData
        0x37 RequestTransferExit
        0x11 ECUReset
    """

    _SVC_SESSION_CTRL = 0x10
    _SVC_SECURITY_ACCESS = 0x27
    _SVC_REQUEST_DOWNLOAD = 0x34
    _SVC_TRANSFER_DATA = 0x36
    _SVC_TRANSFER_EXIT = 0x37
    _SVC_ECU_RESET = 0x11

    _NRC_SNS = 0x11
    _NRC_IMLOIF = 0x13
    _NRC_RSE = 0x24
    _NRC_SAD = 0x33
    _NRC_IK = 0x35
    _NRC_ENOA = 0x36
    _NRC_GPF = 0x72
    _NRC_SFNS = 0x7E

    def __init__(self, security_access: SecurityAccess, session_manager: SessionManager,
                 flash_manager: FlashManager, bootloader: Bootloader,
                 recovery_manager: RecoveryManager, dem: DEM, ecu_state: ECUState) -> None:
        self._sa = security_access
        self._sm = session_manager
        self._fm = flash_manager
        self._bl = bootloader
        self._rm = recovery_manager
        self._dem = dem
        self._ecu = ecu_state
        self._pending_download: dict | None = None

    def process_request(self, service_id: int, sub_func: int, data: bytes) -> tuple[int, bytes]:
        """Process a UDS service request.

        Args:
            service_id: UDS service identifier byte.
            sub_func: Sub-function byte.
            data: Remaining request payload.

        Returns:
            (response_code, response_payload) where response_code is the positive
            response SID or 0x7F on negative response.
        """
        if service_id == self._SVC_SESSION_CTRL:
            return self._handle_session(sub_func)
        if service_id == self._SVC_SECURITY_ACCESS:
            return self._handle_security_access(sub_func, data)
        if service_id == self._SVC_REQUEST_DOWNLOAD:
            return self._handle_request_download(data)
        if service_id == self._SVC_TRANSFER_DATA:
            return self._handle_transfer_data(sub_func, data)
        if service_id == self._SVC_TRANSFER_EXIT:
            return self._handle_transfer_exit(data)
        if service_id == self._SVC_ECU_RESET:
            return self._handle_ecu_reset()
        return 0x7F, bytes([service_id, self._NRC_SNS])

    def get_session_info(self) -> dict:
        """Return current session and ECU state as a dict."""
        return {
            "ecu_state": self._ecu.to_dict(),
            "session_active": self._sm.is_active(),
            "authenticated": self._sa.is_authenticated(),
            "role": self._sa.get_role().value if self._sa.get_role() else None,
            "locked": self._sa.is_locked(),
            "flash_status": self._fm.get_status(),
            "boot_info": self._bl.get_bank_info(),
        }

    def reset(self) -> None:
        """Reset DCM, SecurityAccess and ECU state."""
        self._sa.reset()
        self._sm.destroy()
        self._ecu.reset()
        self._pending_download = None

    def _nrc(self, svc: int, nrc: int) -> tuple[int, bytes]:
        return 0x7F, bytes([svc, nrc])

    def _handle_session(self, sub_func: int) -> tuple[int, bytes]:
        if sub_func == 0x01:
            self._ecu.transition(ECUMode.DEFAULT_SESSION)
            self._sm.destroy()
            return 0x50, bytes([0x01])
        if sub_func == 0x02:
            self._sm.create_session()
            self._ecu.transition(ECUMode.PROGRAMMING_SESSION)
            return 0x50, bytes([0x02])
        return self._nrc(self._SVC_SESSION_CTRL, self._NRC_SFNS)

    def _handle_security_access(self, sub_func: int, data: bytes) -> tuple[int, bytes]:
        if self._ecu.mode not in (ECUMode.PROGRAMMING_SESSION, ECUMode.AUTHENTICATED):
            return self._nrc(self._SVC_SECURITY_ACCESS, self._NRC_SFNS)

        if sub_func % 2 == 1:
            role = self._role_from_sub(sub_func)
            try:
                challenge = self._sa.get_challenge(role)
                return 0x67, bytes([sub_func]) + challenge
            except AuthError as exc:
                if "locked" in str(exc):
                    self._ecu.transition(ECUMode.LOCKED)
                    return self._nrc(self._SVC_SECURITY_ACCESS, self._NRC_ENOA)
                return self._nrc(self._SVC_SECURITY_ACCESS, self._NRC_IK)
        else:
            role = self._role_from_sub(sub_func - 1)
            try:
                ok = self._sa.verify_response(role, data)
                if ok:
                    self._ecu.transition(ECUMode.AUTHENTICATED, role.value)
                    return 0x67, bytes([sub_func])
                return self._nrc(self._SVC_SECURITY_ACCESS, self._NRC_IK)
            except AuthError as exc:
                if "locked" in str(exc):
                    self._ecu.transition(ECUMode.LOCKED)
                    return self._nrc(self._SVC_SECURITY_ACCESS, self._NRC_ENOA)
                return self._nrc(self._SVC_SECURITY_ACCESS, self._NRC_IK)

    def _handle_request_download(self, data: bytes) -> tuple[int, bytes]:
        if not self._sa.is_authenticated():
            return self._nrc(self._SVC_REQUEST_DOWNLOAD, self._NRC_SAD)
        try:
            if len(data) >= 8:
                addr = int.from_bytes(data[0:4], "big")
                size = int.from_bytes(data[4:8], "big")
                version = int.from_bytes(data[8:10], "big") if len(data) >= 10 else 2
            else:
                addr, size, version = 0x08010000, 0x1000, 2
            role = self._sa.get_role().value if self._sa.get_role() else "manufacturing"
            self._fm.begin_download(addr, size, role, image_version=version)
            self._pending_download = {"addr": addr, "size": size}
            return 0x74, bytes([0x10, 0x04])
        except FlashError as exc:
            return self._nrc(self._SVC_REQUEST_DOWNLOAD, self._NRC_GPF)

    def _handle_transfer_data(self, seq: int, data: bytes) -> tuple[int, bytes]:
        if not self._sa.is_authenticated():
            return self._nrc(self._SVC_TRANSFER_DATA, self._NRC_SAD)
        try:
            self._fm.transfer_block(seq, data)
            return 0x76, bytes([seq])
        except FlashError:
            return self._nrc(self._SVC_TRANSFER_DATA, self._NRC_GPF)

    def _handle_transfer_exit(self, data: bytes) -> tuple[int, bytes]:
        if not self._sa.is_authenticated():
            return self._nrc(self._SVC_TRANSFER_EXIT, self._NRC_SAD)
        try:
            sig = data if data else b"\x00"
            status = self._fm.get_status()
            full_image = b""
            self._fm.finalize(full_image, sig)
            return 0x77, b""
        except FlashError:
            return self._nrc(self._SVC_TRANSFER_EXIT, self._NRC_GPF)

    def _handle_ecu_reset(self) -> tuple[int, bytes]:
        ok = self._bl.trigger_reset()
        self.reset()
        return 0x51, bytes([0x01 if ok else 0x00])

    @staticmethod
    def _role_from_sub(sub: int) -> FlashRole:
        roles = [FlashRole.MANUFACTURING, FlashRole.SERVICE,
                 FlashRole.ENGINEERING, FlashRole.DEVELOPMENT]
        idx = (sub - 1) // 2 if sub > 0 else 0
        return roles[idx % len(roles)]
