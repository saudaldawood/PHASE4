"""Voice command transcription using OpenAI Whisper.

Two input modes:
  * file mode: transcribe a .wav / .m4a / .mp3 file.
  * mic mode:  record N seconds from the default microphone, then
               transcribe. Requires the optional `sounddevice` and
               `soundfile` packages.

Output is plain text; pipe it into the existing PatientRoomAgent.handle()
to run the full natural-language control flow on a spoken command.
"""

from __future__ import annotations

import os
import time
from dataclasses import dataclass
from pathlib import Path


@dataclass
class Transcription:
    text: str
    duration_s: float
    latency_s: float
    backend: str
    source: str


def transcribe_file(path: str | Path,
                    model: str = "whisper-1",
                    api_key: str | None = None,
                    language: str = "en") -> Transcription:
    """Send an audio file to OpenAI Whisper and return the transcript."""
    from openai import OpenAI
    p = Path(path)
    if not p.exists():
        raise FileNotFoundError(p)
    client = OpenAI(api_key=api_key or os.environ.get("OPENAI_API_KEY"))
    t0 = time.time()
    with open(p, "rb") as f:
        resp = client.audio.transcriptions.create(
            model=model, file=f, language=language,
        )
    return Transcription(
        text=(resp.text or "").strip(),
        duration_s=0.0,
        latency_s=time.time() - t0,
        backend=f"openai:{model}",
        source=str(p),
    )


def record_microphone(seconds: float = 5.0,
                      sample_rate: int = 16000,
                      out_path: str | Path | None = None) -> Path:
    """Record N seconds of audio from the default mic to a 16 kHz mono WAV.

    Returns the path to the recorded WAV. If `out_path` is None, writes to
    a timestamped file in the system temp dir.
    """
    try:
        import sounddevice as sd
        import soundfile as sf
    except ImportError as e:
        raise RuntimeError(
            "Microphone recording requires the optional packages "
            "`sounddevice` and `soundfile`. Install them with "
            "`pip install sounddevice soundfile`."
        ) from e

    import numpy as np
    if out_path is None:
        out_path = Path(f"/tmp/voice_{int(time.time())}.wav")
    else:
        out_path = Path(out_path)

    frames = int(seconds * sample_rate)
    audio = sd.rec(frames, samplerate=sample_rate, channels=1,
                   dtype="int16")
    sd.wait()
    sf.write(str(out_path), audio, sample_rate, subtype="PCM_16")
    return out_path


def transcribe_microphone(seconds: float = 5.0,
                          model: str = "whisper-1",
                          api_key: str | None = None,
                          language: str = "en") -> Transcription:
    """Record from the mic, then transcribe."""
    wav = record_microphone(seconds=seconds)
    return transcribe_file(wav, model=model, api_key=api_key,
                           language=language)


def synthesize_say(text: str, out_path: str | Path,
                   voice: str = "Samantha") -> Path:
    """macOS-only test helper: render text to a 16 kHz mono WAV using `say`.

    Used to generate reproducible voice-input fixtures without requiring a
    human at a microphone.
    """
    import shutil
    import subprocess
    import tempfile

    out_path = Path(out_path)
    out_path.parent.mkdir(parents=True, exist_ok=True)

    if not shutil.which("say") or not shutil.which("afconvert"):
        raise RuntimeError(
            "synthesize_say requires macOS `say` and `afconvert`.")

    with tempfile.TemporaryDirectory() as td:
        aiff = Path(td) / "out.aiff"
        subprocess.check_call(
            ["say", "-v", voice, "-o", str(aiff), text])
        subprocess.check_call(
            ["afconvert", str(aiff), str(out_path),
             "-f", "WAVE", "-d", "LEI16@16000", "-c", "1"])
    return out_path
