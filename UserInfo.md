# User Guide — Validating Automotive Cybersecurity with `secure_flashing_classic_monitor.html`

**File:** `docs/index.html`
**Type:** Standalone Proof-of-Concept dashboard — pure HTML + JavaScript, no server required
**Purpose:** Walk through the full secure ECU firmware-flashing lifecycle and visually confirm that every cybersecurity control required by `requirements/SoftwareRequirements_AUTOSAR_CLASSIC.txt` (SWR-C-001 … SWR-C-020) behaves correctly, without needing Python, a backend, or real hardware.

> This dashboard **simulates** the logic of the `sim/` Python modules in JavaScript for demonstration purposes. Signatures, hashes, and crypto failures are faked (`fakeSign()` / `fakeVerify()`) so the flow can be explored instantly in a browser. For a version that drives the **real** Python cryptography (ECDSA P-256, SHA-256) over a live FastAPI backend, use `docs/secure_flashing_classic_monitor.html` instead (see the note at the end of this document).

---

## 1. Getting Started

1. Double-click `docs/SecureFlashing.html`, or open it via `File → Open` in any modern browser.
2. No installation, server, or network connection is needed — everything runs client-side.
3. The page loads with a system-ready log entry and all panels initialized to their default (IDLE / unauthenticated) state.

---

## 2. Layout Overview

The dashboard is organized into 4 functional zones, matching the AUTOSAR Classic secure-flashing architecture:

| Zone | What it shows |
|---|---|
| **Header + Architecture Flow strip** | Identity of the demo and the data-flow path: Tester → DCM → SecAccess → CSM → HSM → FlashMgr → DEM |
| **Left column** | ECU State Monitor + Quick Scenarios |
| **Center column** | Authentication panel + Flash Console |
| **Right column** | DEM (Diagnostic Event Manager) Event Log |
| **Bottom strip** | Verification Test Case (VTC) grid — all 16 test cases |

Each panel maps directly to one or more software requirements (`SWR-C-*`), so as you interact with the GUI you are effectively exercising the same control paths that the `pytest` test suite (`tests/test_vtc_*.py`) verifies against the real `sim/` modules.

---

## 3. Header & Architecture Flow Strip

At the top, the flow diagram (🖥️ Tester → 📡 DCM → 🔑 SecAccess → ⚙️ CSM → 🔒 HSM → 📦 FlashMgr → 📋 DEM) is a live map of how a real UDS diagnostic tester talks to the ECU:

- **Tester** — the external diagnostic tool issuing UDS requests (this browser page plays that role).
- **DCM** — Diagnostic Communication Manager, the UDS service dispatcher (0x10 DiagnosticSessionControl, 0x27 SecurityAccess, 0x34/0x36/0x37 firmware transfer).
- **SecAccess** — SecurityAccess: challenge-response authentication, role & lockout enforcement.
- **CSM** — Crypto Service Manager: the job state machine that routes crypto operations.
- **HSM** — Hardware Security Module (simulated): holds all key material, performs signing/verification.
- **FlashMgr** — Flash Manager: Program → Verify → Commit sequencing with memory-boundary checks.
- **DEM** — Diagnostic Event Manager: the audit trail every security-relevant action is logged to.

Hover over any node to see its tooltip describing its responsibility.

---

## 4. ECU State Monitor (left column, top)

This panel is the single source of truth for the ECU's current security posture. It refreshes instantly after every action you take elsewhere on the page.

| Field | Meaning | Security relevance |
|---|---|---|
| **Session Mode** | `DEFAULT_SESSION` / `PROGRAMMING_SESSION` / `AUTHENTICATED` / `LOCKED` | Confirms the ECU only accepts flashing once the correct UDS session sequence has occurred (SWR-C-001) |
| **Auth Status** | Authenticated / Not Authenticated | Directly reflects whether SecurityAccess (0x27) succeeded |
| **Active Role** | The authenticated role (manufacturing / service / engineering / development) | Confirms role-based access control is enforced — only permitted roles can flash the memory regions they own |
| **Active Bank** | `A` or `B` | Shows which A/B firmware bank is currently live — flips after every successful commit |
| **Flash Pending** | Yes/No | If "Yes" persists across a reset, it indicates an interrupted flash — this is exactly the condition the Recovery Manager watches for (SWR-C-009) |
| **SW Version** | Current committed firmware version | Used to prove anti-rollback (SWR-C-019): a new image must have a strictly higher version |
| **Lockout** | 🔓 Open / 🔒 LOCKED | Shows whether repeated authentication failures have tripped the lockout (SWR-C-011) |
| **Retry Count** | `n / 3` | Live counter of failed authentication attempts before lockout triggers |

