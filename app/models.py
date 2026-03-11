from __future__ import annotations

from typing import Any, Literal
from pydantic import BaseModel, Field


Transport = Literal["osc", "websocket", "http", "tcp", "midi", "other"]
SyncMode = Literal["follow", "independent"]


class DeviceCreate(BaseModel):
    name: str = Field(min_length=1, max_length=80)
    device_type: str = Field(default="generic", min_length=1, max_length=40)
    transport: Transport = "osc"
    endpoint: str = Field(default="", max_length=255)
    enabled: bool = True
    sync_mode: SyncMode = "follow"
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)


class DeviceUpdate(BaseModel):
    name: str | None = Field(default=None, min_length=1, max_length=80)
    device_type: str | None = Field(default=None, min_length=1, max_length=40)
    transport: Transport | None = None
    endpoint: str | None = Field(default=None, max_length=255)
    enabled: bool | None = None
    sync_mode: SyncMode | None = None
    tags: list[str] | None = None
    meta: dict[str, Any] | None = None


class Device(BaseModel):
    id: str
    name: str
    device_type: str
    transport: Transport
    endpoint: str
    enabled: bool
    sync_mode: SyncMode
    tags: list[str] = Field(default_factory=list)
    meta: dict[str, Any] = Field(default_factory=dict)
    online: bool = False
    last_seen_ms: int = 0


class CommandPayload(BaseModel):
    grid_profile: str | None = None
    preset: str | None = None
    blank_cells: list[int] = Field(default_factory=list)
    unblank_cells: list[int] = Field(default_factory=list)
    note: str | None = Field(default=None, max_length=200)


class CommandEntry(BaseModel):
    id: int
    ts_ms: int
    scope: Literal["broadcast", "device"]
    target_device_id: str | None = None
    payload: CommandPayload


class GlobalVisualState(BaseModel):
    grid_profile: str = "4x4"
    preset: str = "Corners"
    blanked_cells: list[int] = Field(default_factory=list)
    revision: int = 0


class Snapshot(BaseModel):
    devices: list[Device]
    visual_state: GlobalVisualState
    command_log: list[CommandEntry]
