const THREE = await import("https://cdn.jsdelivr.net/npm/three@0.163.0/build/three.module.js");

const controllers = new Map();
let scanTimer = 0;

const EXPR = {
  neutral: { brow: 0.0, blink: 0.0, mouth: 0.08, jaw: 0.02, hue: 0.0, eyeOpen: 1.0 },
  animated: { brow: 0.08, blink: 0.02, mouth: 0.16, jaw: 0.05, hue: 0.04, eyeOpen: 0.96 },
  intense: { brow: -0.14, blink: 0.0, mouth: 0.12, jaw: 0.04, hue: -0.04, eyeOpen: 0.88 },
  angry: { brow: -0.22, blink: 0.0, mouth: 0.10, jaw: 0.03, hue: -0.06, eyeOpen: 0.84 },
  calm: { brow: 0.02, blink: 0.05, mouth: 0.05, jaw: 0.01, hue: 0.0, eyeOpen: 1.0 },
  vulnerable: { brow: 0.12, blink: 0.0, mouth: 0.22, jaw: 0.08, hue: 0.06, eyeOpen: 0.92 },
  flinch: { brow: 0.18, blink: 0.0, mouth: 0.18, jaw: 0.04, hue: 0.03, eyeOpen: 0.78 },
  playful: { brow: 0.06, blink: 0.03, mouth: 0.14, jaw: 0.04, hue: 0.08, eyeOpen: 1.0 },
  attentive: { brow: 0.04, blink: 0.02, mouth: 0.08, jaw: 0.02, hue: 0.0, eyeOpen: 1.0 },
};

function clamp(v, lo, hi) {
  return Math.max(lo, Math.min(hi, v));
}

function numberAttr(value, fallback = NaN) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function hostState(host) {
  return {
    speaking: host.dataset.avatarSpeaking === "1",
    expression: (host.dataset.avatarExpression || "neutral").toLowerCase(),
    pose: (host.dataset.avatarPose || "lead").toLowerCase(),
    motion: (host.dataset.avatarMotion || "live-reactive").toLowerCase(),
    lipSyncSource: (host.dataset.avatarLipSync || "audio").toLowerCase(),
    portraitSrc: host.dataset.avatarSrc || "",
    riggedSrc: host.dataset.riggedAvatarSrc || "",
    life: {
      breathingPhase: numberAttr(host.dataset.avatarBreathing),
      blinkState: host.dataset.avatarBlink === "1",
      headSwayX: numberAttr(host.dataset.avatarHeadSwayX),
      headSwayY: numberAttr(host.dataset.avatarHeadSwayY),
      mouthAmplitude: numberAttr(host.dataset.avatarMouthAmplitude),
      eyeFocusX: numberAttr(host.dataset.avatarEyeFocusX),
      eyeFocusY: numberAttr(host.dataset.avatarEyeFocusY),
    },
  };
}

