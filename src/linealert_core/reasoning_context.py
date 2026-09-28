"""Deterministic, provenance-preserving context assembly for the LineAlert reasoning node."""

from __future__ import annotations

import argparse
import hashlib
import json
import sys
from collections.abc import Mapping, Sequence
from dataclasses import asdict, dataclass, field
from enum import StrEnum
from pathlib import Path
from types import MappingProxyType
from typing import Any


class ReasoningContextError(ValueError):
    """Raised when a reasoning-context request or candidate is malformed."""


class RetrievalMethod(StrEnum):
    """How a candidate entered the retrieval set."""

    DETERMINISTIC_ID = "DETERMINISTIC_ID"
    DETERMINISTIC_SCOPE = "DETERMINISTIC_SCOPE"
    SEMANTIC_DISCOVERY = "SEMANTIC_DISCOVERY"


class EvidenceRole(StrEnum):
    """Role of retrieved material inside a bounded context package."""

    CURRENT_OBSERVATION = "CURRENT_OBSERVATION"
    DECLARED_CONFIGURATION = "DECLARED_CONFIGURATION"
    TOPOLOGY = "TOPOLOGY"
    PROCEDURE = "PROCEDURE"
    HISTORICAL_OBSERVATION = "HISTORICAL_OBSERVATION"
    ANALYTICAL_FINDING = "ANALYTICAL_FINDING"
    GENERATED_SUMMARY = "GENERATED_SUMMARY"


class ContextUse(StrEnum):
    """Whether a retrieved item may be treated as source evidence or context only."""

    EVIDENCE = "EVIDENCE"
    CONTEXT_ONLY = "CONTEXT_ONLY"


_SOURCE_EVIDENCE_ROLES = {
    EvidenceRole.CURRENT_OBSERVATION,
    EvidenceRole.DECLARED_CONFIGURATION,
    EvidenceRole.TOPOLOGY,
    EvidenceRole.PROCEDURE,
    EvidenceRole.HISTORICAL_OBSERVATION,
}

_CURRENT_CONFIG_ROLES = {
    EvidenceRole.CURRENT_OBSERVATION,
    EvidenceRole.DECLARED_CONFIGURATION,
    EvidenceRole.TOPOLOGY,
    EvidenceRole.PROCEDURE,
}

_ROLE_ORDER = {
    EvidenceRole.CURRENT_OBSERVATION: 0,
    EvidenceRole.DECLARED_CONFIGURATION: 1,
    EvidenceRole.TOPOLOGY: 2,
    EvidenceRole.PROCEDURE: 3,
    EvidenceRole.HISTORICAL_OBSERVATION: 4,
    EvidenceRole.ANALYTICAL_FINDING: 5,
    EvidenceRole.GENERATED_SUMMARY: 6,
}

CLAIM_BOUNDARY = (
    "retrieval != diagnosis",
    "semantic_similarity != evidentiary_authority",
    "generated_summary != source_evidence",
    "historical_pattern != current_root_cause",
    "recommendation != authorized_action",
    "sensor_value != verified_physical_state",
)


def _required_text(name: str, value: object) -> str:
    if not isinstance(value, str) or not value.strip():
        raise ReasoningContextError(f"{name} must be a non-empty string")
    return value.strip()


@dataclass(frozen=True, slots=True)
class ReasoningContextRequest:
    """Bounded context request evaluated before any model invocation."""

    asset_id: str
    purpose: str
    current_configuration_version: str | None = None
    include_historical: bool = True
    include_semantic_discovery: bool = True
    include_generated_context: bool = True
    max_items: int = 32

    def __post_init__(self) -> None:
        object.__setattr__(self, "asset_id", _required_text("asset_id", self.asset_id))
        object.__setattr__(self, "purpose", _required_text("purpose", self.purpose))
        if self.current_configuration_version is not None:
            object.__setattr__(
                self,
                "current_configuration_version",
                _required_text(
                    "current_configuration_version",
                    self.current_configuration_version,
                ),
            )
        if self.max_items < 1 or self.max_items > 256:
            raise ReasoningContextError("max_items must be between 1 and 256")


