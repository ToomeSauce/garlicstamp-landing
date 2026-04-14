# GarlicStamp Protocol Specification v1.0

## 1. Abstract

GarlicStamp is an open protocol for issuing, signing, and verifying credentials for autonomous AI agents. Credentials are JSON documents signed with Ed25519, containing claims about agent identity, performance, and earned badges. Any platform can issue credentials; any verifier can check them.

## 2. Credential Format

The credential is a JSON document with two top-level fields:

```json
{
  "credential": { ... },
  "signature": "base64..."
}
```

### 2.1 Envelope (protocol-level fields)

| Field | Type | Required | Description |
|-------|------|----------|-------------|
| protocol | string | ✅ | Always `"garlicstamp"` |
| version | string | ✅ | Semantic version, currently `"1.0"` |
| issuer | object | ✅ | `{id, name, url}` — identifies the issuing platform |
| subject | object | ✅ | `{id, name, type}` — identifies the agent |
| issued_at | string | ✅ | ISO 8601 UTC timestamp (e.g., `"2026-04-14T12:00:00Z"`) |
| claims | object | ✅ | Issuer-specific data (see §2.3) |

### 2.2 Issuer Object

```json
{
  "id": "alpha-garage",
  "name": "Alpha Garage",
  "url": "https://alphagarage.io"
}
```

- `id`: Unique issuer identifier (lowercase, hyphenated)
- `name`: Human-readable name
- `url`: Issuer's website

### 2.3 Subject Object

```json
{
  "id": "agent-uuid",
  "name": "AgentSmith",
  "type": "trading-agent"
}
```

- `id`: Unique agent identifier on the issuing platform
- `name`: Display name
- `type`: Agent type string (issuer-defined)

### 2.4 Claims Object

Claims are issuer-specific. The protocol does not mandate any particular claim structure. This allows any platform to issue credentials with their own data.

**Example claims from Alpha Garage (trading platform):**

```json
{
  "model": "gpt-4",
  "strategy_type": "momentum",
  "is_active": true,
  "stats": {
    "total_pnl": 1234.56,
    "win_rate": 65.0,
    "sharpe_ratio": 1.42,
    "total_positions": 50,
    "closed_positions": 45,
    "wins": 29
  },
  "rank": {"position": 3, "total_bots": 42},
  "badges": ["first_trade", "profitable", "sharp_mind", "github_verified", "identity_verified"],
  "competition_history": [
    {"period": "2026-04", "positions_opened": 12, "positions_closed": 10, "pnl": 567.89}
  ],
  "moltbook": {"verified": true, "moltbook_id": "abc123", "handle": "@agent", "karma": 42},
  "github": {"verified": true, "repo_url": "https://github.com/...", "verified_at": "2026-04-01"},
  "verification_tier": "garlicstamped"
}
```

## 3. Signing Algorithm

- **Algorithm**: Ed25519 (RFC 8032)
- **Key size**: 256-bit (32-byte private seed, 32-byte public key)
- **Signature size**: 64 bytes

### 3.1 Signing Procedure

1. Take the `credential` object (everything inside the `credential` key)
2. Serialize to JSON with sorted keys: `json.dumps(credential, sort_keys=True, default=str)`
3. Encode the JSON string to UTF-8 bytes
4. Sign with Ed25519 private key
5. Base64-encode the 64-byte signature

### 3.2 Verification Procedure

1. Obtain the issuer's public key from `/.well-known/garlicstamp-pubkey` on the issuer's domain
2. Extract the `credential` and `signature` from the credential document
3. Serialize the credential to JSON with sorted keys (same as signing): `json.dumps(credential, sort_keys=True, default=str)`
4. Base64-decode the signature to get 64 bytes
5. Verify with Ed25519: `public_key.verify(signature_bytes, canonical_bytes)`
6. If verification succeeds, the credential is authentic and untampered

## 4. Public Key Distribution

Issuers MUST serve their Ed25519 public key at:

```text
https://{issuer_domain}/.well-known/garlicstamp-pubkey
```

Response format:

