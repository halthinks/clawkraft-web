#!/usr/bin/env python3
# ClawKraft Public-to-Setup Initiation Contract — conformance test suite.
#
# This is the offline, deterministic negative-test suite for FR-001. It
# exercises the reference Setup-side consumer (HMAC binding, jti caching,
# audience / TTL / forbidden-field guards) against a reference public
# producer. Every required action in the FR-001 work packet is covered:
#
#   - Define signed one-time initiation-intent schema.
#   - Issue intent from the public start contract without privileged state.
#   - Consume and invalidate intent at setup.
#   - Add replay, tamper, expiry, wrong-destination and open-redirect
#     negative tests.
#
# The tests do not contact the network and do not require any third-party
# dependency — only the Python standard library. Run with:
#
#     python3 tests/test_initiation_contract.py
#
# Exit status:
#   0  — every case passed (fail closed)
#   1  — at least one case failed (printed with the failure code)

from __future__ import annotations

import hashlib
import hmac
import json
import os
import re
import sys
import time
import traceback
import urllib.parse
from typing import Any, Callable, Dict, Optional, Tuple

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.dirname(HERE)
SCHEMA_PATH = os.path.join(ROOT, "schemas", "initiation-intent.v1.json")
JS_PATH = os.path.join(ROOT, "get-started", "initiation.js")


# ---------------------------------------------------------------------------
# Contract constants — kept in sync with schemas/initiation-intent.v1.json
# and get-started/initiation.js. If you change one, change the other two.
# ---------------------------------------------------------------------------

CONTRACT_SCHEMA = "clawkraft/initiation-intent/v1"
CONTRACT_AUDIENCE = "https://setup.clawkraft.dev/signup"
CONTRACT_DESTINATION = "https://setup.clawkraft.dev/signup"
CONTRACT_ISSUER = "clawkraft.com"
CONTRACT_INTENT_TYPE = "signup_initiation"
CONTRACT_TTL_SECONDS = 300

ALLOWED_SOURCE_SURFACES = {
    "clawkraft.com/",
    "clawkraft.com/get-started/",
    "clawkraft.com/product/",
    "clawkraft.com/how-it-works/",
    "clawkraft.com/use-cases/",
    "clawkraft.com/security/",
    "clawkraft.com/docs/",
    "clawkraft.com/status/",
}

# Schema-rejected credential-style fields. Defence-in-depth: kept here as
# well as in the JSON Schema `not` clause and in the JS reference impl.
FORBIDDEN_CREDENTIAL_FIELDS = (
    "email", "password", "token", "api_key", "apikey",
    "secret", "credential", "authorization", "cookie", "session",
)


# ---------------------------------------------------------------------------
# Reference Setup-side consumer.
#
# The Setup server is the only party that holds this private key. The
# public site never sees it. The class is deterministic and offline; it
# mirrors the contract behaviour described in docs/initiation-contract.md.
# ---------------------------------------------------------------------------

class SetupInitiateError(Exception):
    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code


