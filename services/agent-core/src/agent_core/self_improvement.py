from __future__ import annotations

import json
import logging
import random
import time
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from agent_core.config import settings
from agent_core.skills.learning import skill_learning
from agent_core.storage import store

logger = logging.getLogger(__name__)


@dataclass
class PromptVariant:
    name: str
    prompt_template: str
    weight: float = 1.0
    stats: dict[str, float] = field(default_factory=lambda: {"successes": 0, "trials": 0, "avg_latency": 0.0, "avg_score": 0.0})


@dataclass
class ABTestConfig:
    test_name: str
    variants: list[PromptVariant]
    traffic_split: dict[str, float] = field(default_factory=dict)
    min_trials_per_variant: int = 20
    confidence_threshold: float = 0.95


@dataclass
class BenchmarkResult:
    benchmark_name: str
    variant_name: str
    score: float
    latency_ms: float
    timestamp: float
    metadata: dict[str, Any] = field(default_factory=dict)


class SelfImprovementPipeline:
    def __init__(self) -> None:
        self.data_dir = Path(settings.resolved_agent_data_dir) / "self_improvement"
        self.data_dir.mkdir(parents=True, exist_ok=True)
        self.ab_tests: dict[str, ABTestConfig] = {}
        self.benchmark_history: list[BenchmarkResult] = []
        self._load_state()
        self._setup_default_tests()

    def _load_state(self) -> None:
        state_file = self.data_dir / "state.json"
        if state_file.exists():
            try:
                data = json.loads(state_file.read_text())
                for test_name, test_data in data.get("ab_tests", {}).items():
                    variants = [PromptVariant(**v) for v in test_data["variants"]]
                    self.ab_tests[test_name] = ABTestConfig(
                        test_name=test_name,
                        variants=variants,
                        traffic_split=test_data.get("traffic_split", {}),
                        min_trials_per_variant=test_data.get("min_trials_per_variant", 20),
                        confidence_threshold=test_data.get("confidence_threshold", 0.95),
                    )
                for b in data.get("benchmark_history", []):
                    self.benchmark_history.append(BenchmarkResult(**b))
            except Exception as e:
                logger.warning("Failed to load self-improvement state: %s", e)

    def _save_state(self) -> None:
        try:
            state_file = self.data_dir / "state.json"
            data = {
                "ab_tests": {
                    name: {
                        "variants": [vars(v) for v in test.variants],
                        "traffic_split": test.traffic_split,
                        "min_trials_per_variant": test.min_trials_per_variant,
                        "confidence_threshold": test.confidence_threshold,
                    }
                    for name, test in self.ab_tests.items()
                },
                "benchmark_history": [vars(b) for b in self.benchmark_history[-500:]],  # Keep last 500
            }
            state_file.write_text(json.dumps(data, indent=2))
        except Exception as e:
            logger.warning("Failed to save self-improvement state: %s", e)

    def _setup_default_tests(self) -> None:
        # A/B test for system prompt variations
        if "system_prompt_style" not in self.ab_tests:
            self.ab_tests["system_prompt_style"] = ABTestConfig(
                test_name="system_prompt_style",
                variants=[
                    PromptVariant(
                        name="concise",
                        prompt_template="You are a concise, helpful assistant. Answer directly without unnecessary preamble.",
                        weight=1.0,
                    ),
                    PromptVariant(
                        name="detailed",
                        prompt_template="You are a thorough assistant. Provide comprehensive answers with explanations and examples.",
                        weight=1.0,
                    ),
                    PromptVariant(
                        name="structured",
                        prompt_template="You are a structured assistant. Use clear headings, bullet points, and organized formatting.",
                        weight=1.0,
                    ),
                ],
                traffic_split={"concise": 0.4, "detailed": 0.3, "structured": 0.3},
                min_trials_per_variant=30,
            )

        # A/B test for model temperature
        if "model_temperature" not in self.ab_tests:
            self.ab_tests["model_temperature"] = ABTestConfig(
                test_name="model_temperature",
                variants=[
                    PromptVariant(name="low_temp", prompt_template="", weight=1.0, stats={"temperature": 0.1}),
                    PromptVariant(name="medium_temp", prompt_template="", weight=1.0, stats={"temperature": 0.3}),
                    PromptVariant(name="high_temp", prompt_template="", weight=1.0, stats={"temperature": 0.5}),
                ],
                traffic_split={"low_temp": 0.4, "medium_temp": 0.4, "high_temp": 0.2},
                min_trials_per_variant=25,
            )

    def select_variant(self, test_name: str) -> PromptVariant | None:
        """Select a variant for an A/B test using weighted random selection."""
        test = self.ab_tests.get(test_name)
        if not test:
            return None

        # Check if we have enough data to make a decision
        ready_variants = [v for v in test.variants if v.stats["trials"] >= test.min_trials_per_variant]
        if len(ready_variants) >= 2:
            # Pick the best performing variant
            best = max(ready_variants, key=lambda v: v.stats["avg_score"])
            return best

        # Otherwise use traffic split
        split = test.traffic_split
        if not split:
            return random.choice(test.variants)

        rand = random.random()
        cumulative = 0.0
        for variant in test.variants:
            cumulative += split.get(variant.name, 0)
            if rand <= cumulative:
                return variant
        return test.variants[-1]

    def record_result(self, test_name: str, variant_name: str, success: bool, latency_ms: float, score: float = 0.0) -> None:
        test = self.ab_tests.get(test_name)
        if not test:
            return
        for variant in test.variants:
            if variant.name == variant_name:
                variant.stats["trials"] += 1
                if success:
                    variant.stats["successes"] += 1
                # Exponential moving average for latency and score
                alpha = 0.1
                variant.stats["avg_latency"] = variant.stats["avg_latency"] * (1 - alpha) + latency_ms * alpha
                variant.stats["avg_score"] = variant.stats["avg_score"] * (1 - alpha) + score * alpha
                break
        self._save_state()

    def get_best_variant(self, test_name: str) -> PromptVariant | None:
        test = self.ab_tests.get(test_name)
        if not test:
            return None
        ready = [v for v in test.variants if v.stats["trials"] >= test.min_trials_per_variant]
        if not ready:
            return None
        return max(ready, key=lambda v: v.stats["avg_score"])

    def detect_tool_gaps(self) -> list[dict[str, Any]]:
        """Analyze skill learning data to detect missing tool capabilities."""
        stats = skill_learning.get_stats()
        gaps = []

        # Look for skills with low success rates that might need better tools
        for skill_name, skill_stats in stats.get("by_skill", {}).items():
            success_rate = skill_stats.get("success_rate", 1.0)
            avg_duration = skill_stats.get("avg_duration", 0)
            total = skill_stats.get("total", 0)

            if total >= 10 and success_rate < 0.5:
                gaps.append({
                    "type": "tool_improvement",
                    "skill": skill_name,
                    "reason": f"Low success rate ({success_rate:.1%}) over {total} interactions",
                    "priority": "high" if success_rate < 0.3 else "medium",
                    "suggested_action": "Create or improve tools for this skill",
                })

            if total >= 5 and avg_duration > 10000:  # >10 seconds average
                gaps.append({
                    "type": "performance_optimization",
                    "skill": skill_name,
                    "reason": f"High average latency ({avg_duration:.0f}ms) over {total} interactions",
                    "priority": "medium",
                    "suggested_action": "Add caching, optimize tool implementations, or add async variants",
                })

        # Look for frequently requested but unavailable tools
        # This would require tracking failed tool calls - for now return what we have
        return gaps

    def run_benchmarks(self) -> list[BenchmarkResult]:
        """Run automated benchmarks against current configuration."""
        results = []

        # Benchmark 1: Simple QA latency
        for variant_name in ["concise", "detailed", "structured"]:
            test = self.ab_tests.get("system_prompt_style")
            if test:
                variant = next((v for v in test.variants if v.name == variant_name), None)
                if variant:
                    # Simulate benchmark (in reality, this would call the actual model)
                    start = time.perf_counter()
                    # Simulated work
                    time.sleep(0.01)
                    latency = (time.perf_counter() - start) * 1000
                    score = variant.stats.get("avg_score", 0.5) + random.uniform(-0.1, 0.1)

                    results.append(BenchmarkResult(
                        benchmark_name="qa_latency",
                        variant_name=variant_name,
                        score=max(0, min(1, score)),
                        latency_ms=latency,
                        timestamp=time.time(),
                    ))

        # Benchmark 2: Tool call success rate
        for skill_name in ["coding", "research", "writing"]:
            stats = skill_learning.get_stats(channel=None, chat_id=None)
            skill_stats = stats.get("by_skill", {}).get(skill_name, {})
            if skill_stats.get("total", 0) > 0:
                results.append(BenchmarkResult(
                    benchmark_name="tool_success_rate",
                    variant_name=skill_name,
                    score=skill_stats.get("success_rate", 0),
                    latency_ms=skill_stats.get("avg_duration", 0),
                    timestamp=time.time(),
                    metadata={"total_calls": skill_stats.get("total", 0)},
                ))

        self.benchmark_history.extend(results)
        self._save_state()
        return results

    def check_regressions(self, threshold: float = 0.1) -> list[dict[str, Any]]:
        """Detect performance regressions by comparing recent benchmarks to history."""
        regressions = []

        # Group benchmarks by name
        by_name: dict[str, list[BenchmarkResult]] = defaultdict(list)
        for b in self.benchmark_history:
            by_name[b.benchmark_name].append(b)

        for name, history in by_name.items():
            if len(history) < 10:
                continue

            # Compare last 5 to previous 5
            recent = history[-5:]
            previous = history[-10:-5]

            recent_avg_score = sum(b.score for b in recent) / len(recent)
            previous_avg_score = sum(b.score for b in previous) / len(previous)

            recent_avg_latency = sum(b.latency_ms for b in recent) / len(recent)
            previous_avg_latency = sum(b.latency_ms for b in previous) / len(previous)

            # Check for score regression
            if previous_avg_score > 0 and (previous_avg_score - recent_avg_score) / previous_avg_score > threshold:
                regressions.append({
                    "benchmark": name,
                    "type": "score_regression",
                    "severity": "high" if (previous_avg_score - recent_avg_score) / previous_avg_score > 0.2 else "medium",
                    "previous_score": previous_avg_score,
                    "current_score": recent_avg_score,
                    "change_pct": (previous_avg_score - recent_avg_score) / previous_avg_score * 100,
                })

            # Check for latency regression
            if previous_avg_latency > 0 and (recent_avg_latency - previous_avg_latency) / previous_avg_latency > threshold:
                regressions.append({
                    "benchmark": name,
                    "type": "latency_regression",
                    "severity": "high" if (recent_avg_latency - previous_avg_latency) / previous_avg_latency > 0.2 else "medium",
                    "previous_latency_ms": previous_avg_latency,
                    "current_latency_ms": recent_avg_latency,
                    "change_pct": (recent_avg_latency - previous_avg_latency) / previous_avg_latency * 100,
                })

        return regressions

    def generate_improvement_proposals(self) -> list[dict[str, Any]]:
        """Generate actionable improvement proposals based on all collected data."""
        proposals = []

        # 1. Promote winning A/B variants
        for test_name, test in self.ab_tests.items():
            best = self.get_best_variant(test_name)
            if best and best.stats["trials"] >= test.min_trials_per_variant:
                proposals.append({
                    "type": "promote_ab_winner",
                    "test": test_name,
                    "variant": best.name,
                    "score": best.stats["avg_score"],
                    "trials": best.stats["trials"],
                    "action": f"Promote '{best.name}' as default for {test_name}",
                })

        # 2. Tool gap proposals
        for gap in self.detect_tool_gaps():
            proposals.append({
                "type": "tool_gap",
                **gap,
            })

        # 3. Regression alerts
        for regression in self.check_regressions():
            proposals.append({
                "type": "regression_alert",
                **regression,
            })

        # 4. Skill-specific tool proposals based on usage patterns
        stats = skill_learning.get_stats()
        for skill_name, skill_stats in stats.get("by_skill", {}).items():
            if skill_stats.get("total", 0) > 20 and skill_stats.get("success_rate", 1) > 0.8:
                # High usage, high success - candidate for tool extraction
                proposals.append({
                    "type": "tool_extraction_candidate",
                    "skill": skill_name,
                    "usage_count": skill_stats["total"],
                    "success_rate": skill_stats["success_rate"],
                    "action": f"Consider extracting common patterns in '{skill_name}' as reusable tools",
                })

        return proposals

    def run_pipeline(self) -> dict[str, Any]:
        """Run the full self-improvement pipeline."""
        logger.info("Running self-improvement pipeline")

        # Run benchmarks
        benchmark_results = self.run_benchmarks()

        # Check for regressions
        regressions = self.check_regressions()

        # Detect tool gaps
        gaps = self.detect_tool_gaps()

        # Generate proposals
        proposals = self.generate_improvement_proposals()

        # Save state
        self._save_state()

        result = {
            "timestamp": datetime.now(UTC).isoformat(),
            "benchmarks_run": len(benchmark_results),
            "regressions_detected": len(regressions),
            "gaps_detected": len(gaps),
            "proposals_generated": len(proposals),
            "regressions": regressions,
            "gaps": gaps,
            "proposals": proposals,
        }

        # Audit log
        store.append_audit("self_improvement_pipeline_run", result)

        logger.info("Pipeline complete: %d proposals, %d regressions, %d gaps",
                    len(proposals), len(regressions), len(gaps))
        return result


pipeline = SelfImprovementPipeline()
