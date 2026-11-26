import * as THREE from 'three';
import { DRACOLoader } from 'three/examples/jsm/loaders/DRACOLoader.js';
import { GLTFLoader } from 'three/examples/jsm/loaders/GLTFLoader.js';
import { Reflector } from 'three/examples/jsm/objects/Reflector.js';
import { DynamicScreenRenderer } from './DynamicScreenRenderer';
import { GroundedContactShadows, IndoorReflectionProbes } from './IndoorProbesAndShadows';
import { patchMaterialWithRgbMLightmap } from './LightmapMaterialPatch';
import { MoodSystem, type MoodId } from './MoodSystem';
import { PerformanceGovernor } from './PerformanceGovernor';
import { PostProcessingPipeline } from './PostProcessing';
import { StudioAudioEngine } from './StudioAudioEngine';
import { patchStudioNeonMaterial } from './StudioNeonEngine';
import { CollisionWorld, type ColliderDef } from '../interaction/CollisionWorld';
import { DualCameraController, type CameraPresetId } from '../interaction/DualCameraController';
import { InteractableRegistry } from '../interaction/InteractableRegistry';
import { HudController } from '../ui/HudController';

/**
 * Physically accurate linear-HDR low-iron silvered architectural mirror shader for Three.js Reflector.
 * Avoids Reflector's default sRGB Photoshop `blendOverlay` (which explodes on linear HDR > 1.0) and
 * skips redundant tonemapping/sRGB conversion so pmndrs EffectComposer applies AgX + Bloom uniformly!
 */
const LINEAR_ARCH_MIRROR_SHADER = {
  name: 'LinearArchMirrorShader',
  uniforms: {
    color: { value: null as THREE.Color | null },
    tDiffuse: { value: null as THREE.Texture | null },
    textureMatrix: { value: null as THREE.Matrix4 | null },
  },
  vertexShader: /* glsl */ `
    uniform mat4 textureMatrix;
    varying vec4 vUv;
    #include <common>
    #include <logdepthbuf_pars_vertex>
    void main() {
      vUv = textureMatrix * vec4( position, 1.0 );
      gl_Position = projectionMatrix * modelViewMatrix * vec4( position, 1.0 );
      #include <logdepthbuf_vertex>
    }
  `,
  fragmentShader: /* glsl */ `
    uniform vec3 color;
    uniform sampler2D tDiffuse;
    varying vec4 vUv;
    #include <logdepthbuf_pars_fragment>
    void main() {
      #include <logdepthbuf_fragment>
      vec4 base = texture2DProj( tDiffuse, vUv );
      vec3 refl = max( base.rgb, vec3( 0.0 ) ) * color;
      gl_FragColor = vec4( refl, 1.0 );
    }
  `,
};

/**
 * Attenuates harsh infinitesimal Three.js PointLight directSpecular orbs on non-lightmapped smooth
 * architectural materials (dark marble, induction glass, porcelain, leather, architectural glass)
 * while preserving 100% of directDiffuse warm pools AND 100% of real per-room Indoor PMREM reflections!
 */
function attenuateDirectSpecular(
  mat: THREE.MeshStandardMaterial,
  factor: number,
  keySuffix: string
): void {
  const fStr = factor.toFixed(3);
  mat.customProgramCacheKey = () => `archviz_softspec_${keySuffix}`;
  mat.onBeforeCompile = (shader) => {
    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <lights_fragment_end>',
      /* glsl */ `
      #include <lights_fragment_end>
      reflectedLight.directSpecular *= ${fStr};
      `
    );
  };
  mat.needsUpdate = true;
}

export class GeekLoftApp {
  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene: THREE.Scene;
  private readonly postFx: PostProcessingPipeline;
  private readonly moodSystem: MoodSystem;
  private readonly audioEngine: StudioAudioEngine;
  private readonly indoorProbes: IndoorReflectionProbes;
  private readonly contactShadows: GroundedContactShadows;
  private readonly screens: DynamicScreenRenderer;
  private readonly collision: CollisionWorld;
  private readonly cameraCtrl: DualCameraController;
  private readonly interactables: InteractableRegistry;
  private readonly perf: PerformanceGovernor;
  private readonly hud: HudController;

  private readonly gltfLoader: GLTFLoader;
  private readonly dracoLoader: DRACOLoader;
  private readonly clock = new THREE.Clock();
  private rafId = 0;
  private frameCount = 0;
  /** `?probes=eager` bakes every mood's reflection probes before the first frame (old behaviour). */
  private readonly probesEager = new URLSearchParams(window.location.search).get('probes') === 'eager';
  private probesReadyMarked = false;
  private readonly timings: Partial<Record<'first-frame' | 'first-input' | 'camera-responded' | 'probes-ready', number>> = {};
  private pendingInputCamPos: THREE.Vector3 | null = null;
  private pendingInputCamQuat: THREE.Quaternion | null = null;

  // Time-of-day automatic cycle (Midnight -> Morning -> Noon -> Golden)
  private readonly moodOrder: MoodId[] = ['midnight', 'daylight', 'noon', 'golden'];
  private currentMood: MoodId = 'midnight';
  private moodAutoCycle = true;
  private moodCycleTimer = 0;
  private readonly moodCycleInterval = 12.0;

  // Interactive inspection modes (Photo / Pure Clay Maquette / Lighting-Only GI / Wireframe)
  private photoMode = false;
  private pureClayMode = false;
  private lightingOnlyMode = false;
  private wireframeMode = false;
  private loftRoot: THREE.Object3D | null = null;
  private readonly pureClayMat = new THREE.MeshStandardMaterial({
    color: '#dcdad5',
    roughness: 0.9,
    metalness: 0.0,
    envMapIntensity: 0.14,
  });
  private readonly clayLightGroup = new THREE.Group();
  private readonly pureClaySavedMats = new Map<THREE.Mesh, THREE.Material | THREE.Material[]>();
  private readonly pureClayHiddenMeshes: THREE.Mesh[] = [];
  private readonly inspectableMats = new Map<
    THREE.MeshStandardMaterial,
    { color: THREE.Color; map: THREE.Texture | null; metalness: number; roughness: number }
  >();
  private readonly allSceneMats = new Set<THREE.MeshStandardMaterial>();
  private wovenRugMaps: { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } | null = null;
  private basaltStoneMaps: { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } | null = null;
  private bathReflector: Reflector | null = null;
  private bedReflector: Reflector | null = null;
  private readonly camForward = new THREE.Vector3();
  private readonly camFocusPos = new THREE.Vector3();

  /**
   * Generates a crisp 256px Honed Japanese Kuro-Mikage Dark Basalt stone albedo + micro-bump map
   * for the portal-aligned Entryway Genkan slab & threshold sill (eliminates flat grey plastic look!).
   */
  private getBasaltStoneMaps(): { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } {
    if (this.basaltStoneMaps) return this.basaltStoneMaps;
    const size = 256;
    const colCanvas = document.createElement('canvas');
    colCanvas.width = size;
    colCanvas.height = size;
    const cctx = colCanvas.getContext('2d')!;
    const bumpCanvas = document.createElement('canvas');
    bumpCanvas.width = size;
    bumpCanvas.height = size;
    const bctx = bumpCanvas.getContext('2d')!;
    const cImg = cctx.createImageData(size, size);
    const bImg = bctx.createImageData(size, size);

    let seed = 4242;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };

    for (let y = 0; y < size; y++) {
      const ny = (y / size) * Math.PI * 2;
      for (let x = 0; x < size; x++) {
        const nx = (x / size) * Math.PI * 2;
        // Seamless multi-frequency volcanic basalt cloud + subtle fine mineral grain
        const cloud =
          Math.sin(nx * 2 + Math.cos(ny * 2)) * 0.045 +
          Math.cos(nx * 5 - ny * 3) * 0.028 +
          Math.sin(nx * 9 + ny * 7) * 0.016;
        const r1 = rand();
        const r2 = rand();
        const speckle = r1 > 0.94 ? 0.075 : r1 < 0.07 ? -0.065 : (r2 - 0.5) * 0.042;
        const base = THREE.MathUtils.clamp(0.46 + cloud + speckle, 0.28, 0.68);
        const hVal = THREE.MathUtils.clamp(0.5 + cloud * 3.0 + (r2 - 0.5) * 0.26, 0.0, 1.0);
        const idx = (y * size + x) * 4;
        cImg.data[idx] = Math.round(base * 246);
        cImg.data[idx + 1] = Math.round(base * 249);
        cImg.data[idx + 2] = Math.round(base * 255);
        cImg.data[idx + 3] = 255;
        const bv = Math.round(hVal * 255);
        bImg.data[idx] = bv;
        bImg.data[idx + 1] = bv;
        bImg.data[idx + 2] = bv;
        bImg.data[idx + 3] = 255;
      }
    }
    cctx.putImageData(cImg, 0, 0);
    bctx.putImageData(bImg, 0, 0);

    const map = new THREE.CanvasTexture(colCanvas);
    map.colorSpace = THREE.SRGBColorSpace;
    map.wrapS = THREE.RepeatWrapping;
    map.wrapT = THREE.RepeatWrapping;
    map.anisotropy = 8;

    const bump = new THREE.CanvasTexture(bumpCanvas);
    bump.wrapS = THREE.RepeatWrapping;
    bump.wrapT = THREE.RepeatWrapping;
    bump.anisotropy = 8;

