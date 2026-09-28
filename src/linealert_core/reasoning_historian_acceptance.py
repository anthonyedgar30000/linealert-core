"""Live read-only acceptance for the governed Reasoning Node historian path."""

from __future__ import annotations

import argparse
import json
import os
import sys
from collections.abc import Mapping
from dataclasses import asdict, dataclass
from pathlib import Path
from typing import Any

from .historian_service import load_localization_topology_authority
from .reasoning_context import ReasoningContextRequest, assemble_reasoning_context
from .reasoning_historian import (
    HistorianConditionQuery,
    HistorianConditionRetrieval,
    HistorianRetrievalAuthority,
    ReadOnlyTimescaleConditionHistorySource,
    retrieve_historian_condition_candidates,
)

CLAIM_BOUNDARY = (
    "This acceptance verifies the controlled synthetic local Timescale -> governed retrieval -> "
    "reasoning-context-bundle path only. It does not establish current physical state, current "
    "configuration applicability, diagnosis, root cause, safety approval, production authority, "
    "or equipment-control authority."
)


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class ReasoningHistorianAcceptanceReport:
    schema_version: str
    scope: str
    passed: bool
    checks: tuple[AcceptanceCheck, ...]
    read_only_verified: bool
    candidate_count: int
    refusal_count: int
    truncated: bool
    clock_evidence_nonempty_count: int
    candidate_configuration_versions: tuple[str, ...]
    current_configuration_applicability: str
    bundle_sha256: str | None
    claim_boundary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "passed": self.passed,
            "checks": [asdict(check) for check in self.checks],
            "read_only_verified": self.read_only_verified,
            "candidate_count": self.candidate_count,
            "refusal_count": self.refusal_count,
            "truncated": self.truncated,
            "clock_evidence_nonempty_count": self.clock_evidence_nonempty_count,
            "candidate_configuration_versions": list(self.candidate_configuration_versions),
            "current_configuration_applicability": self.current_configuration_applicability,
            "bundle_sha256": self.bundle_sha256,
            "claim_boundary": self.claim_boundary,
        }


def _check(check_id: str, condition: bool, detail: str) -> AcceptanceCheck:
    return AcceptanceCheck(check_id=check_id, passed=bool(condition), detail=detail)


def _bundle_counts(bundle: Mapping[str, Any]) -> Mapping[str, Any]:
    raw = bundle.get("counts")
    return raw if isinstance(raw, Mapping) else {}


