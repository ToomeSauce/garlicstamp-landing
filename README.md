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
index.html   — main landing page
404.html     — custom 404 page
_headers     — security headers
_redirects   — URL redirects
```

## Tech

- Pure HTML/CSS/JS — no build step, no framework
- Google Fonts: Space Grotesk (headings), Inter (body), JetBrains Mono (code)
- Intersection Observer for scroll animations
- Responsive down to 375px
- Dark mode only (matches Alpha Garage design system)
