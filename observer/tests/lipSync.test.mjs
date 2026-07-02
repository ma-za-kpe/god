import test from 'node:test';
import assert from 'node:assert/strict';

import {
  alphabetLetters,
  buildAlphabetVisemeTrack,
  sampleVisemeTrack,
  scaleVisemeSample,
  visemeForLetter,
} from '../src/lipSync.js';

test('extracts alphabet letters from the spoken line', () => {
  assert.deepEqual(alphabetLetters('A B C, D.'), ['A', 'B', 'C', 'D']);
  assert.deepEqual(alphabetLetters('123'), []);
});

test('maps alphabet letters onto VRM-compatible viseme names', () => {
  assert.equal(visemeForLetter('A'), 'aa');
  assert.equal(visemeForLetter('E'), 'ee');
  assert.equal(visemeForLetter('O'), 'oh');
  assert.equal(visemeForLetter('U'), 'ou');
  assert.equal(visemeForLetter('S'), 'ih');
});

test('builds a monotonic alphabet viseme timeline', () => {
  const track = buildAlphabetVisemeTrack('A B C D E F G H I J K L M N O P Q R S T U V W X Y Z.', 5.2);

  assert.equal(track[0].t, 0);
  assert.equal(track.at(-1).t, 5.2);
  assert.ok(track.length >= 26 * 3);
  for (let index = 1; index < track.length; index += 1) {
    assert.ok(track[index].t >= track[index - 1].t);
  }
});

test('samples and scales viseme frames for live rig control', () => {
  const track = buildAlphabetVisemeTrack('A B C', 3);
  const sample = sampleVisemeTrack(track, 0.42);
  const scaled = scaleVisemeSample(sample, 0.5);

  assert.ok(sample.jaw > 0);
  assert.ok(sample.weights.aa > 0);
  assert.ok(scaled.jaw <= sample.jaw);
  assert.ok(scaled.weights.aa <= sample.weights.aa);
  assert.deepEqual(sampleVisemeTrack(track, 99).weights, { aa: 0, ih: 0, ou: 0, ee: 0, oh: 0 });
});
