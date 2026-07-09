const VISEME_SEQUENCE = ['aa', 'E', 'I', 'O', 'U', 'PP', 'SS', 'TH', 'DD', 'FF', 'kk', 'nn', 'RR', 'CH', 'sil'];

const DIGRAPH_VISEMES = [
  ['th', 'TH'],
  ['ch', 'CH'],
  ['sh', 'CH'],
  ['ph', 'FF'],
  ['ng', 'nn'],
];

const LETTER_VISEMES = {
  a: 'aa',
  e: 'E',
  i: 'I',
  y: 'I',
  o: 'O',
  u: 'U',
  b: 'PP',
  m: 'PP',
  p: 'PP',
  s: 'SS',
  z: 'SS',
  d: 'DD',
  t: 'DD',
  f: 'FF',
  v: 'FF',
  c: 'kk',
  g: 'kk',
  k: 'kk',
  q: 'kk',
  x: 'kk',
  n: 'nn',
  l: 'nn',
  r: 'RR',
  j: 'CH',
};

export function textToVisemes(text) {
  const words = String(text || '').toLowerCase().match(/[a-z']+|[,.!?;:]/g) || [];
  const visemes = [];
  words.forEach((token) => {
    if (/^[,.!?;:]$/.test(token)) {
      visemes.push('sil');
      return;
    }
    let index = 0;
    while (index < token.length) {
      const pair = token.slice(index, index + 2);
      const digraph = DIGRAPH_VISEMES.find(([letters]) => letters === pair);
      if (digraph) {
        visemes.push(digraph[1]);
        index += 2;
        continue;
      }
      const viseme = LETTER_VISEMES[token[index]];
      if (viseme) visemes.push(viseme);
      index += 1;
    }
    visemes.push('sil');
  });
  return visemes.length ? visemes : ['sil'];
}

export function sampleTextViseme({ text, elapsedSeconds = 0, durationSeconds = 1, tempo = 1 }) {
  const visemes = textToVisemes(text);
  const safeDuration = Math.max(0.6, durationSeconds / Math.max(0.5, tempo));
  const progress = Math.max(0, Math.min(0.999, elapsedSeconds / safeDuration));
  const index = Math.min(visemes.length - 1, Math.floor(progress * visemes.length));
  const local = (progress * visemes.length) - index;
  const attack = Math.min(1, local / 0.22);
  const release = Math.min(1, (1 - local) / 0.28);
  const intensity = Math.max(0.08, Math.min(1, Math.min(attack, release)));
  return {
    current: visemes[index] || 'sil',
    next: visemes[index + 1] || 'sil',
    intensity,
    index,
    count: visemes.length,
    all: VISEME_SEQUENCE,
  };
}
