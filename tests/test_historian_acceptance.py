from __future__ import annotations

import copy

from linealert_core.historian_acceptance import (
    evaluate_historian_acceptance,
    main,
)

SHA = "a" * 64
ASSET = "LABELER-DEMO-01"
RELATIONSHIP = "relationship:label-presentation-delay"
POLICY = "label-presentation-persistence-v1"


def _authority() -> dict[str, object]:
    return {
        "schema_version": "linealert.condition-evidence-authority.v1",
        "authority_scope": "HISTORIAN_WRITE_TIME_POLICY_AUTHORITY",
        "configuration": {
            "asset_id": ASSET,
            "profile_id": "generic-pressure-sensitive-labeler-demo-v1",
            "source_name": "labeler_demo_config.json",
            "source_sha256": SHA,
        },
        "persistence_policy": {
            "asset_id": ASSET,
            "profile_id": "generic-pressure-sensitive-labeler-demo-v1",
            "source_name": "labeler_demo_config.json",
            "source_sha256": SHA,
            "policy": {
                "policy_id": POLICY,
                "policy_revision": "1",
                "relationship_id": RELATIONSHIP,
                "required_outside": 3,
                "window_size": 4,
                "authority_class": "DECLARED_CONFIGURATION",
            },
        },
    }


def _fixtures() -> tuple[
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
    dict[str, object],
]:
    status: dict[str, object] = {
        "connected": True,
        "source_available": True,
        "localization_topology_asset_id": ASSET,
        "localization_topology_source_sha256": SHA,
        "localization_persistence_policy_count": 1,
    }
    rows = [
        {
            "observation_id": f"obs-{index}",
            "relationship_id": RELATIONSHIP,
            "evidence_authority": _authority(),
        }
        for index in range(4)
    ]
    history: dict[str, object] = {
        "count": 4,
        "truncated": False,
        "measurements": rows,
    }
    direct: dict[str, object] = {
        "schema_version": "linealert.configured-condition-localization.v1",
        "disposition": "READY",
        "localization": {"disposition": "PERSISTENCE_ESTABLISHED"},
        "persistence_policy": {
            "policy": {
                "policy_id": POLICY,
                "policy_revision": "1",
            }
        },
        "policy_application": {
            "historical_policy_equivalence": "VERIFIED",
            "reason_code": "POLICY.HISTORICAL_AUTHORITY_EQUIVALENT",
        },
    }
    proxy = copy.deepcopy(direct)
    db_summary: dict[str, object] = {
        "row_count": 4,
        "authority_count": 4,
        "authority_null_count": 0,
        "config_shas": [SHA],
        "target_row_count": 4,
        "target_policy_count": 4,
        "policy_ids": [POLICY],
    }
    return status, history, direct, proxy, db_summary


def _evaluate(
    *,
    status: dict[str, object] | None = None,
    history: dict[str, object] | None = None,
    direct: dict[str, object] | None = None,
    proxy: dict[str, object] | None = None,
    db_summary: dict[str, object] | None = None,
    ui_root_ok: bool = True,
):
    base = _fixtures()
    return evaluate_historian_acceptance(
        status=status or base[0],
        history=history or base[1],
        direct=direct or base[2],
        proxy=proxy or base[3],
        db_summary=db_summary or base[4],
        ui_root_ok=ui_root_ok,
        asset_id=ASSET,
        target_relationship_id=RELATIONSHIP,
        expected_policy_id=POLICY,
        expected_policy_revision="1",
    )


def _check(report, check_id: str):
    return next(check for check in report.checks if check.check_id == check_id)


def test_controlled_synthetic_exact_evidence_passes() -> None:
    report = _evaluate()

    assert report.passed is True
    assert report.scope == "controlled_synthetic_demo"
    assert all(check.passed for check in report.checks)


def test_missing_retained_authority_fails_closed() -> None:
    _, history, _, _, _ = _fixtures()
    history = copy.deepcopy(history)
    rows = history["measurements"]
    assert isinstance(rows, list)
    rows[0]["evidence_authority"] = None

    report = _evaluate(history=history)

    assert report.passed is False
    assert _check(report, "HISTORY.AUTHORITY_RETAINED").passed is False


def test_unverified_localization_equivalence_fails_acceptance() -> None:
    _, _, direct, _, _ = _fixtures()
    direct = copy.deepcopy(direct)
    application = direct["policy_application"]
    assert isinstance(application, dict)
    application["historical_policy_equivalence"] = "UNVERIFIED"
    application["reason_code"] = "POLICY.HISTORICAL_AUTHORITY_INCOMPLETE"
    proxy = copy.deepcopy(direct)

    report = _evaluate(direct=direct, proxy=proxy)

    assert report.passed is False
    assert _check(report, "LOCALIZATION.HISTORICAL_EQUIVALENCE").passed is False


def test_proxy_semantic_mismatch_fails_acceptance() -> None:
    _, _, direct, proxy, _ = _fixtures()
    proxy = copy.deepcopy(proxy)
    application = proxy["policy_application"]
    assert isinstance(application, dict)
    application["historical_policy_equivalence"] = "CONFLICT"

    report = _evaluate(direct=direct, proxy=proxy)

    assert report.passed is False
    assert _check(report, "PROXY.PARITY").passed is False


def test_database_authority_null_fails_acceptance() -> None:
    _, _, _, _, db_summary = _fixtures()
    db_summary = copy.deepcopy(db_summary)
    db_summary["authority_count"] = 3
    db_summary["authority_null_count"] = 1

    report = _evaluate(db_summary=db_summary)

    assert report.passed is False
    assert _check(report, "DB.ROW_PARITY").passed is False


def test_unavailable_ui_root_fails_acceptance() -> None:
    report = _evaluate(ui_root_ok=False)

    assert report.passed is False
    assert _check(report, "UI.ROOT_AVAILABLE").passed is False


def test_cli_requires_explicit_dsn_when_environment_is_empty(
    monkeypatch,
    capsys,
) -> None:
    monkeypatch.delenv("LINEALERT_HISTORIAN_DSN", raising=False)

    assert main([]) == 2
    assert "--dsn or LINEALERT_HISTORIAN_DSN is required" in capsys.readouterr().err


def test_missing_target_policy_row_fails_acceptance() -> None:
    _, _, _, _, db_summary = _fixtures()
    db_summary = copy.deepcopy(db_summary)
    db_summary["target_policy_count"] = 3

    report = _evaluate(db_summary=db_summary)

    assert report.passed is False
    assert _check(report, "DB.TARGET_POLICY").passed is False
