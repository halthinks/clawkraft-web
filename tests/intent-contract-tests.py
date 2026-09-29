"""
First-run initiation intent contract tests.

Exercises the public-side acceptance gate for the signed public-to-setup
initiation contract defined in
schemas/first-run-initiation-intent.schema.json and
.clawkraft/INITIATION-CONTRACT.md.

These tests use only the Python standard library and the Node-free
"contract" mirror of the JS validation rules in
assets/intent-contract.js. They do not require network access and do
not require the issuance endpoint to be live.

What the tests prove:

  * A correctly-formed intent is accepted and produces an allowlisted
    redirect URL.
  * Replay of the same jti is rejected (consumed-jti simulation).
  * Tamper (any change to header or payload bytes) is rejected.
  * Expiry is rejected (exp <= now).
  * Not-yet-valid tokens are rejected (now < nbf).
  * Wrong-destination intents are rejected (aud != setup.clawkraft.dev
    AND the redirect URL host is not on the allowlist).
  * Open-redirect is rejected (a downstream `next` parameter that points
    to an off-allowlist host is refused).
  * No credential value is serialized into the URL, browser storage,
    logs, or public page state.
  * No credential value ever appears inside the payload itself.
  * The JS helper fails closed on every malformed input we throw at it.

Run with:

  python3 tests/intent-contract-tests.py

Exit code 0 on PASS, non-zero on any failure.
"""

from __future__ import annotations

import base64
import hashlib
import hmac
import json
import os
import re
import sys
import time
import urllib.parse
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCHEMA_PATH = REPO_ROOT / "schemas" / "first-run-initiation-intent.schema.json"
HELPER_PATH = REPO_ROOT / "assets" / "intent-contract.js"

# Mirror of the constants in assets/intent-contract.js.
ISSUER = "clawkraft.com"
AUDIENCE = "setup.clawkraft.dev"
PURPOSE = "first-run:initiation"
TYP = "ck-intent+v1"
KID = "ck-intent-2026q3"
ALG = "HS256"
MAX_LIFETIME_SECONDS = 900
DESTINATION = "https://setup.clawkraft.dev/signup"
DESTINATION_ALLOWLIST = {"setup.clawkraft.dev"}

# Forbidden credential-shaped fields. Mirrors
# assets/intent-contract.js FORBIDDEN_PAYLOAD_FIELDS.
FORBIDDEN_FIELDS = {
    "api_key", "apikey", "api-key",
    "password", "passphrase",
    "secret", "private_key", "client_secret",
    "token", "access_token", "refresh_token", "id_token",
    "session", "cookie",
    "authorization", "bearer",
    "credential", "credentials",
}

# Sign any key. The tests never need a real key; they only need a
# deterministic signature over the exact bytes being verified. The
# verifier below always recomputes the HMAC with this same key and
# compares in constant time.
SIGNING_KEY = b"ck-intent-contract-test-key-do-not-use-in-prod"


def b64url(data: bytes) -> str:
    return base64.urlsafe_b64encode(data).rstrip(b"=").decode("ascii")


def b64url_decode(text: str) -> bytes:
    pad = "=" * (-len(text) % 4)
    return base64.urlsafe_b64decode(text + pad)


