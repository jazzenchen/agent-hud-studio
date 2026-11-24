import * as THREE from 'three';
import { OrbitControls } from 'three/examples/jsm/controls/OrbitControls.js';
import { PointerLockControls } from 'three/examples/jsm/controls/PointerLockControls.js';
import type { CollisionWorld } from './CollisionWorld';

export type CameraPresetId =
  | 'hero'
  | 'living'
  | 'kitchen'
  | 'bedroom'
  | 'bathroom'
  | 'desk'
  | 'window'
  | 'shelf'
  | 'vista'
  | 'pc'
  | 'pegboard'
  | 'maker';

interface CameraPreset {
  pos: THREE.Vector3;
  target: THREE.Vector3;
  fov: number;
}

// Blender (x, y, z) -> Three.js (x, z, -y) exact Full 5-Zone Tokyo Penthouse Loft Camera Presets!
const PRESETS: Record<CameraPresetId, CameraPreset> = {
  // 1. Zone 1 Studio Hero (Angled slightly left toward Desk & West Window Skyline, clear of walls/piers)
  hero: {
    pos: new THREE.Vector3(0.18, 1.24, 1.66),
    target: new THREE.Vector3(-0.32, 1.26, -1.42),
    fov: 54,
  },
  // 2. Zone 2 Living & 77" OLED Console Gaming Lounge (Sofa, Walnut Coffee Table, PS5, Atmos Towers, Balcony!)
  living: {
    pos: new THREE.Vector3(3.62, 1.38, 2.15),
    target: new THREE.Vector3(0.35, 0.94, 4.78),
    fov: 54,
  },
  // 3. Zone 3 Open Kitchen & Dark Calacatta Marble Waterfall Espresso Bar Island (Espresso, Grinder, 3 Stools, Ring LED!)
  kitchen: {
    pos: new THREE.Vector3(3.05, 1.44, 2.48),
    target: new THREE.Vector3(4.45, 1.02, -1.25),
    fov: 52,
  },
  // 4. Zone 4 Master Bedroom (Fluted-Glass Steel Partition, Floating JP Walnut Bed, Smoked-Glass Wardrobe!)
  bedroom: {
    pos: new THREE.Vector3(5.12, 1.38, 2.08),
    target: new THREE.Vector3(8.62, 0.92, 3.72),
    fov: 54,
  },
  // 5. Zone 5 Modern Dark-Slate Spa Bathroom (stepped inside past ajar privacy door for 100% unobstructed tub + vanity + mirror view!)
  bathroom: {
    pos: new THREE.Vector3(7.62, 1.40, 0.42),
    target: new THREE.Vector3(8.58, 0.98, -1.08),
    fov: 62,
  },
  // 6. Studio Desk & Official Apple MacBook Air 15" Macro
  desk: {
    pos: new THREE.Vector3(0.54, 1.18, -0.34),
    target: new THREE.Vector3(-0.24, 0.94, -1.44),
    fov: 40,
  },
  // 7. West Steel-Grid Window, Reading Nook & Cantilevered Penthouse Terrace View
  window: {
    pos: new THREE.Vector3(0.88, 1.30, -0.35),
    target: new THREE.Vector3(-1.72, 0.98, 0.62),
    fov: 50,
  },
  // 8. East Geek Gallery Bookshelf (Macintosh 1984, Mac Studio/mini, Zaku, Turntable) & Maker Workbench
  shelf: {
    pos: new THREE.Vector3(-0.46, 1.36, -0.24),
    target: new THREE.Vector3(1.90, 1.18, -0.62),
    fov: 52,
  },
  // 9. Cross-Loft Architectural Vista (Studio -> Open Steel Portal -> Living Lounge -> Fluted Glass Bedroom!)
  vista: {
    pos: new THREE.Vector3(-0.85, 1.42, -0.42),
    target: new THREE.Vector3(3.35, 1.02, 4.10),
    fov: 56,
  },
  // Extra macro shortcuts
  pc: {
    pos: new THREE.Vector3(0.14, 0.56, -0.72),
    target: new THREE.Vector3(0.84, 0.28, -1.48),
    fov: 40,
  },
  pegboard: {
    pos: new THREE.Vector3(1.16, 1.44, -1.10),
    target: new THREE.Vector3(1.16, 1.44, -2.02),
    fov: 40,
  },
  maker: {
    pos: new THREE.Vector3(-0.08, 1.30, 0.78),
    target: new THREE.Vector3(1.88, 0.88, 0.62),
    fov: 44,
  },
};

