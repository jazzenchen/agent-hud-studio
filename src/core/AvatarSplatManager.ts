import * as THREE from 'three';
import { SparkRenderer, SplatMesh } from '@sparkjsdev/spark';
import type { MoodId } from './MoodSystem';

export interface AvatarPose {
  x: number;
  y: number;
  z: number;
  rx: number;
  ry: number;
  rz: number;
  scale: number;
  targetHeight?: number;
}

const MOOD_TINTS: Record<MoodId, THREE.Color> = {
  midnight: new THREE.Color(0.62, 0.68, 0.80),
  daylight: new THREE.Color(0.84, 0.86, 0.90),
  noon: new THREE.Color(0.86, 0.85, 0.82),
  golden: new THREE.Color(0.92, 0.78, 0.64),
};

// Default full-body standing placement on the Studio Loft floor cleanly framed in Studio 1
// (COLMAP OpenCV frame is +Y down -> rx = Math.PI flips upright; ry = Math.PI + 0.22 faces Studio 1!)
const DEFAULT_POSE: AvatarPose = {
  x: 0.22,
  y: 0.86,
  z: -0.38,
  rx: Math.PI,
  ry: Math.PI + 0.22,
  rz: 0,
  scale: 1.0,
  targetHeight: 1.68,
};

export class AvatarSplatManager {
  private readonly scene: THREE.Scene;
  private readonly renderer: THREE.WebGLRenderer;
  private readonly root = new THREE.Group();
  private sparkRenderer: SparkRenderer | null = null;
  private currentMesh: SplatMesh | null = null;
  private currentPose: AvatarPose = { ...DEFAULT_POSE };
  private readonly blendedTint = MOOD_TINTS.midnight.clone();
  private visible = true;

  constructor(renderer: THREE.WebGLRenderer, scene: THREE.Scene) {
    this.renderer = renderer;
    this.scene = scene;
    this.root.name = 'AStudio_3DGS_Avatar_Root';
    this.scene.add(this.root);
    this.installDragDropAndDebugHook();
  }

  private ensureSparkRenderer(): void {
    if (this.sparkRenderer) return;
    this.sparkRenderer = new SparkRenderer({
      renderer: this.renderer,
      blurAmount: 0.0,
      preBlurAmount: 0.0,
    });
    // AStudio renders into a linear HDR EffectComposer followed by AgX ToneMapping + sRGB output.
    // Convert splat sRGB -> Linear here so dark blacks & skin tones aren't double-gamma washed out!
    this.sparkRenderer.defaultView.encodeLinear = true;
    this.scene.add(this.sparkRenderer);
  }

  /**
   * Auto-load default avatar from URL query (?avatar=/assets/avatars/foo.ply)
   * or /assets/avatars/avatar.{ply,spz} if present on the server.
   * The dev server answers /assets/avatars/ from assets/personal/splats/ (git-ignored, never built);
   * a deployed build has no avatar unless one is dropped onto the page.
   */
  public async tryAutoLoad(): Promise<void> {
    const params = new URLSearchParams(window.location.search);
    const explicitUrl = params.get('avatar');
    const candidates = explicitUrl
      ? [explicitUrl]
      : ['/assets/avatars/avatar.ply', '/assets/avatars/avatar.spz'];

    for (const url of candidates) {
      try {
        document.body.dataset.avatarStatus = `fetching:${url}`;
        const res = await fetch(url);
        if (!res.ok) continue;
        const ct = (res.headers.get('content-type') || '').toLowerCase();
        if (ct.includes('text/html')) continue;
        const buf = await res.arrayBuffer();
        const bytes = new Uint8Array(buf);
        // Reject SPA HTML fallback even if content-type header was omitted
        if (bytes.length < 64 || (bytes[0] === 0x3c && (bytes[1] === 0x21 || bytes[1] === 0x68))) {
          continue;
        }
        const fileName = url.split('/').pop() || 'avatar.ply';
        await this.loadFromBytes(bytes, fileName);
        return;
      } catch (err) {
        document.body.dataset.avatarStatus = `error:${String(err)}`;
        console.error('[AStudio Avatar] load failed:', err);
      }
    }
    document.body.dataset.avatarStatus = 'none';
  }

  public async loadFromUrl(url: string, poseOverride?: Partial<AvatarPose>): Promise<void> {
    this.ensureSparkRenderer();
    this.disposeCurrentMesh();
    if (poseOverride) {
      this.currentPose = { ...this.currentPose, ...poseOverride };
    }

    const mesh = new SplatMesh({
      url,
      onLoad: (loaded) => {
        this.normalizeAndPlace(loaded);
      },
    });
    mesh.visible = this.visible;
    mesh.recolor.copy(this.blendedTint);
    this.currentMesh = mesh;
    this.root.add(mesh);
    await mesh.initialized;
  }

