import * as THREE from 'three';

export interface ColliderDef {
  name: string;
  type: 'bounds' | 'box';
  minX: number;
  maxX: number;
  minZ: number;
  maxZ: number;
}

/**
 * Lightweight 2D Circle-vs-AABB collision solver for butter-smooth First-Person WASD walking.
 * Supports smooth wall sliding (never snags or gets stuck on corners).
 */
export class CollisionWorld {
  private bounds: ColliderDef = {
    name: 'room_bounds',
    type: 'bounds',
    minX: -2.3,
    maxX: 2.3,
    minZ: -1.9,
    maxZ: 1.9,
  };
  private boxes: ColliderDef[] = [];
  private readonly playerRadius = 0.17;

  public load(defs: ColliderDef[]): void {
    this.boxes = [];
    for (const d of defs) {
      if (d.type === 'bounds') {
        this.bounds = d;
      } else {
        this.boxes.push(d);
      }
    }
  }

  public isPositionClear(x: number, z: number, margin = 0.24): boolean {
    if (
      x < this.bounds.minX + margin ||
      x > this.bounds.maxX - margin ||
      z < this.bounds.minZ + margin ||
      z > this.bounds.maxZ - margin
    ) {
      return false;
    }
    const rSq = margin * margin;
    for (const b of this.boxes) {
      const closestX = THREE.MathUtils.clamp(x, b.minX, b.maxX);
      const closestZ = THREE.MathUtils.clamp(z, b.minZ, b.maxZ);
      const dx = x - closestX;
      const dz = z - closestZ;
      if (dx * dx + dz * dz < rSq) {
        return false;
      }
    }
    return true;
  }

  /**
   * Sweeps `offset` around `center` on a horizontal circular arc in direction `dirSign` (+1 or -1)
   * up to `maxAngleRad`, returning the furthest collision-free orbit angle.
   */
  public measureSafeOrbitAngle(
    center: THREE.Vector3,
    offset: THREE.Vector3,
    dirSign: 1 | -1,
    maxAngleRad: number,
    margin = 0.24
  ): number {
    const step = 0.012; // ~0.7 deg steps
    let safe = 0;
    for (let a = step; a <= maxAngleRad + 1e-5; a += step) {
      const ang = Math.min(a, maxAngleRad) * dirSign;
      const cosA = Math.cos(ang);
      const sinA = Math.sin(ang);
      // Matches Three.js Vector3.applyAxisAngle((0, 1, 0), ang)
      const rx = offset.x * cosA + offset.z * sinA;
      const rz = -offset.x * sinA + offset.z * cosA;
      if (!this.isPositionClear(center.x + rx, center.z + rz, margin)) {
        break;
      }
      safe = Math.abs(ang);
    }
    return safe;
  }

  public resolvePosition(pos: THREE.Vector3): void {
    const r = this.playerRadius;
    // 3 iterative sliding passes prevent corner snagging or double-box pinching across doorways
    for (let iter = 0; iter < 3; iter++) {
      // 1. Clamp inside interior room walls
      pos.x = THREE.MathUtils.clamp(pos.x, this.bounds.minX, this.bounds.maxX);
      pos.z = THREE.MathUtils.clamp(pos.z, this.bounds.minZ, this.bounds.maxZ);

      // 2. Push out smoothly from furniture AABB boxes
      for (const b of this.boxes) {
        const closestX = THREE.MathUtils.clamp(pos.x, b.minX, b.maxX);
        const closestZ = THREE.MathUtils.clamp(pos.z, b.minZ, b.maxZ);
        const dx = pos.x - closestX;
        const dz = pos.z - closestZ;
        const distSq = dx * dx + dz * dz;

        if (distSq < r * r) {
          if (distSq > 1e-6) {
            const dist = Math.sqrt(distSq);
            const push = r - dist;
            pos.x += (dx / dist) * push;
            pos.z += (dz / dist) * push;
          } else {
            // Inside box: push along shallowest axis
            const dLeft = Math.abs(pos.x - b.minX);
            const dRight = Math.abs(b.maxX - pos.x);
            const dMinZ = Math.abs(pos.z - b.minZ);
            const dMaxZ = Math.abs(b.maxZ - pos.z);
            const m = Math.min(dLeft, dRight, dMinZ, dMaxZ);
            if (m === dLeft) pos.x = b.minX - r;
            else if (m === dRight) pos.x = b.maxX + r;
            else if (m === dMinZ) pos.z = b.minZ - r;
            else pos.z = b.maxZ + r;
          }
        }
      }
    }
  }
}
