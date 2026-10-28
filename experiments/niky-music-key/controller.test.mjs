import test from 'node:test';
import assert from 'node:assert/strict';
import { createMusicKey } from './controller.mjs';

function setup(play = async () => {}) {
  const calls = [];
  const media = {
    play: () => { calls.push('play'); return play(); },
    pause: () => calls.push('pause'),
    load: () => calls.push('load'),
    removeAttribute: () => { delete media.src; calls.push('clear'); },
  };
  const tracks = [{ id: 'demo', url: 'https://example.invalid/demo.wav' }];
  return { ...createMusicKey({ media, tracks }), media, calls, tracks };
}

test('default OFF and construction have no media effects', async () => {
  const s = setup();
  assert.equal((await s.agent.command({ action: 'play', trackId: 'demo' })).status, 'disabled');
  assert.deepEqual(s.calls, []);
  assert.equal(s.agent.enable, undefined);
});
test('explicit enable, exact selection, bounded volume and pause', async () => {
  const s = setup();
  s.host.enable();
  assert.deepEqual(await s.agent.command({ action: 'play', trackId: 'demo', volume: 1 }),
    { status: 'playing', trackId: 'demo' });
  assert.equal(s.media.volume, 0.2);
  assert.equal((await s.agent.command({ action: 'pause' })).status, 'paused');
});
test('reject unknown ID and raw URL without playing', async () => {
  const s = setup();
  s.host.enable();
  for (const trackId of ['unknown', 'https://evil.invalid/a']) {
    assert.equal((await s.agent.command({ action: 'play', trackId })).status, 'rejected');
  }
  assert.deepEqual(s.calls, []);
});
test('STOP clears source and revokes subsequent commands', async () => {
  const s = setup();
  s.host.enable();
  await s.agent.command({ action: 'play', trackId: 'demo' });
  s.host.stop();
  assert.equal(s.media.src, undefined);
  assert.equal(s.host.snapshot().enabled, false);
  assert.equal((await s.agent.command({ action: 'play', trackId: 'demo' })).status, 'disabled');
});
test('STOP wins over a pending play; re-enable waits for settlement', async () => {
  let resolve;
  const s = setup(() => new Promise((r) => { resolve = r; }));
  s.host.enable();
  const pending = s.agent.command({ action: 'play', trackId: 'demo' });
  assert.equal((await s.agent.command({ action: 'play', trackId: 'demo' })).status, 'busy');
  s.host.stop();
  assert.equal(s.host.enable().status, 'busy');
  resolve();
  assert.equal((await pending).status, 'cancelled');
  assert.equal(s.media.src, undefined);
  assert.equal(s.host.snapshot().enabled, false);
});
test('play rejection fails closed without disclosing error text or retrying', async () => {
  const s = setup(async () => { throw new Error('private detail'); });
  s.host.enable();
  assert.deepEqual(await s.agent.command({ action: 'play', trackId: 'demo' }), { status: 'error' });
  assert.equal(s.host.snapshot().enabled, false);
  assert.equal(s.calls.filter((x) => x === 'play').length, 1);
});
test('approved catalog is copied, not mutable by the caller afterwards', async () => {
  const s = setup();
  s.tracks[0].url = 'https://other.invalid/a';
  s.host.enable();
  await s.agent.command({ action: 'play', trackId: 'demo' });
  assert.equal(s.media.src, 'https://example.invalid/demo.wav');
});
test('invalid limits and duplicate catalog IDs fail before playback', () => {
  const s = setup();
  for (const maxVolume of [NaN, -1, 0.21, 1]) {
    assert.throws(() => createMusicKey({ media: s.media, tracks: s.tracks, maxVolume }));
  }
  assert.throws(() => createMusicKey({ media: s.media, tracks: [...s.tracks, ...s.tracks] }));
});
test('unknown action and malformed commands never invoke playback', async () => {
  const s = setup();
  s.host.enable();
  for (const input of [null, [], 'play', { action: 'enable' }, { action: 'execute' }]) {
    assert.ok(['invalid', 'rejected'].includes((await s.agent.command(input)).status));
  }
  assert.deepEqual(s.calls, []);
});
test('agent can voluntarily STOP but cannot re-enable', async () => {
  const s = setup();
  s.host.enable();
  assert.equal((await s.agent.command({ action: 'stop' })).status, 'stopped');
  assert.equal((await s.agent.command({ action: 'enable' })).status, 'disabled');
});