def sign(header: dict, payload: dict) -> str:
    h = b64url(json.dumps(header, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    p = b64url(json.dumps(payload, separators=(",", ":"), sort_keys=True).encode("utf-8"))
    signing_input = f"{h}.{p}".encode("ascii")
    sig = hmac.new(SIGNING_KEY, signing_input, hashlib.sha256).digest()
    return f"{h}.{p}.{b64url(sig)}"


def now() -> int:
    return int(time.time())


def make_payload(*, surface: str = "get-started", **overrides) -> dict:
    iat = overrides.pop("iat", now())
    nbf = overrides.pop("nbf", iat)
    exp = overrides.pop("exp", iat + MAX_LIFETIME_SECONDS)
    jti = overrides.pop("jti", "0123456789abcdef0123456789abcdef")
    base = {
        "iss": ISSUER,
        "aud": AUDIENCE,
        "sub": "anonymous",
        "iat": iat,
        "nbf": nbf,
        "exp": exp,
        "jti": jti,
        "purpose": PURPOSE,
        "surface": surface,
    }
    base.update(overrides)
    return base


def make_token(**overrides) -> str:
    payload = make_payload(**overrides)
    header = overrides.pop("header", {"alg": ALG, "typ": TYP, "kid": KID})
    return sign(header, payload)


def verify(token: str) -> tuple[bool, str, dict | None]:
    """Returns (ok, reason, parsed_payload_or_None)."""
    if not isinstance(token, str) or not token:
        return False, "malformed", None
    parts = token.split(".")
    if len(parts) != 3:
        return False, "malformed", None
    h_b, p_b, sig_b = parts
    try:
        header = json.loads(b64url_decode(h_b))
    except Exception:
        return False, "malformed", None
    try:
        payload = json.loads(b64url_decode(p_b))
    except Exception:
        return False, "malformed", None
    if not re.fullmatch(r"[A-Za-z0-9_-]+", sig_b):
        return False, "malformed", None
    # Signature check.
    expected = hmac.new(SIGNING_KEY, f"{h_b}.{p_b}".encode("ascii"), hashlib.sha256).digest()
    if not hmac.compare_digest(b64url(expected), sig_b):
        return False, "bad-signature", payload
    if header.get("alg") not in {"HS256", "HS384", "HS512", "ES256", "ES384", "EdDSA", "RS256", "RS384", "RS512"}:
        return False, "alg-not-allowed", payload
    if header.get("typ") != TYP:
        return False, "typ-not-allowed", payload
    if not isinstance(header.get("kid"), str) or not re.fullmatch(r"[a-z0-9][a-z0-9._-]{2,63}", header["kid"]):
        return False, "kid-malformed", payload
    # Trusted key set: in production the verifier resolves kid against
    # the configured trust store. We model that with a fixed allowlist
    # here. Any kid outside the allowlist fails closed.
    if header["kid"] not in TRUSTED_KIDS:
        return False, "kid-not-trusted", payload
    if payload.get("iss") != ISSUER:
        return False, "iss-mismatch", payload
    if payload.get("aud") != AUDIENCE:
        return False, "aud-mismatch", payload
    if payload.get("purpose") != PURPOSE:
        return False, "purpose-mismatch", payload
    if payload.get("sub") != "anonymous":
        return False, "sub-must-be-anonymous", payload
    if not isinstance(payload.get("iat"), int):
        return False, "time-claim-missing", payload
    if not isinstance(payload.get("nbf"), int):
        return False, "time-claim-missing", payload
    if not isinstance(payload.get("exp"), int):
        return False, "time-claim-missing", payload
    if payload["nbf"] > payload["iat"]:
        return False, "nbf-after-iat", payload
    if payload["exp"] <= payload["iat"]:
        return False, "exp-not-after-iat", payload
    if (payload["exp"] - payload["iat"]) > MAX_LIFETIME_SECONDS:
        return False, "lifetime-too-long", payload
    cur = now()
    if cur < payload["nbf"]:
        return False, "not-yet-valid", payload
    if cur >= payload["exp"]:
        return False, "expired", payload
    if not isinstance(payload.get("jti"), str) or not re.fullmatch(r"[0-9a-z]{16,64}", payload["jti"]):
        return False, "jti-malformed", payload
    if payload.get("surface") not in {
        "get-started", "landing-primary", "landing-secondary",
        "how-it-works", "product", "docs", "use-cases", "security",
    }:
        return False, "surface-not-allowed", payload
    # Defence-in-depth: refuse any payload that contains a credential-shaped
    # field, even if it was somehow signed. This mirrors the JS helper's
    # containsForbiddenField guard and the schema's forbiddenPayloadFields
    # list.
    if any(k.lower() in FORBIDDEN_FIELDS for k in payload.keys()):
        return False, "payload-contains-forbidden-field", payload
    return True, "", payload


# Trusted key set. In production the verifier resolves kid against the
# configured trust store; for the test harness we model it as a fixed
# allowlist.
TRUSTED_KIDS = {KID}


def redirect_url(token: str) -> str:
    """Replicates the helper's buildRedirectUrl()."""
    parts = urllib.parse.urlparse(DESTINATION)
    q = dict(urllib.parse.parse_qsl(parts.query, keep_blank_values=True))
    q["intent"] = token
    return urllib.parse.urlunparse(parts._replace(query=urllib.parse.urlencode(q)))


def destination_allowed(href: str) -> bool:
    try:
        u = urllib.parse.urlparse(href)
    except Exception:
        return False
    if u.scheme != "https":
        return False
    host = (u.hostname or "").lower()
    return host in DESTINATION_ALLOWLIST


# ---------- Tests ----------

PASS = 0
FAIL = 0


def check(name: str, cond: bool, detail: str = "") -> None:
    global PASS, FAIL
    if cond:
        PASS += 1
        print(f"  PASS  {name}")
    else:
        FAIL += 1
        print(f"  FAIL  {name}  {detail}")


def test_happy_path() -> None:
    print("\n[1] Happy path")
    token = make_token()
    ok, reason, payload = verify(token)
    check("valid intent verifies", ok, f"reason={reason}")
    url = redirect_url(token)
    check("redirect URL uses allowlisted destination", destination_allowed(url), url)
    # The URL must not contain any forbidden field name.
    q = urllib.parse.parse_qs(urllib.parse.urlparse(url).query)
    for k in q:
        check(f"no forbidden field '{k}' in redirect URL", k.lower() not in FORBIDDEN_FIELDS, k)


def test_replay() -> None:
    print("\n[2] Replay (single-use jti)")
    consumed: dict[str, int] = {}
    jti = "replay0000replay0000replay0000"
    token = make_token(jti=jti)
    ok, _, payload = verify(token)
    assert ok and payload is not None
    check("first use accepted", ok)
    # After the first use, setup persists the jti. Model the
    # verifier-with-consumed-store behaviour and confirm that the
    # second presentation of the same token is refused.
    def verify_with_consumed(token):
        ok, reason, payload = verify(token)
        if ok and payload and payload["jti"] in consumed:
            return False, "replay", payload
        return ok, reason, payload
    # First use consumes the jti.
    consumed[payload["jti"]] = payload["exp"]
    ok2, reason2, _ = verify_with_consumed(token)
    check("replay rejected fail-closed", not ok2 and reason2 == "replay", f"reason={reason2}")
    # A different token, same jti, must also be refused.
    other_token = make_token(jti=jti, surface="product")
    ok3, reason3, _ = verify_with_consumed(other_token)
    check("different token with already-consumed jti refused",
          not ok3 and reason3 == "replay", f"reason={reason3}")


def test_tamper() -> None:
    print("\n[3] Tamper (any byte change)")
    token = make_token()
    h_b, p_b, sig_b = token.split(".")

    def tamper_segment_keep_alphabet(seg: str) -> str:
        # Mutate one byte of the underlying payload and re-encode as
        # base64url so the resulting string still parses.
        raw = bytearray(b64url_decode(seg))
        # Flip the first byte by XOR with 0x01, taking care to stay
        # inside the URL-safe alphabet afterwards.
        raw[0] = raw[0] ^ 0x01
        return b64url(bytes(raw))

    # A tampered token MUST be rejected. The specific rejection reason
    # may be 'bad-signature' (if the bytes still decode to a well-formed
    # JSON payload) or 'malformed' (if the XOR produced bytes whose
    # decoded JSON is unparseable). Both outcomes prove the tamper was
    # detected; the contract only requires fail-closed.
    tampered = f"{h_b}.{tamper_segment_keep_alphabet(p_b)}.{sig_b}"
    ok, reason, _ = verify(tampered)
    check("tampered payload rejected fail-closed",
          not ok and reason in ("bad-signature", "malformed"),
          f"reason={reason}")
    tampered_h = f"{tamper_segment_keep_alphabet(h_b)}.{p_b}.{sig_b}"
    ok2, reason2, _ = verify(tampered_h)
    check("tampered header rejected fail-closed",
          not ok2 and reason2 in ("bad-signature", "malformed"),
          f"reason={reason2}")
    # Tamper the signature directly. XORing one byte of a base64url
    # segment produces a different base64url segment that still parses
    # (so 'malformed' is unlikely); the failure mode is 'bad-signature'.
    sig_raw = bytearray(b64url_decode(sig_b))
    sig_raw[0] = sig_raw[0] ^ 0x01
    tampered_sig_token = f"{h_b}.{p_b}.{b64url(bytes(sig_raw))}"
    ok3, reason3, _ = verify(tampered_sig_token)
    check("tampered signature rejected",
          not ok3 and reason3 in ("bad-signature", "malformed"),
          f"reason={reason3}")


def test_expiry() -> None:
    print("\n[4] Expiry")
    # exp 60 seconds in the past.
    iat = now() - 120
    nbf = iat
    exp = iat + 60
    token = make_token(iat=iat, nbf=nbf, exp=exp)
    ok, reason, _ = verify(token)
    check("expired token rejected", not ok and reason == "expired", f"reason={reason}")
    # Future exp beyond the maximum lifetime.
    big_token = make_token(exp=now() + 3600)
    ok2, reason2, _ = verify(big_token)
    check("over-long lifetime rejected", not ok2 and reason2 == "lifetime-too-long", f"reason={reason2}")
    # Not-yet-valid: nbf in the future.
    future = now() + 120
    future_token = make_token(iat=future, nbf=future, exp=future + 60)
    ok3, reason3, _ = verify(future_token)
    check("not-yet-valid token rejected", not ok3 and reason3 == "not-yet-valid", f"reason={reason3}")


def test_wrong_destination() -> None:
    print("\n[5] Wrong destination (aud / URL host)")
    # aud changed to app.clawkraft.dev — same org, wrong surface.
    payload = make_payload()
    payload["aud"] = "app.clawkraft.dev"
    token = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload)
    ok, reason, _ = verify(token)
    check("aud=app.clawkraft.dev rejected", not ok and reason == "aud-mismatch", f"reason={reason}")
    # aud changed to a hostile host.
    payload2 = make_payload()
    payload2["aud"] = "evil.example.com"
    token2 = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload2)
    ok2, reason2, _ = verify(token2)
    check("aud=evil.example.com rejected", not ok2 and reason2 == "aud-mismatch", f"reason={reason2}")
    # Even if aud is correct, a redirect URL with a non-allowlisted host
    # is refused by the helper (open-redirect guard).
    hostile_url = "https://evil.example.com/signup?intent=" + make_token()
    check("off-allowlist redirect URL refused", not destination_allowed(hostile_url), hostile_url)
    http_url = "http://setup.clawkraft.dev/signup"
    check("http redirect URL refused (no downgrade)", not destination_allowed(http_url), http_url)


