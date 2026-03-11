from __future__ import annotations

import asyncio
from pathlib import Path

from fastapi import FastAPI, HTTPException, WebSocket, WebSocketDisconnect
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles

from .models import CommandPayload, DeviceCreate, DeviceUpdate
from .state import OrchestratorState


ROOT = Path(__file__).resolve().parent
STATIC_DIR = ROOT / "static"
STORE_PATH = ROOT.parent / "data" / "state.json"


class WSManager:
    def __init__(self):
        self._clients: set[WebSocket] = set()
        self._lock = asyncio.Lock()

    async def connect(self, ws: WebSocket):
        await ws.accept()
        async with self._lock:
            self._clients.add(ws)

    async def disconnect(self, ws: WebSocket):
        async with self._lock:
            self._clients.discard(ws)

    async def broadcast(self, event: str, data: dict):
        async with self._lock:
            clients = list(self._clients)

        if not clients:
            return

        dead: list[WebSocket] = []
        payload = {"event": event, "data": data}
        for ws in clients:
            try:
                await ws.send_json(payload)
            except Exception:
                dead.append(ws)

        if dead:
            async with self._lock:
                for ws in dead:
                    self._clients.discard(ws)


state = OrchestratorState(STORE_PATH)
ws_manager = WSManager()
app = FastAPI(title="TextGrid Orchestrator", version="0.1.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


async def _broadcast_snapshot():
    await ws_manager.broadcast("snapshot", state.snapshot().model_dump())


@app.on_event("startup")
async def startup_event():
    state.load()

    async def heartbeat_sweeper():
        while True:
            await asyncio.sleep(1.0)
            changed = state.refresh_online_flags()
            if changed:
                await _broadcast_snapshot()

    app.state.sweeper_task = asyncio.create_task(heartbeat_sweeper())


@app.on_event("shutdown")
async def shutdown_event():
    task = getattr(app.state, "sweeper_task", None)
    if task:
        task.cancel()


@app.get("/")
async def root():
    return FileResponse(STATIC_DIR / "index.html")


@app.get("/api/health")
async def health():
    return {"ok": True, "devices": len(state.devices), "max_devices": state.MAX_DEVICES}


@app.get("/api/state")
async def get_state():
    return state.snapshot()


@app.get("/api/devices")
async def get_devices():
    return state.snapshot().devices


@app.post("/api/devices")
async def create_device(payload: DeviceCreate):
    try:
        device = state.add_device(payload)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc))
    await _broadcast_snapshot()
    return device


@app.put("/api/devices/{device_id}")
async def update_device(device_id: str, payload: DeviceUpdate):
    try:
        device = state.update_device(device_id, payload)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    await _broadcast_snapshot()
    return device


@app.delete("/api/devices/{device_id}")
async def delete_device(device_id: str):
    try:
        state.remove_device(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    await _broadcast_snapshot()
    return {"ok": True}


@app.post("/api/heartbeat/{device_id}")
async def heartbeat(device_id: str):
    try:
        dev = state.mark_heartbeat(device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Device not found")
    await _broadcast_snapshot()
    return dev


@app.post("/api/commands/broadcast")
async def command_broadcast(payload: CommandPayload):
    entry = state.apply_command(payload, scope="broadcast")
    await ws_manager.broadcast("command", entry.model_dump())
    await _broadcast_snapshot()
    return entry


@app.post("/api/commands/device/{device_id}")
async def command_device(device_id: str, payload: CommandPayload):
    try:
        entry = state.apply_command(payload, scope="device", target_device_id=device_id)
    except KeyError:
        raise HTTPException(status_code=404, detail="Target device not found")
    await ws_manager.broadcast("command", entry.model_dump())
    await _broadcast_snapshot()
    return entry


@app.websocket("/ws")
async def ws_endpoint(websocket: WebSocket):
    await ws_manager.connect(websocket)
    try:
        await websocket.send_json({"event": "snapshot", "data": state.snapshot().model_dump()})
        while True:
            await websocket.receive_text()
    except WebSocketDisconnect:
        await ws_manager.disconnect(websocket)


if __name__ == "__main__":
    import uvicorn

    uvicorn.run("app.main:app", host="0.0.0.0", port=8787, reload=True)
