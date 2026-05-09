"""Function-calling tool schemas for the patient room."""

from __future__ import annotations

TOOLS = [
    {
        "type": "function",
        "function": {
            "name": "set_bed_head_angle",
            "description": "Raise or lower the head end of the bed. Angle in degrees, 0-60.",
            "parameters": {
                "type": "object",
                "properties": {"angle": {"type": "integer", "minimum": 0, "maximum": 60}},
                "required": ["angle"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_bed_foot_angle",
            "description": "Raise or lower the foot end of the bed. Angle in degrees, 0-30.",
            "parameters": {
                "type": "object",
                "properties": {"angle": {"type": "integer", "minimum": 0, "maximum": 30}},
                "required": ["angle"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_light",
            "description": "Turn a light on/off and/or set brightness 0-100.",
            "parameters": {
                "type": "object",
                "properties": {
                    "light": {"type": "string", "enum": ["main_light", "reading_light"]},
                    "on": {"type": "boolean"},
                    "brightness": {"type": "integer", "minimum": 0, "maximum": 100},
                },
                "required": ["light"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_temperature",
            "description": "Set room target temperature in Celsius (18-26).",
            "parameters": {
                "type": "object",
                "properties": {"temperature_c": {"type": "number", "minimum": 18, "maximum": 26}},
                "required": ["temperature_c"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_hvac_mode",
            "description": "Set HVAC mode: auto, heat, cool, or off.",
            "parameters": {
                "type": "object",
                "properties": {
                    "mode": {"type": "string", "enum": ["auto", "heat", "cool", "off"]},
                },
                "required": ["mode"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_blinds",
            "description": "Set window blind position (0=closed, 100=open).",
            "parameters": {
                "type": "object",
                "properties": {"position": {"type": "integer", "minimum": 0, "maximum": 100}},
                "required": ["position"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_tv_power",
            "description": "Turn the TV on or off.",
            "parameters": {
                "type": "object",
                "properties": {"on": {"type": "boolean"}},
                "required": ["on"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_tv_channel",
            "description": "Set TV channel (1-999).",
            "parameters": {
                "type": "object",
                "properties": {"channel": {"type": "integer", "minimum": 1, "maximum": 999}},
                "required": ["channel"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "set_tv_volume",
            "description": "Set TV volume (0-30).",
            "parameters": {
                "type": "object",
                "properties": {"volume": {"type": "integer", "minimum": 0, "maximum": 30}},
                "required": ["volume"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "call_nurse",
            "description": "Place a nurse call. Priority 'normal' or 'urgent'.",
            "parameters": {
                "type": "object",
                "properties": {
                    "priority": {"type": "string", "enum": ["normal", "urgent"]},
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "clear_nurse_call",
            "description": "Clear the active nurse call (staff only).",
            "parameters": {"type": "object", "properties": {}, "required": []},
        },
    },
]


def tool_names() -> set[str]:
    return {t["function"]["name"] for t in TOOLS}
