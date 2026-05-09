"""Patient room simulator: bed, lights, HVAC, blinds, TV, nurse-call."""

from __future__ import annotations

import json
import time
from dataclasses import dataclass, field, asdict
from typing import Any


# Value ranges shared with the safety validator.
BED_HEAD_RANGE = (0, 60)        # degrees
BED_FOOT_RANGE = (0, 30)        # degrees
LIGHT_BRIGHTNESS_RANGE = (0, 100)
TEMPERATURE_RANGE_C = (18.0, 26.0)
BLIND_RANGE = (0, 100)          # 0 = closed, 100 = open
TV_VOLUME_RANGE = (0, 30)


@dataclass
class AuditEntry:
    timestamp: float
    actor: str               # "patient" | "nurse" | "doctor" | "visitor"
    device: str
    action: str
    args: dict
    accepted: bool
    reason: str = ""


@dataclass
class PatientRoom:
    """In-memory simulation of a single patient room."""

    room_id: str = "ROOM-101"

    bed_head_angle: int = 0
    bed_foot_angle: int = 0
    bed_clinical_lock: bool = False

    main_light_on: bool = True
    main_light_brightness: int = 80
    reading_light_on: bool = False
    reading_light_brightness: int = 60

    temperature_c: float = 22.0
    hvac_mode: str = "auto"

    blinds_position: int = 50

    tv_on: bool = False
    tv_channel: int = 1
    tv_volume: int = 10

    nurse_call_active: bool = False
    nurse_call_priority: str = "normal"

    audit: list[AuditEntry] = field(default_factory=list)

    def _log(self, actor: str, device: str, action: str, args: dict,
             accepted: bool, reason: str = "") -> None:
        self.audit.append(AuditEntry(
            timestamp=time.time(),
            actor=actor, device=device, action=action,
            args=args, accepted=accepted, reason=reason,
        ))

    def snapshot(self) -> dict[str, Any]:
        return {
            "room_id": self.room_id,
            "bed": {
                "head_angle": self.bed_head_angle,
                "foot_angle": self.bed_foot_angle,
                "clinical_lock": self.bed_clinical_lock,
            },
            "main_light": {
                "on": self.main_light_on,
                "brightness": self.main_light_brightness,
            },
            "reading_light": {
                "on": self.reading_light_on,
                "brightness": self.reading_light_brightness,
            },
            "climate": {
                "temperature_c": self.temperature_c,
                "mode": self.hvac_mode,
            },
            "blinds": {"position": self.blinds_position},
            "tv": {
                "on": self.tv_on,
                "channel": self.tv_channel,
                "volume": self.tv_volume,
            },
            "nurse_call": {
                "active": self.nurse_call_active,
                "priority": self.nurse_call_priority,
            },
        }

    def device_catalog(self) -> list[dict[str, Any]]:
        return [
            {"id": "bed", "type": "adjustable_bed",
             "actions": ["set_bed_head_angle", "set_bed_foot_angle"]},
            {"id": "main_light", "type": "ceiling_light",
             "actions": ["set_light"]},
            {"id": "reading_light", "type": "reading_lamp",
             "actions": ["set_light"]},
            {"id": "climate", "type": "hvac",
             "actions": ["set_temperature", "set_hvac_mode"]},
            {"id": "blinds", "type": "motorized_blinds",
             "actions": ["set_blinds"]},
            {"id": "tv", "type": "smart_tv",
             "actions": ["set_tv_power", "set_tv_channel", "set_tv_volume"]},
            {"id": "nurse_call", "type": "nurse_call_button",
             "actions": ["call_nurse"]},
        ]

    def set_bed_head_angle(self, angle: int, actor: str = "patient") -> tuple[bool, str]:
        if self.bed_clinical_lock and actor not in ("nurse", "doctor"):
            self._log(actor, "bed", "set_bed_head_angle", {"angle": angle},
                      False, "clinical_lock")
            return False, "Bed is clinically locked; only staff can adjust."
        lo, hi = BED_HEAD_RANGE
        if not (lo <= angle <= hi):
            self._log(actor, "bed", "set_bed_head_angle", {"angle": angle},
                      False, "out_of_range")
            return False, f"Angle must be in [{lo},{hi}]."
        self.bed_head_angle = angle
        self._log(actor, "bed", "set_bed_head_angle", {"angle": angle}, True)
        return True, f"Bed head set to {angle}°."

    def set_bed_foot_angle(self, angle: int, actor: str = "patient") -> tuple[bool, str]:
        if self.bed_clinical_lock and actor not in ("nurse", "doctor"):
            self._log(actor, "bed", "set_bed_foot_angle", {"angle": angle},
                      False, "clinical_lock")
            return False, "Bed is clinically locked; only staff can adjust."
        lo, hi = BED_FOOT_RANGE
        if not (lo <= angle <= hi):
            self._log(actor, "bed", "set_bed_foot_angle", {"angle": angle},
                      False, "out_of_range")
            return False, f"Angle must be in [{lo},{hi}]."
        self.bed_foot_angle = angle
        self._log(actor, "bed", "set_bed_foot_angle", {"angle": angle}, True)
        return True, f"Bed foot set to {angle}°."

    def set_light(self, light: str, on: bool | None = None,
                  brightness: int | None = None,
                  actor: str = "patient") -> tuple[bool, str]:
        if light not in ("main_light", "reading_light"):
            self._log(actor, light, "set_light",
                      {"on": on, "brightness": brightness},
                      False, "unknown_device")
            return False, f"Unknown light '{light}'."
        if brightness is not None:
            lo, hi = LIGHT_BRIGHTNESS_RANGE
            if not (lo <= brightness <= hi):
                self._log(actor, light, "set_light",
                          {"on": on, "brightness": brightness},
                          False, "out_of_range")
                return False, f"Brightness must be in [{lo},{hi}]."
        if light == "main_light":
            if on is not None:
                self.main_light_on = on
            if brightness is not None:
                self.main_light_brightness = brightness
        else:
            if on is not None:
                self.reading_light_on = on
            if brightness is not None:
                self.reading_light_brightness = brightness
        self._log(actor, light, "set_light",
                  {"on": on, "brightness": brightness}, True)
        return True, f"{light} updated."

    def set_temperature(self, temperature_c: float,
                        actor: str = "patient") -> tuple[bool, str]:
        lo, hi = TEMPERATURE_RANGE_C
        if not (lo <= temperature_c <= hi):
            self._log(actor, "climate", "set_temperature",
                      {"temperature_c": temperature_c},
                      False, "out_of_range")
            return False, f"Temperature must be in [{lo},{hi}] °C."
        self.temperature_c = float(temperature_c)
        self._log(actor, "climate", "set_temperature",
                  {"temperature_c": temperature_c}, True)
        return True, f"Temperature set to {temperature_c} °C."

    def set_hvac_mode(self, mode: str, actor: str = "patient") -> tuple[bool, str]:
        if mode not in ("auto", "heat", "cool", "off"):
            self._log(actor, "climate", "set_hvac_mode", {"mode": mode},
                      False, "invalid_mode")
            return False, f"HVAC mode must be one of auto|heat|cool|off."
        self.hvac_mode = mode
        self._log(actor, "climate", "set_hvac_mode", {"mode": mode}, True)
        return True, f"HVAC mode set to {mode}."

    def set_blinds(self, position: int, actor: str = "patient") -> tuple[bool, str]:
        lo, hi = BLIND_RANGE
        if not (lo <= position <= hi):
            self._log(actor, "blinds", "set_blinds", {"position": position},
                      False, "out_of_range")
            return False, f"Blind position must be in [{lo},{hi}]."
        self.blinds_position = position
        self._log(actor, "blinds", "set_blinds", {"position": position}, True)
        return True, f"Blinds set to {position}%."

    def set_tv_power(self, on: bool, actor: str = "patient") -> tuple[bool, str]:
        self.tv_on = on
        self._log(actor, "tv", "set_tv_power", {"on": on}, True)
        return True, f"TV {'on' if on else 'off'}."

    def set_tv_channel(self, channel: int, actor: str = "patient") -> tuple[bool, str]:
        if not (1 <= channel <= 999):
            self._log(actor, "tv", "set_tv_channel", {"channel": channel},
                      False, "out_of_range")
            return False, "Channel must be 1..999."
        self.tv_channel = channel
        self._log(actor, "tv", "set_tv_channel", {"channel": channel}, True)
        return True, f"TV channel set to {channel}."

    def set_tv_volume(self, volume: int, actor: str = "patient") -> tuple[bool, str]:
        lo, hi = TV_VOLUME_RANGE
        if not (lo <= volume <= hi):
            self._log(actor, "tv", "set_tv_volume", {"volume": volume},
                      False, "out_of_range")
            return False, f"Volume must be in [{lo},{hi}]."
        self.tv_volume = volume
        self._log(actor, "tv", "set_tv_volume", {"volume": volume}, True)
        return True, f"TV volume set to {volume}."

    def call_nurse(self, priority: str = "normal",
                   actor: str = "patient") -> tuple[bool, str]:
        if priority not in ("normal", "urgent"):
            self._log(actor, "nurse_call", "call_nurse", {"priority": priority},
                      False, "invalid_priority")
            return False, "Priority must be 'normal' or 'urgent'."
        self.nurse_call_active = True
        self.nurse_call_priority = priority
        self._log(actor, "nurse_call", "call_nurse", {"priority": priority}, True)
        return True, f"Nurse call placed ({priority})."

    def clear_nurse_call(self, actor: str = "nurse") -> tuple[bool, str]:
        if actor not in ("nurse", "doctor"):
            self._log(actor, "nurse_call", "clear_nurse_call", {},
                      False, "unauthorized")
            return False, "Only staff can clear a nurse call."
        self.nurse_call_active = False
        self._log(actor, "nurse_call", "clear_nurse_call", {}, True)
        return True, "Nurse call cleared."

    def dispatch(self, action: str, args: dict, actor: str) -> tuple[bool, str]:
        handler = {
            "set_bed_head_angle": lambda a: self.set_bed_head_angle(a["angle"], actor),
            "set_bed_foot_angle": lambda a: self.set_bed_foot_angle(a["angle"], actor),
            "set_light": lambda a: self.set_light(
                a["light"], a.get("on"), a.get("brightness"), actor),
            "set_temperature": lambda a: self.set_temperature(a["temperature_c"], actor),
            "set_hvac_mode": lambda a: self.set_hvac_mode(a["mode"], actor),
            "set_blinds": lambda a: self.set_blinds(a["position"], actor),
            "set_tv_power": lambda a: self.set_tv_power(a["on"], actor),
            "set_tv_channel": lambda a: self.set_tv_channel(a["channel"], actor),
            "set_tv_volume": lambda a: self.set_tv_volume(a["volume"], actor),
            "call_nurse": lambda a: self.call_nurse(a.get("priority", "normal"), actor),
            "clear_nurse_call": lambda a: self.clear_nurse_call(actor),
        }.get(action)
        if handler is None:
            self._log(actor, "unknown", action, args, False, "unknown_action")
            return False, f"Unknown action '{action}'."
        try:
            return handler(args)
        except KeyError as e:
            self._log(actor, "unknown", action, args, False, f"missing_arg:{e}")
            return False, f"Missing required argument: {e}"

    def audit_json(self) -> str:
        return json.dumps([asdict(e) for e in self.audit], indent=2, default=str)