/**
 * Dual-Mode ArchViz Camera System:
 * 1. Tour Mode (Default): Smooth damped OrbitControls + cubic-bezier fly-to presets
 * 2. Walk Mode (V key / HUD button): PointerLock First-Person WASD + Shift walk with head-bob & AABB collision
 */
export class DualCameraController {
  public readonly camera: THREE.PerspectiveCamera;
  private readonly orbit: OrbitControls;
  private readonly pointerLock: PointerLockControls;
  private readonly collision: CollisionWorld;

  private mode: 'tour' | 'walk' = 'tour';
  private activePreset: CameraPresetId = 'hero';

  // Fly-to animation state
  private isFlying = false;
  private flyT = 1;
  private readonly flyDuration = 1.05;
  private readonly flyStartPos = new THREE.Vector3();
  private readonly flyEndPos = new THREE.Vector3();
  private readonly flyStartTarget = new THREE.Vector3();
  private readonly flyEndTarget = new THREE.Vector3();
  private flyStartFov = 50;
  private flyEndFov = 50;

  // Slow cinematic circular-arc orbit (Tour mode only: orbits camera around target along XZ circle with collision self-correction)
  private autoPanEnabled = true;
  private isUserInteracting = false;
  private panResumeCountdown = 0;
  private readonly panResumeDelay = 3.8; // Pause ~3.8s after user drag/zoom, then resume from their angle
  private panAnchorValid = false;
  private panPhase = 0;
  private readonly panSpeed = (Math.PI * 2) / 38; // ~38s per full left-right-left arc sweep
  private panCenterAngle = 0;
  private panHalfAngle = 0;
  private readonly panBaseTarget = new THREE.Vector3();
  private readonly panBaseOffset = new THREE.Vector3();
  private readonly panTmpOffset = new THREE.Vector3();
  private readonly worldUp = new THREE.Vector3(0, 1, 0);

  // First-person movement state
  private readonly keys = new Set<string>();
  private readonly velocity = new THREE.Vector3();
  private readonly forward = new THREE.Vector3();
  private readonly right = new THREE.Vector3();
  private bobPhase = 0;
  private readonly eyeHeight = 1.42;

  private readonly onModeChange: (mode: 'tour' | 'walk') => void;
  private readonly onPresetChange: (preset: CameraPresetId) => void;
  private readonly onAutoPanChange?: (active: boolean) => void;

