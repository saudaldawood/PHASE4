"""Run PRC-Bench across configurations and save results."""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from src.benchmark import (                          # noqa: E402
    load_benchmark, run_pipeline_config, run_single_prompt,
    run_intent_classifier, summary_to_dict,
)
from src.llm_client import make_client, MockLLM      # noqa: E402


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--backend", choices=["auto", "openai", "mock"],
                    default="auto")
    ap.add_argument("--model", default="gpt-4o-mini")
    ap.add_argument("--configs", nargs="+",
                    default=["intent_classifier", "single_prompt", "pipeline"])
    ap.add_argument("--out", default="results/benchmark_results.json")
    args = ap.parse_args()

    items = load_benchmark()
    llm = make_client(prefer=args.backend, model=args.model)

    summaries = []
    for cfg in args.configs:
        print(f"\n=== Running: {cfg} ===")
        if cfg == "intent_classifier":
            summary = run_intent_classifier(items)
        elif cfg == "single_prompt":
            baseline_llm = (MockLLM(safe_mode=False)
                            if isinstance(llm, MockLLM) else llm)
            summary = run_single_prompt(items, baseline_llm)
        elif cfg == "pipeline":
            summary = run_pipeline_config(items, llm)
        else:
            print(f"Skipping unknown config: {cfg}")
            continue

        print(f"  n                   = {summary.n}")
        print(f"  overall_accuracy    = {summary.overall_accuracy:.3f}")
        print(f"  refusal_f1          = {summary.refusal_f1:.3f}")
        print(f"  hallucination_rate  = {summary.hallucination_rate:.3f}")
        print(f"  mean_latency_s      = {summary.mean_latency_s:.4f}")
        print(f"  p95_latency_s       = {summary.p95_latency_s:.4f}")
        print(f"  by_category:")
        for cat, m in summary.by_category.items():
            print(f"    {cat:14s} acc={m['accuracy']:.3f} "
                  f"halluc={m['hallucination_rate']:.3f} "
                  f"refusal_ok={m['refusal_correct']:.3f}")
        summaries.append(summary_to_dict(summary))

    out_path = ROOT / args.out
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with open(out_path, "w") as f:
        json.dump({"summaries": summaries}, f, indent=2, default=str)
    print(f"\nWrote {out_path}")


if __name__ == "__main__":
    main()