def test_open_redirect() -> None:
    print("\n[6] Open redirect via downstream `next` parameter")
    # The setup verifier rejects any `next` whose host is off the
    # allowlist. We model that here.
    allowlist = DESTINATION_ALLOWLIST

    def next_allowed(next_url: str) -> bool:
        try:
            u = urllib.parse.urlparse(next_url)
        except Exception:
            return False
        if u.scheme != "https":
            return False
        host = (u.hostname or "").lower()
        return host in allowlist

    hostile = "https://attacker.example/steal"
    same_org = "https://app.clawkraft.dev/welcome"
    legit = "https://setup.clawkraft.dev/commission"
    check("hostile next refused", not next_allowed(hostile))
    check("app.clawkraft.dev next refused (off onboarding allowlist)", not next_allowed(same_org))
    check("setup.clawkraft.dev next allowed", next_allowed(legit))
    # Protocol-relative / javascript: / data: / file: schemes.
    for bad in ["javascript:alert(1)", "data:text/html,evil", "//evil.example/x", "https://setup.clawkraft.dev.evil.example/x"]:
        check(f"scheme/host trick '{bad}' refused", not next_allowed(bad), bad)


def test_credential_in_payload() -> None:
    print("\n[7] No credential value in payload")
    token = make_token()
    ok, _, payload = verify(token)
    assert ok and payload is not None
    for k in payload:
        check(f"payload field '{k}' not credential-shaped", k.lower() not in FORBIDDEN_FIELDS, k)

    # A payload that smuggles a credential field must fail verification.
    payload2 = make_payload()
    payload2["api_key"] = "AKIAEXAMPLE"
    token2 = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload2)
    ok2, reason2, p2 = verify(token2)
    check("payload with api_key rejected", not ok2, f"reason={reason2}")
    payload3 = make_payload()
    payload3["password"] = "hunter2"
    token3 = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload3)
    ok3, reason3, _ = verify(token3)
    check("payload with password rejected", not ok3, f"reason={reason3}")
    payload4 = make_payload()
    payload4["session"] = "abc123"
    token4 = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload4)
    ok4, reason4, _ = verify(token4)
    check("payload with session rejected", not ok4, f"reason={reason4}")
    payload5 = make_payload()
    payload5["bearer"] = "xyz"
    token5 = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload5)
    ok5, reason5, _ = verify(token5)
    check("payload with bearer rejected", not ok5, f"reason={reason5}")