  public async loadFromBytes(
    bytes: Uint8Array,
    fileName: string,
    poseOverride?: Partial<AvatarPose>
  ): Promise<void> {
    this.ensureSparkRenderer();
    this.disposeCurrentMesh();
    if (poseOverride) {
      this.currentPose = { ...this.currentPose, ...poseOverride };
    }

    const mesh = new SplatMesh({
      fileBytes: bytes,
      fileName,
      onLoad: (loaded) => {
        this.normalizeAndPlace(loaded);
      },
    });
    mesh.visible = this.visible;
    mesh.recolor.copy(this.blendedTint);
    this.currentMesh = mesh;
    this.root.add(mesh);
    await mesh.initialized;
  }

  private normalizeAndPlace(mesh: SplatMesh): void {
    const box = mesh.getBoundingBox(true);
    const size = new THREE.Vector3();
    const center = new THREE.Vector3();
    box.getSize(size);
    box.getCenter(center);

    // Center the splat cloud around its local origin so rotation/position are intuitive
    const pivot = new THREE.Group();
    pivot.name = 'AStudio_3DGS_Avatar_Pivot';
    this.root.remove(mesh);
    mesh.position.set(-center.x, -center.y, -center.z);
    pivot.add(mesh);

    // Auto-scale to targetHeight (meters) if raw COLMAP/VGGT scale is arbitrary
    const maxDim = Math.max(size.y, size.x, size.z, 1e-4);
    const autoScale = this.currentPose.targetHeight
      ? this.currentPose.targetHeight / maxDim
      : 1.0;

    this.root.clear();
    this.root.add(pivot);
    this.applyPose(autoScale);
    const count = mesh.packedSplats?.numSplats ?? 0;
    document.body.dataset.avatarStatus = `loaded:${count}:size=${size.x.toFixed(2)}x${size.y.toFixed(2)}x${size.z.toFixed(2)}:scale=${autoScale.toFixed(3)}`;
    console.info('[AStudio Avatar]', document.body.dataset.avatarStatus);
  }

  private applyPose(baseAutoScale = 1.0): void {
    const p = this.currentPose;
    this.root.position.set(p.x, p.y, p.z);
    this.root.rotation.set(p.rx, p.ry, p.rz);
    const s = baseAutoScale * p.scale;
    this.root.scale.setScalar(s);
  }

  public setPose(partial: Partial<AvatarPose>): void {
    this.currentPose = { ...this.currentPose, ...partial };
    this.root.position.set(this.currentPose.x, this.currentPose.y, this.currentPose.z);
    this.root.rotation.set(this.currentPose.rx, this.currentPose.ry, this.currentPose.rz);
    if (partial.scale !== undefined) {
      this.root.scale.setScalar(this.currentPose.scale);
    }
  }

  public setVisible(v: boolean): void {
    this.visible = v;
    this.root.visible = v;
    if (this.currentMesh) this.currentMesh.visible = v;
  }

  /**
   * Sync avatar splat tint smoothly with AStudio's 4 lighting presets.
   */
  public blendMood(from: MoodId, to: MoodId, t: number): void {
    const cFrom = MOOD_TINTS[from] ?? MOOD_TINTS.midnight;
    const cTo = MOOD_TINTS[to] ?? MOOD_TINTS.midnight;
    this.blendedTint.copy(cFrom).lerp(cTo, THREE.MathUtils.clamp(t, 0, 1));
    if (this.currentMesh) {
      this.currentMesh.recolor.copy(this.blendedTint);
    }
  }

  private disposeCurrentMesh(): void {
    if (this.currentMesh) {
      this.currentMesh.dispose();
      this.currentMesh = null;
    }
    this.root.clear();
  }

  private installDragDropAndDebugHook(): void {
    window.addEventListener('dragover', (e) => {
      e.preventDefault();
    });
    window.addEventListener('drop', async (e) => {
      e.preventDefault();
      const file = e.dataTransfer?.files?.[0];
      if (!file) return;
      if (!/\.(ply|spz|splat|ksplat)$/i.test(file.name)) return;
      const bytes = new Uint8Array(await file.arrayBuffer());
      await this.loadFromBytes(bytes, file.name);
      console.info(`[AStudio Avatar] Loaded dropped splat: ${file.name}`);
    });

    (window as unknown as Record<string, unknown>).__ASTUDIO_AVATAR__ = {
      loadUrl: (url: string, pose?: Partial<AvatarPose>) => this.loadFromUrl(url, pose),
      setPose: (pose: Partial<AvatarPose>) => this.setPose(pose),
      setVisible: (v: boolean) => this.setVisible(v),
      getPose: () => ({ ...this.currentPose }),
      getStatus: () => ({
        loaded: Boolean(this.currentMesh?.isInitialized),
        numSplats: this.currentMesh?.packedSplats?.numSplats ?? 0,
        visible: this.visible,
        rootPos: this.root.position.toArray(),
        rootScale: this.root.scale.toArray(),
      }),
    };
  }
}
