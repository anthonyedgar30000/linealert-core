from linealert_core.causal_emulator import EmulatorConfig, LaneBDegradationEmulator
from linealert_core.drift_analysis import GradualDriftAnalyzer


def test_detects_sustained_multi_anchor_drift_without_hidden_truth() -> None:
    run = LaneBDegradationEmulator(EmulatorConfig(seed=9, cycles=150)).run()
    result = GradualDriftAnalyzer().analyze(run)
    assert result.status == "actionable_drift"
    assert result.first_confident_cycle is not None
    assert result.confidence >= 0.75
    assert len(result.agreeing_anchors) >= 2
    assert result.stable_anchors == ("feed/wrapper ratio remained stable",)
    assert result.recommended_action is not None
    assert result.recovery_status == "not_tested"


def test_intervention_recovery_is_functionally_verified() -> None:
    run = LaneBDegradationEmulator(
        EmulatorConfig(seed=19, cycles=160, intervention_cycle=120)
    ).run()
    result = GradualDriftAnalyzer().analyze(run)
    assert result.status == "actionable_drift"
    assert result.recovery_status == "verified"


def test_short_healthy_run_does_not_emit_an_action() -> None:
    run = LaneBDegradationEmulator(
        EmulatorConfig(seed=3, cycles=30, drift_onset_cycle=29)
    ).run()
    result = GradualDriftAnalyzer(baseline_cycles=20, persistence_cycles=6).analyze(run)
    assert result.status == "no_action"
    assert result.recommended_action is None


def test_analysis_fingerprint_is_deterministic_and_bound_to_evidence() -> None:
    analyzer = GradualDriftAnalyzer()
    first = analyzer.analyze(LaneBDegradationEmulator(EmulatorConfig(seed=4)).run())
    second = analyzer.analyze(LaneBDegradationEmulator(EmulatorConfig(seed=4)).run())
    different = analyzer.analyze(LaneBDegradationEmulator(EmulatorConfig(seed=5)).run())
    assert first.analysis_fingerprint_sha256 == second.analysis_fingerprint_sha256
    assert first.analysis_fingerprint_sha256 != different.analysis_fingerprint_sha256
