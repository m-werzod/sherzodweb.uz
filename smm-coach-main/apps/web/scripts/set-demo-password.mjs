// One-shot dev helper: resets the demo@smm.uz password to a known value.
// Run: node apps/web/scripts/set-demo-password.mjs
import { PrismaClient } from '../../../packages/db/generated/client/index.js';
import { scrypt as nodeScrypt, randomBytes } from 'node:crypto';
import { promisify } from 'node:util';

const scrypt = promisify(nodeScrypt);
const COST = 2 ** 15;
const MAXMEM = 128 * 1024 * 1024;
const KEY_LEN = 64;
const SALT_LEN = 16;

async function hash(plain) {
  const salt = randomBytes(SALT_LEN);
  const derived = await scrypt(plain, salt, KEY_LEN, { cost: COST, maxmem: MAXMEM });
  return `scrypt$${COST}$${salt.toString('base64')}$${derived.toString('base64')}`;
}

const PLAIN = process.argv[2] || 'demo-2026';
const EMAIL = process.argv[3] || 'demo@smm.uz';

const prisma = new PrismaClient();
const pw = await hash(PLAIN);
const u = await prisma.user.update({
  where: { email: EMAIL },
  data: { passwordHash: pw },
  select: { id: true, email: true },
});
console.log(`Password set for ${u.email} → ${PLAIN}`);
await prisma.$disconnect();