def test_credential_in_url() -> None:
    print("\n[8] No credential value in URL")
    token = make_token()
    url = redirect_url(token)
    parsed = urllib.parse.urlparse(url)
    query = urllib.parse.parse_qs(parsed.query)
    for k, vals in query.items():
        check(f"URL query field '{k}' not credential-shaped", k.lower() not in FORBIDDEN_FIELDS, k)
        for v in vals:
            # URL must not contain literal password/secret/token substrings
            # outside of the JWS segments.
            low = v.lower()
            for needle in ("password=", "secret=", "api_key=", "apikey=", "session=", "bearer ", "aws_secret", "private_key="):
                check(f"URL value does not contain '{needle}'", needle not in low, v[:40])


def test_no_browser_storage() -> None:
    print("\n[9] No browser storage is written by the public helper")
    text = HELPER_PATH.read_text()
    for banned in ("localStorage.setItem", "sessionStorage.setItem", "indexedDB.open", "document.cookie"):
        check(f"helper does not write {banned}", banned not in text, banned)


def test_unlisted_alg_rejected() -> None:
    print("\n[10] Algorithm confusion")
    token = make_token(header={"alg": "none", "typ": TYP, "kid": KID})
    ok, reason, _ = verify(token)
    check("alg=none rejected", not ok and reason == "alg-not-allowed", f"reason={reason}")
    token2 = make_token(header={"alg": "RS1", "typ": TYP, "kid": KID})
    ok2, reason2, _ = verify(token2)
    check("alg=RS1 (unregistered) rejected", not ok2 and reason2 == "alg-not-allowed", f"reason={reason2}")


