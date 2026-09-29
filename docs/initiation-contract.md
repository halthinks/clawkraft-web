# ClawKraft Public-to-Setup Initiation Contract v1

Status: implementation-ready contract for the `clawkraft.com → setup.clawkraft.dev` hand-off.
Schema identifier: `clawkraft/initiation-intent/v1`.
Source-of-truth schema: [`/schemas/initiation-intent.v1.json`](../schemas/initiation-intent.v1.json).
Public-side reference implementation: [`/get-started/initiation.js`](../get-started/initiation.js).
Negative test suite: [`/tests/test_initiation_contract.py`](../tests/test_initiation_contract.py).

## Why this contract exists

The ClawKraft public surface (`clawkraft.com`) hands a new visitor off to Setup (`setup.clawkraft.dev`) without putting any credential, identifier, email, or contact value into the address bar, browser storage, logs, or public page state. The handoff is a *signed, single-use, expiring* initiation intent that Setup validates server-side before it will accept the visitor into onboarding.

## Threat model

| Adversary | Defence |
| --- | --- |
| Captures the visitor's address bar (Referer, history, screenshots) | Intent envelope is POSTed in the request body and is never serialized into the URL. The response Set-Cookie is `HttpOnly`, `Secure`, `SameSite=Strict`. |
| Replays a captured intent | Setup marks the `jti` consumed on first successful validation. Replay returns a closed-failure (`jti_replayed`). |
| Tampers with the envelope | Setup signs the envelope with its private key after binding. Any subsequent tamper fails HMAC verification (`signature_invalid`). |
| Holds the intent past TTL | `exp` ≤ now is rejected (`expired`). |
| Substitutes a different destination (open redirect) | The `aud` claim must equal `https://setup.clawkraft.dev/signup`. Setup only redirects to paths on `setup.clawkraft.dev`; a `return_path` that contains a scheme, host, or `//` is rejected (`open_redirect`). |
| Substitutes a different audience | The `aud` claim is locked to a single allowed value. Any other value is rejected (`aud_mismatch`). |

## What the public site sends

The public side generates a non-credential envelope locally and POSTs it to the Setup initiation endpoint. The envelope never leaves the public site unsigned; Setup binds it by signing it with its private key on receipt.

Required fields (matches the JSON Schema):

| Field | Value (public side) | Purpose |
| --- | --- | --- |
| `schema` | `clawkraft/initiation-intent/v1` | Identifies the contract version. |
| `iss` | `clawkraft.com` | Always the public surface. Never a privileged identity. |
| `aud` | `https://setup.clawkraft.dev/signup` | Setup rejects any other audience. |
| `iat` | unix seconds, generated client-side | Reference timestamp for TTL. |
| `exp` | `iat + 300` | Hard 5-minute TTL. |
| `jti` | 32-hex-char CSPRNG value (16 random bytes) | One-time identifier. |
| `intent_type` | `signup_initiation` | Reserved enum. |
| `source_surface` | One of the eight canonical public surfaces | Audit trail only. |
| `destination` | `https://setup.clawkraft.dev/signup` | Bound destination. |
| `consent_version` | `v1` | Visitor was shown the public privacy/terms copy before initiation. |

The envelope **MUST NOT** carry any of: `email`, `password`, `token`, `api_key`, `apikey`, `secret`, `credential`, `authorization`, `cookie`, `session`. The schema enforces this with a `not` clause, and the public-side reference implementation enforces it again before submission as defence in depth.

## What Setup does on receipt

1. Validate the envelope against the schema (presence, types, enums, forbidden-field guard).
2. Confirm `aud == https://setup.clawkraft.dev/signup` and `iss == clawkraft.com` (audience binding).
3. Reject if `exp ≤ now` (expiry) or if `iat` is unreasonably far from server clock (clock-skew guard).
4. Reject if `jti` is already present in the consumed-jti cache (replay).
5. Sign the envelope with Setup's private key (HMAC over the canonicalised payload).
6. Mark `jti` consumed (TTL = `exp - now`).
7. Set-Cookie: `__clawkraft_intent=<JWS>` with `HttpOnly; Secure; SameSite=Strict; Path=/signup; Max-Age=300`.
8. `303 See Other` to `https://setup.clawkraft.dev/signup`.

If `return_path` is provided by the caller, Setup MUST:

- Accept only values that begin with `/` and contain no `:` or `//`.
- Reject values that begin with `//`, contain `://`, contain `\\`, or carry a host/scheme.
- Prefix the resulting `Location` with `https://setup.clawkraft.dev` and never with any other origin.

If any step fails, Setup MUST return a closed failure (HTTP 401 for envelope issues, HTTP 400 for `return_path` shape issues, HTTP 410 for replay, HTTP 408 for expiry) and MUST NOT redirect the visitor to any non-Setup origin.

## Failure modes (fail closed)

| Code | When | HTTP | What Setup returns |
| --- | --- | --- | --- |
| `schema_invalid` | Missing required field, wrong type, enum mismatch | 400 | No redirect, no cookie, no intent state written. |
| `credential_field_present` | Envelope carries a forbidden credential-style field | 400 | No redirect, no cookie. |
| `aud_mismatch` | `aud` is anything other than `https://setup.clawkraft.dev/signup` | 401 | No redirect, no cookie. |
| `expired` | `exp ≤ now` | 408 | No redirect, no cookie. |
| `signature_invalid` | HMAC over the bound envelope does not match | 401 | No redirect, no cookie. |
| `jti_replayed` | `jti` already present in the consumed-jti cache | 410 | No redirect, no cookie. |
| `open_redirect` | `return_path` carries a scheme, host, or `//` | 400 | No redirect, no cookie. |

All failure modes leave Setup state untouched: no row is written, no jti is consumed, no cookie is set.

## What the public site never does

- Never sends an email, password, identifier, token, or contact value in the envelope.
- Never stores the intent in `localStorage`, `sessionStorage`, IndexedDB, cookies, or the address bar.
- Never logs the envelope.
- Never embeds the envelope in DOM text, screenshots, or any public page state.
- Never uses the intent to gate any privileged action on `clawkraft.com`.

## What Setup never does

- Never treats a missing intent as an implicit authorisation.
- Never grants access to /signup without a valid, unexpired, single-use, audience-bound intent.
- Never redirects to a host other than `setup.clawkraft.dev`.
- Never echoes the envelope back into the address bar.
- Never reflects the envelope into HTML pages on `setup.clawkraft.dev`.

## Conformance tests

Run:

```bash
python3 tests/test_initiation_contract.py
```

The test suite is offline and deterministic. It validates:

1. A valid envelope passes binding and consumption.
2. Replaying a consumed `jti` fails closed.
3. Tampering with any field after binding fails closed.
4. An expired envelope fails closed.
5. An envelope with a non-canonical `aud` fails closed.
6. An envelope carrying a forbidden credential field fails closed.
7. An `open_redirect` attempt (a `return_path` carrying a scheme or `//`) fails closed.
8. The reference envelope does not contain any value that the schema marks as forbidden.

A failing test exits non-zero and prints the specific failure code from the table above.

## Versioning

The contract is versioned by the `schema` field (`clawkraft/initiation-intent/v1`). A future revision MUST introduce a new schema identifier (e.g. `clawkraft/initiation-intent/v2`) and MUST be additive — Setup continues to accept `v1` for a documented deprecation window.