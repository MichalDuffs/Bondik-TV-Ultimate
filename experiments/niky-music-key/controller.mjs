// Isolated experiment. No imports into the production player.
export function createMusicKey({ media, tracks, maxVolume = 0.2 }) {
  if (!media || !['play', 'pause', 'load', 'removeAttribute'].every(
    (name) => typeof media[name] === 'function',
  )) throw new TypeError('A trusted media adapter is required');
  if (!Number.isFinite(maxVolume) || maxVolume < 0 || maxVolume > 0.2) {
    throw new RangeError('Volume ceiling must be between 0 and 0.2');
  }
  if (!Array.isArray(tracks)) throw new TypeError('Approved tracks required');
  const approved = new Map();
  for (const track of tracks) {
    if (!track || typeof track.id !== 'string' || !track.id.trim()
      || approved.has(track.id) || typeof track.url !== 'string'
      || !/^https:\/\//.test(track.url)) throw new TypeError('Invalid approved track');
    approved.set(track.id, track.url);
  }
  let enabled = false;
  let busy = false;
  let generation = 0;
  let selected = null;

  function silence() {
    media.pause();
    media.removeAttribute('src');
    media.load();
    selected = null;
  }

  function stop() {
    enabled = false;
    generation += 1;
    silence();
    return { status: 'stopped', enabled: false };
  }

  async function command(input) {
    if (!input || typeof input !== 'object' || Array.isArray(input)) {
      return { status: 'invalid' };
    }
    if (input.action === 'stop') return stop();
    if (!enabled) return { status: 'disabled' };
    if (busy) return { status: 'busy' };
    if (input.action === 'pause') {
      media.pause();
      return { status: 'paused' };
    }
    if (input.action !== 'play' || !approved.has(input.trackId)) {
      return { status: 'rejected' };
    }
    const ticket = generation;
    busy = true;
    try {
      media.pause();
      media.volume = maxVolume;
      media.src = approved.get(input.trackId);
      selected = input.trackId;
      await media.play();
      if (!enabled || generation !== ticket) {
        silence();
        return { status: 'cancelled' };
      }
      return { status: 'playing', trackId: selected };
    } catch {
      stop();
      return { status: 'error' };
    } finally {
      busy = false;
    }
  }

  // Give only agent to the command consumer; keep host with the human UI.
  // This is an API separation, not a sandbox for arbitrary JavaScript.
  return Object.freeze({
    agent: Object.freeze({ command }),
    host: Object.freeze({
      enable() {
        if (busy) return { status: 'busy' };
        generation += 1;
        enabled = true;
        return { status: 'enabled' };
      },
      stop,
      snapshot: () => Object.freeze({ enabled, busy, selected }),
    }),
  });
}
