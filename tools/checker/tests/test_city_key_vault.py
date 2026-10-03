import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.audit_office import (
    build_audit_entry,
)
from tools.city.key_vault import (
    ENTRY_PROTOCOL,
    CityKeyVaultError,
    InactiveCertificateVault,
    build_registry_entry,
    load_contract,
)
from tools.city.permit_office import (
    prepare_permit_request,
)
from tools.city.review_board import (
    record_human_review,
)
from tools.city.seal_office import (
    issue_inactive_certificate,
)
from tools.city.storage_adapter import (
    MemoryStorageAdapter,
)


ROOT = Path(__file__).resolve().parents[3]


def certificate():
    permit = prepare_permit_request(
        ticket_id="permit-001",
        principal={
            "id": "demo-agent",
            "role": "observer",
        },
        operation="command",
        capability_id="city.command-boundary.local",
        reason="Need human review.",
        requested_at="2026-10-03T21:10:00+02:00",
    )
    review = record_human_review(
        permit,
        reviewer_id="michal",
        decision="approve",
        reviewed_at="2026-10-03T21:11:00+02:00",
        note="Review complete.",
    )
    return issue_inactive_certificate(
        build_audit_entry(
            permit,
            review,
        )
    )


def test_build_entry_preserves_inactive_boundary():
    entry = build_registry_entry(
        certificate()
    )

    assert entry["protocol"] == ENTRY_PROTOCOL
    assert entry["state"] == "registered-inactive"
    assert entry["runtimeAuthority"] is False
    assert entry["grantsPermission"] is False
    assert entry["activatesPolicy"] is False
    assert entry["executesAction"] is False


def test_entry_contains_certificate_digest():
    entry = build_registry_entry(
        certificate()
    )

    assert entry[
        "certificateDigest"
    ].startswith("sha256:")
    assert len(
        entry["certificateDigest"]
    ) == 71


def test_entry_preserves_certificate_snapshot():
    source = certificate()
    entry = build_registry_entry(
        source
    )

    assert entry["certificate"] == source
    assert entry["certificate"] is not source


def test_registration_is_create_once():
    vault = InactiveCertificateVault(
        MemoryStorageAdapter()
    )
    source = certificate()

    first = vault.register(source)

    assert first["revision"] == 1

    with pytest.raises(
        CityKeyVaultError,
        match="already registered",
    ):
        vault.register(source)


def test_registered_certificate_can_be_read():
    vault = InactiveCertificateVault(
        MemoryStorageAdapter()
    )
    source = certificate()
    stored = vault.register(source)

    restored = vault.read(
        source["certificateId"]
    )

    assert restored == stored


def test_list_certificate_ids_is_sorted():
    vault = InactiveCertificateVault(
        MemoryStorageAdapter()
    )

    first = certificate()
    vault.register(first)

    second = copy.deepcopy(first)
    second["certificateId"] = "seal-zzzz"
    vault.register(second)

    assert vault.list_certificate_ids() == sorted(
        [
            first["certificateId"],
            second["certificateId"],
        ]
    )


def test_active_certificate_is_rejected():
    source = certificate()
    source["state"] = "active"

    with pytest.raises(
        CityKeyVaultError,
        match="issued-inactive",
    ):
        build_registry_entry(source)


def test_runtime_authority_is_rejected():
    source = certificate()
    source["runtimeAuthority"] = True

    with pytest.raises(
        CityKeyVaultError,
        match="runtime authority",
    ):
        build_registry_entry(source)


def test_permission_granting_certificate_is_rejected():
    source = certificate()
    source["grantsPermission"] = True

    with pytest.raises(
        CityKeyVaultError,
        match="grant permission",
    ):
        build_registry_entry(source)


def test_policy_activating_certificate_is_rejected():
    source = certificate()
    source["activatesPolicy"] = True

    with pytest.raises(
        CityKeyVaultError,
        match="activate policy",
    ):
        build_registry_entry(source)


def test_executing_certificate_is_rejected():
    source = certificate()
    source["executesAction"] = True

    with pytest.raises(
        CityKeyVaultError,
        match="execute action",
    ):
        build_registry_entry(source)


def test_input_certificate_is_not_mutated():
    source = certificate()
    snapshot = copy.deepcopy(source)

    build_registry_entry(source)

    assert source == snapshot


def test_contract_is_create_once_registry_only():
    contract = load_contract()

    assert contract["authority"] == "registry-only"
    assert contract["writePolicy"] == "create-once"
    assert contract["acceptedState"] == "issued-inactive"
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "append-only-wrapper",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyActivation": "not-allowed",
    }


def test_direct_cli_registers_inactive_certificate():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "key_vault.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Key Vault OK: "
        "registered-inactive / revision=1 / "
        "permission=false / "
        "bondik-city-key-vault-entry/1"
        in result.stdout
    )
