import * as THREE from 'three';
import { RGBELoader } from 'three/examples/jsm/loaders/RGBELoader.js';
import { ExteriorCity } from './ExteriorCity';
import type { LightmapBlendUniforms } from './LightmapMaterialPatch';
import type { PostProcessingPipeline } from './PostProcessing';
import {
  STUDIO_NEON_MODES,
  createStudioNeonUniforms,
  evaluateNeonWashLights,
  type StudioNeonModeSpec,
  type StudioNeonUniforms,
} from './StudioNeonEngine';
import type { AudioReactiveFrame } from './StudioAudioEngine';

export type MoodId = 'midnight' | 'golden' | 'daylight' | 'noon';
type SkyAssetMoodId = 'midnight' | 'golden' | 'daylight';
export type LightmapAtlasId = 'west' | 'east';
export type LightSceneMode = 'bright' | 'cozy' | 'cinema';

function toSkyMood(mood: MoodId): SkyAssetMoodId {
  return mood === 'noon' ? 'daylight' : mood;
}

interface LightSceneProfile {
  label: string;
  lmMult: number;
  overheadMult: number;
  accentMult: number;
  screenBarMult: number;
  bloomBoost: number;
  exposureDelta: number;
}

const LIGHT_SCENE_PROFILES: Record<LightSceneMode, LightSceneProfile> = {
  bright: {
    label: '全屋开灯',
    lmMult: 1.38,
    overheadMult: 1.85,
    accentMult: 1.12,
    screenBarMult: 1.0,
    bloomBoost: 0.04,
    exposureDelta: 0.09,
  },
  cozy: {
    label: '柔光氛围',
    lmMult: 0.42,
    overheadMult: 0.0,
    accentMult: 1.18,
    screenBarMult: 0.45,
    bloomBoost: 0.14,
    exposureDelta: -0.04,
  },
  cinema: {
    label: '关灯影院',
    lmMult: 0.12,
    overheadMult: 0.0,
    accentMult: 0.0,
    screenBarMult: 0.0,
    bloomBoost: 0.24,
    exposureDelta: -0.10,
  },
};

interface MoodConfig {
  exposure: number;
  lightMapScale: number;
  envIntensity: number;
  skyBrightness: number;
  bloomIntensity: number;
  vignetteDarkness: number;
  keyLightColor: THREE.Color;
  keyLightIntensity: number;
  westRimColor: THREE.Color;
  westRimIntensity: number;
  pcLightIntensity: number;
  screenBarIntensity: number;
  screenEmissive: number;
}

const MOOD_CONFIGS: Record<MoodId, MoodConfig> = {
  midnight: {
    exposure: 0.96,
    lightMapScale: 0.88,
    envIntensity: 0.26,
    skyBrightness: 1.32,
    bloomIntensity: 0.40,
    vignetteDarkness: 0.42,
    keyLightColor: new THREE.Color('#ffd096'),
    keyLightIntensity: 1.05,
    westRimColor: new THREE.Color('#3058a8'),
    westRimIntensity: 0.28,
    pcLightIntensity: 1.35,
    screenBarIntensity: 1.35,
    screenEmissive: 1.48,
  },
  golden: {
    exposure: 0.98,
    lightMapScale: 0.90,
    envIntensity: 0.52,
    skyBrightness: 1.40,
    bloomIntensity: 0.30,
    vignetteDarkness: 0.28,
    keyLightColor: new THREE.Color('#ffb168'),
    keyLightIntensity: 1.35,
    westRimColor: new THREE.Color('#ff8e3c'),
    westRimIntensity: 1.75,
    pcLightIntensity: 0.95,
    screenBarIntensity: 0.85,
    screenEmissive: 1.40,
  },
  daylight: {
    exposure: 0.89,
    lightMapScale: 0.78,
    envIntensity: 0.56,
    skyBrightness: 1.32,
    bloomIntensity: 0.22,
    vignetteDarkness: 0.22,
    keyLightColor: new THREE.Color('#ffebd0'),
    keyLightIntensity: 1.12,
    westRimColor: new THREE.Color('#d8e6fa'),
    westRimIntensity: 1.45,
    pcLightIntensity: 0.78,
    screenBarIntensity: 0.62,
    screenEmissive: 1.40,
  },
  noon: {
    exposure: 1.10,
    lightMapScale: 1.02,
    envIntensity: 1.06,
    skyBrightness: 1.72,
    bloomIntensity: 0.12,
    vignetteDarkness: 0.10,
    keyLightColor: new THREE.Color('#ffffff'),
    keyLightIntensity: 0.62,
    westRimColor: new THREE.Color('#e4f3ff'),
    westRimIntensity: 2.85,
    pcLightIntensity: 0.32,
    screenBarIntensity: 0.10,
    screenEmissive: 1.62,
  },
};

export type RgbPalette = StudioNeonModeSpec;

interface VirtualPointLight {
  position: THREE.Vector3;
  color: THREE.Color;
  intensity: number;
  distance: number;
  decay: number;
  priority: number;
}

interface SunProjectionProfile {
  color: THREE.Color;
  studioIntensity: number;
  livingIntensity: number;
  // Direction ray FROM exterior sky INTO the loft (normalized in Three.js world space: +X = East inward, -Y = downward)
  dir: THREE.Vector3;
}

const SUN_PROFILES: Record<MoodId, SunProjectionProfile> = {
  // Midnight: subtle cool blue-indigo urban moonlight grazing the West window jamb & blinds
  midnight: {
    color: new THREE.Color('#5a86d6'),
    studioIntensity: 0.42,
    livingIntensity: 0.36,
    dir: new THREE.Vector3(0.82, -0.44, -0.36).normalize(),
  },
  // Golden Hour: dramatic low-angle (~13 deg) warm sunset sun slicing razor-crisp Venetian blind stripes directly across walnut slats, desk, & sofa!
  golden: {
    color: new THREE.Color('#ff9a42'),
    studioIntensity: 8.4,
    livingIntensity: 7.2,
    dir: new THREE.Vector3(0.74, -0.22, -0.63).normalize(),
  },
  // Daylight (Early Morning ~7:30): soft misty pale-peach morning sun (~28 deg) with calm cool interior shadows
  daylight: {
    color: new THREE.Color('#ffe2bd'),
    studioIntensity: 5.0,
    livingIntensity: 4.5,
    dir: new THREE.Vector3(0.76, -0.47, -0.45).normalize(),
  },
  // Noon (High Midday ~12:30): blazing steep ~60 deg pure-white zenith sun throwing stark bright midday light pools & razor-crisp blind stripes!
  noon: {
    color: new THREE.Color('#ffffff'),
    studioIntensity: 11.4,
    livingIntensity: 10.4,
    dir: new THREE.Vector3(0.49, -0.86, -0.11).normalize(),
  },
};

const ACTIVE_POINT_LIGHT_POOL_SIZE = 6;

/**
 * Orchestrates seamless 1.2s transitions between Midnight Stream, Golden Hour, and Daylight:
 * - Cross-fades Cycles-baked HDR RGBM Lightmaps on UV1
 * - Cross-fades curved exterior City Skyline Cyclorama photography
 * - Switches pre-baked Poly Haven PMREM HDRI environment reflections
 * - Runs a fixed 6-slot dynamic PointLight pool (down from 22!) so WebGL fragment shaders run 3.7x fewer GGX loops!
 */
export class MoodSystem {
  public readonly lightmapUniformsWest: LightmapBlendUniforms = {
    uLightMapB: { value: null },
    uLightMapMix: { value: 0 },
    uLightMapRange: { value: 8.0 },
    uLightMapScale: { value: 1.05 },
  };
  public readonly lightmapUniformsEast: LightmapBlendUniforms = {
    uLightMapB: { value: null },
    uLightMapMix: { value: 0 },
    uLightMapRange: { value: 8.0 },
    uLightMapScale: { value: 1.05 },
  };

