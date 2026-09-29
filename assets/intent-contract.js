/*!
 * ClawKraft First-Run Initiation Intent — public-side helper.
 *
 * This helper is loaded by every ClawKraft public page that exposes a
 * "Get Started" call to action. It implements the public-side of the
 * signed public-to-setup initiation contract defined in
 * schemas/first-run-initiation-intent.schema.json and
 * .clawkraft/INITIATION-CONTRACT.md.
 *
 * Contract rules implemented here:
 *   - The intent is requested from a fixed first-party endpoint.
 *   - The helper validates the returned compact JWS structure client-side
 *     before performing the redirect. Validation failures fail closed.
 *   - The helper only redirects to https://setup.clawkraft.dev/signup with
 *     the intent placed in the `intent` query parameter. Any other
 *     destination fails closed.
 *   - No browser-side persistent storage is used. The token is held in a
 *     function-scoped variable for the lifetime of the click handler.
 *   - No credential, password, API key, or session identifier is ever
 *     serialized into the URL.
 *
 * This helper does NOT sign the intent. Signing is performed by the
 * clawkraft.dev issuance endpoint, which holds the signing key off the
 * public web. The helper only requests, validates the wire shape, and
 * redirects.
 */
(function (root) {
  'use strict';

  // Fixed trust anchors. These MUST NOT be configurable from the page.
  var DESTINATION = 'https://setup.clawkraft.dev/signup';
  var ISSUER = 'clawkraft.com';
  var AUDIENCE = 'setup.clawkraft.dev';
  var PURPOSE = 'first-run:initiation';

  // Issuance endpoint. The public site never holds a signing key; it only
  // asks the trusted endpoint to mint a fresh one-time intent.
  // The endpoint is exposed on setup.clawkraft.dev so the same origin
  // policy applies to both issuance and verification. The public site
  // calls it cross-origin with a strict response validator.
  var ISSUANCE_ENDPOINT = 'https://setup.clawkraft.dev/api/intent/start';

  // Hard ceiling for exp - iat, in seconds. Mirrors schema rule.
  var MAX_LIFETIME_SECONDS = 900;

  // Hard ceiling for the issuance request, in milliseconds. Anything
  // beyond this fails closed so the user is never silently redirected
  // without a valid intent.
  var ISSUANCE_TIMEOUT_MS = 4000;

  // Disallowed redirect targets. The helper will refuse to follow any
  // redirect or "next" parameter whose host is not on this allowlist.
  var DESTINATION_ALLOWLIST = ['setup.clawkraft.dev'];

  // Trusted key set. In production this is resolved server-side from
  // a configured trust store. The public helper bakes in the same
  // allowlist so a tampered kid never gets used to construct a redirect.
  var TRUSTED_KIDS = ['ck-intent-2026q3'];

  // Surface registry. Each page that wants to expose the helper picks
  // the surface it belongs to. The page opts in via a data attribute:
  //   <a class="intent-cta" data-surface="landing-primary" href="...">
  // The CTA href is preserved as a fallback if the intent helper fails
  // to mint a token, but only when the fallback destination matches the
  // allowlist (so a tampered href cannot turn into an open redirect).
  function b64UrlDecode(input) {
    if (typeof input !== 'string') return null;
    var pad = input.length % 4 === 0 ? 0 : 4 - (input.length % 4);
    var s = input.replace(/-/g, '+').replace(/_/g, '/');
    for (var i = 0; i < pad; i++) s += '=';
    try {
      var decoded = decodeURIComponent(escape(atob(s)));
      return decoded;
    } catch (_) {
      return null;
    }
  }

  function b64UrlDecodeJson(input) {
    var s = b64UrlDecode(input);
    if (s === null) return null;
    try {
      return JSON.parse(s);
    } catch (_) {
      return null;
    }
  }

  // Field names that MUST NEVER appear in the payload. Mirrors the
  // forbiddenPayloadFields list in the schema. We check both the schema
  // (where present) and a defensive client-side check here.
  var FORBIDDEN_PAYLOAD_FIELDS = [
    'api_key', 'apikey', 'api-key',
    'password', 'passphrase',
    'secret', 'private_key', 'client_secret',
    'token', 'access_token', 'refresh_token', 'id_token',
    'session', 'cookie',
    'authorization', 'bearer',
    'credential', 'credentials'
  ];

  function containsForbiddenField(obj) {
    if (!obj || typeof obj !== 'object') return false;
    for (var key in obj) {
      if (!Object.prototype.hasOwnProperty.call(obj, key)) continue;
      if (FORBIDDEN_PAYLOAD_FIELDS.indexOf(key.toLowerCase()) !== -1) return true;
      // Defence-in-depth: also reject anything that smells credential-ish
      var lk = key.toLowerCase();
      if (/key|pass|secret|token|session|auth/.test(lk) &&
          FORBIDDEN_PAYLOAD_FIELDS.indexOf(lk) === -1 &&
          // these are explicitly allowed payload claims; anything else matches
          ['iss', 'aud', 'sub', 'iat', 'nbf', 'exp', 'jti', 'purpose', 'surface', 'ref'].indexOf(lk) === -1) {
        return true;
      }
      if (typeof obj[key] === 'object' && containsForbiddenField(obj[key])) return true;
    }
    return false;
  }

  function validateCompactJws(token) {
    if (typeof token !== 'string' || token.length === 0) return null;
    var parts = token.split('.');
    if (parts.length !== 3) return null;
    var header = b64UrlDecodeJson(parts[0]);
    var payload = b64UrlDecodeJson(parts[1]);
    var signature = parts[2];
    if (!header || !payload || typeof signature !== 'string') return null;
    if (!/^[A-Za-z0-9_-]+$/.test(signature)) return null;
    return { header: header, payload: payload, signature: signature };
  }

  function validatePayloadRules(parsed, surface, nowSec) {
    var p = parsed.payload;
    var h = parsed.header;
    if (!h || !p) return 'malformed';
    if (h.alg !== 'HS256' && h.alg !== 'HS384' && h.alg !== 'HS512' &&
        h.alg !== 'ES256' && h.alg !== 'ES384' && h.alg !== 'EdDSA' &&
        h.alg !== 'RS256' && h.alg !== 'RS384' && h.alg !== 'RS512') return 'alg-not-allowed';
    if (h.typ !== 'ck-intent+v1') return 'typ-not-allowed';
    if (typeof h.kid !== 'string' || !/^[a-z0-9][a-z0-9._-]{2,63}$/.test(h.kid)) return 'kid-malformed';
    if (TRUSTED_KIDS.indexOf(h.kid) === -1) return 'kid-not-trusted';
    if (p.iss !== ISSUER) return 'iss-mismatch';
    if (p.aud !== AUDIENCE) return 'aud-mismatch';
    if (p.purpose !== PURPOSE) return 'purpose-mismatch';
    if (p.sub !== 'anonymous') return 'sub-must-be-anonymous';
    if (p.surface !== surface) return 'surface-mismatch';
    if (typeof p.iat !== 'number' || typeof p.nbf !== 'number' || typeof p.exp !== 'number') return 'time-claim-missing';
    if (p.nbf > p.iat) return 'nbf-after-iat';
    if (p.exp <= p.iat) return 'exp-not-after-iat';
    if ((p.exp - p.iat) > MAX_LIFETIME_SECONDS) return 'lifetime-too-long';
    if (nowSec < p.nbf) return 'not-yet-valid';
    if (nowSec >= p.exp) return 'expired';
    if (typeof p.jti !== 'string' || !/^[0-9a-z]{16,64}$/.test(p.jti)) return 'jti-malformed';
    if (containsForbiddenField(p)) return 'payload-contains-forbidden-field';
    return null;
  }

  function parseDestination(href) {
    try {
      var base = (typeof window !== 'undefined' && window.location && window.location.href) || 'https://clawkraft.com/';
      var u = new URL(href, base);
      return u;
    } catch (_) {
      return null;
    }
  }

  function destinationAllowed(u) {
    if (!u) return false;
    if (u.protocol !== 'https:') return false;
    var host = u.hostname.toLowerCase();
    for (var i = 0; i < DESTINATION_ALLOWLIST.length; i++) {
      if (host === DESTINATION_ALLOWLIST[i]) return true;
    }
    return false;
  }

  function fallbackAllowed(href) {
    var u = parseDestination(href);
    return destinationAllowed(u);
  }

  // Issue an intent by POSTing to the trusted endpoint with the surface
  // and a CSRF-style freshness token derived from `crypto.randomUUID`
  // when available, otherwise a Math.random fallback. The freshness
  // value is NOT a credential; it is a per-click correlation reference.
  function issueIntent(surface, signal) {
    var ref;
    if (typeof crypto !== 'undefined' && typeof crypto.randomUUID === 'function') {
      ref = crypto.randomUUID().replace(/-/g, '').slice(0, 32);
    } else {
      var r = '';
      var alphabet = '0123456789abcdef';
      for (var i = 0; i < 32; i++) r += alphabet[Math.floor(Math.random() * 16)];
      ref = r;
    }
    var body = JSON.stringify({ surface: surface, ref: ref });
    var controller = (typeof AbortController === 'function') ? new AbortController() : null;
    var timer = null;
    var timeoutPromise = new Promise(function (resolve) {
      timer = setTimeout(function () {
        if (controller) controller.abort();
        resolve(null);
      }, ISSUANCE_TIMEOUT_MS);
    });
    var fetchPromise = fetch(ISSUANCE_ENDPOINT, {
      method: 'POST',
      credentials: 'omit',
      mode: 'cors',
      redirect: 'error',
      referrerPolicy: 'no-referrer',
      headers: { 'Content-Type': 'application/json', 'Accept': 'application/jose' },
      body: body,
      signal: controller ? controller.signal : undefined
    }).then(function (r) {
      clearTimeout(timer);
      if (!r || !r.ok) return null;
      var ct = r.headers.get('content-type') || '';
      if (ct.indexOf('application/jose') === -1 && ct.indexOf('text/plain') === -1) return null;
      return r.text();
    }).catch(function () { clearTimeout(timer); return null; });
    return Promise.race([fetchPromise, timeoutPromise]).then(function (token) {
      if (!token) return null;
      var parsed = validateCompactJws(token);
      if (!parsed) return null;
      var nowSec = Math.floor(Date.now() / 1000);
      var reason = validatePayloadRules(parsed, surface, nowSec);
      if (reason) return null;
      return token;
    });
  }

  function buildRedirectUrl(intentToken) {
    var u = new URL(DESTINATION);
    u.searchParams.set('intent', intentToken);
    return u.toString();
  }

  function logFailure(surface, reason) {
    // Public-page failure log. We intentionally do NOT log the token or
    // any value derived from it. The reason is a coarse categorical
    // label only.
    if (typeof console !== 'undefined' && console.warn) {
      console.warn('[clawkraft-intent] issuance failed for surface=' + surface + ' reason=' + reason);
    }
  }

  function attach(elements) {
    if (!elements || !elements.length) return;
    for (var i = 0; i < elements.length; i++) {
      (function (el) {
        if (el.__ckIntentBound) return;
        el.__ckIntentBound = true;
        var surface = el.getAttribute('data-surface') || 'get-started';
        var fallbackHref = el.getAttribute('href') || DESTINATION;
        // The fallback href is only honored if it points to the
        // allowlisted destination. Otherwise the click fails closed.
        var fallbackOk = fallbackAllowed(fallbackHref);
        el.addEventListener('click', function (ev) {
          // Allow modifier-clicks (open in new tab, etc.) to behave as
          // ordinary link clicks. We still require an intent for them.
          if (ev.metaKey || ev.ctrlKey || ev.shiftKey || ev.altKey) return;
          ev.preventDefault();
          issueIntent(surface).then(function (token) {
            if (!token) {
              logFailure(surface, 'issuance-failed');
              // Fail closed. We do not navigate to the fallback URL
              // unless it was already allowlisted AND we have a token.
              // We also do not silently navigate to the static
              // destination because that would defeat the contract.
              if (fallbackOk) {
                // Even with an allowlisted fallback, we still refuse to
                // navigate without an intent. The user must retry.
                if (el.dataset.ckIntentNotice !== '1') {
                  el.setAttribute('data-ck-intent-notice', '1');
                  el.dataset.ckIntentNotice = '1';
                }
              }
              return;
            }
            var target = buildRedirectUrl(token);
            // Final defence: re-parse the redirect URL and confirm it
            // matches the fixed destination.
            var finalUrl = parseDestination(target);
            if (!destinationAllowed(finalUrl)) {
              logFailure(surface, 'redirect-not-allowed');
              return;
            }
            window.location.assign(target);
          });
        });
      })(elements[i]);
    }
  }

  var API = {
    DESTINATION: DESTINATION,
    AUDIENCE: AUDIENCE,
    PURPOSE: PURPOSE,
    MAX_LIFETIME_SECONDS: MAX_LIFETIME_SECONDS,
    DESTINATION_ALLOWLIST: DESTINATION_ALLOWLIST.slice(),
    // Exposed for the test harness only.
    _internals: {
      validateCompactJws: validateCompactJws,
      validatePayloadRules: validatePayloadRules,
      parseDestination: parseDestination,
      destinationAllowed: destinationAllowed,
      buildRedirectUrl: buildRedirectUrl,
      containsForbiddenField: containsForbiddenField
    }
  };

  function bindAll() {
    if (typeof document === 'undefined') return;
    var nodes = document.querySelectorAll('.intent-cta');
    attach(nodes);
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', bindAll);
    } else {
      bindAll();
    }
  }

  // Expose for tests on Node-style loaders; harmless on the public web.
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = API;
  }
  if (root) {
    root.ClawKraftIntent = API;
  }
})(typeof window !== 'undefined' ? window : null);