@dataclass(frozen=True, slots=True)
class EvidenceCandidate:
    """One immutable retrieval candidate with its original provenance."""

    evidence_id: str
    asset_id: str
    source_id: str
    source_class: str
    evidence_role: EvidenceRole
    retrieval_method: RetrievalMethod
    content: Mapping[str, Any]
    provenance: tuple[str, ...]
    semantic_admitted: bool = True
    binding_verified: bool = True
    invalidated: bool = False
    superseded_by: str | None = None
    configuration_version: str | None = None
    observed_at: str | None = None
    authority_class: str | None = None
    tags: Mapping[str, str] = field(default_factory=dict)

    def __post_init__(self) -> None:
        for name in ("evidence_id", "asset_id", "source_id", "source_class"):
            object.__setattr__(self, name, _required_text(name, getattr(self, name)))
        if not isinstance(self.content, Mapping) or not self.content:
            raise ReasoningContextError("content must be a non-empty mapping")
        if not self.provenance:
            raise ReasoningContextError("provenance must contain at least one source reference")
        normalized_provenance = tuple(
            _required_text("provenance item", item) for item in self.provenance
        )
        object.__setattr__(self, "provenance", normalized_provenance)
        if self.superseded_by is not None:
            object.__setattr__(
                self,
                "superseded_by",
                _required_text("superseded_by", self.superseded_by),
            )
        if self.configuration_version is not None:
            object.__setattr__(
                self,
                "configuration_version",
                _required_text("configuration_version", self.configuration_version),
            )
        if self.observed_at is not None:
            object.__setattr__(self, "observed_at", _required_text("observed_at", self.observed_at))
        if self.authority_class is not None:
            object.__setattr__(
                self,
                "authority_class",
                _required_text("authority_class", self.authority_class),
            )
        object.__setattr__(self, "content", MappingProxyType(dict(self.content)))
        object.__setattr__(
            self,
            "tags",
            MappingProxyType(
                dict(
                    sorted(
                        (
                            _required_text("tag key", key),
                            _required_text("tag value", value),
                        )
                        for key, value in self.tags.items()
                    )
                )
            ),
        )


def reasoning_context_request_from_dict(payload: Mapping[str, Any]) -> ReasoningContextRequest:
    """Load a request from a JSON-compatible mapping."""

    return ReasoningContextRequest(
        asset_id=payload.get("asset_id", ""),
        purpose=payload.get("purpose", ""),
        current_configuration_version=payload.get("current_configuration_version"),
        include_historical=bool(payload.get("include_historical", True)),
        include_semantic_discovery=bool(payload.get("include_semantic_discovery", True)),
        include_generated_context=bool(payload.get("include_generated_context", True)),
        max_items=int(payload.get("max_items", 32)),
    )


def evidence_candidate_from_dict(payload: Mapping[str, Any]) -> EvidenceCandidate:
    """Load one provenance-preserving candidate from JSON-compatible input."""

    role_value = payload.get("evidence_role")
    method_value = payload.get("retrieval_method")
    if not isinstance(role_value, str) or not isinstance(method_value, str):
        raise ReasoningContextError("evidence_role and retrieval_method must be strings")
    try:
        role = EvidenceRole(role_value)
        method = RetrievalMethod(method_value)
    except ValueError as exc:
        raise ReasoningContextError("unsupported evidence_role or retrieval_method") from exc
    provenance = payload.get("provenance", ())
    if not isinstance(provenance, Sequence) or isinstance(provenance, (str, bytes)):
        raise ReasoningContextError("provenance must be an array of source references")
    tags = payload.get("tags", {})
    if not isinstance(tags, Mapping):
        raise ReasoningContextError("tags must be an object")
    content = payload.get("content", {})
    if not isinstance(content, Mapping):
        raise ReasoningContextError("content must be an object")
    return EvidenceCandidate(
        evidence_id=payload.get("evidence_id", ""),
        asset_id=payload.get("asset_id", ""),
        source_id=payload.get("source_id", ""),
        source_class=payload.get("source_class", ""),
        evidence_role=role,
        retrieval_method=method,
        content=content,
        provenance=tuple(provenance),
        semantic_admitted=payload.get("semantic_admitted") is True,
        binding_verified=payload.get("binding_verified") is True,
        invalidated=payload.get("invalidated") is True,
        superseded_by=payload.get("superseded_by"),
        configuration_version=payload.get("configuration_version"),
        observed_at=payload.get("observed_at"),
        authority_class=payload.get("authority_class"),
        tags=tags,
    )


