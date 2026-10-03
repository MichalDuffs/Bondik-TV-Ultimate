from __future__ import annotations

import argparse
import copy
import hashlib
import json
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.permit_office import (
    PERMIT_PROTOCOL,
    CityPermitError,
    prepare_permit_request,
)
from tools.city.review_board import (
    REVIEW_PROTOCOL,
    CityReviewError,
    record_human_review,
)
from tools.city.storage_adapter import (
    MemoryStorageAdapter,
    StorageAdapter,
    StorageConflictError,
)

LEDGER_PROTOCOL = "bondik-city-audit-ledger/1"
ENTRY_PROTOCOL = "bondik-city-audit-entry/1"
VERSION = 1
DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-audit-ledger-contract.json"
)


class CityAuditError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityAuditError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityAuditError(
            f"{label} must be valid JSON"
        ) from error


def _canonical_bytes(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            ensure_ascii=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (TypeError, ValueError) as error:
        raise CityAuditError(
            "audit value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="audit ledger contract",
    )

    if not isinstance(payload, dict):
        raise CityAuditError(
            "audit ledger contract root must be an object"
        )

    if payload.get("protocol") != LEDGER_PROTOCOL:
        raise CityAuditError(
            "unsupported audit ledger protocol"
        )

    if payload.get("version") != VERSION:
        raise CityAuditError(
            "unsupported audit ledger version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityAuditError(
            "audit ledger cityId mismatch"
        )

    if payload.get("permitProtocol") != PERMIT_PROTOCOL:
        raise CityAuditError(
            "permit protocol mismatch"
        )

    if payload.get("reviewProtocol") != REVIEW_PROTOCOL:
        raise CityAuditError(
            "review protocol mismatch"
        )

    if payload.get("entryProtocol") != ENTRY_PROTOCOL:
        raise CityAuditError(
            "entry protocol mismatch"
        )

    if payload.get("namespace") != "city.audit.review":
        raise CityAuditError(
            "audit namespace mismatch"
        )

    if payload.get("authority") != "record-only":
        raise CityAuditError(
            "audit authority must be record-only"
        )

    if payload.get("writePolicy") != "create-once":
        raise CityAuditError(
            "audit write policy must be create-once"
        )

    if payload.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "append-only-wrapper",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyChange": "not-allowed",
    }:
        raise CityAuditError(
            "audit exposure contract invalid"
        )

    return payload


def _review_matches_permit(
    permit: dict[str, Any],
    review: dict[str, Any],
) -> bool:
    review_permit = review.get("permit")

    if not isinstance(review_permit, dict):
        return False

    return (
        review_permit.get("ticketId")
        == permit.get("ticketId")
        and review_permit.get("requestedAt")
        == permit.get("requestedAt")
        and review_permit.get("request")
        == permit.get("request")
        and review_permit.get("currentPolicy")
        == permit.get("currentPolicy")
        and review_permit.get("route")
        == permit.get("route")
    )


def build_audit_entry(
    permit: Any,
    review: Any,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(permit, dict):
        raise CityAuditError(
            "permit must be an object"
        )

    if not isinstance(review, dict):
        raise CityAuditError(
            "review must be an object"
        )

    if permit.get("protocol") != (
        contract["permitProtocol"]
    ):
        raise CityAuditError(
            "permit protocol mismatch"
        )

    if review.get("protocol") != (
        contract["reviewProtocol"]
    ):
        raise CityAuditError(
            "review protocol mismatch"
        )

    if permit.get("grantsPermission") is not False:
        raise CityAuditError(
            "permit must not grant permission"
        )

    if review.get("grantsPermission") is not False:
        raise CityAuditError(
            "review must not grant permission"
        )

    if review.get("changesPolicy") is not False:
        raise CityAuditError(
            "review must not change policy"
        )

    if review.get("executesAction") is not False:
        raise CityAuditError(
            "review must not execute action"
        )

    if not _review_matches_permit(
        permit,
        review,
    ):
        raise CityAuditError(
            "review does not match permit"
        )

    ticket_id = permit.get("ticketId")

    if (
        not isinstance(ticket_id, str)
        or not ticket_id
    ):
        raise CityAuditError(
            "permit ticketId is invalid"
        )

    ticket_hash = hashlib.sha256(
        ticket_id.encode("utf-8")
    ).hexdigest()

    return {
        "protocol": ENTRY_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "review-audit-entry",
        "entryId": (
            "review-" + ticket_hash[:24]
        ),
        "ticketId": ticket_id,
        "permitDigest": (
            "sha256:" + _sha256(permit)
        ),
        "reviewDigest": (
            "sha256:" + _sha256(review)
        ),
        "permit": copy.deepcopy(
            permit
        ),
        "review": copy.deepcopy(
            review
        ),
        "authority": contract[
            "authority"
        ],
        "grantsPermission": False,
        "changesPolicy": False,
        "executesAction": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


class ReviewAuditLedger:
    def __init__(
        self,
        storage: StorageAdapter,
        *,
        contract: dict[str, Any] | None = None,
    ) -> None:
        self.storage = storage
        self.contract = (
            contract
            if contract is not None
            else load_contract()
        )

    def record(
        self,
        permit: Any,
        review: Any,
    ) -> dict[str, Any]:
        entry = build_audit_entry(
            permit,
            review,
            contract=self.contract,
        )

        try:
            return self.storage.write(
                self.contract[
                    "namespace"
                ],
                entry["entryId"],
                entry,
                expected_revision=0,
            )
        except StorageConflictError as error:
            raise CityAuditError(
                "audit entry already exists"
            ) from error

    def read(
        self,
        entry_id: str,
    ) -> dict[str, Any] | None:
        return self.storage.read(
            self.contract["namespace"],
            entry_id,
        )

    def list_entry_ids(self) -> list[str]:
        return self.storage.list_keys(
            self.contract["namespace"]
        )


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Record a create-once Bondik City "
            "human-review audit entry."
        )
    ).parse_args()

    try:
        permit = prepare_permit_request(
            ticket_id="demo-ticket-1",
            principal={
                "id": "demo-agent",
                "role": "observer",
            },
            operation="command",
            capability_id=(
                "city.command-boundary.local"
            ),
            reason="Request human review.",
            requested_at=(
                "2026-01-01T00:00:00Z"
            ),
        )
        review = record_human_review(
            permit,
            reviewer_id="demo-human",
            decision="approve",
            reviewed_at=(
                "2026-01-01T00:01:00Z"
            ),
            note="Recorded for audit.",
        )
        ledger = ReviewAuditLedger(
            MemoryStorageAdapter()
        )
        stored = ledger.record(
            permit,
            review,
        )
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
    ) as error:
        print(
            "Bondik City Audit Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Audit Office OK: "
        "review-recorded / "
        f"revision={stored['revision']} / "
        "permission=false / "
        f"{ENTRY_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
