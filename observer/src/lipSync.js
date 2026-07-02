export const VRM_VISEMES = Object.freeze(['aa', 'ih', 'ou', 'ee', 'oh']);

const ALPHABET = 'ABCDEFGHIJKLMNOPQRSTUVWXYZ'.split('');

const LETTER_TO_VISEME = Object.freeze({
  A: 'aa',
  B: 'ee',
  C: 'ee',
  D: 'ee',
  E: 'ee',
  F: 'ih',
  G: 'ee',
  H: 'aa',
  I: 'aa',
  J: 'aa',
  K: 'aa',
  L: 'ih',
  M: 'ih',
  N: 'ih',
  O: 'oh',
  P: 'ee',
  Q: 'ou',
  R: 'ih',
  S: 'ih',
  T: 'ee',
  U: 'ou',
  V: 'ee',
  W: 'ou',
  X: 'ih',
  Y: 'aa',
  Z: 'ee',
});

const JAW_BY_VISEME = Object.freeze({
  aa: 0.95,
  ih: 0.48,
  ou: 0.56,
  ee: 0.42,
  oh: 0.78,
});

function clamp(value, lower, upper) {
  return Math.max(lower, Math.min(upper, value));
}

function blankWeights() {
  return { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 };
}

function smoothstep(value) {
  const x = clamp(value, 0, 1);
  return x * x * (3 - 2 * x);
}

export function alphabetLetters(line) {
  const matches = String(line || '').toUpperCase().match(/[A-Z]/g);
  return matches?.length ? matches : [];
}

export function visemeForLetter(letter) {
  return LETTER_TO_VISEME[String(letter || '').toUpperCase()] || 'aa';
}

export function buildAlphabetVisemeTrack(line, durationSeconds = 0) {
  const letters = alphabetLetters(line);
  const sequence = letters.length ? letters : ALPHABET;
  const safeDuration = Number.isFinite(Number(durationSeconds)) && Number(durationSeconds) > 0
    ? Number(durationSeconds)
    : Math.max(3.8, sequence.length * 0.14);
  const step = safeDuration / sequence.length;
  const frames = [];

  for (let index = 0; index < sequence.length; index += 1) {
    const letter = sequence[index];
    const viseme = visemeForLetter(letter);
    const start = index * step;
    const peak = start + step * 0.42;
    const release = start + step * 0.82;
    const weights = blankWeights();
    weights[viseme] = 1;

    frames.push({ t: start, letter, weights: blankWeights(), jaw: 0.04 });
    frames.push({ t: peak, letter, weights, jaw: JAW_BY_VISEME[viseme] || 0.55 });
    frames.push({ t: release, letter, weights: blankWeights(), jaw: 0.08 });
  }

  frames.push({ t: safeDuration, letter: '', weights: blankWeights(), jaw: 0 });
  return frames.sort((left, right) => left.t - right.t);
}

function interpolateWeights(left, right, alpha) {
  const weights = blankWeights();
  for (const name of VRM_VISEMES) {
    weights[name] = left.weights[name] + (right.weights[name] - left.weights[name]) * alpha;
  }
  return weights;
}

export function sampleVisemeTrack(track, elapsedSeconds) {
  if (!Array.isArray(track) || track.length === 0) {
    return { letter: '', weights: blankWeights(), jaw: 0 };
  }

  const t = Math.max(0, Number(elapsedSeconds) || 0);
  if (t <= track[0].t) return track[0];
  if (t >= track[track.length - 1].t) return track[track.length - 1];

  let lower = 0;
  let upper = track.length - 1;
  while (lower <= upper) {
    const middle = Math.floor((lower + upper) / 2);
    if (track[middle].t <= t) lower = middle + 1;
    else upper = middle - 1;
  }

  const left = track[Math.max(0, upper)];
  const right = track[Math.min(track.length - 1, upper + 1)];
  const span = Math.max(0.001, right.t - left.t);
  const alpha = smoothstep((t - left.t) / span);
  return {
    letter: alpha < 0.5 ? left.letter : right.letter,
    weights: interpolateWeights(left, right, alpha),
    jaw: left.jaw + (right.jaw - left.jaw) * alpha,
  };
}

export function scaleVisemeSample(sample, amplitude = 1) {
  const scale = clamp(Number(amplitude) || 0, 0, 1);
  const weights = blankWeights();
  for (const name of VRM_VISEMES) {
    weights[name] = clamp((sample?.weights?.[name] || 0) * scale, 0, 1);
  }
  return {
    letter: sample?.letter || '',
    weights,
    jaw: clamp((sample?.jaw || 0) * scale, 0, 1),
  };
}
