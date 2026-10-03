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

from tools.city.activation_confirmation import (
    CONFIRMATION_PROTOCOL,
    CityActivationConfirmationError,
    confirm_activation_intent,
)
from tools.city.audit_office import (
    CityAuditError,
    build_audit_entry,
)
from tools.city.ignition_office import (
    INTENT_PROTOCOL,
    CityIgnitionError,
    prepare_activation_intent,
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

GRANT_CONTRACT_PROTOCOL = "bondik-city-runtime-grant/1"
GRANT_PROTOCOL = "bondik-city-runtime-grant-token/1"
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-runtime-grant-contract.json"
)


class CityRuntimeGrantError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityRuntimeGrantError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityRuntimeGrantError(
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
        raise CityRuntimeGrantError(
            "grant value must be JSON serializable"
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
        label="runtime grant contract",
    )

    expected = {
        "protocol": GRANT_CONTRACT_PROTOCOL,
        "version": VERSION,
        "cityId": "bondik-city",
        "intentProtocol": INTENT_PROTOCOL,
        "confirmationProtocol": CONFIRMATION_PROTOCOL,
        "grantProtocol": GRANT_PROTOCOL,
        "authority": "grant-issuer",
        "grantState": "issued-unconsumed",
        "actorKind": "human",
        "constraints": {
            "singleUse": True,
            "localOnly": True,
            "consumerConnected": False,
        },
        "exposure": {
            "execution": "not-exposed",
            "mutation": "not-allowed",
            "network": "not-exposed",
            "policyMutation": "not-allowed",
        },
    }

    if not isinstance(payload, dict):
        raise CityRuntimeGrantError(
            "runtime grant contract root must be an object"
        )

    for key, value in expected.items():
        if payload.get(key) != value:
            raise CityRuntimeGrantError(
                f"runtime grant contract field invalid: {key}"
            )

    return payload


def issue_runtime_grant(
    intent: Any,
    confirmation: Any,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(intent, dict):
        raise CityRuntimeGrantError(
            "intent must be an object"
        )
    if not isinstance(confirmation, dict):
        raise CityRuntimeGrantError(
            "confirmation must be an object"
        )

    if intent.get("protocol") != contract["intentProtocol"]:
        raise CityRuntimeGrantError(
            "intent protocol mismatch"
        )
    if confirmation.get("protocol") != (
        contract["confirmationProtocol"]
    ):
        raise CityRuntimeGrantError(
            "confirmation protocol mismatch"
        )

    if intent.get("state") != "prepared-not-active":
        raise CityRuntimeGrantError(
            "intent must be prepared-not-active"
        )
    if confirmation.get("state") != "confirmed-not-active":
        raise CityRuntimeGrantError(
            "confirmation must be confirmed-not-active"
        )

    for source_name, source in (
        ("intent", intent),
        ("confirmation", confirmation),
    ):
        for field in (
            "runtimeAuthority",
            "grantsPermission",
            "activatesPolicy",
            "executesAction",
        ):
            if source.get(field) is not False:
                raise CityRuntimeGrantError(
                    f"{source_name} unsafe field: {field}"
                )

    intent_id = intent.get("intentId")
    evidence = confirmation.get("evidence")

    if (
        not isinstance(intent_id, str)
        or not intent_id
        or not isinstance(evidence, dict)
    ):
        raise CityRuntimeGrantError(
            "activation evidence invalid"
        )

    if evidence.get("intentId") != intent_id:
        raise CityRuntimeGrantError(
            "confirmation intentId mismatch"
        )

    expected_intent_digest = (
        "sha256:" + _sha256(intent)
    )
    if evidence.get("intentDigest") != (
        expected_intent_digest
    ):
        raise CityRuntimeGrantError(
            "confirmation intent digest mismatch"
        )

    if confirmation.get("subject") != intent.get("subject"):
        raise CityRuntimeGrantError(
            "confirmation subject mismatch"
        )
    if confirmation.get("scope") != intent.get("scope"):
        raise CityRuntimeGrantError(
            "confirmation scope mismatch"
        )

    confirmer = confirmation.get("confirmer")
    if (
        not isinstance(confirmer, dict)
        or confirmer.get("kind") != contract["actorKind"]
        or not isinstance(confirmer.get("id"), str)
        or not confirmer.get("id")
    ):
        raise CityRuntimeGrantError(
            "human confirmer invalid"
        )

    subject = intent.get("subject")
    scope = intent.get("scope")
    confirmation_id = confirmation.get("confirmationId")

    if (
        not isinstance(subject, dict)
        or not isinstance(scope, dict)
        or not isinstance(confirmation_id, str)
        or not confirmation_id
    ):
        raise CityRuntimeGrantError(
            "grant scope invalid"
        )

    grant_id = (
        "grant-"
        + hashlib.sha256(
            (
                confirmation_id
                + "|"
                + scope.get("operation", "")
                + "|"
                + scope.get("capabilityId", "")
            ).encode("utf-8")
        ).hexdigest()[:24]
    )

    return {
        "protocol": GRANT_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "runtime-grant-token",
        "grantId": grant_id,
        "state": contract["grantState"],
        "authority": contract["authority"],
        "subject": copy.deepcopy(subject),
        "scope": copy.deepcopy(scope),
        "humanAuthorization": {
            "confirmerId": confirmer["id"],
            "confirmationId": confirmation_id,
        },
        "evidence": {
            "intentId": intent_id,
            "intentDigest": expected_intent_digest,
            "confirmationDigest": (
                "sha256:" + _sha256(confirmation)
            ),
        },
        "constraints": copy.deepcopy(
            contract["constraints"]
        ),
        "grantsPermission": True,
        "runtimeAuthority": True,
        "consumed": False,
        "executesAction": False,
        "activatesPolicy": False,
        "mutatesPolicy": False,
        "consumerConnected": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Issue a human-confirmed, exact-scope "
            "Bondik City runtime grant token "
            "without consuming or executing it."
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
            note="Approved.",
        )
        certificate = issue_inactive_certificate(
            build_audit_entry(
                permit,
                review,
            )
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
            reason="Prepare exact-scope activation.",
        )
        confirmation = confirm_activation_intent(
            intent,
            confirmer_id="demo-human",
            confirmed_at=(
                "2026-01-01T00:03:00Z"
            ),
            confirm_intent_id=intent["intentId"],
            reason="Confirm exact intent.",
        )
        grant = issue_runtime_grant(
            intent,
            confirmation,
        )
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
        CitySealError,
        CityKeyVaultError,
        CityIgnitionError,
        CityActivationConfirmationError,
        CityRuntimeGrantError,
    ) as error:
        print(
            "Bondik City Grant Office ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Grant Office OK: "
        f"{grant['state']} / "
        "permission=true / consumed=false / "
        f"{GRANT_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