function createController(host) {
  const canvas = host.querySelector("canvas[data-rigged-avatar-canvas]") || document.createElement("canvas");
  if (!canvas.isConnected) host.appendChild(canvas);
  canvas.className = "rigged-avatar-canvas";

  const renderer = new THREE.WebGLRenderer({ canvas, alpha: true, antialias: true, powerPreference: "high-performance" });
  renderer.setClearColor(0x000000, 0);
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(28, 1, 0.1, 100);
  camera.position.set(0, 0.1, 5.6);

  const ambient = new THREE.AmbientLight(0xffffff, 1.6);
  scene.add(ambient);
  const key = new THREE.DirectionalLight(0xffffff, 2.2);
  key.position.set(2.5, 3.0, 4.0);
  scene.add(key);
  const rim = new THREE.DirectionalLight(0x66ccff, 0.8);
  rim.position.set(-2.5, 0.5, -1.5);
  scene.add(rim);

  const root = new THREE.Group();
  scene.add(root);

  const neck = new THREE.Mesh(
    new THREE.CylinderGeometry(0.28, 0.38, 0.52, 16),
    new THREE.MeshStandardMaterial({ color: 0x8d6b57, roughness: 0.95, metalness: 0.02 })
  );
  neck.position.set(0, -1.0, 0);
  root.add(neck);

  const shoulders = new THREE.Mesh(
    new THREE.CapsuleGeometry(0.82, 0.65, 6, 16),
    new THREE.MeshStandardMaterial({ color: 0x1a2034, roughness: 0.95, metalness: 0.02 })
  );
  shoulders.scale.set(1.38, 0.92, 1.1);
  shoulders.position.set(0, -1.66, -0.02);
  root.add(shoulders);

  const head = new THREE.Group();
  head.position.set(0, 0.15, 0);
  root.add(head);

  const headMesh = new THREE.Mesh(
    new THREE.SphereGeometry(1.15, 32, 32),
    new THREE.MeshStandardMaterial({ color: 0x8e6c5b, roughness: 0.82, metalness: 0.02 })
  );
  headMesh.scale.set(1.0, 1.08, 0.95);
  head.add(headMesh);

  const mask = new THREE.Mesh(
    new THREE.CylinderGeometry(1.02, 1.02, 0.14, 32, 1, true),
    new THREE.MeshStandardMaterial({ color: 0x10131e, transparent: true, opacity: 0.16, roughness: 1.0, metalness: 0.0 })
  );
  mask.rotation.x = Math.PI / 2;
  mask.position.z = 0.72;
  head.add(mask);

  const face = new THREE.Mesh(
    new THREE.PlaneGeometry(1.98, 2.18),
    new THREE.MeshStandardMaterial({
      color: 0xf0d0c0,
      transparent: true,
      opacity: 0.95,
      roughness: 0.96,
      metalness: 0.01,
      side: THREE.DoubleSide,
    })
  );
  face.position.z = 0.78;
  head.add(face);

  const hair = new THREE.Mesh(
    new THREE.SphereGeometry(1.16, 32, 32, 0, Math.PI * 2, 0, Math.PI * 0.6),
    new THREE.MeshStandardMaterial({ color: 0x24304e, roughness: 0.98, metalness: 0.01 })
  );
  hair.scale.set(1.02, 0.78, 1.02);
  hair.position.set(0, 0.33, 0.02);
  head.add(hair);

  const leftEye = new THREE.Mesh(
    new THREE.SphereGeometry(0.13, 16, 16),
    new THREE.MeshStandardMaterial({ color: 0xf2f5ff, roughness: 0.6, metalness: 0.0 })
  );
  leftEye.position.set(-0.35, 0.24, 0.98);
  head.add(leftEye);

  const rightEye = leftEye.clone();
  rightEye.position.x = 0.35;
  head.add(rightEye);

  const leftPupil = new THREE.Mesh(
    new THREE.SphereGeometry(0.055, 12, 12),
    new THREE.MeshStandardMaterial({ color: 0x0c1018, roughness: 0.9 })
  );
  leftPupil.position.set(0, 0, 0.11);
  leftEye.add(leftPupil);
  const rightPupil = leftPupil.clone();
  rightEye.add(rightPupil);

  const browMaterial = new THREE.MeshStandardMaterial({ color: 0x221d1a, roughness: 0.96 });
  const leftBrow = new THREE.Mesh(new THREE.BoxGeometry(0.42, 0.06, 0.06), browMaterial);
  leftBrow.position.set(-0.36, 0.46, 1.0);
  head.add(leftBrow);
  const rightBrow = leftBrow.clone();
  rightBrow.position.x = 0.36;
  head.add(rightBrow);

  const jaw = new THREE.Group();
  jaw.position.set(0, -0.46, 0.92);
  head.add(jaw);

  const mouth = new THREE.Mesh(
    new THREE.BoxGeometry(0.68, 0.1, 0.08),
    new THREE.MeshStandardMaterial({ color: 0x2b1015, roughness: 0.92, metalness: 0.0 })
  );
  mouth.position.set(0, -0.02, 0.02);
  jaw.add(mouth);

  const lowerLip = new THREE.Mesh(
    new THREE.BoxGeometry(0.5, 0.05, 0.05),
    new THREE.MeshStandardMaterial({ color: 0xb75c6a, roughness: 0.94, metalness: 0.0 })
  );
  lowerLip.position.set(0, -0.04, 0.035);
  jaw.add(lowerLip);

  const cheekGlow = new THREE.Mesh(
    new THREE.SphereGeometry(1.1, 24, 24),
    new THREE.MeshStandardMaterial({ color: 0x3b77ff, transparent: true, opacity: 0.04, roughness: 1.0 })
  );
  cheekGlow.scale.set(1.05, 0.85, 1.02);
  cheekGlow.position.set(0, 0.02, 0.64);
  head.add(cheekGlow);

  const loader = new THREE.TextureLoader();
  let loadedPortraitSrc = "";
  let portraitTexture = null;

  function setPortrait(src) {
    if (!src || src === loadedPortraitSrc) return;
    loadedPortraitSrc = src;
    loader.load(
      src,
      (texture) => {
        texture.colorSpace = THREE.SRGBColorSpace;
        texture.anisotropy = 8;
        portraitTexture = texture;
        face.material.map = portraitTexture;
        face.material.color.set(0xffffff);
        face.material.needsUpdate = true;
      },
      undefined,
      () => {
        portraitTexture = null;
        face.material.map = null;
        face.material.color.set(0xf0d0c0);
        face.material.needsUpdate = true;
      }
    );
  }

  let width = 0;
  let height = 0;

  function resize() {
    const rect = host.getBoundingClientRect();
    const w = Math.max(1, Math.floor(rect.width));
    const h = Math.max(1, Math.floor(rect.height));
    if (w !== width || h !== height) {
      width = w;
      height = h;
      renderer.setSize(width, height, false);
      camera.aspect = width / height;
      camera.updateProjectionMatrix();
    }
  }

  const state = hostState(host);
  setPortrait(state.portraitSrc);

  function updateFromHost() {
    const next = hostState(host);
    setPortrait(next.portraitSrc);
    return next;
  }

  function animate(now) {
    resize();
    const t = now / 1000;
    const state = updateFromHost();
    const profile = EXPR[state.expression] || EXPR.neutral;
    const speaking = state.speaking;
    const localBreath = 0.5 + 0.5 * Math.sin(t * 2.1 + (host.dataset.agentId?.length || 0));
    const breathingPhase = Number.isFinite(state.life.breathingPhase)
      ? clamp(state.life.breathingPhase * 0.7 + localBreath * 0.3, 0.0, 1.0)
      : localBreath;
    const lifeMouth = Number.isFinite(state.life.mouthAmplitude)
      ? clamp(state.life.mouthAmplitude, 0.0, 1.0)
      : 0.0;
    const speechWave = speaking
      ? (lifeMouth > 0.0
        ? lifeMouth * (0.86 + 0.14 * Math.abs(Math.sin(t * 12.0)))
        : (0.34 + 0.24 * Math.abs(Math.sin(t * 11.0)) + 0.08 * Math.sin(t * 23.0)))
      : 0.0;
    const mouthOpen = clamp(profile.mouth + speechWave, 0.0, 0.95);
    const blink = 0.5 + 0.5 * Math.sin((t + (host.dataset.agentId?.length || 0)) * 0.62);
    const blinkMask = state.life.blinkState
      ? 1.0
      : clamp(Math.pow(Math.max(0, blink - 0.91) * 18, 2), 0, 1);

    const motion = state.motion === "idle" ? 0.35 : 1.0;
    const poseBias = state.pose === "presenting" ? -0.08 : state.pose === "debate" ? 0.06 : state.pose === "still" ? 0.0 : -0.02;
    const sway = Number.isFinite(state.life.headSwayX)
      ? state.life.headSwayX + Math.sin(t * motion * 1.5) * 0.018
      : Math.sin(t * motion * 1.5) * 0.06;
    const verticalSway = Number.isFinite(state.life.headSwayY)
      ? state.life.headSwayY
      : Math.cos(t * motion * 1.2) * 0.03;
    const bob = (breathingPhase - 0.5) * 0.12 + Math.sin(t * motion * 2.1) * 0.018;

    root.rotation.y = sway + (state.expression === "angry" ? 0.08 : state.expression === "playful" ? -0.05 : 0);
    root.rotation.x = -0.06 + poseBias + verticalSway * 0.28 + Math.sin(t * 0.65) * 0.015;
    root.position.y = bob;

    head.rotation.y = sway * 0.55 + Math.sin(t * 1.1) * 0.025 + (state.speaking ? 0.025 : 0);
    head.rotation.x = profile.brow * 0.35;
    head.rotation.z = state.expression === "vulnerable" ? -0.03 : 0;

    face.material.color.setHSL(0.06 + profile.hue, 0.34, 0.62);
    headMesh.material.color.setHSL(0.06 + profile.hue, 0.28, 0.48);

    leftBrow.position.y = 0.46 + profile.brow * 0.15;
    rightBrow.position.y = 0.46 + profile.brow * 0.15;
    leftBrow.rotation.z = profile.brow * 0.6;
    rightBrow.rotation.z = -profile.brow * 0.6;
    leftBrow.scale.y = 1 - Math.min(0.4, blinkMask * 0.65);
    rightBrow.scale.y = 1 - Math.min(0.4, blinkMask * 0.65);

    leftEye.scale.y = clamp(profile.eyeOpen - blinkMask * 0.85, 0.08, 1);
    rightEye.scale.y = clamp(profile.eyeOpen - blinkMask * 0.85, 0.08, 1);
    leftEye.rotation.z = profile.brow * -0.24;
    rightEye.rotation.z = profile.brow * 0.24;
    const focusX = Number.isFinite(state.life.eyeFocusX) ? state.life.eyeFocusX * 0.18 : Math.sin(t * 0.7) * 0.02;
    const focusY = Number.isFinite(state.life.eyeFocusY) ? state.life.eyeFocusY * 0.14 : Math.cos(t * 0.9) * 0.01;
    leftPupil.position.x = clamp(focusX, -0.04, 0.04);
    rightPupil.position.x = clamp(focusX + Math.sin(t * 0.7 + 0.5) * 0.004, -0.04, 0.04);
    leftPupil.position.y = clamp(focusY, -0.025, 0.025);
    rightPupil.position.y = clamp(focusY, -0.025, 0.025);

    jaw.rotation.x = -0.05 - mouthOpen * 0.42;
    mouth.scale.y = clamp(0.5 + mouthOpen * 4.2, 0.45, 4.8);
    lowerLip.scale.y = clamp(0.7 + mouthOpen * 2.8, 0.6, 3.2);
    mouth.position.y = -0.01 - mouthOpen * 0.18;
    lowerLip.position.y = -0.045 - mouthOpen * 0.16;
    mouth.material.color.set(speaking ? 0x20050b : 0x2b1015);
    lowerLip.material.color.set(speaking ? 0xcd6577 : 0xb75c6a);

    if (state.expression === "flinch") {
      head.rotation.z = Math.sin(t * 18.0) * 0.02;
    }

    renderer.render(scene, camera);
    requestAnimationFrame(animate);
  }

  requestAnimationFrame(animate);

  return {
    host,
    dispose() {
      renderer.dispose();
      controllers.delete(host);
    },
  };
}

