"""Run-level gradual-drift analysis over observable emulator evidence only."""

from __future__ import annotations

import hashlib
import json
import math
from collections.abc import Iterable
from dataclasses import asdict, dataclass
from statistics import mean, pstdev

from .causal_emulator import CycleEvidence, EmulatorRun


@dataclass(frozen=True, slots=True)
class SignalBaseline:
    mean: float
    standard_deviation: float


@dataclass(frozen=True, slots=True)
class RunDriftAssessment:
    """One bounded decision derived without access to simulator ground truth."""

    status: str
    first_confident_cycle: int | None
    confidence: float
    agreeing_anchors: tuple[str, ...]
    stable_anchors: tuple[str, ...]
    observation: str
    recommended_action: str | None
    retained_uncertainty: str
    recovery_status: str
    evidence_fingerprint_sha256: str
    analysis_fingerprint_sha256: str

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


class GradualDriftAnalyzer:
    """Detect sustained drift and coordinate one conservative operator action."""

    def __init__(self, *, baseline_cycles: int = 20, persistence_cycles: int = 6) -> None:
        if baseline_cycles < 8:
            raise ValueError("baseline_cycles must be at least 8")
        if persistence_cycles < 3:
            raise ValueError("persistence_cycles must be at least 3")
        self.baseline_cycles = baseline_cycles
        self.persistence_cycles = persistence_cycles

    def analyze(self, run: EmulatorRun) -> RunDriftAssessment:
        evidence = tuple(record.evidence for record in run.records)
        if len(evidence) < self.baseline_cycles + self.persistence_cycles:
            raise ValueError("run is too short for baseline and persistence windows")

        baseline = evidence[: self.baseline_cycles]
        latency = self._baseline(item.camera_actuator_latency_ms for item in baseline)
        arrival = self._baseline(item.s1_arrival_ms for item in baseline)
        offset = self._baseline(abs(item.label_offset_mm) for item in baseline)
        ratio = self._baseline(item.feed_wrapper_ratio for item in baseline)

        first_confident_cycle: int | None = None
        selected_anchors: tuple[str, ...] = ()
        selected_confidence = 0.0
        for end in range(self.baseline_cycles + self.persistence_cycles, len(evidence) + 1):
            window = evidence[end - self.persistence_cycles : end]
            anchors, confidence = self._window_assessment(
                window, latency=latency, arrival=arrival, offset=offset
            )
            if len(anchors) >= 2 and confidence >= 0.75:
                first_confident_cycle = end - 1
                selected_anchors = anchors
                selected_confidence = confidence
                break

        stable_anchors: tuple[str, ...] = ()
        if first_confident_cycle is not None:
            decision_window = evidence[
                first_confident_cycle - self.persistence_cycles + 1 : first_confident_cycle + 1
            ]
            decision_ratio = mean(item.feed_wrapper_ratio for item in decision_window)
            ratio_delta = abs(decision_ratio - ratio.mean)
            ratio_limit = max(0.006, 4.0 * ratio.standard_deviation)
            if ratio_delta <= ratio_limit:
                stable_anchors = ("feed/wrapper ratio remained stable",)

        status = "actionable_drift" if first_confident_cycle is not None else "no_action"
        action = (
            "Inspect Lane B release motion and merge spacing before changing upstream timing."
            if first_confident_cycle is not None
            else None
        )
        observation = (
            "Lane B release timing drift is sustained across independent observations; "
            "feed/wrapper coordination remains stable."
            if first_confident_cycle is not None
            else "No sustained multi-anchor drift crossed the action threshold."
        )
        recovery = self._recovery_status(
            evidence,
            intervention_cycle=run.config.intervention_cycle,
            latency=latency,
            arrival=arrival,
        )
        payload = {
            "analyzer": "gradual-drift-v1",
            "baseline_cycles": self.baseline_cycles,
            "persistence_cycles": self.persistence_cycles,
            "evidence_fingerprint_sha256": run.evidence_fingerprint,
            "status": status,
            "first_confident_cycle": first_confident_cycle,
            "confidence": round(selected_confidence, 6),
            "agreeing_anchors": selected_anchors,
            "stable_anchors": stable_anchors,
            "recommended_action": action,
            "recovery_status": recovery,
        }
        analysis_hash = hashlib.sha256(
            json.dumps(payload, sort_keys=True, separators=(",", ":")).encode()
        ).hexdigest()
        return RunDriftAssessment(
            status=status,
            first_confident_cycle=first_confident_cycle,
            confidence=round(selected_confidence, 3),
            agreeing_anchors=selected_anchors,
            stable_anchors=stable_anchors,
            observation=observation,
            recommended_action=action,
            retained_uncertainty=(
                "The observations localize the first changed relationship; they do not "
                "prove whether leakage, stiction, alignment, or another mechanical "
                "cause is responsible."
            ),
            recovery_status=recovery,
            evidence_fingerprint_sha256=run.evidence_fingerprint,
            analysis_fingerprint_sha256=analysis_hash,
        )

    @staticmethod
    def _baseline(values: Iterable[float]) -> SignalBaseline:
        samples = tuple(float(value) for value in values)
        return SignalBaseline(mean(samples), max(pstdev(samples), 1e-6))

    @staticmethod
    def _excess_score(observed: float, baseline: SignalBaseline, floor: float) -> float:
        limit = baseline.mean + max(floor, 4.0 * baseline.standard_deviation)
        scale = max(floor, 3.0 * baseline.standard_deviation)
        return max(0.0, min(1.0, (observed - limit) / scale))

    def _window_assessment(
        self,
        window: tuple[CycleEvidence, ...],
        *,
        latency: SignalBaseline,
        arrival: SignalBaseline,
        offset: SignalBaseline,
    ) -> tuple[tuple[str, ...], float]:
        scores = {
            "camera-observed actuator latency": self._excess_score(
                mean(item.camera_actuator_latency_ms for item in window), latency, 6.0
            ),
            "photoeye-observed downstream arrival": self._excess_score(
                mean(item.s1_arrival_ms for item in window), arrival, 7.0
            ),
            "inspection-observed label displacement": self._excess_score(
                mean(abs(item.label_offset_mm) for item in window), offset, 0.7
            ),
        }
        anchors = tuple(name for name, score in scores.items() if score >= 0.35)
        if len(anchors) < 2:
            return anchors, 0.0
        confidence = 0.58 + 0.12 * len(anchors) + 0.08 * mean(scores[name] for name in anchors)
        return anchors, min(0.99, confidence)

    def _recovery_status(
        self,
        evidence: tuple[CycleEvidence, ...],
        *,
        intervention_cycle: int | None,
        latency: SignalBaseline,
        arrival: SignalBaseline,
    ) -> str:
        if intervention_cycle is None:
            return "not_tested"
        remaining = evidence[intervention_cycle:]
        if len(remaining) < self.persistence_cycles:
            return "insufficient_post_intervention_evidence"
        window = remaining[-self.persistence_cycles :]
        latency_ok = mean(item.camera_actuator_latency_ms for item in window) <= (
            latency.mean + max(6.0, 4.0 * latency.standard_deviation)
        )
        arrival_ok = mean(item.s1_arrival_ms for item in window) <= (
            arrival.mean + max(7.0, 4.0 * arrival.standard_deviation)
        )
        quality_ok = sum(item.product_accepted for item in window) >= math.ceil(
            0.8 * len(window)
        )
        return "verified" if latency_ok and arrival_ok and quality_ok else "not_verified"