  private readonly lightmapsWest = new Map<MoodId, THREE.Texture>();
  private readonly lightmapsEast = new Map<MoodId, THREE.Texture>();
  private readonly skylines = new Map<SkyAssetMoodId, THREE.Texture>();
  private readonly pmrems = new Map<SkyAssetMoodId, THREE.Texture>();
  private readonly patchedMaterialsWest: THREE.MeshStandardMaterial[] = [];
  private readonly patchedMaterialsEast: THREE.MeshStandardMaterial[] = [];
  private onMoodBlend?: (
    from: MoodId,
    to: MoodId,
    t: number,
    envA: THREE.Texture | null,
    envB: THREE.Texture | null
  ) => void;
  private externalSceneEnvManaged = false;

  private currentMood: MoodId = 'midnight';
  private fromMood: MoodId = 'midnight';
  private toMood: MoodId = 'midnight';
  private transitionT = 1.0;
  private transitionDuration = 1.15;

  private screenBarOn = true;
  private rgbIndex = 0;
  private lightScene: LightSceneMode = 'bright';
  private curLmMult = LIGHT_SCENE_PROFILES.bright.lmMult;
  private curOverheadMult = LIGHT_SCENE_PROFILES.bright.overheadMult;
  private curAccentMult = LIGHT_SCENE_PROFILES.bright.accentMult;
  private curScreenBarMult = LIGHT_SCENE_PROFILES.bright.screenBarMult;
  private curBloomBoost = LIGHT_SCENE_PROFILES.bright.bloomBoost;
  private curExposureDelta = LIGHT_SCENE_PROFILES.bright.exposureDelta;

  private readonly renderer: THREE.WebGLRenderer;
  private readonly scene: THREE.Scene;
  private readonly postFx: PostProcessingPipeline;

  // Fixed 6-slot GPU PointLight pool driven by 22 room-aware virtual fixtures (3.7x faster fragment shaders!)
  private readonly westWindowLight: THREE.DirectionalLight;
  private readonly studioSunSpot: THREE.SpotLight;
  private readonly livingSunSpot: THREE.SpotLight;
  private readonly blindsGoboTex: THREE.CanvasTexture;
  private readonly tmpSunDir = new THREE.Vector3();
  private readonly lightPool: THREE.PointLight[] = [];
  private readonly allVirtualLights: VirtualPointLight[] = [];
  private readonly lightScores: Float32Array;
  private readonly slotOwner = new Int32Array(ACTIVE_POINT_LIGHT_POOL_SIZE).fill(-1);
  private readonly lastFocusPos = new THREE.Vector3(-0.2, 1.3, -0.8);

  private readonly keySpotLight: VirtualPointLight;
  private readonly screenBarLight: VirtualPointLight;
  private readonly floorLampLight: VirtualPointLight;
  private readonly candleLight: VirtualPointLight;
  private readonly pcPrimaryLight: VirtualPointLight;
  private readonly pcWarmLight: VirtualPointLight;
  private readonly hexWallLightL: VirtualPointLight;
  private readonly hexWallLightR: VirtualPointLight;
  private readonly deskStripLightL: VirtualPointLight;
  private readonly deskStripLightR: VirtualPointLight;
  private readonly slatSeamWashLight: VirtualPointLight;
  private readonly shelfFillLight: VirtualPointLight;
  private readonly zoneFillLights: Array<{ light: VirtualPointLight; baseIntensity: number; kind: 'overhead' | 'accent' }> = [];

  // Exterior curved skyline cyclorama with custom smooth cross-fade shader
  private readonly skylineUniforms = {
    uTexA: { value: null as THREE.Texture | null },
    uTexB: { value: null as THREE.Texture | null },
    uMix: { value: 0 },
    uBrightness: { value: 1.35 },
  };
  private readonly skylineMesh: THREE.Mesh;
  private readonly exteriorCity: ExteriorCity;
  private elapsedTime = 0;

  private screenMaterials: THREE.MeshStandardMaterial[] = [];
  private screenBarLedMats: THREE.MeshStandardMaterial[] = [];
  public readonly studioNeonUniforms: StudioNeonUniforms = createStudioNeonUniforms();
  private readonly tmpNeonPri = new THREE.Color();
  private readonly tmpNeonSec = new THREE.Color();
  private neonIntensityMult = 1.0;
  private overheadEmissiveMats: Array<{ mat: THREE.MeshStandardMaterial; base: number }> = [];
  private accentEmissiveMats: Array<{ mat: THREE.MeshStandardMaterial; base: number }> = [];