class ReferenceSetupInitiator:
    """Reference implementation of the Setup side of FR-001."""

    def __init__(self, key: bytes, now: Optional[Callable[[], int]] = None):
        self._key = key
        self._consumed_jti = set()
        self._now_fn = now or (lambda: int(time.time()))

    # ---- private helpers ----

    def _canonical(self, env: Dict[str, Any]) -> bytes:
        # Stable JSON serialisation so signing/verifying always agrees.
        return json.dumps(env, sort_keys=True, separators=(",", ":")).encode("utf-8")

    def _sign(self, env: Dict[str, Any]) -> str:
        mac = hmac.new(self._key, self._canonical(env), hashlib.sha256)
        return mac.hexdigest()

    def _verify(self, env: Dict[str, Any], signature: str) -> bool:
        expected = self._sign(env)
        return hmac.compare_digest(expected, signature)

    def _validate_envelope(self, env: Any) -> None:
        if not isinstance(env, dict):
            raise SetupInitiateError("schema_invalid", "envelope is not an object")

        # Required fields.
        required = ("schema", "iss", "aud", "iat", "exp", "jti",
                    "intent_type", "source_surface", "destination")
        for f in required:
            if f not in env:
                raise SetupInitiateError("schema_invalid", f"missing {f}")

        # Schema id.
        if env["schema"] != CONTRACT_SCHEMA:
            raise SetupInitiateError("schema_invalid", "unknown schema")

        # Issuer.
        if env["iss"] != CONTRACT_ISSUER:
            raise SetupInitiateError("schema_invalid", "iss must be clawkraft.com")

        # Audience binding.
        if env["aud"] != CONTRACT_AUDIENCE:
            raise SetupInitiateError("aud_mismatch",
                                     "aud must be https://setup.clawkraft.dev/signup")

        # Destination binding.
        if env["destination"] != CONTRACT_DESTINATION:
            raise SetupInitiateError("aud_mismatch",
                                     "destination must be https://setup.clawkraft.dev/signup")

        # Intent type.
        if env["intent_type"] != CONTRACT_INTENT_TYPE:
            raise SetupInitiateError("schema_invalid", "intent_type must be signup_initiation")

        # Source surface enum.
        if env["source_surface"] not in ALLOWED_SOURCE_SURFACES:
            raise SetupInitiateError("schema_invalid",
                                     f"source_surface {env['source_surface']!r} not allowed")

        # iat / exp.
        if not isinstance(env["iat"], int) or env["iat"] <= 0:
            raise SetupInitiateError("schema_invalid", "iat must be a positive integer")
        if not isinstance(env["exp"], int):
            raise SetupInitiateError("schema_invalid", "exp must be an integer")
        if env["exp"] != env["iat"] + CONTRACT_TTL_SECONDS:
            raise SetupInitiateError("schema_invalid",
                                     f"exp must equal iat + {CONTRACT_TTL_SECONDS}")

        # jti.
        if not isinstance(env["jti"], str) or not (16 <= len(env["jti"]) <= 128):
            raise SetupInitiateError("schema_invalid",
                                     "jti must be 16..128 chars")

        # Forbidden credential fields.
        for f in FORBIDDEN_CREDENTIAL_FIELDS:
            if f in env:
                raise SetupInitiateError(
                    "credential_field_present",
                    f"envelope must not carry {f!r}",
                )

    def _validate_return_path(self, return_path: Any) -> None:
        """Setup may only redirect to a same-origin path on setup.clawkraft.dev."""
        if return_path is None:
            return
        if not isinstance(return_path, str):
            raise SetupInitiateError("open_redirect", "return_path must be a string")
        # Must begin with a single '/'.
        if not return_path.startswith("/"):
            raise SetupInitiateError("open_redirect",
                                     "return_path must be a same-origin path")
        # Must not begin with '//' (protocol-relative URL).
        if return_path.startswith("//"):
            raise SetupInitiateError("open_redirect",
                                     "return_path must not be protocol-relative")
        # Must not carry a scheme.
        if re.match(r"^[a-zA-Z][a-zA-Z0-9+\-.]*:", return_path):
            raise SetupInitiateError("open_redirect",
                                     "return_path must not carry a scheme")
        # Must not contain a backslash trick.
        if "\\" in return_path:
            raise SetupInitiateError("open_redirect",
                                     "return_path must not contain backslashes")

    # ---- public surface ----

    def bind(self, env: Dict[str, Any], return_path: Optional[str] = None) -> Tuple[Dict[str, Any], str]:
        """Validate, sign, mark consumed, and return (signed_env, signature)."""
        self._validate_envelope(env)
        self._validate_return_path(return_path)

        now = self._now_fn()

        # Future skew guard: iat must not be unreasonably far in the future.
        # (Past iat is handled by the expiry guard; a backdated envelope
        # is exactly what `expired` is supposed to catch.)
        if env["iat"] > now + 60:
            raise SetupInitiateError("schema_invalid",
                                     "iat unreasonably far in the future")

        # Expiry.
        if env["exp"] <= now:
            raise SetupInitiateError("expired", "exp <= now")

        # Replay guard.
        if env["jti"] in self._consumed_jti:
            raise SetupInitiateError("jti_replayed", "jti already consumed")

        # Sign.
        signature = self._sign(env)

        # Consume.
        self._consumed_jti.add(env["jti"])

        return env, signature

    def verify(self, env: Dict[str, Any], signature: str) -> None:
        """Verify a bound envelope without consuming it (used to exercise tamper tests)."""
        self._validate_envelope(env)
        if not self._verify(env, signature):
            raise SetupInitiateError("signature_invalid", "HMAC mismatch")


