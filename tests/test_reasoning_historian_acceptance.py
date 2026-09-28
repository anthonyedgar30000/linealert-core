from __future__ import annotations

import copy

from linealert_core.reasoning_context import (
    EvidenceCandidate,
    EvidenceRole,
    ReasoningContextRequest,
    RetrievalMethod,
    assemble_reasoning_context,
)
from linealert_core.reasoning_historian import (
    HistorianConditionQuery,
    HistorianConditionRetrieval,
    HistorianRetrievalRefusal,
)
from linealert_core.reasoning_historian_acceptance import (
    evaluate_reasoning_historian_acceptance,
    main,
)

ASSET = "LABELER-DEMO-01"
RELATIONSHIP = "relationship:label-presentation-delay"
SOURCE = "timescaledb:linealert-local:condition_measurements"
CONFIG_SOURCE = "labeler_demo_config.json"
CONFIG_SHA = "a" * 64


def _candidate(
    index: int,
    *,
    clock_evidence: dict[str, object] | None = None,
) -> EvidenceCandidate:
    observation_id = f"obs-{index}"
    return EvidenceCandidate(
        evidence_id=f"historian.condition:{observation_id}",
        asset_id=ASSET,
        source_id=SOURCE,
        source_class="timescaledb_condition_measurement",
        evidence_role=EvidenceRole.HISTORICAL_OBSERVATION,
        retrieval_method=RetrievalMethod.DETERMINISTIC_SCOPE,
        content={
            "observation_id": observation_id,
            "asset_id": ASSET,
            "relationship_id": RELATIONSHIP,
            "episode_id": "condition-runtime-replay",
            "quality": "good",
            "clock_evidence": (
                clock_evidence
                if clock_evidence is not None
                else {
                    "schema_version": "linealert.clock-evidence.v1",
                    "status": "BOUNDED",
                }
            ),
        },
        provenance=(
            f"{SOURCE}:{observation_id}",
            f"config:{CONFIG_SOURCE}:sha256:{CONFIG_SHA}",
        ),
        semantic_admitted=True,
        binding_verified=True,
        observed_at=f"2026-07-19T14:10:{index:02d}+00:00",
        authority_class="HISTORIAN_WRITE_TIME_POLICY_AUTHORITY",
    )


def _retrieval(
    *,
    candidates: tuple[EvidenceCandidate, ...] | None = None,
    refusals: tuple[HistorianRetrievalRefusal, ...] = (),
    truncated: bool = False,
    read_only_verified: bool = True,
) -> HistorianConditionRetrieval:
    selected = candidates if candidates is not None else tuple(_candidate(i) for i in range(1, 4))
    return HistorianConditionRetrieval(
        query=HistorianConditionQuery(
            asset_id=ASSET,
            relationship_id=RELATIONSHIP,
            episode_id="condition-runtime-replay",
            limit=100,
        ),
        source_id=SOURCE,
        candidates=selected,
        refusals=refusals,
        truncated=truncated,
        read_only_verified=read_only_verified,
    )


def _bundles(retrieval: HistorianConditionRetrieval):
    request = ReasoningContextRequest(
        asset_id=ASSET,
        purpose="test live acceptance",
        max_items=100,
    )
    bundle = assemble_reasoning_context(request, retrieval.candidates)
    return bundle, assemble_reasoning_context(request, retrieval.candidates)


def _evaluate(
    retrieval: HistorianConditionRetrieval | None = None,
    *,
    expected_candidate_count: int | None = 3,
    require_clock_evidence: bool = True,
    repeat_mutator=None,
):
    active = retrieval or _retrieval()
    bundle, repeat = _bundles(active)
    if repeat_mutator is not None:
        repeat = copy.deepcopy(repeat)
        repeat_mutator(repeat)
    return evaluate_reasoning_historian_acceptance(
        retrieval=active,
        bundle=bundle,
        repeat_bundle=repeat,
        expected_candidate_count=expected_candidate_count,
        expected_config_source_name=CONFIG_SOURCE,
        expected_config_sha256=CONFIG_SHA,
        require_clock_evidence=require_clock_evidence,
    )


def _check(report, check_id: str):
    return next(check for check in report.checks if check.check_id == check_id)


def test_exact_controlled_retrieval_passes_acceptance() -> None:
    report = _evaluate()

    assert report.passed is True
    assert report.read_only_verified is True
    assert report.candidate_count == 3
    assert report.refusal_count == 0
    assert report.truncated is False
    assert report.clock_evidence_nonempty_count == 3
    assert report.current_configuration_applicability == "UNASSESSED"
    assert report.candidate_configuration_versions == ()
    assert all(check.passed for check in report.checks)


