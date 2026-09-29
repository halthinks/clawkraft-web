/*!
 * ClawKraft Public-to-Setup Initiation Contract (public side).
 *
 * The public clawkraft.com surface possesses NO signing secret.
 * This module produces an UNSIGNED, NON-CREDENTIAL intent envelope and
 * POSTs it to https://setup.clawkraft.dev/initiate so that Setup can:
 *   - validate the envelope against the published schema,
 *   - bind it to the canonical destination,
 *   - sign it with its own private key,
 *   - mark the embedded jti as single-use,
 *   - 303-redirect the visitor to https://setup.clawkraft.dev/signup
 *     carrying a Secure / HttpOnly / SameSite=Strict cookie or signed
 *     fragment that Setup consumes server-side.
 *
 * If anything in this flow fails (missing API, unsupported UA, validation
 * error, etc.), the public site silently falls back to the existing
 * noscript-friendly link target so the Get Started CTA still works.
 *
 * The intent envelope MUST NOT carry any credential, identifier, email,
 * contact value, or provider secret. See schemas/initiation-intent.v1.json.
 */
(function () {
  'use strict';

  // ----- Contract constants (kept in sync with schemas/initiation-intent.v1.json) -----

  var CONTRACT_SCHEMA = 'clawkraft/initiation-intent/v1';
  var CONTRACT_VERSION = 'v1';
  var CONTRACT_AUDIENCE = 'https://setup.clawkraft.dev/signup';
  var CONTRACT_DESTINATION = 'https://setup.clawkraft.dev/signup';
  var CONTRACT_ISSUER = 'clawkraft.com';
  var CONTRACT_INTENT_TYPE = 'signup_initiation';
  // 5 minutes — see acceptance gate "Intent is single-use/expiring/bound to expected destination".
  var CONTRACT_TTL_SECONDS = 300;

  // Allowed source surfaces; mirrors schemas/initiation-intent.v1.json#source_surface enum.
  var ALLOWED_SOURCE_SURFACES = {
    'clawkraft.com/': 1,
    'clawkraft.com/get-started/': 1,
    'clawkraft.com/product/': 1,
    'clawkraft.com/how-it-works/': 1,
    'clawkraft.com/use-cases/': 1,
    'clawkraft.com/security/': 1,
    'clawkraft.com/docs/': 1,
    'clawkraft.com/status/': 1
  };

  // The Setup endpoint that signs the envelope and 303s to /signup.
  // Public site has no control plane; this is a contract value, not a credential.
  var SETUP_INITIATE_ENDPOINT = 'https://setup.clawkraft.dev/initiate';

  // ----- Minimal utilities (no third-party dependencies, no eval, no remote) -----

  function getSourceSurface() {
    var path = (typeof window !== 'undefined' && window.location && window.location.pathname) || '/';
    // Normalise trailing slash.
    if (path.length > 1 && path.charAt(path.length - 1) !== '/') {
      path = path + '/';
    }
    var host = (typeof window !== 'undefined' && window.location && window.location.host) || 'clawkraft.com';
    return host + path;
  }

  function nowSeconds() {
    return Math.floor((typeof window !== 'undefined' && window.location && Date.now)
      ? Date.now()
      : new Date().getTime() / 1000);
  }

  function hex(bytes) {
    var s = '';
    for (var i = 0; i < bytes.length; i++) {
      s += (bytes[i] < 16 ? '0' : '') + bytes[i].toString(16);
    }
    return s;
  }

  function b64urlEncode(bytes) {
    var s = '';
    for (var i = 0; i < bytes.length; i++) s += String.fromCharCode(bytes[i]);
    return btoa(s).replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, '');
  }

  // CSPRNG-backed jti (16 random bytes -> 32 hex chars). Falls back to
  // Math.random only if window.crypto is unavailable; in that degraded
  // path we abort initiation and let the no-JS link take over.
  function newJti() {
    var c = (typeof window !== 'undefined') ? window.crypto || window.msCrypto : null;
    if (!c || !c.getRandomValues) return null;
    var buf = new Uint8Array(16);
    c.getRandomValues(buf);
    return hex(buf);
  }

  // Build the intent envelope per the published schema. Strictly bounded:
  // no credential-style fields are ever added regardless of caller state.
  function buildEnvelope(sourceSurface, jti, iat) {
    return {
      schema: CONTRACT_SCHEMA,
      iss: CONTRACT_ISSUER,
      aud: CONTRACT_AUDIENCE,
      iat: iat,
      exp: iat + CONTRACT_TTL_SECONDS,
      jti: jti,
      intent_type: CONTRACT_INTENT_TYPE,
      source_surface: sourceSurface,
      destination: CONTRACT_DESTINATION,
      consent_version: CONTRACT_VERSION
    };
  }

  // Local schema check — defence in depth. The authoritative validator
  // is Setup's server, but the public side refuses to even submit a
  // malformed envelope.
  function isValidEnvelope(env) {
    if (!env || typeof env !== 'object') return false;
    if (env.schema !== CONTRACT_SCHEMA) return false;
    if (env.iss !== CONTRACT_ISSUER) return false;
    if (env.aud !== CONTRACT_AUDIENCE) return false;
    if (env.destination !== CONTRACT_DESTINATION) return false;
    if (env.intent_type !== CONTRACT_INTENT_TYPE) return false;
    if (!ALLOWED_SOURCE_SURFACES[env.source_surface]) return false;
    if (typeof env.iat !== 'number' || env.iat <= 0) return false;
    if (typeof env.exp !== 'number') return false;
    if (env.exp !== env.iat + CONTRACT_TTL_SECONDS) return false;
    if (typeof env.jti !== 'string' || env.jti.length < 16 || env.jti.length > 128) return false;
    // Hard guard: reject any intent that accidentally carries a credential
    // field. Mirrors schemas/initiation-intent.v1.json#not.
    var FORBIDDEN = ['email', 'password', 'token', 'api_key', 'apikey', 'secret', 'credential', 'authorization', 'cookie', 'session'];
    for (var i = 0; i < FORBIDDEN.length; i++) {
      if (Object.prototype.hasOwnProperty.call(env, FORBIDDEN[i])) return false;
    }
    return true;
  }

  // Build an auto-submitting POST form so that:
  //   - the intent envelope travels in the request body, not the URL,
  //   - the browser still navigates the user to the Setup destination,
  //   - no JavaScript-only state survives in the address bar.
  function submitAsForm(env) {
    var f = document.createElement('form');
    f.method = 'POST';
    f.action = SETUP_INITIATE_ENDPOINT;
    f.enctype = 'application/x-www-form-urlencoded';
    f.setAttribute('data-clawkraft-initiation', 'v1');
    // Carry the envelope as a single field so Setup can parse it deterministically.
    var payload = document.createElement('input');
    payload.type = 'hidden';
    payload.name = 'initiation';
    payload.value = JSON.stringify(env);
    f.appendChild(payload);
    // Carry source and intent_type as discrete fields too, so Setup can
    // do cheap filtering without parsing JSON. None of these are sensitive.
    var fields = ['intent_type', 'source_surface', 'destination', 'aud', 'iss', 'iat', 'exp', 'jti'];
    for (var i = 0; i < fields.length; i++) {
      var inp = document.createElement('input');
      inp.type = 'hidden';
      inp.name = fields[i];
      inp.value = String(env[fields[i]]);
      f.appendChild(inp);
    }
    // Append to DOM (required for some browsers to honour the form submit).
    f.style.display = 'none';
    document.body.appendChild(f);
    f.submit();
  }

  // Try to initiate. Returns true if a form submission was triggered,
  // false if the public site should fall back to the bare link.
  function tryInitiate(anchor) {
    try {
      var sourceSurface = getSourceSurface();
      if (!ALLOWED_SOURCE_SURFACES[sourceSurface]) return false;
      var jti = newJti();
      if (!jti) return false; // CSPRNG unavailable; do not initiate.
      var iat = nowSeconds();
      var env = buildEnvelope(sourceSurface, jti, iat);
      if (!isValidEnvelope(env)) return false;
      // Suppress the bare navigation: we'll POST instead.
      if (anchor && anchor.addEventListener) {
        anchor.addEventListener('click', function (e) {
          e.preventDefault();
          e.stopPropagation();
          submitAsForm(env);
        }, { once: true });
      }
      return true;
    } catch (err) {
      // Any failure here means we let the original link target through.
      return false;
    }
  }

  // Public entrypoint: enhance every "Get Started" anchor whose href is the
  // canonical setup destination. Anchors whose target is anything else
  // (mailto, tel, internal anchor) are left alone.
  function enhance(root) {
    if (!root || !root.querySelectorAll) return;
    var anchors = root.querySelectorAll('a[href]');
    for (var i = 0; i < anchors.length; i++) {
      var a = anchors[i];
      if (!a) continue;
      var href = a.getAttribute('href') || '';
      // Only enhance the canonical signup target. We do NOT enhance
      // app.clawkraft.dev/ (Login) — that path is unrelated to the
      // initiation contract.
      if (href.indexOf('https://setup.clawkraft.dev/signup') !== 0) continue;
      if (a.getAttribute('data-clawkraft-enhanced') === 'v1') continue;
      a.setAttribute('data-clawkraft-enhanced', 'v1');
      tryInitiate(a);
    }
  }

  if (typeof document !== 'undefined') {
    if (document.readyState === 'loading') {
      document.addEventListener('DOMContentLoaded', function () { enhance(document); });
    } else {
      enhance(document);
    }
  }

  // Expose a tiny, non-credential surface for tooling/tests that load this
  // module. Nothing here returns or accepts a credential, identifier, email,
  // or contact value.
  var ClawKraftInitiation = {
    CONTRACT_SCHEMA: CONTRACT_SCHEMA,
    CONTRACT_AUDIENCE: CONTRACT_AUDIENCE,
    CONTRACT_DESTINATION: CONTRACT_DESTINATION,
    CONTRACT_ISSUER: CONTRACT_ISSUER,
    CONTRACT_INTENT_TYPE: CONTRACT_INTENT_TYPE,
    CONTRACT_TTL_SECONDS: CONTRACT_TTL_SECONDS,
    ALLOWED_SOURCE_SURFACES: ALLOWED_SOURCE_SURFACES,
    SETUP_INITIATE_ENDPOINT: SETUP_INITIATE_ENDPOINT,
    buildEnvelope: buildEnvelope,
    isValidEnvelope: isValidEnvelope
  };
  if (typeof module !== 'undefined' && module.exports) {
    module.exports = ClawKraftInitiation;
  }
  if (typeof window !== 'undefined') {
    window.ClawKraftInitiation = ClawKraftInitiation;
  }
})();