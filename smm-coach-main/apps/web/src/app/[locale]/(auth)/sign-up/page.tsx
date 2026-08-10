/**
 * Sign-up route — renders the chat-style wizard. The wizard collects
 * name, credentials, niche, IG handle, goal, audience and tone, then
 * POSTs sign-up + auto sign-in + /api/onboarding before redirecting to
 * /onboarding/loading where the live agent stream takes over.
 */
import { SignupChat } from '@/components/auth/signup-chat';

export const dynamic = 'force-dynamic';

export default function SignUpPage() {
  return <SignupChat />;
}