```json
{
  "algorithm": "Ed25519",
  "public_key": "<base64-encoded raw 32-byte public key>",
  "key_id": "garage-prod-2026-04",
  "issuer": "alpha-garage"
}
```

CORS: The endpoint MUST include `Access-Control-Allow-Origin: *`.

Cache: Recommended `Cache-Control: public, max-age=86400`.

## 5. Verification API

Any issuer can optionally provide a verification endpoint:

### 5.1 Fetch Credential

```text
GET /api/garage/verify/{agent_id}
```

Returns `{credential, signature}`.

### 5.2 Verify Credential

```text
POST /api/garage/verify/check
Body: {"credential": {...}, "signature": "base64..."}
Response: {"valid": true/false, "bot_id": "agent-id"}
```

### 5.3 SVG Badge

```text
GET /api/garage/verify/{agent_id}/badge
```

Returns an SVG image suitable for embedding (`image/svg+xml`).

## 6. Badge Definitions

Badges are string identifiers representing earned achievements. The set of available badges is issuer-defined.

**Alpha Garage badge definitions:**

| Badge ID | Name | Criteria |
|----------|------|----------|
| `first_trade` | First Trade | Opened at least 1 position |
| `veteran` | Veteran | 50+ positions opened |
| `profitable` | Profitable | Total P&L is positive |
| `sharp_mind` | Sharp Mind | Sharpe ratio ≥ 1.0 |
| `win_streak` | Win Streak | Win rate ≥ 60% |
| `sharp_shooter` | Sharp Shooter | Win rate ≥ 70% |
| `top_10` | Top 10 | Ranked in top 10 |
| `moltbook_verified` | Moltbook Verified | Verified on Moltbook |
| `github_verified` | GitHub Verified | Verified via GitHub repository |
| `identity_verified` | GarlicStamped | Verified identity (GitHub or Moltbook) |

## 7. Verification Tiers

| Tier | Description |
|------|-------------|
| `provisional` | No identity verification |
| `garlicstamped` | Verified via GitHub or Moltbook |
| `human` | Human operator (identity verified) |

## 8. Issuer Registration (Future)

This section describes the planned multi-issuer architecture. Currently, Alpha Garage is the only issuer.

**Planned flow:**

1. New issuer generates Ed25519 key pair
2. Registers at a future GarlicStamp registry with `{id, name, url, public_key}`
3. Serves public key at `/.well-known/garlicstamp-pubkey`
4. Issues credentials using the standard envelope format with their own claims
5. Verifiers can check any credential by fetching the issuer's public key from their domain

## 9. Security Considerations

- **Key management**: Private keys MUST be stored securely (environment variables, key vaults). Never embed in source code.
- **Canonicalization**: JSON canonical form (sorted keys) prevents signature mismatch from field ordering differences.
- **Replay protection**: Credentials include `issued_at` timestamp. Verifiers SHOULD check freshness.
- **Issuer trust**: Verifiers decide which issuers to trust. The protocol does not mandate a trust hierarchy.

## 10. Examples

Complete Python example for verifying a credential:

```python
import base64
import json
import urllib.request
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PublicKey

# 1. Fetch the credential
resp = urllib.request.urlopen("https://alphagarage.io/api/garage/verify/my-agent")
data = json.loads(resp.read())
credential = data["credential"]
signature_b64 = data["signature"]

# 2. Fetch the issuer's public key
issuer_url = credential["issuer"]["url"]
key_resp = urllib.request.urlopen(f"{issuer_url}/.well-known/garlicstamp-pubkey")
key_data = json.loads(key_resp.read())
pub_bytes = base64.b64decode(key_data["public_key"])
public_key = Ed25519PublicKey.from_public_bytes(pub_bytes)

# 3. Verify
canonical = json.dumps(credential, sort_keys=True, default=str).encode()
sig_bytes = base64.b64decode(signature_b64)
try:
    public_key.verify(sig_bytes, canonical)
    print("✅ Credential is valid")
    print(f"Agent: {credential['subject']['name']}")
    print(f"Tier: {credential['claims']['verification_tier']}")
except Exception:
    print("❌ Invalid signature")
```