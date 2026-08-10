import { redirect } from 'next/navigation';
import { auth } from '@/lib/auth/auth';
import { getAgentsData } from '@/lib/agents/data';
import { AgentsView } from '@/components/traj/agents-view';
import { AgentCatalog } from '@/components/traj/agent-catalog';

export const dynamic = 'force-dynamic';

/** Build the env-gate map server-side so client tiles know which keys are live. */
function envConfigured(name: string): boolean {
  const v = process.env[name];
  return !!v && v.length > 0;
}

export default async function AgentsPage() {
  const session = await auth();
  if (!session?.user?.tenantId) redirect('/sign-in');

  const data = await getAgentsData(session.user.tenantId);
  const envStatus = {
    ANTHROPIC_API_KEY: envConfigured('ANTHROPIC_API_KEY'),
    GEMINI_API_KEY: envConfigured('GEMINI_API_KEY'),
    GROQ_API_KEY: envConfigured('GROQ_API_KEY'),
    OPENAI_API_KEY: envConfigured('OPENAI_API_KEY'),
    VOYAGE_API_KEY: envConfigured('VOYAGE_API_KEY'),
    ELEVENLABS_API_KEY: envConfigured('ELEVENLABS_API_KEY'),
    HEYGEN_API_KEY: envConfigured('HEYGEN_API_KEY'),
    RUNWAY_API_KEY: envConfigured('RUNWAY_API_KEY'),
    IG_SCRAPER_ACCOUNTS: envConfigured('IG_SCRAPER_ACCOUNTS'),
  };

  return (
    <>
      <AgentsView userId={session.user.id} initialMessages={data.messages} stats={data.stats} />
      <AgentCatalog envStatus={envStatus} catalogStats={data.catalogStats} />
    </>
  );
}
