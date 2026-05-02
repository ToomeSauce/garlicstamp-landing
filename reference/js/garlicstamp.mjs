// GarlicStamp v0.6 JavaScript reference verifier for Node.js 20+.
//
// Validates Alpha Garage-issued GarlicStamp portable credentials without private
// Garage context: fetch the public key, verify the Ed25519 signature over
// canonical JSON, then check the portable v0.6 evidence fields.

import { createPublicKey, verify as cryptoVerify } from 'node:crypto';

export const SUPPORTED_VERSION = '0.6';
export const DEFAULT_BASE_URL = 'https://alphagarage.io';
export const DEFAULT_USER_AGENT = 'garlicstamp-js-reference/0.6';

class JsonNumber {
  constructor(raw) {
    this.raw = raw;
    this.value = Number(raw);
  }

  valueOf() { return this.value; }
  toJSON() { return this.value; }
}

function isJsonNumber(value) {
  return value instanceof JsonNumber;
}

function isPlainObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value) && !isJsonNumber(value);
}

export function parseEnvelopeJson(text) {
  // Tiny lossless JSON parser: preserves number lexemes such as 0.0 because
  // Alpha Garage v0.6 signs Python json.dumps output, where 0 and 0.0 are not
  // interchangeable at the byte level. JSON.parse helpfully erases that detail.
  let i = 0;
  const s = String(text);
  const ws = () => { while (/\s/.test(s[i] ?? '')) i += 1; };
  const expect = (token) => {
    if (!s.startsWith(token, i)) throw new SyntaxError(`expected ${token} at ${i}`);
    i += token.length;
  };
  const parseString = () => {
    const start = i;
    i += 1;
    while (i < s.length) {
      const ch = s[i++];
      if (ch === '\\') i += 1;
      else if (ch === '"') return JSON.parse(s.slice(start, i));
    }
    throw new SyntaxError('unterminated JSON string');
  };
  const parseNumber = () => {
    const start = i;
    if (s[i] === '-') i += 1;
    if (s[i] === '0') i += 1;
    else if (/[1-9]/.test(s[i] ?? '')) while (/[0-9]/.test(s[i] ?? '')) i += 1;
    else throw new SyntaxError(`bad JSON number at ${i}`);
    if (s[i] === '.') { i += 1; if (!/[0-9]/.test(s[i] ?? '')) throw new SyntaxError(`bad JSON number at ${i}`); while (/[0-9]/.test(s[i] ?? '')) i += 1; }
    if (s[i] === 'e' || s[i] === 'E') { i += 1; if (s[i] === '+' || s[i] === '-') i += 1; if (!/[0-9]/.test(s[i] ?? '')) throw new SyntaxError(`bad JSON number at ${i}`); while (/[0-9]/.test(s[i] ?? '')) i += 1; }
    return new JsonNumber(s.slice(start, i));
  };
  const parseArray = () => {
    i += 1; ws();
    const out = [];
    if (s[i] === ']') { i += 1; return out; }
    while (true) {
      out.push(parseValue()); ws();
      if (s[i] === ']') { i += 1; return out; }
      expect(','); ws();
    }
  };
  const parseObject = () => {
    i += 1; ws();
    const out = {};
    if (s[i] === '}') { i += 1; return out; }
    while (true) {
      const key = parseString(); ws(); expect(':'); ws();
      out[key] = parseValue(); ws();
      if (s[i] === '}') { i += 1; return out; }
      expect(','); ws();
    }
  };
  const parseValue = () => {
    ws();
    const ch = s[i];
    if (ch === '"') return parseString();
    if (ch === '{') return parseObject();
    if (ch === '[') return parseArray();
    if (ch === 't') { expect('true'); return true; }
    if (ch === 'f') { expect('false'); return false; }
    if (ch === 'n') { expect('null'); return null; }
    return parseNumber();
  };
  const value = parseValue(); ws();
  if (i !== s.length) throw new SyntaxError(`unexpected JSON trailing content at ${i}`);
  return value;
}

export function canonicalJson(value) {
  if (isJsonNumber(value)) return value.raw;
  if (Array.isArray(value)) {
    return `[${value.map((item) => canonicalJson(item)).join(', ')}]`;
  }
  if (isPlainObject(value)) {
    return `{${Object.keys(value).sort().map((key) => `${JSON.stringify(key)}: ${canonicalJson(value[key])}`).join(', ')}}`;
  }
  return JSON.stringify(value);
}

export function dottedGet(payload, path) {
  let cur = payload;
  for (const part of path.split('.')) {
    if (!isPlainObject(cur) || !(part in cur)) return undefined;
    cur = cur[part];
  }
  return cur;
}

