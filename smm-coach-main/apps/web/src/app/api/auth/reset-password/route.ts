/**
 * POST /api/auth/reset-password
 *
 * Verifies the reset token and updates the user's password.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@smm/db';
import { hashPassword } from '@/lib/auth/password';

const BodySchema = z.object({
  token: z.string().min(1),
  password: z.string().min(8).max(128),
});

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Ma'lumot noto'g'ri" }, { status: 400 });
  }

  const { token, password } = parsed.data;

  // Pre-auth flow → RAW prisma. prismaForTenant('system') scoped the User
  // update to a 'system' tenant and matched zero rows, so resets silently failed.
  const db = prisma;
  const account = await db.account.findFirst({
    where: {
      provider: 'reset-token',
      access_token: token,
    },
    include: { user: true },
  });

  if (!account) {
    return NextResponse.json(
      { error: 'Tiklash kodi noto\'g\'ri yoki muddati tugagan.' },
      { status: 400 },
    );
  }

  // Check expiry
  if (account.expires_at && account.expires_at * 1000 < Date.now()) {
    return NextResponse.json(
      { error: 'Tiklash kodi muddati tugagan.' },
      { status: 400 },
    );
  }

  // Update password
  const hashed = await hashPassword(password);
  await db.user.update({
    where: { id: account.userId },
    data: { passwordHash: hashed },
  });

  // Delete the token so it can't be reused
  await db.account.delete({
    where: {
      provider_providerAccountId: {
        provider: account.provider,
        providerAccountId: account.providerAccountId,
      },
    },
  });

  return NextResponse.json(
    { message: 'Parol muvaffaqiyatli yangilandi.' },
    { status: 200 },
  );
}
