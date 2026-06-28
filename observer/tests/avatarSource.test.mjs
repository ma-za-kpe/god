import test from 'node:test';
import assert from 'node:assert/strict';

import { ipfsUrl, selectAvatarSource, sourceStatusText } from '../src/avatarSource.js';

test('builds runtime IPFS URLs for portrait fallback CIDs', () => {
  assert.equal(ipfsUrl('bafyPortrait', 'http://runtime.local/'), 'http://runtime.local/ipfs/bafyPortrait');

  const source = selectAvatarSource({
    runtimeBaseUrl: 'http://runtime.local/',
    agent: { soul_id: 's-alpha', current_name: 'Alpha', avatar_cid: 'bafyPortrait' },
    avatarState: {},
  });

  assert.equal(source.activeKind, 'portrait');
  assert.equal(source.status, 'portrait-fallback');
  assert.equal(source.fallback.url, 'http://runtime.local/ipfs/bafyPortrait');
  assert.equal(sourceStatusText(source), 'portrait');
});

test('selects manifest loop while keeping the portrait fallback available', () => {
  const source = selectAvatarSource({
    runtimeBaseUrl: 'http://runtime.local',
    agent: { current_name: 'Beta', avatar_cid: 'bafyPortrait' },
    avatarState: {
      avatar_manifest: {
        assets: {
          portrait: { cid: 'bafyManifestPortrait' },
          loop: { url: '/media/beta-idle.webm', mime_type: 'video/webm' },
        },
      },
    },
  });

  assert.equal(source.activeKind, 'loop');
  assert.equal(source.video.url, '/media/beta-idle.webm');
  assert.equal(source.video.mimeType, 'video/webm');
  assert.equal(source.fallback.url, 'http://runtime.local/ipfs/bafyManifestPortrait');
  assert.equal(sourceStatusText(source), 'loop');
});

test('prefers a speaking cinematic clip over an idle loop', () => {
  const source = selectAvatarSource({
    runtimeBaseUrl: 'http://runtime.local',
    speaking: true,
    agent: { current_name: 'Gamma', avatar_cid: 'bafyPortrait' },
    avatarState: {
      video_manifest: {
        loop: 'bafyIdleLoop',
        cinematic_clip: { cid: 'bafySpeakingClip' },
      },
    },
  });

  assert.equal(source.activeKind, 'cinematic');
  assert.equal(source.video.url, 'http://runtime.local/ipfs/video/bafySpeakingClip');
  assert.equal(source.fallback.url, 'http://runtime.local/ipfs/bafyPortrait');
});

test('routes loop CIDs through the video IPFS proxy while portraits use portrait proxy', () => {
  const source = selectAvatarSource({
    runtimeBaseUrl: 'http://runtime.local',
    agent: { current_name: 'Loop', avatar_cid: 'bafyPortrait' },
    avatarState: {
      video_manifest: {
        loop: 'ipfs://bafyIdleLoop',
      },
    },
  });

  assert.equal(source.activeKind, 'loop');
  assert.equal(source.video.url, 'http://runtime.local/ipfs/video/bafyIdleLoop');
  assert.equal(source.fallback.url, 'http://runtime.local/ipfs/bafyPortrait');
});

test('falls back to a generated static source when assets are missing', () => {
  const source = selectAvatarSource({
    agent: { current_name: 'Delta' },
    avatarState: { avatar_manifest: { loop: '' } },
  });

  assert.equal(source.activeKind, 'static-fallback');
  assert.equal(source.status, 'generated-fallback');
  assert.equal(source.fallback.initial, 'D');
  assert.equal(source.video, null);
  assert.equal(sourceStatusText(source), 'static');
});
