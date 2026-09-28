# clawkraft.com Landing-Page Information Architecture

Status: implementation-ready for `clawkraft.com` public product and onboarding front door (SURF-003).

## Boundary

`clawkraft.com` is the public product/company surface. Authenticated technical and operational work lives on `clawkraft.dev` unless a successor ProgramSnapshot changes that decision.

Public site may contain:

- product explanation and capability overview;
- non-interactive product screenshots/previews of authenticated surfaces, using only synthetic or intentionally public data and exposing no privileged action path;
- how-it-works narrative;
- use cases;
- security and trust positioning;
- public docs entry;
- Get Started and Login entrypoints that route off `.com`;
- public assets and intentionally public API contracts.

Public site must not contain privileged controls, private Program/task state, credentials, private runbooks, Mission Control runtime chrome, or operator actions.

## Canonical journey

```
clawkraft.com  →  setup.clawkraft.dev  →  app.clawkraft.dev
```

| Entry | Meaning | Destination |
| --- | --- | --- |
| Get Started | New visitor begins onboarding | `https://setup.clawkraft.dev/signup` |
| Login | Existing operator opens the authenticated app | `https://app.clawkraft.dev/` |
| Docs | Public technical entry | `/docs/` on `clawkraft.com` |
| Connect an Agent | External MCP attachment | `https://mcp.clawkraft.dev/mcp` (documented from `/docs/`) |

External agents attach independently through `https://mcp.clawkraft.dev/mcp`.

## Top-level map

```
clawkraft.com/
├── /                      Landing — value prop, proof, primary CTAs
├── /product/              Product surface — what ClawKraft is and does
├── /how-it-works/         How it works — infrastructure → workforce → programs → delivery
├── /use-cases/            Use cases — who it is for and what work looks like
├── /security/             Security & trust — governance, isolation, privacy posture
├── /get-started/          Get started — onboarding path into setup.clawkraft.dev
├── /docs/                 Docs entry — public documentation index
│   ├── /docs/privacy/     Privacy policy
│   ├── /docs/terms/       Terms
│   └── /docs/support/     Support
└── /status/               Public coarse service status
```

## Navigation (public chrome)

Primary nav on every marketing surface:

- Product → `/product/`
- How it Works → `/how-it-works/`
- Use Cases → `/use-cases/`
- Security → `/security/`
- Docs → `/docs/`
- Status → `/status/`
- Login → `https://app.clawkraft.dev/` (off-site)
- Get Started → `https://setup.clawkraft.dev/signup` (off-site, primary button)

Footer repeats Docs, Status, Privacy, Terms, Support, and the off-site Login / Get Started routes.

No privileged controls are operable from public chrome. Pause/resume/stop, worker ON/OFF, Hard Stop, authority envelope changes, and Mission Control runtime actions remain on `app.clawkraft.dev`. The public site may show non-interactive product screenshots/previews when they contain only synthetic or intentionally public state.

## Landing page (`/`) narrative order

1. **Header brand strip** — identity only.
2. **Early-access bar** — waitlist CTA (public, no privileged state).
3. **Hero** — value proposition, Get Started / Login-aware CTAs, terminal-style proof of durable execution.
4. **Capability display** — sandboxing/VMs, vault-backed credentials, workers, Programs, recovery, MCP, Mission Control, and governed delivery.
5. **Product views** — non-interactive onboarding and Mission Control visuals using public/synthetic state only.
6. **Product overview** — what the execution fabric does (summary; deep-dive on `/product/`).
7. **Positioning comparison** — explain where ClawKraft overlaps with compute/sandbox platforms and where the durable execution/control-plane scope extends further.
8. **Bring your own infrastructure** — commission path (summary; deep-dive on `/how-it-works/`).
9. **Use-case display** — concrete work shapes and operational outcomes (deep-dive on `/use-cases/`).
10. **Security & trust teaser** — governance/isolation posture (summary; deep-dive on `/security/`).
11. **Governed delivery** — execute → review → evidence → deliver.
12. **Architecture boundary** — `.com` explains; `.dev` operates; control plane is authoritative.
13. **Final CTA** — Get Started, Docs, Login.
14. **Footer** — public links only.

## Surface content contracts

### `/product/`
Explain the execution fabric: persistent workers, isolated execution, durable handoffs, governed review/deployment, private workloads. Link to `/how-it-works/`, `/use-cases/`, `/security/`, `/docs/`, Get Started.

### `/how-it-works/`
Four-stage story: Infrastructure → Setup/qualification → Workforce → Programs. Include durable handoff model and delivery path. No privileged UI.

### `/use-cases/`
Concrete work shapes: multi-agent product delivery, long-running research-to-execution, bring-your-own-infra teams, external agent attachment, recovery after worker failure. Keep claims to product behavior, not customer logos or private deployments.

### `/security/`
Trust posture: isolation, governed review/deploy, private workloads, credential boundary, domain split (`.com` public / `.dev` operational), MCP boundary, what is intentionally not published. Link to Privacy and Support.

### `/docs/`
Public docs entry: connect an agent (MCP), product surface links, capability Programs at a high level, pointer to Privacy/Terms/Support. Explicitly state private runbooks/credentials are not published.

### `/get-started/`
Onboarding front door: what Get Started does, the canonical journey, what you need (infrastructure + agents), and a primary CTA to `https://setup.clawkraft.dev/signup`. Secondary: Login (`https://app.clawkraft.dev/`), Docs, Connect an Agent.

## Routing rules

1. Get Started CTAs leave `clawkraft.com` for `https://setup.clawkraft.dev/signup`.
2. Login CTAs leave `clawkraft.com` for `https://app.clawkraft.dev/`.
3. Privileged controls are never rendered on `clawkraft.com`.
4. Deployment-owned hostnames are configuration, not hard-coded customer hostnames.
5. ClawKraft MCP traffic is never routed through a TextPCB MCP endpoint or vhost.

## Responsive qualification

All marketing surfaces must remain usable at:

- desktop ≥ 1280px width;
- tablet ~ 768px width;
- mobile ≤ 620px width.

Qualification evidence covers desktop and mobile screenshots plus link-target verification for Get Started and Login.

## Out of scope for `.com`

- Mission Control runtime controls;
- Setup/review privileged implementation;
- Program/task state, private inventories, credentials, provider secrets;
- Operator runbooks or internal evidence;
- Customer deployment hostnames as product constants.