  constructor(renderer: THREE.WebGLRenderer, scene: THREE.Scene, postFx: PostProcessingPipeline) {
    this.renderer = renderer;
    this.scene = scene;
    this.postFx = postFx;

    // Allocate ONLY 6 hardware PointLights in the scene (constant shader define, zero recompiles, 3.7x less per-pixel PBR!)
    for (let i = 0; i < ACTIVE_POINT_LIGHT_POOL_SIZE; i++) {
      const pl = new THREE.PointLight('#ffffff', 0, 5.0, 1.6);
      this.scene.add(pl);
      this.lightPool.push(pl);
    }

    const addVLight = (
      x: number,
      y: number,
      z: number,
      col: string,
      intensity: number,
      distance: number,
      decay: number,
      priority = 1.0
    ): VirtualPointLight => {
      const vl: VirtualPointLight = {
        position: new THREE.Vector3(x, y, z),
        color: new THREE.Color(col),
        intensity,
        distance,
        decay,
        priority,
      };
      this.allVirtualLights.push(vl);
      return vl;
    };

    // Blender (x, y, z) -> Three.js (x, z, -y) for Full 5-Zone 87 m^2 Geek Loft!
    this.westWindowLight = new THREE.DirectionalLight('#2664e8', 0.85);
    this.westWindowLight.position.set(-4.5, 2.4, 1.5);
    this.scene.add(this.westWindowLight);

    // Dual West-Window Architectural Sunlight & Venetian-Blind Gobo Projectors!
    // Projects crisp 1024px Venetian blind slats + black steel mullions + bamboo leaf silhouettes across
    // the walnut wall, standing desk, concrete panels, sofa, & herringbone floor with time-of-day solar angles!
    this.blindsGoboTex = this.createVenetianBlindsGobo();
    const makeSunSpot = (): THREE.SpotLight => {
      const sp = new THREE.SpotLight('#ff9d47', 0.4, 24, 0.34, 0.08, 0);
      sp.map = this.blindsGoboTex;
      sp.castShadow = true;
      sp.shadow.mapSize.set(1024, 1024);
      sp.shadow.camera.near = 4.2;
      sp.shadow.camera.far = 18.5;
      sp.shadow.bias = -0.0005;
      sp.shadow.normalBias = 0.032;
      this.scene.add(sp);
      this.scene.add(sp.target);
      return sp;
    };
    this.studioSunSpot = makeSunSpot();
    this.livingSunSpot = makeSunSpot();

    this.keySpotLight = addVLight(-0.08, 2.45, -1.02, '#ffe2ba', 2.05, 7.6, 1.55, 1.15);
    this.screenBarLight = addVLight(-0.26, 1.14, -1.24, '#ffd8a4', 1.85, 3.2, 1.45, 1.35);
    this.floorLampLight = addVLight(-1.56, 1.56, -1.35, '#ffb768', 2.65, 4.4, 1.68, 1.10);
    this.candleLight = addVLight(1.12, 0.54, 4.14, '#ff9438', 1.15, 2.2, 1.8, 1.25);
    this.pcPrimaryLight = addVLight(0.86, 0.24, -1.38, '#1fd2ff', 1.4, 2.0, 1.8, 1.25);
    this.pcWarmLight = addVLight(0.94, 0.16, -1.44, '#ff7024', 0.65, 1.4, 1.8, 0.70);
    this.hexWallLightL = addVLight(-0.42, 1.96, -1.84, '#1fd2ff', 1.05, 2.5, 1.7, 1.30);
    this.hexWallLightR = addVLight(0.28, 2.02, -1.84, '#ff7024', 0.95, 2.5, 1.7, 1.30);
    // Tucked safely below & behind Desk_WalnutTop (Y=0.64, Z=-1.96) -> silky indirect concrete wall-wash with ZERO desk-edge hotspot!
    this.deskStripLightL = addVLight(-0.74, 0.64, -1.96, '#1fd2ff', 0.68, 2.8, 1.55, 1.10);
    this.deskStripLightR = addVLight(0.32, 0.64, -1.96, '#ff7024', 0.64, 2.8, 1.55, 1.10);
    // Tucked inside the 4-tier Bookshelf bay (X=1.78, Z=-0.78) so it washes shelf props without glaring onto the North Pegboard!
    this.slatSeamWashLight = addVLight(1.78, 1.44, -0.78, '#ff7024', 0.72, 2.2, 1.8, 1.05);
    this.shelfFillLight = addVLight(1.22, 2.25, -0.35, '#ffcf96', 1.35, 4.6, 1.6, 0.95);

    // Practical architectural fixture pools across Zones 1–5 (classified as overhead vs accent for Lutron dimming!)
    const zoneSpecs: Array<[number, number, number, string, number, number, 'overhead' | 'accent']> = [
      [1.18, 2.15, 0.74, '#ffd29b', 1.25, 4.4, 'overhead'],    // Zone 1 East Maker Workbench
      [0.90, 2.42, 3.70, '#ffd096', 2.20, 7.6, 'overhead'],    // Zone 2 Living Track Overhead
      [0.90, 1.34, 5.24, '#ffb66c', 1.35, 3.4, 'accent'],      // Zone 2 77" OLED TV Rear Architectural Bias Glow!
      [-1.02, 1.38, 2.86, '#ffbe74', 1.85, 4.2, 'accent'],     // Zone 2 Oslo Brushed-Brass Floor Lamp Pool beside Sofa!
      [4.00, 2.52, 4.96, '#ffd49c', 2.15, 4.8, 'overhead'],    // Zone 2 Penthouse Main Entryway Recessed Ceiling Welcome Downlight!
      [4.25, 2.12, 0.18, '#ffc67c', 2.45, 6.2, 'overhead'],    // Zone 3 Kitchen 3-Pendant Marble Island Pool (raised for uniform 3-lamp spread!)
      [3.96, 1.44, -1.28, '#ffbe70', 0.78, 3.6, 'accent'],     // Zone 3 Kitchen Under-Cabinet Warm Wash (pulled off backsplash -> zero round orb!)
      [7.15, 2.38, 3.45, '#ffcb8c', 1.55, 6.2, 'overhead'],    // Zone 4 Master Bedroom Main Ceiling
      [8.68, 0.74, 2.02, '#ffbc6e', 1.05, 2.6, 'accent'],      // Zone 4 Bedroom North Architectural Bedside Lamp
      [8.68, 0.74, 4.88, '#ffbc6e', 1.05, 2.6, 'accent'],      // Zone 4 Bedroom South Architectural Bedside Lamp
      [6.36, 1.56, 4.42, '#ffc278', 0.58, 4.2, 'accent'],      // Zone 4 Porada Walnut Wardrobe Soft Warm Fill
      [8.10, 2.42, -0.25, '#ffd6a2', 1.75, 5.8, 'overhead'],   // Zone 5 Spa Bathroom Overhead
      [8.76, 1.98, -0.18, '#ffc880', 1.25, 3.2, 'accent'],     // Zone 5 Spa Bathroom Vanity Pool
      [8.42, 1.38, -1.48, '#ffc276', 0.62, 2.5, 'accent'],     // Zone 5 Aman-Tokyo Recessed Spa Niche Warm Wash (pulled off wall -> zero dot!)
    ];
    for (const [x, y, z, col, intensity, dist, kind] of zoneSpecs) {
      const vl = addVLight(x, y, z, col, intensity, dist, 1.6, 1.05);
      this.zoneFillLights.push({ light: vl, baseIntensity: intensity, kind });
    }
    this.lightScores = new Float32Array(this.allVirtualLights.length);

    this.skylineMesh = this.createSkylineCyclorama();
    this.skylineMesh.visible = false; // Replaced by true 3D multi-layered instanced Tokyo skyline in ExteriorCity (genuine 3D parallax!)
    this.scene.add(this.skylineMesh);

    // Continuous 7.8m Cantilevered Penthouse Glass Balcony spanning BOTH Zone 1 Studio AND Zone 2 Living Lounge!
    this.exteriorCity = new ExteriorCity([-2.2, 5.6]);
    this.scene.add(this.exteriorCity.group);
  }

