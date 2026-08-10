/**
 * clip route — streams the task's source clip to STUDIO (cross-origin), authed
 * by the same short-lived token. Tests token auth, tenant-scoped lookup, the
 * normalized(graded) → studio_source → user_upload preference, and the missing-clip 404.
 */
import { beforeEach, describe, expect, it, vi } from 'vitest';
import type { NextRequest } from 'next/server';

const h = vi.hoisted(() => ({
  findFirst: vi.fn(),
  getObject: vi.fn(),
  verifyStudioToken: vi.fn(),
}));
vi.mock('@smm/db', () => ({ prisma: { taskMedia: { findFirst: h.findFirst } } }));
vi.mock('@/lib/storage/s3', () => ({ getObject: h.getObject }));
vi.mock('@/lib/studio/link', () => ({ verifyStudioToken: h.verifyStudioToken }));

import { GET } from './route';

const req = (token: string) =>
  ({ nextUrl: { searchParams: new URLSearchParams(`token=${token}`) } }) as unknown as NextRequest;
const ctx = (taskId: string) => ({ params: Promise.resolve({ taskId }) });

beforeEach(() => {
  vi.clearAllMocks();
  h.verifyStudioToken.mockReturnValue({ tenantId: 'tn1', taskId: 't1' });
  h.getObject.mockResolvedValue({
    Body: new Uint8Array([1, 2, 3]),
    ContentType: 'video/mp4',
    ContentLength: 3,
  });
});

describe('GET clip', () => {
  it('prefers the render normalized(graded) clip and skips the source lookups', async () => {
    // First lookup is the final_render row; its meta.normalizedKey wins outright.
    h.findFirst.mockResolvedValueOnce({ meta: { normalizedKey: 'tn1/t1/normalized-x.mp4' } });
    const res = await GET(req('tok'), ctx('t1'));
    expect(res.status).toBe(200);
    expect(h.getObject).toHaveBeenCalledWith('tn1/t1/normalized-x.mp4');
    // No studio_source / user_upload query when a normalized clip exists.
    expect(h.findFirst).toHaveBeenCalledTimes(1);
    expect(h.findFirst.mock.calls[0]?.[0]?.where).toMatchObject({ taskId: 't1', tenantId: 'tn1', kind: 'final_render' });
  });

  it('streams the studio_source clip when the render has no normalizedKey', async () => {
    h.findFirst
      .mockResolvedValueOnce({ meta: {} }) // final_render, no normalizedKey
      .mockResolvedValueOnce({ objectKey: 'tn1/t1/studio.mp4', contentType: 'video/mp4' });
    const res = await GET(req('tok'), ctx('t1'));
    expect(res.status).toBe(200);
    expect(res.headers.get('Content-Type')).toBe('video/mp4');
    expect(h.findFirst.mock.calls[1]?.[0]?.where).toMatchObject({ taskId: 't1', tenantId: 'tn1', kind: 'studio_source' });
  });

  it('falls through null meta / no final_render, then studio_source, then user_upload', async () => {
    h.findFirst
      .mockResolvedValueOnce({ meta: null }) // final_render present but null meta
      .mockResolvedValueOnce(null) // no studio_source
      .mockResolvedValueOnce({ objectKey: 'tn1/t1/raw.mov', contentType: 'video/quicktime' });
    const res = await GET(req('tok'), ctx('t1'));
    expect(res.status).toBe(200);
    expect(h.findFirst.mock.calls[2]?.[0]?.where).toMatchObject({ kind: 'user_upload' });
  });

  it('returns 404 no_clip when neither source exists', async () => {
    h.findFirst.mockResolvedValue(null);
    const res = await GET(req('tok'), ctx('t1'));
    expect(res.status).toBe(404);
    expect(await res.text()).toBe('no_clip');
    expect(h.getObject).not.toHaveBeenCalled();
  });

  it('rejects a forged token with 401 before any DB lookup', async () => {
    h.verifyStudioToken.mockReturnValue(null);
    const res = await GET(req('bad'), ctx('t1'));
    expect(res.status).toBe(401);
    expect(h.findFirst).not.toHaveBeenCalled();
  });

  it('rejects a token minted for a different task (401)', async () => {
    h.verifyStudioToken.mockReturnValue({ tenantId: 'tn1', taskId: 'OTHER' });
    const res = await GET(req('tok'), ctx('t1'));
    expect(res.status).toBe(401);
    expect(h.findFirst).not.toHaveBeenCalled();
  });

  it('maps a missing object (NoSuchKey) to 404, not a 500', async () => {
    h.findFirst
      .mockResolvedValueOnce({ meta: {} }) // final_render, no normalizedKey
      .mockResolvedValueOnce({ objectKey: 'gone.mp4', contentType: 'video/mp4' });
    h.getObject.mockRejectedValue(Object.assign(new Error('gone'), { name: 'NoSuchKey' }));
    const res = await GET(req('tok'), ctx('t1'));
    expect(res.status).toBe(404);
  });
});
