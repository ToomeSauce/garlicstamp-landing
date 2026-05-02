#!/usr/bin/env python3
"""Verify a GarlicStamp credential with the Python reference library.

Usage:
  python reference/python/example_verify.py TheGoat
  python reference/python/example_verify.py ./credential.json
"""

from __future__ import annotations

import copy
import json
import sys
from pathlib import Path

import garlicstamp


def load_input(arg: str) -> dict:
    path = Path(arg)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return garlicstamp.fetch_credential(arg)


def main() -> int:
    arg = sys.argv[1] if len(sys.argv) > 1 else "TheGoat"
    envelope = load_input(arg)

    tampered = copy.deepcopy(envelope)
    tampered["credential"]["subject"]["name"] = tampered["credential"]["subject"].get("name", "agent") + "-tampered"

    missing = copy.deepcopy(envelope)
    missing["credential"].setdefault("claims", {}).pop("performance", None)
    missing["credential"].setdefault("claims", {}).pop("verification_sources", None)

    summary = {
        "canonical": garlicstamp.verify(envelope).to_dict(),
        "tampered": garlicstamp.verify(tampered).to_dict(),
        "missing": garlicstamp.verify(missing).to_dict(),
    }
    print(json.dumps(summary, indent=2, sort_keys=True))
    return 0 if summary["canonical"]["valid"] and not summary["tampered"]["valid"] and not summary["missing"]["valid"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
