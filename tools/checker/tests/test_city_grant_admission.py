import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.activation_confirmation import (
    confirm_activation_intent,
)
from tools.city.audit_office import (
    build_audit_entry,
)
from tools.city.grant_admission import (
    ADMISSION_PROTOCOL,
    CityGrantAdmissionError,
    admit_runtime_grant,
    load_contract,
)
from tools.city.ignition_office import (
    prepare_activation_intent,
)
from tools.city.key_vault import (
    build_registry_entry,
)
from tools.city.permit_office import (
    prepare_permit_request,
)
from tools.city.review_board import (
    record_human_review,
)
from tools.city.runtime_grant import (
    issue_runtime_grant,
)
from tools.city.seal_office import (
    issue_inactive_certificate,
)
from tools.city.service_directory import (
    build_directory,
)


ROOT = Path(__file__).resolve().parents[3]


def grant():
    permit = prepare_permit_request(
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
            "2026-10-03T21:50:00+02:00"
        ),
    )
    review = record_human_review(
        permit,
        reviewer_id="michal",
        decision="approve",
        reviewed_at=(
            "2026-10-03T21:51:00+02:00"
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
        actor_id="michal",
        prepared_at=(
            "2026-10-03T21:52:00+02:00"
        ),
        reason="Prepare activation.",
    )
    confirmation = confirm_activation_intent(
        intent,
        confirmer_id="michal",
        confirmed_at=(
            "2026-10-03T21:53:00+02:00"
        ),
        confirm_intent_id=intent["intentId"],
        reason="Confirm intent.",
    )
    return issue_runtime_grant(
        intent,
        confirmation,
    )


def admit(source=None, **kwargs):
    source = (
        source
        if source is not None
        else grant()
    )
    return admit_runtime_grant(
        source,
        consumer_id=kwargs.pop(
            "consumer_id",
            "dispatch-office",
        ),
        **kwargs,
    )


def test_admission_is_not_consumed_or_executed():
    value = admit()

    assert value["protocol"] == (
        ADMISSION_PROTOCOL
    )
    assert value["state"] == (
        "admitted-not-consumed"
    )
    assert value["grantConsumed"] is False
    assert value["dispatchesCommand"] is False
    assert value["executesAction"] is False


def test_admission_does_not_grant_permission_itself():
    value = admit()

    assert value[
        "sourceGrantPermission"
    ] is True
    assert value[
        "sourceGrantRuntimeAuthority"
    ] is True
    assert value["grantsPermission"] is False
    assert value["runtimeAuthority"] is False


def test_admission_targets_exact_capability_owner():
    value = admit()

    assert value["consumer"] == {
        "id": "dispatch-office",
        "connected": False,
    }
    assert value["target"][
        "locationId"
    ] == "dispatch-office"
    assert value["scope"][
        "capabilityId"
    ] == "city.command-boundary.local"


def test_admission_binds_grant_digest():
    source = grant()
    value = admit(source)

    assert value["evidence"][
        "grantId"
    ] == source["grantId"]
    assert value["evidence"][
        "grantDigest"
    ].startswith("sha256:")


def test_admission_id_is_deterministic():
    source = grant()

    first = admit(source)
    second = admit(source)

    assert first["admissionId"] == (
        second["admissionId"]
    )


def test_wrong_consumer_is_rejected():
    with pytest.raises(
        CityGrantAdmissionError,
        match="does not own grant capability",
    ):
        admit(
            consumer_id="grant-office"
        )


@pytest.mark.parametrize(
    "field,value,match",
    [
        (
            "grantsPermission",
            False,
            "must carry permission",
        ),
        (
            "runtimeAuthority",
            False,
            "must carry runtime authority",
        ),
        (
            "consumed",
            True,
            "must be unconsumed",
        ),
        (
            "executesAction",
            True,
            "must not execute action",
        ),
        (
            "activatesPolicy",
            True,
            "must not activate policy",
        ),
        (
            "mutatesPolicy",
            True,
            "must not mutate policy",
        ),
        (
            "consumerConnected",
            True,
            "must not already have a consumer",
        ),
    ],
)
def test_unsafe_grant_is_rejected(
    field,
    value,
    match,
):
    source = grant()
    source[field] = value

    with pytest.raises(
        CityGrantAdmissionError,
        match=match,
    ):
        admit(source)


def test_invalid_constraints_are_rejected():
    source = grant()
    source["constraints"][
        "singleUse"
    ] = False

    with pytest.raises(
        CityGrantAdmissionError,
        match="constraints invalid",
    ):
        admit(source)


def test_unknown_capability_fails_closed():
    source = grant()
    source["scope"][
        "capabilityId"
    ] = "city.missing"

    with pytest.raises(
        CityGrantAdmissionError,
        match="resolve exactly once",
    ):
        admit(source)


def test_directory_protocol_mismatch_fails_closed():
    directory = build_directory()
    directory["protocol"] = "wrong/1"

    with pytest.raises(
        CityGrantAdmissionError,
        match="directory protocol mismatch",
    ):
        admit(
            directory=directory
        )


def test_input_grant_is_not_mutated():
    source = grant()
    snapshot = copy.deepcopy(source)

    admit(source)

    assert source == snapshot


def test_contract_is_admission_only():
    contract = load_contract()

    assert contract[
        "authority"
    ] == "admission-only"
    assert contract[
        "admissionState"
    ] == "admitted-not-consumed"
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "policyMutation": "not-allowed",
    }


def test_direct_cli_admits_without_execution():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "grant_admission.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Starter Gate OK: "
        "admitted-not-consumed / "
        "consumer=dispatch-office / "
        "consumed=false / executed=false / "
        "bondik-city-grant-admission-record/1"
        in result.stdout
    )
