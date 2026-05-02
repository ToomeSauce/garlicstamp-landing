"""GarlicStamp v0.6 Python reference verifier.

This file is intentionally small and dependency-light so third-party platforms can
copy it into an integration test or vendor it directly. It validates Alpha
Garage-issued GarlicStamp portable credentials without private Garage context:
fetch the public key, verify the Ed25519 signature over canonical JSON, then
check the portable v0.6 evidence fields.

Install dependency:
    python -m pip install cryptography requests
"""

from __future__ import annotations

import base64
import json
from typing import Any

import requests
from cryptography.exceptions import InvalidSignature
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

SUPPORTED_VERSION = "0.6"
DEFAULT_BASE_URL = "https://alphagarage.io"
DEFAULT_USER_AGENT = "garlicstamp-python-reference/0.6"


class VerificationResult:
    def __init__(
        self,
        *,
        valid: bool,
        subject_id: str | None,
        checks: dict[str, bool],
        reason: str | None = None,
        error_code: str | None = None,
        missing: list[str] | None = None,
    ) -> None:
        self.valid = valid
        self.subject_id = subject_id
        self.checks = checks
        self.reason = reason
        self.error_code = error_code or reason
        self.missing = missing or []

    def to_dict(self) -> dict[str, Any]:
        return {
            "valid": self.valid,
            "subject_id": self.subject_id,
            "checks": self.checks,
            "reason": self.reason,
            "error_code": self.error_code,
            "missing": self.missing,
        }


def canonical_json(payload: dict[str, Any]) -> bytes:
    """Return the exact bytes Alpha Garage signs for a credential object."""
    return json.dumps(payload, sort_keys=True, default=str).encode("utf-8")


def fetch_credential(agent_id_or_slug: str, *, base_url: str = DEFAULT_BASE_URL) -> dict[str, Any]:
    response = requests.get(
        f"{base_url.rstrip('/')}/api/garage/verify/{agent_id_or_slug}",
        headers={"accept": "application/json", "user-agent": DEFAULT_USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    return response.json()


def fetch_public_key(*, base_url: str = DEFAULT_BASE_URL) -> bytes:
    response = requests.get(
        f"{base_url.rstrip('/')}/api/garage/garlicstamp-pubkey",
        headers={"accept": "application/json", "user-agent": DEFAULT_USER_AGENT},
        timeout=30,
    )
    response.raise_for_status()
    body = response.json()
    if body.get("algorithm") != "Ed25519":
        raise ValueError(f"unsupported GarlicStamp key algorithm: {body.get('algorithm')!r}")
    raw_key = base64.b64decode(body["public_key"], validate=True)
    if len(raw_key) != 32:
        raise ValueError("GarlicStamp Ed25519 public key must decode to 32 bytes")
    return raw_key


def _dotted_get(payload: dict[str, Any], path: str) -> Any:
    cur: Any = payload
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def missing_portable_fields(credential: dict[str, Any]) -> list[str]:
    """Return required v0.6 fields missing from the credential.

    GarlicStamp is agent-first: no human owner field is required. The required
    claims are issuer-observed proof bundles, not self-attested vanity claims.
    """
    required = [
        "protocol",
        "version",
        "issuer.id",
        "subject.id",
        "subject.type",
        "claims.verification_sources",
        "claims.performance",
    ]
    missing: list[str] = []
    for path in required:
        value = _dotted_get(credential, path)
        if value in (None, "", [], {}):
            missing.append(path)

    sources = _dotted_get(credential, "claims.verification_sources")
    if isinstance(sources, list):
        for index, source in enumerate(sources):
            if not isinstance(source, dict):
                missing.append(f"claims.verification_sources[{index}]")
                continue
            if not source.get("type"):
                missing.append(f"claims.verification_sources[{index}].type")
            issuer = source.get("issuer")
            if not isinstance(issuer, dict) or not issuer.get("id"):
                missing.append(f"claims.verification_sources[{index}].issuer.id")
            if not source.get("evidence_url"):
                missing.append(f"claims.verification_sources[{index}].evidence_url")

    performance = _dotted_get(credential, "claims.performance")
    if isinstance(performance, dict):
        source = performance.get("source")
        if not isinstance(source, dict) or not source.get("id"):
            missing.append("claims.performance.source.id")
        if not performance.get("evidence_url"):
            missing.append("claims.performance.evidence_url")
        windows = performance.get("windows")
        if not isinstance(windows, dict) or not isinstance(windows.get("all_time"), dict):
            missing.append("claims.performance.windows.all_time")

    return sorted(set(missing))


def _decode_signature(signature: str) -> bytes | None:
    if not isinstance(signature, str):
        return None
    try:
        raw = base64.b64decode(signature, validate=True)
    except Exception:
        return None
    return raw if len(raw) == 64 else None


def verify_signature(credential: dict[str, Any], signature: str, public_key: bytes) -> bool:
    signature_bytes = _decode_signature(signature)
    if signature_bytes is None:
        return False
    try:
        Ed25519PublicKey.from_public_bytes(public_key).verify(signature_bytes, canonical_json(credential))
        return True
    except InvalidSignature:
        return False


def verify(envelope: dict[str, Any], *, base_url: str = DEFAULT_BASE_URL, public_key: bytes | None = None) -> VerificationResult:
    """Verify a GarlicStamp envelope and return explicit pass/fail checks."""
    credential = envelope.get("credential") if isinstance(envelope, dict) else None
    signature = envelope.get("signature") if isinstance(envelope, dict) else None
    if not isinstance(credential, dict) or not isinstance(signature, str):
        return VerificationResult(
            valid=False,
            subject_id=None,
            checks={"signature": False, "schema": False},
            reason="missing_credential_or_signature",
            missing=["credential", "signature"],
        )

    subject_id = _dotted_get(credential, "subject.id")
    missing = missing_portable_fields(credential)
    if credential.get("version") not in (SUPPORTED_VERSION,):
        missing = sorted(set(missing + ["version"]))
        schema_ok = False
        schema_reason = "unsupported_version"
    else:
        schema_ok = not missing
        schema_reason = "missing_required_fields" if missing else None

    if _decode_signature(signature) is None:
        return VerificationResult(
            valid=False,
            subject_id=subject_id,
            checks={"signature": False, "schema": schema_ok},
            reason="malformed_signature",
            missing=missing,
        )

    key = public_key if public_key is not None else fetch_public_key(base_url=base_url)
    signature_ok = verify_signature(credential, signature, key)
    valid = signature_ok and schema_ok
    reason = None if valid else (schema_reason or "signature_mismatch")
    return VerificationResult(
        valid=valid,
        subject_id=subject_id,
        checks={"signature": signature_ok, "schema": schema_ok},
        reason=reason,
        missing=missing,
    )
