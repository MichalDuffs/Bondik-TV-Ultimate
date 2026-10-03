import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.authorized_dispatch import (
    _build_demo_sources,
    execute_authorized_read_only,
)
from tools.city.execution_evidence import (
    EVIDENCE_PROTOCOL,
    CityExecutionEvidenceError,
    build_execution_evidence,
    load_contract,
)
from tools.city.storage_adapter import (
    MemoryStorageAdapter,
)


ROOT = Path(__file__).resolve().parents[3]


def source():
    grant, packet, preflight, dispatcher = (
        _build_demo_sources()
    )
    storage = MemoryStorageAdapter()
    receipt = execute_authorized_read_only(
        grant,
        packet,
        preflight,
        dispatcher=dispatcher,
        storage=storage,
        executed_at=(
            "2026-10-03T23:00:00+02:00"
        ),
    )
    return receipt, storage


def evidence(receipt=None, storage=None):
    default_receipt, default_storage = (
        source()
    )
    return build_execution_evidence(
        (
            receipt
            if receipt is not None
            else default_receipt
        ),
        storage=(
            storage
            if storage is not None
            else default_storage
        ),
    )


def test_evidence_is_verified_completed():
    value = evidence()

    assert value["protocol"] == (
        EVIDENCE_PROTOCOL
    )
    assert value["state"] == (
        "verified-completed"
    )
    assert value["verification"] == {
        "receiptMatchesStorage": True,
        "resultDigestVerified": True,
        "singleUseConsumptionVerified": True,
    }


def test_evidence_is_non_executing():
    value = evidence()

    assert value["dispatchesCommand"] is False
    assert value["executesAction"] is False
    assert value["grantsPermission"] is False
    assert value["runtimeAuthority"] is False


def test_evidence_does_not_copy_result_content():
    value = evidence()

    assert value["command"][
        "resultContent"
    ] == "not-copied"
    assert "result" not in value["command"]
    assert value["command"][
        "resultDigest"
    ].startswith("sha256:")


def test_receipt_and_storage_revision_are_bound():
    receipt, storage = source()
    value = build_execution_evidence(
        receipt,
        storage=storage,
    )

    assert value["receipt"][
        "receiptId"
    ] == receipt["receiptId"]
    assert value["grant"][
        "consumptionRevision"
    ] == 2


def test_evidence_id_is_deterministic():
    receipt, storage = source()

    first = build_execution_evidence(
        receipt,
        storage=storage,
    )
    second = build_execution_evidence(
        receipt,
        storage=storage,
    )

    assert first["evidenceId"] == (
        second["evidenceId"]
    )


def test_missing_consumption_record_is_rejected():
    receipt, _storage = source()

    with pytest.raises(
        CityExecutionEvidenceError,
        match="record is missing",
    ):
        build_execution_evidence(
            receipt,
            storage=MemoryStorageAdapter(),
        )


def test_consumption_revision_mismatch_is_rejected():
    receipt, storage = source()
    receipt["grant"][
        "consumptionRevision"
    ] = 3

    with pytest.raises(
        CityExecutionEvidenceError,
        match="revision mismatch",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


def test_tampered_result_is_rejected():
    receipt, storage = source()
    receipt["command"]["result"][
        "status"
    ] = "tampered"

    with pytest.raises(
        CityExecutionEvidenceError,
        match="result digest mismatch",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


def test_tampered_storage_result_digest_is_rejected():
    receipt, storage = source()
    record = storage.read(
        "city.dispatch.spent",
        receipt["grant"]["grantId"],
    )
    record["value"]["resultDigest"] = (
        "sha256:" + "0" * 64
    )
    storage.write(
        "city.dispatch.spent",
        receipt["grant"]["grantId"],
        record["value"],
        expected_revision=2,
    )
    receipt["grant"][
        "consumptionRevision"
    ] = 3

    with pytest.raises(
        CityExecutionEvidenceError,
        match="consumption evidence mismatch: resultDigest",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


def test_non_completed_receipt_is_rejected():
    receipt, storage = source()
    receipt["state"] = "other"

    with pytest.raises(
        CityExecutionEvidenceError,
        match="dispatched-consumed",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


def test_non_read_only_receipt_is_rejected():
    receipt, storage = source()
    receipt["command"]["mutation"] = "write"

    with pytest.raises(
        CityExecutionEvidenceError,
        match="must be read-only",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


def test_network_use_is_rejected():
    receipt, storage = source()
    receipt["usesNetwork"] = True

    with pytest.raises(
        CityExecutionEvidenceError,
        match="safety field invalid",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


@pytest.mark.parametrize(
    "field",
    [
        "grantConsumed",
        "consumerConnected",
        "dispatchesCommand",
        "executesAction",
    ],
)
def test_completion_flags_must_be_true(
    field,
):
    receipt, storage = source()
    receipt[field] = False

    with pytest.raises(
        CityExecutionEvidenceError,
        match="completion field invalid",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


def test_source_grant_immutability_must_be_preserved():
    receipt, storage = source()
    receipt["grant"][
        "sourceArtifactConsumed"
    ] = True

    with pytest.raises(
        CityExecutionEvidenceError,
        match="must remain immutable",
    ):
        build_execution_evidence(
            receipt,
            storage=storage,
        )


def test_invalid_storage_is_rejected():
    receipt, _storage = source()

    with pytest.raises(
        CityExecutionEvidenceError,
        match="storage adapter is invalid",
    ):
        build_execution_evidence(
            receipt,
            storage=object(),
        )


def test_inputs_are_not_mutated():
    receipt, storage = source()
    snapshot = copy.deepcopy(receipt)

    build_execution_evidence(
        receipt,
        storage=storage,
    )

    assert receipt == snapshot


def test_contract_is_digest_only_evidence():
    contract = load_contract()

    assert contract["authority"] == (
        "evidence-only"
    )
    assert contract["evidenceState"] == (
        "verified-completed"
    )
    assert contract["exposure"][
        "resultContent"
    ] == "digest-only"


def test_direct_cli_verifies_completed_dispatch():
    result = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "execution_evidence.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert result.returncode == 0, result.stdout
    assert (
        "Bondik City Receipt Office OK: "
        "verified-completed / "
        "command=city.status.read / "
        "receipt-storage=true / result-digest=true / "
        "bondik-city-execution-evidence-record/1"
        in result.stdout
    )