**Controls:**
- **⟳ ECU Reset** — returns the ECU to `DEFAULT_SESSION`, clears auth/lockout state. Use this between scenarios to start from a clean baseline.
- **🥾 Boot** — simulates a power-on reset. If `Flash Pending` was left `Yes` (e.g. after a simulated power loss), this button triggers the A/B bank recovery fallback and logs a `RECOVERY_ACTIVATED` DEM event.

**How to validate security with this panel:** after running any scenario or manual flash, glance at this panel first — it should always reflect a *consistent* state (e.g. you should never see `Flash Pending: Yes` and `Session Mode: AUTHENTICATED` persist indefinitely; that would indicate a stuck/incomplete transaction that a real ECU must recover from).

---

## 5. Quick Scenarios (left column, bottom)

Six pre-scripted, one-click end-to-end attack/success scenarios. Each animates the full chain of panels so you can watch the security control activate in real time. This is the fastest way to demonstrate the lab to someone unfamiliar with the project.

| Scenario | What it proves | Requirement |
|---|---|---|
| ✅ **Happy path — full flash** | A legitimate manufacturing-role tester with a valid key can authenticate and flash a correctly signed image, and the ECU boots successfully afterward | SWR-C-001, 003, 010 |
| 🚫 **Bad credentials** | Three consecutive invalid signature attempts trigger a hard lockout — brute-forcing SecurityAccess is not viable | SWR-C-011 |
| 🔄 **Replay attack** | A previously used transaction counter is rejected when replayed | SWR-C-005 |
| ❌ **Tampered firmware** | An image modified *after* it was signed fails signature verification, aborts the flash, and zeroes the staging buffer | SWR-C-003, SWR-C-015 |
| ⬇️ **Downgrade attempt** | An older firmware version is rejected by the monotonic version counter in NvM, even if otherwise validly signed | SWR-C-019 |
| ⚡ **Power loss recovery** | A flash interrupted mid-transfer leaves `flash_pending=true`; on next boot, the Recovery Manager rolls back to the last known-good bank instead of booting corrupted firmware | SWR-C-009 |

**How to use:** click a scenario button — its icon changes to ⏳ while it plays, then ✓ when complete. Watch the **Flash Console** workflow steps animate, the **ECU State Monitor** update, and new entries appear in the **DEM Event Log** — all three panels are your evidence trail for that scenario's outcome.

---

## 6. Authentication Panel (center column, top)

Models UDS SecurityAccess (service 0x27) — the gate that must be passed before any flashing is permitted (SWR-C-001, 002, 006, 011).

**Controls:**
- **Role selector** — choose which of the four roles (Manufacturing / Service / Engineering / Development) is attempting to authenticate. Each role has different memory-region permissions (see Flash Console below).
- **Credential selector** — choose what kind of key the "attacker/tester" presents:
  - **Valid Key** — the correct key for the selected role → authentication succeeds.
  - **Invalid Key** — a garbage/incorrect signature → authentication fails, retry counter increments.
  - **Wrong Role Key** — a validly-formed key, but belonging to a *different* role → authentication fails (proves role-key binding, not just "any signature passes").
- **① Enter Prog Session** — simulates UDS `0x10 0x02` (enter Programming Session). Must be done before a challenge can be requested.
- **② Request Seed** — simulates UDS `0x27 0x01`. Issues a fresh 32-byte ECDSA challenge nonce (shown in the mono-font box above the buttons). A *new, unpredictable* nonce every time proves replay protection is structurally possible.
- **③ Send Key Response** — simulates UDS `0x27 0x02`. Signs the nonce with the credential you selected and submits it for verification. Enabled only once a challenge is pending.

