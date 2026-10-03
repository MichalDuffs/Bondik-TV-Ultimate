from __future__ import annotations

import argparse
import copy
import json
import re
import sys
from datetime import datetime
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

REVIEW_PROTOCOL = "bondik-city-human-review/1"
VERSION = 1
DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-human-review-contract.json"
)
REVIEWER_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class CityReviewError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityReviewError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityReviewError(
            f"{label} must be valid JSON"
        ) from error


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="human review contract",
    )

    if not isinstance(payload, dict):
        raise CityReviewError(
            "human review contract root must be an object"
        )

    if payload.get("protocol") != REVIEW_PROTOCOL:
        raise CityReviewError(
            "unsupported human review protocol"
        )

    if payload.get("version") != VERSION:
        raise CityReviewError(
            "unsupported human review version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityReviewError(
            "human review cityId mismatch"
        )

    if payload.get("permitProtocol") != (
        PERMIT_PROTOCOL
    ):
        raise CityReviewError(
            "permit protocol mismatch"
        )

    if payload.get("authority") != "record-only":
        raise CityReviewError(
            "review authority must be record-only"
        )

    if payload.get("decisions") != [
        "approve",
        "deny",
        "needs-info",
    ]:
        raise CityReviewError(
            "review decisions invalid"
        )

    if payload.get("reviewEffect") != (
        "recorded-only"
    ):
        raise CityReviewError(
            "review effect must be recorded-only"
        )

    if payload.get("limits") != {
        "noteChars": 2048
    }:
        raise CityReviewError(
            "review limits invalid"
        )

    if payload.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyChange": "not-allowed",
    }:
        raise CityReviewError(
            "human review exposure contract invalid"
        )

    return payload


def _validate_time(value: Any) -> str:
    if not isinstance(value, str):
        raise CityReviewError(
            "reviewedAt must be a string"
        )

    normalized = (
        value[:-1] + "+00:00"
        if value.endswith("Z")
        else value
    )

    try:
        parsed = datetime.fromisoformat(
            normalized
        )
    except ValueError as error:
        raise CityReviewError(
            "reviewedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityReviewError(
            "reviewedAt must include timezone"
        )

    return value


def _validate_note(
    value: Any,
    *,
    limit: int,
) -> str:
    if not isinstance(value, str):
        raise CityReviewError(
            "note must be a string"
        )

    if len(value) > limit:
        raise CityReviewError(
            "note exceeds size limit"
        )

    return value


def record_human_review(
    permit: Any,
    *,
    reviewer_id: Any,
    decision: Any,
    reviewed_at: Any,
    note: Any = "",
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(permit, dict):
        raise CityReviewError(
            "permit must be an object"
        )

    if permit.get("protocol") != (
        contract["permitProtocol"]
    ):
        raise CityReviewError(
            "permit protocol mismatch"
        )

    if permit.get("status") != (
        "pending-human-review"
    ):
        raise CityReviewError(
            "permit must be pending human review"
        )

    if permit.get("grantsPermission") is not False:
        raise CityReviewError(
            "permit must not grant permission"
        )

    if (
        not isinstance(reviewer_id, str)
        or not REVIEWER_ID_RE.fullmatch(
            reviewer_id
        )
    ):
        raise CityReviewError(
            "reviewerId is invalid"
        )

    if decision not in contract[
        "decisions"
    ]:
        raise CityReviewError(
            "review decision is invalid"
        )

    reviewed_at = _validate_time(
        reviewed_at
    )
    note = _validate_note(
        note,
        limit=contract["limits"][
            "noteChars"
        ],
    )

    return {
        "protocol": REVIEW_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "human-review-record",
        "authority": contract[
            "authority"
        ],
        "effect": contract[
            "reviewEffect"
        ],
        "permit": {
            "ticketId": permit[
                "ticketId"
            ],
            "requestedAt": permit[
                "requestedAt"
            ],
            "request": copy.deepcopy(
                permit["request"]
            ),
            "currentPolicy": (
                copy.deepcopy(
                    permit[
                        "currentPolicy"
                    ]
                )
            ),
            "route": copy.deepcopy(
                permit["route"]
            ),
        },
        "review": {
            "reviewerKind": "human",
            "reviewerId": reviewer_id,
            "decision": decision,
            "reviewedAt": reviewed_at,
            "note": note,
        },
        "grantsPermission": False,
        "changesPolicy": False,
        "executesAction": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Record a non-granting human "
            "review for a Bondik City permit."
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
            note=(
                "Recorded for later "
                "permission workflow."
            ),
        )
    except (
        CityPermitError,
        CityReviewError,
    ) as error:
        print(
            "Bondik City Review Board ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Review Board OK: "
        f"{review['review']['decision']} / "
        f"{review['effect']} / "
        "permission=false / "
        f"{REVIEW_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
