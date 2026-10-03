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

from tools.city.seal_office import (
    CERTIFICATE_PROTOCOL,
    CitySealError,
    issue_inactive_certificate,
)
from tools.city.audit_office import (
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
from tools.city.storage_adapter import (
    MemoryStorageAdapter,
    StorageAdapter,
    StorageConflictError,
)

VAULT_PROTOCOL = "bondik-city-key-vault/1"
ENTRY_PROTOCOL = "bondik-city-key-vault-entry/1"
VERSION = 1

DEFAULT_CONTRACT_PATH = (
    ROOT / "config" / "city-key-vault-contract.json"
)


class CityKeyVaultError(ValueError):
    pass


def _load_json(path: Path, *, label: str) -> Any:
    try:
        return json.loads(
            path.read_text(encoding="utf-8-sig")
        )
    except OSError as error:
        raise CityKeyVaultError(
            f"cannot read {label}: {error}"
        ) from error
    except json.JSONDecodeError as error:
        raise CityKeyVaultError(
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
        raise CityKeyVaultError(
            "certificate must be JSON serializable"
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
        label="key vault contract",
    )

    if not isinstance(payload, dict):
        raise CityKeyVaultError(
            "key vault contract root must be an object"
        )

    if payload.get("protocol") != VAULT_PROTOCOL:
        raise CityKeyVaultError(
            "unsupported key vault protocol"
        )

    if payload.get("version") != VERSION:
        raise CityKeyVaultError(
            "unsupported key vault version"
        )

    if payload.get("cityId") != "bondik-city":
        raise CityKeyVaultError(
            "key vault cityId mismatch"
        )

    if payload.get(
        "certificateProtocol"
    ) != CERTIFICATE_PROTOCOL:
        raise CityKeyVaultError(
            "certificate protocol mismatch"
        )

    if payload.get("entryProtocol") != ENTRY_PROTOCOL:
        raise CityKeyVaultError(
            "entry protocol mismatch"
        )

    if payload.get("namespace") != "city.keys.inactive":
        raise CityKeyVaultError(
            "key vault namespace mismatch"
        )

    if payload.get("authority") != "registry-only":
        raise CityKeyVaultError(
            "key vault authority must be registry-only"
        )

    if payload.get("writePolicy") != "create-once":
        raise CityKeyVaultError(
            "key vault write policy must be create-once"
        )

    if payload.get("acceptedState") != "issued-inactive":
        raise CityKeyVaultError(
            "key vault accepted state invalid"
        )

    if payload.get("exposure") != {
        "execution": "not-exposed",
        "mutation": "append-only-wrapper",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyActivation": "not-allowed",
    }:
        raise CityKeyVaultError(
            "key vault exposure contract invalid"
        )

    return payload


def build_registry_entry(
    certificate: Any,
    *,
    contract: dict[str, Any] | None = None,
) -> dict[str, Any]:
    contract = (
        contract
        if contract is not None
        else load_contract()
    )

    if not isinstance(certificate, dict):
        raise CityKeyVaultError(
            "certificate must be an object"
        )

    if certificate.get("protocol") != (
        contract["certificateProtocol"]
    ):
        raise CityKeyVaultError(
            "certificate protocol mismatch"
        )

    if certificate.get("state") != (
        contract["acceptedState"]
    ):
        raise CityKeyVaultError(
            "certificate must be issued-inactive"
        )

    if certificate.get("runtimeAuthority") is not False:
        raise CityKeyVaultError(
            "certificate must not have runtime authority"
        )

    if certificate.get("grantsPermission") is not False:
        raise CityKeyVaultError(
            "certificate must not grant permission"
        )

    if certificate.get("activatesPolicy") is not False:
        raise CityKeyVaultError(
            "certificate must not activate policy"
        )

    if certificate.get("executesAction") is not False:
        raise CityKeyVaultError(
            "certificate must not execute action"
        )

    certificate_id = certificate.get("certificateId")

    if (
        not isinstance(certificate_id, str)
        or not certificate_id
    ):
        raise CityKeyVaultError(
            "certificateId is invalid"
        )

    return {
        "protocol": ENTRY_PROTOCOL,
        "version": VERSION,
        "cityId": contract["cityId"],
        "kind": "inactive-certificate-registry-entry",
        "certificateId": certificate_id,
        "certificateDigest": (
            "sha256:" + _sha256(certificate)
        ),
        "state": "registered-inactive",
        "certificate": copy.deepcopy(certificate),
        "authority": contract["authority"],
        "runtimeAuthority": False,
        "grantsPermission": False,
        "activatesPolicy": False,
        "executesAction": False,
        "exposure": copy.deepcopy(
            contract["exposure"]
        ),
    }


class InactiveCertificateVault:
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

    def register(
        self,
        certificate: Any,
    ) -> dict[str, Any]:
        entry = build_registry_entry(
            certificate,
            contract=self.contract,
        )

        try:
            return self.storage.write(
                self.contract["namespace"],
                entry["certificateId"],
                entry,
                expected_revision=0,
            )
        except StorageConflictError as error:
            raise CityKeyVaultError(
                "certificate already registered"
            ) from error

    def read(
        self,
        certificate_id: str,
    ) -> dict[str, Any] | None:
        return self.storage.read(
            self.contract["namespace"],
            certificate_id,
        )

    def list_certificate_ids(self) -> list[str]:
        return self.storage.list_keys(
            self.contract["namespace"]
        )


def main() -> int:
    argparse.ArgumentParser(
        description=(
            "Register an inactive Bondik City "
            "approval certificate in the Key Vault."
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
            capability_id="city.command-boundary.local",
            reason="Request human review.",
            requested_at="2026-01-01T00:00:00Z",
        )
        review = record_human_review(
            permit,
            reviewer_id="demo-human",
            decision="approve",
            reviewed_at="2026-01-01T00:01:00Z",
            note="Approved for inactive certificate.",
        )
        audit_entry = build_audit_entry(
            permit,
            review,
        )
        certificate = issue_inactive_certificate(
            audit_entry
        )
        vault = InactiveCertificateVault(
            MemoryStorageAdapter()
        )
        stored = vault.register(
            certificate
        )
    except (
        CityPermitError,
        CityReviewError,
        CityAuditError,
        CitySealError,
        CityKeyVaultError,
    ) as error:
        print(
            "Bondik City Key Vault ERROR: "
            f"{error}"
        )
        return 1

    print(
        "Bondik City Key Vault OK: "
        "registered-inactive / "
        f"revision={stored['revision']} / "
        "permission=false / "
        f"{ENTRY_PROTOCOL}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
