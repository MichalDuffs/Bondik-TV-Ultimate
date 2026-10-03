from __future__ import annotations

import argparse
import copy
import hashlib
import json
import re
import sys
from datetime import datetime
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[2]

if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from tools.city.ignition_office import (
    INTENT_PROTOCOL,
    CityIgnitionError,
    prepare_activation_intent,
)
from tools.city.audit_office import (
    CityAuditError,
    build_audit_entry,
)
from tools.city.key_vault import (
    CityKeyVaultError,
    build_registry_entry,
)
from tools.city.permit_office import (
    CityPermitError,
    prepare_permit_request,
)
from tools.city.review_board import (
    CityReviewError,
    record_human_review,
)
from tools.city.seal_office import (
    CitySealError,
    issue_inactive_certificate,
)

CONFIRMATION_PROTOCOL = (
    "bondik-city-activation-confirmation/1"
)
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT
    / "config"
    / "city-activation-confirmation-contract.json"
)

ACTOR_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class CityActivationConfirmationError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityActivationConfirmationError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityActivationConfirmationError(
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
        raise CityActivationConfirmationError(
            "confirmation value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def _validate_time(value: Any) -> str:
    if not isinstance(value, str):
        raise CityActivationConfirmationError(
            "confirmedAt must be a string"
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
        raise CityActivationConfirmationError(
            "confirmedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityActivationConfirmationError(
            "confirmedAt must include timezone"
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
        raise CityActivationConfirmationError(
            "reason must be a non-empty string"
        )

    if len(value) > limit:
        raise CityActivationConfirmationError(
            "reason exceeds size limit"
        )

    return value


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="activation confirmation contract",
    )

    if not isinstance(payload, dict):
        raise CityActivationConfirmationError(
            "activation confirmation contract root "
            "must be an object"
        )

    expected = {
        "protocol": CONFIRMATION_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "intentProtocol": INTENT_PROTOCOL,
        "authority": "confirmation-only",
        "confirmationState": "confirmed-not-active",
        "actorKind": "human",
        "limits": {"reasonChars": 1024},
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "permissionGrant": "not-allowed",
            "policyActivation": "not-allowed",
        },
    }

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityActivationConfirmationError(
                f"activation confirmation contract "
                f"field invalid: {key}"
            )

    return payload


def confirm_activation_intent(
    intent: Any,
    *,
    confirmer_id: Any,
    confirmed_at: Any,
    confirm_intent_id: Any,
    reason: Any,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(intent, dict):
        raise CityActivationConfirmationError(
            "intent must be an object"
        )

    if intent.get("protocol") != (
        contract["intentProtocol"]
    ):
        raise CityActivationConfirmationError(
            "intent protocol mismatch"
        )

    if intent.get("state") != (
        "prepared-not-active"
    ):
        raise CityActivationConfirmationError(
            "intent must be prepared-not-active"
        )

    for field in (
        "runtimeAuthority",
        "grantsPermission",
        "activatesPolicy",
        "executesAction",
    ):
        if intent.get(field) is not False:
            raise CityActivationConfirmationError(
                f"intent unsafe field: {field}"
            )

    intent_id = intent.get("intentId")

    if (
        not isinstance(intent_id, str)
        or not intent_id
    ):
        raise CityActivationConfirmationError(
            "intentId is invalid"
        )

    if confirm_intent_id != intent_id:
        raise CityActivationConfirmationError(
            "confirmIntentId mismatch"
        )

    if (
        not isinstance(confirmer_id, str)
        or not ACTOR_ID_RE.fullmatch(
            confirmer_id
        )
    ):
        raise CityActivationConfirmationError(
            "confirmerId is invalid"
        )

    confirmed_at = _validate_time(
        confirmed_at
    )
    reason = _validate_reason(
        reason,
        limit=contract["limits"][
            "reasonChars"
        ],
    )

    subject = intent.get("subject")
    scope = intent.get("scope")

    if (
        not isinstance(subject, dict)
        or not isinstance(scope, dict)
    ):
        raise CityActivationConfirmationError(
            "intent activation scope invalid"
        )

    confirmation_id = (
        "confirm-"
        + hashlib.sha256(
            (
                intent_id
                + "|"
                + confirmer_id
                + "|"
                + confirmed_at
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": CONFIRMATION_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "activation-confirmation",
        "confirmationId": confirmation_id,
        "state": contract[
            "confirmationState"
        ],
        "authority": contract["authority"],
        "confirmer": {
            "kind": contract["actorKind"],
            "id": confirmer_id,
        },
        "confirmedAt": confirmed_at,
        "reason": reason,
        "subject": copy.deepcopy(subject),
        "scope": copy.deepcopy(scope),
        "evidence": {
            "intentId": intent_id,
            "intentDigest": (
                "sha256:" + _sha256(intent)
            ),
            "sourceActor": copy.deepcopy(
                intent.get("actor")
            ),
            "sourcePreparedAt": intent.get(
                "preparedAt"
            ),
        },
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
            "Record a non-activating Bondik City "
            "human activation confirmation."
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
            note="Approved for inactive certificate.",
        )
        audit_entry = build_audit_entry(
            permit,
            review,
        )
        certificate = issue_inactive_certificate(
            audit_entry
        )
        vault_entry = build_registry_entry(
            certificate
        )
        intent = prepare_activation_intent(
            vault_entry,
            actor_id="demo-human",
            prepared_at=(
                "2026-01-01T00:02:00Z"
            ),
            reason=(
                "Prepare exact-scope activation "
                "for confirmation."
            ),
        )
        confirmation = confirm_activation_intent(
            intent,
            confirmer_id="demo-human",
            confirmed_at=(
                "2026-01-01T00:03:00Z"
            ),
            confirm_intent_id=intent[
                "intentId"
            ],
            reason=(
                "Confirm exact prepared intent "
                "without activation."
            ),
        )
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
        CitySealError,
        CityKeyVaultError,
        CityIgnitionError,
        CityActivationConfirmationError,
    ) as error:
        print(
            "Bondik City Key Turn Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Key Turn Office OK: "
        f"{confirmation['state']} / "
        "permission=false / "
        f"{CONFIRMATION_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
