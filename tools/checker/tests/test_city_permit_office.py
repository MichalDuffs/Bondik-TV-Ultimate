import pytest

from tools.city.permit_office import (
    PERMIT_PROTOCOL,
    CityPermitError,
    load_contract,
    prepare_permit_request,
)


def base_kwargs():
    return {
        "ticket_id": "permit-001",
        "principal": {
            "id": "demo-agent",
            "role": "observer",
        },
        "operation": "command",
        "capability_id": (
            "city.command-boundary.local"
        ),
        "reason": "Need human review.",
        "requested_at": (
            "2026-10-03T20:30:00+02:00"
        ),
    }


def test_prepare_command_ticket_stays_pending():
    ticket = prepare_permit_request(
        **base_kwargs()
    )

    assert ticket["protocol"] == (
        PERMIT_PROTOCOL
    )
    assert ticket["status"] == (
        "pending-human-review"
    )
    assert ticket["currentPolicy"] == {
        "decision": "deny",
        "reason": (
            "operation-denied-by-policy"
        ),
    }
    assert ticket["review"] == {
        "required": True,
        "reviewerKind": "human",
        "decision": None,
    }
    assert ticket["grantsPermission"] is False


def test_ticket_resolves_target_location():
    ticket = prepare_permit_request(
        **base_kwargs()
    )

    assert ticket["route"][
        "locationId"
    ] == "dispatch-office"


@pytest.mark.parametrize(
    "operation",
    [
        "command",
        "handoff",
        "mutate",
        "publish-event",
        "execute",
    ],
)
def test_fixed_requestable_operations(
    operation,
):
    kwargs = base_kwargs()
    kwargs["operation"] = operation

    ticket = prepare_permit_request(
        **kwargs
    )

    assert ticket["request"][
        "operation"
    ] == operation
    assert ticket["grantsPermission"] is False


def test_non_requestable_operation_is_rejected():
    kwargs = base_kwargs()
    kwargs["operation"] = (
        "inspect-evidence"
    )

    with pytest.raises(
        CityPermitError,
        match="not requestable",
    ):
        prepare_permit_request(
            **kwargs
        )


def test_bad_ticket_id_is_rejected():
    kwargs = base_kwargs()
    kwargs["ticket_id"] = "bad ticket id"

    with pytest.raises(
        CityPermitError,
        match="ticketId is invalid",
    ):
        prepare_permit_request(
            **kwargs
        )


def test_timestamp_requires_timezone():
    kwargs = base_kwargs()
    kwargs["requested_at"] = (
        "2026-10-03T20:30:00"
    )

    with pytest.raises(
        CityPermitError,
        match="include timezone",
    ):
        prepare_permit_request(
            **kwargs
        )


def test_reason_is_required():
    kwargs = base_kwargs()
    kwargs["reason"] = " "

    with pytest.raises(
        CityPermitError,
        match="non-empty string",
    ):
        prepare_permit_request(
            **kwargs
        )


def test_reason_limit_is_enforced():
    kwargs = base_kwargs()
    kwargs["reason"] = "x" * 1025

    with pytest.raises(
        CityPermitError,
        match="size limit",
    ):
        prepare_permit_request(
            **kwargs
        )


def test_unknown_capability_stays_pending_and_unresolved():
    kwargs = base_kwargs()
    kwargs["capability_id"] = (
        "city.missing.capability"
    )

    ticket = prepare_permit_request(
        **kwargs
    )

    assert ticket["status"] == (
        "pending-human-review"
    )
    assert ticket["currentPolicy"][
        "decision"
    ] == "deny"
    assert ticket["route"] == {
        "status": "unresolved",
        "locationId": None,
    }
    assert ticket["grantsPermission"] is False


def test_contract_is_request_only():
    contract = load_contract()

    assert contract["authority"] == (
        "request-only"
    )
    assert contract["ticketStatus"] == (
        "pending-human-review"
    )
    assert contract["exposure"] == {
        "execution": "not-exposed",
        "mutation": "not-allowed",
        "network": "not-exposed",
        "permissionGrant": "not-allowed",
        "autoApproval": "not-allowed",
    }
