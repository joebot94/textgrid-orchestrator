from __future__ import annotations

import json
import time
import uuid
from pathlib import Path

from pydantic import ValidationError

from .models import (
    CommandEntry,
    CommandPayload,
    Device,
    DeviceCreate,
    DeviceUpdate,
    GlobalVisualState,
    Snapshot,
)


class OrchestratorState:
    MAX_DEVICES = 25
    OFFLINE_AFTER_MS = 15_000
    MAX_COMMAND_LOG = 250

    def __init__(self, store_path: Path):
        self.store_path = store_path
        self.devices: dict[str, Device] = {}
        self.visual_state = GlobalVisualState()
        self.command_log: list[CommandEntry] = []
        self._next_command_id = 1

    def _now_ms(self) -> int:
        return int(time.time() * 1000)

    def load(self):
        if not self.store_path.exists():
            return
        raw = json.loads(self.store_path.read_text(encoding="utf-8"))

        self.devices = {}
        for d in raw.get("devices", []):
            try:
                dev = Device(**d)
                self.devices[dev.id] = dev
            except ValidationError:
                continue

        try:
            self.visual_state = GlobalVisualState(**raw.get("visual_state", {}))
        except ValidationError:
            self.visual_state = GlobalVisualState()

        self.command_log = []
        for c in raw.get("command_log", []):
            try:
                self.command_log.append(CommandEntry(**c))
            except ValidationError:
                continue

        if self.command_log:
            self._next_command_id = max(c.id for c in self.command_log) + 1

    def save(self):
        self.store_path.parent.mkdir(parents=True, exist_ok=True)
        snapshot = self.snapshot().model_dump()
        self.store_path.write_text(json.dumps(snapshot, indent=2), encoding="utf-8")

    def snapshot(self) -> Snapshot:
        devices = sorted(self.devices.values(), key=lambda d: d.name.lower())
        commands = sorted(self.command_log, key=lambda c: c.id, reverse=True)
        return Snapshot(devices=devices, visual_state=self.visual_state, command_log=commands)

    def add_device(self, payload: DeviceCreate) -> Device:
        if len(self.devices) >= self.MAX_DEVICES:
            raise ValueError(f"Device limit reached ({self.MAX_DEVICES})")

        device_id = str(uuid.uuid4())
        now_ms = self._now_ms()
        device = Device(
            id=device_id,
            name=payload.name.strip(),
            device_type=payload.device_type.strip(),
            transport=payload.transport,
            endpoint=payload.endpoint.strip(),
            enabled=payload.enabled,
            sync_mode=payload.sync_mode,
            tags=[t.strip() for t in payload.tags if t.strip()],
            meta=payload.meta,
            online=False,
            last_seen_ms=0,
        )
        self.devices[device_id] = device
        self.save()
        return device

    def update_device(self, device_id: str, payload: DeviceUpdate) -> Device:
        if device_id not in self.devices:
            raise KeyError("Device not found")

        current = self.devices[device_id]
        patch = payload.model_dump(exclude_none=True)

        update_data = current.model_dump()
        for key, value in patch.items():
            if key in {"name", "device_type", "endpoint"} and isinstance(value, str):
                update_data[key] = value.strip()
            elif key == "tags" and value is not None:
                update_data[key] = [t.strip() for t in value if t.strip()]
            else:
                update_data[key] = value

        updated = Device(**update_data)
        self.devices[device_id] = updated
        self.save()
        return updated

    def remove_device(self, device_id: str):
        if device_id not in self.devices:
            raise KeyError("Device not found")
        del self.devices[device_id]
        self.save()

    def mark_heartbeat(self, device_id: str) -> Device:
        if device_id not in self.devices:
            raise KeyError("Device not found")

        device = self.devices[device_id]
        updated = device.model_copy(update={
            "last_seen_ms": self._now_ms(),
            "online": True,
        })
        self.devices[device_id] = updated
        self.save()
        return updated

    def refresh_online_flags(self) -> bool:
        now = self._now_ms()
        changed = False
        for device_id, dev in list(self.devices.items()):
            online = bool(dev.last_seen_ms and (now - dev.last_seen_ms) <= self.OFFLINE_AFTER_MS)
            if online != dev.online:
                self.devices[device_id] = dev.model_copy(update={"online": online})
                changed = True

        if changed:
            self.save()
        return changed

    def apply_command(
        self,
        payload: CommandPayload,
        *,
        scope: str,
        target_device_id: str | None = None,
    ) -> CommandEntry:
        if scope == "device" and target_device_id and target_device_id not in self.devices:
            raise KeyError("Target device not found")

        cleaned_blank = sorted({i for i in payload.blank_cells if i >= 0})
        cleaned_unblank = sorted({i for i in payload.unblank_cells if i >= 0})
        normalized = CommandPayload(
            grid_profile=(payload.grid_profile or "").strip() or None,
            preset=(payload.preset or "").strip() or None,
            blank_cells=cleaned_blank,
            unblank_cells=cleaned_unblank,
            note=(payload.note or "").strip() or None,
        )

        if scope == "broadcast":
            if normalized.grid_profile:
                self.visual_state.grid_profile = normalized.grid_profile
            if normalized.preset:
                self.visual_state.preset = normalized.preset

            current = set(self.visual_state.blanked_cells)
            current.update(normalized.blank_cells)
            current.difference_update(normalized.unblank_cells)
            self.visual_state.blanked_cells = sorted(current)
            self.visual_state.revision += 1

        entry = CommandEntry(
            id=self._next_command_id,
            ts_ms=self._now_ms(),
            scope=scope,
            target_device_id=target_device_id,
            payload=normalized,
        )
        self._next_command_id += 1

        self.command_log.append(entry)
        if len(self.command_log) > self.MAX_COMMAND_LOG:
            self.command_log = self.command_log[-self.MAX_COMMAND_LOG :]

        self.save()
        return entry
