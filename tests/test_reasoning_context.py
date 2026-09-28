from __future__ import annotations

import json

from linealert_core.reasoning_context import (
    ContextUse,
    EvidenceCandidate,
    EvidenceRole,
    ReasoningContextRequest,
    RetrievalMethod,
    assemble_reasoning_context,
    main,
)


def _candidate(
    evidence_id: str,
    *,
    asset_id: str = "LABELER-DEMO-01",
    role: EvidenceRole = EvidenceRole.CURRENT_OBSERVATION,
    method: RetrievalMethod = RetrievalMethod.DETERMINISTIC_SCOPE,
    config: str | None = "cfg-2",
    semantic_admitted: bool = True,
    binding_verified: bool = True,
    invalidated: bool = False,
    superseded_by: str | None = None,
) -> EvidenceCandidate:
    return EvidenceCandidate(
        evidence_id=evidence_id,
        asset_id=asset_id,
        source_id=f"source:{evidence_id}",
        source_class="historian_record",
        evidence_role=role,
        retrieval_method=method,
        content={"value": evidence_id},
        provenance=(f"timescale:condition_measurements:{evidence_id}",),
        semantic_admitted=semantic_admitted,
        binding_verified=binding_verified,
        invalidated=invalidated,
        superseded_by=superseded_by,
        configuration_version=config,
        authority_class="OBSERVED_EVIDENCE",
    )


def _request(**overrides) -> ReasoningContextRequest:
    values = {
        "asset_id": "LABELER-DEMO-01",
        "purpose": "bounded troubleshooting context",
        "current_configuration_version": "cfg-2",
        "max_items": 32,
    }
    values.update(overrides)
    return ReasoningContextRequest(**values)


def _refusal_codes(bundle: dict[str, object]) -> set[str]:
    refusals = bundle["refusals"]
    assert isinstance(refusals, list)
    return {item["reason_code"] for item in refusals}


def test_exact_current_source_evidence_is_admitted_without_authority_escalation() -> None:
    bundle = assemble_reasoning_context(_request(), [_candidate("obs-1")])

    assert bundle["counts"]["evidence_count"] == 1
    assert bundle["counts"]["context_only_count"] == 0
    assert bundle["evidence"][0]["context_use"] == ContextUse.EVIDENCE.value
    assert bundle["authorized_action"] is False
    assert bundle["diagnosis_established"] is False
    assert bundle["retrieval_policy"]["model_invoked"] is False


def test_asset_scope_mismatch_fails_closed() -> None:
    bundle = assemble_reasoning_context(
        _request(),
        [_candidate("obs-other", asset_id="OTHER-ASSET")],
    )

    assert bundle["counts"]["evidence_count"] == 0
    assert "RETRIEVAL.ASSET_SCOPE_MISMATCH" in _refusal_codes(bundle)


def test_invalidated_and_superseded_evidence_are_refused() -> None:
    bundle = assemble_reasoning_context(
        _request(),
        [
            _candidate("invalid", invalidated=True),
            _candidate("old", superseded_by="new"),
        ],
    )

    codes = _refusal_codes(bundle)
    assert "RETRIEVAL.INVALIDATED_EVIDENCE_REFUSED" in codes
    assert "RETRIEVAL.SUPERSEDED_EVIDENCE_REFUSED" in codes


def test_unverified_source_binding_is_refused() -> None:
    bundle = assemble_reasoning_context(
        _request(),
        [_candidate("unbound", binding_verified=False)],
    )

    assert "RETRIEVAL.SOURCE_BINDING_UNVERIFIED" in _refusal_codes(bundle)


def test_source_authority_must_be_declared() -> None:
    candidate = _candidate("no-authority")
    candidate = EvidenceCandidate(
        evidence_id=candidate.evidence_id,
        asset_id=candidate.asset_id,
        source_id=candidate.source_id,
        source_class=candidate.source_class,
        evidence_role=candidate.evidence_role,
        retrieval_method=candidate.retrieval_method,
        content=candidate.content,
        provenance=candidate.provenance,
        semantic_admitted=True,
        binding_verified=True,
        configuration_version="cfg-2",
        authority_class=None,
    )

    bundle = assemble_reasoning_context(_request(), [candidate])

    assert "RETRIEVAL.SOURCE_AUTHORITY_UNDECLARED" in _refusal_codes(bundle)


def test_current_configuration_mismatch_is_refused() -> None:
    bundle = assemble_reasoning_context(
        _request(),
        [_candidate("wrong-config", config="cfg-1")],
    )

    assert "RETRIEVAL.CURRENT_CONFIGURATION_MISMATCH" in _refusal_codes(bundle)


def test_current_configuration_must_be_declared_when_request_is_bound() -> None:
    bundle = assemble_reasoning_context(
        _request(),
        [_candidate("unknown-config", config=None)],
    )

    assert "RETRIEVAL.CURRENT_CONFIGURATION_UNDECLARED" in _refusal_codes(bundle)


