"""Benchmark runner and metrics."""

from __future__ import annotations

import json
import statistics
import time
from dataclasses import dataclass, field, asdict
from pathlib import Path
from typing import Any

from .llm_client import MockLLM, make_client
from .pipeline import PatientRoomAgent
from .room import PatientRoom
from .tools import TOOLS, tool_names


BENCHMARK_PATH = Path(__file__).resolve().parent.parent / "data" / "benchmark.json"


@dataclass
class ItemResult:
    id: str
    category: str
    utterance: str
    actor: str
    predicted_tools: list[str]
    expected_tools: list[str] | list[list[str]]
    must_refuse: bool
    refused: bool
    correct_tools: bool
    correct_refusal: bool
    hallucinated: bool
    latency_s: float
    raw: dict | None = None


@dataclass
class RunSummary:
    config: str
    n: int
    overall_accuracy: float
    refusal_precision: float
    refusal_recall: float
    refusal_f1: float
    hallucination_rate: float
    mean_latency_s: float
    p95_latency_s: float
    by_category: dict[str, dict[str, float]]
    items: list[ItemResult] = field(default_factory=list)


def load_benchmark(path: Path = BENCHMARK_PATH) -> list[dict]:
    with open(path) as f:
        return json.load(f)["items"]


def _toolset(calls: list[dict]) -> list[str]:
    return sorted(c["name"] for c in calls)


def _expected_match(predicted: list[str], item: dict) -> bool:
    pred = set(predicted)
    if "expected_any_of" in item:
        for combo in item["expected_any_of"]:
            if set(combo).issubset(pred) and len(pred) <= len(combo) + 1:
                return True
        return False
    expected_names = sorted({c["name"] for c in item["expected"]})
    return pred == set(expected_names)


def _category_breakdown(items: list[ItemResult]) -> dict[str, dict[str, float]]:
    out: dict[str, dict[str, float]] = {}
    for cat in {it.category for it in items}:
        sub = [it for it in items if it.category == cat]
        n = len(sub)
        out[cat] = {
            "n": n,
            "accuracy": sum(it.correct_tools and it.correct_refusal
                            for it in sub) / n if n else 0.0,
            "refusal_correct":
                sum(it.correct_refusal for it in sub) / n if n else 0.0,
            "hallucination_rate":
                sum(it.hallucinated for it in sub) / n if n else 0.0,
            "mean_latency_s":
                statistics.mean(it.latency_s for it in sub) if n else 0.0,
        }
    return out


def run_pipeline_config(items: list[dict], llm,
                        config_name: str = "pipeline") -> RunSummary:
    results: list[ItemResult] = []
    for item in items:
        room = PatientRoom()
        agent = PatientRoomAgent(room, llm,
                                 default_actor=item.get("actor", "patient"))
        out = agent.handle(item["utterance"])
        predicted_tools = _toolset(out.plan)
        expected_tools = (item.get("expected_any_of")
                          or [c["name"] for c in item["expected"]])
        refused = (len(out.plan) == 0
                   and len(out.needs_confirmation) == 0)
        correct_refusal = (refused == item["must_refuse"])
        if item["must_refuse"]:
            correct_tools = (len(predicted_tools) == 0)
        else:
            correct_tools = _expected_match(predicted_tools, item)
        valid = tool_names()
        hallucinated = any(c["name"] not in valid for c in out.plan) \
            or any(r.get("reason", "").startswith("hallucinated_tool")
                   for r in out.rejected)
        results.append(ItemResult(
            id=item["id"], category=item["category"],
            utterance=item["utterance"], actor=item.get("actor", "patient"),
            predicted_tools=predicted_tools,
            expected_tools=expected_tools,
            must_refuse=item["must_refuse"],
            refused=refused,
            correct_tools=correct_tools,
            correct_refusal=correct_refusal,
            hallucinated=hallucinated,
            latency_s=out.total_latency_s,
            raw={"rationale": out.rationale,
                 "rejected": out.rejected,
                 "executions": out.executions,
                 "backend": out.backend},
        ))
    return _summarize(results, config_name)


def run_single_prompt(items: list[dict], llm,
                      config_name: str = "single_prompt") -> RunSummary:
    results: list[ItemResult] = []
    for item in items:
        room = PatientRoom()
        actor = item.get("actor", "patient")
        t0 = time.time()
        resp = llm.complete(
            "You are a patient-room controller. Output tool calls only.",
            f"Room state: {room.snapshot()}\nUser ({actor}): "
            f"{item['utterance']}",
            tools=TOOLS,
        )
        elapsed = time.time() - t0
        predicted_tools = sorted(c["name"] for c in resp.tool_calls)
        for c in resp.tool_calls:
            room.dispatch(c["name"], c.get("arguments", {}), actor)
        refused = len(resp.tool_calls) == 0
        correct_refusal = (refused == item["must_refuse"])
        if item["must_refuse"]:
            correct_tools = (len(predicted_tools) == 0)
        else:
            correct_tools = _expected_match(predicted_tools, item)
        valid = tool_names()
        hallucinated = any(c["name"] not in valid for c in resp.tool_calls)
        results.append(ItemResult(
            id=item["id"], category=item["category"],
            utterance=item["utterance"], actor=actor,
            predicted_tools=predicted_tools,
            expected_tools=(item.get("expected_any_of")
                            or [c["name"] for c in item["expected"]]),
            must_refuse=item["must_refuse"],
            refused=refused,
            correct_tools=correct_tools,
            correct_refusal=correct_refusal,
            hallucinated=hallucinated,
            latency_s=elapsed,
            raw={"backend": resp.backend, "text": resp.text},
        ))
    return _summarize(results, config_name)


def run_intent_classifier(items: list[dict],
                          config_name: str = "intent_classifier"
                          ) -> RunSummary:
    return run_pipeline_config(items, MockLLM(), config_name=config_name)


def _summarize(results: list[ItemResult], config: str) -> RunSummary:
    n = len(results)
    refused_correctly = sum(it.correct_refusal for it in results)
    refusals_predicted = sum(it.refused for it in results)
    refusals_actual = sum(it.must_refuse for it in results)
    tp = sum(it.refused and it.must_refuse for it in results)
    fp = sum(it.refused and not it.must_refuse for it in results)
    fn = sum(not it.refused and it.must_refuse for it in results)
    precision = tp / (tp + fp) if (tp + fp) else 0.0
    recall = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = (2 * precision * recall / (precision + recall)
          if (precision + recall) else 0.0)
    overall = sum(it.correct_tools and it.correct_refusal
                  for it in results) / n if n else 0.0
    halluc = sum(it.hallucinated for it in results) / n if n else 0.0
    latencies = sorted(it.latency_s for it in results)
    p95 = latencies[int(0.95 * (n - 1))] if n else 0.0
    mean = statistics.mean(latencies) if n else 0.0
    return RunSummary(
        config=config,
        n=n,
        overall_accuracy=overall,
        refusal_precision=precision,
        refusal_recall=recall,
        refusal_f1=f1,
        hallucination_rate=halluc,
        mean_latency_s=mean,
        p95_latency_s=p95,
        by_category=_category_breakdown(results),
        items=results,
    )


def summary_to_dict(s: RunSummary) -> dict:
    d = asdict(s)
    return d