  public async preloadAssets(
    onProgress?: (pct: number, msg: string, byteInfo?: { loaded: number; total: number }) => void,
    messages?: { lightmaps: string; sky: string; pmrem: string },
    byteTracker?: { initialLoaded: number; totalBytes: number }
  ): Promise<void> {
    const texLoader = new THREE.TextureLoader();
    const rgbeLoader = new RGBELoader();
    const pmremGen = new THREE.PMREMGenerator(this.renderer);
    pmremGen.compileEquirectangularShader();

    const lmMoods: MoodId[] = ['midnight', 'golden', 'daylight', 'noon'];
    const skyMoods: SkyAssetMoodId[] = ['midnight', 'golden', 'daylight'];

    const totalExpectedBytes = byteTracker?.totalBytes ?? 89_311_109;
    let downloadedBytes = byteTracker?.initialLoaded ?? 0;

    const emitProgress = (msg: string, inFlightBytes = 0): void => {
      const loaded = downloadedBytes + inFlightBytes;
      const total = Math.max(totalExpectedBytes, loaded);
      const pct = Math.round(4 + (loaded / total) * 88);
      onProgress?.(pct, msg, { loaded, total });
    };

    const fetchAsBlobUrl = async (
      url: string,
      onChunk: (received: number, total: number) => void
    ): Promise<{ blobUrl: string; bytes: number }> => {
      const res = await fetch(url);
      if (!res.ok) throw new Error(`Failed to fetch ${url}: ${res.status}`);
      const total = Number(res.headers.get('content-length')) || 0;
      if (!res.body) {
        const blob = await res.blob();
        onChunk(blob.size, blob.size);
        return { blobUrl: URL.createObjectURL(blob), bytes: blob.size };
      }
      const reader = res.body.getReader();
      const chunks: BlobPart[] = [];
      let received = 0;
      let lastEmit = 0;
      while (true) {
        const { done, value } = await reader.read();
        if (done) break;
        if (value) {
          chunks.push(value);
          received += value.byteLength;
          const now = performance.now();
          if (now - lastEmit >= 80) {
            lastEmit = now;
            onChunk(received, total);
          }
        }
      }
      onChunk(received, total || received);
      const mime = res.headers.get('content-type') || undefined;
      const blob = new Blob(chunks, mime ? { type: mime } : undefined);
      return { blobUrl: URL.createObjectURL(blob), bytes: received };
    };

    const loadLm = async (
      url: string,
      onChunk: (received: number, total: number) => void
    ): Promise<THREE.Texture> => {
      const { blobUrl, bytes } = await fetchAsBlobUrl(url, onChunk);
      downloadedBytes += bytes;
      try {
        const tex = await texLoader.loadAsync(blobUrl);
        tex.colorSpace = THREE.NoColorSpace; // Raw linear RGBA RGBM!
        tex.flipY = false;
        tex.channel = 1;
        tex.generateMipmaps = true;
        tex.minFilter = THREE.LinearMipmapLinearFilter;
        tex.magFilter = THREE.LinearFilter;
        tex.anisotropy = 4;
        return tex;
      } finally {
        URL.revokeObjectURL(blobUrl);
      }
    };

    // 1. Load All 8 Cycles-Baked 2048px OIDN HDR RGBM Lightmaps sequentially with unified byte progress
    const lmBaseMsg = messages?.lightmaps ?? '正在加载全屋四时段双图集 2K HDR + OIDN 光照贴图…';
    const lmTasks: Array<{ mood: MoodId; atlas: LightmapAtlasId; url: string }> = lmMoods.flatMap((m) => [
      { mood: m, atlas: 'west' as const, url: `/assets/lightmaps/loft_west_${m}.png` },
      { mood: m, atlas: 'east' as const, url: `/assets/lightmaps/loft_east_${m}.png` },
    ]);

    for (let i = 0; i < lmTasks.length; i++) {
      const task = lmTasks[i];
      const stepMsg = `${lmBaseMsg} (${i + 1}/${lmTasks.length})`;
      emitProgress(stepMsg, 0);
      const tex = await loadLm(task.url, (received) => {
        emitProgress(stepMsg, received);
      });
      if (task.atlas === 'west') this.lightmapsWest.set(task.mood, tex);
      else this.lightmapsEast.set(task.mood, tex);
    }

    // 2. Load Photorealistic Exterior City Skyline Panoramas sequentially with unified byte progress
    const skyBaseMsg = messages?.sky ?? '正在加载四时段东京高空天际线全景…';
    for (let i = 0; i < skyMoods.length; i++) {
      const m = skyMoods[i];
      const stepMsg = `${skyBaseMsg} (${i + 1}/${skyMoods.length})`;
      emitProgress(stepMsg, 0);
      const { blobUrl, bytes } = await fetchAsBlobUrl(`/assets/sky/skyline_${m}.jpg`, (received) => {
        emitProgress(stepMsg, received);
      });
      downloadedBytes += bytes;
      try {
        const tex = await texLoader.loadAsync(blobUrl);
        tex.colorSpace = THREE.SRGBColorSpace;
        tex.wrapS = THREE.ClampToEdgeWrapping;
        tex.wrapT = THREE.ClampToEdgeWrapping;
        this.skylines.set(m, tex);
      } finally {
        URL.revokeObjectURL(blobUrl);
      }
    }

    // 3. Load & Pre-Bake Poly Haven 2K HDRIs via PMREMGenerator sequentially with unified byte progress
    const hdriFiles: Record<SkyAssetMoodId, string> = {
      midnight: 'blue_lagoon_night_2k.hdr',
      golden: 'belfast_sunset_puresky_2k.hdr',
      daylight: 'aristea_wreck_puresky_2k.hdr',
    };

    const pmremBaseMsg = messages?.pmrem ?? '正在烘焙 Poly Haven 真实环境反射 (PMREM)…';
    for (let i = 0; i < skyMoods.length; i++) {
      const m = skyMoods[i];
      const stepMsg = `${pmremBaseMsg} (${i + 1}/${skyMoods.length})`;
      emitProgress(stepMsg, 0);
      const { blobUrl, bytes } = await fetchAsBlobUrl(`/assets/hdris/${hdriFiles[m]}`, (received) => {
        emitProgress(stepMsg, received);
      });
      downloadedBytes += bytes;
      try {
        const hdr = await rgbeLoader.loadAsync(blobUrl);
        const rt = pmremGen.fromEquirectangular(hdr);
        hdr.dispose();
        this.pmrems.set(m, rt.texture);
      } finally {
        URL.revokeObjectURL(blobUrl);
      }
    }
    emitProgress(pmremBaseMsg, 0);
    pmremGen.dispose();

    // Initialize default Midnight state immediately
    this.lightmapUniformsWest.uLightMapB.value = this.lightmapsWest.get('midnight')!;
    this.lightmapUniformsEast.uLightMapB.value = this.lightmapsEast.get('midnight')!;
    this.skylineUniforms.uTexA.value = this.skylines.get('midnight')!;
    this.skylineUniforms.uTexB.value = this.skylines.get('midnight')!;
    this.applyImmediate('midnight');
  }

  public getLightmap(mood: MoodId, atlas: LightmapAtlasId = 'west'): THREE.Texture {
    return (atlas === 'east' ? this.lightmapsEast : this.lightmapsWest).get(mood)!;
  }

  public getSkyPmrem(mood: MoodId): THREE.Texture | null {
    return this.pmrems.get(toSkyMood(mood)) ?? null;
  }

  public setOnMoodBlend(
    cb: (from: MoodId, to: MoodId, t: number, envA: THREE.Texture | null, envB: THREE.Texture | null) => void,
    manageSceneEnv = true
  ): void {
    this.onMoodBlend = cb;
    this.externalSceneEnvManaged = manageSceneEnv;
  }

  /**
   * Synchronously snaps lightmaps, dynamic lights, sun, sky, & outdoor PMREM for startup offline probe pre-baking.
   */
  public applyImmediateForBake(mood: MoodId): void {
    const lmW = this.lightmapsWest.get(mood)!;
    const lmE = this.lightmapsEast.get(mood)!;
    for (const mat of this.patchedMaterialsWest) mat.lightMap = lmW;
    this.lightmapUniformsWest.uLightMapB.value = lmW;
    this.lightmapUniformsWest.uLightMapMix.value = 0;

    for (const mat of this.patchedMaterialsEast) mat.lightMap = lmE;
    this.lightmapUniformsEast.uLightMapB.value = lmE;
    this.lightmapUniformsEast.uLightMapMix.value = 0;

    const skyTex = this.skylines.get(toSkyMood(mood))!;
    this.skylineUniforms.uTexA.value = skyTex;
    this.skylineUniforms.uTexB.value = skyTex;
    this.skylineUniforms.uMix.value = 0;

    this.applyImmediate(mood);
    this.syncLightPool(0);
  }

  public getLightmapUniforms(atlas: LightmapAtlasId = 'west'): LightmapBlendUniforms {
    return atlas === 'east' ? this.lightmapUniformsEast : this.lightmapUniformsWest;
  }

  public registerPatchedMaterial(mat: THREE.MeshStandardMaterial, atlas: LightmapAtlasId = 'west'): void {
    if (atlas === 'east') this.patchedMaterialsEast.push(mat);
    else this.patchedMaterialsWest.push(mat);
  }

  public registerDynamicMaterials(
    screens: THREE.MeshStandardMaterial[],
    screenBarLeds: THREE.MeshStandardMaterial[],
    _rgbMats: THREE.MeshStandardMaterial[],
    overheadEmissives: Array<{ mat: THREE.MeshStandardMaterial; base: number }> = [],
    accentEmissives: Array<{ mat: THREE.MeshStandardMaterial; base: number }> = [],
    _rgbSecondaryMats: THREE.MeshStandardMaterial[] = [],
    _rgbSoftMats: THREE.MeshStandardMaterial[] = []
  ): void {
    this.screenMaterials = screens;
    this.screenBarLedMats = screenBarLeds;
    this.overheadEmissiveMats = overheadEmissives;
    this.accentEmissiveMats = accentEmissives;
    this.applyRgbPalette();
    this.applyLightingFrame(1.0);
  }

