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

from tools.city.audit_office import (
    ENTRY_PROTOCOL,
    CityAuditError,
    build_audit_entry,
)
from tools.city.permit_office import (
    CityPermitError,
    prepare_permit_request,
)
from tools.city.review_board import (
    CityReviewError,
    record_human_review,
)

SEAL_PROTOCOL = "bondik-city-approval-seal/1"
CERTIFICATE_PROTOCOL = (
    "bondik-city-approval-certificate/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-approval-seal-contract.json"
)


class CitySealError(ValueError):
    pass


def _load_json(
    path: Path,
    *,
    label: str,
) -> Any:
    try:
        return json.loads(
            path.read_text(
                encoding="utf-8-sig"
            )
        )
    except OSError as error:
        raise CitySealError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CitySealError(
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
        raise CitySealError(
            "seal value must be JSON serializable"
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
        label="approval seal contract",
    )

    if not isinstance(payload, dict):
        raise CitySealError(
            "approval seal contract root "
            "must be an object"
        )

    if payload.get("protocol") != SEAL_PROTOCOL:
        raise CitySealError(
            "unsupported approval seal protocol"
        )

    if payload.get("version") != VERSION:
        raise CitySealError(
            "unsupported approval seal version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CitySealError(
            "approval seal cityId mismatch"
        )

    if payload.get(
        "auditEntryProtocol"
    ) != ENTRY_PROTOCOL:
        raise CitySealError(
            "audit entry protocol mismatch"
        )

    if payload.get(
        "certificateProtocol"
    ) != CERTIFICATE_PROTOCOL:
        raise CitySealError(
            "certificate protocol mismatch"
        )

    if payload.get("authority") != (
        "certificate-only"
    ):
        raise CitySealError(
            "seal authority must be "
            "certificate-only"
        )

    if payload.get(
        "certificateState"
    ) != "issued-inactive":
        raise CitySealError(
            "certificate state must be "
            "issued-inactive"
        )

    if payload.get(
        "acceptedDecision"
    ) != "approve":
        raise CitySealError(
            "seal accepted decision invalid"
        )

    if payload.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyActivation": "not-allowed",
    }:
        raise CitySealError(
            "approval seal exposure "
            "contract invalid"
        )

    return payload


def _audit_link_is_valid(
    audit_entry: dict[str, Any],
) -> bool:
    permit = audit_entry.get("permit")
    review = audit_entry.get("review")

    if (
        not isinstance(permit, dict)
        or not isinstance(review, dict)
    ):
        return False

    review_permit = review.get("permit")

    if not isinstance(
        review_permit,
        dict,
    ):
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


def issue_inactive_certificate(
    audit_entry: Any,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(
        audit_entry,
        dict,
    ):
        raise CitySealError(
            "audit entry must be an object"
        )

    if audit_entry.get(
        "protocol"
    ) != contract[
        "auditEntryProtocol"
    ]:
        raise CitySealError(
            "audit entry protocol mismatch"
        )

    if audit_entry.get(
        "grantsPermission"
    ) is not False:
        raise CitySealError(
            "audit entry must not grant "
            "permission"
        )

    if audit_entry.get(
        "changesPolicy"
    ) is not False:
        raise CitySealError(
            "audit entry must not change policy"
        )

    if audit_entry.get(
        "executesAction"
    ) is not False:
        raise CitySealError(
            "audit entry must not execute action"
        )

    if not _audit_link_is_valid(
        audit_entry
    ):
        raise CitySealError(
            "audit permit/review linkage invalid"
        )

    permit = audit_entry["permit"]
    review = audit_entry["review"]

    if review.get(
        "review",
        {},
    ).get("decision") != contract[
        "acceptedDecision"
    ]:
        raise CitySealError(
            "review decision is not approvable"
        )

    request = permit.get("request")

    if not isinstance(request, dict):
        raise CitySealError(
            "permit request invalid"
        )

    principal = request.get("principal")

    if not isinstance(principal, dict):
        raise CitySealError(
            "permit principal invalid"
        )

    operation = request.get("operation")
    capability_id = request.get(
        "capabilityId"
    )

    if (
        not isinstance(operation, str)
        or not operation
        or not isinstance(
            capability_id,
            str,
        )
        or not capability_id
    ):
        raise CitySealError(
            "permit scope invalid"
        )

    entry_id = audit_entry.get(
        "entryId"
    )

    if (
        not isinstance(entry_id, str)
        or not entry_id
    ):
        raise CitySealError(
            "audit entryId invalid"
        )

    certificate_id = (
        "seal-"
        + hashlib.sha256(
            entry_id.encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": (
            CERTIFICATE_PROTOCOL
        ),
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": (
            "approval-certificate"
        ),
        "certificateId": (
            certificate_id
        ),
        "state": contract[
            "certificateState"
        ],
        "authority": contract[
            "authority"
        ],
        "subject": copy.deepcopy(
            principal
        ),
        "scope": {
            "operation": operation,
            "capabilityId": (
                capability_id
            ),
        },
        "review": {
            "reviewerKind": review[
                "review"
            ].get("reviewerKind"),
            "reviewerId": review[
                "review"
            ].get("reviewerId"),
            "decision": review[
                "review"
            ].get("decision"),
            "reviewedAt": review[
                "review"
            ].get("reviewedAt"),
        },
        "evidence": {
            "auditEntryId": entry_id,
            "auditEntryDigest": (
                "sha256:"
                + _sha256(
                    audit_entry
                )
            ),
            "permitDigest": (
                audit_entry.get(
                    "permitDigest"
                )
            ),
            "reviewDigest": (
                audit_entry.get(
                    "reviewDigest"
                )
            ),
        },
        "currentPolicy": (
            copy.deepcopy(
                permit.get(
                    "currentPolicy"
                )
            )
        ),
        "route": copy.deepcopy(
            permit.get("route")
        ),
        "runtimeAuthority": False,
        "grantsPermission": False,
        "activatesPolicy": False,
        "executesAction": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Issue an inactive Bondik City "
            "human-approval certificate."
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
            reason=(
                "Request human review."
            ),
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
            note=(
                "Approved for inactive "
                "certificate issuance."
            ),
        )
        audit_entry = build_audit_entry(
            permit,
            review,
        )
        certificate = (
            issue_inactive_certificate(
                audit_entry
            )
        )
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
        CitySealError,
    ) as error:
        print(
            "Bondik City Seal Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Seal Office OK: "
        f"{certificate['state']} / "
        "permission=false / "
        f"{CERTIFICATE_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
