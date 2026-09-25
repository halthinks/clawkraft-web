# ClawKraft Web

Public website and onboarding front door for ClawKraft.

## Repository boundary

This repository owns the public `clawkraft.com` web experience only.

Allowed:
- landing/product/how-it-works/use-cases;
- trust/security and pricing/availability;
- public docs entry;
- Get Started and Login entrypoints;
- public assets and intentionally public API contracts.

Not allowed:
- ClawKraft runtime or worker credentials;
- private project inventories;
- private Program/task state;
- provider secrets or deployment secrets;
- Mission Control/runtime source;
- setup/review privileged implementation;
- private operator runbooks or internal evidence.

Canonical private core/runtime source remains:

`halthinks/ClawKraft`

The public site may consume only intentionally public interfaces/contracts from core. It must not become a public mirror of the private repository.

## Canonical journey

`clawkraft.com → setup.clawkraft.dev → app.clawkraft.dev`

External agents attach independently through:

`https://mcp.clawkraft.dev/mcp`
