"""LLM client: OpenAI Chat Completions backend with deterministic mock fallback."""

from __future__ import annotations

import json
import os
import re
import time
from dataclasses import dataclass
from typing import Any


@dataclass
class LLMResponse:
    text: str
    tool_calls: list[dict]
    raw_latency_s: float
    backend: str


class OpenAIClient:
    def __init__(self, model: str = "gpt-4o-mini", api_key: str | None = None):
        try:
            from openai import OpenAI  # noqa: F401
        except ImportError as e:
            raise RuntimeError(
                "openai package is not installed. `pip install openai`"
            ) from e
        from openai import OpenAI
        self._client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
        self.model = model

    def complete(self, system: str, user: str,
                 tools: list[dict] | None = None,
                 force_tools: bool = False) -> LLMResponse:
        t0 = time.time()
        kwargs: dict[str, Any] = {
            "model": self.model,
            "messages": [
                {"role": "system", "content": system},
                {"role": "user", "content": user},
            ],
            "temperature": 0.0,
        }
        if tools:
            kwargs["tools"] = tools
            if force_tools:
                kwargs["tool_choice"] = "required"
        resp = self._client.chat.completions.create(**kwargs)
        msg = resp.choices[0].message
        tool_calls = []
        for tc in (getattr(msg, "tool_calls", None) or []):
            try:
                args = json.loads(tc.function.arguments or "{}")
            except json.JSONDecodeError:
                args = {}
            tool_calls.append({"name": tc.function.name, "arguments": args})
        return LLMResponse(
            text=msg.content or "",
            tool_calls=tool_calls,
            raw_latency_s=time.time() - t0,
            backend=f"openai:{self.model}",
        )


class MockLLM:
    """Deterministic regex-based planner. safe_mode=False bypasses refusals."""

    backend_name = "mock"

    def __init__(self, safe_mode: bool = True):
        self.safe_mode = safe_mode

    def complete(self, system: str, user: str,
                 tools: list[dict] | None = None,
                 force_tools: bool = False) -> LLMResponse:
        t0 = time.time()
        m = re.search(r"User says:\s*['\"]?(.+?)['\"]?\s*$", user, re.DOTALL)
        if not m:
            m = re.search(r"User\s*\([^)]*\):\s*(.+?)\s*$", user, re.DOTALL)
        utterance = m.group(1).strip() if m else user
        text, calls = _mock_plan(utterance, safe_mode=self.safe_mode)
        time.sleep(0.005)
        return LLMResponse(
            text=text,
            tool_calls=calls,
            raw_latency_s=time.time() - t0,
            backend=f"mock{'' if self.safe_mode else '-unsafe'}",
        )


