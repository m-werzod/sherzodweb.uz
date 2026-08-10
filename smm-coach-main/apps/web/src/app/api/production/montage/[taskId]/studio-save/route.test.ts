/**
 * studio-save route — the money/data path that persists STUDIO's finished
 * montage as the task's final_render. Tests the T5.1 hardening: tenant-scoped
 * destructive delete, atomic delete+create, and an operator alert + clean error
 * on failure (instead of silently losing the user's render).
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';

const h = vi.hoisted(() => ({
  findFirst: vi.fn(),
  findMany: vi.fn(),
  deleteMany: vi.fn(),
  create: vi.fn(),
  putObject: vi.fn(),
  deleteObject: vi.fn(),
  parseStudioToken: vi.fn(),
  notifyTelegram: vi.fn(),
}));

vi.mock('@smm/db', () => ({
  prisma: {
    contentTask: { findFirst: h.findFirst },
    // findMany (prior-render lookup) lives OUTSIDE the tx; deleteMany/create inside.
    taskMedia: { findMany: h.findMany },
    // Execute the callback with a mock tx so we can assert the scoped delete.
    $transaction: async (cb: (tx: unknown) => unknown) =>
      cb({ taskMedia: { deleteMany: h.deleteMany, create: h.create } }),
  },
}));
vi.mock('@/lib/storage/s3', () => ({
  putObject: h.putObject,
  deleteObject: h.deleteObject,
  mediaUrl: (k: string) => `https://cdn/${k}`,
}));
vi.mock('@/lib/studio/link', () => ({
  parseStudioToken: h.parseStudioToken,
  STUDIO_CONTRACT_VERSION: 1,
}));
vi.mock('@/lib/telegram', () => ({ notifyTelegram: h.notifyTelegram }));

import { POST } from './route';

function req(token: string, withFile = true, edl?: unknown): Request {
  const fd = new FormData();
  fd.set('token', token);
  if (withFile) fd.set('file', new Blob([new Uint8Array(64)], { type: 'video/mp4' }), 'out.mp4');
  if (edl !== undefined) fd.set('edl', typeof edl === 'string' ? edl : JSON.stringify(edl));
  return new Request('http://x/api/production/montage/t1/studio-save', { method: 'POST', body: fd });
}

// A known-valid coach EDL (same shape edl-contract.test.ts parses).
const VALID_EDL = {
  task_id: 't1', tenant_id: 'tn1',
  source: { upload_key: 'k', duration_sec: 30 },
  cuts: [{ src_start: 0, src_end: 5 }],
  captions: { windows: [{ words: [{ text: 'Salom', start: 0.5, end: 1 }] }] },
};
const ctx = (taskId: string) => ({ params: Promise.resolve({ taskId }) });

beforeEach(() => {
  vi.clearAllMocks();
  h.parseStudioToken.mockReturnValue({ ok: true, tenantId: 'tn1', taskId: 't1', v: 1 });
  h.findFirst.mockResolvedValue({ id: 't1' });
  h.findMany.mockResolvedValue([]); // no prior render by default
  h.putObject.mockResolvedValue(undefined);
  h.deleteObject.mockResolvedValue(undefined);
  h.create.mockResolvedValue({ id: 'r1' });
});

describe('POST studio-save', () => {
  it('saves the render and scopes the destructive delete to the tenant', async () => {
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(200);
    expect(await res.json()).toEqual({ ok: true, renderId: 'r1' });
    // The deleteMany MUST carry tenantId (convention for raw-prisma destructive ops).
    expect(h.deleteMany).toHaveBeenCalledWith({
      where: { taskId: 't1', tenantId: 'tn1', kind: 'final_render' },
    });
    expect(h.create).toHaveBeenCalledOnce();
    expect(h.notifyTelegram).not.toHaveBeenCalled();
  });

  it('reclaims the prior render object from storage after a successful swap', async () => {
    h.findMany.mockResolvedValue([{ objectKey: 'tn1/t1/studio-OLD.mp4' }]);
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(200);
    // The superseded object is deleted so it doesn't orphan in the bucket.
    expect(h.deleteObject).toHaveBeenCalledWith('tn1/t1/studio-OLD.mp4');
  });

  it('PRESERVES the prior render meta (edl/normalizedKey/coverKey) + marks editSource', async () => {
    // Regression: the swap used to write meta:{editSource:'studio'} only, dropping the AI draft
    // edl, the graded normalizedKey, and the coverKey — so after a STUDIO save /edl 404'd, /clip
    // fell back to the raw clip, and the cover was lost. The new row must MERGE the prior meta.
    h.findMany.mockResolvedValue([
      { objectKey: 'tn1/t1/studio-OLD.mp4', meta: { edl: { version: 1 }, normalizedKey: 'norm-1', coverKey: 'cover-1' } },
    ]);
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(200);
    const created = h.create.mock.calls[0]?.[0] as { data: { meta: Record<string, unknown> } };
    expect(created.data.meta).toMatchObject({
      edl: { version: 1 },
      normalizedKey: 'norm-1',
      coverKey: 'cover-1',
      editSource: 'studio',
    });
  });

  it('no prior meta → meta is just {editSource:studio} (no crash on empty/array meta)', async () => {
    h.findMany.mockResolvedValue([{ objectKey: 'tn1/t1/x.mp4', meta: null }]);
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(200);
    const created = h.create.mock.calls[0]?.[0] as { data: { meta: Record<string, unknown> } };
    expect(created.data.meta).toEqual({ editSource: 'studio' });
  });

  it('EDL write-back: stores a valid posted EDL in meta.edl', async () => {
    const res = await POST(req('tok', true, VALID_EDL), ctx('t1'));
    expect(res.status).toBe(200);
    const created = h.create.mock.calls[0]?.[0] as { data: { meta: Record<string, unknown> } };
    const edl = created.data.meta.edl as { cuts: unknown[] } | undefined;
    expect(edl).toBeTruthy();
    expect(edl!.cuts).toHaveLength(1);
    expect(created.data.meta.editSource).toBe('studio');
  });

  it('EDL write-back: a malformed EDL is ignored — prior meta.edl + normalizedKey kept', async () => {
    h.findMany.mockResolvedValue([
      { objectKey: 'tn1/t1/OLD.mp4', meta: { edl: { version: 1 }, normalizedKey: 'norm-1' } },
    ]);
    const res = await POST(req('tok', true, '{not valid json'), ctx('t1'));
    expect(res.status).toBe(200);
    const created = h.create.mock.calls[0]?.[0] as { data: { meta: Record<string, unknown> } };
    expect(created.data.meta.edl).toEqual({ version: 1 }); // prior draft kept, not clobbered
    expect(created.data.meta.normalizedKey).toBe('norm-1');
  });

  it('alerts + returns save_failed (not a silent loss) when the upload fails', async () => {
    h.putObject.mockRejectedValue(new Error('minio down'));
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(500);
    expect(await res.json()).toEqual({ error: 'save_failed' });
    expect(h.notifyTelegram).toHaveBeenCalledOnce();
    expect(String(h.notifyTelegram.mock.calls[0]?.[0])).toContain('t1');
    // Upload failed → we must NOT have deleted the prior render.
    expect(h.deleteMany).not.toHaveBeenCalled();
  });

  it('alerts + cleans up the orphaned object + returns save_failed when the DB swap fails', async () => {
    h.create.mockRejectedValue(new Error('db boom'));
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(500);
    expect(await res.json()).toEqual({ error: 'save_failed' });
    expect(h.notifyTelegram).toHaveBeenCalledOnce();
    // The uploaded object (putObject ran before the failed tx) must be deleted so
    // it doesn't orphan in the bucket.
    expect(h.deleteObject).toHaveBeenCalledOnce();
  });

  it('rejects a bad/forged token with 401 unauthorized before touching storage', async () => {
    h.parseStudioToken.mockReturnValue({ ok: false, reason: 'invalid' });
    const res = await POST(req('bad'), ctx('t1'));
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: 'unauthorized' });
    expect(h.putObject).not.toHaveBeenCalled();
  });

  it('returns structured token_expired (not a bare 401) for an expired token', async () => {
    h.parseStudioToken.mockReturnValue({ ok: false, reason: 'expired' });
    const res = await POST(req('old'), ctx('t1'));
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: 'token_expired' });
    expect(h.putObject).not.toHaveBeenCalled();
  });

  it('rejects when the token tenant does not own the task (404)', async () => {
    h.findFirst.mockResolvedValue(null);
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(404);
    expect(h.putObject).not.toHaveBeenCalled();
  });

  it('rejects a token with an unrecognized contract version (409, clean code)', async () => {
    h.parseStudioToken.mockReturnValue({ ok: true, tenantId: 'tn1', taskId: 't1', v: 2 });
    const res = await POST(req('tok'), ctx('t1'));
    expect(res.status).toBe(409);
    expect(await res.json()).toEqual({ error: 'contract_mismatch' });
    expect(h.putObject).not.toHaveBeenCalled();
  });

  it('rejects a token minted for a DIFFERENT task (cross-task replay → 401, no write)', async () => {
    // Valid token (same tenant) claims task t1, but it is replayed against t2's save
    // URL. The route MUST reject on claim.taskId !== url taskId BEFORE any storage/DB
    // write — else a token for one task could overwrite another task's render.
    h.parseStudioToken.mockReturnValue({ ok: true, tenantId: 'tn1', taskId: 't1', v: 1 });
    const res = await POST(req('tok'), ctx('t2'));
    expect(res.status).toBe(401);
    expect(await res.json()).toEqual({ error: 'unauthorized' });
    expect(h.putObject).not.toHaveBeenCalled();
    expect(h.deleteMany).not.toHaveBeenCalled();
    expect(h.create).not.toHaveBeenCalled();
  });
});
