#!/usr/bin/env python3
"""Live smoke test for garlicstamp.com/docs examples.

Checks that the static docs' required-field table agrees with the live
Alpha Garage GarlicStamp v0.6 response shape and hosted verifier behavior.
Uses `requests` so the smoke path matches normal third-party integrations.
"""

from __future__ import annotations

import argparse
import copy
import json
import sys
import requests
from html.parser import HTMLParser
from pathlib import Path
from typing import Any


class RequiredFieldParser(HTMLParser):
    def __init__(self) -> None:
        super().__init__()
        self.fields: list[str] = []

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        attrs_dict = dict(attrs)
        value = attrs_dict.get("data-required-field")
        if value:
            self.fields.append(value)


def get_json(url: str) -> dict[str, Any]:
    resp = requests.get(
        url,
        headers={"accept": "application/json", "user-agent": "garlicstamp-docs-smoke/1.0"},
        timeout=30,
    )
    if resp.status_code != 200:
        raise AssertionError(f"GET {url} returned {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def post_json(url: str, body: dict[str, Any]) -> dict[str, Any]:
    resp = requests.post(
        url,
        json=body,
        headers={
            "accept": "application/json",
            "user-agent": "garlicstamp-docs-smoke/1.0",
        },
        timeout=30,
    )
    if resp.status_code != 200:
        raise AssertionError(f"POST {url} returned {resp.status_code}: {resp.text[:200]}")
    return resp.json()


def dotted_get(payload: dict[str, Any], path: str) -> Any:
    cur: Any = payload
    for part in path.split("."):
        if not isinstance(cur, dict) or part not in cur:
            return None
        cur = cur[part]
    return cur


def assert_live_field(credential: dict[str, Any], signature: str, field: str) -> None:
    if field == "signature":
        assert isinstance(signature, str) and len(signature) == 88, "signature should be 88-char base64 Ed25519 material"
        return
    value = dotted_get(credential, field)
    assert value not in (None, "", [], {}), f"live credential missing required docs field: {field}"


def assert_verification_sources(sources: Any) -> None:
    assert isinstance(sources, list) and sources, "verification_sources must be a non-empty array"
    for i, source in enumerate(sources):
        assert isinstance(source, dict), f"verification_sources[{i}] must be an object"
        assert source.get("type"), f"verification_sources[{i}].type missing"
        assert isinstance(source.get("issuer"), dict) and source["issuer"].get("id"), f"verification_sources[{i}].issuer.id missing"
        assert source.get("evidence_url"), f"verification_sources[{i}].evidence_url missing"


def assert_performance(performance: Any) -> None:
    assert isinstance(performance, dict), "performance must be an object"
    assert isinstance(performance.get("source"), dict) and performance["source"].get("id"), "performance.source.id missing"
    assert performance.get("evidence_url"), "performance.evidence_url missing"
    assert isinstance(performance.get("windows"), dict) and isinstance(performance["windows"].get("all_time"), dict), "performance.windows.all_time missing"


def main() -> int:
    parser = argparse.ArgumentParser(description="Verify garlicstamp.com/docs against the live GarlicStamp v0.6 API")
    parser.add_argument("--docs", default="docs.html", help="Path to docs.html")
    parser.add_argument("--base-url", default="https://alphagarage.io", help="Issuer base URL")
    parser.add_argument("--agent", default="TheGoat", help="Canonical agent id or slug to smoke-test")
    args = parser.parse_args()

    docs_path = Path(args.docs)
    html = docs_path.read_text(encoding="utf-8")
    parser_obj = RequiredFieldParser()
    parser_obj.feed(html)
    docs_fields = set(parser_obj.fields)
    expected_docs_fields = {
        "protocol",
        "version",
        "issuer.id",
        "subject.id",
        "subject.type",
        "claims.verification_sources",
        "claims.performance",
        "signature",
    }
    assert expected_docs_fields.issubset(docs_fields), f"docs missing data-required-field markers: {sorted(expected_docs_fields - docs_fields)}"

    hosted_resolver_needles = [
        "POST /api/garage/verify/resolve",
        "agent_id",
        "url",
        "subject",
        "credential",
        "provenance_sources",
        "performance_snapshot",
        "warnings",
        "errors",
        "cache",
        "unsupported_lookup",
        "subject_not_found",
        "issuer_unavailable",
        "hosted-verification-endpoint.md",
    ]
    for needle in hosted_resolver_needles:
        assert needle in html, f"docs hosted resolver scope missing {needle!r}"

    base = args.base_url.rstrip("/")
    spec = get_json(f"{base}/api/garage/garlicstamp/spec")
    assert spec.get("protocol") == "garlicstamp", "spec protocol mismatch"
    assert spec.get("version") == "0.6", "spec version mismatch"
    assert spec.get("issuer", {}).get("id") == "alpha-garage", "spec issuer mismatch"
    assert set(spec.get("required_claims", [])) >= {"verification_sources", "performance"}, "spec required_claims missing portable bundles"

    live = get_json(f"{base}/api/garage/verify/{args.agent}")
    credential = live.get("credential")
    signature = live.get("signature")
    assert isinstance(credential, dict), "live response missing credential object"
    assert isinstance(signature, str), "live response missing signature string"

    for field in docs_fields:
        assert_live_field(credential, signature, field)
    assert credential["version"] == spec["version"], "docs/live/spec credential version mismatch"
    assert credential["issuer"]["id"] == spec["issuer"]["id"], "docs/live/spec issuer mismatch"
    assert_verification_sources(credential["claims"]["verification_sources"])
    assert_performance(credential["claims"]["performance"])

    check_url = spec["verification_endpoint"].replace("https://alphagarage.io", base)
    valid = post_json(check_url, live)
    assert valid.get("valid") is True, f"canonical credential rejected: {valid}"
    assert valid.get("checks", {}).get("signature") is True, f"canonical signature check failed: {valid}"
    assert valid.get("checks", {}).get("schema") is True, f"canonical schema check failed: {valid}"

    tampered = copy.deepcopy(live)
    tampered["credential"]["subject"]["name"] = tampered["credential"]["subject"].get("name", "agent") + "-tampered"
    tampered_result = post_json(check_url, tampered)
    assert tampered_result.get("valid") is False, f"tampered credential unexpectedly valid: {tampered_result}"
    assert tampered_result.get("reason") == "signature_mismatch", f"tampered reason should be signature_mismatch: {tampered_result}"
    assert tampered_result.get("checks", {}).get("signature") is False, f"tampered signature check should fail: {tampered_result}"

    missing = copy.deepcopy(live)
    missing["credential"].setdefault("claims", {}).pop("performance", None)
    missing["credential"].setdefault("claims", {}).pop("verification_sources", None)
    missing_result = post_json(check_url, missing)
    missing_fields = set(missing_result.get("missing") or [])
    assert missing_result.get("valid") is False, f"missing-data credential unexpectedly valid: {missing_result}"
    assert missing_result.get("checks", {}).get("schema") is False, f"missing-data schema check should fail: {missing_result}"
    assert {"claims.performance", "claims.verification_sources"}.issubset(missing_fields), f"missing-data response missing required paths: {missing_result}"

    print(json.dumps({
        "docs_fields": sorted(docs_fields),
        "agent": credential["subject"],
        "valid_result": valid,
        "tampered_result": tampered_result,
        "missing_result": missing_result,
    }, indent=2, sort_keys=True))
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"docs smoke failed: {exc}", file=sys.stderr)
        raise SystemExit(1)
