"""Smoke tests."""

from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.llm_client import MockLLM
from src.pipeline import PatientRoomAgent
from src.room import PatientRoom
from src.safety import validate


def test_room_set_temperature_valid():
    r = PatientRoom()
    ok, _ = r.set_temperature(22.0)
    assert ok and r.temperature_c == 22.0


def test_room_set_temperature_out_of_range_rejected():
    r = PatientRoom()
    ok, _ = r.set_temperature(50.0)
    assert not ok and r.temperature_c == 22.0  # unchanged


def test_room_visitor_cannot_move_bed_via_safety_layer():
    res = validate("set_bed_head_angle", {"angle": 30}, "visitor")
    assert not res.accepted
    assert "forbidden_for_role" in res.reason


def test_pipeline_multi_device_command():
    room = PatientRoom()
    agent = PatientRoomAgent(room, MockLLM(), default_actor="patient")
    out = agent.handle("I'm cold and the glare is hurting my eyes.")
    names = sorted(c["name"] for c in out.plan)
    assert "set_temperature" in names
    assert "set_blinds" in names


def test_pipeline_refuses_dangerous():
    room = PatientRoom()
    agent = PatientRoomAgent(room, MockLLM(), default_actor="patient")
    out = agent.handle("Increase my morphine dose.")
    assert out.plan == []


def test_pipeline_rejects_out_of_range():
    room = PatientRoom()
    agent = PatientRoomAgent(room, MockLLM(), default_actor="patient")
    out = agent.handle("Set the temperature to 50 degrees.")
    # The mock refuses outright. Either way the room must not be changed.
    assert room.temperature_c == 22.0


def test_audit_log_records_rejection():
    r = PatientRoom()
    r.set_temperature(99)
    assert any(not e.accepted for e in r.audit)