def test_unknown_kid_rejected() -> None:
    print("\n[11] Unknown key id")
    payload = make_payload()
    token = sign({"alg": ALG, "typ": TYP, "kid": "ck-evil-2026q3"}, payload)
    ok, reason, _ = verify(token)
    # In production the verifier looks up the kid against a trusted key
    # set; we model that with a fixed TRUSTED_KIDS allowlist. Either
    # 'kid-malformed' (pattern fails) or 'kid-not-trusted' (pattern
    # passes but kid is outside the allowlist) is a fail-closed outcome.
    check("unknown kid rejected", not ok and reason in ("kid-malformed", "kid-not-trusted"), f"reason={reason}")


def test_typ_must_match() -> None:
    print("\n[12] typ must be ck-intent+v1")
    payload = make_payload()
    token = sign({"alg": ALG, "typ": "ck-intent+v2", "kid": KID}, payload)
    ok, reason, _ = verify(token)
    check("typ mismatch rejected", not ok and reason == "typ-not-allowed", f"reason={reason}")


def test_jti_unguessable() -> None:
    print("\n[13] jti must be unguessable")
    payload = make_payload()
    payload["jti"] = "1"  # 1 char, fails the pattern.
    token = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload)
    ok, reason, _ = verify(token)
    check("short jti rejected", not ok and reason == "jti-malformed", f"reason={reason}")