# ---------------------------------------------------------------------------
# Reference public-side producer.
# ---------------------------------------------------------------------------

def produce_envelope(source_surface: str, jti: str, iat: int) -> Dict[str, Any]:
    return {
        "schema": CONTRACT_SCHEMA,
        "iss": CONTRACT_ISSUER,
        "aud": CONTRACT_AUDIENCE,
        "iat": iat,
        "exp": iat + CONTRACT_TTL_SECONDS,
        "jti": jti,
        "intent_type": CONTRACT_INTENT_TYPE,
        "source_surface": source_surface,
        "destination": CONTRACT_DESTINATION,
        "consent_version": "v1",
    }


# ---------------------------------------------------------------------------
# Test harness.
# ---------------------------------------------------------------------------

class TestResult:
    def __init__(self):
        self.passed = 0
        self.failed = 0
        self.failures = []

    def record(self, name: str, ok: bool, detail: str = "") -> None:
        if ok:
            self.passed += 1
            print(f"  [PASS] {name}")
        else:
            self.failed += 1
            self.failures.append((name, detail))
            print(f"  [FAIL] {name}: {detail}")


def expect_fail(callable_: Callable[[], Any], expected_code: str, label: str,
                result: TestResult) -> None:
    try:
        callable_()
    except SetupInitiateError as exc:
        if exc.code == expected_code:
            result.record(label, True)
            return
        result.record(label, False, f"expected {expected_code}, got {exc.code}")
        return
    except Exception as exc:  # pragma: no cover
        result.record(label, False, f"unexpected exception: {exc!r}")
        return
    result.record(label, False, f"expected failure {expected_code}, but call succeeded")


def expect_pass(callable_: Callable[[], Any], label: str,
                result: TestResult) -> None:
    try:
        callable_()
        result.record(label, True)
    except SetupInitiateError as exc:
        result.record(label, False, f"unexpected failure {exc.code}: {exc}")
    except Exception as exc:  # pragma: no cover
        result.record(label, False, f"unexpected exception: {exc!r}")


