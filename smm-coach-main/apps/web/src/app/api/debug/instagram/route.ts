/**
 * GET /api/debug/instagram — Instagram OAuth configuration diagnostic.
 *
 * Returns whether each required env var is set + masked previews (first 4
 * + last 4 chars) so the user can verify Coolify env matches Meta dashboard
 * WITHOUT exposing secrets. Also assembles the exact authorize URL the
 * start route would generate, so the user can sanity-check the redirect URI
 * against Meta's "Valid OAuth Redirect URIs" allowlist.
 *
 * Requires an authenticated session — won't leak config to anonymous users.
 */
import { NextResponse } from 'next/server';
import { auth } from '@/lib/auth/auth';

export const dynamic = 'force-dynamic';
export const runtime = 'nodejs';

function mask(v: string | undefined): string | null {
  if (!v) return null;
  if (v.length <= 8) return '••••';
  return `${v.slice(0, 4)}••••${v.slice(-4)} (${v.length} chars)`;
}

export async function GET() {
  const session = await auth();
  if (!session?.user?.id) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const appId = process.env.INSTAGRAM_APP_ID;
  const appSecret = process.env.INSTAGRAM_APP_SECRET;
  const redirectUri = process.env.INSTAGRAM_REDIRECT_URI;
  const webhookToken = process.env.INSTAGRAM_WEBHOOK_VERIFY_TOKEN;
  const nextAuthUrl = process.env.NEXTAUTH_URL;

  // Reconstruct the URLs Meta sees so the user can copy them into the
  // dashboard fields.
  const baseUrl = nextAuthUrl?.replace(/\/$/, '') ?? null;
  const expectedRedirectUri = baseUrl ? `${baseUrl}/api/auth/callback/instagram` : null;
  const deauthorizeCallbackUrl = baseUrl ? `${baseUrl}/api/meta/deauthorize` : null;
  const dataDeletionCallbackUrl = baseUrl ? `${baseUrl}/api/meta/data-deletion` : null;
  const privacyUrl = baseUrl ? `${baseUrl}/privacy` : null;
  const termsUrl = baseUrl ? `${baseUrl}/terms` : null;
  const dataDeletionInstructionsUrl = baseUrl ? `${baseUrl}/data-deletion` : null;

  const issues: string[] = [];
  if (!appId) issues.push('INSTAGRAM_APP_ID env var not set');
  if (!appSecret) issues.push('INSTAGRAM_APP_SECRET env var not set');
  if (!redirectUri) {
    issues.push('INSTAGRAM_REDIRECT_URI env var not set');
  } else if (expectedRedirectUri && redirectUri !== expectedRedirectUri) {
    issues.push(
      `INSTAGRAM_REDIRECT_URI mismatch: env="${redirectUri}", expected based on NEXTAUTH_URL="${expectedRedirectUri}"`,
    );
  } else if (redirectUri.includes('localhost') && nextAuthUrl?.startsWith('https://')) {
    issues.push(
      `INSTAGRAM_REDIRECT_URI is localhost but NEXTAUTH_URL is HTTPS — production should use the public URL`,
    );
  }

  return NextResponse.json({
    ok: issues.length === 0,
    env: {
      INSTAGRAM_APP_ID: mask(appId),
      INSTAGRAM_APP_SECRET: appSecret ? '••••(set)' : null,
      INSTAGRAM_REDIRECT_URI: redirectUri ?? null,
      INSTAGRAM_WEBHOOK_VERIFY_TOKEN: webhookToken ? '••••(set)' : null,
      NEXTAUTH_URL: nextAuthUrl ?? null,
    },
    expected: {
      // What the user must add to Meta dashboard → Instagram → API setup:
      redirectUriToAddInMetaDashboard: redirectUri ?? expectedRedirectUri,
      deauthorizeCallbackUrl,
      dataDeletionCallbackUrl,
      // App Settings → Basic:
      privacyPolicyUrl: privacyUrl,
      termsOfServiceUrl: termsUrl,
      dataDeletionInstructionsUrl,
      // The scopes our app requests — must be Advanced Access in Meta:
      requiredScopes: [
        'instagram_business_basic',
        'instagram_business_manage_insights',
        'instagram_business_manage_comments',
        'instagram_business_content_publish',
      ],
      // The Meta product the app must have enabled:
      requiredMetaProduct: 'Instagram API with Instagram Login (NOT Basic Display, NOT Graph API)',
    },
    issues,
    // Checklist for the user (full guide: META_APP_REVIEW.md in the repo):
    metaDashboardChecklist: [
      '1. Meta Developer dashboard → My Apps → your app → check it exists',
      '2. App Settings → Basic → copy App ID + App Secret → match Coolify env vars',
      '3. App Settings → Basic → set Privacy Policy URL, Terms URL, Data Deletion callback (see expected.* above)',
      '4. Products → Instagram → API setup with Instagram business login → must be added',
      '5. Instagram → API setup → Valid OAuth Redirect URIs → paste redirectUriToAddInMetaDashboard',
      '6. Instagram → API setup → set Deauthorize + Data Deletion callback URLs (see expected.* above)',
      '7. App Roles → Roles → add yourself as Instagram Tester (if app is not Live)',
      '8. Your IG account → accept tester invitation in instagram.com/accounts/manage_access',
      '9. App Review → request Advanced Access for the scopes above + attach screencast (see META_APP_REVIEW.md)',
    ],
  });
}