  public getLightSceneMode(): LightSceneMode {
    return this.lightScene;
  }

  public getLightSceneLabel(): string {
    return LIGHT_SCENE_PROFILES[this.lightScene].label;
  }

  public setLightSceneMode(mode: LightSceneMode): LightSceneMode {
    this.lightScene = mode;
    this.screenBarOn = mode !== 'cinema';
    return this.lightScene;
  }

  public cycleLightScene(): { mode: LightSceneMode; label: string } {
    const order: LightSceneMode[] = ['bright', 'cozy', 'cinema'];
    this.lightScene = order[(order.indexOf(this.lightScene) + 1) % order.length];
    this.screenBarOn = this.lightScene !== 'cinema';
    return { mode: this.lightScene, label: LIGHT_SCENE_PROFILES[this.lightScene].label };
  }

  public getCurrentMood(): MoodId {
    return this.currentMood;
  }

  public setTransitionDuration(seconds: number): void {
    this.transitionDuration = Math.max(0.05, seconds);
  }

  public snapMood(mood: MoodId): void {
    this.applyImmediateForBake(mood);
    this.fromMood = mood;
    this.toMood = mood;
    this.currentMood = mood;
    this.transitionT = 1.0;
    const env = this.getSkyPmrem(mood);
    this.onMoodBlend?.(mood, mood, 1.0, env, env);
  }

  public setMood(target: MoodId): void {
    if (target === this.toMood && this.transitionT >= 1.0) return;

    const skyCur = toSkyMood(this.currentMood);
    const skyTarget = toSkyMood(target);

    const lmWA = this.lightmapsWest.get(this.currentMood)!;
    const lmWB = this.lightmapsWest.get(target)!;
    for (const mat of this.patchedMaterialsWest) mat.lightMap = lmWA;
    this.lightmapUniformsWest.uLightMapB.value = lmWB;
    this.lightmapUniformsWest.uLightMapMix.value = 0;

    const lmEA = this.lightmapsEast.get(this.currentMood)!;
    const lmEB = this.lightmapsEast.get(target)!;
    for (const mat of this.patchedMaterialsEast) mat.lightMap = lmEA;
    this.lightmapUniformsEast.uLightMapB.value = lmEB;
    this.lightmapUniformsEast.uLightMapMix.value = 0;

    this.skylineUniforms.uTexA.value = this.skylines.get(skyCur)!;
    this.skylineUniforms.uTexB.value = this.skylines.get(skyTarget)!;
    this.skylineUniforms.uMix.value = 0;

    this.fromMood = this.currentMood;
    this.toMood = target;
    this.currentMood = target;
    this.transitionT = 0;

    if (!this.externalSceneEnvManaged) {
      const envTex = this.pmrems.get(skyTarget);
      if (envTex) {
        this.scene.environment = envTex;
      }
    }
  }

  public toggleScreenBar(): boolean {
    this.screenBarOn = !this.screenBarOn;
    if (this.screenBarOn && this.curScreenBarMult < 0.4) {
      this.curScreenBarMult = 0.85;
    }
    this.syncInteractiveLights();
    return this.screenBarOn;
  }

  public cycleRgbPalette(step = 1): RgbPalette {
    const n = STUDIO_NEON_MODES.length;
    this.rgbIndex = (((this.rgbIndex + step) % n) + n) % n;
    this.applyRgbPalette();
    return STUDIO_NEON_MODES[this.rgbIndex];
  }

  public setRgbMode(index: number): RgbPalette {
    const n = STUDIO_NEON_MODES.length;
    this.rgbIndex = ((index % n) + n) % n;
    this.applyRgbPalette();
    return STUDIO_NEON_MODES[this.rgbIndex];
  }

  public update(delta: number, focusPos?: THREE.Vector3, audio?: AudioReactiveFrame): void {
    this.elapsedTime += delta;
    this.exteriorCity.update(this.elapsedTime);
    if (focusPos) this.lastFocusPos.copy(focusPos);
    this.updateAnimatedNeonSync(audio);

    // Gentle organic candle flame flicker in Living Lounge!
    const flicker =
      1.0 + Math.sin(this.elapsedTime * 7.3) * 0.08 + Math.sin(this.elapsedTime * 13.7) * 0.05;
    const candleBase = this.currentMood === 'noon' ? 0.18 : this.currentMood === 'daylight' ? 0.35 : 1.25;
    this.candleLight.intensity = candleBase * flicker;

    // Smooth physical Lutron dimmer ramp (~0.45s) for whole-home light scene changes!
    const targetP = LIGHT_SCENE_PROFILES[this.lightScene];
    const dimmerDamp = 1 - Math.exp(-7.5 * delta);
    const dimmerMoving =
      Math.abs(this.curLmMult - targetP.lmMult) > 0.002 ||
      Math.abs(this.curOverheadMult - targetP.overheadMult) > 0.002 ||
      Math.abs(this.curAccentMult - targetP.accentMult) > 0.002;
    if (dimmerMoving) {
      this.curLmMult = THREE.MathUtils.lerp(this.curLmMult, targetP.lmMult, dimmerDamp);
      this.curOverheadMult = THREE.MathUtils.lerp(this.curOverheadMult, targetP.overheadMult, dimmerDamp);
      this.curAccentMult = THREE.MathUtils.lerp(this.curAccentMult, targetP.accentMult, dimmerDamp);
      this.curScreenBarMult = THREE.MathUtils.lerp(this.curScreenBarMult, targetP.screenBarMult, dimmerDamp);
      this.curBloomBoost = THREE.MathUtils.lerp(this.curBloomBoost, targetP.bloomBoost, dimmerDamp);
      this.curExposureDelta = THREE.MathUtils.lerp(this.curExposureDelta, targetP.exposureDelta, dimmerDamp);
    }

    if (this.transitionT >= 1.0) {
      if (dimmerMoving) this.applyLightingFrame(1.0);
      this.syncLightPool(delta);
      return;
    }

    this.transitionT = Math.min(1.0, this.transitionT + delta / this.transitionDuration);
    const t =
      this.transitionT < 0.5
        ? 4 * this.transitionT * this.transitionT * this.transitionT
        : 1 - Math.pow(-2 * this.transitionT + 2, 3) / 2;

    this.lightmapUniformsWest.uLightMapMix.value = t;
    this.lightmapUniformsEast.uLightMapMix.value = t;
    this.skylineUniforms.uMix.value = t;
    this.exteriorCity.setMoodBlend(this.fromMood, this.toMood, t);
    this.onMoodBlend?.(
      this.fromMood,
      this.toMood,
      t,
      this.getSkyPmrem(this.fromMood),
      this.getSkyPmrem(this.toMood)
    );
    this.applyLightingFrame(t);
    this.syncLightPool(delta);
    // Keep uLightMapMix = 1.0 cleanly at transition end (zero texture-slot churn or end-of-animation flash!)
  }