def test_unverified_read_only_state_fails_acceptance() -> None:
    report = _evaluate(_retrieval(read_only_verified=False))

    assert report.passed is False
    assert _check(report, "SOURCE.READ_ONLY_VERIFIED").passed is False


def test_truncated_retrieval_fails_acceptance() -> None:
    report = _evaluate(_retrieval(truncated=True))

    assert report.passed is False
    assert _check(report, "RETRIEVAL.NOT_TRUNCATED").passed is False


def test_retrieval_refusal_fails_acceptance() -> None:
    report = _evaluate(
        _retrieval(
            refusals=(
                HistorianRetrievalRefusal(
                    observation_id="obs-x",
                    reason_code="HISTORIAN.RETAINED_AUTHORITY_MISSING",
                ),
            )
        )
    )

    assert report.passed is False
    assert _check(report, "RETRIEVAL.NO_REFUSALS").passed is False


def test_expected_candidate_count_is_enforced() -> None:
    report = _evaluate(expected_candidate_count=10)

    assert report.passed is False
    assert _check(report, "RETRIEVAL.EXPECTED_COUNT").passed is False


def test_missing_clock_evidence_fails_when_required() -> None:
    candidates = (
        _candidate(1),
        _candidate(2, clock_evidence={}),
        _candidate(3),
    )
    report = _evaluate(_retrieval(candidates=candidates))

    assert report.passed is False
    assert _check(report, "CANDIDATE.CLOCK_EVIDENCE_PRESERVED").passed is False


def test_clock_evidence_requirement_can_be_disabled() -> None:
    candidates = (
        _candidate(1),
        _candidate(2, clock_evidence={}),
        _candidate(3),
    )
    report = _evaluate(
        _retrieval(candidates=candidates),
        require_clock_evidence=False,
    )

    assert _check(report, "CANDIDATE.CLOCK_EVIDENCE_PRESERVED").passed is True


def test_config_provenance_mismatch_fails_acceptance() -> None:
    original = _candidate(1)
    bad = EvidenceCandidate(
        evidence_id=original.evidence_id,
        asset_id=original.asset_id,
        source_id=original.source_id,
        source_class=original.source_class,
        evidence_role=original.evidence_role,
        retrieval_method=original.retrieval_method,
        content=original.content,
        provenance=(
            f"{SOURCE}:obs-1",
            f"config:{CONFIG_SOURCE}:sha256:{'b' * 64}",
        ),
        semantic_admitted=True,
        binding_verified=True,
        observed_at=original.observed_at,
        authority_class=original.authority_class,
    )
    report = _evaluate(_retrieval(candidates=(bad, _candidate(2), _candidate(3))))

    assert report.passed is False
    assert _check(report, "CANDIDATE.CONFIG_PROVENANCE").passed is False


def test_repeat_bundle_mismatch_fails_determinism_check() -> None:
    def mutate(repeat):
        repeat["bundle_sha256"] = "b" * 64

    report = _evaluate(repeat_mutator=mutate)

    assert report.passed is False
    assert _check(report, "BUNDLE.DETERMINISTIC").passed is False


def test_context_bundle_authority_escalation_fails_acceptance() -> None:
    retrieval = _retrieval()
    bundle, repeat = _bundles(retrieval)
    bundle = copy.deepcopy(bundle)
    repeat = copy.deepcopy(repeat)
    bundle["authorized_action"] = True
    repeat["authorized_action"] = True

    report = evaluate_reasoning_historian_acceptance(
        retrieval=retrieval,
        bundle=bundle,
        repeat_bundle=repeat,
        expected_candidate_count=3,
        expected_config_source_name=CONFIG_SOURCE,
        expected_config_sha256=CONFIG_SHA,
        require_clock_evidence=True,
    )

    assert report.passed is False
    assert _check(report, "BUNDLE.NO_AUTHORITY_ESCALATION").passed is False


def test_cli_requires_explicit_dsn(monkeypatch, capsys) -> None:
    monkeypatch.delenv("LINEALERT_HISTORIAN_DSN", raising=False)

    assert main([]) == 2
    assert "--dsn or LINEALERT_HISTORIAN_DSN is required" in capsys.readouterr().err


def test_cli_rejects_bundle_limit_above_context_contract(monkeypatch, capsys) -> None:
    monkeypatch.setenv("LINEALERT_HISTORIAN_DSN", "postgresql://example.invalid/db")

    assert main(["--limit", "257"]) == 2
    assert "--limit must be between 1 and 256" in capsys.readouterr().err
