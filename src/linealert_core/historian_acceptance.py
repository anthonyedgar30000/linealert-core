"""Read-only live acceptance checks for the controlled synthetic historian path."""

from __future__ import annotations

import argparse
import json
import os
import sys
from dataclasses import asdict, dataclass
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen

CLAIM_BOUNDARY = (
    "This acceptance verifies the controlled synthetic local persistence/API/proxy "
    "contract only. It does not establish production equipment connectivity, physical "
    "root cause, verified physical state, safety approval, or authorized control."
)


@dataclass(frozen=True, slots=True)
class AcceptanceCheck:
    check_id: str
    passed: bool
    detail: str


@dataclass(frozen=True, slots=True)
class HistorianAcceptanceReport:
    schema_version: str
    scope: str
    passed: bool
    checks: tuple[AcceptanceCheck, ...]
    claim_boundary: str

    def to_dict(self) -> dict[str, object]:
        return {
            "schema_version": self.schema_version,
            "scope": self.scope,
            "passed": self.passed,
            "checks": [asdict(check) for check in self.checks],
            "claim_boundary": self.claim_boundary,
        }


def _get(payload: dict[str, Any], *path: str) -> Any:
    value: Any = payload
    for key in path:
        if not isinstance(value, dict):
            return None
        value = value.get(key)
    return value


def _check(check_id: str, condition: bool, detail: str) -> AcceptanceCheck:
    return AcceptanceCheck(check_id=check_id, passed=bool(condition), detail=detail)


def evaluate_historian_acceptance(
    *,
    status: dict[str, Any],
    history: dict[str, Any],
    direct: dict[str, Any],
    proxy: dict[str, Any],
    db_summary: dict[str, Any],
    ui_root_ok: bool,
    asset_id: str,
    target_relationship_id: str,
    expected_policy_id: str,
    expected_policy_revision: str,
) -> HistorianAcceptanceReport:
    """Evaluate already-read acceptance evidence without performing I/O."""

    measurements = history.get("measurements")
    rows = measurements if isinstance(measurements, list) else []
    target_rows = [row for row in rows if row.get("relationship_id") == target_relationship_id]
    retained = [row for row in rows if isinstance(row.get("evidence_authority"), dict)]
    status_sha = status.get("localization_topology_source_sha256")

    history_shas = sorted(
        {
            _get(row["evidence_authority"], "configuration", "source_sha256")
            for row in retained
            if _get(row["evidence_authority"], "configuration", "source_sha256")
        }
    )
    target_policy_values = [
        (
            _get(
                row["evidence_authority"],
                "persistence_policy",
                "policy",
                "policy_id",
            )
            if isinstance(row.get("evidence_authority"), dict)
            else None
        )
        for row in target_rows
    ]
    history_policy_ids = sorted({value for value in target_policy_values if isinstance(value, str)})

    checks = [
        _check(
            "HISTORIAN.CONNECTED",
            status.get("connected") is True and status.get("source_available") is True,
            (
                f"connected={status.get('connected')} "
                f"source_available={status.get('source_available')}"
            ),
        ),
        _check(
            "HISTORIAN.CONFIG_AUTHORITY",
            status.get("localization_topology_asset_id") == asset_id
            and isinstance(status_sha, str)
            and len(status_sha) == 64
            and int(status.get("localization_persistence_policy_count") or 0) >= 1,
            (
                f"asset={status.get('localization_topology_asset_id')} sha={status_sha} "
                "policy_count="
                f"{status.get('localization_persistence_policy_count')}"
            ),
        ),
        _check(
            "HISTORY.COMPLETE",
            history.get("truncated") is False
            and len(rows) > 0
            and history.get("count") == len(rows),
            f"count={history.get('count')} rows={len(rows)} truncated={history.get('truncated')}",
        ),
        _check(
            "HISTORY.AUTHORITY_RETAINED",
            len(retained) == len(rows),
            f"retained={len(retained)} selected={len(rows)}",
        ),
        _check(
            "HISTORY.CONFIG_SHA",
            bool(status_sha) and history_shas == [status_sha],
            f"history_shas={history_shas} status_sha={status_sha}",
        ),
        _check(
            "HISTORY.TARGET_POLICY",
            len(target_rows) > 0
            and history_policy_ids == [expected_policy_id]
            and all(value == expected_policy_id for value in target_policy_values),
            (
                f"target_rows={len(target_rows)} policy_ids={history_policy_ids} "
                f"policy_values={target_policy_values}"
            ),
        ),
        _check(
            "DB.ROW_PARITY",
            db_summary.get("row_count") == len(rows)
            and db_summary.get("authority_count") == len(rows)
            and db_summary.get("authority_null_count") == 0,
            (
                f"db_rows={db_summary.get('row_count')} api_rows={len(rows)} "
                f"db_authority={db_summary.get('authority_count')} "
                f"db_null={db_summary.get('authority_null_count')}"
            ),
        ),
        _check(
            "DB.CONFIG_SHA",
            db_summary.get("config_shas") == [status_sha],
            f"db_shas={db_summary.get('config_shas')} status_sha={status_sha}",
        ),
        _check(
            "DB.TARGET_POLICY",
            db_summary.get("target_row_count", 0) > 0
            and db_summary.get("target_policy_count") == db_summary.get("target_row_count")
            and db_summary.get("policy_ids") == [expected_policy_id],
            (
                f"target_rows={db_summary.get('target_row_count')} "
                f"policy_rows={db_summary.get('target_policy_count')} "
                f"db_policy_ids={db_summary.get('policy_ids')}"
            ),
        ),
        _check(
            "LOCALIZATION.READY",
            direct.get("disposition") == "READY"
            and _get(direct, "localization", "disposition") == "PERSISTENCE_ESTABLISHED",
            (
                f"disposition={direct.get('disposition')} "
                f"localization={_get(direct, 'localization', 'disposition')}"
            ),
        ),
        _check(
            "LOCALIZATION.POLICY",
            _get(direct, "persistence_policy", "policy", "policy_id") == expected_policy_id
            and str(_get(direct, "persistence_policy", "policy", "policy_revision"))
            == expected_policy_revision,
            (
                f"policy={_get(direct, 'persistence_policy', 'policy', 'policy_id')} "
                f"revision={_get(direct, 'persistence_policy', 'policy', 'policy_revision')}"
            ),
        ),
        _check(
            "LOCALIZATION.HISTORICAL_EQUIVALENCE",
            _get(direct, "policy_application", "historical_policy_equivalence") == "VERIFIED"
            and _get(direct, "policy_application", "reason_code")
            == "POLICY.HISTORICAL_AUTHORITY_EQUIVALENT",
            (
                "equivalence="
                f"{_get(direct, 'policy_application', 'historical_policy_equivalence')} "
                f"reason={_get(direct, 'policy_application', 'reason_code')}"
            ),
        ),
    ]

    parity_paths = (
        ("schema_version",),
        ("disposition",),
        ("localization", "disposition"),
        ("persistence_policy", "policy", "policy_id"),
        ("persistence_policy", "policy", "policy_revision"),
        ("policy_application", "historical_policy_equivalence"),
        ("policy_application", "reason_code"),
    )
    mismatches = [
        ".".join(path) for path in parity_paths if _get(direct, *path) != _get(proxy, *path)
    ]
    checks.append(
        _check(
            "PROXY.PARITY",
            not mismatches,
            f"mismatches={mismatches}",
        )
    )
    checks.append(
        _check(
            "UI.ROOT_AVAILABLE",
            ui_root_ok,
            f"ui_root_ok={ui_root_ok}",
        )
    )

    passed = all(check.passed for check in checks)
    return HistorianAcceptanceReport(
        schema_version="linealert.local-historian-acceptance.v1",
        scope="controlled_synthetic_demo",
        passed=passed,
        checks=tuple(checks),
        claim_boundary=CLAIM_BOUNDARY,
    )


