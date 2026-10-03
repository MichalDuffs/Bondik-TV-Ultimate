import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.audit_office import (
    ENTRY_PROTOCOL,
    CityAuditError,
    ReviewAuditLedger,
    build_audit_entry,
    load_contract,
)
from tools.city.permit_office import (
    prepare_permit_request,
)
from tools.city.review_board import (
    record_human_review,
)
from tools.city.storage_adapter import (
    MemoryStorageAdapter,
)


ROOT = Path(__file__).resolve().parents[3]


def permit():
    return prepare_permit_request(
        ticket_id="permit-001",
        principal={
            "id": "demo-agent",
            "role": "observer",
        },
        operation="command",
        capability_id=(
            "city.command-boundary.local"
        ),
        reason="Need human review.",
        requested_at=(
            "2026-10-03T20:45:00+02:00"
        ),
    )


def review(value=None):
    value = value or permit()
    return record_human_review(
        value,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T20:46:00+02:00"
        ),
        note="Approved review record.",
    )


def test_build_entry_preserves_non_granting_boundary():
    p = permit()
    r = review(p)
    entry = build_audit_entry(
        p,
        r,
    )

    assert entry["protocol"] == (
        ENTRY_PROTOCOL
    )
    assert entry["grantsPermission"] is False
    assert entry["changesPolicy"] is False
    assert entry["executesAction"] is False


def test_entry_contains_sha256_digests():
    p = permit()
    r = review(p)
    entry = build_audit_entry(
        p,
        r,
    )

    assert entry["permitDigest"].startswith(
        "sha256:"
    )
    assert entry["reviewDigest"].startswith(
        "sha256:"
    )
    assert len(
        entry["permitDigest"]
    ) == 71
    assert len(
        entry["reviewDigest"]
    ) == 71


def test_entry_id_is_deterministic_per_ticket():
    p = permit()
    r = review(p)

    first = build_audit_entry(p, r)
    second = build_audit_entry(p, r)

    assert first["entryId"] == (
        second["entryId"]
    )


def test_record_is_create_once():
    p = permit()
    r = review(p)
    ledger = ReviewAuditLedger(
        MemoryStorageAdapter()
    )

    first = ledger.record(p, r)

    assert first["revision"] == 1

    with pytest.raises(
        CityAuditError,
        match="already exists",
    ):
        ledger.record(p, r)


def test_record_can_be_read_back():
    p = permit()
    r = review(p)
    ledger = ReviewAuditLedger(
        MemoryStorageAdapter()
    )

    stored = ledger.record(p, r)
    restored = ledger.read(
        stored["key"]
    )

    assert restored == stored


def test_list_entry_ids_is_sorted():
    storage = MemoryStorageAdapter()
    ledger = ReviewAuditLedger(storage)

    p1 = permit()
    r1 = review(p1)
    first = ledger.record(p1, r1)

    p2 = prepare_permit_request(
        ticket_id="permit-002",
        principal={
            "id": "demo-agent",
            "role": "observer",
        },
        operation="command",
        capability_id=(
            "city.command-boundary.local"
        ),
        reason="Need another review.",
        requested_at=(
            "2026-10-03T20:47:00+02:00"
        ),
    )
    r2 = review(p2)
    second = ledger.record(p2, r2)

    assert ledger.list_entry_ids() == sorted(
        [
            first["key"],
            second["key"],
        ]
    )


def test_review_must_match_exact_permit_snapshot():
    p = permit()
    r = review(p)
    broken = copy.deepcopy(r)
    broken["permit"]["route"][
        "locationId"
    ] = "wrong-place"

    with pytest.raises(
        CityAuditError,
        match="does not match permit",
    ):
        build_audit_entry(
            p,
            broken,
        )


def test_permission_granting_review_is_rejected():
    p = permit()
    r = review(p)
    r["grantsPermission"] = True

    with pytest.raises(
        CityAuditError,
        match="review must not grant permission",
    ):
        build_audit_entry(p, r)


def test_policy_changing_review_is_rejected():
    p = permit()
    r = review(p)
    r["changesPolicy"] = True

    with pytest.raises(
        CityAuditError,
        match="must not change policy",
    ):
        build_audit_entry(p, r)


def test_executing_review_is_rejected():
    p = permit()
    r = review(p)
    r["executesAction"] = True

    with pytest.raises(
        CityAuditError,
        match="must not execute action",
    ):
        build_audit_entry(p, r)


def test_inputs_are_not_mutated():
    p = permit()
    r = review(p)
    p_snapshot = copy.deepcopy(p)
    r_snapshot = copy.deepcopy(r)

    build_audit_entry(p, r)

    assert p == p_snapshot
    assert r == r_snapshot


def test_contract_is_create_once_record_only():
    contract = load_contract()

    assert contract["authority"] == (
        "record-only"
    )
    assert contract["writePolicy"] == (
        "create-once"
    )
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "append-only-wrapper",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyChange": "not-allowed",
    }


def test_underlying_storage_revision_stays_one():
    p = permit()
    r = review(p)
    ledger = ReviewAuditLedger(
        MemoryStorageAdapter()
    )

    stored = ledger.record(p, r)

    assert stored["revision"] == 1


def test_direct_cli_records_create_once_entry():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "audit_office.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Audit Office OK: "
        "review-recorded / revision=1 / "
        "permission=false / "
        "bondik-city-audit-entry/1"
        in result.stdout
    )
