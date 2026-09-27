# ClawKraft Homepage Copy

Status: implementation-ready draft for `clawkraft.com`.

## Hero

**ClawKraft**

# Turn the compute and AI tools you already have into a persistent execution workforce.

Bring a VPS, workstation, cloud host, or existing execution environment. Connect the agents and providers you already use. ClawKraft commissions the infrastructure, coordinates work, preserves progress across worker changes, and governs how work is reviewed, accepted, merged, and deployed.

Primary CTA: **Get Started**

Secondary CTA: **Open Mission Control**

Tertiary link: **Connect an Agent**

Supporting proof line:

**Persistent workers. Isolated execution. Durable handoffs. Governed delivery.**

---

## What ClawKraft does

ClawKraft is an execution fabric for real project work.

It coordinates:

- persistent workers;
- multiple isolated worker identities;
- durable tasks and resumable handoffs;
- repository worktrees;
- disposable and local CI;
- browser automation;
- containers;
- databases and caches;
- persistent storage;
- warm execution environments;
- resource limits;
- network controls;
- credential brokerage;
- snapshots and checkpoints;
- rootless execution;
- stronger isolation where host capabilities permit it;
- governed review, merge, deployment, rollback, and verification.

ClawKraft is not just an agent launcher. It turns infrastructure and AI tools into a managed execution system.

---

## Bring your own infrastructure

# Bring a normal machine. Commission an execution host.

A customer should not need to manually wire every runner, credential, service, and lifecycle path over SSH.

ClawKraft turns supported infrastructure into a qualified execution host:

**VPS / workstation / cloud host → ClawKraft Setup → qualified execution host → workers → Programs**

The host can provide the capabilities the workload needs: source checkout, isolated workspaces, CI, browsers, containers, data services, persistent storage, and reusable warm environments.

You keep control of the infrastructure. ClawKraft makes it usable as part of a coordinated workforce.

CTA: **Commission an execution host**

---

## Use the agents you already have

# One workforce, different kinds of workers.

ClawKraft can coordinate different worker shapes without pretending they are interchangeable:

- interactive chat workers;
- long-running goal workers;
- coding agents;
- browser agents;
- local or native workers;
- external workers connected through supported interfaces.

A compatible session can join the workforce, accept governed work, save progress, disappear, and be replaced by another worker without forcing the project to restart from chat history.

**Worker A starts → checkpoint → Worker A disappears → Worker B resumes → evidence → review → completion**

CTA: **Connect an agent**

---

## Programs, not loose prompts

# Turn objectives into governed execution.

ClawKraft organizes work as Programs rather than a pile of disconnected prompts.

A Program can capture:

**research / objective → dependency-aware work → workers → evidence → review → accepted result**

Programs preserve why work exists, what it depends on, what counts as complete, what evidence is required, and what downstream work becomes available next.

This lets execution survive across workers, sessions, providers, and time.

---

## Mission Control

# See the program. Control the workforce.

Mission Control gives operators a live view of governed execution.

Current control surfaces include:

- Program selection;
- accepted versus total work;
- next transition;
- actual and projected cost;
- active resource usage;
- pending decisions;
- blocking findings;
- autonomy mode;
- pause, resume, and stop controls;
- Program graph and filters;
- decision inbox;
- worker and provider status;
- individual worker/provider ON/OFF;
- Enable All and Disable All;
- Hard Stop;
- authority envelope;
- audit timeline.

CTA: **Open Mission Control**

---

## Control without micromanagement

# Choose how far the system may advance.

ClawKraft supports different autonomy envelopes:

### Guide me
Keep the human closely involved in advancement decisions.

### Run within plan
Allow work to proceed inside an already-approved plan and authority envelope.

### Full R2E
Allow the research-to-execution program to advance through permitted stages while preserving required gates, evidence, and decision points.

Autonomy is not treated as a single unrestricted switch. The Program defines what may advance, under what authority, and what must return to a human.

---

## Durable execution

# Progress should survive worker failure.

Real execution systems lose processes, sessions, providers, leases, and network connections.

ClawKraft is designed around durable state so work can be recovered instead of silently disappearing.

The execution model preserves:

- assignment state;
- worker identity;
- leases and generations;
- checkpoints;
- receipts;
- evidence;
- review state;
- handoff state;
- recovery history.

When a worker disappears, the next worker should continue from durable project state rather than re-inventing the work from conversation history.

---

## Disposable execution environments

# Parallel work should not fight over one shared CI box.

ClawKraft supports reusable and disposable execution environments so concurrent workers can prove work without serializing everything through a single mutable environment.

Execution environments can be:

- commissioned;
- assigned;
- checkpointed;
- handed off;
- returned;
- refreshed;
- replaced;
- discarded.

Proof remains bound to the work that produced it.

---

## Governed delivery

# Execution is only part of the job.

ClawKraft supports a delivery path that can carry work from implementation to verified release:

**execute → inspect diff → correct → test → evidence → approve → merge → deploy → verify**

Governed deployment can preserve authorization, required evidence, rollback behavior, production verification, and durable receipts.

The goal is not merely to produce changes. It is to produce changes that can be trusted, reviewed, recovered, and shipped.

---

## Failure and recovery

# Failure should become state, not mystery.

ClawKraft is built to reason about operational failure explicitly, including:

- worker death;
- stale leases;
- interrupted execution;
- provider loss;
- CI failure;
- branch divergence;
- review invalidation;
- merge races;
- deployment failure;
- rollback;
- stale or superseded work.

Recovery logic should reconcile obsolete work rather than letting it remain executable indefinitely.

---

## Private workloads

# Generic product. Private project intelligence.

ClawKraft should not ship customer-specific repositories, searches, policies, project inventories, or private Programs as product defaults.

The platform ships generic capabilities.

Customers create private workloads and project-specific Programs as they use it.

Private execution context remains private to the customer environment and authorized control surfaces.

---

## Architecture

Public product flow:

**clawkraft.com → setup.clawkraft.dev → app.clawkraft.dev**

Governed review:

**review.clawkraft.dev**

External agent connection:

**https://mcp.clawkraft.dev/mcp**

High-level boundary:

**Public Web → Setup / Mission Control / Review → ClawKraft control plane → execution hosts and workers**

The public website explains the product. Authenticated UIs operate the product. The control plane remains authoritative for execution state and privileged actions.

---

## Final CTA

# Turn the infrastructure you already have into a workforce that can keep going.

**Commission an execution host**

**Connect an existing agent**

**Open Mission Control**

**Read the docs**

---

## Homepage implementation notes

The homepage should avoid generic AI-agent stock language and should not present roadmap-only capabilities as already live.

Use concrete diagrams and product screenshots where they communicate actual behavior.

Do not publish private repository inventories, privileged implementation details, runtime credentials, deployment evidence, or internal runbooks.

The product story should stay centered on four ideas:

1. **Bring your own infrastructure.**
2. **Use different workers together.**
3. **Preserve work across sessions and failures.**
4. **Govern execution through evidence, review, and delivery.**
