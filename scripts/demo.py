"""Interactive demo. Slash commands: /state /audit /role <r> /voice [secs] /file <path> /quit."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.llm_client import make_client            # noqa: E402
from src.pipeline import PatientRoomAgent          # noqa: E402
from src.room import PatientRoom                   # noqa: E402
from src.voice import (                            # noqa: E402
    transcribe_file, transcribe_microphone,
)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["auto", "openai", "mock"],
                    default="auto")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--actor", default="patient",
                    choices=["patient", "nurse", "doctor", "visitor"])
    args = ap.parse_args()

    llm = make_client(prefer=args.backend, model=args.model)
    room = PatientRoom()
    agent = PatientRoomAgent(room, llm, default_actor=args.actor)

    backend = getattr(llm, "model", None) or getattr(llm, "backend_name", "?")
    print(f"== Patient Room Demo ==  actor={args.actor}  backend={backend}")
    print("Type a command. Slash commands:")
    print("  /state                  show current room state")
    print("  /audit                  show audit log")
    print("  /role <role>            switch actor")
    print("  /voice [seconds]        record from mic and transcribe")
    print("  /file <path>            transcribe an audio file")
    print("  /quit                   exit")
    while True:
        try:
            line = input(f"[{agent.default_actor}] > ").strip()
        except (EOFError, KeyboardInterrupt):
            print()
            return
        if not line:
            continue
        if line == "/quit":
            return
        if line == "/state":
            print(json.dumps(room.snapshot(), indent=2))
            continue
        if line == "/audit":
            print(room.audit_json())
            continue
        if line.startswith("/role "):
            agent.default_actor = line.split(maxsplit=1)[1].strip()
            print(f"actor -> {agent.default_actor}")
            continue
        if line.startswith("/voice"):
            parts = line.split()
            secs = float(parts[1]) if len(parts) > 1 else 5.0
            print(f"  recording {secs:.1f} s ...")
            try:
                tr = transcribe_microphone(seconds=secs)
            except Exception as exc:
                print(f"  voice error: {exc}")
                continue
            print(f"  heard: {tr.text!r}  ({tr.latency_s*1000:.0f} ms)")
            line = tr.text
            if not line:
                continue
        elif line.startswith("/file "):
            path = line.split(maxsplit=1)[1].strip()
            try:
                tr = transcribe_file(path)
            except Exception as exc:
                print(f"  voice error: {exc}")
                continue
            print(f"  heard: {tr.text!r}  ({tr.latency_s*1000:.0f} ms)")
            line = tr.text
            if not line:
                continue
        result = agent.handle(line)
        print(f"  rationale: {result.rationale}")
        for ex in result.executions:
            ok = "OK" if ex["ok"] else "FAIL"
            print(f"  [{ok}] {ex['name']} {ex['args']}: {ex['message']}")
        for r in result.rejected:
            print(f"  [REJ] {r['name']} {r['args']}: {r['reason']}")
        for p in result.needs_confirmation:
            print(f"  [PENDING] {p['name']} {p['args']}  (say 'yes' to confirm)")
        print(f"  ({result.total_latency_s*1000:.0f} ms; backend={result.backend})")


if __name__ == "__main__":
    main()
