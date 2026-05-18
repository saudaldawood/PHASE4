"""Voice path tests.

Most tests run offline using stubs. One integration test hits the
real OpenAI Whisper API; it is skipped automatically when there is no
OPENAI_API_KEY in the environment.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.llm_client import MockLLM                     # noqa: E402
from src.pipeline import PatientRoomAgent              # noqa: E402
from src.room import PatientRoom                       # noqa: E402
from src.voice import (                                # noqa: E402
    Transcription, synthesize_say, transcribe_file,
)


SAMPLE_DIR = ROOT / "data" / "audio"


def test_transcription_dataclass_round_trip():
    t = Transcription(text="hi", duration_s=1.0, latency_s=0.5,
                      backend="x", source="y")
    assert t.text == "hi" and t.backend == "x"


def test_voice_pipeline_with_fixed_transcript():
    """Feed a known transcript straight to the pipeline (no API call)."""
    room = PatientRoom()
    agent = PatientRoomAgent(room, MockLLM(), default_actor="patient")
    out = agent.handle("I am cold and the glare is hurting my eyes.")
    names = sorted(c["name"] for c in out.plan)
    assert "set_temperature" in names
    assert "set_blinds" in names


def test_synthesize_say_writes_file(tmp_path):
    """Verify the macOS test-fixture helper produces a real WAV."""
    import shutil
    if not shutil.which("say"):
        pytest.skip("`say` not available (non-macOS)")
    out = tmp_path / "out.wav"
    synthesize_say("turn off the light", out)
    assert out.exists() and out.stat().st_size > 1024


@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"),
                    reason="needs OPENAI_API_KEY")
@pytest.mark.skipif(not (SAMPLE_DIR / "sample_lights_off.wav").exists(),
                    reason="audio fixture missing")
def test_whisper_transcribes_sample_clip():
    """Live integration test: send a sample clip to OpenAI Whisper."""
    tr = transcribe_file(SAMPLE_DIR / "sample_lights_off.wav")
    assert "light" in tr.text.lower()
    assert tr.latency_s > 0
