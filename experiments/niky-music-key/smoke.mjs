import { createMusicKey } from './controller.mjs';

// Local PCM fixture: no microphone, external media, telemetry or timer.
function tone() {
  const rate = 16000;
  const samples = rate * 2;
  const buffer = new ArrayBuffer(44 + samples * 2);
  const view = new DataView(buffer);
  const text = (offset, value) => [...value].forEach(
    (letter, index) => view.setUint8(offset + index, letter.charCodeAt(0)),
  );
  text(0, 'RIFF'); view.setUint32(4, buffer.byteLength - 8, true);
  text(8, 'WAVE'); text(12, 'fmt '); view.setUint32(16, 16, true);
  view.setUint16(20, 1, true); view.setUint16(22, 1, true);
  view.setUint32(24, rate, true); view.setUint32(28, rate * 2, true);
  view.setUint16(32, 2, true); view.setUint16(34, 16, true);
  text(36, 'data'); view.setUint32(40, samples * 2, true);
  for (let index = 0; index < samples; index += 1) {
    const fade = Math.min(1, index / 160, (samples - index) / 160);
    view.setInt16(44 + index * 2,
      Math.round(3276 * fade * Math.sin(2 * Math.PI * 440 * index / rate)), true);
  }
  return URL.createObjectURL(new Blob([buffer], { type: 'audio/wav' }));
}

const audio = document.createElement('audio');
const localTone = tone();
let mode = 'normal';
let settle = null;
const media = {
  set volume(value) { audio.volume = value; },
  // Only this trusted fixture adapter substitutes the approved virtual URL.
  set src(value) {
    if (value !== 'https://example.invalid/tone.wav') throw new Error('Unknown fixture');
    audio.src = localTone;
  },
  play() {
    const selectedMode = mode;
    mode = 'normal';
    if (selectedMode === 'failure') return Promise.reject(new Error('Simulated'));
    if (selectedMode === 'pending') {
      return new Promise((resolve) => { settle = resolve; });
    }
    return audio.play();
  },
  pause: () => audio.pause(),
  load: () => audio.load(),
  removeAttribute: (name) => audio.removeAttribute(name),
};
const key = createMusicKey({ media, maxVolume: 0.1,
  tracks: [{ id: 'tone', url: 'https://example.invalid/tone.wav' }] });
const state = document.querySelector('#state');
const results = document.querySelector('#results');
function show(label, result) {
  state.textContent = JSON.stringify({ ...key.host.snapshot(),
    audioPaused: audio.paused, hasSource: audio.hasAttribute('src'),
    volume: audio.volume }, null, 2);
  const lines = `${label}: ${JSON.stringify(result)}\n${results.textContent}`;
  results.textContent = lines.split('\n').slice(0, 40).join('\n');
}
function command(action, trackId, nextMode = 'normal') {
  // A rejected/busy command must not arm a later simulation accidentally.
  mode = nextMode;
  const pending = key.agent.command({ action, trackId });
  mode = 'normal';
  show('příkaz', { action, trackId });
  pending.then((result) => show(action, result)).catch(() => {
    key.host.stop(); show(action, { status: 'harness-error' });
  });
}
document.querySelector('#enable').onclick = () => show('člověk: enable', key.host.enable());
document.querySelector('#stop').onclick = () => show('člověk: STOP', key.host.stop());
document.querySelector('#play').onclick = () => command('play', 'tone');
document.querySelector('#pause').onclick = () => command('pause');
document.querySelector('#unknown').onclick = () => command('play', 'not-approved');
document.querySelector('#failure').onclick = () => command('play', 'tone', 'failure');
document.querySelector('#pending').onclick = () => command('play', 'tone', 'pending');
document.querySelector('#settle').onclick = () => {
  if (settle) { const resolve = settle; settle = null; resolve(); }
  show('dokončení simulace', {});
};
for (const event of ['playing', 'pause', 'ended', 'error']) {
  audio.addEventListener(event, () => show(`audio:${event}`, {}));
}
window.addEventListener('pagehide', () => {
  key.host.stop();
  URL.revokeObjectURL(localTone);
});
show('start', { status: 'disabled' });