def test_historical_configuration_mismatch_is_context_only() -> None:
    historical = _candidate(
        "history-1",
        role=EvidenceRole.HISTORICAL_OBSERVATION,
        config="cfg-1",
    )
    bundle = assemble_reasoning_context(_request(), [historical])

    assert bundle["counts"]["evidence_count"] == 0
    assert bundle["counts"]["context_only_count"] == 1
    assert (
        bundle["context_only"][0]["reason_code"]
        == "RETRIEVAL.HISTORICAL_CONFIGURATION_CONTEXT_ONLY"
    )


def test_semantic_discovery_never_becomes_source_evidence() -> None:
    semantic = _candidate(
        "semantic-1",
        role=EvidenceRole.PROCEDURE,
        method=RetrievalMethod.SEMANTIC_DISCOVERY,
    )
    bundle = assemble_reasoning_context(_request(), [semantic])

    assert bundle["counts"]["evidence_count"] == 0
    assert bundle["counts"]["context_only_count"] == 1
    assert (
        bundle["context_only"][0]["reason_code"]
        == "RETRIEVAL.SEMANTIC_DISCOVERY_CONTEXT_ONLY"
    )
    assert bundle["retrieval_policy"]["semantic_discovery_confers_authority"] is False


def test_generated_summary_is_context_only_even_when_deterministically_selected() -> None:
    generated = _candidate(
        "summary-1",
        role=EvidenceRole.GENERATED_SUMMARY,
        method=RetrievalMethod.DETERMINISTIC_ID,
    )
    bundle = assemble_reasoning_context(_request(), [generated])

    assert bundle["counts"]["evidence_count"] == 0
    assert bundle["counts"]["context_only_count"] == 1
    assert bundle["context_only"][0]["reason_code"] == "RETRIEVAL.DERIVED_CONTEXT_ONLY"


def test_conflicting_duplicate_evidence_id_is_refused() -> None:
    first = _candidate("duplicate")
    second = EvidenceCandidate(
        evidence_id="duplicate",
        asset_id="LABELER-DEMO-01",
        source_id="source:other",
        source_class="historian_record",
        evidence_role=EvidenceRole.CURRENT_OBSERVATION,
        retrieval_method=RetrievalMethod.DETERMINISTIC_SCOPE,
        content={"value": "different"},
        provenance=("timescale:other",),
        configuration_version="cfg-2",
    )

    bundle = assemble_reasoning_context(_request(), [first, second])

    assert bundle["counts"]["evidence_count"] == 0
    assert "RETRIEVAL.DUPLICATE_EVIDENCE_ID_CONFLICT" in _refusal_codes(bundle)


def test_bundle_is_deterministic_across_candidate_input_order() -> None:
    candidates = [
        _candidate("b"),
        _candidate("a", role=EvidenceRole.DECLARED_CONFIGURATION),
        _candidate(
            "c",
            role=EvidenceRole.ANALYTICAL_FINDING,
            method=RetrievalMethod.DETERMINISTIC_ID,
        ),
    ]

    first = assemble_reasoning_context(_request(), candidates)
    second = assemble_reasoning_context(_request(), list(reversed(candidates)))

    assert first == second
    assert len(first["bundle_sha256"]) == 64


def test_context_limit_refuses_excess_candidates() -> None:
    bundle = assemble_reasoning_context(
        _request(max_items=1),
        [_candidate("a"), _candidate("b")],
    )

    assert bundle["counts"]["evidence_count"] == 1
    assert "RETRIEVAL.CONTEXT_LIMIT_REACHED" in _refusal_codes(bundle)


def test_cli_builds_json_bundle(tmp_path, capsys) -> None:
    request_path = tmp_path / "request.json"
    candidates_path = tmp_path / "candidates.json"
    request_path.write_text(
        json.dumps(
            {
                "asset_id": "LABELER-DEMO-01",
                "purpose": "test",
                "current_configuration_version": "cfg-2",
            }
        ),
        encoding="utf-8",
    )
    candidates_path.write_text(
        json.dumps(
            [
                {
                    "evidence_id": "obs-1",
                    "asset_id": "LABELER-DEMO-01",
                    "source_id": "historian",
                    "source_class": "historian_record",
                    "evidence_role": "CURRENT_OBSERVATION",
                    "retrieval_method": "DETERMINISTIC_SCOPE",
                    "content": {"value": 1},
                    "provenance": ["timescale:condition_measurements:obs-1"],
                    "semantic_admitted": True,
                    "binding_verified": True,
                    "configuration_version": "cfg-2",
                    "authority_class": "OBSERVED_EVIDENCE",
                }
            ]
        ),
        encoding="utf-8",
    )

    assert main(["--request", str(request_path), "--candidates", str(candidates_path)]) == 0
    rendered = json.loads(capsys.readouterr().out)
    assert rendered["counts"]["evidence_count"] == 1
    assert rendered["authorized_action"] is False
