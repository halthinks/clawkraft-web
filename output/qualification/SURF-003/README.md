# SURF-003 Qualification Evidence

- Outcome: **PASS**
- Requirement: SURF-003-EV-01 — Browser evidence proves the public site is responsive and routes Get Started/Login correctly.
- Gate: SURF-003-GATE
- Work packet: sha256:8b1be96df61a1522667b70fb174736c0a4fcc88460718e9e90bb2fb86b8312bc
- Source binding: halthinks/clawkraft-web@6d0cd8610dbf48fc0003057dbb3070776c75fc69 (SURF-003-SRC-1)
- Generated: 2026-09-27T23:51:06.808Z
- Base URL: http://127.0.0.1:8765

## Routing

- Get Started destinations: https://setup.clawkraft.dev/signup, https://setup.clawkraft.dev/
- Login destinations: https://app.clawkraft.dev/

## Viewports

- desktop: 1440x900
- mobile: 390x844 (mobile emulation)

## Screenshots

- output/qualification/SURF-003/home-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/product-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/how-it-works-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/use-cases-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/security-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/get-started-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/docs-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/status-desktop.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/home-mobile.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/product-mobile.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/how-it-works-mobile.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/use-cases-mobile.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/security-mobile.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/get-started-mobile.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/docs-mobile.png (HTTP 200, overflow=false)
- output/qualification/SURF-003/status-mobile.png (HTTP 200, overflow=false)

## Checks

Total: 80, Failed: 0

All checks passed.

## Acceptance mapping

- Desktop and mobile full-page screenshots captured for landing, product, how-it-works, use-cases, security, get-started, docs, and status surfaces.
- Responsive check: no horizontal overflow at 1440x900 or 390x844.
- Get Started routes to https://setup.clawkraft.dev (signup).
- Login routes to https://app.clawkraft.dev/.
- No privileged control element ids rendered on clawkraft.com surfaces.
- Render checks: visible h1 + brand chrome + visible Get Started/Login on every page/viewport (`render-checks.json`).
- Pixel sampling confirms dark themed non-blank renders on desktop and mobile screenshots.

## Artifacts

- `qualification.json` — full machine-readable qualification record
- `summary.json` — compact outcome summary
- `render-checks.json` — DOM/routing/pixel verification
- `qualify.mjs` — reproducible browser qualification script
- `*-desktop.png` / `*-mobile.png` — full-page screenshots (8 surfaces × 2 viewports)