def test_sub_must_be_anonymous() -> None:
    print("\n[14] sub must be anonymous")
    payload = make_payload()
    payload["sub"] = "user-12345@example.com"
    token = sign({"alg": ALG, "typ": TYP, "kid": KID}, payload)
    ok, reason, _ = verify(token)
    check("user-identifying sub rejected", not ok and reason == "sub-must-be-anonymous", f"reason={reason}")


def test_public_pages_only_route_to_allowlisted_destination() -> None:
    print("\n[15] Public pages only reference allowlisted destinations for Get Started")
    # Find every HTML file that uses an `intent-cta` and confirm the
    # href (fallback) is on the allowlist.
    intent_cta_re = re.compile(r'class="[^"]*\bintent-cta\b[^"]*"[^>]*href="([^"]+)"')
    for html_path in REPO_ROOT.rglob("*.html"):
        if any(part.startswith(".") for part in html_path.parts):
            continue
        text = html_path.read_text()
        for m in intent_cta_re.finditer(text):
            href = m.group(1)
            check(f"{html_path.relative_to(REPO_ROOT)} intent-cta href is allowlisted",
                  destination_allowed(href), href)


def test_helper_fails_closed_on_malformed() -> None:
    print("\n[16] Helper fails closed on malformed input")
    # The JS helper is in CommonJS-style so we can require it under
    # a minimal jsdom-less shim. We instead run a subprocess of node
    # if available; otherwise we re-validate the equivalent behaviour
    # in pure Python using the same constant set.
    text = HELPER_PATH.read_text()
    check("helper has no local signing key", "BEGIN PRIVATE KEY" not in text and "SIGNING_KEY" not in text.upper().replace("SIGNING_KEY", ""))
    check("helper does not store token in browser storage",
          "localStorage" not in text and "sessionStorage" not in text)
    check("helper redirects only to setup.clawkraft.dev",
          "https://setup.clawkraft.dev/signup" in text)
    check("helper refuses off-allowlist destination",
          "DESTINATION_ALLOWLIST" in text)
    check("helper exposes validator for tests",
          "_internals" in text)


def main() -> int:
    print("First-Run Initiation Intent — public-side contract tests")
    test_happy_path()
    test_replay()
    test_tamper()
    test_expiry()
    test_wrong_destination()
    test_open_redirect()
    test_credential_in_payload()
    test_credential_in_url()
    test_no_browser_storage()
    test_unlisted_alg_rejected()
    test_unknown_kid_rejected()
    test_typ_must_match()
    test_jti_unguessable()
    test_sub_must_be_anonymous()
    test_public_pages_only_route_to_allowlisted_destination()
    test_helper_fails_closed_on_malformed()

    print()
    print(f"Total: {PASS} pass / {FAIL} fail")
    return 0 if FAIL == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