function scan() {
  if (!THREE) return;
  const hosts = new Set(document.querySelectorAll(".avatar-orb[data-rigged-avatar-host='1']"));
  for (const host of hosts) {
    if (!controllers.has(host)) {
      controllers.set(host, createController(host));
    }
  }
  for (const [host, controller] of controllers.entries()) {
    if (!document.contains(host)) {
      controller.dispose();
    }
  }
}

function scheduleScan() {
  if (scanTimer) return;
  scanTimer = window.setTimeout(() => {
    scanTimer = 0;
    scan();
  }, 0);
}

window.GodRig = {
  scan: scheduleScan,
  controllers,
};

if (document.readyState === "loading") {
  document.addEventListener("DOMContentLoaded", () => {
    scan();
    scheduleScan();
  });
} else {
  scan();
  scheduleScan();
}

new MutationObserver(() => scheduleScan()).observe(document.documentElement, {
  childList: true,
  subtree: true,
  attributes: true,
  attributeFilter: [
    "data-rigged-avatar-host",
    "data-avatar-src",
    "data-avatar-expression",
    "data-avatar-speaking",
    "data-avatar-motion",
    "data-avatar-pose",
    "data-avatar-breathing",
    "data-avatar-blink",
    "data-avatar-head-sway-x",
    "data-avatar-head-sway-y",
    "data-avatar-mouth-amplitude",
    "data-avatar-eye-focus-x",
    "data-avatar-eye-focus-y",
  ],
});