  private applyLightingFrame(moodT: number): void {
    const a = MOOD_CONFIGS[this.fromMood];
    const b = MOOD_CONFIGS[this.toMood];

    // Morning & Noon sunlight stays bright even when indoor lamps are dimmed; Midnight responds dramatically!
    const isDay = (m: MoodId) => m === 'daylight' || m === 'noon';
    const isDayFactor = (isDay(this.fromMood) ? 1 - moodT : 0) + (isDay(this.toMood) ? moodT : 0);
    const isNoonFactor = (this.fromMood === 'noon' ? 1 - moodT : 0) + (this.toMood === 'noon' ? moodT : 0);
    const effectiveLmMult = THREE.MathUtils.lerp(this.curLmMult, Math.max(0.88, this.curLmMult), isDayFactor);

    this.renderer.toneMappingExposure =
      THREE.MathUtils.lerp(a.exposure, b.exposure, moodT) + this.curExposureDelta * (1 - isDayFactor * 0.65);
    const lmScale = THREE.MathUtils.lerp(a.lightMapScale, b.lightMapScale, moodT) * effectiveLmMult;
    this.lightmapUniformsWest.uLightMapScale.value = lmScale;
    this.lightmapUniformsEast.uLightMapScale.value = lmScale;
    this.scene.environmentIntensity =
      THREE.MathUtils.lerp(a.envIntensity, b.envIntensity, moodT) *
      THREE.MathUtils.lerp(0.42, 1.12, Math.min(1, effectiveLmMult));
    this.skylineUniforms.uBrightness.value = THREE.MathUtils.lerp(a.skyBrightness, b.skyBrightness, moodT);

    this.postFx.setMoodVisuals(
      THREE.MathUtils.lerp(a.bloomIntensity, b.bloomIntensity, moodT) + this.curBloomBoost * (1 - isDayFactor * 0.72),
      THREE.MathUtils.lerp(a.vignetteDarkness, b.vignetteDarkness, moodT)
    );

    const lampColor = a.keyLightColor.clone().lerp(b.keyLightColor, moodT);
    const overheadColor = lampColor.clone().lerp(new THREE.Color('#fff2de'), 0.35);
    const baseKey = THREE.MathUtils.lerp(a.keyLightIntensity, b.keyLightIntensity, moodT);
    this.keySpotLight.color.copy(overheadColor);
    this.keySpotLight.intensity = baseKey * 1.55 * this.curOverheadMult * (1 - isNoonFactor * 0.28);
    this.shelfFillLight.color.copy(lampColor);
    this.shelfFillLight.intensity = 1.25 * this.curAccentMult * (1 - isNoonFactor * 0.35);
    this.floorLampLight.intensity = 2.65 * this.curAccentMult * (1 - isDayFactor * 0.65 - isNoonFactor * 0.18);

    for (const zl of this.zoneFillLights) {
      zl.light.color.copy(zl.kind === 'overhead' ? overheadColor : lampColor);
      const mult = zl.kind === 'overhead' ? this.curOverheadMult : this.curAccentMult;
      zl.light.intensity = zl.baseIntensity * mult * (1 - isDayFactor * 0.45 - isNoonFactor * 0.20);
    }

    const nightSkyFill = THREE.MathUtils.lerp(0.45, 1.0, Math.min(1, effectiveLmMult));
    const isGoldenOrDay =
      (this.fromMood !== 'midnight' ? 1 - moodT : 0) + (this.toMood !== 'midnight' ? moodT : 0);
    // Keep diffuse westWindowLight restrained when Golden/Morning sun projectors are active, with brighter sky bounce at high noon!
    this.westWindowLight.color.lerpColors(a.westRimColor, b.westRimColor, moodT);
    this.westWindowLight.intensity =
      THREE.MathUtils.lerp(a.westRimIntensity, b.westRimIntensity, moodT) *
      THREE.MathUtils.lerp(nightSkyFill, 0.56 + isNoonFactor * 0.16, isGoldenOrDay);

    // Update Time-of-Day Dual West-Window Sun Projectors (sweeps Venetian blind shadows dynamically across the loft!)
    const sunA = SUN_PROFILES[this.fromMood];
    const sunB = SUN_PROFILES[this.toMood];
    this.tmpSunDir.lerpVectors(sunA.dir, sunB.dir, moodT).normalize();
    const sunDist = 8.6;
    const targetDist = 3.4;

    this.studioSunSpot.color.lerpColors(sunA.color, sunB.color, moodT);
    this.studioSunSpot.intensity = THREE.MathUtils.lerp(sunA.studioIntensity, sunB.studioIntensity, moodT);
    this.studioSunSpot.position.set(
      -2.18 - this.tmpSunDir.x * sunDist,
      1.42 - this.tmpSunDir.y * sunDist,
      -0.35 - this.tmpSunDir.z * sunDist
    );
    this.studioSunSpot.target.position.set(
      -2.18 + this.tmpSunDir.x * targetDist,
      1.42 + this.tmpSunDir.y * targetDist,
      -0.35 + this.tmpSunDir.z * targetDist
    );
    this.studioSunSpot.target.updateMatrixWorld();

    this.livingSunSpot.color.lerpColors(sunA.color, sunB.color, moodT);
    this.livingSunSpot.intensity = THREE.MathUtils.lerp(sunA.livingIntensity, sunB.livingIntensity, moodT);
    this.livingSunSpot.position.set(
      -2.18 - this.tmpSunDir.x * sunDist,
      1.37 - this.tmpSunDir.y * sunDist,
      3.69 - this.tmpSunDir.z * sunDist
    );
    this.livingSunSpot.target.position.set(
      -2.18 + this.tmpSunDir.x * targetDist,
      1.37 + this.tmpSunDir.y * targetDist,
      3.69 + this.tmpSunDir.z * targetDist
    );
    this.livingSunSpot.target.updateMatrixWorld();

    // Refresh static-cached shadow maps strictly when sun geometry shifts (zero ongoing FPS cost once settled!)
    this.renderer.shadowMap.needsUpdate = true;
    this.pcPrimaryLight.intensity = THREE.MathUtils.lerp(a.pcLightIntensity, b.pcLightIntensity, moodT);
    const hexMult = THREE.MathUtils.lerp(0.60, 1.0, Math.min(1, this.curAccentMult)) * (1 - isDayFactor * 0.48) * this.neonIntensityMult;
    this.hexWallLightL.intensity = 1.05 * hexMult;
    this.hexWallLightR.intensity = 0.95 * hexMult;
    this.deskStripLightL.intensity = 0.68 * hexMult;
    this.deskStripLightR.intensity = 0.64 * hexMult;
    this.slatSeamWashLight.intensity = 0.68 * hexMult;

    const baseSb = THREE.MathUtils.lerp(a.screenBarIntensity, b.screenBarIntensity, moodT);
    this.screenBarLight.intensity = this.screenBarOn ? baseSb * 1.65 * this.curScreenBarMult : 0;
    for (const m of this.screenBarLedMats) {
      m.emissiveIntensity = this.screenBarOn ? Math.max(0.04, 2.8 * this.curScreenBarMult) : 0.04;
    }

    for (const item of this.overheadEmissiveMats) {
      item.mat.emissiveIntensity = item.base * Math.min(1.25, this.curOverheadMult);
    }
    for (const item of this.accentEmissiveMats) {
      item.mat.emissiveIntensity = item.base * Math.min(1.25, this.curAccentMult);
    }

    const scrEm = THREE.MathUtils.lerp(a.screenEmissive, b.screenEmissive, moodT);
    for (const m of this.screenMaterials) {
      m.emissiveIntensity = scrEm;
    }
  }

  private applyImmediate(mood: MoodId): void {
    this.currentMood = mood;
    this.fromMood = mood;
    this.toMood = mood;
    this.transitionT = 1.0;

    this.scene.environment = this.pmrems.get(toSkyMood(mood)) ?? null;
    this.exteriorCity.setMoodBlend(mood, mood, 1.0);
    this.applyLightingFrame(1.0);
  }

  private syncInteractiveLights(): void {
    this.applyLightingFrame(1.0);
  }

  private applyRgbPalette(): void {
    const p = STUDIO_NEON_MODES[this.rgbIndex];
    this.studioNeonUniforms.uNeonMode.value = p.id;
    this.studioNeonUniforms.uNeonPri.value.copy(p.primary);
    this.studioNeonUniforms.uNeonSec.value.copy(p.secondary);
    this.studioNeonUniforms.uNeonAcc.value.copy(p.accent);
    this.updateAnimatedNeonSync();
    this.syncLightPool();
  }

