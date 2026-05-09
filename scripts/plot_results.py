"""Generate paper figures from results/benchmark_results.json."""

from __future__ import annotations

import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
RESULTS = ROOT / "results" / "benchmark_results.json"
FIG_DIR = ROOT / "results" / "figures"
FIG_DIR.mkdir(parents=True, exist_ok=True)


def _load():
    with open(RESULTS) as f:
        return json.load(f)["summaries"]


def _ascii_bar(label: str, value: float, max_v: float, width: int = 30) -> str:
    n = int((value / max_v) * width) if max_v else 0
    return f"{label:24s} | {'#' * n}{' ' * (width - n)} {value:.3f}"


def main():
    summaries = _load()
    try:
        import matplotlib  # noqa: F401
        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
        have_mpl = True
    except ImportError:
        have_mpl = False

    configs = [s["config"] for s in summaries]
    overall = [s["overall_accuracy"] for s in summaries]
    halluc  = [s["hallucination_rate"] for s in summaries]
    f1      = [s["refusal_f1"] for s in summaries]
    p95     = [s["p95_latency_s"] for s in summaries]

    print("=== Overall accuracy ===")
    for c, v in zip(configs, overall):
        print(_ascii_bar(c, v, 1.0))
    print("\n=== Refusal F1 ===")
    for c, v in zip(configs, f1):
        print(_ascii_bar(c, v, 1.0))
    print("\n=== Hallucination rate ===")
    for c, v in zip(configs, halluc):
        print(_ascii_bar(c, v, max(halluc) or 1.0))
    print("\n=== p95 latency (s) ===")
    for c, v in zip(configs, p95):
        print(_ascii_bar(c, v, max(p95) or 1.0))

    if not have_mpl:
        print("\nmatplotlib not installed; ASCII charts only. Run "
              "`pip install matplotlib` to emit PNG figures.")
        return

    import numpy as np
    x = np.arange(len(configs))
    fig, ax = plt.subplots(figsize=(7, 3.5))
    w = 0.27
    ax.bar(x - w, overall, w, label="Overall accuracy")
    ax.bar(x,     f1,      w, label="Refusal F1")
    ax.bar(x + w, halluc,  w, label="Hallucination rate")
    ax.set_xticks(x); ax.set_xticklabels(configs)
    ax.set_ylim(0, 1.05)
    ax.set_ylabel("score")
    ax.set_title("Patient-Room Benchmark: configurations compared")
    ax.legend(loc="upper left", fontsize=8)
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_accuracy.png", dpi=160)
    plt.close(fig)

    fig, ax = plt.subplots(figsize=(5.5, 3.0))
    ax.bar(configs, p95, color="#5B7FBE")
    ax.set_ylabel("p95 latency (seconds)")
    ax.set_title("End-to-end p95 latency per configuration")
    fig.tight_layout()
    fig.savefig(FIG_DIR / "fig_latency.png", dpi=160)
    plt.close(fig)

    pipeline = next((s for s in summaries if s["config"] == "pipeline"), None)
    if pipeline:
        cats = list(pipeline["by_category"].keys())
        accs = [pipeline["by_category"][c]["accuracy"] for c in cats]
        halls = [pipeline["by_category"][c]["hallucination_rate"] for c in cats]
        x = np.arange(len(cats))
        fig, ax = plt.subplots(figsize=(7, 3.5))
        ax.bar(x - 0.2, accs, 0.4, label="accuracy")
        ax.bar(x + 0.2, halls, 0.4, label="hallucination")
        ax.set_xticks(x); ax.set_xticklabels(cats, rotation=20)
        ax.set_ylim(0, 1.05); ax.set_ylabel("score")
        ax.set_title("Pipeline: per-category accuracy and hallucination")
        ax.legend()
        fig.tight_layout()
        fig.savefig(FIG_DIR / "fig_per_category.png", dpi=160)
        plt.close(fig)

    print(f"Wrote PNGs to {FIG_DIR}")


if __name__ == "__main__":
    main()
