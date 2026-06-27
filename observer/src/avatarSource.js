const CID_FIELDS = ['cid', 'ipfs_cid', 'ipfsCid', 'asset_cid', 'assetCid', 'hash'];
const URL_FIELDS = ['url', 'src', 'href', 'uri', 'path'];

function trimString(value) {
  return typeof value === 'string' ? value.trim() : '';
}

function asObject(value) {
  return value && typeof value === 'object' && !Array.isArray(value) ? value : {};
}

function isUrl(value) {
  return /^(https?:|blob:|data:|\/|\.\/|\.\.\/)/i.test(value);
}

function normalizeRuntimeBaseUrl(runtimeBaseUrl) {
  return trimString(runtimeBaseUrl).replace(/\/+$/, '');
}

export function ipfsUrl(cid, runtimeBaseUrl = '') {
  const value = trimString(cid);
  if (!value) return '';
  if (isUrl(value)) return value;
  const stripped = value.replace(/^ipfs:\/\//i, '');
  const base = normalizeRuntimeBaseUrl(runtimeBaseUrl);
  const encodedPath = stripped
    .split('/')
    .filter(Boolean)
    .map((part) => encodeURIComponent(part))
    .join('/');
  return base ? `${base}/ipfs/${encodedPath}` : `/ipfs/${encodedPath}`;
}

function valueAt(root, path) {
  let cursor = root;
  for (const key of path) {
    if (!cursor || typeof cursor !== 'object') return undefined;
    cursor = cursor[key];
  }
  return cursor;
}

function firstPath(root, paths) {
  for (const path of paths) {
    const value = valueAt(root, path);
    if (value !== undefined && value !== null && value !== '') return { value, path };
  }
  return null;
}

function firstString(root, fields) {
  for (const field of fields) {
    const value = trimString(root?.[field]);
    if (value) return value;
  }
  return '';
}

function firstSourceEntry(value) {
  if (Array.isArray(value)) {
    return value.find((entry) => entry !== undefined && entry !== null && entry !== '') || null;
  }
  const obj = asObject(value);
  if (Array.isArray(obj.sources)) return firstSourceEntry(obj.sources);
  if (obj.sources && typeof obj.sources === 'object') {
    return firstSourceEntry(Object.values(obj.sources));
  }
  return value;
}

function assetFromRef(value, runtimeBaseUrl, kind, label) {
  const source = firstSourceEntry(value);
  const stringValue = trimString(source);
  if (stringValue) {
    return {
      kind,
      label,
      url: isUrl(stringValue) ? stringValue : ipfsUrl(stringValue, runtimeBaseUrl),
      cid: isUrl(stringValue) ? '' : stringValue.replace(/^ipfs:\/\//i, ''),
      mimeType: '',
    };
  }

  const obj = asObject(source);
  const url = firstString(obj, URL_FIELDS);
  if (url) {
    return {
      kind,
      label,
      url,
      cid: '',
      mimeType: trimString(obj.mime_type || obj.mimeType || obj.type),
    };
  }

  const cid = firstString(obj, CID_FIELDS);
  if (cid) {
    return {
      kind,
      label,
      url: ipfsUrl(cid, runtimeBaseUrl),
      cid: cid.replace(/^ipfs:\/\//i, ''),
      mimeType: trimString(obj.mime_type || obj.mimeType || obj.type),
    };
  }

  return null;
}

function collectManifests(agent, avatarState) {
  const containers = [
    ['avatar.avatar_manifest', avatarState?.avatar_manifest],
    ['avatar.video_manifest', avatarState?.video_manifest],
    ['avatar.manifest', avatarState?.manifest],
    ['avatar.plan.avatar_manifest', avatarState?.plan?.avatar_manifest],
    ['avatar.plan.video_manifest', avatarState?.plan?.video_manifest],
    ['avatar.plan.manifest', avatarState?.plan?.manifest],
    ['agent.avatar_manifest', agent?.avatar_manifest],
    ['agent.video_manifest', agent?.video_manifest],
    ['agent.manifest', agent?.manifest],
  ];
  return containers
    .filter(([, manifest]) => manifest && typeof manifest === 'object' && !Array.isArray(manifest))
    .map(([label, manifest]) => ({ label, manifest }));
}

function pickFromManifests(manifests, paths, runtimeBaseUrl, kind) {
  for (const { label, manifest } of manifests) {
    const match = firstPath(manifest, paths);
    if (!match) continue;
    const asset = assetFromRef(match.value, runtimeBaseUrl, kind, `${label}.${match.path.join('.')}`);
    if (asset?.url) return asset;
  }
  return null;
}

function pickDirect(containers, fields, runtimeBaseUrl, kind) {
  for (const [label, container] of containers) {
    const match = firstPath(asObject(container), fields.map((field) => [field]));
    if (!match) continue;
    const asset = assetFromRef(match.value, runtimeBaseUrl, kind, `${label}.${match.path[0]}`);
    if (asset?.url) return asset;
  }
  return null;
}

const PORTRAIT_PATHS = [
  ['portrait'],
  ['static'],
  ['static_fallback'],
  ['fallback'],
  ['avatar'],
  ['assets', 'portrait'],
  ['assets', 'static'],
  ['assets', 'fallback'],
  ['images', 'portrait'],
  ['sources', 'portrait'],
];

const LOOP_PATHS = [
  ['speaking_loop'],
  ['talking_loop'],
  ['loop_speaking'],
  ['assets', 'speaking_loop'],
  ['loops', 'speaking'],
  ['videos', 'speaking'],
  ['sources', 'speaking'],
  ['loop'],
  ['idle_loop'],
  ['listening_loop'],
  ['video_loop'],
  ['assets', 'loop'],
  ['assets', 'idle_loop'],
  ['loops', 'idle'],
  ['loops', 'default'],
  ['videos', 'loop'],
  ['video', 'loop'],
  ['sources', 'loop'],
];

const CINEMATIC_PATHS = [
  ['cinematic_clip'],
  ['cinematic'],
  ['generated_clip'],
  ['clip'],
  ['assets', 'cinematic'],
  ['assets', 'clip'],
  ['videos', 'cinematic'],
  ['video', 'cinematic'],
  ['sources', 'cinematic'],
];

const DIRECT_PORTRAIT_FIELDS = [
  'avatar_cid',
  'avatar_asset',
  'portrait_cid',
  'portrait_url',
  'rigged_avatar_cid',
];

const DIRECT_LOOP_FIELDS = [
  'avatar_loop_url',
  'avatar_loop_cid',
  'video_loop_url',
  'video_loop_cid',
  'loop_url',
  'loop_cid',
  'idle_loop_url',
  'idle_loop_cid',
  'speaking_loop_url',
  'speaking_loop_cid',
];

const DIRECT_CINEMATIC_FIELDS = [
  'cinematic_clip_url',
  'cinematic_clip_cid',
  'cinematic_url',
  'cinematic_cid',
  'generated_clip_url',
  'generated_clip_cid',
];

function generatedFallback(agent) {
  const label = trimString(agent?.current_name || agent?.name || agent?.soul_id || '?');
  return {
    kind: 'static-fallback',
    label: 'generated-fallback',
    url: '',
    cid: '',
    mimeType: '',
    initial: label.slice(0, 1).toUpperCase() || '?',
  };
}

export function selectAvatarSource({
  agent = {},
  avatarState = {},
  runtimeBaseUrl = '',
  speaking = false,
  preferCinematic = true,
} = {}) {
  const manifests = collectManifests(agent, avatarState);
  const directContainers = [
    ['avatar', avatarState],
    ['avatar.plan', avatarState?.plan],
    ['agent', agent],
  ];

  const portrait =
    pickFromManifests(manifests, PORTRAIT_PATHS, runtimeBaseUrl, 'portrait') ||
    pickDirect(directContainers, DIRECT_PORTRAIT_FIELDS, runtimeBaseUrl, 'portrait');

  const cinematic = preferCinematic && speaking
    ? (
      pickFromManifests(manifests, CINEMATIC_PATHS, runtimeBaseUrl, 'cinematic') ||
      pickDirect(directContainers, DIRECT_CINEMATIC_FIELDS, runtimeBaseUrl, 'cinematic')
    )
    : null;

  const loop =
    pickFromManifests(manifests, LOOP_PATHS, runtimeBaseUrl, 'loop') ||
    pickDirect(directContainers, DIRECT_LOOP_FIELDS, runtimeBaseUrl, 'loop');

  const video = cinematic || loop;
  const fallback = portrait || generatedFallback(agent);
  const active = video || fallback;
  const status = video
    ? `${video.kind}-selected`
    : (portrait ? 'portrait-fallback' : 'generated-fallback');

  return {
    active,
    activeKind: active.kind,
    activeUrl: active.url,
    fallback,
    fallbackKind: fallback.kind,
    hasFallback: Boolean(fallback),
    manifestAware: manifests.length > 0,
    portrait,
    status,
    video,
  };
}

export function sourceStatusText(source) {
  if (!source) return 'unknown';
  if (source.video?.kind === 'cinematic') return 'cinematic';
  if (source.video?.kind === 'loop') return 'loop';
  if (source.portrait?.url) return 'portrait';
  return 'static';
}
