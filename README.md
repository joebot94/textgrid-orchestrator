# TextGrid Orchestrator

Master sync server + live control GUI for multi-device visual rigs.

This project is designed as the control plane for setups that include TextGrid,
MGP/video-wall processors, DVI matrix systems, and other adapters.

## What It Does (v0.1)

- Central server state for:
  - `grid_profile`
  - `preset`
  - `blanked_cells`
  - revision count
- Device registry with **up to 25 devices**
- Per-device sync policy (`follow` or `independent`)
- Heartbeat + online/offline status
- Command dispatch:
  - broadcast to all
  - target a single device
- Real-time dashboard via WebSocket

## Versioning and Releases

- This repo uses semantic-style versions with pre-release tags while features are stabilizing.
- Current tag: `v0.1.0-alpha.1`
- Day-to-day changes go into `## [Unreleased]` in `CHANGELOG.md`.
- When shipping:
  1. move unreleased notes into a new version section
  2. commit
  3. tag and push

Example:

```bash
git add -A
git commit -m "release: v0.1.0"
git tag -a v0.1.0 -m "v0.1.0"
git push
git push origin v0.1.0
```

## Run

```bash
cd "/Users/joe/Desktop/textgrid-orchestrator"
python3 -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
python3 -m app.main
```

Open: `http://localhost:8787`

## UI

- **CONFIG** tab:
  - add/remove devices
  - ping heartbeat
  - toggle follow/independent mode
- **LIVE** tab:
  - current global visual state
  - online/offline device counts
  - recent command timeline
- **COMMANDS** tab:
  - send grid/preset/blank commands to all or one device

## API (core)

- `GET /api/health`
- `GET /api/state`
- `GET /api/devices`
- `POST /api/devices`
- `PUT /api/devices/{device_id}`
- `DELETE /api/devices/{device_id}`
- `POST /api/heartbeat/{device_id}`
- `POST /api/commands/broadcast`
- `POST /api/commands/device/{device_id}`
- `WS /ws`

## Architecture Notes

- `app/state.py` contains orchestration logic and persistence.
- `app/main.py` contains API, WebSocket fanout, and background status sweep.
- `app/static/` is a lightweight performance-friendly dashboard.

This split keeps orchestration rules separate from UI and adapters.

## Next Extensions (Phase 2)

1. Clock sources:
   - internal timer
   - tap tempo
   - audio beat
   - MIDI clock
   - OSC beat
2. Scene scripting:
   - preset order
   - per-scene dwell
   - sparse/full alternation
3. Adapter workers:
   - TextGrid OSC adapter
   - MGP adapter
   - DVI matrix adapter
4. Reliability:
   - ack tracking
   - latency metrics
   - command replay on reconnect