def evaluate_reasoning_historian_acceptance(
    *,
    retrieval: HistorianConditionRetrieval,
    bundle: Mapping[str, Any],
    repeat_bundle: Mapping[str, Any],
    expected_candidate_count: int | None,
    expected_config_source_name: str,
    expected_config_sha256: str,
    require_clock_evidence: bool,
) -> ReasoningHistorianAcceptanceReport:
    """Evaluate already-retrieved evidence without performing database I/O."""

    candidates = retrieval.candidates
    candidate_count = len(candidates)
    refusal_count = len(retrieval.refusals)
    unique_count = len({candidate.evidence_id for candidate in candidates})
    clock_count = sum(
        1
        for candidate in candidates
        if isinstance(candidate.content.get("clock_evidence"), Mapping)
        and bool(candidate.content.get("clock_evidence"))
    )
    config_versions = tuple(
        sorted(
            {
                candidate.configuration_version
                for candidate in candidates
                if candidate.configuration_version is not None
            }
        )
    )
    expected_config_provenance = (
        f"config:{expected_config_source_name}:sha256:{expected_config_sha256.lower()}"
    )
    counts = _bundle_counts(bundle)
    bundle_sha = bundle.get("bundle_sha256")
    repeat_sha = repeat_bundle.get("bundle_sha256")
    retrieval_policy = bundle.get("retrieval_policy")
    policy = retrieval_policy if isinstance(retrieval_policy, Mapping) else {}

    checks = [
        _check(
            "SOURCE.READ_ONLY_VERIFIED",
            retrieval.read_only_verified is True,
            f"read_only_verified={retrieval.read_only_verified}",
        ),
        _check(
            "RETRIEVAL.NOT_TRUNCATED",
            retrieval.truncated is False,
            f"truncated={retrieval.truncated}",
        ),
        _check(
            "RETRIEVAL.NO_REFUSALS",
            refusal_count == 0,
            (
                f"refusal_count={refusal_count} "
                f"reasons={[item.reason_code for item in retrieval.refusals]}"
            ),
        ),
        _check(
            "RETRIEVAL.NONEMPTY",
            candidate_count > 0,
            f"candidate_count={candidate_count}",
        ),
        _check(
            "RETRIEVAL.EXPECTED_COUNT",
            expected_candidate_count is None or candidate_count == expected_candidate_count,
            (
                f"candidate_count={candidate_count} "
                f"expected_candidate_count={expected_candidate_count}"
            ),
        ),
        _check(
            "CANDIDATE.UNIQUE_IDENTITY",
            unique_count == candidate_count,
            f"unique={unique_count} total={candidate_count}",
        ),
        _check(
            "CANDIDATE.SOURCE_BINDING",
            all(
                candidate.binding_verified
                and candidate.semantic_admitted
                and candidate.authority_class == "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY"
                for candidate in candidates
            ),
            f"candidate_count={candidate_count}",
        ),
        _check(
            "CANDIDATE.CONFIG_PROVENANCE",
            all(expected_config_provenance in candidate.provenance for candidate in candidates),
            (
                f"expected={expected_config_provenance} "
                f"candidate_count={candidate_count}"
            ),
        ),
        _check(
            "CANDIDATE.CLOCK_EVIDENCE_PRESERVED",
            (not require_clock_evidence) or clock_count == candidate_count,
            (
                f"clock_evidence_nonempty={clock_count} candidate_count={candidate_count} "
                f"required={require_clock_evidence}"
            ),
        ),
        _check(
            "BUNDLE.SCHEMA",
            bundle.get("schema_version") == "linealert.reasoning-context-bundle.v1",
            f"schema_version={bundle.get('schema_version')}",
        ),
        _check(
            "BUNDLE.CANDIDATE_PARITY",
            counts.get("candidate_count") == candidate_count
            and counts.get("evidence_count") == candidate_count
            and counts.get("context_only_count") == 0
            and counts.get("refusal_count") == 0,
            f"bundle_counts={dict(counts)} candidate_count={candidate_count}",
        ),
        _check(
            "BUNDLE.DETERMINISTIC",
            bundle == repeat_bundle
            and isinstance(bundle_sha, str)
            and len(bundle_sha) == 64
            and bundle_sha == repeat_sha,
            f"bundle_sha256={bundle_sha} repeat_sha256={repeat_sha}",
        ),
        _check(
            "BUNDLE.NO_MODEL",
            policy.get("model_invoked") is False,
            f"model_invoked={policy.get('model_invoked')}",
        ),
        _check(
            "BUNDLE.NO_AUTHORITY_ESCALATION",
            bundle.get("authorized_action") is False
            and bundle.get("diagnosis_established") is False,
            (
                f"authorized_action={bundle.get('authorized_action')} "
                f"diagnosis_established={bundle.get('diagnosis_established')}"
            ),
        ),
    ]

    passed = all(check.passed for check in checks)
    return ReasoningHistorianAcceptanceReport(
        schema_version="linealert.reasoning-historian-live-acceptance.v1",
        scope="controlled_synthetic_local_historian",
        passed=passed,
        checks=tuple(checks),
        read_only_verified=retrieval.read_only_verified,
        candidate_count=candidate_count,
        refusal_count=refusal_count,
        truncated=retrieval.truncated,
        clock_evidence_nonempty_count=clock_count,
        candidate_configuration_versions=config_versions,
        current_configuration_applicability="UNASSESSED",
        bundle_sha256=bundle_sha if isinstance(bundle_sha, str) else None,
        claim_boundary=CLAIM_BOUNDARY,
    )