def _candidate_to_dict(candidate: EvidenceCandidate) -> dict[str, Any]:
    return {
        "evidence_id": candidate.evidence_id,
        "asset_id": candidate.asset_id,
        "source_id": candidate.source_id,
        "source_class": candidate.source_class,
        "evidence_role": candidate.evidence_role.value,
        "retrieval_method": candidate.retrieval_method.value,
        "content": dict(candidate.content),
        "provenance": list(candidate.provenance),
        "semantic_admitted": candidate.semantic_admitted,
        "binding_verified": candidate.binding_verified,
        "invalidated": candidate.invalidated,
        "superseded_by": candidate.superseded_by,
        "configuration_version": candidate.configuration_version,
        "observed_at": candidate.observed_at,
        "authority_class": candidate.authority_class,
        "tags": dict(candidate.tags),
    }


def _canonical_json(payload: object) -> str:
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def _refusal(candidate: EvidenceCandidate, reason_code: str) -> dict[str, Any]:
    return {
        "evidence_id": candidate.evidence_id,
        "source_id": candidate.source_id,
        "evidence_role": candidate.evidence_role.value,
        "reason_code": reason_code,
    }


def _classify_candidate(
    request: ReasoningContextRequest,
    candidate: EvidenceCandidate,
) -> tuple[ContextUse | None, str]:
    if candidate.asset_id != request.asset_id:
        return None, "RETRIEVAL.ASSET_SCOPE_MISMATCH"
    if candidate.invalidated:
        return None, "RETRIEVAL.INVALIDATED_EVIDENCE_REFUSED"
    if candidate.superseded_by is not None:
        return None, "RETRIEVAL.SUPERSEDED_EVIDENCE_REFUSED"
    if not candidate.semantic_admitted:
        return None, "RETRIEVAL.SEMANTICALLY_INADMISSIBLE"
    if candidate.evidence_role in _SOURCE_EVIDENCE_ROLES and not candidate.binding_verified:
        return None, "RETRIEVAL.SOURCE_BINDING_UNVERIFIED"
    if candidate.evidence_role in _SOURCE_EVIDENCE_ROLES and candidate.authority_class is None:
        return None, "RETRIEVAL.SOURCE_AUTHORITY_UNDECLARED"
    if (
        candidate.evidence_role is EvidenceRole.HISTORICAL_OBSERVATION
        and not request.include_historical
    ):
        return None, "RETRIEVAL.HISTORICAL_CONTEXT_DISABLED"
    if (
        candidate.evidence_role is EvidenceRole.GENERATED_SUMMARY
        and not request.include_generated_context
    ):
        return None, "RETRIEVAL.GENERATED_CONTEXT_DISABLED"
    if candidate.retrieval_method is RetrievalMethod.SEMANTIC_DISCOVERY:
        if not request.include_semantic_discovery:
            return None, "RETRIEVAL.SEMANTIC_DISCOVERY_DISABLED"
        return ContextUse.CONTEXT_ONLY, "RETRIEVAL.SEMANTIC_DISCOVERY_CONTEXT_ONLY"

    requested_config = request.current_configuration_version
    if requested_config is not None and candidate.evidence_role in _CURRENT_CONFIG_ROLES:
        if candidate.configuration_version is None:
            return None, "RETRIEVAL.CURRENT_CONFIGURATION_UNDECLARED"
        if candidate.configuration_version != requested_config:
            return None, "RETRIEVAL.CURRENT_CONFIGURATION_MISMATCH"
    if (
        requested_config is not None
        and candidate.evidence_role is EvidenceRole.HISTORICAL_OBSERVATION
    ):
        if candidate.configuration_version is None:
            return ContextUse.CONTEXT_ONLY, "RETRIEVAL.HISTORICAL_CONFIGURATION_UNKNOWN"
        if candidate.configuration_version != requested_config:
            return ContextUse.CONTEXT_ONLY, "RETRIEVAL.HISTORICAL_CONFIGURATION_CONTEXT_ONLY"

    if candidate.evidence_role in {
        EvidenceRole.ANALYTICAL_FINDING,
        EvidenceRole.GENERATED_SUMMARY,
    }:
        return ContextUse.CONTEXT_ONLY, "RETRIEVAL.DERIVED_CONTEXT_ONLY"

    return ContextUse.EVIDENCE, "RETRIEVAL.SOURCE_EVIDENCE_ADMITTED"


