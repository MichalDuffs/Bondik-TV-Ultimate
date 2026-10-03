import copy
import subprocess
import sys
from pathlib import Path

import pytest

from tools.city.result_return import (
    _demo as result_return_demo,
)
from tools.city.result_view import (
    RESULT_CARD_PROTOCOL,
    CityResultViewError,
    build_result_card,
    load_contract,
)


ROOT = Path(__file__).resolve().parents[3]


def envelope():
    return result_return_demo()


def card(value=None, *, viewer_id="demo-human"):
    return build_result_card(
        value if value is not None else envelope(),
        viewer_id=viewer_id,
    )


def test_card_is_rendered_local():
    value = card()

    assert value["protocol"] == RESULT_CARD_PROTOCOL
    assert value["state"] == "rendered-local"
    assert value["authority"] == "presentation-only"


def test_card_preserves_named_human_audience():
    value = card()

    assert value["audience"] == {
        "kind": "human-local",
        "viewerId": "demo-human",
        "agentReadable": False,
    }


def test_card_presents_only_allowed_status():
    value = card()

    assert value["display"] == {
        "label": "Control Tower status",
        "value": "available",
    }


def test_card_is_non_executing():
    value = card()

    assert value["grantsPermission"] is False
    assert value["runtimeAuthority"] is False
    assert value["dispatchesCommand"] is False
    assert value["executesAction"] is False


def test_card_has_no_side_effect_channels():
    value = card()

    assert value["mutatesPolicy"] is False
    assert value["publishesEvent"] is False
    assert value["performsHandoff"] is False
    assert value["usesNetwork"] is False


def test_card_binds_result_receipt_and_evidence():
    source_envelope = envelope()
    value = card(source_envelope)

    assert value["source"]["resultId"] == (
        source_envelope["resultId"]
    )
    assert value["source"]["receiptId"] == (
        source_envelope["source"]["receiptId"]
    )
    assert value["source"]["evidenceId"] == (
        source_envelope["source"]["evidenceId"]
    )


def test_card_id_is_deterministic():
    source_envelope = envelope()

    first = card(source_envelope)
    second = card(source_envelope)

    assert first["cardId"] == second["cardId"]


def test_wrong_viewer_is_rejected():
    with pytest.raises(
        CityResultViewError,
        match="viewerId does not match",
    ):
        card(viewer_id="other-human")


def test_wrong_input_protocol_is_rejected():
    value = envelope()
    value["protocol"] = "other/1"

    with pytest.raises(
        CityResultViewError,
        match="protocol mismatch",
    ):
        card(value)


def test_wrong_input_authority_is_rejected():
    value = envelope()
    value["authority"] = "other"

    with pytest.raises(
        CityResultViewError,
        match="authority mismatch",
    ):
        card(value)


def test_agent_readable_result_is_rejected():
    value = envelope()
    value["audience"]["agentReadable"] = True

    with pytest.raises(
        CityResultViewError,
        match="non-agent-readable",
    ):
        card(value)


def test_runtime_authority_is_rejected():
    value = envelope()
    value["runtimeAuthority"] = True

    with pytest.raises(
        CityResultViewError,
        match="unsafe result envelope field",
    ):
        card(value)


def test_unknown_command_is_rejected():
    value = envelope()
    value["command"]["commandType"] = "city.github.read"

    with pytest.raises(
        CityResultViewError,
        match="not presentation-allowed",
    ):
        card(value)


def test_wrong_target_is_rejected():
    value = envelope()
    value["command"]["targetBuildingId"] = "github-service"

    with pytest.raises(
        CityResultViewError,
        match="targetBuildingId mismatch",
    ):
        card(value)


def test_non_read_only_source_is_rejected():
    value = envelope()
    value["command"]["mutation"] = "write"

    with pytest.raises(
        CityResultViewError,
        match="mutation mismatch",
    ):
        card(value)


def test_extra_result_key_is_rejected():
    value = envelope()
    value["result"]["extra"] = "no"

    with pytest.raises(
        CityResultViewError,
        match="keys are not presentation-allowed",
    ):
        card(value)


def test_unapproved_status_is_rejected():
    value = envelope()
    value["result"]["status"] = "secret"

    with pytest.raises(
        CityResultViewError,
        match="status is not presentation-allowed",
    ):
        card(value)


def test_result_digest_mismatch_is_rejected():
    value = envelope()
    value["resultDigest"] = "sha256:" + "0" * 64

    with pytest.raises(
        CityResultViewError,
        match="result digest mismatch",
    ):
        card(value)


def test_input_is_not_mutated():
    value = envelope()
    snapshot = copy.deepcopy(value)

    card(value)

    assert value == snapshot


def test_contract_is_one_command_human_local_only():
    value = load_contract()

    assert set(value["allowedCommands"]) == {
        "city.status.read"
    }
    assert value["audience"] == {
        "kind": "human-local",
        "agentReadable": False,
    }
    assert value["exposure"]["agentResult"] == "not-exposed"


def test_direct_cli_renders_bounded_result_card():
    completed = subprocess.run(
        [
            sys.executable,
            str(
                ROOT
                / "tools"
                / "city"
                / "result_view.py"
            ),
        ],
        cwd=ROOT,
        capture_output=True,
        text=True,
        check=False,
    )

    assert completed.returncode == 0, completed.stdout
    assert (
        "Bondik City Result Window OK: "
        "rendered-local / "
        "viewer=demo-human / "
        "city.status.read=available / "
        "bondik-city-result-card/1"
        in completed.stdout
    )