  constructor(
    domElement: HTMLElement,
    collision: CollisionWorld,
    onModeChange: (mode: 'tour' | 'walk') => void,
    onPresetChange: (preset: CameraPresetId) => void,
    onAutoPanChange?: (active: boolean) => void
  ) {
    this.collision = collision;
    this.onModeChange = onModeChange;
    this.onPresetChange = onPresetChange;
    this.onAutoPanChange = onAutoPanChange;

    this.camera = new THREE.PerspectiveCamera(PRESETS.hero.fov, window.innerWidth / window.innerHeight, 0.06, 480);
    this.camera.position.copy(PRESETS.hero.pos);

    this.orbit = new OrbitControls(this.camera, domElement);
    this.orbit.enableDamping = true;
    this.orbit.dampingFactor = 0.065;
    this.orbit.rotateSpeed = 0.68;
    this.orbit.zoomSpeed = 0.85;
    this.orbit.panSpeed = 0.65;
    this.orbit.minDistance = 0.45;
    this.orbit.maxDistance = 7.8;
    this.orbit.maxPolarAngle = Math.PI * 0.56;
    this.orbit.minPolarAngle = Math.PI * 0.16;
    this.orbit.target.copy(PRESETS.hero.target);
    this.orbit.update();
    this.capturePanAnchor();

    // Pause slow pan while user drags/zooms, then resume smoothly from the user's new angle after a short dwell
    this.orbit.addEventListener('start', () => {
      this.isFlying = false;
      this.isUserInteracting = true;
      this.panAnchorValid = false;
      this.panResumeCountdown = this.panResumeDelay;
    });
    this.orbit.addEventListener('end', () => {
      this.isUserInteracting = false;
      this.panAnchorValid = false;
      this.panResumeCountdown = this.panResumeDelay;
    });

    this.pointerLock = new PointerLockControls(this.camera, domElement);
    this.pointerLock.addEventListener('unlock', () => {
      if (this.mode === 'walk') {
        this.exitWalkMode();
      }
    });

    window.addEventListener('keydown', this.handleKeyDown);
    window.addEventListener('keyup', this.handleKeyUp);
  }

  public getMode(): 'tour' | 'walk' {
    return this.mode;
  }

  public getActivePreset(): CameraPresetId {
    return this.activePreset;
  }

  public getFocusDistance(): number {
    return this.camera.position.distanceTo(this.orbit.target);
  }

  public isAutoPanEnabled(): boolean {
    return this.autoPanEnabled;
  }

  public setAutoPan(enabled: boolean): void {
    if (this.autoPanEnabled === enabled) return;
    this.autoPanEnabled = enabled;
    this.panResumeCountdown = 0;
    this.panAnchorValid = false;
    if (enabled && this.mode === 'tour' && !this.isFlying && !this.isUserInteracting) {
      this.capturePanAnchor();
    }
    this.onAutoPanChange?.(enabled);
  }

  public refreshPanBounds(): void {
    if (this.autoPanEnabled && this.mode === 'tour' && !this.isFlying && !this.isUserInteracting) {
      this.capturePanAnchor();
    }
  }

  private capturePanAnchor(): void {
    // Self-correction: level horizon, clamp position safely inside loft walls, snapshot immutable orbit center & radius,
    // and probe CollisionWorld along both circular arc directions so orbiting NEVER clips into walls or furniture!
    this.camera.up.set(0, 1, 0);
    this.camera.position.x = THREE.MathUtils.clamp(this.camera.position.x, -1.92, 9.16);
    this.camera.position.z = THREE.MathUtils.clamp(this.camera.position.z, -1.80, 5.18);
    this.camera.position.y = THREE.MathUtils.clamp(this.camera.position.y, 0.42, 2.52);

    this.panBaseTarget.copy(this.orbit.target);
    this.panBaseOffset.copy(this.camera.position).sub(this.panBaseTarget);

    const horizRadius = Math.hypot(this.panBaseOffset.x, this.panBaseOffset.z);
    if (horizRadius < 0.25) {
      this.panCenterAngle = 0;
      this.panHalfAngle = 0;
      this.panPhase = 0;
      this.panAnchorValid = true;
      return;
    }

    const isTight =
      this.activePreset === 'desk' ||
      this.activePreset === 'bathroom' ||
      this.activePreset === 'pc' ||
      this.activePreset === 'pegboard' ||
      this.activePreset === 'maker';
    // Gentle circular arc: ±10° in wide rooms, ±7° in tight/macro views
    const desiredMaxAngle = ((isTight ? 7 : 10) * Math.PI) / 180;

    const maxPos = this.collision.measureSafeOrbitAngle(
      this.panBaseTarget,
      this.panBaseOffset,
      1,
      desiredMaxAngle,
      0.24
    );
    const maxNeg = this.collision.measureSafeOrbitAngle(
      this.panBaseTarget,
      this.panBaseOffset,
      -1,
      desiredMaxAngle,
      0.24
    );

    const totalSafe = maxPos + maxNeg;
    if (totalSafe < 0.025) {
      this.panCenterAngle = 0;
      this.panHalfAngle = 0;
      this.panPhase = 0;
    } else {
      // Self-correction: center the arc inside [-maxNeg, +maxPos] and start at exact phase where angle == 0 (zero jump, zero drift!)
      this.panCenterAngle = (maxPos - maxNeg) * 0.5;
      this.panHalfAngle = totalSafe * 0.5;
      const ratio = THREE.MathUtils.clamp(-this.panCenterAngle / this.panHalfAngle, -1, 1);
      this.panPhase = Math.asin(ratio);
    }
    this.panAnchorValid = true;
  }

