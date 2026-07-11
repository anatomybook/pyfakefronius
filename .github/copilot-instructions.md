# Copilot Instructions

## Build, test, and lint commands

This repository does not define a build system, test suite, linter config, or single-test command. The only lightweight validation currently available from the checked-in files is:

```bash
python -m py_compile fake_fronius.py receive_UDP.py
```

## High-level architecture

This repository is a small protocol bridge that makes a SENEC battery system look enough like a Fronius installation for a downstream client to consume.

- `fake_fronius.py` is the main service. It exposes a `FastAPI` app that implements a narrow subset of Fronius Solar API endpoints:
  - `/solar_api/v1/GetPowerFlowRealtimeData.fcgi`
  - `/solar_api/v1/GetStorageRealtimeData.cgi`
  - `/solar_api/v1/GetOhmPilotRealtimeData.cgi`
  - `/debug/`
- The Fronius-shaped responses are not backed by Fronius hardware. They are synthesized from live SENEC values fetched through `pysenec`.
- `receive_UDP.py` is a separate standalone UDP responder for Fronius Datamanager discovery on port `50052`. It answers one specific discovery payload with a hard-coded JSON response so clients can find the fake device on the network.

Runtime flow in `fake_fronius.py`:

1. A request hits one of the Solar API endpoints.
2. The module-level `memorizer` decides whether cached data is stale (`> 9` seconds old).
3. If stale, the handler opens a fresh `aiohttp.ClientSession`, queries the hard-coded SENEC host (`192.168.178.59`) via `pysenec`, and updates the in-memory cache.
4. The handler maps SENEC fields into Fronius-style JSON payloads and returns them immediately.

There is no persistent storage, background polling loop, dependency injection layer, or shared app startup/shutdown lifecycle in use right now. All state lives in the singleton `memorizer`.

## Key conventions

- API compatibility is more important than internal elegance. Keep the existing Fronius endpoint paths, payload nesting, and status-code conventions stable unless the consuming client is updated at the same time.
- The bridge intentionally rewrites SENEC values into Fronius semantics:
  - `p_load` is `-senec.house_power`
  - `p_akku` is `-senec.battery_state_power`
  - `p_grid` and `p_pv` keep SENEC sign conventions
  These sign flips are essential to the JSON the downstream client expects.
- `GetPowerFlowRealtimeData` and `GetStorageRealtimeData` share the same cached SENEC snapshot through the module-level `memorizer`; edits should preserve that consistency unless the caching model is intentionally redesigned.
- Battery state is translated heuristically from `system_state`, `charging_info`, and `soc` into Fronius-like fields such as `Battery_Mode`, `BatteryStandby`, and `Status_BatteryCell`. Those mappings are domain-specific behavior, not incidental formatting.
- Several hardware identity values are intentionally hard-coded to mimic a real Fronius/BYD installation:
  - SENEC host IP in `fake_fronius.py`
  - UDP discovery response fields in `receive_UDP.py`
  - BYD battery metadata returned by `GetStorageRealtimeData`
  Treat these as deployment-specific fixtures when changing behavior.
- `/debug/?akku=hack` is not a generic debug endpoint. It applies a specific data rewrite: charging battery power is folded into load, discharge is folded into grid, and `P_Akku` is hidden. Preserve that meaning if the endpoint is kept.
