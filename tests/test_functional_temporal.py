from __future__ import annotations

import pytest

from linealert_core import (
    EpistemicState,
    EvidenceObservation,
    EvidenceValidity,
    FunctionalTemporalError,
    FunctionalTemporalEvaluator,
    FunctionalTemporalModel,
    GuardDefinition,
    InvariantDefinition,
    PhaseDefinition,
    TemporalCoverage,
    TransitionDefinition,
    TransitionDisposition,
)


def model() -> FunctionalTemporalModel:
    return FunctionalTemporalModel(
        phases=(
            PhaseDefinition("INDEXED", "Bottle indexed", "indexer"),
            PhaseDefinition(
                "CAPTURED",
                "Bottle captured",
                "capture",
                invariant_ids=("INV_CAPTURE_RESTRAINT",),
            ),
            PhaseDefinition("WRAP", "Wrap active", "wrapper", invariant_ids=("INV_WRAP_READY",)),
        ),
        transitions=(
            TransitionDefinition(
                "INDEXED_TO_CAPTURED",
                "INDEXED",
                "CAPTURED",
                "CaptureEstablished",
                ("GUARD_BOTTLE_PRESENT", "GUARD_CAPTURE_READY"),
            ),
            TransitionDefinition(
                "CAPTURED_TO_WRAP",
                "CAPTURED",
                "WRAP",
                "WrapBegin",
                ("GUARD_CAPTURE_READY",),
            ),
        ),
        guards=(
            GuardDefinition(
                "GUARD_BOTTLE_PRESENT",
                ("bottle_present",),
                TemporalCoverage.POINT_ONLY,
            ),
            GuardDefinition(
                "GUARD_CAPTURE_READY",
                ("capture_ready",),
                TemporalCoverage.POINT_ONLY,
                depends_on_requirement_ids=("GUARD_BOTTLE_PRESENT",),
            ),
        ),
        invariants=(
            InvariantDefinition(
                "INV_CAPTURE_RESTRAINT",
                ("capture_restraint",),
                TemporalCoverage.THROUGHOUT_SCOPE,
            ),
            InvariantDefinition(
                "INV_WRAP_READY",
                ("wrap_relationship",),
                TemporalCoverage.THROUGHOUT_SCOPE,
                depends_on_requirement_ids=("INV_CAPTURE_RESTRAINT",),
            ),
        ),
    )


def observation(
    key: str,
    *,
    state: EpistemicState = EpistemicState.VERIFIED,
    validity: EvidenceValidity = EvidenceValidity.CURRENT,
    coverage: TemporalCoverage = TemporalCoverage.POINT_ONLY,
) -> EvidenceObservation:
    return EvidenceObservation(
        evidence_id=f"E:{key}",
        evidence_key=key,
        state=state,
        validity=validity,
        coverage=coverage,
        source_id="synthetic-labeler",
        cycle_id="cycle-42",
    )


def test_event_does_not_admit_phase_when_guard_evidence_is_missing() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    result = evaluator.evaluate_transition(
        "INDEXED",
        "CaptureEstablished",
        {"bottle_present": observation("bottle_present")},
    )

    assert result.disposition is TransitionDisposition.UNRESOLVED
    assert result.to_phase_id == "CAPTURED"
    assert result.target_phase_admission_state is EpistemicState.EXPOSED
    assert result.guard_results[1].state is EpistemicState.UNRESOLVED


def test_transition_is_admitted_only_when_all_guards_are_verified() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    evidence = {
        "bottle_present": observation("bottle_present"),
        "capture_ready": observation("capture_ready"),
    }

    result = evaluator.evaluate_transition("INDEXED", "CaptureEstablished", evidence)

    assert result.disposition is TransitionDisposition.ADMITTED
    assert result.target_phase_admission_state is EpistemicState.VERIFIED
    assert all(item.state is EpistemicState.VERIFIED for item in result.guard_results)


def test_explicit_guard_violation_rejects_transition_without_diagnosing_cause() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    evidence = {
        "bottle_present": observation("bottle_present", state=EpistemicState.VIOLATED),
        "capture_ready": observation("capture_ready"),
    }

    result = evaluator.evaluate_transition("INDEXED", "CaptureEstablished", evidence)

    assert result.disposition is TransitionDisposition.REJECTED
    assert result.target_phase_admission_state is EpistemicState.VIOLATED


