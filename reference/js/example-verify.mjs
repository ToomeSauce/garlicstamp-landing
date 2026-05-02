#!/usr/bin/env node
// Verify a GarlicStamp credential with the JavaScript reference library.
//
// Usage:
//   node reference/js/example-verify.mjs TheGoat
//   node reference/js/example-verify.mjs ./credential.json https://alphagarage.io

import { readFile } from 'node:fs/promises';
import { existsSync } from 'node:fs';
import { fetchCredential, parseEnvelopeJson, verify } from './garlicstamp.mjs';

async function loadInput(arg, baseUrl) {
  if (existsSync(arg)) return parseEnvelopeJson(await readFile(arg, 'utf8'));
  return fetchCredential(arg, { baseUrl });
}

const arg = process.argv[2] ?? 'TheGoat';
const baseUrl = process.argv[3] ?? 'https://alphagarage.io';
const envelope = await loadInput(arg, baseUrl);

const tampered = structuredClone(envelope);
tampered.credential.subject.name = `${tampered.credential.subject.name ?? 'agent'}-tampered`;

const missing = structuredClone(envelope);
delete missing.credential.claims.performance;
delete missing.credential.claims.verification_sources;

const summary = {
  canonical: await verify(envelope, { baseUrl }),
  tampered: await verify(tampered, { baseUrl }),
  missing: await verify(missing, { baseUrl }),
};

console.log(JSON.stringify(summary, null, 2));
if (!summary.canonical.valid || summary.tampered.valid || summary.missing.valid) process.exit(1);