  public flyToPreset(id: CameraPresetId, instant = false): void {
    if (this.mode === 'walk') {
      this.exitWalkMode();
    }
    const preset = PRESETS[id];
    this.activePreset = id;
    this.onPresetChange(id);

    if (instant) {
      this.camera.position.copy(preset.pos);
      this.orbit.target.copy(preset.target);
      this.camera.fov = preset.fov;
      this.camera.updateProjectionMatrix();
      this.orbit.update();
      this.isFlying = false;
      this.capturePanAnchor();
      return;
    }

    this.flyStartPos.copy(this.camera.position);
    this.flyEndPos.copy(preset.pos);
    this.flyStartTarget.copy(this.orbit.target);
    this.flyEndTarget.copy(preset.target);
    this.flyStartFov = this.camera.fov;
    this.flyEndFov = preset.fov;
    this.flyT = 0;
    this.isFlying = true;
  }

  public setRawCamera(pos: [number, number, number], target: [number, number, number], fov = 42): void {
    if (this.mode === 'walk') {
      this.exitWalkMode();
    }
    this.isFlying = false;
    this.setAutoPan(false);
    this.camera.position.set(pos[0], pos[1], pos[2]);
    this.orbit.target.set(target[0], target[1], target[2]);
    this.camera.fov = fov;
    this.camera.updateProjectionMatrix();
    this.orbit.update();
  }

  public toggleWalkMode(): void {
    if (this.mode === 'walk') {
      this.exitWalkMode();
    } else {
      this.enterWalkMode();
    }
  }

  public enterWalkMode(): void {
    this.isFlying = false;
    this.mode = 'walk';
    this.orbit.enabled = false;
    this.camera.fov = 58;
    this.camera.updateProjectionMatrix();
    this.camera.position.y = this.eyeHeight;
    this.collision.resolvePosition(this.camera.position);
    this.pointerLock.lock();
    this.onModeChange('walk');
  }

  public exitWalkMode(): void {
    this.mode = 'tour';
    this.keys.clear();
    if (document.pointerLockElement) {
      document.exitPointerLock();
    }
    // Hand target cleanly back to OrbitControls 1.6m ahead of where user was looking
    const lookDir = new THREE.Vector3();
    this.camera.getWorldDirection(lookDir);
    this.orbit.target.copy(this.camera.position).addScaledVector(lookDir, 1.6);
    this.orbit.enabled = true;
    this.camera.fov = PRESETS[this.activePreset].fov;
    this.camera.updateProjectionMatrix();
    if (this.autoPanEnabled) {
      this.capturePanAnchor();
    }
    this.onModeChange('tour');
  }

  public resize(width: number, height: number): void {
    this.camera.aspect = width / height;
    this.camera.updateProjectionMatrix();
  }