**How to validate security with this panel:**
1. Pick **Manufacturing** + **Valid Key**, click through ①②③ — confirm `Auth Status` turns green/Authenticated and `Retry Count` stays at 0.
2. Reset, then pick **Invalid Key** and click ①②③ three times in a row — confirm the retry counter climbs 1/3 → 2/3 → 3/3, and on the third failure `Lockout` flips to 🔒 LOCKED. Try a fourth attempt — it should be rejected outright with "locked" even before checking the signature.
3. Reset, then pick **Wrong Role Key** — confirm this is also rejected (not silently accepted as "any signature is fine").

---

## 7. Flash Console (center column, bottom)

Models the firmware download/program/verify/commit pipeline (SWR-C-003, 004, 007, 008, 017). Only usable once authenticated (the **⬆ Flash Image** button stays disabled otherwise — proving flashing cannot bypass authentication).

**Controls:**
- **Image selector** — choose the firmware payload to flash:
  - **✅ Valid — signed v2** — correctly signed, version-incremented image → should flash and commit successfully.
  - **🔴 Tampered — modified after sign** — signature won't match content → should abort at the Verify step.
  - **⬇️ Downgrade — version 0** — version lower than the currently installed one → should be rejected immediately, before any data transfer.
  - **🚫 Wrong Address — bootloader region** — targets a protected memory region the current role isn't permitted to write → should be rejected immediately.
- **Workflow steps strip** (📥 Download → ✍️ Program → 🔍 Verify → ✅ Commit → 🥾 Secure Boot) — each step highlights **blue/pulsing** while active, turns **green** on success, or **red** if that step is where the operation failed. This is the clearest visual indicator of *where* in the pipeline a given firmware image was rejected.
- **Progress bar** — overall completion percentage of the current flash operation.
- **Flashing Console log** — a timestamped, color-coded (info/ok/warn/err) transcript of every UDS request/response exchanged during the flash (0x34 RequestDownload, 0x36 TransferData, 0x37 RequestTransferExit, etc.) — this is your evidence log for a specific flash attempt.
- **⬆ Flash Image** — starts the sequence for the selected image.
- **✕ Abort** — manually aborts an in-progress flash; confirms the staging buffer is sanitized and `Flash Pending` clears (SWR-C-015).
- **🗑 Clear Log** — clears only the Flashing Console log (not the DEM Event Log).

**How to validate security with this panel:**
1. After authenticating, select **Valid** and flash — confirm all 5 workflow steps turn green in sequence, ending in a "Secure boot PASSED" log line and the **Active Bank** flipping (A ↔ B).
2. Select **Tampered** and flash — confirm the sequence proceeds through Download/Program normally, but **Verify** turns red, and the log shows `SIGNATURE MISMATCH` followed by a buffer-sanitization warning.
3. Select **Downgrade** — confirm it's rejected at the very first step (Download turns red immediately) with a `DOWNGRADE_REJECTED` reason, without ever touching the staging buffer.
4. Select **Wrong Address** — confirm the same immediate rejection pattern, this time citing the protected memory region.
5. Start a **Valid** flash, then click **✕ Abort** partway through — confirm the workflow resets and no bank switch occurs.

---

## 8. DEM Event Log (right column)

The Diagnostic Event Manager panel is the ECU's permanent security audit trail (SWR-C-014) — every authentication attempt, flash operation, lockout, and recovery event is logged here, independent of which panel triggered it.

- Each entry shows: **severity badge** (INFO / WARNING / CRITICAL), a unique **event ID** (`DEM-####-EVENT_NAME`), the **SWR requirement reference** it relates to, and a **timestamp**.
- **CRITICAL** events (red) always correspond to a security-relevant abort: signature mismatch, HSM failure, downgrade rejection, manual/forced abort with buffer sanitization.
- **WARNING** events (amber) flag suspicious-but-recoverable conditions: auth failures, replay detection, power-loss recovery.
- **INFO** events (blue) are normal lifecycle steps: session entry, challenge issuance, successful auth, successful flash, secure boot success.
- **Clear** button empties the visible log (does not affect ECU state) — useful to reset the view before starting a fresh demonstration scenario so the audit trail for that scenario is easy to isolate and screenshot.

**How to validate security with this panel:** for every scenario or manual action you run, confirm a DEM entry was created with the severity you'd expect. A security control that fails "silently" (i.e., no DEM entry despite a rejection happening) would itself be a finding — in this simulation, every meaningful reject path is instrumented, which is what SWR-C-014 requires.

---

