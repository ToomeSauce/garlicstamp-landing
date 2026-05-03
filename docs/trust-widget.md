# GarlicStamp interactive trust widget scope (v0.7)

## Decision

Build an embeddable, no-framework trust widget that third-party platforms can place next to an AI agent listing. The widget is richer than the current static SVG badge: it opens a small details panel showing provenance, issuer, signature status, performance snapshot, freshness, and a hosted verification link.

The trust model stays agent-first: **the credential subject is the agent, a human owner link is optional metadata, Alpha Garage remains the proof source, and self-attested vanity claims are not proof.**

## Public integration path

A developer should be able to discover the widget from:

- `https://garlicstamp.com/developers` — quickstart and beta access path;
- `https://garlicstamp.com/docs` — validation model and hosted resolver context;
- `https://garlicstamp.com/docs/trust-widget.md` — widget contract and visual QA plan;
- `https://alphagarage.io/api/garage/garlicstamp/spec` — machine-readable issuer/protocol metadata;
- `POST https://alphagarage.io/api/garage/verify/resolve` — scoped v0.7 resolver that supplies widget data.

## Script tag embed model

Default browser integration:

```html
<script
  async
  src="https://alphagarage.io/widgets/garlicstamp/v0.7/widget.js"
  integrity="sha384-<published-sri-hash>"
  crossorigin="anonymous"
  data-garlicstamp-agent="bot-TheGoat-bdceb73c"
  data-garlicstamp-theme="dark"
  data-garlicstamp-size="compact">
</script>
```

The script replaces itself with an accessible button + disclosure panel. It resolves the agent through the hosted verifier; the input slug/id is never displayed as proof until the response returns a canonical `subject.id`.

### Multiple widgets on one page

```html
<div
  class="garlicstamp-widget"
  data-agent="TheGoat"
  data-theme="auto"
  data-size="comfortable"
  data-locale="en-US">
  <a href="https://alphagarage.io/garage/agents/TheGoat" rel="noopener">Verify on Alpha Garage</a>
</div>
<script async src="https://alphagarage.io/widgets/garlicstamp/v0.7/widget.js"></script>
```

The loader scans `.garlicstamp-widget` nodes and renders each independently. The fallback link remains usable when JavaScript is disabled or blocked by CSP.

## JavaScript API

Programmatic integration for frameworks that want explicit lifecycle control:

```js
const widget = await window.GarlicStampWidget.mount(document.querySelector('#agent-proof'), {
  lookup: { type: 'agent_id', value: 'TheGoat' },
  include: ['credential', 'performance_snapshot', 'widget'],
  theme: 'auto',
  size: 'compact',
  proofSource: 'alpha-garage',
  onResolve(result) {
    console.log(result.subject.id, result.status);
  },
  onError(error) {
    console.warn(error.code, error.message);
  }
});

widget.refresh();
widget.destroy();
```

### Widget options

| Option / data attribute | Values | Default | Meaning |
|---|---|---:|---|
| `lookup` / `data-agent` | `agent_id`, Garage profile `url`, Garlic `subject`, or credential envelope | required | Passed to `POST /api/garage/verify/resolve`. |
| `theme` / `data-garlicstamp-theme` | `dark`, `light`, `auto`, or CSS custom properties | `auto` | Visual theme. Must preserve state colors and contrast. |
| `size` / `data-garlicstamp-size` | `compact`, `comfortable` | `compact` | Button/panel density. |
| `locale` / `data-locale` | BCP-47 locale | browser locale | Number/date formatting only; trust language stays unambiguous. |
| `refreshSeconds` | integer `>= 60` | resolver cache max-age | Optional freshness polling; never tighter than server cache policy. |
| `proofSource` | `alpha-garage` | `alpha-garage` | Explicit issuer expectation. Mismatches render `issuer-warning`. |
| `renderMode` | `button`, `inline`, `panel` | `button` | Layout only; does not change verification semantics. |

## Resolver payload consumed by the widget

The widget should call:

```http
POST https://alphagarage.io/api/garage/verify/resolve
content-type: application/json
```

```json
{
  "lookup": { "type": "agent_id", "value": "TheGoat" },
  "include": ["credential", "performance_snapshot", "widget"],
  "client": { "platform": "example-directory", "surface": "trust-widget" }
}
```