  public update(delta: number): void {
    if (this.mode === 'tour') {
      if (this.isFlying) {
        this.flyT = Math.min(1, this.flyT + delta / this.flyDuration);
        const ease = 1 - Math.pow(1 - this.flyT, 3);
        this.camera.position.lerpVectors(this.flyStartPos, this.flyEndPos, ease);
        this.orbit.target.lerpVectors(this.flyStartTarget, this.flyEndTarget, ease);
        this.camera.fov = THREE.MathUtils.lerp(this.flyStartFov, this.flyEndFov, ease);
        this.camera.updateProjectionMatrix();
        if (this.flyT >= 1) {
          this.isFlying = false;
          this.panResumeCountdown = 0;
          this.capturePanAnchor();
        }
      } else if (this.autoPanEnabled && !this.isUserInteracting) {
        if (this.panResumeCountdown > 0) {
          this.panResumeCountdown = Math.max(0, this.panResumeCountdown - delta);
        } else {
          if (!this.panAnchorValid) {
            this.capturePanAnchor();
          }
          if (this.panHalfAngle > 0.001) {
            this.panPhase += delta * this.panSpeed;
            const angle = this.panCenterAngle + Math.sin(this.panPhase) * this.panHalfAngle;
            // Orbit camera along horizontal circle around target (fixed focal point, zero wall clipping!)
            this.panTmpOffset.copy(this.panBaseOffset).applyAxisAngle(this.worldUp, angle);
            this.camera.position.copy(this.panBaseTarget).add(this.panTmpOffset);
            this.orbit.target.copy(this.panBaseTarget);
          }
        }
      }
      // Keep orbit camera comfortably inside the full 5-zone 87 m^2 penthouse loft bounds!
      this.camera.position.x = THREE.MathUtils.clamp(this.camera.position.x, -1.98, 9.24);
      this.camera.position.z = THREE.MathUtils.clamp(this.camera.position.z, -1.86, 5.28);
      this.camera.position.y = THREE.MathUtils.clamp(this.camera.position.y, 0.35, 2.58);
      this.orbit.update();
      return;
    }

    // First-person WASD walking with smooth damping & AABB sliding collision
    const moveZ = (this.keys.has('KeyW') || this.keys.has('ArrowUp') ? 1 : 0) -
      (this.keys.has('KeyS') || this.keys.has('ArrowDown') ? 1 : 0);
    const moveX = (this.keys.has('KeyD') || this.keys.has('ArrowRight') ? 1 : 0) -
      (this.keys.has('KeyA') || this.keys.has('ArrowLeft') ? 1 : 0);

    const speed = this.keys.has('ShiftLeft') || this.keys.has('ShiftRight') ? 3.8 : 2.25;
    this.camera.getWorldDirection(this.forward);
    this.forward.y = 0;
    this.forward.normalize();
    this.right.crossVectors(this.forward, THREE.Object3D.DEFAULT_UP).normalize();

    const targetVel = new THREE.Vector3();
    if (moveZ !== 0 || moveX !== 0) {
      targetVel
        .addScaledVector(this.forward, moveZ)
        .addScaledVector(this.right, moveX)
        .normalize()
        .multiplyScalar(speed);
    }

    const damp = 1 - Math.exp(-10 * delta);
    this.velocity.lerp(targetVel, damp);
    this.camera.position.addScaledVector(this.velocity, delta);
    this.collision.resolvePosition(this.camera.position);

    // Subtle organic walking head-bob
    const horizSpeed = Math.hypot(this.velocity.x, this.velocity.z);
    if (horizSpeed > 0.12) {
      this.bobPhase += delta * (7.5 + horizSpeed * 1.4);
      this.camera.position.y = this.eyeHeight + Math.sin(this.bobPhase) * 0.018;
    } else {
      this.camera.position.y = THREE.MathUtils.lerp(this.camera.position.y, this.eyeHeight, damp);
    }
  }

  public dispose(): void {
    window.removeEventListener('keydown', this.handleKeyDown);
    window.removeEventListener('keyup', this.handleKeyUp);
    this.orbit.dispose();
    this.pointerLock.dispose();
  }

  private readonly handleKeyDown = (e: KeyboardEvent): void => {
    this.keys.add(e.code);
  };

  private readonly handleKeyUp = (e: KeyboardEvent): void => {
    this.keys.delete(e.code);
  };
}
