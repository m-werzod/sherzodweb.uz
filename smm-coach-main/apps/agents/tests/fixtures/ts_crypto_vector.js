// Cross-language golden-vector generator for the web<->agents OAuth-token
// cipher. This is a faithful, standalone mirror of the WEB implementation at
// apps/web/src/lib/security/crypto.ts — it exists so the golden vector baked
// into tests/test_crypto.py is reproducible and auditable without booting the
// Next.js app. If crypto.ts ever changes, update BOTH it and this file, then
// regenerate the vector.
//
//   Wire format (base64url, no padding):  [0x01][12-byte nonce][ct+tag]
//   Key: HKDF-SHA256(IKM=AUTH_SECRET, salt='smm-token-v1', info='oauth-token', 32)
//
//   Regenerate the test vector:
//     AUTH_SECRET=test-secret-do-not-use-in-production-1234567890 \
//       node apps/agents/tests/fixtures/ts_crypto_vector.js enc \
//       "IGAAcrossLangGolden_vector-0123456789ABCdef"
const { createCipheriv, createDecipheriv, hkdfSync, randomBytes } = require('node:crypto');
const VERSION = 0x01, NONCE_LEN = 12;
const SALT = Buffer.from('smm-token-v1', 'utf-8');
const INFO = Buffer.from('oauth-token', 'utf-8');
function masterKey() {
  const secret = process.env.AUTH_SECRET || process.env.NEXTAUTH_SECRET;
  if (!secret) throw new Error('AUTH_SECRET not set');
  return Buffer.from(hkdfSync('sha256', Buffer.from(secret, 'utf-8'), SALT, INFO, 32));
}
function toB64Url(b) { return b.toString('base64').replace(/\+/g, '-').replace(/\//g, '_').replace(/=+$/g, ''); }
function fromB64Url(s) { const p = s + '='.repeat((4 - (s.length % 4)) % 4); return Buffer.from(p.replace(/-/g, '+').replace(/_/g, '/'), 'base64'); }
function enc(pt) {
  const nonce = randomBytes(NONCE_LEN);
  const c = createCipheriv('aes-256-gcm', masterKey(), nonce);
  const ct = Buffer.concat([c.update(pt, 'utf-8'), c.final()]);
  return toB64Url(Buffer.concat([Buffer.from([VERSION]), nonce, ct, c.getAuthTag()]));
}
function dec(b64) {
  const blob = fromB64Url(b64);
  if (blob[0] !== VERSION) throw new Error('bad version ' + blob[0]);
  const nonce = blob.subarray(1, 1 + NONCE_LEN);
  const end = blob.length - 16;
  const d = createDecipheriv('aes-256-gcm', masterKey(), nonce);
  d.setAuthTag(blob.subarray(end));
  return Buffer.concat([d.update(blob.subarray(1 + NONCE_LEN, end)), d.final()]).toString('utf-8');
}
const [, , mode, arg] = process.argv;
if (mode === 'enc') process.stdout.write(enc(arg));
else if (mode === 'dec') process.stdout.write(dec(arg));
else { console.error('usage: node ts_crypto_vector.js enc|dec <arg>'); process.exit(2); }
