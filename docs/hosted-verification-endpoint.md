# Hosted GarlicStamp verification endpoint scope (v0.7)

## Decision

Add a hosted resolver/verifier endpoint that lets a third-party platform make **one HTTP call** and receive:

- a trustworthy `valid` answer;
- the canonical GarlicStamp agent identity;
- issuer/provenance/signature context needed to render the result safely;
- a small Garage-sourced performance snapshot; and
- deterministic warnings/errors/cache metadata.

This is a scope document for GarlicStamp v0.7. It does not change the trust model: **the credential subject is the agent, Alpha Garage is the first proof source, and GarlicStamp does not accept self-attested vanity claims.** Human owner linkage may be displayed later, but it is never required for credential validity.

## Endpoint

```http
POST https://alphagarage.io/api/garage/verify/resolve
content-type: application/json
```

`GET /api/garage/verify/{agent_id_or_slug}` remains the raw signed credential fetch. `POST /api/garage/verify/check` remains the envelope-only checker. The resolver is the developer-friendly hosted path for integrations that need full profile resolution, not just a public key and a boolean.

## Request shape

Exactly one lookup mode is required.

```json
{
  "lookup": {
    "type": "agent_id",
    "value": "TheGoat"
  },
  "include": ["credential", "performance_snapshot", "widget"],
  "client": {
    "platform": "example-directory",
    "request_id": "optional-idempotency-or-log-correlation-id"
  }
}
```

Supported `lookup.type` values:

| Type | Value | Resolution rule |
|---|---|---|
| `agent_id` | Garage canonical id or public slug, e.g. `bot-TheGoat-bdceb73c` or `TheGoat` | Resolve to the canonical signed `credential.subject.id`. Slugs are convenience inputs only. Integrations should store the canonical subject id from the response. |
| `url` | Garage public profile URL, e.g. `https://alphagarage.io/garage/agents/bot-TheGoat-bdceb73c` | Parse only recognized Alpha Garage public agent URLs; reject arbitrary domains. |
| `subject` | DID-like subject identifier, e.g. `did:garlic:alpha-garage:bot-TheGoat-bdceb73c` | Resolve namespace `alpha-garage` and subject id. Future namespaces require explicit issuer trust decisions. |
| `credential` | Full `{credential, signature}` envelope | Verify the supplied envelope and, when possible, resolve the subject back to the current Garage public profile. |

A compact credential lookup may also be sent as:

```json
{
  "lookup": {
    "type": "credential",
    "credential": {"protocol": "garlicstamp", "version": "0.6"},
    "signature": "base64-ed25519-signature"
  }
}
```

Reject requests that include multiple lookup modes, missing values, unrecognized URL hosts, unsupported subject namespaces, or oversized credential bodies.

## Response schema

### Valid response

```json
{
  "valid": true,
  "status": "verified",
  "resolved_via": "agent_id",
  "subject": {
    "id": "bot-TheGoat-bdceb73c",
    "did": "did:garlic:alpha-garage:bot-TheGoat-bdceb73c",
    "name": "TheGoat",
    "type": "trading-agent",
    "profile_url": "https://alphagarage.io/garage/agents/bot-TheGoat-bdceb73c",
    "aliases": ["TheGoat"]
  },
  "issuer": {
    "id": "alpha-garage",
    "name": "Alpha Garage",
    "url": "https://alphagarage.io",
    "proof_source": true
  },
  "credential": {
    "protocol": "garlicstamp",
    "version": "0.6",
    "subject": {"id": "bot-TheGoat-bdceb73c"}
  },
  "signatures": {
    "algorithm": "Ed25519",
    "key_id": "garage-prod-2026-04",
    "public_key_url": "https://alphagarage.io/api/garage/garlicstamp-pubkey",
    "signature_valid": true,
    "schema_valid": true
  },
  "provenance_sources": [
    {
      "type": "garage_registration",
      "issuer": {"id": "alpha-garage"},
      "evidence_url": "https://alphagarage.io/garage/agents/bot-TheGoat-bdceb73c"
    }
  ],
  "performance_snapshot": {
    "source": {"id": "alpha-garage", "name": "Alpha Garage"},
    "as_of": "2026-05-02T00:00:00Z",
    "profile_url": "https://alphagarage.io/garage/agents/bot-TheGoat-bdceb73c",
    "windows": {
      "all_time": {
        "total_pnl": 1234.56,
        "win_rate": 0.64,
        "sharpe_ratio": 1.21,
        "rank": {"position": 3, "total_agents": 42}
      }
    }
  },
  "widget": {
    "badge_url": "https://alphagarage.io/api/garage/verify/bot-TheGoat-bdceb73c/badge",
    "embed_html": "<a href=\"https://alphagarage.io/garage/agents/bot-TheGoat-bdceb73c\" rel=\"noopener\">GarlicStamped</a>"
  },
  "warnings": [],
  "errors": [],
  "cache": {
    "cacheable": true,
    "max_age_seconds": 300,
    "stale_while_revalidate_seconds": 86400,
    "etag": "W/\"garlicstamp-bot-TheGoat-bdceb73c-...\""
  }
}
```

### Invalid but deterministic response

Use structured JSON for every failure. Do not return HTML error pages to API clients.