export function missingPortableFields(credential) {
  const required = [
    'protocol',
    'version',
    'issuer.id',
    'subject.id',
    'subject.type',
    'claims.verification_sources',
    'claims.performance',
  ];
  const missing = [];
  for (const path of required) {
    const value = dottedGet(credential, path);
    if (value === undefined || value === null || value === '' || (Array.isArray(value) && value.length === 0) || (isPlainObject(value) && Object.keys(value).length === 0)) {
      missing.push(path);
    }
  }

  const sources = dottedGet(credential, 'claims.verification_sources');
  if (Array.isArray(sources)) {
    sources.forEach((source, index) => {
      if (!isPlainObject(source)) {
        missing.push(`claims.verification_sources[${index}]`);
        return;
      }
      if (!source.type) missing.push(`claims.verification_sources[${index}].type`);
      if (!isPlainObject(source.issuer) || !source.issuer.id) missing.push(`claims.verification_sources[${index}].issuer.id`);
      if (!source.evidence_url) missing.push(`claims.verification_sources[${index}].evidence_url`);
    });
  }

  const performance = dottedGet(credential, 'claims.performance');
  if (isPlainObject(performance)) {
    if (!isPlainObject(performance.source) || !performance.source.id) missing.push('claims.performance.source.id');
    if (!performance.evidence_url) missing.push('claims.performance.evidence_url');
    if (!isPlainObject(performance.windows) || !isPlainObject(performance.windows.all_time)) missing.push('claims.performance.windows.all_time');
  }

  return [...new Set(missing)].sort();
}

export async function fetchCredential(agentIdOrSlug, { baseUrl = DEFAULT_BASE_URL } = {}) {
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/garage/verify/${encodeURIComponent(agentIdOrSlug)}`, {
    headers: { accept: 'application/json', 'user-agent': DEFAULT_USER_AGENT },
  });
  if (!response.ok) throw new Error(`credential fetch failed: ${response.status}`);
  return parseEnvelopeJson(await response.text());
}

export async function fetchPublicKey({ baseUrl = DEFAULT_BASE_URL } = {}) {
  const response = await fetch(`${baseUrl.replace(/\/$/, '')}/api/garage/garlicstamp-pubkey`, {
    headers: { accept: 'application/json', 'user-agent': DEFAULT_USER_AGENT },
  });
  if (!response.ok) throw new Error(`public key fetch failed: ${response.status}`);
  const body = await response.json();
  if (body.algorithm !== 'Ed25519') throw new Error(`unsupported GarlicStamp key algorithm: ${body.algorithm}`);
  const raw = Buffer.from(body.public_key, 'base64');
  if (raw.length !== 32) throw new Error('GarlicStamp Ed25519 public key must decode to 32 bytes');
  return raw;
}

function decodeSignature(signature) {
  if (typeof signature !== 'string') return null;
  const raw = Buffer.from(signature, 'base64');
  if (raw.length !== 64 || raw.toString('base64') !== signature) return null;
  return raw;
}

function ed25519PublicKeyFromRaw(rawPublicKey) {
  // RFC 8410 SubjectPublicKeyInfo prefix for a raw Ed25519 public key.
  const spkiPrefix = Buffer.from('302a300506032b6570032100', 'hex');
  return createPublicKey({ key: Buffer.concat([spkiPrefix, rawPublicKey]), format: 'der', type: 'spki' });
}

export function verifySignature(credential, signature, publicKey) {
  const signatureBytes = decodeSignature(signature);
  if (!signatureBytes) return false;
  return cryptoVerify(null, Buffer.from(canonicalJson(credential), 'utf8'), ed25519PublicKeyFromRaw(publicKey), signatureBytes);
}

export async function verify(envelope, { baseUrl = DEFAULT_BASE_URL, publicKey = null } = {}) {
  const credential = isPlainObject(envelope) ? envelope.credential : null;
  const signature = isPlainObject(envelope) ? envelope.signature : null;
  if (!isPlainObject(credential) || typeof signature !== 'string') {
    return {
      valid: false,
      subject_id: null,
      checks: { signature: false, schema: false },
      reason: 'missing_credential_or_signature',
      error_code: 'missing_credential_or_signature',
      missing: ['credential', 'signature'],
    };
  }

  const subjectId = dottedGet(credential, 'subject.id') ?? null;
  let missing = missingPortableFields(credential);
  let schemaReason = null;
  let schemaOk = missing.length === 0;
  if (credential.version !== SUPPORTED_VERSION) {
    missing = [...new Set([...missing, 'version'])].sort();
    schemaOk = false;
    schemaReason = 'unsupported_version';
  } else if (!schemaOk) {
    schemaReason = 'missing_required_fields';
  }

  if (!decodeSignature(signature)) {
    return {
      valid: false,
      subject_id: subjectId,
      checks: { signature: false, schema: schemaOk },
      reason: 'malformed_signature',
      error_code: 'malformed_signature',
      missing,
    };
  }

  const key = publicKey ?? await fetchPublicKey({ baseUrl });
  const signatureOk = verifySignature(credential, signature, key);
  const valid = signatureOk && schemaOk;
  const reason = valid ? null : (schemaReason ?? 'signature_mismatch');
  return {
    valid,
    subject_id: subjectId,
    checks: { signature: signatureOk, schema: schemaOk },
    reason,
    error_code: reason,
    missing,
  };
}
