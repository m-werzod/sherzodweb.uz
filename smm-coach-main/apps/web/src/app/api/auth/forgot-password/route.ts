/**
 * POST /api/auth/forgot-password
 *
 * Accepts an email, verifies the user exists, and (when SMTP is configured)
 * sends a password-reset link. If SMTP is unavailable, returns a clear
 * message so the UI can guide the user.
 */
import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@smm/db';
import crypto from 'crypto';
import { sendEmailSafe } from '@/lib/email/transport';

const BodySchema = z.object({
  email: z.string().email(),
});

export async function POST(req: Request) {
  const body = await req.json().catch(() => ({}));
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json({ error: "Email noto'g'ri" }, { status: 400 });
  }

  const { email } = parsed.data;

  // Pre-auth flow: use the RAW prisma client (the documented auth/webhook
  // exception). prismaForTenant('system') would scope User to a non-existent
  // 'system' tenant and find NOBODY — silently breaking every reset.
  const db = prisma;
  const user = await db.user.findFirst({ where: { email } });

  // Always return the same message regardless of whether the user exists
  // (prevents email enumeration attacks).
  if (!user) {
    return NextResponse.json(
      { message: "Agar hisob mavjud bo'lsa, tiklash havolasi emailga jo'natildi." },
      { status: 200 },
    );
  }

  // Generate a secure reset token
  const token = crypto.randomBytes(32).toString('hex');
  const expiresAt = new Date(Date.now() + 1000 * 60 * 60); // 1 hour

  // Store token in DB. We reuse the Account table (auth.js) with a custom
  // provider since we don't have a dedicated PasswordResetToken model.
  await db.account.upsert({
    where: {
      provider_providerAccountId: {
        provider: 'reset-token',
        providerAccountId: email,
      },
    },
    update: {
      access_token: token,
      expires_at: Math.floor(expiresAt.getTime() / 1000),
    },
    create: {
      userId: user.id,
      type: 'credentials',
      provider: 'reset-token',
      providerAccountId: email,
      access_token: token,
      expires_at: Math.floor(expiresAt.getTime() / 1000),
    },
  });

  const resetUrl = `${process.env.AUTH_URL ?? 'http://localhost:3000'}/reset-password?token=${token}`;

  // Actually send the reset link (fire-and-forget — never throws, so a flaky
  // relay can't turn into a 500 that leaks "this email exists"). Dev → Mailpit;
  // prod → the configured SMTP relay (Resend).
  await sendEmailSafe({
    to: email,
    subject: 'SMM Coach — parolni tiklash',
    text:
      "Parolingizni tiklash uchun ushbu havolaga o'ting (1 soat amal qiladi):\n" +
      `${resetUrl}\n\nAgar buni siz so'ramagan bo'lsangiz, ushbu xatni e'tiborsiz qoldiring.`,
    html:
      "<p>Parolingizni tiklash uchun quyidagi havolaga o'ting (1 soat amal qiladi):</p>" +
      `<p><a href="${resetUrl}">Parolni tiklash</a></p>` +
      "<p style=\"color:#888\">Agar buni siz so'ramagan bo'lsangiz, ushbu xatni e'tiborsiz qoldiring.</p>",
  });

  return NextResponse.json(
    {
      message: "Agar hisob mavjud bo'lsa, tiklash havolasi emailga jo'natildi.",
      // Dev-only: expose the URL when there's no SMTP so the developer
      // can still test the flow.
      _devResetUrl: process.env.NODE_ENV === 'development' ? resetUrl : undefined,
    },
    { status: 200 },
  );
}