def _sort_key(candidate: EvidenceCandidate) -> tuple[int, str, str, str]:
    return (
        _ROLE_ORDER[candidate.evidence_role],
        candidate.source_class,
        candidate.source_id,
        candidate.evidence_id,
    )


def assemble_reasoning_context(
    request: ReasoningContextRequest,
    candidates: Sequence[EvidenceCandidate],
) -> dict[str, Any]:
    """Build a deterministic context package without invoking an LLM or vector search."""

    grouped: dict[str, list[EvidenceCandidate]] = {}
    for candidate in candidates:
        grouped.setdefault(candidate.evidence_id, []).append(candidate)

    normalized: list[EvidenceCandidate] = []
    refusals: list[dict[str, Any]] = []
    for evidence_id in sorted(grouped):
        group = grouped[evidence_id]
        variants = {_canonical_json(_candidate_to_dict(item)) for item in group}
        if len(variants) > 1:
            representative = sorted(group, key=_sort_key)[0]
            refusals.append(
                _refusal(representative, "RETRIEVAL.DUPLICATE_EVIDENCE_ID_CONFLICT")
            )
            continue
        normalized.append(group[0])

    evidence: list[dict[str, Any]] = []
    context_only: list[dict[str, Any]] = []
    accepted_count = 0

    for candidate in sorted(normalized, key=_sort_key):
        context_use, reason_code = _classify_candidate(request, candidate)
        if context_use is None:
            refusals.append(_refusal(candidate, reason_code))
            continue
        if accepted_count >= request.max_items:
            refusals.append(_refusal(candidate, "RETRIEVAL.CONTEXT_LIMIT_REACHED"))
            continue

        entry = {
            "context_use": context_use.value,
            "reason_code": reason_code,
            "candidate": _candidate_to_dict(candidate),
        }
        if context_use is ContextUse.EVIDENCE:
            evidence.append(entry)
        else:
            context_only.append(entry)
        accepted_count += 1

    body: dict[str, Any] = {
        "schema_version": "linealert.reasoning-context-bundle.v1",
        "scope": "retrieval_context_only",
        "request": asdict(request),
        "evidence": evidence,
        "context_only": context_only,
        "refusals": sorted(
            refusals,
            key=lambda item: (
                item["evidence_id"],
                item["reason_code"],
                item["source_id"],
            ),
        ),
        "counts": {
            "candidate_count": len(candidates),
            "evidence_count": len(evidence),
            "context_only_count": len(context_only),
            "refusal_count": len(refusals),
        },
        "retrieval_policy": {
            "deterministic_assembly": True,
            "semantic_discovery_confers_authority": False,
            "generated_content_confers_authority": False,
            "source_content_mutated": False,
            "ranking_confers_authority": False,
            "model_invoked": False,
        },
        "claim_boundary": list(CLAIM_BOUNDARY),
        "diagnosis_established": False,
        "authorized_action": False,
    }
    body["bundle_sha256"] = hashlib.sha256(_canonical_json(body).encode("utf-8")).hexdigest()
    return body


def _load_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Build a deterministic LineAlert reasoning-node context bundle."
    )
    parser.add_argument("--request", type=Path, required=True)
    parser.add_argument("--candidates", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    try:
        request_payload = _load_json(args.request)
        candidate_payload = _load_json(args.candidates)
        if not isinstance(request_payload, Mapping):
            raise ReasoningContextError("request JSON must be an object")
        if not isinstance(candidate_payload, list):
            raise ReasoningContextError("candidates JSON must be an array")
        request = reasoning_context_request_from_dict(request_payload)
        candidates = [
            evidence_candidate_from_dict(item)
            for item in candidate_payload
            if isinstance(item, Mapping)
        ]
        if len(candidates) != len(candidate_payload):
            raise ReasoningContextError("every candidate must be an object")
        bundle = assemble_reasoning_context(request, candidates)
    except (OSError, json.JSONDecodeError, ReasoningContextError) as exc:
        print(
            json.dumps(
                {
                    "schema_version": "linealert.reasoning-context-bundle.v1",
                    "passed": False,
                    "error": type(exc).__name__,
                    "detail": str(exc),
                    "authorized_action": False,
                },
                indent=2,
                sort_keys=True,
            ),
            file=sys.stderr,
        )
        return 2

    rendered = json.dumps(bundle, indent=2, sort_keys=True)
    if args.output is None:
        print(rendered)
    else:
        args.output.write_text(f"{rendered}\n", encoding="utf-8")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
