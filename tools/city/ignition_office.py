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

from tools.city.audit_office import (
    CityAuditError,
    build_audit_entry,
)
from tools.city.key_vault import (
    ENTRY_PROTOCOL as VAULT_ENTRY_PROTOCOL,
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
    CERTIFICATE_PROTOCOL,
    CitySealError,
    issue_inactive_certificate,
)

IGNITION_PROTOCOL = "bondik-city-ignition/1"
INTENT_PROTOCOL = "bondik-city-activation-intent/1"
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-ignition-contract.json"
)

ACTOR_ID_RE = re.compile(
    r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$"
)


class CityIgnitionError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityIgnitionError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityIgnitionError(
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
        raise CityIgnitionError(
            "ignition value must be JSON serializable"
        ) from error


def _sha256(value: Any) -> str:
    return hashlib.sha256(
        _canonical_bytes(value)
    ).hexdigest()


def _validate_time(value: Any) -> str:
    if not isinstance(value, str):
        raise CityIgnitionError(
            "preparedAt must be a string"
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
        raise CityIgnitionError(
            "preparedAt must be ISO-8601"
        ) from error

    if parsed.tzinfo is None:
        raise CityIgnitionError(
            "preparedAt must include timezone"
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
        raise CityIgnitionError(
            "reason must be a non-empty string"
        )

    if len(value) > limit:
        raise CityIgnitionError(
            "reason exceeds size limit"
        )

    return value


def load_contract(
    path: Path = DEFAULT_CONTRACT_PATH,
) -> dict[str, Any]:
    payload = _load_json(
        path,
        label="ignition contract",
    )

    if not isinstance(payload, dict):
        raise CityIgnitionError(
            "ignition contract root must be an object"
        )

    expected = {
        "protocol": IGNITION_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "vaultEntryProtocol": VAULT_ENTRY_PROTOCOL,
        "certificateProtocol": CERTIFICATE_PROTOCOL,
        "intentProtocol": INTENT_PROTOCOL,
        "authority": "intent-only",
        "intentState": "prepared-not-active",
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
            raise CityIgnitionError(
                f"ignition contract field invalid: {key}"
            )

    return payload


def prepare_activation_intent(
    vault_entry: Any,
    *,
    actor_id: Any,
    prepared_at: Any,
    reason: Any,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(vault_entry, dict):
        raise CityIgnitionError(
            "vault entry must be an object"
        )

    if vault_entry.get("protocol") != (
        contract["vaultEntryProtocol"]
    ):
        raise CityIgnitionError(
            "vault entry protocol mismatch"
        )

    if vault_entry.get("state") != (
        "registered-inactive"
    ):
        raise CityIgnitionError(
            "vault entry must be registered-inactive"
        )

    for field in (
        "runtimeAuthority",
        "grantsPermission",
        "activatesPolicy",
        "executesAction",
    ):
        if vault_entry.get(field) is not False:
            raise CityIgnitionError(
                f"vault entry unsafe field: {field}"
            )

    certificate = vault_entry.get("certificate")

    if not isinstance(certificate, dict):
        raise CityIgnitionError(
            "vault entry certificate missing"
        )

    if certificate.get("protocol") != (
        contract["certificateProtocol"]
    ):
        raise CityIgnitionError(
            "certificate protocol mismatch"
        )

    if certificate.get("state") != "issued-inactive":
        raise CityIgnitionError(
            "certificate must be issued-inactive"
        )

    expected_digest = (
        "sha256:" + _sha256(certificate)
    )

    if vault_entry.get(
        "certificateDigest"
    ) != expected_digest:
        raise CityIgnitionError(
            "certificate digest mismatch"
        )

    for field in (
        "runtimeAuthority",
        "grantsPermission",
        "activatesPolicy",
        "executesAction",
    ):
        if certificate.get(field) is not False:
            raise CityIgnitionError(
                f"certificate unsafe field: {field}"
            )

    if (
        not isinstance(actor_id, str)
        or not ACTOR_ID_RE.fullmatch(actor_id)
    ):
        raise CityIgnitionError(
            "actorId is invalid"
        )

    prepared_at = _validate_time(
        prepared_at
    )
    reason = _validate_reason(
        reason,
        limit=contract["limits"][
            "reasonChars"
        ],
    )

    certificate_id = certificate.get(
        "certificateId"
    )
    subject = certificate.get("subject")
    scope = certificate.get("scope")

    if (
        not isinstance(certificate_id, str)
        or not certificate_id
        or not isinstance(subject, dict)
        or not isinstance(scope, dict)
    ):
        raise CityIgnitionError(
            "certificate activation scope invalid"
        )

    intent_id = (
        "intent-"
        + hashlib.sha256(
            (
                certificate_id
                + "|"
                + actor_id
                + "|"
                + prepared_at
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": INTENT_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "activation-intent",
        "intentId": intent_id,
        "state": contract["intentState"],
        "authority": contract["authority"],
        "actor": {
            "kind": contract["actorKind"],
            "id": actor_id,
        },
        "preparedAt": prepared_at,
        "reason": reason,
        "subject": copy.deepcopy(subject),
        "scope": copy.deepcopy(scope),
        "evidence": {
            "vaultEntryDigest": (
                "sha256:" + _sha256(
                    vault_entry
                )
            ),
            "certificateId": certificate_id,
            "certificateDigest": expected_digest,
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
            "Prepare a non-activating Bondik City "
            "human activation intent."
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
                "for later human confirmation."
            ),
        )
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
        CitySealError,
        CityKeyVaultError,
        CityIgnitionError,
    ) as error:
        print(
            "Bondik City Ignition Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Ignition Office OK: "
        f"{intent['state']} / "
        "permission=false / "
        f"{INTENT_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
