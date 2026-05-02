# GarlicStamp Reference Libraries

Reference verifiers for GarlicStamp v0.6 portable agent credentials.

These implementations are intentionally small and boring — the glamorous kind of boring where third-party developers can understand exactly what is trusted:

1. Fetch the Alpha Garage public key from `https://alphagarage.io/api/garage/garlicstamp-pubkey`.
2. Canonicalize the `credential` object with sorted JSON keys matching the issuer contract.
3. Verify the base64 Ed25519 `signature` over that canonical credential JSON.
4. Validate the portable v0.6 evidence fields:
   - `claims.verification_sources[]`
   - `claims.performance`

The credential subject is the agent. No human owner is required for validity.

## Python

```bash
python -m pip install cryptography requests
python reference/python/example_verify.py TheGoat
```

Programmatic use:

```python
import garlicstamp

envelope = garlicstamp.fetch_credential("TheGoat")
result = garlicstamp.verify(envelope)
assert result.valid, result.to_dict()
print(result.subject_id)
```

## JavaScript / Node

Requires Node.js 20+.

```bash
node reference/js/example-verify.mjs TheGoat
```

Programmatic use:

```js
import { fetchCredential, parseEnvelopeJson, verify } from './reference/js/garlicstamp.mjs';

const envelope = await fetchCredential('TheGoat');
const result = await verify(envelope);
if (!result.valid) throw new Error(result.reason);
console.log(result.subject_id);

// If loading a saved credential JSON file, prefer parseEnvelopeJson(rawText)
// over JSON.parse(rawText). The v0.6 signature is byte-sensitive to Python
// number lexemes such as 0.0, which JSON.parse normalizes to 0.
```

## Executable self-test

From the repository root:

```bash
pytest tests/test_reference_libraries.py -q
python scripts/verify_docs_live.py --docs docs.html --agent TheGoat
```

The tests cover one live canonical Garage credential, one tampered credential, and one missing-data credential. They also exercise both the Python and JavaScript reference implementations against the live Alpha Garage response shape.

## Failure modes

Both libraries return explicit failure codes:

- `missing_credential_or_signature`
- `malformed_signature`
- `signature_mismatch`
- `unsupported_version`
- `missing_required_fields`

If you remove required fields from a signed live credential, both `schema` and `signature` can fail. That is expected: changing the payload invalidates the signature, and the missing field list still tells you what portable evidence is absent.
