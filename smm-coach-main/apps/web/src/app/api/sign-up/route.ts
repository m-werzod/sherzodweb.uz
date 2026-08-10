import { NextResponse } from 'next/server';
import { z } from 'zod';
import { prisma } from '@smm/db';
import { hashPassword } from '@/lib/auth/password';
import { sendWelcomeEmail } from '@/lib/email/welcome';
import { ensureFreeSubscription } from '@/lib/payments/subscription';
import { notifyTelegram } from '@/lib/telegram';

const SignUpSchema = z.object({
  email: z.string().email(),
  password: z.string().min(8).max(128),
  name: z.string().max(120).optional(),
  locale: z.enum(['uz', 'ru', 'en']).default('uz'),
});

export async function POST(req: Request) {
  let raw: unknown;
  const contentType = req.headers.get('content-type') ?? '';
  if (contentType.includes('application/json')) {
    raw = await req.json().catch(() => null);
  } else {
    const form = await req.formData();
    raw = Object.fromEntries(form.entries());
  }

  const parsed = SignUpSchema.safeParse(raw);
  if (!parsed.success) {
    if (contentType.includes('application/json')) {
      return NextResponse.json({ error: 'invalid', issues: parsed.error.issues }, { status: 400 });
    }
    // Browser form POST → bounce back to the styled sign-up page with an
    // inline error query param. Avoids dumping raw JSON on the user.
    return NextResponse.redirect(new URL('/sign-up?error=invalid', req.url), { status: 303 });
  }

  const existing = await prisma.user.findUnique({ where: { email: parsed.data.email } });
  if (existing) {
    if (contentType.includes('application/json')) {
      return NextResponse.json({ error: 'email_in_use' }, { status: 409 });
    }
    return NextResponse.redirect(new URL('/sign-up?error=email_in_use', req.url), { status: 303 });
  }

  const passwordHash = await hashPassword(parsed.data.password);

  // Each new B2C user gets their own personal tenant.
  const tenant = await prisma.tenant.create({
    data: { name: parsed.data.email, type: 'personal' },
  });
  await prisma.user.create({
    data: {
      tenantId: tenant.id,
      email: parsed.data.email,
      name: parsed.data.name,
      passwordHash,
      locale: parsed.data.locale,
      role: 'owner',
    },
  });
  // Every tenant starts on a free subscription so plan-gating + the billing UI
  // always have a row to read (paid plans upgrade it via the Payme webhook).
  await ensureFreeSubscription(tenant.id);

  void notifyTelegram(
    `👤 Yangi ro'yxat (email) · ${parsed.data.email} · tenant=${tenant.id} · locale=${parsed.data.locale}` +
      (parsed.data.name ? ` · ism="${parsed.data.name}"` : ''),
  );

  // Fire-and-forget welcome email. Sign-up shouldn't fail if Mailpit is
  // down or the upstream relay is throttled.
  void sendWelcomeEmail({ to: parsed.data.email, name: parsed.data.name });

  if (contentType.includes('application/json')) {
    return NextResponse.json({ ok: true });
  }
  return NextResponse.redirect(new URL('/sign-in', req.url), { status: 303 });
}