def _mock_plan(utterance: str,
               safe_mode: bool = True) -> tuple[str, list[dict]]:
    u = utterance.lower().strip()
    calls: list[dict] = []

    if any(w in u for w in ["iv pump", "morphine", "medication dose",
                            "increase the drip", "raise the dose"]):
        if safe_mode:
            return ("Refusing: medication/IV control is out of scope.", [])
        return ("Attempting medication adjustment via available tools.",
                [{"name": "set_temperature", "arguments": {"temperature_c": 22.0}}])

    if "nurse" in u and ("call" in u or "help" in u or "i need" in u
                         or "emergency" in u or "urgent" in u):
        priority = "urgent" if any(w in u for w in
            ["urgent", "emergency", "can't breathe", "help me"]) else "normal"
        calls.append({"name": "call_nurse", "arguments": {"priority": priority}})
        return ("User requested nurse assistance.", calls)

    if any(w in u for w in ["cozy", "comfortable", "comfy", "settle in"]):
        calls.extend([
            {"name": "set_temperature", "arguments": {"temperature_c": 23.0}},
            {"name": "set_light", "arguments":
                {"light": "main_light", "brightness": 30, "on": True}},
            {"name": "set_blinds", "arguments": {"position": 20}},
        ])
        return ("Cozy preset: warm, dim, blinds mostly down.", calls)

    m = re.search(r"(\d{2})\s*°?\s*c", u) or re.search(r"to (\d{2}) degrees", u)
    if m:
        try:
            t = float(m.group(1))
            calls.append({"name": "set_temperature",
                          "arguments": {"temperature_c": t}})
        except ValueError:
            pass
    if "warmer" in u or "cold" in u or "freezing" in u or "i'm cold" in u:
        calls.append({"name": "set_temperature", "arguments": {"temperature_c": 24.0}})
    if "cooler" in u or "hot" in u or "i'm hot" in u or "too warm" in u:
        calls.append({"name": "set_temperature", "arguments": {"temperature_c": 20.0}})

    if "dim" in u or "darker" in u:
        calls.append({"name": "set_light", "arguments":
            {"light": "main_light", "brightness": 20, "on": True}})
    if "lights off" in u or "turn off the light" in u or "lights out" in u:
        calls.append({"name": "set_light", "arguments":
            {"light": "main_light", "on": False}})
    if "lights on" in u or "turn on the light" in u or "brighter" in u:
        calls.append({"name": "set_light", "arguments":
            {"light": "main_light", "on": True, "brightness": 80}})
    if "reading" in u and ("light" in u or "lamp" in u):
        calls.append({"name": "set_light", "arguments":
            {"light": "reading_light", "on": True, "brightness": 70}})

    if "glare" in u or "sun in my eyes" in u or "light hurting" in u or "hallway" in u:
        calls.append({"name": "set_blinds", "arguments": {"position": 10}})

    if "raise" in u and "head" in u or "sit up" in u or "incline" in u:
        calls.append({"name": "set_bed_head_angle", "arguments": {"angle": 35}})
    if "lower" in u and "head" in u or "lie flat" in u or "lay flat" in u:
        calls.append({"name": "set_bed_head_angle", "arguments": {"angle": 0}})
    if "raise" in u and "feet" in u or "elevate my feet" in u:
        calls.append({"name": "set_bed_foot_angle", "arguments": {"angle": 20}})

    if "close the blinds" in u or "shut the blinds" in u or "blinds down" in u:
        calls.append({"name": "set_blinds", "arguments": {"position": 0}})
    if "open the blinds" in u or "blinds up" in u:
        calls.append({"name": "set_blinds", "arguments": {"position": 100}})

    if "turn on the tv" in u or "switch on tv" in u or "tv on" in u:
        calls.append({"name": "set_tv_power", "arguments": {"on": True}})
    if "turn off the tv" in u or "tv off" in u:
        calls.append({"name": "set_tv_power", "arguments": {"on": False}})
    m = re.search(r"channel (\d{1,3})", u)
    if m:
        calls.append({"name": "set_tv_channel",
                      "arguments": {"channel": int(m.group(1))}})
    if "volume up" in u or "louder" in u:
        calls.append({"name": "set_tv_volume", "arguments": {"volume": 20}})
    if "volume down" in u or "quieter" in u or "mute" in u:
        calls.append({"name": "set_tv_volume", "arguments": {"volume": 5}})

    # Direct out-of-range temperatures
    m_temp = re.search(r"(\d{2,3})\s*degrees?", u)
    if m_temp:
        try:
            tval = float(m_temp.group(1))
            if tval > 26 or tval < 18:
                if safe_mode:
                    return ("Requested temperature out of safe range; refusing.",
                            [])
                # Unsafe baseline: dutifully tries the out-of-range value.
                calls.append({"name": "set_temperature",
                              "arguments": {"temperature_c": tval}})
        except ValueError:
            pass
    # Out-of-range bed angles
    m_bed = re.search(r"(\d{2,3})\s*degrees? .*bed|bed .*?(\d{2,3})\s*degrees?", u)
    if m_bed:
        try:
            angle = int(m_bed.group(1) or m_bed.group(2))
            if angle > 60:
                if safe_mode:
                    return ("Bed angle exceeds safe maximum; refusing.", [])
                calls.append({"name": "set_bed_head_angle",
                              "arguments": {"angle": angle}})
        except (ValueError, TypeError):
            pass
    m_chan = re.search(r"channel (\d{4,})", u)
    if m_chan:
        ch = int(m_chan.group(1))
        if safe_mode:
            return ("Channel out of range; refusing.", [])
        calls.append({"name": "set_tv_channel", "arguments": {"channel": ch}})
    if "volume" in u and "100" in u:
        if safe_mode:
            return ("Volume out of range; refusing.", [])
        calls.append({"name": "set_tv_volume", "arguments": {"volume": 100}})

    # Out-of-scope nouns (door/window/coffee/pizza)
    if any(w in u for w in ["window", "door", "coffee", "pizza", "lock"]):
        if safe_mode:
            return ("No tool available for that request; refusing.", [])
        # Unsafe: hallucinate a vaguely related tool name.
        calls.append({"name": "open_window", "arguments": {}})

    rationale = ("Mock-LLM mapped utterance to "
                 f"{len(calls)} tool calls.") if calls \
                else "Mock-LLM could not map utterance to any known tool."
    return (rationale, calls)



def make_client(prefer: str = "auto", model: str = "gpt-4o-mini"):
    """Return an OpenAI client if a key is available, else MockLLM.

    `prefer` can be "openai", "mock", or "auto".
    """
    if prefer == "mock":
        return MockLLM()
    if prefer == "openai":
        return OpenAIClient(model=model)
    if os.environ.get("OPENAI_API_KEY"):
        try:
            return OpenAIClient(model=model)
        except RuntimeError:
            pass
    return MockLLM()
