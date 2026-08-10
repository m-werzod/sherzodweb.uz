/**
 * Platform-admin AI provider overview.
 *   GET /api/admin/providers   per-provider: configured, spend, live quota, manual balance
 *   PUT /api/admin/providers   { provider, toppedUpUsd, note?, resetTopupDate? } — set manual balance
 *
 * Most LLM providers expose no balance API, so the admin enters the topped-up
 * amount manually; we subtract our tracked spend since that date.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@smm/db';
import { getAdminSession } from '@/lib/auth/admin';
import { getProviderOverview } from '@/lib/admin/data';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

const PROVIDERS = [
  'anthropic',
  'openai',
  'groq',
  'gemini',
  'voyage',
  'elevenlabs',
  'heygen',
  'runway',
] as const;

export async function GET() {
  const session = await getAdminSession();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });
  const providers = await getProviderOverview();
  return NextResponse.json({ providers });
}

const PutSchema = z.object({
  provider: z.enum(PROVIDERS),
  toppedUpUsd: z.number().min(0).max(1000000),
  note: z.string().max(500).optional(),
  // When true, reset the "spend counts from" date to now (i.e. a fresh top-up).
  resetTopupDate: z.boolean().optional(),
});

export async function PUT(req: Request) {
  const session = await getAdminSession();
  if (!session) return NextResponse.json({ error: 'forbidden' }, { status: 403 });

  const parsed = PutSchema.safeParse(await req.json().catch(() => null));
  if (!parsed.success) {
    return NextResponse.json({ error: 'invalid_body' }, { status: 400 });
  }
  const { provider, toppedUpUsd, note, resetTopupDate } = parsed.data;
  const editor = session.user!.email!;

  const data: {
    toppedUpUsd: number;
    note: string | null;
    updatedBy: string;
    toppedUpAt?: Date;
  } = { toppedUpUsd, note: note ?? null, updatedBy: editor };
  if (resetTopupDate) data.toppedUpAt = new Date();

  await prisma.providerBalance.upsert({
    where: { provider },
    create: { provider, toppedUpUsd, note: note ?? null, updatedBy: editor },
    update: data,
  });

  return NextResponse.json({ ok: true });
}