def _fetch_json(url: str) -> dict[str, Any]:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - bounded local acceptance URL
        payload = json.load(response)
    if not isinstance(payload, dict):
        raise ValueError(f"expected JSON object from {url}")
    return payload


def _fetch_ui_root(url: str) -> bool:
    with urlopen(url, timeout=5) as response:  # noqa: S310 - bounded local acceptance URL
        body = response.read().decode("utf-8", "replace")
        return response.status == 200 and "LineAlert" in body


def _read_db_summary(
    dsn: str,
    *,
    asset_id: str,
    episode_id: str,
    target_relationship_id: str,
) -> dict[str, Any]:
    try:
        import psycopg
    except ImportError as exc:  # pragma: no cover - environment contract
        raise RuntimeError(
            "psycopg is required; install the historian optional dependency"
        ) from exc

    query = """
        SELECT
            count(*),
            count(evidence_authority),
            count(*) FILTER (WHERE evidence_authority IS NULL),
            array_remove(
                array_agg(DISTINCT evidence_authority->'configuration'->>'source_sha256'),
                NULL
            )
        FROM condition_measurements
        WHERE asset_id = %s AND episode_id = %s
    """
    policy_query = """
        SELECT
            count(*),
            count(
                evidence_authority->'persistence_policy'->'policy'->>'policy_id'
            ),
            array_remove(
                array_agg(
                    DISTINCT evidence_authority->'persistence_policy'->'policy'->>'policy_id'
                ),
                NULL
            )
        FROM condition_measurements
        WHERE asset_id = %s AND episode_id = %s AND relationship_id = %s
    """
    with psycopg.connect(
        dsn,
        options="-c default_transaction_read_only=on",
    ) as connection:
        with connection.cursor() as cursor:
            cursor.execute(query, (asset_id, episode_id))
            summary_row = cursor.fetchone()
            if summary_row is None:
                raise RuntimeError("condition history acceptance query returned no row")
            row_count, authority_count, null_count, config_shas = summary_row
            cursor.execute(
                policy_query,
                (asset_id, episode_id, target_relationship_id),
            )
            policy_row = cursor.fetchone()
            if policy_row is None:
                raise RuntimeError("condition policy acceptance query returned no row")
            target_row_count, target_policy_count, policy_ids = policy_row

    return {
        "row_count": row_count,
        "authority_count": authority_count,
        "authority_null_count": null_count,
        "config_shas": sorted(config_shas or []),
        "target_row_count": target_row_count,
        "target_policy_count": target_policy_count,
        "policy_ids": sorted(policy_ids or []),
    }


