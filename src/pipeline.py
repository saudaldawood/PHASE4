"""Five-stage agent pipeline: clarify, filter, plan, safety, execute."""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from typing import Any

from .llm_client import LLMResponse
from .room import PatientRoom
from .safety import validate
from .tools import TOOLS, tool_names


SYSTEM_PROMPT = """You are the natural-language controller for a hospital \
patient room. You help users (patients, staff, visitors) operate the \
in-room comfort and entertainment devices by translating their request \
into one or more structured tool calls drawn ONLY from the provided tools.

What patients ARE allowed to do (call the tool, do not refuse):
  - Adjust their own bed angle (head 0-60, foot 0-30).
  - Turn lights on/off and set brightness.
  - Set temperature (18-26 C) and HVAC mode.
  - Open/close blinds.
  - Turn the TV on/off, change channel, set volume.
  - Place a nurse call.

What patients are NOT allowed to do:
  - Clear an active nurse call (staff only).
  - Adjust medications, IV pumps, ventilators (out of scope: NO TOOL EXISTS).
  - Override the clinical bed lock when set.

Visitors may operate lights, blinds, TV, and call a nurse. They MUST NOT \
move the bed. Temperature and HVAC changes by visitors require confirmation.

Rules:
  - NEVER invent a tool name. Only use tools from the provided tool list.
  - NEVER set values outside the ranges declared in the tool schema.
  - For ambiguous comfort requests ("make it cozy", "I'm uncomfortable"), \
PICK a small combination of plausible tool calls (typically temperature + \
lights, possibly blinds). Do not refuse.
  - For requests that have no matching tool (medication, doors, windows, \
pizza), respond in plain text WITHOUT any tool calls.
  - For requests that exceed declared ranges (channel 5000, temperature 50), \
respond in plain text WITHOUT any tool calls.
  - When the user's role permits the action, ALWAYS call the appropriate \
tool. Do not punt to staff for routine comfort actions a patient can do."""


@dataclass
class StageTrace:
    name: str
    duration_s: float
    note: str = ""
    payload: dict | None = None


@dataclass
class PipelineResult:
    utterance: str
    actor: str
    plan: list[dict]
    rejected: list[dict]
    executions: list[dict]
    rationale: str
    needs_confirmation: list[dict]
    stage_traces: list[StageTrace] = field(default_factory=list)
    total_latency_s: float = 0.0
    backend: str = ""


class PatientRoomAgent:
    def __init__(self, room: PatientRoom, llm, default_actor: str = "patient"):
        self.room = room
        self.llm = llm
        self.default_actor = default_actor

    def _clarify(self, utterance: str) -> tuple[str, StageTrace]:
        t0 = time.time()
        cleaned = " ".join(utterance.strip().split())
        for filler in ("hey ", "ok ", "please ", "could you "):
            if cleaned.lower().startswith(filler):
                cleaned = cleaned[len(filler):]
        return cleaned, StageTrace("clarify", time.time() - t0,
                                   note=f"cleaned={cleaned!r}")

    def _filter(self, utterance: str) -> tuple[list[dict], StageTrace]:
        t0 = time.time()
        catalog = self.room.device_catalog()
        u = utterance.lower()
        keep_all = any(w in u for w in
                       ["cozy", "comfortable", "settle", "comfy"])
        if keep_all:
            kept = catalog
        else:
            keywords = {
                "bed": ["bed", "head", "feet", "incline", "sit up", "lie flat"],
                "main_light": ["light", "lamp", "dim", "bright", "dark"],
                "reading_light": ["reading", "book"],
                "climate": ["temperature", "warm", "cold", "hot", "cool",
                            "ac", "heater", "freezing"],
                "blinds": ["blind", "curtain", "window", "glare", "sun"],
                "tv": ["tv", "channel", "volume", "louder", "quieter", "mute"],
                "nurse_call": ["nurse", "help", "emergency", "urgent",
                               "i need someone"],
            }
            kept = [d for d in catalog
                    if any(k in u for k in keywords.get(d["id"], []))]
            if not kept:
                kept = catalog
        return kept, StageTrace("filter", time.time() - t0,
                                note=f"devices={len(kept)}")

    def _plan(self, utterance: str, devices: list[dict]
              ) -> tuple[LLMResponse, StageTrace]:
        t0 = time.time()
        snap = self.room.snapshot()
        if not snap["bed"]["clinical_lock"]:
            snap["bed"].pop("clinical_lock", None)
        user_msg = (
            f"Current room state:\n{snap}\n\n"
            f"Available devices: {devices}\n\n"
            f"User role: {self.default_actor}\n"
            f"User says: {utterance!r}"
        )
        resp = self.llm.complete(SYSTEM_PROMPT, user_msg, tools=TOOLS)
        return resp, StageTrace("plan", time.time() - t0,
                                note=f"backend={resp.backend} "
                                     f"calls={len(resp.tool_calls)}")

    def _safety(self, calls: list[dict]
                ) -> tuple[list[dict], list[dict], list[dict], StageTrace]:
        t0 = time.time()
        kept, rejected, pending = [], [], []
        valid_names = tool_names()
        for call in calls:
            name = call["name"]
            args = call.get("arguments", {})
            if name not in valid_names:
                rejected.append({"name": name, "args": args,
                                 "reason": "hallucinated_tool"})
                continue
            res = validate(name, args, self.default_actor)
            if not res.accepted:
                rejected.append({"name": name, "args": args,
                                 "reason": res.reason})
            elif res.needs_confirmation:
                pending.append({"name": name, "args": args})
            else:
                kept.append({"name": name, "args": args})
        return kept, rejected, pending, StageTrace(
            "safety", time.time() - t0,
            note=f"kept={len(kept)} rejected={len(rejected)} "
                 f"pending={len(pending)}")

    def _execute(self, calls: list[dict]) -> tuple[list[dict], StageTrace]:
        t0 = time.time()
        out = []
        for c in calls:
            ok, msg = self.room.dispatch(c["name"], c["args"], self.default_actor)
            out.append({"name": c["name"], "args": c["args"],
                        "ok": ok, "message": msg})
        return out, StageTrace("execute", time.time() - t0,
                               note=f"executed={len(out)}")

    def handle(self, utterance: str) -> PipelineResult:
        traces: list[StageTrace] = []
        t_start = time.time()

        cleaned, t = self._clarify(utterance)
        traces.append(t)
        devices, t = self._filter(cleaned)
        traces.append(t)
        llm_resp, t = self._plan(cleaned, devices)
        traces.append(t)
        kept, rejected, pending, t = self._safety(llm_resp.tool_calls)
        traces.append(t)
        executions, t = self._execute(kept)
        traces.append(t)

        rationale_parts = []
        if llm_resp.text:
            rationale_parts.append(llm_resp.text.strip())
        if pending:
            rationale_parts.append(
                f"Awaiting confirmation for {len(pending)} action(s).")
        if rejected:
            rationale_parts.append(
                f"Rejected {len(rejected)} unsafe/invalid action(s).")
        if not rationale_parts:
            rationale_parts.append(
                f"Executed {len(executions)} action(s).")
        rationale = " ".join(rationale_parts)

        return PipelineResult(
            utterance=utterance,
            actor=self.default_actor,
            plan=kept,
            rejected=rejected,
            executions=executions,
            rationale=rationale,
            needs_confirmation=pending,
            stage_traces=traces,
            total_latency_s=time.time() - t_start,
            backend=llm_resp.backend,
        )