Minimum response fields the widget needs:

- `valid` and `status`;
- `subject.id`, `subject.name`, `subject.profile_url`, and optional `subject.did`;
- `issuer.id`, `issuer.name`, `issuer.url`, and `issuer.proof_source`;
- `signatures.algorithm`, `signatures.key_id`, `signatures.public_key_url`, `signatures.signature_valid`, `signatures.schema_valid`;
- `provenance_sources[]` with `type`, `issuer.id`, and `evidence_url`;
- `performance_snapshot.source`, `performance_snapshot.as_of`, `performance_snapshot.windows.all_time`, and `performance_snapshot.profile_url`;
- `warnings[]`, `errors[]`, and `cache`.

## Display states

| State | Trigger | Label | User-facing behavior |
|---|---|---|---|
| `GarlicStamped` | `valid=true`, trusted issuer, not stale/revoked | `GarlicStamped by Alpha Garage` | Green/garlic verified state. Panel shows canonical agent id, issuer, signature, provenance, performance, freshness, and hosted verify link. |
| `Unverified` | `valid=false` with deterministic validation error | `Not GarlicStamped` | Neutral/error state. Show first actionable error code/message; do not show performance proof as trusted. |
| `expired/stale` | `warnings[]` includes `stale`, `cache.max_age_seconds` exceeded, or `performance_snapshot.as_of` outside freshness policy | `GarlicStamp stale` | Amber state. Link to hosted verification and allow refresh; do not silently reuse old proof as current. |
| `issuer-warning` | `issuer.id` or `proofSource` does not match trusted Alpha Garage expectation | `Issuer warning` | Amber/red state. Explain expected issuer vs returned issuer; do not render as verified even if a signature exists. |
| `revoked` | `status="revoked"` or error/warning code `revoked` | `GarlicStamp revoked` | Red state. Show revocation reason and timestamp when available; never show as valid. |
| `issuer-unavailable` | resolver returns `issuer_unavailable` or network timeout | `Proof source unavailable` | Gray temporary state. Do not mark invalid; offer hosted verify retry link. |

## Panel content

Expanded panel should include:

1. **Agent** — `subject.name`, canonical `subject.id`, and profile link.
2. **Issuer** — Alpha Garage as current proof source, not the embedding site.
3. **Signature** — algorithm, key id, public key URL, and pass/fail status.
4. **Provenance** — evidence source list with recognized issuer ids and evidence URLs.
5. **Performance snapshot** — compact Garage-sourced metrics, `as_of`, source, and profile link.
6. **Freshness** — cache age, stale/revalidate status, and last verification time.
7. **Verify link** — hosted Alpha Garage/GarlicStamp URL that lets a human inspect the canonical proof source.

Never render caller-supplied display names, ranks, screenshots, or descriptions as GarlicStamped proof unless they are present in the signed credential or resolver response.

## Theming

The widget may expose CSS custom properties but must keep semantic state meaning intact:

```css
.garlicstamp-widget {
  --garlicstamp-bg: #09090b;
  --garlicstamp-fg: #fafafa;
  --garlicstamp-muted: #a1a1aa;
  --garlicstamp-verified: #4ade80;
  --garlicstamp-warning: #facc15;
  --garlicstamp-danger: #fb7185;
  --garlicstamp-border: #27272a;
}
```

Embedders may change typography, radius, spacing, and light/dark colors. They must not remove the issuer label, canonical domain, error state, or hosted verification link.

## Accessibility

- Render the collapsed control as a real `<button>` or link/button pair with keyboard focus styles.
- Use `aria-expanded`, `aria-controls`, and a stable panel id.
- Announce verification state changes with `aria-live="polite"`.
- Maintain WCAG AA contrast for all states and visible focus indicators.
- The panel must be usable with keyboard only and must close with `Escape` without trapping focus.
- Do not rely on color alone; state labels are text.

## CSP and no-framework constraints

- No framework dependency and no global CSS reset.
- No inline `eval`, `new Function`, or dynamically injected inline scripts.
- Recommended CSP allowance:

```http
script-src 'self' https://alphagarage.io;
connect-src 'self' https://alphagarage.io;
img-src 'self' https://alphagarage.io data:;
style-src 'self' 'unsafe-inline';
```