def run_historian_acceptance(
    *,
    historian_url: str,
    proxy_url: str,
    ui_url: str,
    dsn: str,
    asset_id: str,
    episode_id: str,
    target_relationship_id: str,
    expected_policy_id: str,
    expected_policy_revision: str,
    limit: int,
) -> HistorianAcceptanceReport:
    query = urlencode(
        {
            "asset_id": asset_id,
            "episode_id": episode_id,
            "limit": str(limit),
        }
    )
    localization_query = urlencode(
        {
            "asset_id": asset_id,
            "selection_label": "Live Timescale acceptance",
            "target_relationship_id": target_relationship_id,
            "episode_id": episode_id,
            "limit": str(limit),
        }
    )

    status = _fetch_json(f"{historian_url.rstrip('/')}/api/status")
    history = _fetch_json(f"{historian_url.rstrip('/')}/api/history/conditions?{query}")
    direct = _fetch_json(
        f"{historian_url.rstrip('/')}/api/history/conditions/localize?{localization_query}"
    )
    proxy = _fetch_json(
        f"{proxy_url.rstrip('/')}/api/historian/conditions/localize?{localization_query}"
    )
    db_summary = _read_db_summary(
        dsn,
        asset_id=asset_id,
        episode_id=episode_id,
        target_relationship_id=target_relationship_id,
    )
    ui_root_ok = _fetch_ui_root(ui_url)

    return evaluate_historian_acceptance(
        status=status,
        history=history,
        direct=direct,
        proxy=proxy,
        db_summary=db_summary,
        ui_root_ok=ui_root_ok,
        asset_id=asset_id,
        target_relationship_id=target_relationship_id,
        expected_policy_id=expected_policy_id,
        expected_policy_revision=expected_policy_revision,
    )


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Read-only acceptance check for the controlled synthetic historian path."
    )
    parser.add_argument(
        "--historian-url",
        default="http://127.0.0.1:8767",
    )
    parser.add_argument(
        "--proxy-url",
        default="http://127.0.0.1:8766",
    )
    parser.add_argument(
        "--ui-url",
        default="http://127.0.0.1:8766/",
    )
    parser.add_argument(
        "--dsn",
        default=os.environ.get("LINEALERT_HISTORIAN_DSN"),
    )
    parser.add_argument("--asset-id", default="LABELER-DEMO-01")
    parser.add_argument("--episode-id", default="condition-runtime-replay")
    parser.add_argument(
        "--target-relationship-id",
        default="relationship:label-presentation-delay",
    )
    parser.add_argument(
        "--expected-policy-id",
        default="label-presentation-persistence-v1",
    )
    parser.add_argument("--expected-policy-revision", default="1")
    parser.add_argument("--limit", type=int, default=100)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if not args.dsn:
        print(
            "ERROR: --dsn or LINEALERT_HISTORIAN_DSN is required",
            file=sys.stderr,
        )
        return 2
    if args.limit < 1 or args.limit > 5000:
        print("ERROR: --limit must be between 1 and 5000", file=sys.stderr)
        return 2

    try:
        report = run_historian_acceptance(
            historian_url=args.historian_url,
            proxy_url=args.proxy_url,
            ui_url=args.ui_url,
            dsn=args.dsn,
            asset_id=args.asset_id,
            episode_id=args.episode_id,
            target_relationship_id=args.target_relationship_id,
            expected_policy_id=args.expected_policy_id,
            expected_policy_revision=args.expected_policy_revision,
            limit=args.limit,
        )
    except Exception as exc:
        print(
            json.dumps(
                {
                    "schema_version": "linealert.local-historian-acceptance.v1",
                    "scope": "controlled_synthetic_demo",
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