    this.basaltStoneMaps = { map, bump };
    return this.basaltStoneMaps;
  }

  /**
   * Generates a crisp, quiet, seamless 512px woven wool/bouclé textile CanvasTexture + micro-bump map
   * (zero noisy checkerboard, genuine tactile woven threads so solid rugs & sofas never look like flat rubber!).
   */
  private getWovenTextileMaps(): { map: THREE.CanvasTexture; bump: THREE.CanvasTexture } {
    if (this.wovenRugMaps) return this.wovenRugMaps;
    const size = 256;
    const colCanvas = document.createElement('canvas');
    colCanvas.width = size;
    colCanvas.height = size;
    const cctx = colCanvas.getContext('2d')!;
    const bumpCanvas = document.createElement('canvas');
    bumpCanvas.width = size;
    bumpCanvas.height = size;
    const bctx = bumpCanvas.getContext('2d')!;

    const cImg = cctx.createImageData(size, size);
    const bImg = bctx.createImageData(size, size);
    // Deterministic subtle 2x2 basket-weave linen/wool thread relief + gentle organic yarn slub variation
    let seed = 1337;
    const rand = () => {
      seed = (seed * 16807) % 2147483647;
      return (seed - 1) / 2147483646;
    };
    const rowJitter = new Float32Array(size);
    const colJitter = new Float32Array(size);
    for (let i = 0; i < size; i++) {
      rowJitter[i] = (rand() - 0.5) * 0.065;
      colJitter[i] = (rand() - 0.5) * 0.065;
    }
    for (let y = 0; y < size; y++) {
      const ty = (y >> 1) & 1;
      const inRow = y & 1;
      for (let x = 0; x < size; x++) {
        const tx = (x >> 1) & 1;
        const inCol = x & 1;
        const warp = (tx ^ ty) === 0;
        const ridge = warp ? (inCol === 0 ? 1.0 : 0.70) : inRow === 0 ? 0.94 : 0.66;
        const grain = (rand() - 0.5) * 0.048;
        const slub = warp ? colJitter[x] : rowJitter[y];
        const tone = THREE.MathUtils.clamp(0.84 + (ridge - 0.82) * 0.36 + slub + grain, 0.68, 1.0);
        const hVal = THREE.MathUtils.clamp(0.45 + (ridge - 0.66) * 1.65 + grain * 2.0, 0.0, 1.0);
        const idx = (y * size + x) * 4;
        const cv = Math.round(tone * 255);
        const bv = Math.round(hVal * 255);
        cImg.data[idx] = cv;
        cImg.data[idx + 1] = cv;
        cImg.data[idx + 2] = cv;
        cImg.data[idx + 3] = 255;
        bImg.data[idx] = bv;
        bImg.data[idx + 1] = bv;
        bImg.data[idx + 2] = bv;
        bImg.data[idx + 3] = 255;
      }
    }
    cctx.putImageData(cImg, 0, 0);
    bctx.putImageData(bImg, 0, 0);

    const map = new THREE.CanvasTexture(colCanvas);
    map.colorSpace = THREE.SRGBColorSpace;
    map.wrapS = THREE.RepeatWrapping;
    map.wrapT = THREE.RepeatWrapping;
    map.anisotropy = 8;

    const bump = new THREE.CanvasTexture(bumpCanvas);
    bump.wrapS = THREE.RepeatWrapping;
    bump.wrapT = THREE.RepeatWrapping;
    bump.anisotropy = 8;

    this.wovenRugMaps = { map, bump };
    return this.wovenRugMaps;
  }

  constructor(canvas: HTMLCanvasElement) {
    this.renderer = new THREE.WebGLRenderer({
      canvas,
      antialias: false, // Handled cleanly by WebGL2 MSAA inside pmndrs EffectComposer
      powerPreference: 'high-performance',
      stencil: false,
      depth: true,
    });
    this.renderer.outputColorSpace = THREE.SRGBColorSpace;
    this.renderer.toneMapping = THREE.NoToneMapping; // Handled by postprocessing AgX ToneMappingEffect!
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.shadowMap.autoUpdate = false; // Zero ongoing FPS cost: re-renders sun shadow maps ONLY when time-of-day shifts!
    this.renderer.info.autoReset = false; // Accumulate full-frame scene DC/tris cleanly before EffectPass!
    this.renderer.setSize(window.innerWidth, window.innerHeight);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color('#070a12');

    // Dedicated sculptural architectural studio clay rig (active ONLY in Pure Clay mode — crisp form shading & depth!)
    const clayHemi = new THREE.HemisphereLight('#f6f8fb', '#6a707c', 0.68);
    const clayKey = new THREE.DirectionalLight('#fffaf2', 1.25);
    clayKey.position.set(-4.5, 5.8, 4.2);
    const clayFill = new THREE.DirectionalLight('#c8d4e6', 0.32);
    clayFill.position.set(11.0, 3.8, -4.5);
    this.clayLightGroup.add(clayHemi, clayKey, clayFill);
    this.clayLightGroup.visible = false;
    this.scene.add(this.clayLightGroup);

    this.collision = new CollisionWorld();
    this.hud = new HudController({
      onSelectCamera: (id) => this.cameraCtrl.flyToPreset(id),
      onToggleCamPan: () => {
        const next = !this.cameraCtrl.isAutoPanEnabled();
        this.cameraCtrl.setAutoPan(next);
        this.hud.setCamPanActive(next, true);
      },
      onSelectMood: (id) => this.selectMoodManually(id),
      onToggleMoodCycle: () => this.setMoodAutoCycle(!this.moodAutoCycle, true),
      onToggleWalk: () => this.cameraCtrl.toggleWalkMode(),
      onCycleScreen: () => this.screens.cycleMode(),
      onCycleLightScene: () => {
        const res = this.moodSystem.cycleLightScene();
        this.audioEngine.setLightScene(res.mode);
        this.hud.setLightSceneLabel(res.mode);
      },
      onCycleRgb: () => {
        const pal = this.moodSystem.cycleRgbPalette();
        this.hud.setRgbMode(pal.id);
      },
      onToggleMusic: () => {
        const enabled = this.audioEngine.toggleEnabled();
        const st = this.audioEngine.getState();
        this.hud.setMusicState(enabled, st.enabled && st.unlocked, st.mood, true);
      },
      onSelectQuality: (tier) => this.perf.setTier(tier),
      onTogglePhotoMode: () => this.togglePhotoMode(),
      onTogglePureClay: () => this.togglePureClayMode(),
      onToggleLightingOnly: () => this.toggleLightingOnlyMode(),
      onToggleWireframe: () => this.toggleWireframeMode(),
    });

    this.cameraCtrl = new DualCameraController(
      canvas,
      this.collision,
      (mode) => {
        this.hud.setWalkMode(mode === 'walk');
        this.interactables.setEnabled(mode === 'tour');
      },
      (preset) => this.hud.setActiveCamera(preset),
      (active) => this.hud.setCamPanActive(active, false)
    );

    this.postFx = new PostProcessingPipeline(this.renderer, this.scene, this.cameraCtrl.camera);
    this.moodSystem = new MoodSystem(this.renderer, this.scene, this.postFx);
    this.audioEngine = new StudioAudioEngine('midnight', (st) => {
      this.hud.setMusicState(st.enabled, st.enabled && st.unlocked, st.mood, false);
    });
    const initAudio = this.audioEngine.getState();
    this.hud.setMusicState(initAudio.enabled, false, initAudio.mood, false);
    this.indoorProbes = new IndoorReflectionProbes(this.renderer);
    this.contactShadows = new GroundedContactShadows();
    this.screens = new DynamicScreenRenderer();
    this.interactables = new InteractableRegistry(
      this.cameraCtrl.camera,
      canvas,
      document.getElementById('interact-tooltip')!,
      document.getElementById('interact-label')!
    );
    this.perf = new PerformanceGovernor(this.renderer, this.postFx, (snap) => this.hud.updatePerf(snap));

    // Configure local Draco WASM GLTFLoader (Zero third-party CDN latency!)
    this.dracoLoader = new DRACOLoader();
    this.dracoLoader.setDecoderPath('/draco/');
    this.gltfLoader = new GLTFLoader();
    this.gltfLoader.setDRACOLoader(this.dracoLoader);

    window.addEventListener('resize', this.handleResize);
    this.setupDragDropSlotLoader(canvas);
  }

  public async init(): Promise<void> {
    const STARTUP_TOTAL_BYTES = 89_311_109;
    let loftLoadedBytes = 0;
    let loftTotalBytes = 11_993_036;

    this.hud.setLoading(4, this.hud.getMessages().loading.mesh, {
      loaded: 0,
      total: STARTUP_TOTAL_BYTES,
    });

    const [gltf, collidersResp] = await Promise.all([
      this.gltfLoader.loadAsync('/assets/full_loft.glb', (ev) => {
        loftLoadedBytes = ev.loaded;
        if (ev.lengthComputable && ev.total > 0) {
          loftTotalBytes = ev.total;
        }
        const total = Math.max(STARTUP_TOTAL_BYTES, loftLoadedBytes);
        const pct = Math.round(4 + (loftLoadedBytes / total) * 88);
        const filePct = loftTotalBytes > 0 ? Math.min(100, Math.round((loftLoadedBytes / loftTotalBytes) * 100)) : 0;
        this.hud.setLoading(
          pct,
          this.hud.getMessages().loading.loftProgress(filePct),
          { loaded: loftLoadedBytes, total }
        );
      }),
      fetch('/assets/loft_colliders.json').then((r) => (r.ok ? r.json() : []) as Promise<ColliderDef[]>),
    ]);

    this.collision.load(collidersResp);
    this.cameraCtrl.refreshPanBounds();
    const loadMsgs = this.hud.getMessages().loading;
    await this.moodSystem.preloadAssets(
      (pct, msg, byteInfo) => this.hud.setLoading(pct, msg, byteInfo),
      {
        lightmaps: loadMsgs.lightmaps,
        sky: loadMsgs.sky,
        pmrem: loadMsgs.pmrem,
      },
      {
        initialLoaded: Math.max(loftLoadedBytes, loftTotalBytes) + 3_290,
        totalBytes: STARTUP_TOTAL_BYTES,
      }
    );

    this.hud.setLoading(94, this.hud.getMessages().loading.shaders, {
      loaded: STARTUP_TOTAL_BYTES,
      total: STARTUP_TOTAL_BYTES,
    });
    this.integrateLoadedScene(gltf.scene);

    // Expose safe debug hook for automated browser QA & performance verification
    (window as unknown as Record<string, unknown>).__ASTUDIO__ = {
      getLocale: () => this.hud.getLocale(),
      setLocale: (locale: 'zh' | 'en') => this.hud.setLocale(locale, false),
      setMood: (m: MoodId) => {
        this.selectMoodManually(m);
      },
      setMoodAutoCycle: (enabled: boolean) => this.setMoodAutoCycle(enabled, false),
      getTimings: () => ({ probes: this.probesEager ? 'eager' : 'deferred', ...this.timings }),
      setCamera: (c: CameraPresetId, instant = false) =>
        this.cameraCtrl.flyToPreset(c, instant),
      setRawCamera: (pos: [number, number, number], target: [number, number, number], fov = 42) =>
        this.cameraCtrl.setRawCamera(pos, target, fov),
      togglePhotoMode: () => this.togglePhotoMode(),
      togglePureClay: () => this.togglePureClayMode(),
      toggleLightingOnly: () => this.toggleLightingOnlyMode(),
      toggleWireframe: () => this.toggleWireframeMode(),
      replayReveal: () => this.postFx.triggerReveal(),
      cycleScreens: () => this.screens.cycleMode(),
      cycleTvChannel: () => this.screens.cycleTvChannel(),
      cycleLightScene: () => {
        const res = this.moodSystem.cycleLightScene();
        this.audioEngine.setLightScene(res.mode);
        this.hud.setLightSceneLabel(res.mode);
        return res;
      },
      toggleMusic: () => this.audioEngine.toggleEnabled(),
      getAudioState: () => ({
        ...this.audioEngine.getState(),
        reactive: {
          active: this.audioEngine.reactive.active,
          bass: this.audioEngine.reactive.bass,
          mid: this.audioEngine.reactive.mid,
          treble: this.audioEngine.reactive.treble,
          beat: this.audioEngine.reactive.beat,
          breath: this.audioEngine.reactive.breath,
        },
      }),
      toggleScreenBar: () => this.moodSystem.toggleScreenBar(),
      cycleRgb: () => {
        const pal = this.moodSystem.cycleRgbPalette();
        this.hud.setRgbMode(pal.id);
        return pal;
      },
      setRgbMode: (idx: number) => {
        const pal = this.moodSystem.setRgbMode(idx);
        this.hud.setRgbMode(pal.id);
        return pal;
      },
      getAnimatableDevices: () => {
        const list: Array<{ name: string; pos: [number, number, number] }> = [];
        this.loftRoot?.traverse((o) => {
          if (o.userData?.animatableDevice) {
            list.push({
              name: o.name,
              pos: [
                Number(o.position.x.toFixed(3)),
                Number(o.position.y.toFixed(3)),
                Number(o.position.z.toFixed(3)),
              ],
            });
          }
        });
        return list.sort((a, b) => a.name.localeCompare(b.name));
      },
      getStats: () => ({
        drawCalls: this.renderer.info.render.calls,
        triangles: this.renderer.info.render.triangles,
        geometries: this.renderer.info.memory.geometries,
        textures: this.renderer.info.memory.textures,
      }),
      // Deterministic 60 FPS frame-by-frame cinematic video capture director (zero HUD, native 1:1 MSAA!)
      director: {
        enterCapture: (width: number, height: number) => {
          cancelAnimationFrame(this.rafId);
          this.rafId = 0;
          this.cameraCtrl.setAutoPan(false);
          if (!this.photoMode) this.togglePhotoMode();
          // Hide every DOM overlay sibling of #webgl-canvas so zero pills/toasts ever appear in cinema captures
          for (const el of Array.from(document.body.children)) {
            if (el.id !== 'webgl-canvas') {
              (el as HTMLElement).style.display = 'none';
            }
          }
          this.perf.setTier('ultra');
          this.renderer.setPixelRatio(1);
          this.cameraCtrl.resize(width, height);
          this.renderer.setSize(width, height);
          this.postFx.setSize(width, height);
        },
        setCamera: (pos: [number, number, number], target: [number, number, number], fov = 44) => {
          this.cameraCtrl.setRawCamera(pos, target, fov);
        },
        setMacroDof: (enabled: boolean, focusDist = 1.45, bokehScale = 3.4) => {
          this.postFx.setMacroDof(enabled, focusDist, bokehScale);
        },
        setRenderMode: (mode: 'final' | 'clay' | 'lighting' | 'wire') => {
          if (this.wireframeMode) this.toggleWireframeMode();
          if (this.pureClayMode) this.togglePureClayMode();
          if (this.lightingOnlyMode) this.toggleLightingOnlyMode();
          if (mode === 'clay') this.togglePureClayMode();
          else if (mode === 'lighting') this.toggleLightingOnlyMode();
          else if (mode === 'wire') {
            this.togglePureClayMode();
            this.toggleWireframeMode();
          }
        },
        setMoodTransitionDuration: (sec: number) => this.moodSystem.setTransitionDuration(sec),
        snapMood: (m: 'midnight' | 'golden' | 'daylight' | 'noon') => {
          this.hud.setActiveMood(m);
          this.ensureProbesFor(m);
          this.moodSystem.snapMood(m);
        },
        setMood: (m: 'midnight' | 'golden' | 'daylight' | 'noon') => {
          this.hud.setActiveMood(m);
          this.ensureProbesFor(m);
          this.moodSystem.setMood(m);
        },
        setRgbMode: (idx: number) => {
          const pal = this.moodSystem.setRgbMode(idx);
          this.hud.setRgbMode(pal.id);
          return pal;
        },
        setLightScene: (mode: 'bright' | 'cozy' | 'cinema') => {
          this.moodSystem.setLightSceneMode(mode);
          this.hud.setLightSceneLabel(mode);
        },
        step: (dt: number, elapsed: number) => {
          this.cameraCtrl.camera.getWorldDirection(this.camForward);
          this.camFocusPos.copy(this.cameraCtrl.camera.position).addScaledVector(this.camForward, 1.8);
          this.postFx.updateMacroDof(dt);
          this.moodSystem.update(dt, this.camFocusPos);
          this.screens.update(dt, elapsed);
          const allowMirrors = !this.pureClayMode && !this.lightingOnlyMode && !this.wireframeMode;
          const camPos = this.cameraCtrl.camera.position;
          if (this.bathReflector) {
            this.bathReflector.visible =
              allowMirrors && camPos.x > 4.6 && camPos.z < 1.95 && this.camForward.x > -0.25;
          }
          if (this.bedReflector) {
            this.bedReflector.visible =
              allowMirrors && camPos.x > 3.2 && camPos.z > 1.64 && this.camForward.z < 0.25;
          }
          this.renderer.info.reset();
          this.postFx.render(dt);
        },
      },
    };

    this.hud.setLoading(96, this.hud.getMessages().loading.probes);
    // Default: bake only the starting mood's reflections now; the other moods bake after the first frame.
    // `?probes=eager` restores the old all-moods-up-front bake for A/B timing.
    if (this.probesEager) {
      this.indoorProbes.prebakeAllMoods(
        this.scene,
        (m) => this.moodSystem.applyImmediateForBake(m),
        (m) => this.moodSystem.getSkyPmrem(m),
        'midnight'
      );
    } else {
      this.indoorProbes.bakeInitialMood(
        this.scene,
        (m) => this.moodSystem.applyImmediateForBake(m),
        (m) => this.moodSystem.getSkyPmrem(m),
        'midnight'
      );
    }
    this.moodSystem.setOnMoodBlend((from, to, t, envA, envB) => {
      if (!this.pureClayMode && !this.wireframeMode) {
        this.indoorProbes.blendMood(from, to, t, envA, envB);
      }
    }, true);

    // Install TRUE real-time planar mirrors (Spa Bathroom Circular Mirror + Bedroom Full-Length Dressing Mirror)
    // only once every mood's probes are baked, so CubeCameras never recurse into planar Reflectors!
    // In deferred mode stepBackgroundProbeBake() installs them when the last mood finishes.
    if (this.indoorProbes.isFullyBaked()) {
      this.setupRealPlanarMirrors();
      this.markTiming('probes-ready');
    }


    this.hud.setLoading(98, this.hud.getMessages().loading.warmup);
    this.postFx.warmup();

    this.hud.setLoading(100, this.hud.getMessages().loading.ready);
    this.audioEngine.prefetch();
    for (const ev of ['pointerdown', 'wheel', 'keydown', 'touchstart'] as const) {
      window.addEventListener(ev, this.onFirstUserInput, { capture: true, passive: true });
    }
    requestAnimationFrame(() => {
      this.clock.start();
      this.loop();
      this.hud.showStartPrompt(() => {
        this.postFx.triggerReveal();
        this.audioEngine.tryAutoPlay();
      });
    });
  }

  private integrateLoadedScene(root: THREE.Group): void {
    const maxAniso = Math.min(8, this.renderer.capabilities.getMaxAnisotropy());
    const propAniso = Math.min(4, maxAniso);
    const initialLmWest = this.moodSystem.getLightmap('midnight', 'west');
    const initialLmEast = this.moodSystem.getLightmap('midnight', 'east');
    const patchedCloneByBase = new Map<string, THREE.MeshStandardMaterial>();
    const slimmedPhysCache = new Map<THREE.Material, THREE.MeshStandardMaterial>();

    const screenMats: THREE.MeshStandardMaterial[] = [];
    const screenBarMats: THREE.MeshStandardMaterial[] = [];
    const rgbMats: THREE.MeshStandardMaterial[] = [];
    const rgbSecondaryMats: THREE.MeshStandardMaterial[] = [];
    const rgbSoftMats: THREE.MeshStandardMaterial[] = [];
    const overheadEmissives: Array<{ mat: THREE.MeshStandardMaterial; base: number }> = [];
    const accentEmissives: Array<{ mat: THREE.MeshStandardMaterial; base: number }> = [];

    let ultrawideMesh: THREE.Object3D | null = null;
    let verticalMesh: THREE.Object3D | null = null;
    let livingTvMesh: THREE.Object3D | null = null;
    const macbookMeshes: THREE.Object3D[] = [];
    let screenBarObj: THREE.Object3D | null = null;
    let floorLampObj: THREE.Object3D | null = null;
    let kitchenPendantObj: THREE.Object3D | null = null;
    let pcObj: THREE.Object3D | null = null;

    root.traverse((obj) => {
      if (obj.name.startsWith('BK_CreatorsPC')) pcObj = pcObj ?? obj;
      if (obj.name.startsWith('Interact_ScreenBar')) screenBarObj = screenBarObj ?? obj;
      if (obj.name === 'Studio_LampOpalGlobe' || obj.name === 'Studio_LampGlobe') floorLampObj = floorLampObj ?? obj;
      if (obj.name === 'Kit_PendShade_1') kitchenPendantObj = kitchenPendantObj ?? obj;

      if (!(obj instanceof THREE.Mesh)) return;
      const isArrayMat = Array.isArray(obj.material);
      const mats = isArrayMat ? [...obj.material] : [obj.material];
      let replacedAny = false;

      // Upgrade anisotropic filtering & slim heavy MeshPhysicalMaterial -> lightweight MeshStandardMaterial (faster fragment shaders!)
      for (let i = 0; i < mats.length; i++) {
        const rawMat = mats[i];
        if (!(rawMat instanceof THREE.MeshStandardMaterial)) continue;
        let m: THREE.MeshStandardMaterial = rawMat;

        const baseName = m.name.replace(/__(West|East)$/, '');

        // Downgrade ALL redundant MeshPhysicalMaterial (no clearcoat/transmission orbs needed!) to faster MeshStandardMaterial!
        if (m instanceof THREE.MeshPhysicalMaterial) {
          let std = slimmedPhysCache.get(m);
          if (!std) {
            std = new THREE.MeshStandardMaterial({
              name: m.name,
              color: m.color,
              map: m.map,
              normalMap: m.normalMap,
              normalScale: m.normalScale,
              roughness: Math.max(0.06, m.roughness),
              roughnessMap: m.roughnessMap,
              metalness: m.metalness,
              metalnessMap: m.metalnessMap,
              emissive: m.emissive,
              emissiveMap: m.emissiveMap,
              emissiveIntensity: m.emissiveIntensity,
              aoMap: m.aoMap,
              aoMapIntensity: m.aoMapIntensity,
              bumpMap: m.bumpMap,
              bumpScale: m.bumpScale,
              alphaMap: m.alphaMap,
              alphaTest: m.alphaTest,
              transparent: m.transparent,
              opacity: m.opacity,
              side: m.side,
              vertexColors: m.vertexColors,
              envMapIntensity: m.envMapIntensity,
            });
            std.userData = { ...m.userData };
            slimmedPhysCache.set(m, std);
          }
          m = std;
          mats[i] = std;
          replacedAny = true;
        }

        const isArchSurface = baseName.startsWith('Arch_') || baseName.includes('Rug');
        const targetAniso = isArchSurface ? maxAniso : propAniso;
        if (m.map) m.map.anisotropy = targetAniso;
        if (m.normalMap) m.normalMap.anisotropy = targetAniso;

        // Guard GGX roughness=0 / KHR_materials_transmission / KHR_materials_anisotropy NaN hazards in MSAA HalfFloat Bloom!
        m.roughness = Math.max(0.06, m.roughness);
        if (m instanceof THREE.MeshPhysicalMaterial) {
          m.transmission = 0;
          m.anisotropy = 0;
          m.clearcoatRoughness = Math.max(0.06, m.clearcoatRoughness);
        }

        // 1. Live Interactive Anti-Glare Nano-Texture OLED Screens! (ZERO point-light spotlight glare blob!)
        if (baseName === 'Screen_Ultrawide' || obj.name === 'Monitor_Ultrawide38_Screen') {
          m.map = null;
          m.color.set('#020305');
          m.emissive.set('#ffffff');
          m.emissiveMap = this.screens.ultrawideTexture;
          m.emissiveIntensity = 1.50;
          m.roughness = 0.94;
          m.metalness = 0.0;
          m.envMapIntensity = 0.04;
          m.needsUpdate = true;
          screenMats.push(m);
          ultrawideMesh = obj;
          continue;
        }
        if (baseName === 'Screen_LivingTV' || obj.name === 'Liv_OLED77_Screen') {
          m.map = null;
          m.color.set('#020305');
          m.emissive.set('#ffffff');
          m.emissiveMap = this.screens.livingTvTexture;
          m.emissiveIntensity = 1.48;
          m.roughness = 0.92;
          m.metalness = 0.0;
          m.envMapIntensity = 0.05;
          m.needsUpdate = true;
          screenMats.push(m);
          livingTvMesh = obj;
          continue;
        }
        if (baseName === 'Screen_MacBook') {
          m.map = null;
          m.color.set('#020305');
          m.emissive.set('#ffffff');
          m.emissiveMap = this.screens.livingTvTexture;
          m.emissiveIntensity = 1.40;
          m.roughness = 0.92;
          m.metalness = 0.0;
          m.envMapIntensity = 0.05;
          m.needsUpdate = true;
          screenMats.push(m);
          macbookMeshes.push(obj);
          continue;
        }
        if (baseName === 'Screen_Vertical' || obj.name === 'Monitor_Vertical27_Screen') {
          m.map = null;
          m.color.set('#020305');
          m.emissive.set('#ffffff');
          m.emissiveMap = this.screens.verticalTexture;
          m.emissiveIntensity = 1.50;
          m.roughness = 0.94;
          m.metalness = 0.0;
          m.envMapIntensity = 0.04;
          m.needsUpdate = true;
          screenMats.push(m);
          verticalMesh = obj;
          continue;
        }
        if (baseName === 'Screen_StreamDeck' || obj.name === 'SD_KeysPanel') {
          m.map = null;
          m.color.set('#080a0f');
          m.emissive.set('#ffffff');
          m.emissiveMap = this.screens.streamDeckTexture;
          m.emissiveIntensity = 2.0;
          m.roughness = 0.22;
          m.needsUpdate = true;
          screenMats.push(m);
          continue;
        }

        // 2. Clean Architectural, Fluted, Frosted Door, Shower, Wardrobe & Smoked PC Glass (zero costly transmission pass!)
        if (
          baseName === 'Arch_WindowGlass' ||
          obj.name === 'Arch_LoftWin_Glass' ||
          obj.name === 'Arch_LivWin_Glass' ||
          baseName === 'Arch_FlutedGlass' ||
          baseName === 'Arch_FrostedBathDoor' ||
          baseName === 'Arch_ShowerGlass' ||
          baseName === 'Furn_SmokedGlass' ||
          baseName === 'HW_PCGlassTinted' ||
          baseName === 'Acrül' ||
          baseName === 'Material.069' ||
          baseName === 'dust cover' ||
          baseName === 'Glass.001' ||
          baseName === 'Glass.003'
        ) {
          const isWin = baseName === 'Arch_WindowGlass' || obj.name === 'Arch_LoftWin_Glass' || obj.name === 'Arch_LivWin_Glass';
          const isFluted = baseName === 'Arch_FlutedGlass';
          const isFrosted = baseName === 'Arch_FrostedBathDoor';
          const isShower = baseName === 'Arch_ShowerGlass';
          const isWardrobe = baseName === 'Furn_SmokedGlass';
          const isPc = baseName === 'HW_PCGlassTinted';
          m.transparent = true;
          m.opacity = isWin ? 0.03 : isFrosted ? 0.56 : isFluted ? 0.36 : isWardrobe ? 0.28 : isShower ? 0.16 : isPc ? 0.22 : 0.16;
          m.color.set(isWin || isShower ? '#dceaff' : isFrosted || isFluted ? '#cdd5dc' : '#0b1018');
          m.roughness = isFrosted ? 0.48 : isFluted ? 0.34 : isWardrobe ? 0.14 : 0.08;
          m.metalness = isPc || isWardrobe ? 0.10 : 0.04;
          if (isWardrobe) m.envMapIntensity = 0.22;
          m.depthWrite = false;
          // Suppress pinpoint circular PointLight specular spots on shower glass, fluted partitions, & smoked glass!
          attenuateDirectSpecular(m, 0.10, 'archglass');
          continue;
        }

        // 2a. Real Indoor Spa-Probe Vanity Mirror (now reflects authentic warm indoor Spa Bath limestone & tub!)
        if (baseName === 'Arch_MirrorSilver') {
          m.color.set('#d4d8dc');
          m.roughness = 0.06;
          m.metalness = 0.94;
          m.envMapIntensity = 0.95;
          m.needsUpdate = true;
          continue;
        }
        if (baseName === 'Emit_CandleFlame') {
          m.emissive.set('#ffaa38');
          m.emissiveIntensity = 3.6;
          m.needsUpdate = true;
          continue;
        }
        if (baseName === 'Emit_OpalFloorLamp') {
          m.color.set('#fff0d8');
          m.emissive.set('#ffcf8a');
          m.emissiveIntensity = 2.15;
          m.roughness = 0.36;
          m.metalness = 0.0;
          m.needsUpdate = true;
          accentEmissives.push({ mat: m, base: 2.15 });
          continue;
        }
        if (baseName === 'Emit_KitchenPendantBulb') {
          m.color.set('#fff3df');
          m.emissive.set('#ffd28c');
          m.emissiveIntensity = 3.8;
          m.roughness = 0.25;
          m.metalness = 0.0;
          m.needsUpdate = true;
          overheadEmissives.push({ mat: m, base: 3.8 });
          continue;
        }
        if (baseName === 'Emit_KitchenPendantInner') {
          // Uniform warm brushed-brass inner glow across all 3 kitchen island pendants (zero bright/dark mismatch!)
          m.color.set('#ffcf86');
          m.emissive.set('#ffc268');
          m.emissiveIntensity = 1.40;
          m.roughness = 0.42;
          m.metalness = 0.14;
          m.needsUpdate = true;
          overheadEmissives.push({ mat: m, base: 1.40 });
          continue;
        }
        if (baseName === 'HW_MicFoam') {
          // Authentic porous matte deep-charcoal Shure A7WS acoustic windscreen foam (zero shiny muddy plastic!)
          const woven = this.getWovenTextileMaps();
          const foamBmp = woven.bump.clone();
          foamBmp.repeat.set(36, 36);
          foamBmp.needsUpdate = true;
          m.map = null;
          m.normalMap = null;
          m.roughnessMap = null;
          m.color.set('#17181c');
          m.bumpMap = foamBmp;
          m.bumpScale = 0.0075;
          m.roughness = 0.98;
          m.metalness = 0.0;
          m.envMapIntensity = 0.03;
          m.needsUpdate = true;
          continue;
        }
        if (baseName === 'Furn_SpaTubStoneResin' || baseName === 'Porcelain_white') {
          // Honed matte-satin architectural stone-resin tub & ceramic (ZERO harsh circular PointLight dot!)
          m.color.set('#e2dfd8');
          m.roughness = baseName === 'Porcelain_white' ? 0.36 : 0.38;
          m.metalness = 0.0;
          m.envMapIntensity = 0.20;
          attenuateDirectSpecular(m, 0.16, 'ceramic');
          continue;
        }
        if (baseName === 'HW_InductionGlass') {
          // Black Schott Ceran induction cooktop & smart-lock glass (real room PMREM reflections, ZERO fake PointLight orbs!)
          m.roughness = 0.16;
          m.metalness = 0.08;
          m.envMapIntensity = 0.38;
          attenuateDirectSpecular(m, 0.04, 'induct');
          continue;
        }
        if (baseName === 'Furn_GenkanBasaltMatte') {
          // Honed Japanese Kuro-Mikage dark basalt entryway stone (tactile natural mineral grain, zero flat plastic look!)
          const basalt = this.getBasaltStoneMaps();
          const bCol = basalt.map.clone();
          const bBmp = basalt.bump.clone();
          bCol.repeat.set(3.2, 2.2);
          bBmp.repeat.set(3.2, 2.2);
          bCol.needsUpdate = true;
          bBmp.needsUpdate = true;
          m.map = bCol;
          m.bumpMap = bBmp;
          m.bumpScale = 0.0045;
          m.color.set('#5e626a');
          m.roughness = 0.78;
          m.metalness = 0.02;
          m.envMapIntensity = 0.14;
          attenuateDirectSpecular(m, 0.14, 'basalt');
          continue;
        }
        if (baseName === 'Furn_EntryArmoredMatte') {
          // Oikos/Rimadesio satin-matte architectural dark-graphite armored steel entry door
          const basalt = this.getBasaltStoneMaps();
          const dBmp = basalt.bump.clone();
          dBmp.repeat.set(6, 12);
          dBmp.needsUpdate = true;
          m.bumpMap = dBmp;
          m.bumpScale = 0.0014;
          m.color.set('#26282d');
          m.roughness = 0.68;
          m.metalness = 0.16;
          m.envMapIntensity = 0.15;
          attenuateDirectSpecular(m, 0.18, 'armored');
          continue;
        }
        if (baseName === 'Emit_EntryCeilingLight') {
          // Dedicated warm 2700K recessed entryway welcome ceiling downlight diffuser (dims cleanly with K!)
          m.color.set('#fff2dc');
          m.emissive.set('#ffd492');
          m.emissiveIntensity = 3.6;
          m.roughness = 0.24;
          m.metalness = 0.0;
          m.needsUpdate = true;
          overheadEmissives.push({ mat: m, base: 3.6 });
          continue;
        }
        if (baseName === 'Emit_PhoneStandby' || baseName === 'Emit_OP1Display') {
          m.emissive.set(baseName === 'Emit_OP1Display' ? '#52d6ff' : '#ff5230');
          m.emissiveIntensity = baseName === 'Emit_OP1Display' ? 1.45 : 0.75;
          m.needsUpdate = true;
          continue;
        }
        if (
          baseName === 'Furn_LinenTaupe' ||
          baseName === 'Furn_BedDuvetGreige' ||
          baseName === 'Furn_BedPillowCharcoal' ||
          baseName === 'Furn_BedThrowCamel' ||
          baseName === 'Prop_SpaTowelStone'
        ) {
          m.roughness = 0.94;
          m.metalness = 0.0;
          m.envMapIntensity = 0.06;
          if (m instanceof THREE.MeshPhysicalMaterial) m.clearcoat = 0;
          m.needsUpdate = true;
        }

        // 2b. Harmonize glTF PBR surfaces with Cycles offline look across BOTH West & East atlases!
        if (baseName.includes('main controler') || baseName === 'Fabric' || baseName === 'Plane.001_Baked.001') {
          m.side = THREE.DoubleSide;
          m.needsUpdate = true;
        } else if (baseName === 'HM_Sayl_Material') {
          m.map = null;
          m.color.set('#181b21');
          m.roughness = 0.56;
          m.metalness = 0.08;
          m.needsUpdate = true;
        } else if (baseName === 'Furn_AmericanWalnut' || baseName === 'Arch_WalnutSlats') {
          // Hand-rubbed satin-matte Japanese oiled walnut (silky wood grain, ZERO plastic specular glare hotspots!)
          m.color.set('#ffffff');
          m.roughness = baseName === 'Arch_WalnutSlats' ? 0.66 : 0.72;
          m.metalness = 0.0;
          m.envMapIntensity = 0.14;
          if (m instanceof THREE.MeshPhysicalMaterial) m.clearcoat = 0;
          m.needsUpdate = true;
        } else if (baseName === 'Arch_Wall_StudioDarkConcrete') {
          // Deep architectural dark charcoal concrete behind Studio monitors & honeycomb neon wall!
          m.color.set('#2c303a');
          m.roughness = 0.88;
          m.metalness = 0.0;
          m.envMapIntensity = 0.09;
          if (m.normalScale) m.normalScale.set(0.38, 0.38);
          m.needsUpdate = true;
        } else if (baseName === 'HW_HexAcousticCore') {
          m.color.set('#14171e');
          m.roughness = 0.82;
          m.metalness = 0.04;
          m.envMapIntensity = 0.14;
          m.needsUpdate = true;
        } else if (
          baseName === 'Arch_Wall_RawConcrete' ||
          baseName === 'Arch_Wall_Microcement' ||
          baseName === 'Arch_Wall_WarmPlaster' ||
          baseName === 'Arch_Ceiling_Concrete'
        ) {
          m.color.set('#d8dad6');
          m.roughness = 0.88;
          m.metalness = 0.0;
          m.envMapIntensity = 0.08;
          if (m.normalScale) m.normalScale.set(0.32, 0.32);
          m.needsUpdate = true;
        } else if (baseName === 'Arch_Floor_Herringbone') {
          // Hand-oiled satin-matte Japanese oak parquet (eliminates overly glossy wet-varnish reflections!)
          m.roughnessMap = null;
          m.roughness = 0.82;
          m.metalness = 0.0;
          m.envMapIntensity = 0.10;
          if (m.normalScale) m.normalScale.set(0.36, 0.36);
          if (m instanceof THREE.MeshPhysicalMaterial) m.clearcoat = 0;
          m.needsUpdate = true;
        } else if (
          baseName === 'Furn_StudioRugCharcoal' ||
          baseName === 'Furn_LivingRugCharcoal' ||
          baseName === 'Furn_BedBoucleRug' ||
          baseName === 'Prop_BathCottonMat' ||
          baseName === 'Furn_WovenRug'
        ) {
          // Clean, bright warm stone-oatmeal woven wool rugs (zero dirty smudges, crisp contrast under black leather sofas!)
          const woven = this.getWovenTextileMaps();
          const colTex = woven.map.clone();
          const bmpTex = woven.bump.clone();
          const rep = baseName === 'Prop_BathCottonMat' ? 10 : 28;
          colTex.repeat.set(rep, rep);
          bmpTex.repeat.set(rep, rep);
          colTex.needsUpdate = true;
          bmpTex.needsUpdate = true;
          m.map = colTex;
          m.bumpMap = bmpTex;
          m.bumpScale = 0.0065;
          if (baseName === 'Furn_StudioRugCharcoal' || baseName === 'Furn_LivingRugCharcoal') {
            m.color.set('#bcb5a8'); // Crisp clean warm stone-oatmeal wool (anchors black leather sofas cleanly!)
          } else if (baseName === 'Furn_BedBoucleRug') {
            m.color.set('#c8c1b5');
          } else if (baseName === 'Prop_BathCottonMat') {
            m.color.set('#afa89d');
          }
          m.roughness = 0.96;
          m.metalness = 0.0;
          m.envMapIntensity = 0.03;
          if (m instanceof THREE.MeshPhysicalMaterial) m.clearcoat = 0;
          m.needsUpdate = true;
        } else if (
          baseName === 'Furn_SofaCloudOatmeal' ||
          baseName === 'Furn_LoaferCognacVelvet' ||
          baseName === 'Guide Lounge Chair_Baked'
        ) {
          // Unified Italian Full-Grain Satin-Matte Black Leather across ALL sofas & lounge chairs (clean, cohesive, zero UV bleed!)
          const woven = this.getWovenTextileMaps();
          const bmpTex = woven.bump.clone();
          bmpTex.repeat.set(22, 22);
          bmpTex.needsUpdate = true;
          m.map = null;
          m.normalMap = null;
          m.roughnessMap = null;
          m.color.set('#1a1b1f');
          m.bumpMap = bmpTex;
          m.bumpScale = 0.0022;
          m.roughness = 0.52;
          m.metalness = 0.03;
          m.envMapIntensity = 0.16;
          m.userData.directSpecFactor = 0.28;
          m.userData.directSpecKey = 'leather';
          m.needsUpdate = true;
        } else if (
          baseName.startsWith('Furn_SofaPillow') ||
          baseName.startsWith('Furn_BedDuvet') ||
          baseName.startsWith('Furn_BedThrow') ||
          baseName.startsWith('Furn_BedPillow')
        ) {
          // Crisp matte linen/wool pillows & hotel bedding (zero flat plastic look!)
          const woven = this.getWovenTextileMaps();
          const bmpTex = woven.bump.clone();
          bmpTex.repeat.set(16, 16);
          bmpTex.needsUpdate = true;
          if (baseName === 'Furn_SofaPillowCognac' || baseName === 'Furn_SofaPillowWarmTaupe') {
            m.color.set('#c4bdb2'); // Clean warm stone-ivory linen accent pillows on black leather sofa
          } else if (baseName === 'Furn_SofaPillowSageGrey' || baseName === 'Furn_SofaPillowCharcoal') {
            m.color.set('#27292e'); // Tailored charcoal-slate matte pillows
          }
          m.bumpMap = bmpTex;
          m.bumpScale = 0.0035;
          m.roughness = 0.94;
          m.metalness = 0.0;
          m.envMapIntensity = 0.05;
          if (m instanceof THREE.MeshPhysicalMaterial) m.clearcoat = 0;
          m.needsUpdate = true;
        } else if (
          baseName.toLowerCase().includes('leaf') ||
          baseName.toLowerCase().includes('foliage') ||
          baseName.toLowerCase().includes('pothos') ||
          baseName.toLowerCase().includes('ivy') ||
          baseName.toLowerCase().includes('plant') ||
          baseName.toLowerCase().includes('vine')
        ) {
          // Natural botanical satin-matte foliage (DoubleSide prevents dark backfaces on curved leaves!)
          const isTrunk = baseName.toLowerCase().includes('trunk') || baseName.toLowerCase().includes('stem');
          m.roughness = isTrunk ? 0.88 : 0.72;
          m.metalness = 0.0;
          m.envMapIntensity = isTrunk ? 0.06 : 0.10;
          if (!isTrunk) m.side = THREE.DoubleSide;
          if (m instanceof THREE.MeshPhysicalMaterial) m.clearcoat = 0;
          m.needsUpdate = true;
        } else if (baseName === 'Arch_DarkMarble') {
          // Honed satin dark Calacatta marble (silky indoor PMREM reflections, ZERO fake circular PointLight white orbs!)
          m.color.set('#ffffff');
          m.roughness = 0.36;
          m.metalness = 0.0;
          m.envMapIntensity = 0.44;
          m.userData.directSpecFactor = 0.03;
          m.userData.directSpecKey = 'marble';
          m.needsUpdate = true;
        } else if (baseName === 'Furn_KitchenMatteBlack') {
          // Fenix NTM ultra-matte architectural black cabinetry (zero glossy plastic glare spots!)
          m.color.set('#141619');
          m.roughness = 0.66;
          m.metalness = 0.06;
          m.envMapIntensity = 0.14;
          m.userData.directSpecFactor = 0.18;
          m.userData.directSpecKey = 'kmatte';
          m.needsUpdate = true;
        } else if (baseName === 'Furn_DarkLeather' || baseName.toLowerCase().includes('leather')) {
          m.roughness = Math.max(0.52, m.roughness);
          m.envMapIntensity = 0.16;
          m.userData.directSpecFactor = 0.30;
          m.userData.directSpecKey = 'leather';
          m.needsUpdate = true;
        } else if (baseName === 'Arch_SpaStoneTile') {
          m.color.set('#ffffff');
          m.roughness = 0.74;
          m.metalness = 0.0;
          m.envMapIntensity = 0.14;
          if (m.normalScale) m.normalScale.set(0.38, 0.38);
          m.needsUpdate = true;
        } else if (baseName === 'Furn_WovenRug') {
          m.roughness = 0.96;
          m.metalness = 0.0;
          m.envMapIntensity = 0.04;
          if (m.normalScale) m.normalScale.set(0.24, 0.24);
          m.needsUpdate = true;
        } else if (baseName === 'HW_AnodizedBlack') {
          // Architectural powder-coated matte-black steel (IKEA SKADIS pegboard, frames, arms -> ZERO harsh purple/white sheet glare!)
          m.color.set('#14161a');
          m.roughness = 0.74;
          m.metalness = 0.10;
          m.envMapIntensity = 0.16;
          m.needsUpdate = true;
        } else if (baseName === 'Prop_DeskMatWool' || baseName === 'Furn_SofaCharcoalWool') {
          m.color.set(baseName === 'Furn_SofaCharcoalWool' ? '#202020' : '#14171d');
          m.roughness = 0.94;
          m.metalness = 0.0;
          m.envMapIntensity = 0.10;
          if (m instanceof THREE.MeshPhysicalMaterial) m.clearcoat = 0;
          m.needsUpdate = true;
        } else if (baseName === 'Prop_PothosLeaf') {
          m.side = THREE.DoubleSide;
          m.needsUpdate = true;
        } else if (baseName === 'HW_PCFanBlades') {
          m.color.set('#0c2633');
          m.roughness = 0.28;
          m.metalness = 0.14;
          m.needsUpdate = true;
        } else if (
          baseName === 'Emit_ShelfUnderLED' ||
          baseName === 'Emit_KitchenUnderLED' ||
          baseName === 'Emit_BedroomCoveLED' ||
          baseName === 'Emit_BathMirrorHalo' ||
          baseName === 'Emit_BedsideLampBulb' ||
          baseName === 'Emit_StudioLinearWarm'
        ) {
          m.emissive.set(baseName === 'Emit_StudioLinearWarm' ? '#ffd092' : '#ffc980');
          const baseInt =
            baseName === 'Emit_StudioLinearWarm'
              ? 2.85
              : baseName === 'Emit_BathMirrorHalo'
                ? 2.6
                : baseName === 'Emit_BedsideLampBulb'
                  ? 2.4
                  : 1.9;
          m.emissiveIntensity = baseInt;
          m.needsUpdate = true;
          accentEmissives.push({ mat: m, base: baseInt });
          continue;
        } else if (baseName === 'Emit_DeskKeyLight') {
          m.emissive.set('#ffefd8');
          m.emissiveIntensity = 1.9;
          m.needsUpdate = true;
          accentEmissives.push({ mat: m, base: 1.9 });
          continue;
        } else if (baseName === 'Emit_HomeLabLED') {
          m.emissive.set('#22e58b');
          m.emissiveIntensity = 2.8;
          m.needsUpdate = true;
          continue;
        } else if (baseName === 'Screen_PixelClock' || baseName === 'Screen_AIO_LCD') {
          m.emissiveIntensity = 1.85;
          m.roughness = 0.20;
          m.needsUpdate = true;
          continue;
        } else if (baseName === 'Emit_TrackSpotLED') {
          m.emissive.set('#ffe2b4');
          m.emissiveIntensity = 4.2;
          m.needsUpdate = true;
          overheadEmissives.push({ mat: m, base: 4.2 });
          continue;
        } else if (baseName === 'phone_screen_mat') {
          m.color.set('#12161e');
          m.emissiveIntensity = 0.18;
          m.roughness = 0.14;
          m.needsUpdate = true;
        }

        // 3. Interactive ScreenBar LED & Unified 8-Mode Addressable ARGB Studio Neon Ecosystem!
        if (baseName === 'Emit_CoveWarm' || obj.name.includes('ScreenBar_LED')) {
          m.emissive.set('#ffcf91');
          m.emissiveIntensity = 2.4;
          screenBarMats.push(m);
          continue;
        }
        const neonU = this.moodSystem.studioNeonUniforms;
        if (baseName === 'Emit_RGB_Cyan' || baseName === 'Emit_PC_FanGlow') {
          patchStudioNeonMaterial(m, neonU, 'pc_fan', 2.9);
          rgbMats.push(m);
          continue;
        }
        if (baseName === 'Emit_StudioWallFrameRGB') {
          patchStudioNeonMaterial(m, neonU, 'wall_frame', 3.25);
          rgbMats.push(m);
          continue;
        }
        if (baseName === 'Emit_StudioShelfRGB') {
          patchStudioNeonMaterial(m, neonU, 'shelf_strip', 3.35);
          rgbMats.push(m);
          continue;
        }
        if (baseName === 'Emit_HexNeon_Primary' || baseName === 'Emit_StudioStripRGB_Primary') {
          patchStudioNeonMaterial(m, neonU, baseName === 'Emit_HexNeon_Primary' ? 'hex_ring_pri' : 'desk_pri', 3.25);
          rgbMats.push(m);
          continue;
        }
        if (baseName === 'Emit_HexNeon_Secondary' || baseName === 'Emit_StudioStripRGB_Secondary') {
          patchStudioNeonMaterial(m, neonU, baseName === 'Emit_HexNeon_Secondary' ? 'hex_ring_sec' : 'desk_sec', 3.10);
          rgbSecondaryMats.push(m);
          continue;
        }
        if (baseName === 'Emit_HexNeon_SoftFace') {
          patchStudioNeonMaterial(m, neonU, 'hex_soft', 1.55);
          rgbSoftMats.push(m);
          continue;
        }

        // 4. Patch Dual-Atlas Cycles-Baked HDR RGBM Lightmaps onto West (Studio+Living) & East (Kitchen+Bed+Bath)!
        const hasUv1 = Boolean(obj.geometry.attributes.uv1);
        const atlasMeta =
          m.userData?.useLightMapAtlas ??
          obj.userData?.useLightMapAtlas ??
          obj.parent?.userData?.useLightMapAtlas ??
          (obj.name.startsWith('Arch_LightMapped_East') || m.name.endsWith('__East')
            ? 'east'
            : obj.name.startsWith('Arch_LightMapped_West') ||
                obj.name.startsWith('Arch_LightMapped') ||
                m.name.endsWith('__West')
              ? 'west'
              : null);

        if (hasUv1 && (atlasMeta === 'west' || atlasMeta === 'east')) {
          const key = `${m.uuid}:${atlasMeta}`;
          let patched = patchedCloneByBase.get(key);
          if (!patched) {
            patched = m.clone();
            patchMaterialWithRgbMLightmap(
              patched,
              atlasMeta === 'east' ? initialLmEast : initialLmWest,
              this.moodSystem.getLightmapUniforms(atlasMeta),
              1.0
            );
            patchedCloneByBase.set(key, patched);
            this.moodSystem.registerPatchedMaterial(patched, atlasMeta);
          }
          mats[i] = patched;
          replacedAny = true;
        } else {
          if (m.emissiveMap?.name === 'LM_UV1_Anchor') {
            m.emissiveMap = null;
            m.emissive.setRGB(0, 0, 0);
            m.emissiveIntensity = 0;
            m.needsUpdate = true;
          }
          // Non-lightmapped smooth architectural materials: attenuate infinitesimal PointLight specular orbs
          // while preserving 100% of directDiffuse pools & real Indoor PMREM environment reflections!
          const specFactor = m.userData?.directSpecFactor as number | undefined;
          const specKey = m.userData?.directSpecKey as string | undefined;
          if (specFactor !== undefined && specKey && !m.userData._softSpecApplied) {
            m.userData._softSpecApplied = true;
            attenuateDirectSpecular(m, specFactor, specKey);
          } else if (
            !m.userData._softSpecApplied &&
            !m.transparent &&
            m.metalness < 0.25 &&
            m.roughness < 0.22 &&
            m.emissiveIntensity < 0.3 &&
            !baseName.startsWith('Screen_') &&
            !baseName.startsWith('Emit_') &&
            baseName !== 'Arch_MirrorSilver'
          ) {
            // Clamp stray BlenderKit micro-prop glossy plastics (roughness=0..0.21) so they never pop harsh white dots
            m.roughness = 0.26;
            m.userData._softSpecApplied = true;
            attenuateDirectSpecular(m, 0.35, 'prop');
          }
        }
      }

      if (replacedAny) {
        obj.material = isArrayMat ? mats : mats[0];
      }

      // Enable real physical sunlight & Venetian-blind Gobo shadow projection:
      // Architectural shell (Arch_LightMapped_West/East) casts clean wall/pier occlusion shadows while keeping
      // thin 2mm physical blind slats out of the 1024px shadow map so our crisp 1024px Venetian-blind Gobo shines cleanly!
      const finalMats = Array.isArray(obj.material) ? obj.material : [obj.material];
      const isGlassLike =
        obj.name.includes('Glass') ||
        obj.name.includes('Skyline') ||
        finalMats.some((fm) => fm instanceof THREE.MeshStandardMaterial && fm.transparent);
      const isArchShell = obj.name.startsWith('Arch_LightMapped') || obj.name.includes('Arch_Concrete') || obj.name.includes('Arch_East');
      obj.receiveShadow = !isGlassLike;
      obj.castShadow = !isGlassLike && isArchShell;

      // Track finalized PBR materials for Lighting-Only Clay & Wireframe inspection modes
      for (const fm of finalMats) {
        if (!(fm instanceof THREE.MeshStandardMaterial)) continue;
        this.allSceneMats.add(fm);
        const isSpecial =
          fm.transparent ||
          fm.emissiveIntensity > 0.35 ||
          fm.name.startsWith('Screen_') ||
          fm.name.startsWith('Emit_');
        if (!isSpecial && !this.inspectableMats.has(fm)) {
          this.inspectableMats.set(fm, {
            color: fm.color.clone(),
            map: fm.map,
            metalness: fm.metalness,
            roughness: fm.roughness,
          });
        }
      }
    });

    this.moodSystem.registerDynamicMaterials(
      screenMats,
      screenBarMats,
      rgbMats,
      overheadEmissives,
      accentEmissives,
      rgbSecondaryMats,
      rgbSoftMats
    );

    // Register clickable interactive world props
    const openAgentHud = () => {
      window.open('https://agenthud.app', '_blank', 'noopener,noreferrer');
    };

    if (ultrawideMesh) {
      this.interactables.register({
        object: ultrawideMesh,
        label: () => this.hud.getMessages().interact.agentHud,
        onClick: openAgentHud,
      });
    }
    if (verticalMesh) {
      this.interactables.register({
        object: verticalMesh,
        label: () => this.hud.getMessages().interact.agentHud,
        onClick: openAgentHud,
      });
    }
    for (const mb of macbookMeshes) {
      this.interactables.register({
        object: mb,
        label: () => this.hud.getMessages().interact.agentHud,
        onClick: openAgentHud,
      });
    }
    if (livingTvMesh) {
      this.interactables.register({
        object: livingTvMesh,
        label: () => this.hud.getMessages().interact.agentHudSite,
        onClick: openAgentHud,
      });
    }
    if (screenBarObj) {
      this.interactables.register({
        object: screenBarObj,
        label: () => this.hud.getMessages().interact.screenBar,
        onClick: () => this.moodSystem.toggleScreenBar(),
      });
    }
    if (pcObj) {
      this.interactables.register({
        object: pcObj,
        label: () => this.hud.getMessages().interact.pcRgb,
        onClick: () => {
          const pal = this.moodSystem.cycleRgbPalette();
          this.hud.setRgbMode(pal.id);
        },
      });
    }
    if (floorLampObj) {
      this.interactables.register({
        object: floorLampObj,
        label: () => this.hud.getMessages().interact.floorLamp,
        onClick: () => {
          const res = this.moodSystem.cycleLightScene();
          this.audioEngine.setLightScene(res.mode);
          this.hud.setLightSceneLabel(res.mode);
        },
      });
    }
    if (kitchenPendantObj) {
      this.interactables.register({
        object: kitchenPendantObj,
        label: () => this.hud.getMessages().interact.kitchenPendant,
        onClick: () => {
          const res = this.moodSystem.cycleLightScene();
          this.audioEngine.setLightScene(res.mode);
          this.hud.setLightSceneLabel(res.mode);
        },
      });
    }

    this.loftRoot = root;
    this.scene.add(root);
    // Attach grounded soft contact shadows (including movable shadows parented directly to un-batched chairs!)
    this.contactShadows.populate(root);
    this.scene.add(this.contactShadows.staticGroup);
    // Bind 4 per-room indoor reflection probes (Studio/Living, Kitchen, Bedroom, Spa Bath)
    this.indoorProbes.bindScene(root);
    // Bake initial time-of-day West-window sun shadow maps once (zero per-frame shadow render cost!)
    this.renderer.shadowMap.needsUpdate = true;
  }

  /**
   * Installs TRUE real-time planar Reflector mirrors over BOTH architectural mirrors in the loft:
   *  1. Zone 5 Spa Bathroom Circular Backlit Vanity Mirror (`Bath_MirrorGlass`, Ø85cm, facing -X)
   *  2. Zone 4 Master Bedroom Full-Length Leaning Dressing Mirror (`Bed_MirrorPane`, 63×187cm, tilted 2.2° facing +Z)
   * Both use LINEAR_ARCH_MIRROR_SHADER (linear HDR + 4× MSAA HalfFloat -> clean AgX + Bloom, zero blendOverlay clipping!)
   * and are room-culled to 0.00ms GPU cost whenever the camera is outside their room!
   */
  private setupRealPlanarMirrors(): void {
    // 1. Spa Bathroom Circular Backlit Vanity Mirror (Blender (9.354, 0.18, 1.58) -> Three.js (9.3515, 1.58, -0.18), facing -X)
    const bathGeo = new THREE.CircleGeometry(0.426, 64);
    const bathMirror = new Reflector(bathGeo, {
      color: 0xf0f4f7,
      textureWidth: 512,
      textureHeight: 512,
      multisample: 4,
      clipBias: 0.0,
      shader: LINEAR_ARCH_MIRROR_SHADER,
    });
    bathMirror.name = 'RealPlanarMirror_SpaBath';
    bathMirror.position.set(9.3515, 1.58, -0.18);
    bathMirror.rotation.set(0, -Math.PI * 0.5, 0);
    bathMirror.visible = false;
    this.scene.add(bathMirror);
    this.bathReflector = bathMirror;

    // 2. Master Bedroom Full-Length Leaning Dressing Mirror (Blender (6.02, -1.6036, 0.9601) -> Three.js (6.02, 0.9601, 1.6062), leaning -2.2° facing +Z)
    //    Positioned +4mm proud of Bed_MirrorPane with clipBias: 0.0 so the oblique near-plane cleanly clips Bed_MirrorBrassTrim & Frame behind it!
    const bedGeo = new THREE.PlaneGeometry(0.632, 1.872);
    const bedMirror = new Reflector(bedGeo, {
      color: 0xf0f4f7,
      textureWidth: 512,
      textureHeight: 768,
      multisample: 4,
      clipBias: 0.0,
      shader: LINEAR_ARCH_MIRROR_SHADER,
    });
    bedMirror.name = 'RealPlanarMirror_Bedroom';
    bedMirror.position.set(6.02, 0.96008, 1.6062);
    bedMirror.rotation.set((-2.2 * Math.PI) / 180, 0, 0);
    bedMirror.visible = false;
    this.scene.add(bedMirror);
    this.bedReflector = bedMirror;
  }

  private syncInspectionBackdrop(): void {
    const hideBackdrop = this.pureClayMode || this.lightingOnlyMode || this.wireframeMode;
    this.moodSystem.setBackdropVisible(!hideBackdrop);
    this.contactShadows.setVisible(!hideBackdrop);
    if (this.loftRoot) {
      this.loftRoot.traverse((obj) => {
        if (obj.name.includes('CitySkylineBackdrop')) {
          obj.visible = !hideBackdrop;
        }
      });
    }
    if (this.pureClayMode) {
      this.scene.background = new THREE.Color(this.wireframeMode ? '#14171f' : '#dfe2e7');
    } else if (this.wireframeMode) {
      this.scene.background = new THREE.Color('#11141a');
    } else if (this.lightingOnlyMode) {
      this.scene.background = new THREE.Color('#181a20');
    } else {
      this.scene.background = new THREE.Color('#070a12');
    }
  }

  public togglePhotoMode(): void {
    this.photoMode = !this.photoMode;
    this.hud.setPhotoMode(this.photoMode);
  }

  public togglePureClayMode(): void {
    if (!this.pureClayMode && this.lightingOnlyMode) {
      this.toggleLightingOnlyMode();
    }
    this.pureClayMode = !this.pureClayMode;
    this.hud.setPureClayMode(this.pureClayMode);
    this.clayLightGroup.visible = this.pureClayMode;
    this.moodSystem.setClayLightsMuted(this.pureClayMode);
    this.postFx.setForceAo(this.pureClayMode);
    this.pureClayMat.wireframe = this.wireframeMode;

    if (this.loftRoot) {
      if (this.pureClayMode) {
        this.pureClaySavedMats.clear();
        this.pureClayHiddenMeshes.length = 0;
        this.loftRoot.traverse((obj) => {
          if (!(obj instanceof THREE.Mesh)) return;
          if (obj.name.includes('CitySkylineBackdrop')) return;
          // Hide clear architectural glass panes in Pure Clay so window openings & shower glass stay airy!
          const n = obj.name.toLowerCase();
          if (
            n.includes('windowglass') ||
            n.includes('livwin_glass') ||
            n.includes('showerglass') ||
            n.includes('fluted_glass') ||
            n.includes('fluted_rib') ||
            n.includes('flutedslide_glass')
          ) {
            if (obj.visible) {
              obj.visible = false;
              this.pureClayHiddenMeshes.push(obj);
            }
            return;
          }
          this.pureClaySavedMats.set(obj, obj.material);
          obj.material = this.pureClayMat;
        });
      } else {
        for (const [mesh, origMat] of this.pureClaySavedMats) {
          mesh.material = origMat;
        }
        this.pureClaySavedMats.clear();
        for (const mesh of this.pureClayHiddenMeshes) {
          mesh.visible = true;
        }
        this.pureClayHiddenMeshes.length = 0;
      }
    }
    this.syncInspectionBackdrop();
  }

  public toggleLightingOnlyMode(): void {
    if (!this.lightingOnlyMode && this.pureClayMode) {
      this.togglePureClayMode();
    }
    this.lightingOnlyMode = !this.lightingOnlyMode;
    this.hud.setLightingOnlyMode(this.lightingOnlyMode);
    for (const [mat, orig] of this.inspectableMats) {
      if (this.lightingOnlyMode) {
        mat.color.set('#d4d2ce');
        mat.map = null;
        mat.metalness = 0.0;
        mat.roughness = 0.88;
      } else {
        mat.color.copy(orig.color);
        mat.map = orig.map;
        mat.metalness = orig.metalness;
        mat.roughness = orig.roughness;
      }
      mat.needsUpdate = true;
    }
    this.syncInspectionBackdrop();
  }

  public toggleWireframeMode(): void {
    this.wireframeMode = !this.wireframeMode;
    this.hud.setWireframeMode(this.wireframeMode);
    this.pureClayMat.wireframe = this.wireframeMode;
    for (const mat of this.allSceneMats) {
      mat.wireframe = this.wireframeMode;
    }
    if (this.loftRoot) {
      this.loftRoot.traverse((obj) => {
        if (!(obj instanceof THREE.Mesh)) return;
        const mats = Array.isArray(obj.material) ? obj.material : [obj.material];
        for (const m of mats) {
          if (m && 'wireframe' in m) {
            (m as THREE.MeshStandardMaterial).wireframe = this.wireframeMode;
          }
        }
      });
    }
    this.syncInspectionBackdrop();
  }

  /**
   * Hybrid Asset Pipeline Drag-and-Drop Slot Loader:
   * Dropping any local .glb file onto the canvas normalizes its size and previews it on the rug!
   */
  private setupDragDropSlotLoader(canvas: HTMLCanvasElement): void {
    let customPreview: THREE.Object3D | null = null;
    canvas.addEventListener('dragover', (e) => e.preventDefault());
    canvas.addEventListener('drop', async (e) => {
      e.preventDefault();
      const file = e.dataTransfer?.files?.[0];
      if (!file || !file.name.toLowerCase().endsWith('.glb')) return;
      const url = URL.createObjectURL(file);
      try {
        const gltf = await this.gltfLoader.loadAsync(url);
        if (customPreview) this.scene.remove(customPreview);
        const obj = gltf.scene;
        const box = new THREE.Box3().setFromObject(obj);
        const size = box.getSize(new THREE.Vector3());
        const scale = 0.85 / Math.max(size.x, size.y, size.z, 0.01);
        obj.scale.setScalar(scale);
        box.setFromObject(obj);
        const center = box.getCenter(new THREE.Vector3());
        obj.position.set(-center.x, -box.min.y, -center.z + 0.45);
        customPreview = obj;
        this.scene.add(obj);
      } finally {
        URL.revokeObjectURL(url);
      }
    });
  }

  private readonly handleResize = (): void => {
    const w = window.innerWidth;
    const h = window.innerHeight;
    this.cameraCtrl.resize(w, h);
    this.renderer.setSize(w, h);
    this.postFx.setSize(w, h);
  };

  private selectMoodManually(id: MoodId): void {
    this.currentMood = id;
    if (this.moodAutoCycle) {
      this.setMoodAutoCycle(false, false);
    }
    this.applyMood(id, true);
  }

  private setMoodAutoCycle(enabled: boolean, notify = false): void {
    this.moodAutoCycle = enabled;
    this.moodCycleTimer = 0;
    this.audioEngine.setAutoAdvance(enabled);
    if (!enabled) {
      // Stopping auto-cycle syncs music to the current time-of-day (no-op if already on that track)
      this.audioEngine.setMood(this.currentMood);
    }
    this.hud.setMoodCycleActive(enabled, notify);
  }

  private applyMood(id: MoodId, syncAudio: boolean): void {
    this.currentMood = id;
    this.hud.setActiveMood(id);
    this.ensureProbesFor(id);
    this.moodSystem.setMood(id);
    if (syncAudio) {
      this.audioEngine.setMood(id);
    }
  }

  private readonly loop = (): void => {
    this.rafId = requestAnimationFrame(this.loop);
    const delta = Math.min(this.clock.getDelta(), 0.05);
    const elapsed = this.clock.elapsedTime;

    if (this.moodAutoCycle) {
      this.moodCycleTimer += delta;
      if (this.moodCycleTimer >= this.moodCycleInterval) {
        this.moodCycleTimer = 0;
        const nextIdx = (this.moodOrder.indexOf(this.currentMood) + 1) % this.moodOrder.length;
        this.applyMood(this.moodOrder[nextIdx], false);
      }
    }

    this.cameraCtrl.update(delta);
    this.cameraCtrl.camera.getWorldDirection(this.camForward);
    this.camFocusPos.copy(this.cameraCtrl.camera.position).addScaledVector(this.camForward, 1.8);

    // Engage authentic 50mm f/2.8 shallow Depth of Field when framing Desk/PC/Pegboard Macro close-ups!
    // Focus plane sits midway between keyboard (1.37m) & 38" ultrawide monitor (1.61m) so BOTH stay 100% tack-sharp,
    // while background concrete wall, hex neon, floor lamp, & exterior skyline melt smoothly into cinema bokeh!
    const preset = this.cameraCtrl.getActivePreset();
    const isMacroPreset = preset === 'desk' || preset === 'pc' || preset === 'pegboard';
    const focusDist = this.cameraCtrl.getFocusDistance();
    const wantMacroDof =
      this.cameraCtrl.getMode() === 'tour' &&
      isMacroPreset &&
      focusDist < 2.35 &&
      !this.pureClayMode &&
      !this.wireframeMode;
    const tunedFocus = preset === 'desk' ? focusDist + 0.12 : focusDist;
    this.postFx.setMacroDof(wantMacroDof, tunedFocus, preset === 'desk' ? 3.65 : 2.95);
    this.postFx.updateMacroDof(delta);

    const audioFrame = this.audioEngine.update(delta);
    this.moodSystem.update(delta, this.camFocusPos, audioFrame);
    this.screens.update(delta, elapsed, audioFrame);

    // Zero-cost spatial + facing gating for real-time planar Reflector mirrors (0.00ms outside Spa Bath / Bedroom or when facing away!)
    const allowMirrors = !this.pureClayMode && !this.lightingOnlyMode && !this.wireframeMode;
    const camPos = this.cameraCtrl.camera.position;
    if (this.bathReflector) {
      this.bathReflector.visible =
        allowMirrors && camPos.x > 4.6 && camPos.z < 1.95 && this.camForward.x > -0.25;
    }
    if (this.bedReflector) {
      this.bedReflector.visible =
        allowMirrors && camPos.x > 3.2 && camPos.z > 1.64 && this.camForward.z < 0.25;
    }

    this.renderer.info.reset();
    this.postFx.render(delta);
    this.perf.tick(delta);

    this.frameCount++;
    if (this.frameCount === 1) this.markTiming('first-frame');
    this.checkCameraResponded();
    this.stepBackgroundProbeBake();
  };

  // ---- Deferred reflection probes -------------------------------------------------------------

  /** Probes must only be baked with the normal materials on screen (not clay / wireframe / lighting-only). */
  private canBakeProbes(): boolean {
    return !this.pureClayMode && !this.wireframeMode && !this.lightingOnlyMode;
  }

  /** Puts the scene back on `mood` after a probe bake applied another mood to it. */
  private restoreLiveMood(mood: MoodId): void {
    this.moodSystem.applyImmediateForBake(mood);
    const env = this.indoorProbes.getActiveSceneEnvTexture();
    if (env) this.scene.environment = env;
  }

  /**
   * Called before every mood switch: if the target mood's probes have not been baked in the
   * background yet, bake them now (one short hitch) so the switch still blends reflections.
   */
  private ensureProbesFor(mood: MoodId): void {
    if (!this.canBakeProbes()) return;
    const live = this.moodSystem.getCurrentMood();
    // Both ends of the blend need probes (the live one can be missing if it was picked in clay mode).
    for (const m of live === mood ? [mood] : [live, mood]) {
      if (this.indoorProbes.hasMood(m)) continue;
      this.indoorProbes.bakeMoodNow(
        this.scene,
        m,
        (x) => this.moodSystem.applyImmediateForBake(x),
        () => this.restoreLiveMood(live)
      );
      this.onProbeMoodBaked(m);
    }
  }

  /** Bakes one room probe every other frame once the first frame is on screen, while no mood transition runs. */
  private stepBackgroundProbeBake(): void {
    if (this.probesReadyMarked) return;
    if (this.frameCount < 2 || this.frameCount % 2 !== 0) return;
    if (!this.canBakeProbes() || this.moodSystem.isTransitioning()) return;
    const live = this.moodSystem.getCurrentMood();
    const done = this.indoorProbes.bakeNextZone(
      this.scene,
      (m) => this.moodSystem.applyImmediateForBake(m),
      () => this.restoreLiveMood(live)
    );
    if (done) this.onProbeMoodBaked(done);
  }

  private onProbeMoodBaked(mood: MoodId): void {
    // If we were showing this mood without its probes (e.g. switched while in clay mode), sync them now.
    const live = this.moodSystem.getCurrentMood();
    if (mood === live && !this.moodSystem.isTransitioning() && this.canBakeProbes()) {
      const env = this.moodSystem.getSkyPmrem(live);
      this.indoorProbes.blendMood(live, live, 1.0, env, env);
    }
    if (!this.probesReadyMarked && this.indoorProbes.isFullyBaked()) {
      this.setupRealPlanarMirrors();
      this.markTiming('probes-ready');
    }
  }

  // ---- Startup timing marks (performance.mark, readable via __ASTUDIO__.getTimings()) ------------

  private markTiming(name: 'first-frame' | 'first-input' | 'camera-responded' | 'probes-ready'): void {
    if (name === 'probes-ready') this.probesReadyMarked = true;
    if (this.timings[name] !== undefined) return;
    this.timings[name] = Math.round(performance.now());
    performance.mark(`astudio:${name}`);
    console.info(`[astudio] ${name} at ${this.timings[name]} ms (probes: ${this.probesEager ? 'eager' : 'deferred'})`);
  }

  private readonly onFirstUserInput = (): void => {
    if (this.pendingInputCamPos || this.timings['camera-responded'] !== undefined) return;
    const cam = this.cameraCtrl.camera;
    this.pendingInputCamPos = cam.position.clone();
    this.pendingInputCamQuat = cam.quaternion.clone();
    this.markTiming('first-input');
  };

  /** Marks the first frame where the camera moved after a user input. */
  private checkCameraResponded(): void {
    if (!this.pendingInputCamPos || !this.pendingInputCamQuat) return;
    const cam = this.cameraCtrl.camera;
    if (
      cam.position.distanceToSquared(this.pendingInputCamPos) > 1e-8 ||
      1 - Math.abs(cam.quaternion.dot(this.pendingInputCamQuat)) > 1e-8
    ) {
      this.pendingInputCamPos = null;
      this.pendingInputCamQuat = null;
      this.markTiming('camera-responded');
      for (const ev of ['pointerdown', 'wheel', 'keydown', 'touchstart'] as const) {
        window.removeEventListener(ev, this.onFirstUserInput, true);
      }
    }
  }

  public dispose(): void {
    cancelAnimationFrame(this.rafId);
    window.removeEventListener('resize', this.handleResize);
    if (this.bathReflector) {
      this.bathReflector.geometry.dispose();
      this.bathReflector.dispose();
    }
    if (this.bedReflector) {
      this.bedReflector.geometry.dispose();
      this.bedReflector.dispose();
    }
    this.cameraCtrl.dispose();
    this.interactables.dispose();
    this.screens.dispose();
    this.audioEngine.dispose();
    this.moodSystem.dispose();
    this.indoorProbes.dispose();
    this.contactShadows.dispose();
    this.postFx.dispose();
    this.dracoLoader.dispose();
    this.renderer.dispose();
  }
}
