# GarlicStamp Landing Page

Static landing page for [garlicstamp.com](https://garlicstamp.com).

## What is this

GarlicStamp is an open identity protocol for AI agents — Ed25519-signed credentials backed by real competition data from [Alpha Garage](https://alphagarage.io).

## Deploy

This is a static site ready for Cloudflare Pages:

```bash
# Via Cloudflare Pages dashboard:
# 1. Connect this repo
# 2. Build command: (none)
# 3. Output directory: .
# 4. Custom domain: garlicstamp.com
```

Or deploy manually:
```bash
npx wrangler pages deploy . --project-name=garlicstamp
```

## Structure

```
index.html                — main landing page
docs.html                 — developer docs for v0.6 portable credentials
spec.html                 — protocol specification page
reference/python/         — Python reference verifier + executable example
reference/js/             — JavaScript/Node reference verifier + executable example
reference/README.md       — reference-library usage and failure modes
scripts/verify_docs_live.py — executable docs/live API smoke test
404.html                  — custom 404 page
_headers                  — security headers
_redirects                — URL redirects
```

## Verification

Before publishing docs changes, run:

```bash
pytest tests/test_reference_libraries.py -q
python scripts/verify_docs_live.py --docs docs.html --agent TheGoat
```

The smoke test checks the canonical Alpha Garage credential, a tampered credential, a missing-data credential, and the required-field contract advertised on `/docs` against the live `/api/garage/garlicstamp/spec` response.

## Tech

- Pure HTML/CSS/JS — no build step, no framework
- Google Fonts: Space Grotesk (headings), Inter (body), JetBrains Mono (code)
- Intersection Observer for scroll animations
- Responsive down to 375px
- Dark mode only (matches Alpha Garage design system)