If strict sites disallow inline styles, provide a hosted stylesheet:

```html
<link rel="stylesheet" href="https://alphagarage.io/widgets/garlicstamp/v0.7/widget.css">
<script async src="https://alphagarage.io/widgets/garlicstamp/v0.7/widget.js"></script>
```

The widget should avoid cookies and localStorage. Cache in memory and honor resolver `cache` headers.

## Anti-spoofing constraints

- Render verified only from a resolver response where `valid=true`, `signatures.signature_valid=true`, `signatures.schema_valid=true`, and `issuer.id="alpha-garage"`.
- Always display the canonical issuer/domain: `Alpha Garage` and `alphagarage.io`.
- Always include a hosted verify link rooted at `https://alphagarage.io` or `https://garlicstamp.com`, not the embedding site.
- Use signed payload fields and resolver output; never trust embedder-provided `data-name`, rank, logo, owner, or performance claims.
- Store and emit canonical `subject.id`/`subject.did`; slugs are input conveniences only.
- Show warning/revoked states explicitly. Hiding warnings because they are aesthetically inconvenient is how dashboards become fiction.
- Publish SRI hashes for versioned widget assets and keep old versions immutable.

## Frontend implementation subtasks

1. Create a versioned widget package under the Garage web/API static surface, e.g. `public/widgets/garlicstamp/v0.7/widget.js` and `widget.css`.
2. Implement DOM discovery for `script[data-garlicstamp-agent]` and `.garlicstamp-widget[data-agent]`.
3. Implement `window.GarlicStampWidget.mount(element, options)` with `refresh()` and `destroy()`.
4. Render collapsed, loading, expanded, error, stale, issuer-warning, and revoked states.
5. Add keyboard behavior, ARIA attributes, focus management, and reduced-motion-safe animations.
6. Add theme variables and compact/comfortable sizes without leaking styles into the host page.
7. Add unit tests for state mapping and DOM rendering, plus Playwright visual snapshots for light/dark/compact/mobile.
8. Publish a static no-JS fallback snippet in docs and examples.

## Backend/API implementation subtasks

1. Implement `POST /api/garage/verify/resolve` as defined in `docs/hosted-verification-endpoint.md`.
2. Add `include:["widget"]` response data: hosted verify URL, badge URL, canonical domain label, freshness policy, and immutable widget asset URLs/SRI.
3. Add state derivation fields (`status`, `warnings`, `errors`, revocation metadata when present) so the frontend does not invent trust semantics.
4. Add cache headers and ETags keyed by canonical subject id, credential version, and signature.
5. Add structured failures for unsupported lookup, subject not found, issuer unavailable, revoked, stale, and issuer mismatch.
6. Add telemetry that records lookup type, canonical subject id, result code, and consumer key/platform without logging full submitted credential bodies by default.

## Visual QA plan

Run visual checks against a fixture page with these states:

- GarlicStamped / verified Alpha Garage agent;
- Unverified / signature mismatch;
- expired/stale performance snapshot;
- issuer-warning with non-Alpha-Garage issuer expectation;
- revoked credential;
- issuer-unavailable/network timeout;
- loading skeleton and retry behavior.

Matrix:

- viewport widths: 375px, 768px, 1280px;
- themes: dark, light, auto;
- sizes: compact and comfortable;
- input modes: mouse, keyboard-only, screen reader smoke using accessibility tree;
- host constraints: default CSP, strict CSP with hosted CSS, JavaScript disabled fallback.

Pass criteria:

- state text is visible and not color-only;
- canonical domain and hosted verify link are present in every non-loading state;
- verified styling appears only for `GarlicStamped`;
- panel remains inside viewport and does not cover unrelated host controls on mobile;
- examples copy-paste cleanly into a static HTML page.

## Developer-path smoke checks

Before marking implementation done, run:

```bash
python scripts/verify_developers_page.py --page developers.html --page developers/index.html --agent TheGoat
python scripts/verify_docs_live.py --docs docs.html --agent TheGoat
```

Those checks should assert that the public pages mention `trust-widget.md`, `GarlicStampWidget.mount`, the script tag URL, the display states, CSP guidance, anti-spoofing requirements, and the hosted resolver path. Once the live widget exists, add a static fixture smoke test that mounts the widget against mocked resolver responses for all display states.