def run_reasoning_historian_acceptance(
    *,
    dsn: str,
    config_path: Path,
    asset_id: str,
    relationship_id: str,
    episode_id: str,
    limit: int,
    expected_candidate_count: int | None,
    require_clock_evidence: bool,
) -> ReasoningHistorianAcceptanceReport:
    """Run the live database retrieval and deterministic context-bundle acceptance."""

    authority_source = load_localization_topology_authority(config_path)
    authority = HistorianRetrievalAuthority(
        asset_id=authority_source.asset_id,
        profile_id=authority_source.profile_id,
        source_name=authority_source.source_name,
        source_sha256=authority_source.source_sha256,
    )
    if asset_id != authority.asset_id:
        raise ValueError("asset_id does not match configured historian authority")

    source = ReadOnlyTimescaleConditionHistorySource(
        dsn,
        source_id="timescaledb:linealert-local:condition_measurements",
    )
    try:
        retrieval = retrieve_historian_condition_candidates(
            source,
            HistorianConditionQuery(
                asset_id=asset_id,
                relationship_id=relationship_id,
                episode_id=episode_id,
                limit=limit,
            ),
            authority,
        )
        request = ReasoningContextRequest(
            asset_id=asset_id,
            purpose="live NUC Timescale Reasoning Node acceptance",
            max_items=limit,
        )
        bundle = assemble_reasoning_context(request, retrieval.candidates)
        repeat_bundle = assemble_reasoning_context(request, retrieval.candidates)
    finally:
        source.close()

    return evaluate_reasoning_historian_acceptance(
        retrieval=retrieval,
        bundle=bundle,
        repeat_bundle=repeat_bundle,
        expected_candidate_count=expected_candidate_count,
        expected_config_source_name=authority.source_name,
        expected_config_sha256=authority.source_sha256,
        require_clock_evidence=require_clock_evidence,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only live acceptance for the governed Reasoning Node historian path."
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("LINEALERT_HISTORIAN_DSN"),
    )
    parser.add_argument(
        "--config",
        type=Path,
        default=Path("examples/labeler_demo_config.json"),
    )
    parser.add_argument("--asset-id", default="LABELER-DEMO-01")
    parser.add_argument(
        "--relationship-id",
        default="relationship:label-presentation-delay",
    )
    parser.add_argument("--episode-id", default="condition-runtime-replay")
    parser.add_argument("--limit", type=int, default=100)
    parser.add_argument("--expected-candidate-count", type=int, default=10)
    parser.add_argument(
        "--require-clock-evidence",
        action=argparse.BooleanOptionalAction,
        default=True,
    )
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.dsn:
        print("ERROR: --dsn or LINEALERT_HISTORIAN_DSN is required", file=sys.stderr)
        return 2
    if args.limit < 1 or args.limit > 256:
        print("ERROR: --limit must be between 1 and 256", file=sys.stderr)
        return 2
    if args.expected_candidate_count is not None and args.expected_candidate_count < 1:
        print("ERROR: --expected-candidate-count must be positive", file=sys.stderr)
        return 2

    try:
        report = run_reasoning_historian_acceptance(
            dsn=args.dsn,
            config_path=args.config,
            asset_id=args.asset_id,
            relationship_id=args.relationship_id,
            episode_id=args.episode_id,
            limit=args.limit,
            expected_candidate_count=args.expected_candidate_count,
            require_clock_evidence=args.require_clock_evidence,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": "linealert.reasoning-historian-live-acceptance.v1",
                    "scope": "controlled_synthetic_local_historian",
                    "passed": False,
                    "error": type(exc).__name__,
                    "detail": str(exc),
                    "claim_boundary": CLAIM_BOUNDARY,
                },
                indent=2,
                sort_keys=True,
            )
        )
        return 1

    print(json.dumps(report.to_dict(), indent=2, sort_keys=True))
    return 0 if report.passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