  /**
   * Drives synchronized real-time addressable ARGB modes (fixed, rainbow marquee, dual-comet chase,
   * liquid synthwave flow, synced full-spectrum morph, 4-color combo chase, deep breathing pulse, warm white)
   * across ALL Studio neon shaders AND 7 dynamic room-wash PointLights!
   */
  private updateAnimatedNeonSync(audio?: AudioReactiveFrame): void {
    const t = this.elapsedTime;
    this.studioNeonUniforms.uNeonTime.value = t;
    // Cinema dimmer gently scales neon brightness while keeping marquee effects vivid in Bright & Cozy modes
    this.studioNeonUniforms.uNeonDim.value = THREE.MathUtils.lerp(0.32, 1.0, Math.min(1, this.curAccentMult));

    if (audio) {
      this.studioNeonUniforms.uAudioBands.value.set(audio.bass, audio.mid, audio.treble, audio.breath);
      this.studioNeonUniforms.uAudioBeat.value.set(audio.beat, audio.beatPhase, audio.active);
    }

    const mult = evaluateNeonWashLights(this.rgbIndex, t, this.tmpNeonPri, this.tmpNeonSec, audio);
    this.neonIntensityMult = mult;

    this.pcPrimaryLight.color.copy(this.tmpNeonPri);
    this.pcWarmLight.color.copy(this.tmpNeonSec);
    this.hexWallLightL.color.copy(this.tmpNeonPri);
    this.hexWallLightR.color.copy(this.tmpNeonSec);
    this.deskStripLightL.color.copy(this.tmpNeonPri);
    this.deskStripLightR.color.copy(this.tmpNeonSec);
    // Bookshelf dynamic wash light directly illuminates the 4-tier shelf props & East wall in live ARGB sync!
    this.slatSeamWashLight.color.copy(this.tmpNeonSec);
    this.shelfFillLight.color.copy(this.tmpNeonPri).lerp(new THREE.Color('#ffe0bc'), this.rgbIndex === 5 ? 0.85 : 0.35);

    const isDay = this.currentMood === 'daylight' || this.currentMood === 'noon';
    const dayScale = isDay ? 0.56 : 1.0;
    const accentScale = THREE.MathUtils.lerp(0.62, 1.0, Math.min(1, this.curAccentMult)) * dayScale * mult;
    this.hexWallLightL.intensity = 1.12 * accentScale;
    this.hexWallLightR.intensity = 1.05 * accentScale;
    this.deskStripLightL.intensity = 0.68 * accentScale;
    this.deskStripLightR.intensity = 0.64 * accentScale;
    this.slatSeamWashLight.intensity = 0.72 * accentScale;
  }

  /**
   * Builds the curved photorealistic City Skyline Cyclorama outside the West steel-grid loft window (-X).
   */
  private createSkylineCyclorama(): THREE.Mesh {
    const radius = 38.0; // Positioned behind our 3D balcony & mid-ground parallax bokeh/beacons!
    const thetaLength = THREE.MathUtils.degToRad(138); // Wide panoramic sweep for multi-room West windows!
    const height = 74.0;
    const geom = new THREE.CylinderGeometry(
      radius,
      radius,
      height,
      48,
      1,
      true,
      Math.PI * 1.5 - thetaLength * 0.5,
      thetaLength
    );
    // Flip horizontal UV so image reads cleanly from inside
    const uvAttr = geom.attributes.uv;
    for (let i = 0; i < uvAttr.count; i++) {
      uvAttr.setX(i, 1.0 - uvAttr.getX(i));
    }

    const mat = new THREE.ShaderMaterial({
      side: THREE.BackSide,
      depthWrite: false,
      uniforms: this.skylineUniforms,
      vertexShader: /* glsl */ `
        varying vec2 vUv;
        void main() {
          vUv = uv;
          gl_Position = projectionMatrix * modelViewMatrix * vec4(position, 1.0);
        }
      `,
      fragmentShader: /* glsl */ `
        uniform sampler2D uTexA;
        uniform sampler2D uTexB;
        uniform float uMix;
        uniform float uBrightness;
        varying vec2 vUv;
        void main() {
          // Center band displays full high-res Tokyo skyline photography; lower band smoothly continues darkened bokeh!
          float mappedV = (vUv.y - 0.24) / 0.52;
          float lowerFade = smoothstep(-0.42, 0.06, mappedV);
          float sampleV = mappedV < 0.0 ? clamp(-mappedV * 0.42, 0.0, 0.28) : clamp(mappedV, 0.0, 1.0);
          vec2 st = vec2(vUv.x, sampleV);
          vec3 colA = texture2D(uTexA, st).rgb;
          vec3 colB = texture2D(uTexB, st).rgb;
          vec3 col = mix(colA, colB, uMix) * uBrightness * mix(0.24, 1.0, lowerFade);
          gl_FragColor = vec4(col, 1.0);
        }
      `,
    });

    const mesh = new THREE.Mesh(geom, mat);
    mesh.name = 'Runtime_CitySkylineCyclorama';
    mesh.position.set(0, 2.2, 0);
    mesh.renderOrder = -15;
    return mesh;
  }

  private clayLightsMuted = false;

  public setBackdropVisible(visible: boolean): void {
    this.skylineMesh.visible = false; // True 3D Tokyo skyline lives in exteriorCity!
    this.exteriorCity.group.visible = visible;
  }

