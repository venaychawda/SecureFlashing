# Secure Flashing Lab — AUTOSAR Classic (Phase 1)

Spec-driven, TDD simulation of a secure ECU flashing stack implementing AUTOSAR Classic modules:
DCM · CSM · CryIf · HSM · DEM · NvM · Bootloader · FlashManager · SecurityAccess · PKI Manager ·
Session Manager · Recovery Manager · Version Manager · Failure Handler

**[▶ Live Demo](https://venaychawda.github.io/SecureFlashing/)** — the standalone PoC dashboard,
served straight from this repo via GitHub Pages. No backend needed to view it.

## What's in this repo

- **`sim/`** — a full Python simulation of the AUTOSAR Classic secure-flashing stack (16
  modules), covering authentication, block-wise flashing, A/B bank secure boot, anti-rollback,
  recovery, and failure handling.
- **`tests/`** — 16 pytest suites, one per Verification Test Case (VTC-01 … VTC-16), driving
  every module through its happy path and failure scenarios.
- **`api/`** — a FastAPI backend that exposes the simulation over REST + a WebSocket event bus,
  so you can drive it interactively instead of just running pytest.
- **`docs/`** — the two-panel dashboards you actually look at:
  - `index.html` — a self-contained, no-server **Proof of Concept**. Open it directly in a
    browser (or use the live demo link above) and it animates the flashing workflow, ECU state
    machine, and all 16 VTC scenarios using scripted JS — no Python required.
  - `secure_flashing_classic_monitor.html` — the **live monitor**. Connects to the FastAPI
    backend over WebSocket and shows real ECU state/events as you drive the simulation.
- **`documents/`** — the ASPICE SWE.1–SWE.6 compliance package (requirements traceability,
  architecture, detailed design, unit/integration/qualification test evidence).
- **`design/`** — architecture diagrams, HLD, per-module LLDs, and Mermaid sequence diagrams.
- **`requirements/`** — customer/system/software requirements and the test plan, as
  CSV-importable `.txt` files, plus the generated traceability matrix.

> Note: `docs/` here holds the **dashboards**, not documentation — it's named `docs/`
> specifically so GitHub Pages can publish `index.html` directly. Compliance documents live in
> `documents/` instead.

## Quick Start

### Option A — One-click launch (Windows, recommended)

Double-click **`launch.bat`** in the repo root. It will:

1. Find a working Python 3.11/3.12 interpreter (via the `py` launcher or `python` on PATH).
2. Create/reuse a virtual environment in `.\venv`.
3. Install all dependencies from `requirements.txt`.
4. Start the FastAPI backend (`uvicorn api.main:app --port 8000`) in its own window.
5. Open `docs\secure_flashing_classic_monitor.html` — the live monitor — in your default
   browser, already connected to the backend.

Close the "Backend" console window (or `Ctrl+C` inside it) to stop the server when you're done.
Nothing else needs to be installed or configured by hand.

### Option B — Manual steps

```bash
pip install -r requirements.txt

# Run all 16 VTC tests
pytest tests/ -v --tb=short

# Start the simulation backend
uvicorn api.main:app --reload --port 8000

# In a separate terminal: serve the dashboards
python -m http.server 3000 --directory docs
# → open http://localhost:3000/secure_flashing_classic_monitor.html for the live monitor
# → or open docs/index.html directly (double-click, no server) for the standalone PoC
```

## Phase Gate

Phase 1 (AUTOSAR Classic simulation) is **complete**: all 16 VTCs pass, both dashboards are
functional, and the ASPICE SWE.1–SWE.6 package is in `documents/`. Phases 2–6 (hardware
integration via ATECC608A, ASPICE audit finalisation, and the AUTOSAR Adaptive track) are
blocked pending explicit instruction — see `CLAUDE.md` for the full phase plan.

## Structure

| Directory | Purpose |
|---|---|
| `requirements/` | CR / SR / SWR-C / VTC CSV files + traceability matrix |
| `design/` | Architecture, HLD, LLDs, sequence diagrams |
| `sim/` | Python simulation of all 16 AUTOSAR modules |
| `api/` | FastAPI backend + WebSocket event bus |
| `docs/` | Dashboards — PoC (`index.html`) + live monitor, published via GitHub Pages |
| `tests/` | 16 pytest VTC test files |
| `documents/` | ASPICE SWE.1–SWE.6 compliance documents |
| `launch.bat` | One-click Windows launcher — see Quick Start above |
