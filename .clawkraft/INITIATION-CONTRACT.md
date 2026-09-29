# First-Run Initiation Intent Contract

This document is the public-side specification for the signed one-time
initiation intent issued from `clawkraft.com` to `setup.clawkraft.dev`.
It is owned by `halthinks/clawkraft-web` and consumed by
`halthinks/clawkraft-dev` (verifier) and `halthinks/ClawKraft` (key
material / commissioning authority).

## 1. Purpose

Every public "Get Started" call to action on `clawkraft.com` (landing,
product, how-it-works, use-cases, security, docs, get-started) must
issue a **signed one-time initiation intent** before the browser is
allowed to navigate to `setup.clawkraft.dev/signup`. The intent binds
the public click to:

- A **specific destination** (`setup.clawkraft.dev`).
- A **short lifetime** (≤ 15 minutes, single-use).
- A **specific issuer** (`clawkraft.com`).
- A **specific purpose** (`first-run:initiation`).

It carries **no credential, password, API key, or session identifier**.
It is an authorization assertion, not a secret.

## 2. Wire format

The intent is a compact JWS:

```
<base64url(header)>.<base64url(payload)>.<base64url(signature)>
```

Header (`alg`, `typ`, `kid`):

```json
{
  "alg": "HS256" | "HS384" | "HS512" | "ES256" | "ES384" | "EdDSA" | "RS256" | "RS384" | "RS512",
  "typ": "ck-intent+v1",
  "kid": "ck-intent-2026q3"
}
```

Payload claims:

| Claim   | Value                                      | Required |
|---------|--------------------------------------------|----------|
| `iss`   | `"clawkraft.com"`                          | yes      |
| `aud`   | `"setup.clawkraft.dev"`                    | yes      |
| `sub`   | `"anonymous"`                              | yes      |
| `iat`   | seconds since epoch                        | yes      |
| `nbf`   | seconds since epoch, `≤ iat`               | yes      |
| `exp`   | seconds since epoch, `≤ iat + 900`         | yes      |
| `jti`   | non-guessable single-use id, 16-64 chars   | yes      |
| `purpose` | `"first-run:initiation"`                 | yes      |
| `surface` | enum (see schema)                        | yes      |
| `ref`   | public-side correlation reference         | optional |

The full machine-readable schema lives at
[`schemas/first-run-initiation-intent.schema.json`](../schemas/first-run-initiation-intent.schema.json).

## 3. Issuance flow (clawkraft.com)

1. The visitor clicks an element with class `intent-cta` and a
   `data-surface` attribute.
2. `assets/intent-contract.js` `POST`s `{ surface, ref }` to
   `https://setup.clawkraft.dev/api/intent/start`.
3. The endpoint mints a compact JWS using a key the public site never
   holds. The endpoint is the **only** signer.
4. The helper validates the response structure client-side:
   - It must parse as a 3-segment compact JWS.
   - `alg` must be in the allowed list.
   - `typ` must be exactly `ck-intent+v1`.
   - All payload claims must match the fixed values and ranges above.
   - The payload must not contain any forbidden field name
     (`api_key`, `password`, `secret`, `token`, `session`, etc.).
   - `exp - iat ≤ 900` and `now ∈ [nbf, exp)`.
5. On success, the helper builds
   `https://setup.clawkraft.dev/signup?intent=<token>` and assigns it
   to `window.location`.
6. On any validation failure the helper **fails closed**: no navigation
   occurs, and the helper does not fall back to a non-allowlisted URL.

## 4. Consumption flow (setup.clawkraft.dev)

1. Setup receives `GET /signup?intent=…`.
2. Setup splits the JWS, validates `alg`, `typ`, `kid`, and signature
   using a key resolved against its trusted key set. Unknown `kid`
   fails closed.
3. Setup validates `iss == "clawkraft.com"`, `aud == "setup.clawkraft.dev"`,
   `purpose == "first-run:initiation"`, `sub == "anonymous"`.
4. Setup validates the lifetime window.
5. Setup checks `jti` against the consumed-jti store. A consumed jti
   fails closed (replay).
6. Setup consumes the intent: it stores `jti` until `exp`, then
   proceeds with onboarding. The intent cannot be used again.
7. If the user completes onboarding and lands on a "next" page, that
   page must be on the `setup.clawkraft.dev` allowlist. Any other host
   fails closed (open-redirect guard).

## 5. Negative-path guarantees

| Attack                 | Outcome                          |
|------------------------|----------------------------------|
| Replay (same jti twice)| Setup refuses the second use.    |
| Tamper (modify payload)| Signature fails to verify.      |
| Expiry (`exp` past)    | Setup refuses.                   |
| Not-yet-valid (`nbf`)  | Setup refuses.                   |
| Wrong destination      | Setup refuses (aud mismatch).    |
| Wrong issuer           | Setup refuses (iss mismatch).    |
| Open redirect          | Setup refuses off-allowlist next.|
| Algorithm confusion    | Setup refuses unlisted alg.      |
| Unknown key            | Setup refuses unknown `kid`.     |
| Credential leakage     | Helper fails closed if it sees a forbidden payload field. |

## 6. Storage and credential rules

- The clawkraft.com page **never** writes the intent to
  `localStorage`, `sessionStorage`, `IndexedDB`, cookies, or any other
  persistent store. The token lives only in the redirect URL.
- No secret, password, API key, bearer token, or session identifier
  appears in any URL on `clawkraft.com` or in any redirect from
  `clawkraft.com` to `setup.clawkraft.dev`.
- The intent token itself is an authorization assertion, not a
  credential. Carrying it in the redirect URL is consistent with the
  acceptance gate.

## 7. What is NOT in scope

- The actual signing key. That is held by
  `halthinks/clawkraft-dev` and rotated under
  `halthinks/ClawKraft` governance.
- Mission Control privileged controls. The intent does not authorize
  any privileged action — it only authorizes the public-initiation step.
- Login flows. Existing users still use the
  `https://app.clawkraft.dev/` route, which is unchanged.