```json
{
  "valid": false,
  "status": "rejected",
  "resolved_via": "credential",
  "subject": null,
  "issuer": {"id": "alpha-garage"},
  "signatures": {"signature_valid": false, "schema_valid": null},
  "provenance_sources": [],
  "performance_snapshot": null,
  "warnings": [],
  "errors": [
    {
      "code": "signature_mismatch",
      "message": "Credential signature did not verify against the trusted Alpha Garage key.",
      "field": "signature",
      "retryable": false
    }
  ],
  "cache": {"cacheable": false, "max_age_seconds": 0}
}
```

## Error codes and HTTP status

| HTTP | `errors[].code` | Meaning | Integration behavior |
|---:|---|---|---|
| 200 | _none_ | Verified. `valid=true`. | Safe to render as Garage-backed proof with the returned subject/provenance context. |
| 200 | `signature_mismatch` | Envelope was altered, canonicalization differs, or wrong key. | Do not render as verified. Show actionable failure, not a badge. |
| 200 | `missing_required_fields` | Signature may be valid but portable fields are absent. | Reject for trust decisions; inspect `errors[].field`/`missing[]`. |
| 400 | `invalid_request` | Missing lookup, multiple lookup modes, malformed JSON, unsupported include. | Fix request; do not retry unchanged. |
| 400 | `unsupported_lookup` | Lookup type, URL host, or subject namespace is not supported. | Use Garage agent id/URL, a Garlic subject DID, or a credential envelope. |
| 404 | `subject_not_found` | No public Garage agent/profile resolved. | Do not invent profile data or fall back to vanity claims. |
| 409 | `identity_conflict` | Lookup resolves to multiple or inconsistent canonical subjects. | Treat as unverified and contact support. |
| 422 | `unsupported_version` | Credential version is not accepted by the hosted verifier. | Refresh against `/api/garage/garlicstamp/spec`. |
| 429 | `rate_limited` | Consumer exceeded public or key-scoped limit. | Honor `Retry-After`; cache successful lookups. |
| 503 | `issuer_unavailable` | Garage proof source cannot be reached or verified. | Show temporary unavailable; do not silently mark invalid. |

`valid=false` does not always mean fraud. It means the verifier cannot safely assert GarlicStamped proof for this input.

## Cache semantics

- Successful public profile resolutions: `Cache-Control: public, max-age=300, stale-while-revalidate=86400` and `ETag` keyed by canonical subject id + credential version/signature.
- Raw public key/spec responses may keep the existing longer cache (`max-age=86400`) because they change rarely.
- Failures caused by malformed requests are not cacheable.
- `subject_not_found` may be cached for at most 60 seconds to avoid pinning newly registered agents as missing.
- `issuer_unavailable` is never proof of invalidity and should not be cached as a negative trust result.
- API-key-authenticated/high-volume callers may receive stricter private cache headers if policy requires it, but the response body shape stays identical.

## Privacy and security boundaries

- Return only public Garage profile/evidence data and signed credential fields; never leak private strategy prompts, owner emails, API keys, account ids, brokerage details, or internal notes.
- The resolver may display a human owner link later, but human ownership is optional metadata and not required for `valid=true`.
- Do not accept third-party self-attested claims as provenance. External URLs can be inputs only when they are recognized Garage profile URLs.
- Canonical subject identity comes from the signed credential and Garage profile resolution, not caller-supplied names, slugs, or display copy.
- All failures are deterministic JSON with stable codes. No ambiguous `500` for expected validation failures. We are building trust infrastructure, not a haunted vending machine.
- Logs should record lookup type, canonical subject id when resolved, consumer key/platform when present, and result code; do not log full submitted credentials from third parties unless explicitly sampled/redacted for debugging.

## Implementation subtasks

1. **Backend resolver**
   - Add `POST /api/garage/verify/resolve` in Garage API.
   - Normalize lookup modes (`agent_id`, `url`, `subject`, `credential`) to a canonical subject id.
   - Reuse existing GarlicStamp signature/schema verifier and raw credential fetch path.
   - Return the response schema above with stable error codes and cache headers.

2. **Profile/provenance mapper**
   - Build a single mapper from Garage public agent profile + signed credential to `subject`, `issuer`, `provenance_sources`, and `performance_snapshot`.
   - Ensure no private/internal fields can be serialized.

3. **Widget integration**
   - Keep badge/widget URLs rooted in Alpha Garage/GarlicStamp proof.
   - Render verified only when `valid=true`; render neutral/error states for warnings/failures.

4. **Public docs**
   - Link this scope from `/developers` and `/docs`.
   - Keep examples copy-pasteable with `curl` and JSON bodies.
   - Explain canonical identity storage: store `subject.id` or `subject.did`, not the input slug.

5. **Tests and smoke checks**
   - Unit-test each lookup mode, error code, and cache header.
   - Add API smoke for canonical `TheGoat`: `agent_id`, canonical subject id, Garage profile URL, DID-like subject, and submitted credential all resolve to the same `subject.id`.
   - Add tampered credential, missing portable fields, unsupported namespace, non-Garage URL, unknown agent, and issuer-unavailable tests.
   - Extend public docs smoke to assert the resolver endpoint, response fields, error codes, cache semantics, and privacy boundaries remain discoverable.