  /**
   * Zero-allocation dynamic light pooling with +18% active-slot hysteresis & smooth temporal lerping:
   * Picks the top 6 most relevant room fixtures around camera focus while preserving stable slot ownership
   * so rotating or walking across room boundaries NEVER flickers or pops!
   */
  private syncLightPool(delta = 0): void {
    if (this.clayLightsMuted) {
      for (let i = 0; i < ACTIVE_POINT_LIGHT_POOL_SIZE; i++) {
        this.lightPool[i].intensity = 0;
      }
      return;
    }

    const n = this.allVirtualLights.length;
    const fx = this.lastFocusPos.x;
    const fy = this.lastFocusPos.y;
    const fz = this.lastFocusPos.z;
    for (let i = 0; i < n; i++) {
      const vl = this.allVirtualLights[i];
      if (vl.intensity <= 0.015) {
        this.lightScores[i] = -1;
        continue;
      }
      const dx = vl.position.x - fx;
      const dy = vl.position.y - fy;
      const dz = vl.position.z - fz;
      const dSq = dx * dx + dy * dy + dz * dz;
      let score = (vl.intensity * vl.distance * vl.priority) / (1.0 + dSq * 0.42);
      // +18% hysteresis bonus for currently active pool lights -> eliminates edge oscillation!
      for (let s = 0; s < ACTIVE_POINT_LIGHT_POOL_SIZE; s++) {
        if (this.slotOwner[s] === i) {
          score *= 1.18;
          break;
        }
      }
      this.lightScores[i] = score;
    }

    // Select top 6 virtual light indices
    const wanted = new Int32Array(ACTIVE_POINT_LIGHT_POOL_SIZE).fill(-1);
    for (let k = 0; k < ACTIVE_POINT_LIGHT_POOL_SIZE; k++) {
      let bestIdx = -1;
      let bestScore = 0;
      for (let i = 0; i < n; i++) {
        const s = this.lightScores[i];
        if (s > bestScore) {
          bestScore = s;
          bestIdx = i;
        }
      }
      if (bestIdx >= 0) {
        wanted[k] = bestIdx;
        this.lightScores[bestIdx] = -1;
      }
    }

    // Keep existing owners pinned to their SAME hardware slot (prevents cross-slot swaps!)
    const slotKept = new Uint8Array(ACTIVE_POINT_LIGHT_POOL_SIZE);
    const wantedAssigned = new Uint8Array(ACTIVE_POINT_LIGHT_POOL_SIZE);
    for (let s = 0; s < ACTIVE_POINT_LIGHT_POOL_SIZE; s++) {
      const cur = this.slotOwner[s];
      if (cur < 0) continue;
      for (let k = 0; k < ACTIVE_POINT_LIGHT_POOL_SIZE; k++) {
        if (wanted[k] === cur) {
          slotKept[s] = 1;
          wantedAssigned[k] = 1;
          break;
        }
      }
    }

    // Assign newly entering lights to free slots
    const damp = delta > 0 ? 1 - Math.exp(-9.0 * delta) : 1.0;
    for (let s = 0; s < ACTIVE_POINT_LIGHT_POOL_SIZE; s++) {
      const pl = this.lightPool[s];
      if (!slotKept[s]) {
        let nextIdx = -1;
        for (let k = 0; k < ACTIVE_POINT_LIGHT_POOL_SIZE; k++) {
          if (wanted[k] >= 0 && !wantedAssigned[k]) {
            nextIdx = wanted[k];
            wantedAssigned[k] = 1;
            break;
          }
        }
        const changed = this.slotOwner[s] !== nextIdx;
        this.slotOwner[s] = nextIdx;
        if (nextIdx >= 0 && changed) {
          // Teleport newly assigned slot while fading intensity smoothly up from 0 (zero pop!)
          const vl = this.allVirtualLights[nextIdx];
          pl.position.copy(vl.position);
          pl.color.copy(vl.color);
          pl.distance = vl.distance;
          pl.decay = vl.decay;
          pl.intensity = delta > 0 ? 0.0 : vl.intensity;
        }
      }
      const owner = this.slotOwner[s];
      if (owner >= 0) {
        const vl = this.allVirtualLights[owner];
        pl.position.copy(vl.position);
        pl.color.lerp(vl.color, damp);
        pl.distance = vl.distance;
        pl.decay = vl.decay;
        pl.intensity = THREE.MathUtils.lerp(pl.intensity, vl.intensity, damp);
      } else {
        pl.intensity = THREE.MathUtils.lerp(pl.intensity, 0.0, damp);
      }
    }
  }

  /**
   * Generates a crisp 1024x1024 architectural West-window Gobo projection cookie:
   * - Top 46%: 22 angled Venetian blind horizontal slat bars w/ optical solar penumbra + fine lift cords
   * - Full height: 4-bay matte-black industrial steel window mullions & horizontal transoms
   * - Lower glass edges: organic cantilevered balcony bamboo culm & lance-leaf dappling
   */
  private createVenetianBlindsGobo(): THREE.CanvasTexture {
    const size = 1024;
    const canvas = document.createElement('canvas');
    canvas.width = size;
    canvas.height = size;
    const ctx = canvas.getContext('2d')!;

    // Strict black surround so zero stray cone light leaks past architectural window piers
    ctx.fillStyle = '#000000';
    ctx.fillRect(0, 0, size, size);

    const x0 = 112;
    const x1 = 912;
    const y0 = 148;
    const y1 = 876;
    const w = x1 - x0;
    const h = y1 - y0;

    // Bright sunlit glass opening
    ctx.fillStyle = '#ffffff';
    ctx.fillRect(x0, y0, w, h);

    // 1. Upper 54% Venetian Blind horizontal slats (tilted aluminum slats casting crisp parallel sun stripes!)
    const blindBottom = y0 + Math.round(h * 0.54);
    const numSlats = 20;
    const pitch = (blindBottom - y0) / numSlats;
    ctx.save();
    ctx.fillStyle = '#000000';
    ctx.shadowColor = 'rgba(0,0,0,0.88)';
    ctx.shadowBlur = 1.6;
    for (let i = 0; i < numSlats; i++) {
      const sy = y0 + i * pitch;
      const barH = pitch * 0.62; // 62% crisp dark slat bar, 38% luminous golden sun slit!
      ctx.fillRect(x0, sy, w, barH);
    }
    // Bottom weighted blind rail + 3 slender vertical lift cords
    ctx.fillRect(x0, blindBottom - 5, w, 10);
    ctx.shadowBlur = 1;
    for (const frac of [0.18, 0.5, 0.82]) {
      ctx.fillRect(x0 + w * frac - 1.5, y0, 3, blindBottom - y0);
    }
    ctx.restore();

    // 2. Industrial Black Steel Window Mullions (4 vertical bays + 4 horizontal transoms matching Arch_LoftWin!)
    ctx.save();
    ctx.fillStyle = '#030305';
    ctx.shadowColor = 'rgba(0,0,0,0.75)';
    ctx.shadowBlur = 2.0;
    for (let i = 0; i <= 4; i++) {
      const mx = x0 + (i / 4) * w;
      const mw = i === 0 || i === 2 || i === 4 ? 14 : 9;
      ctx.fillRect(mx - mw * 0.5, y0 - 4, mw, h + 8);
    }
    for (let j = 0; j <= 5; j++) {
      const my = y0 + (j / 5) * h;
      const mh = j === 0 || j === 5 ? 14 : 8;
      ctx.fillRect(x0 - 4, my - mh * 0.5, w + 8, mh);
    }
    ctx.restore();

    // 3. Subtle organic terrace bamboo silhouette grazing lower glass corners for rich natural outdoor depth
    ctx.save();
    ctx.strokeStyle = 'rgba(0,0,0,0.52)';
    ctx.fillStyle = 'rgba(0,0,0,0.46)';
    ctx.filter = 'blur(3.5px)';
    const drawBambooCluster = (baseX: number, lean: number) => {
      for (let s = 0; s < 3; s++) {
        const bx = baseX + (s - 1) * 28;
        ctx.lineWidth = 5;
        ctx.beginPath();
        ctx.moveTo(bx, y1);
        ctx.quadraticCurveTo(bx + lean * 24, y1 - 150, bx + lean * 58, y1 - 310);
        ctx.stroke();
        for (let l = 0; l < 7; l++) {
          const ly = y1 - 70 - l * 34;
          const lx = bx + lean * (l * 8);
          const side = l % 2 === 0 ? 1 : -1;
          ctx.beginPath();
          ctx.ellipse(lx + side * 24, ly, 26, 5.5, side * -0.35, 0, Math.PI * 2);
          ctx.fill();
        }
      }
    };
    drawBambooCluster(x0 + 85, 1);
    drawBambooCluster(x1 - 95, -1);
    ctx.restore();

    const tex = new THREE.CanvasTexture(canvas);
    tex.colorSpace = THREE.SRGBColorSpace;
    tex.anisotropy = 8;
    tex.needsUpdate = true;
    return tex;
  }

  public setClayLightsMuted(muted: boolean): void {
    if (this.clayLightsMuted === muted) return;
    this.clayLightsMuted = muted;
    this.westWindowLight.visible = !muted;
    this.studioSunSpot.visible = !muted;
    this.livingSunSpot.visible = !muted;
    this.syncLightPool();
  }

  public dispose(): void {
    this.lightmapsWest.forEach((t) => t.dispose());
    this.lightmapsEast.forEach((t) => t.dispose());
    this.skylines.forEach((t) => t.dispose());
    this.pmrems.forEach((t) => t.dispose());
    this.blindsGoboTex.dispose();
    this.skylineMesh.geometry.dispose();
    (this.skylineMesh.material as THREE.Material).dispose();
    this.exteriorCity.dispose();
  }
}
