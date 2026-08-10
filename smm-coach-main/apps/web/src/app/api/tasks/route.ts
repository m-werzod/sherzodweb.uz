import { NextResponse } from 'next/server';
import { z } from 'zod';
import { auth } from '@/lib/auth/auth';
import { prismaForTenant } from '@smm/db';

// Lightweight task-creation payload. Most fields are optional — the
// scriptwriter agent fills the rest in via the regenerate-script endpoint.
const BodySchema = z.object({
  title: z.string().min(2).max(120),
  type: z
    .enum(['reel', 'post', 'carousel', 'story', 'live', 'collab', 'action'])
    .default('reel'),
  parentId: z.string().cuid().optional(),
  hook: z.string().max(400).optional(),
  scriptMd: z.string().max(8000).optional(),
  hashtags: z.array(z.string().max(40)).max(30).optional(),
  pillarId: z.string().cuid().optional(),
});

export async function POST(req: Request) {
  const session = await auth();
  if (!session?.user?.tenantId) {
    return NextResponse.json({ error: 'unauthorized' }, { status: 401 });
  }

  const body = await req.json().catch(() => null);
  const parsed = BodySchema.safeParse(body);
  if (!parsed.success) {
    return NextResponse.json(
      { error: 'invalid_body', issues: parsed.error.issues },
      { status: 400 },
    );
  }

  const db = prismaForTenant(session.user.tenantId);

  // The roadmap is implicit — every tenant has at most one active roadmap
  // (older roadmaps go to status='archived' when a new one is generated).
  const roadmap = await db.roadmap.findFirst({
    where: { status: 'active' },
    orderBy: { createdAt: 'desc' },
  });
  if (!roadmap) {
    return NextResponse.json(
      { error: 'no_active_roadmap', message: 'Avval onboarding pipelinedan o\'tib roadmap yarating' },
      { status: 409 },
    );
  }

  // Place new task at the end of its branch so the React Flow tree appends
  // it visually instead of disturbing siblings' positions.
  const lastSibling = await db.contentTask.findFirst({
    where: { roadmapId: roadmap.id, parentId: parsed.data.parentId ?? null },
    orderBy: { orderInBranch: 'desc' },
  });
  const orderInBranch = (lastSibling?.orderInBranch ?? -1) + 1;

  const parent = parsed.data.parentId
    ? await db.contentTask.findFirst({ where: { id: parsed.data.parentId } })
    : null;

  // `tenantId` is overwritten by the prismaForTenant middleware, but Prisma's
  // generated types require it as a scalar (or the `tenant` relation) up front.
  // Pass it explicitly so TypeScript is happy; the middleware re-applies the
  // scoped value either way.
  const task = await db.contentTask.create({
    data: {
      tenantId: session.user.tenantId,
      roadmapId: roadmap.id,
      parentId: parsed.data.parentId ?? null,
      orderInBranch,
      depth: parent ? parent.depth + 1 : 0,
      title: parsed.data.title,
      type: parsed.data.type,
      hook: parsed.data.hook ?? null,
      scriptMd: parsed.data.scriptMd ?? null,
      hashtags: parsed.data.hashtags ?? [],
      pillarId: parsed.data.pillarId ?? null,
      status: 'planned',
      // Sensible defaults so the UI has something to show before the agent
      // refines them. The /regenerate-script endpoint replaces these.
      format: _defaultFormatFor(parsed.data.type),
      publishWindow: _nextSlot(orderInBranch),
    },
  });

  return NextResponse.json({ ok: true, task }, { status: 201 });
}

function _defaultFormatFor(type: string): string {
  switch (type) {
    case 'reel':
      return 'Reel · 9:16 · 60s';
    case 'post':
      return 'Post · 1:1';
    case 'carousel':
      return 'Karusel · 1:1 · 5 slayd';
    case 'story':
      return 'Story · 9:16 · 15s';
    case 'live':
      return 'Live · vertikal';
    case 'collab':
      return 'Kollab · Reel · 9:16';
    default:
      return 'Reel · 9:16 · 30s';
  }
}

function _nextSlot(offset: number): string {
  // Roughly: spread new tasks across the week so the user isn't told to
  // publish three Reels on the same day.
  const days = [
    'Dush, 18:00 — 20:00',
    'Sesh, 19:00 — 21:00',
    'Chor, 12:00 — 14:00',
    'Pay, 20:00 — 22:00',
    'Jum, 19:00 — 21:00',
    'Shan, 11:00 — 13:00',
    'Yak, 11:00 — 13:00',
  ];
  return days[(new Date().getDay() + offset) % days.length]!;
}