## 9. Verification Test Case (VTC) Grid (bottom strip)

This is the formal test evidence panel — all 16 Verification Test Cases from `requirements/TestPlan.txt`, each mapped to specific SWR-C requirement(s) (shown in the tooltip on hover).

| Control | Behavior |
|---|---|
| **▶ Run All 16 VTCs** | Executes every VTC in sequence, animating each card (⏳ running → ✅ pass / ❌ fail), logging the pass/fail evidence to both the Flashing Console log and the DEM Event Log, and updating the `n / 16 passed` counter |
| **Click an individual VTC card** | Runs just that one test case and updates its card/counter |
| **↺ Reset** | Clears all VTC card results back to their default (un-run) icon |

The 16 VTCs, at a glance:

| VTC | Validates | Requirement |
|---|---|---|
| VTC-01 | Flash rejected before authentication; allowed after | SWR-C-001, 002 |
| VTC-02 | Invalid signature is rejected and does not authenticate | SWR-C-001, 011 |
| VTC-03 | Replayed transaction counter is rejected | SWR-C-005 |
| VTC-04 | Correctly signed image is accepted | SWR-C-003 |
| VTC-05 | Tampered image is rejected; abort + buffer sanitization | SWR-C-003, 015 |
| VTC-06 | Writes outside the permitted memory region are rejected | SWR-C-007 |
| VTC-07 | Incomplete flash correctly sets/clears the pending flag | SWR-C-008, 009 |
| VTC-08 | Power-loss recovery falls back to the last valid bank | SWR-C-009 |
| VTC-09 | Firmware downgrade is rejected | SWR-C-019 |
| VTC-10 | Secure boot verifies the active bank's signature | SWR-C-010 |
| VTC-11 | HSM failure during verification aborts safely | SWR-C-012, 015 |
| VTC-12 | Idle session times out correctly | SWR-C-005 |
| VTC-13 | Repeated auth failures trigger lockout | SWR-C-011 |
| VTC-14 | Corrupted block data is detected before commit | SWR-C-004, 008 |
| VTC-15 | Staging buffer is sanitized after any abort | SWR-C-015 |
| VTC-16 | PKI certificate chain validation (expired/revoked rejected) | SWR-C-020 |

**How to use this section as a validation report:** running **▶ Run All 16 VTCs** and reaching **16 / 16 passed** is the same pass criterion used by the Phase 1 Gate checklist (all `SWR-C-001` … `SWR-C-020` = VERIFIED). This is the quickest way to give a reviewer, auditor, or stakeholder a live, visual "all green" confirmation that every mandated security control behaves as specified.

---

## 10. Suggested End-to-End Walkthrough (for a live demo or audit)

1. Open the page — note the banner confirms this is a **Proof of Concept**.
2. Run **▶ Run All 16 VTCs** first — establish a baseline "all controls pass" result.
3. Walk through the 6 **Quick Scenarios** in order (Happy Path → Bad Credentials → Replay → Tampered → Downgrade → Power Loss) — narrate what each one proves, pointing at the ECU State Monitor, Flash Console workflow steps, and DEM Event Log as evidence.
4. Switch to manual mode: pick a role/credential combination not covered by the canned scenarios (e.g. **Service** role with **Wrong Role Key**) to show the controls generalize beyond the scripted paths.
5. Finish by clicking **⟳ ECU Reset** to show the ECU returns cleanly to a known-good baseline state.

---

## 11. Important Limitation — This is a Simulation

`index.html` fakes cryptography in JavaScript (`fakeSign()` / `fakeVerify()` — see the file's `<script>` section) purely so the control-flow logic can be demonstrated instantly, offline, with no dependencies. It does **not** call real ECDSA P-256 signing/verification, and it does **not** exercise the actual Python `sim/` modules.

For a version that performs **real cryptography** by calling the live FastAPI backend and the actual `sim/hsm.py`, `sim/security_access.py`, `sim/flash_manager.py`, etc., use:

```
docs/secure_flashing_classic_monitor.html
```

which requires the backend running first:

```bash
uvicorn api.main:app --reload --port 8000
```

The Live Monitor has the identical GUI layout described above — everything in this guide applies to it panel-for-panel — the only difference is that every action is a real HTTP/WebSocket call to the real simulation engine instead of an in-browser animation.
