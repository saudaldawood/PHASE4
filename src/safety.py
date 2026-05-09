"""Per-actor permission matrix and argument validation."""

from __future__ import annotations

from dataclasses import dataclass

from .tools import tool_names


# True = allow, False = deny, "confirm" = allow but require user confirmation.
PERMISSIONS: dict[str, dict[str, bool | str]] = {
    "patient": {
        "set_bed_head_angle": True,
        "set_bed_foot_angle": True,
        "set_light": True,
        "set_temperature": True,
        "set_hvac_mode": True,
        "set_blinds": True,
        "set_tv_power": True,
        "set_tv_channel": True,
        "set_tv_volume": True,
        "call_nurse": True,
        "clear_nurse_call": False,
    },
    "visitor": {
        "set_bed_head_angle": False,
        "set_bed_foot_angle": False,
        "set_light": True,
        "set_temperature": "confirm",
        "set_hvac_mode": "confirm",
        "set_blinds": True,
        "set_tv_power": True,
        "set_tv_channel": True,
        "set_tv_volume": True,
        "call_nurse": True,
        "clear_nurse_call": False,
    },
    "nurse": {name: True for name in tool_names()},
    "doctor": {name: True for name in tool_names()},
}


@dataclass
class ValidationResult:
    accepted: bool
    needs_confirmation: bool
    reason: str = ""


def validate(action: str, args: dict, actor: str) -> ValidationResult:
    if action not in tool_names():
        return ValidationResult(False, False, f"hallucinated_tool:{action}")
    role_perms = PERMISSIONS.get(actor)
    if role_perms is None:
        return ValidationResult(False, False, f"unknown_role:{actor}")
    perm = role_perms.get(action, False)
    if perm is False:
        return ValidationResult(False, False, f"forbidden_for_role:{actor}:{action}")
    err = _arg_check(action, args)
    if err:
        return ValidationResult(False, False, err)
    if perm == "confirm":
        return ValidationResult(True, True, "needs_confirmation")
    return ValidationResult(True, False)


def _arg_check(action: str, args: dict) -> str:
    if action == "set_bed_head_angle":
        a = args.get("angle")
        if not isinstance(a, int) or not 0 <= a <= 60:
            return "bad_arg:angle"
    elif action == "set_bed_foot_angle":
        a = args.get("angle")
        if not isinstance(a, int) or not 0 <= a <= 30:
            return "bad_arg:angle"
    elif action == "set_light":
        if args.get("light") not in ("main_light", "reading_light"):
            return "bad_arg:light"
        b = args.get("brightness")
        if b is not None and (not isinstance(b, int) or not 0 <= b <= 100):
            return "bad_arg:brightness"
    elif action == "set_temperature":
        t = args.get("temperature_c")
        if not isinstance(t, (int, float)) or not 18 <= t <= 26:
            return "bad_arg:temperature_c"
    elif action == "set_hvac_mode":
        if args.get("mode") not in ("auto", "heat", "cool", "off"):
            return "bad_arg:mode"
    elif action == "set_blinds":
        p = args.get("position")
        if not isinstance(p, int) or not 0 <= p <= 100:
            return "bad_arg:position"
    elif action == "set_tv_channel":
        c = args.get("channel")
        if not isinstance(c, int) or not 1 <= c <= 999:
            return "bad_arg:channel"
    elif action == "set_tv_volume":
        v = args.get("volume")
        if not isinstance(v, int) or not 0 <= v <= 30:
            return "bad_arg:volume"
    elif action == "call_nurse":
        p = args.get("priority", "normal")
        if p not in ("normal", "urgent"):
            return "bad_arg:priority"
    return ""