def test_point_observation_cannot_verify_throughout_phase_invariant() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    result = evaluator.evaluate_phase(
        "CAPTURED",
        {"capture_restraint": observation("capture_restraint")},
    )

    assert result.state is EpistemicState.UNRESOLVED
    assert "does not satisfy THROUGHOUT_SCOPE" in result.invariant_results[0].reasons[0]


def test_interval_evidence_can_verify_throughout_phase_invariant() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    result = evaluator.evaluate_phase(
        "CAPTURED",
        {
            "capture_restraint": observation(
                "capture_restraint", coverage=TemporalCoverage.THROUGHOUT_SCOPE
            )
        },
    )

    assert result.state is EpistemicState.VERIFIED


def test_stale_evidence_is_preserved_but_not_usable_as_current_proof() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    result = evaluator.evaluate_phase(
        "CAPTURED",
        {
            "capture_restraint": observation(
                "capture_restraint",
                validity=EvidenceValidity.STALE,
                coverage=TemporalCoverage.THROUGHOUT_SCOPE,
            )
        },
    )

    assert result.state is EpistemicState.UNRESOLVED
    assert result.invariant_results[0].evidence_ids == ("E:capture_restraint",)
    assert "validity is STALE" in result.invariant_results[0].reasons[0]


def test_unresolved_dependency_exposes_downstream_requirement() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    evidence = {
        "wrap_relationship": observation(
            "wrap_relationship", coverage=TemporalCoverage.THROUGHOUT_SCOPE
        )
    }

    result = evaluator.evaluate_phase("WRAP", evidence)

    assert result.state is EpistemicState.EXPOSED
    assert result.invariant_results[0].state is EpistemicState.EXPOSED


def test_conflicting_current_evidence_is_preserved_as_conflict() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    result = evaluator.evaluate_transition(
        "INDEXED",
        "CaptureEstablished",
        {
            "bottle_present": observation("bottle_present", state=EpistemicState.CONFLICT),
            "capture_ready": observation("capture_ready"),
        },
    )

    assert result.disposition is TransitionDisposition.UNRESOLVED
    assert result.target_phase_admission_state is EpistemicState.CONFLICT


def test_unrelated_event_does_not_trigger_transition() -> None:
    result = FunctionalTemporalEvaluator(model()).evaluate_transition(
        "INDEXED", "BottleDetected", {}
    )

    assert result.disposition is TransitionDisposition.NOT_TRIGGERED


def test_reachable_state_set_does_not_silently_satisfy_interval_requirement() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    result = evaluator.evaluate_phase(
        "CAPTURED",
        {
            "capture_restraint": observation(
                "capture_restraint",
                coverage=TemporalCoverage.REACHABLE_STATE_SET,
            )
        },
    )

    assert result.state is EpistemicState.UNRESOLVED


def test_requirement_dependency_cycles_are_rejected() -> None:
    with pytest.raises(FunctionalTemporalError, match="dependency graph contains a cycle"):
        FunctionalTemporalModel(
            phases=(PhaseDefinition("A", "A", "component"),),
            transitions=(),
            guards=(
                GuardDefinition("G1", ("one",), TemporalCoverage.POINT_ONLY, ("G2",)),
                GuardDefinition("G2", ("two",), TemporalCoverage.POINT_ONLY, ("G1",)),
            ),
            invariants=(),
        )


def test_exposed_is_derived_and_cannot_be_admitted_as_raw_evidence() -> None:
    with pytest.raises(FunctionalTemporalError, match="EXPOSED is derived"):
        observation("derived", state=EpistemicState.EXPOSED)


def test_unknown_current_phase_fails_closed() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    with pytest.raises(FunctionalTemporalError, match="unknown phase"):
        evaluator.evaluate_transition("MISSING", "CaptureEstablished", {})


def test_evidence_mapping_key_must_match_observation_identity() -> None:
    evaluator = FunctionalTemporalEvaluator(model())
    with pytest.raises(FunctionalTemporalError, match="does not match observation key"):
        evaluator.evaluate_transition(
            "INDEXED",
            "CaptureEstablished",
            {"bottle_present": observation("capture_ready")},
        )


def test_phase_without_invariants_is_not_silently_verified() -> None:
    result = FunctionalTemporalEvaluator(model()).evaluate_phase("INDEXED", {})
    assert result.state is EpistemicState.UNRESOLVED
