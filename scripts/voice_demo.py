"""Voice demo: speak a command, see the room react.

Examples:
    # transcribe a .wav file and run it through the pipeline
    python scripts/voice_demo.py --file data/audio/sample_cold_glare.wav

    # record 5 s from the mic, transcribe, and run it
    python scripts/voice_demo.py --mic --seconds 5

    # generate a test clip via macOS `say` and run it
    python scripts/voice_demo.py --say "make it warmer and dim the lights"
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.llm_client import make_client                # noqa: E402
from src.pipeline import PatientRoomAgent              # noqa: E402
from src.room import PatientRoom                       # noqa: E402
from src.voice import (                                # noqa: E402
    transcribe_file, transcribe_microphone, synthesize_say,
)


def main():
    ap = argparse.ArgumentParser()
    src_group = ap.add_mutually_exclusive_group(required=True)
    src_group.add_argument("--file", help="path to a .wav/.m4a/.mp3 file")
    src_group.add_argument("--mic", action="store_true",
                           help="record from microphone")
    src_group.add_argument("--say", help="render this string with macOS "
                                         "`say` and use it as input")
    ap.add_argument("--seconds", type=float, default=5.0,
                    help="mic record length (default 5 s)")
    ap.add_argument("--actor", default="patient",
                    choices=["patient", "nurse", "doctor", "visitor"])
    ap.add_argument("--backend", default="auto",
                    choices=["auto", "openai", "mock"])
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--whisper-model", default="whisper-1")
    args = ap.parse_args()

    if args.file:
        print(f"[1/3] transcribing {args.file} ...")
        tr = transcribe_file(args.file, model=args.whisper_model)
    elif args.mic:
        print(f"[1/3] recording {args.seconds:.1f} s from the mic ...")
        tr = transcribe_microphone(seconds=args.seconds,
                                   model=args.whisper_model)
    else:
        out = Path("/tmp/voice_say.wav")
        print(f"[1/3] synthesizing via `say`, then transcribing ...")
        synthesize_say(args.say, out)
        tr = transcribe_file(out, model=args.whisper_model)
    print(f"      transcript: {tr.text!r}")
    print(f"      whisper latency: {tr.latency_s*1000:.0f} ms "
          f"(backend={tr.backend})")

    print(f"[2/3] planning + safety + execute (actor={args.actor}) ...")
    llm = make_client(prefer=args.backend, model=args.model)
    room = PatientRoom()
    agent = PatientRoomAgent(room, llm, default_actor=args.actor)
    result = agent.handle(tr.text)

    print(f"      rationale: {result.rationale}")
    for ex in result.executions:
        flag = "OK" if ex["ok"] else "FAIL"
        print(f"      [{flag}] {ex['name']} {ex['args']}: {ex['message']}")
    for rej in result.rejected:
        print(f"      [REJ] {rej['name']} {rej['args']}: {rej['reason']}")
    print(f"      pipeline latency: {result.total_latency_s*1000:.0f} ms")

    print(f"[3/3] resulting room state:")
    print(json.dumps(room.snapshot(), indent=2))


if __name__ == "__main__":
    main()