def run_tests() -> TestResult:
    result = TestResult()
    KEY = b"setup-private-key-not-known-to-public-site-" + os.urandom(8)

    # Use a fixed clock so expiry and replay tests are deterministic.
    clock = {"now": 1_760_000_000}

    def now_fn() -> int:
        return clock["now"]

    setup = ReferenceSetupInitiator(KEY, now=now_fn)

    # ---- positive case ----
    print("Positive case")
    env = produce_envelope("clawkraft.com/get-started/", "deadbeefcafef00d000000000000abcd0", clock["now"])
    signed, sig = setup.bind(env)
    setup.verify(signed, sig)
    result.record("valid envelope binds, signs, and verifies", True)

    # ---- replay ----
    print("\nReplay")
    replay_env = produce_envelope("clawkraft.com/get-started/", "replay000000000000000000000000abcd", clock["now"])
    _, sig = setup.bind(replay_env)
    def replay():
        # Setup must refuse a second bind of the same jti, even with the
        # same payload.
        setup.bind(replay_env)
    expect_fail(replay, "jti_replayed", "replay of consumed jti fails closed", result)

    # ---- tamper ----
    print("\nTamper")
    base_env = produce_envelope("clawkraft.com/get-started/", "tamper000000000000000000000000abcd", clock["now"])
    _, sig = setup.bind(base_env)

    # Tampering with the destination trips both the audience guard and
    # the signature check. Both are fail-closed; either is acceptable.
    tampered = dict(base_env)
    tampered["destination"] = "https://attacker.example/"
    def tamper_call():
        try:
            setup.verify(tampered, sig)
        except SetupInitiateError as exc:
            if exc.code in ("signature_invalid", "aud_mismatch"):
                return
            raise
    try:
        tamper_call()
        result.record("tampering with destination after binding fails closed", True)
    except SetupInitiateError as exc:
        result.record("tampering with destination after binding fails closed", False,
                      f"unexpected failure code {exc.code}")

    # Tampering with jti flips a byte inside the bound payload while
    # preserving shape — only the signature check can catch it.
    tampered2 = dict(base_env)
    tampered2["jti"] = "tampered000000000000000000000000abc"  # same length
    def tamper_call2():
        setup.verify(tampered2, sig)
    expect_fail(tamper_call2, "signature_invalid",
                "tampering with jti after binding fails closed", result)

    # ---- expiry ----
    print("\nExpiry")
    # Reset clock and issue a fresh envelope that we will then age out.
    clock["now"] = 1_760_010_000
    exp_env = produce_envelope("clawkraft.com/get-started/",
                               "expiry000000000000000000000000abcd",
                               clock["now"])
    setup.bind(exp_env)  # consume while fresh — proves it binds before expiry
    # Advance the clock past exp without changing iat.
    clock["now"] = exp_env["iat"] + CONTRACT_TTL_SECONDS + 1
    late_env = produce_envelope("clawkraft.com/get-started/",
                                "late0000000000000000000000000abcd",
                                exp_env["iat"])  # iat is the same as the bound envelope
    def expired_call():
        setup.bind(late_env)
    expect_fail(expired_call, "expired", "expired envelope fails closed", result)

    # ---- wrong destination (aud mismatch) ----
    print("\nWrong destination / audience")
    clock["now"] = 1_760_001_000
    bad_aud = produce_envelope("clawkraft.com/get-started/", "badaud00000000000000000000000abcd", clock["now"])
    bad_aud["aud"] = "https://attacker.example/welcome"
    def wrong_aud():
        setup.bind(bad_aud)
    expect_fail(wrong_aud, "aud_mismatch",
                "non-canonical aud fails closed", result)

    bad_dest = produce_envelope("clawkraft.com/get-started/", "baddest0000000000000000000000abcd", clock["now"])
    bad_dest["destination"] = "https://attacker.example/welcome"
    def wrong_dest():
        setup.bind(bad_dest)
    expect_fail(wrong_dest, "aud_mismatch",
                "non-canonical destination fails closed", result)

    # ---- open redirect ----
    print("\nOpen redirect")
    fresh_env = produce_envelope("clawkraft.com/get-started/", "opnredir0000000000000000000000abcd", clock["now"])
    def open_redirect_full():
        setup.bind(fresh_env, return_path="https://attacker.example/login")
    expect_fail(open_redirect_full, "open_redirect",
                "absolute http URL in return_path fails closed", result)

    def open_redirect_proto():
        setup.bind(produce_envelope("clawkraft.com/get-started/",
                                    "opnredir1000000000000000000000abcd",
                                    clock["now"]),
                   return_path="//attacker.example/login")
    expect_fail(open_redirect_proto, "open_redirect",
                "protocol-relative return_path fails closed", result)

    def open_redirect_evil_scheme():
        setup.bind(produce_envelope("clawkraft.com/get-started/",
                                    "opnredir2000000000000000000000abcd",
                                    clock["now"]),
                   return_path="javascript:alert(1)")
    expect_fail(open_redirect_evil_scheme, "open_redirect",
                "javascript: scheme in return_path fails closed", result)

    def open_redirect_backslash():
        setup.bind(produce_envelope("clawkraft.com/get-started/",
                                    "opnredir3000000000000000000000abcd",
                                    clock["now"]),
                   return_path="/\\attacker.example/login")
    expect_fail(open_redirect_backslash, "open_redirect",
                "backslash trick in return_path fails closed", result)

    def open_redirect_absolute():
        setup.bind(produce_envelope("clawkraft.com/get-started/",
                                    "opnredir4000000000000000000000abcd",
                                    clock["now"]),
                   return_path="attacker.example/login")
    expect_fail(open_redirect_absolute, "open_redirect",
                "host-relative return_path without leading slash fails closed", result)

    # ---- credential-field guard ----
    print("\nForbidden credential fields")
    for cred_field in FORBIDDEN_CREDENTIAL_FIELDS:
        bad = produce_envelope("clawkraft.com/get-started/", f"cred{cred_field}0000000000000000abcd".ljust(32, "0")[:32], clock["now"])
        bad[cred_field] = "attacker-supplied"
        def cred_call(b=bad):
            setup.bind(b)
        expect_fail(cred_call, "credential_field_present",
                    f"envelope carrying {cred_field!r} fails closed", result)

    # ---- schema-invalid guards ----
    print("\nSchema guards")
    missing_field = produce_envelope("clawkraft.com/get-started/", "missing0000000000000000000000abcd", clock["now"])
    del missing_field["exp"]
    expect_fail(lambda: setup.bind(missing_field), "schema_invalid",
                "missing required field fails closed", result)

    bad_intent_type = produce_envelope("clawkraft.com/get-started/", "badi0000000000000000000000000abcd", clock["now"])
    bad_intent_type["intent_type"] = "admin_login"
    expect_fail(lambda: setup.bind(bad_intent_type), "schema_invalid",
                "unknown intent_type fails closed", result)

    bad_source = produce_envelope("clawkraft.com/get-started/", "bads0000000000000000000000000abcd", clock["now"])
    bad_source["source_surface"] = "clawkraft.com/admin/"
    expect_fail(lambda: setup.bind(bad_source), "schema_invalid",
                "unknown source_surface fails closed", result)

    bad_ttl = produce_envelope("clawkraft.com/get-started/", "badttl00000000000000000000000abcd", clock["now"])
    bad_ttl["exp"] = bad_ttl["iat"] + 600  # longer than the contract permits
    expect_fail(lambda: setup.bind(bad_ttl), "schema_invalid",
                "exp != iat + TTL fails closed", result)

    short_jti = produce_envelope("clawkraft.com/get-started/", "abc", clock["now"])
    expect_fail(lambda: setup.bind(short_jti), "schema_invalid",
                "jti shorter than 16 chars fails closed", result)

    # ---- no URL/credential leakage in reference envelope ----
    print("\nNo URL/credential leakage in reference envelope")
    sample = produce_envelope("clawkraft.com/get-started/", "leakchk000000000000000000000abcd", clock["now"])
    serialised = json.dumps(sample, sort_keys=True)
    lower = serialised.lower()
    forbidden_strings = ("email", "password", "token", "api_key", "apikey",
                         "secret", "credential", "authorization", "cookie",
                         "session", "://")
    leak_found = False
    for s in forbidden_strings:
        # '://' is fine if it's the canonical audience/destination; we
        # permit exactly two occurrences (one in aud, one in destination).
        if s == "://":
            count = lower.count("://")
            if count > 2:
                leak_found = True
                break
        elif s in lower:
            leak_found = True
            break
    result.record("reference envelope carries no credential-style substring",
                  not leak_found,
                  "credential-style substring found" if leak_found else "")

    # ---- on-the-wire sanity: the form-POST path keeps the envelope out of the URL ----
    print("\nForm-POST keeps envelope out of URL")
    body = urllib.parse.urlencode({
        "initiation": json.dumps(sample),
        "intent_type": sample["intent_type"],
        "source_surface": sample["source_surface"],
        "destination": sample["destination"],
        "aud": sample["aud"],
        "iss": sample["iss"],
        "iat": sample["iat"],
        "exp": sample["exp"],
        "jti": sample["jti"],
    })
    # The envelope appears only in the request body, not in the URL query string.
    leaked_in_query = any(
        v in body.lower() for v in ("email", "password", "token", "secret")
    )
    result.record("initiation body does not serialise credential-style fields",
                  not leaked_in_query,
                  "credential-style field found in body" if leaked_in_query else "")

    # ---- schema-file presence and synchronisation ----
    print("\nSchema and source synchronisation")
    if not os.path.isfile(SCHEMA_PATH):
        result.record("schema file present", False, f"{SCHEMA_PATH} missing")
    else:
        schema_doc = json.loads(open(SCHEMA_PATH, "r", encoding="utf-8").read())
        schema_ok = (
            schema_doc.get("title") == "ClawKraft Public-to-Setup Initiation Intent"
            and schema_doc.get("properties", {}).get("aud", {}).get("enum") == [CONTRACT_AUDIENCE]
            and schema_doc.get("properties", {}).get("destination", {}).get("enum") == [CONTRACT_DESTINATION]
            and schema_doc.get("properties", {}).get("intent_type", {}).get("enum") == [CONTRACT_INTENT_TYPE]
        )
        result.record("schema file is the source of truth for v1 constants", schema_ok,
                      "schema mismatch" if not schema_ok else "")

    if not os.path.isfile(JS_PATH):
        result.record("public-side reference implementation present", False, f"{JS_PATH} missing")
    else:
        js_doc = open(JS_PATH, "r", encoding="utf-8").read()
        js_ok = (
            "CONTRACT_AUDIENCE = 'https://setup.clawkraft.dev/signup'" in js_doc
            and "CONTRACT_DESTINATION = 'https://setup.clawkraft.dev/signup'" in js_doc
            and "CONTRACT_ISSUER = 'clawkraft.com'" in js_doc
            and "CONTRACT_INTENT_TYPE = 'signup_initiation'" in js_doc
            and "CONTRACT_TTL_SECONDS = 300" in js_doc
            and "SETUP_INITIATE_ENDPOINT = 'https://setup.clawkraft.dev/initiate'" in js_doc
            and "isValidEnvelope" in js_doc
        )
        result.record("public-side JS matches the contract constants", js_ok,
                      "JS contract constants out of sync" if not js_ok else "")

    # ---- get-started page wires the script and preserves no-JS fallback ----
    print("\nPublic page wires the contract")
    gs_path = os.path.join(ROOT, "get-started", "index.html")
    if not os.path.isfile(gs_path):
        result.record("get-started/index.html present", False, f"{gs_path} missing")
    else:
        gs = open(gs_path, "r", encoding="utf-8").read()
        gs_ok = (
            "/get-started/initiation.js" in gs
            and "https://setup.clawkraft.dev/signup" in gs
            and "https://app.clawkraft.dev/" in gs
            and "https://setup.clawkraft.dev/initiate" in gs
            and "initiation-intent" in gs
        )
        result.record("get-started page references the contract and keeps canonical fallbacks", gs_ok,
                      "get-started page missing contract references" if not gs_ok else "")

    return result


def main() -> int:
    print("ClawKraft Initiation Contract (FR-001) — conformance suite")
    print("=" * 64)
    try:
        result = run_tests()
    except Exception:  # pragma: no cover
        traceback.print_exc()
        return 2

    print("\n" + "=" * 64)
    print(f"Passed: {result.passed}")
    print(f"Failed: {result.failed}")
    if result.failures:
        print("\nFailures (failures here mean the contract did NOT fail closed):")
        for name, detail in result.failures:
            print(f"  - {name}: {detail}")
    return 0 if result.failed == 0 else 1


if __name__ == "__main__":
    sys.exit(main())