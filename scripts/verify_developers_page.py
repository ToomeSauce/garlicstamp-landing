#!/usr/bin/env python3
"""Smoke-check the GarlicStamp developer access page and developer-path API examples."""
from __future__ import annotations

import argparse
import json
import pathlib
import sys
import urllib.request

REQUIRED = [
    "GarlicStamp developer access",
    "agent trust infrastructure",
    "Who GarlicStamp is for",
    "Quickstart",
    "Request beta access",
    "API keys",
    "Manual beta approval",
    "automated later",
    "Scopes",
    "Rate limits",
    "Revocation",
    "Support",
    "credential:read",
    "verify:check",
    "widget:embed",
    "no human owner is required",
    "Alpha Garage remains the proof source",
    "does not accept self-attested vanity claims",
    "GET /api/garage/verify/{agent_id_or_slug}",
    "POST /api/garage/verify/check",
    "POST /api/garage/verify/resolve",
    "agent_id",
    "subject",
    "provenance_sources",
    "performance_snapshot",
    "warnings",
    "errors",
    "cache",
    "subject_not_found",
    "issuer_unavailable",
    "hosted-verification-endpoint.md",
    "curl -sS https://alphagarage.io/api/garage/verify/TheGoat",
    "signature_mismatch",
    "missing_required_fields",
    "developers [at] garlicstamp.com",
]


def read_source(source: str) -> str:
    if source.startswith("http://") or source.startswith("https://"):
        req = urllib.request.Request(source, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=25) as response:
            if response.status != 200:
                raise AssertionError(f"{source} returned HTTP {response.status}")
            return response.read().decode("utf-8", errors="replace")
    return pathlib.Path(source).read_text(encoding="utf-8")


def assert_page(source: str) -> None:
    html = read_source(source)
    for needle in REQUIRED:
        assert needle in html, f"{source} missing {needle!r}"


def fetch_json(url: str, method: str = "GET", body: dict | None = None) -> dict:
    data = None if body is None else json.dumps(body).encode("utf-8")
    req = urllib.request.Request(
        url,
        data=data,
        method=method,
        headers={"User-Agent": "Mozilla/5.0", "content-type": "application/json"},
    )
    with urllib.request.urlopen(req, timeout=25) as response:
        return json.loads(response.read().decode("utf-8"))


def assert_api_examples(base_url: str, agent: str) -> None:
    base = base_url.rstrip("/")
    envelope = fetch_json(f"{base}/api/garage/verify/{agent}")
    credential = envelope["credential"]
    signature = envelope["signature"]
    assert credential["protocol"] == "garlicstamp"
    assert credential["issuer"]["id"] == "alpha-garage"
    assert credential["subject"]["id"]
    assert credential["subject"]["type"] == "trading-agent"
    assert credential["claims"]["verification_sources"]
    assert credential["claims"]["performance"]

    canonical_id = credential["subject"]["id"]
    resolved = fetch_json(f"{base}/api/garage/verify/{canonical_id}")["credential"]["subject"]["id"]
    assert resolved == canonical_id, f"canonical identity drift: {resolved} != {canonical_id}"

    valid = fetch_json(f"{base}/api/garage/verify/check", "POST", {"credential": credential, "signature": signature})
    assert valid["valid"] is True and valid["checks"]["signature"] is True and valid["checks"]["schema"] is True

    tampered = json.loads(json.dumps(credential))
    tampered["subject"]["name"] = "Tampered"
    invalid = fetch_json(f"{base}/api/garage/verify/check", "POST", {"credential": tampered, "signature": signature})
    assert invalid["valid"] is False
    assert invalid.get("error_code") == "signature_mismatch" or invalid.get("reason") == "signature_mismatch"

    missing = json.loads(json.dumps(credential))
    missing["claims"].pop("performance", None)
    missing["claims"].pop("verification_sources", None)
    schema = fetch_json(f"{base}/api/garage/verify/check", "POST", {"credential": missing, "signature": signature})
    assert schema["valid"] is False and schema["checks"]["schema"] is False
    assert {"claims.performance", "claims.verification_sources"}.issubset(set(schema.get("missing") or []))


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--page", action="append", required=True, help="Local HTML file or live URL to check. Repeatable.")
    parser.add_argument("--api-base", default="https://alphagarage.io")
    parser.add_argument("--agent", default="TheGoat")
    parser.add_argument("--skip-api", action="store_true")
    args = parser.parse_args()

    for page in args.page:
        assert_page(page)
    if not args.skip_api:
        assert_api_examples(args.api_base, args.agent)
    print("GarlicStamp developers page smoke passed")
    return 0


if __name__ == "__main__":
    sys.exit(main())
