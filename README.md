# Secure Flashing Lab — AUTOSAR Classic (Phase 1)

Spec-driven, TDD simulation of a secure ECU flashing stack implementing AUTOSAR Classic modules:
DCM · CSM · CryIf · HSM · DEM · NvM · Bootloader · FlashManager · SecurityAccess

**[▶ Live Demo](https://venaychawda.github.io/SecureFlashing/)**

## Quick Start

```bash
pip install -r requirements.txt

# Run all tests
pytest tests/ -v --tb=short

# Start simulation backend
uvicorn api.main:app --reload --port 8000

# Open dashboard (separate terminal)
python -m http.server 3000 --directory dashboard
# → http://localhost:3000
```

## Phase Gate

Phase 1 is complete when all 16 VTCs pass and the dashboard renders them green.
Do NOT start Phase 2 without explicit instruction.

## Structure

| Directory | Purpose |
|---|---|
| `requirements/` | CR / SR / SWR-C / VTC CSV files + traceability matrix |
| `design/` | Architecture, HLD, LLDs, sequence diagrams |
| `sim/` | Python simulation of all AUTOSAR modules |
| `api/` | FastAPI backend + WebSocket event bus |
| `dashboard/` | Single-page dark industrial UI |
| `tests/` | 16 pytest VTC test files |
| `docs/` | ASPICE SWE.1–SWE.6 compliance documents |
