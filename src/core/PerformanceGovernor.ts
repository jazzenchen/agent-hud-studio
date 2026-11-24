import * as THREE from 'three';
import type { PostProcessingPipeline } from './PostProcessing';

export type QualityTier = 'auto' | 'ultra' | 'high' | 'balanced';

export interface PerfSnapshot {
  fps: number;
  frameMs: number;
  drawCalls: number;
  triangles: number;
  pixelRatio: number;
}

/**
 * Adaptive 60 FPS Performance Governor:
 * Monitors EMA frame time and smoothly scales DPR / MSAA in 'auto' mode to keep 60 FPS locked.
 */
export class PerformanceGovernor {
  private tier: QualityTier = 'auto';
  private emaFrameMs = 16.6;
  private frames = 0;
  private lastReportTime = performance.now();
  private lastAdaptTime = performance.now();
  private currentDpr: number;
  private readonly nativeDpr: number;
  private readonly isMobile: boolean;

  private readonly renderer: THREE.WebGLRenderer;
  private readonly postFx: PostProcessingPipeline;
  private readonly onSnapshot: (snap: PerfSnapshot) => void;

  constructor(
    renderer: THREE.WebGLRenderer,
    postFx: PostProcessingPipeline,
    onSnapshot: (snap: PerfSnapshot) => void
  ) {
    this.renderer = renderer;
    this.postFx = postFx;
    this.onSnapshot = onSnapshot;
    this.isMobile =
      (typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches) ||
      /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

    if (this.isMobile) {
      // Mobile GPUs: keep 1.0x crisp CSS resolution + SMAA (3x fewer pixels than 1.75x) & fast post-fx!
      this.nativeDpr = Math.min(window.devicePixelRatio || 1, 1.35);
      this.currentDpr = Math.min(this.nativeDpr, 1.0);
      this.applyDpr(this.currentDpr);
      this.postFx.setQualityMode('fast');
    } else {
      this.nativeDpr = Math.min(window.devicePixelRatio || 1, 2);
      this.currentDpr = Math.min(this.nativeDpr, 1.75);
      this.applyDpr(this.currentDpr);
      this.postFx.setQualityMode('ultra');
    }
  }

  public setTier(tier: QualityTier): void {
    this.tier = tier;
    if (tier === 'ultra') {
      this.applyDpr(this.nativeDpr);
      this.postFx.setQualityMode('ultra');
    } else if (tier === 'high') {
      this.applyDpr(Math.min(this.nativeDpr, 1.75));
      this.postFx.setQualityMode('high');
    } else if (tier === 'balanced') {
      // '60F+' tier: crisp 1.25x Retina + 2x MSAA + SMAA ULTRA!
      this.applyDpr(Math.min(this.nativeDpr, 1.25));
      this.postFx.setQualityMode('fast');
    } else {
      this.applyDpr(Math.min(this.nativeDpr, 1.75));
      this.postFx.setQualityMode('ultra');
    }
  }

  public tick(deltaSec: number): void {
    const ms = Math.min(100, Math.max(1, deltaSec * 1000));
    this.emaFrameMs = this.emaFrameMs * 0.90 + ms * 0.10;
    this.frames++;

    const now = performance.now();
    if (now - this.lastReportTime >= 400) {
      const elapsedSec = (now - this.lastReportTime) / 1000;
      const fps = Math.round(this.frames / elapsedSec);
      const info = this.renderer.info;
      this.onSnapshot({
        fps: Math.min(fps, 144),
        frameMs: this.emaFrameMs,
        drawCalls: info.render.calls,
        triangles: info.render.triangles,
        pixelRatio: this.currentDpr,
      });
      this.frames = 0;
      this.lastReportTime = now;
    }

    // Auto adaptive 60 FPS governor: only step down on sustained heavy load (never oscillate up/down,
    // because resizing WebGL/EffectComposer buffers causes a 1-frame flash!)
    if (this.tier === 'auto' && now - this.lastAdaptTime >= 6000) {
      this.lastAdaptTime = now;
      if (this.isMobile) {
        if (this.emaFrameMs > 28.0 && this.currentDpr > 0.85) {
          this.applyDpr(0.85);
        }
      } else if (this.emaFrameMs > 26.0 && this.currentDpr > 1.25) {
        this.applyDpr(Math.max(1.25, this.currentDpr - 0.25));
      } else if (this.emaFrameMs > 32.0 && this.currentDpr > 1.0) {
        this.applyDpr(1.0);
        this.postFx.setQualityMode('fast');
      }
    }
  }

  private applyDpr(dpr: number): void {
    const next = Number(dpr.toFixed(2));
    if (next === this.currentDpr && this.renderer.getPixelRatio() === next) return;
    this.currentDpr = next;
    this.renderer.setPixelRatio(this.currentDpr);
    this.postFx.setSize(window.innerWidth, window.innerHeight);
  }
}
