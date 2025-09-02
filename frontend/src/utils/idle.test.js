import { describe, it, expect, vi } from 'vitest';
import { scheduleIdle, cancelIdle } from './idle.js';

describe('idle scheduling', () => {
  it('executes callback after timeout fallback', async () => {
    const fn = vi.fn();
    const id = scheduleIdle(fn, { timeout: 10 });
    expect(id).toBeDefined();
    await new Promise(r => setTimeout(r, 25));
    expect(fn).toHaveBeenCalledOnce();
  });

  it('cancelIdle prevents execution', async () => {
    const fn = vi.fn();
    const id = scheduleIdle(fn, { timeout: 20 });
    cancelIdle(id);
    await new Promise(r => setTimeout(r, 30));
    expect(fn).not.toHaveBeenCalled();
  });
});
