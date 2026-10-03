import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.execution_evidence import (
    _demo as evidence_demo,
    build_execution_evidence,
)
from tools.city.result_return import (
    RESULT_PROTOCOL,
    CityResultReturnError,
    load_contract,
    prepare_verified_result,
)


ROOT = Path(__file__).resolve().parents[3]


def source():
    receipt, storage = evidence_demo()
    evidence = build_execution_evidence(
        receipt,
        storage=storage,
    )
    return receipt, evidence


def result(
    receipt=None,
    evidence=None,
    *,
    viewer_id="michal",
):
    default_receipt, default_evidence = source()
    return prepare_verified_result(
        receipt if receipt is not None else default_receipt,
        evidence if evidence is not None else default_evidence,
        viewer_id=viewer_id,
    )


def test_result_is_verified_ready():
    value = result()
    assert value["protocol"] == RESULT_PROTOCOL
    assert value["state"] == "verified-result-ready"
    assert value["verified"] is True


def test_result_is_human_local_only():
    value = result()
    assert value["audience"] == {
        "kind": "human-local",
        "viewerId": "michal",
        "agentReadable": False,
    }
    assert value["exposure"]["agentResult"] == "not-exposed"


def test_result_content_is_returned_after_verification():
    value = result()
    assert value["result"] == {"status": "available"}
    assert value["resultDigest"].startswith("sha256:")


def test_result_layer_is_non_executing():
    value = result()
    assert value["dispatchesCommand"] is False
    assert value["executesAction"] is False
    assert value["grantsPermission"] is False
    assert value["runtimeAuthority"] is False


def test_result_layer_has_no_side_effect_channels():
    value = result()
    assert value["mutatesPolicy"] is False
    assert value["publishesEvent"] is False
    assert value["performsHandoff"] is False
    assert value["usesNetwork"] is False


def test_source_digests_are_bound():
    receipt, evidence = source()
    value = prepare_verified_result(
        receipt,
        evidence,
        viewer_id="michal",
    )
    assert value["source"]["receiptId"] == receipt["receiptId"]
    assert value["source"]["evidenceId"] == evidence["evidenceId"]
    assert value["source"]["receiptDigest"].startswith("sha256:")
    assert value["source"]["evidenceDigest"].startswith("sha256:")


def test_result_id_is_deterministic():
    receipt, evidence = source()
    first = prepare_verified_result(
        receipt,
        evidence,
        viewer_id="michal",
    )
    second = prepare_verified_result(
        receipt,
        evidence,
        viewer_id="michal",
    )
    assert first["resultId"] == second["resultId"]


def test_viewer_is_part_of_result_identity():
    receipt, evidence = source()
    first = prepare_verified_result(
        receipt,
        evidence,
        viewer_id="michal",
    )
    second = prepare_verified_result(
        receipt,
        evidence,
        viewer_id="other-human",
    )
    assert first["resultId"] != second["resultId"]


def test_invalid_viewer_is_rejected():
    with pytest.raises(
        CityResultReturnError,
        match="viewerId is invalid",
    ):
        result(viewer_id="bad viewer")


def test_tampered_receipt_digest_is_rejected():
    receipt, evidence = source()
    evidence["receipt"]["receiptDigest"] = "sha256:" + "0" * 64
    with pytest.raises(
        CityResultReturnError,
        match="receipt digest mismatch",
    ):
        result(receipt, evidence)


def test_tampered_receipt_result_is_rejected():
    receipt, evidence = source()
    receipt["command"]["result"]["status"] = "tampered"

    # Rebind the evidence receipt digest so this test reaches the
    # independent result-digest check instead of correctly failing
    # earlier at full receipt-integrity verification.
    evidence["receipt"]["receiptDigest"] = (
        "sha256:"
        + __import__("hashlib").sha256(
            __import__("json").dumps(
                receipt,
                ensure_ascii=False,
                sort_keys=True,
                separators=(",", ":"),
            ).encode("utf-8")
        ).hexdigest()
    )

    with pytest.raises(
        CityResultReturnError,
        match="receipt result digest mismatch",
    ):
        result(receipt, evidence)


def test_tampered_evidence_result_digest_is_rejected():
    receipt, evidence = source()
    evidence["command"]["resultDigest"] = "sha256:" + "0" * 64
    with pytest.raises(
        CityResultReturnError,
        match="evidence result digest mismatch",
    ):
        result(receipt, evidence)


def test_command_identity_mismatch_is_rejected():
    receipt, evidence = source()
    evidence["command"]["commandId"] = "other-command"
    with pytest.raises(
        CityResultReturnError,
        match="command evidence mismatch",
    ):
        result(receipt, evidence)


def test_non_verified_evidence_is_rejected():
    receipt, evidence = source()
    evidence["state"] = "other"
    with pytest.raises(
        CityResultReturnError,
        match="verified-completed",
    ):
        result(receipt, evidence)


def test_evidence_with_execution_authority_is_rejected():
    receipt, evidence = source()
    evidence["runtimeAuthority"] = True
    with pytest.raises(
        CityResultReturnError,
        match="evidence safety field invalid",
    ):
        result(receipt, evidence)


def test_evidence_verification_must_be_complete():
    receipt, evidence = source()
    evidence["verification"]["receiptMatchesStorage"] = False
    with pytest.raises(
        CityResultReturnError,
        match="verification invalid",
    ):
        result(receipt, evidence)


def test_inputs_are_not_mutated():
    receipt, evidence = source()
    receipt_snapshot = copy.deepcopy(receipt)
    evidence_snapshot = copy.deepcopy(evidence)
    result(receipt, evidence)
    assert receipt == receipt_snapshot
    assert evidence == evidence_snapshot


def test_contract_is_human_local_return_only():
    contract = load_contract()
    assert contract["authority"] == "human-local-result-return-only"
    assert contract["resultState"] == "verified-result-ready"
    assert contract["audience"] == {
        "kind": "human-local",
        "agentReadable": False,
    }


def test_contract_keeps_agent_result_closed():
    contract = load_contract()
    assert contract["exposure"]["agentResult"] == "not-exposed"
    assert contract["exposure"]["execution"] == "not-exposed"


def test_direct_cli_returns_verified_human_result():
    completed = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "result_return.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )
    assert completed.returncode == 0, completed.stdout
    assert (
        "Bondik City Result Office OK: "
        "verified-result-ready / "
        "command=city.status.read / "
        "viewer=demo-human / "
        "result=available / "
        "bondik-city-verified-result-envelope/1"
        in completed.stdout
    )
