from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.access_route_planner import (
    ROUTE_PROTOCOL,
    CityRouteError,
    plan_access_route,
)

PERMIT_PROTOCOL = "bondik-city-permit-request/1"
VERSION = 1
DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-permit-request-contract.json"
)
TICKET_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class CityPermitError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityPermitError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityPermitError(
            f"{label} must be valid JSON"
        ) from error


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="permit request contract",
    )

    if not isinstance(payload, dict):
        raise CityPermitError(
            "permit request contract root must be an object"
        )

    if payload.get("protocol") != PERMIT_PROTOCOL:
        raise CityPermitError(
            "unsupported permit request protocol"
        )

    if payload.get("version") != VERSION:
        raise CityPermitError(
            "unsupported permit request version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityPermitError(
            "permit request cityId mismatch"
        )

    if payload.get("routeProtocol") != ROUTE_PROTOCOL:
        raise CityPermitError(
            "route protocol mismatch"
        )

    if payload.get("authority") != "request-only":
        raise CityPermitError(
            "permit authority must be request-only"
        )

    if payload.get("ticketStatus") != (
        "pending-human-review"
    ):
        raise CityPermitError(
            "permit ticket status invalid"
        )

    if payload.get("requestableOperations") != [
        "command",
        "handoff",
        "mutate",
        "publish-event",
        "execute",
    ]:
        raise CityPermitError(
            "requestable operations invalid"
        )

    if payload.get("limits") != {
        "reasonChars": 1024
    }:
        raise CityPermitError(
            "permit limits invalid"
        )

    if payload.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "autoApproval": "not-allowed",
    }:
        raise CityPermitError(
            "permit exposure contract invalid"
        )

    return payload


def _validate_timestamp(value: Any) -> str:
    if not isinstance(value, str):
        raise CityPermitError(
            "requestedAt must be a string"
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
        raise CityPermitError(
            "requestedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityPermitError(
            "requestedAt must include timezone"
        )

    return value


def _validate_reason(
    value: Any,
    *,
    limit: int,
) -> str:
    if (
        not isinstance(value, str)
        or not value.strip()
    ):
        raise CityPermitError(
            "reason must be a non-empty string"
        )

    if len(value) > limit:
        raise CityPermitError(
            "reason exceeds size limit"
        )

    return value


def prepare_permit_request(
    *,
    ticket_id: Any,
    principal: Any,
    operation: Any,
    capability_id: Any,
    reason: Any,
    requested_at: Any,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if (
        not isinstance(ticket_id, str)
        or not TICKET_ID_RE.fullmatch(
            ticket_id
        )
    ):
        raise CityPermitError(
            "ticketId is invalid"
        )

    if operation not in contract[
        "requestableOperations"
    ]:
        raise CityPermitError(
            "operation is not requestable"
        )

    if (
        not isinstance(capability_id, str)
        or not capability_id
    ):
        raise CityPermitError(
            "capabilityId must be a non-empty string"
        )

    requested_at = _validate_timestamp(
        requested_at
    )
    reason = _validate_reason(
        reason,
        limit=contract[
            "limits"
        ]["reasonChars"],
    )

    try:
        route = plan_access_route(
            {
                "principal": principal,
                "operation": operation,
                "capabilityId": capability_id,
            }
        )
    except CityRouteError as error:
        raise CityPermitError(
            str(error)
        ) from error

    return {
        "protocol": PERMIT_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "permit-request",
        "ticketId": ticket_id,
        "status": contract[
            "ticketStatus"
        ],
        "authority": contract[
            "authority"
        ],
        "requestedAt": requested_at,
        "request": {
            "principal": route[
                "request"
            ]["principal"],
            "operation": route[
                "request"
            ]["operation"],
            "capabilityId": route[
                "request"
            ]["capabilityId"],
            "reason": reason,
        },
        "currentPolicy": {
            "decision": route[
                "access"
            ]["decision"],
            "reason": route[
                "access"
            ]["reason"],
        },
        "route": route["route"],
        "review": {
            "required": True,
            "reviewerKind": "human",
            "decision": None,
        },
        "grantsPermission": False,
        "exposure": contract[
            "exposure"
        ],
    }


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Prepare a non-granting Bondik City "
            "permit request ticket."
        )
    ).parse_args()

    try:
        ticket = prepare_permit_request(
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
                "Request human review for a "
                "future bounded command."
            ),
            requested_at=(
                "2026-01-01T00:00:00Z"
            ),
        )
    except CityPermitError as error:
        print(
            "Bondik City Permit Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Permit Office OK: "
        f"{ticket['status']} / "
        f"policy={ticket['currentPolicy']['decision']} / "
        f"{PERMIT_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
