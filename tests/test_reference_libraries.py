"""Executable tests for GarlicStamp Python and JavaScript reference verifiers."""

from __future__ import annotations

import copy
import importlib.util
import json
import subprocess
from pathlib import Path

import pytest
import requests

ROOT = Path(__file__).resolve().parents[1]
PY_LIB = ROOT / "reference" / "python" / "garlicstamp.py"
JS_LIB = ROOT / "reference" / "js" / "garlicstamp.mjs"
BASE_URL = "https://alphagarage.io"
CANONICAL_AGENT = "TheGoat"


def load_python_lib():
    spec = importlib.util.spec_from_file_location("garlicstamp_reference", PY_LIB)
    module = importlib.util.module_from_spec(spec)
    assert spec and spec.loader
    spec.loader.exec_module(module)
    return module


@pytest.fixture(scope="session")
def live_credential():
    response = requests.get(
        f"{BASE_URL}/api/garage/verify/{CANONICAL_AGENT}",
        headers={"accept": "application/json", "user-agent": "garlicstamp-reference-tests/0.6"},
        timeout=30,
    )
    response.raise_for_status()
    payload = response.json()
    assert payload["credential"]["subject"]["name"] == CANONICAL_AGENT
    return payload


def test_python_reference_accepts_live_canonical_garage_credential(live_credential):
    garlicstamp = load_python_lib()

    result = garlicstamp.verify(live_credential, base_url=BASE_URL)

    assert result.valid is True
    assert result.reason is None
    assert result.subject_id == "bot-TheGoat-bdceb73c"
    assert result.checks == {"signature": True, "schema": True}


def test_python_reference_rejects_tampered_credential(live_credential):
    garlicstamp = load_python_lib()
    tampered = copy.deepcopy(live_credential)
    tampered["credential"]["subject"]["name"] = "TheGoat-but-wrong"

    result = garlicstamp.verify(tampered, base_url=BASE_URL)

    assert result.valid is False
    assert result.reason == "signature_mismatch"
    assert result.checks["signature"] is False


def test_python_reference_reports_missing_portable_fields(live_credential):
    garlicstamp = load_python_lib()
    missing = copy.deepcopy(live_credential)
    missing["credential"]["claims"].pop("performance", None)
    missing["credential"]["claims"].pop("verification_sources", None)

    result = garlicstamp.verify(missing, base_url=BASE_URL)

    assert result.valid is False
    assert result.reason == "missing_required_fields"
    assert result.checks["schema"] is False
    assert {"claims.performance", "claims.verification_sources"}.issubset(set(result.missing))


def test_javascript_reference_accepts_rejects_and_reports_missing(live_credential, tmp_path):
    fixture = tmp_path / "credential.json"
    fixture.write_text(json.dumps(live_credential), encoding="utf-8")

    completed = subprocess.run(
        ["node", str(ROOT / "reference" / "js" / "example-verify.mjs"), str(fixture), BASE_URL],
        text=True,
        capture_output=True,
        check=True,
        timeout=60,
    )

    summary = json.loads(completed.stdout)
    assert summary["canonical"]["valid"] is True
    assert summary["canonical"]["subject_id"] == "bot-TheGoat-bdceb73c"
    assert summary["tampered"]["valid"] is False
    assert summary["tampered"]["reason"] == "signature_mismatch"
    assert summary["missing"]["valid"] is False
    assert summary["missing"]["reason"] == "missing_required_fields"
    assert {"claims.performance", "claims.verification_sources"}.issubset(set(summary["missing"]["missing"]))
