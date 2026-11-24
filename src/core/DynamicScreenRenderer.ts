import * as THREE from 'three';
import type { AudioReactiveFrame } from './StudioAudioEngine';

export type ScreenMode = 'agenthud' | 'ide' | 'obs' | 'visualizer';
export type TvChannel = 'agenthud' | 'ps5' | 'lofi' | 'cinema';

interface ScreenEntry {
  canvas: HTMLCanvasElement;
  ctx: CanvasRenderingContext2D;
  texture: THREE.CanvasTexture;
  interval: number;
  accum: number;
  draw: (t: number, mode: ScreenMode, force: boolean) => boolean;
}

/**
 * High-framerate (60 FPS) offscreen CanvasTexture renderer with static-layer caching.
 * Drives the 38" Curved Ultrawide OLED, 27" Vertical Telemetry/Chat Monitor,
 * Stream Deck MK.2, and the Living Lounge 77" 4K OLED Cinema TV / MacBook Pro.
 */
export class DynamicScreenRenderer {
  public readonly ultrawideTexture: THREE.CanvasTexture;
  public readonly verticalTexture: THREE.CanvasTexture;
  public readonly streamDeckTexture: THREE.CanvasTexture;
  public readonly livingTvTexture: THREE.CanvasTexture;

  private mode: ScreenMode = 'agenthud';
  private tvChannel: TvChannel = 'agenthud';
  private readonly screens: ScreenEntry[] = [];
  private readonly tvEntry: ScreenEntry;
  private readonly staticCache = new Map<string, HTMLCanvasElement>();
  private latestAudio?: AudioReactiveFrame;

  // Change-detection caches for low-frequency screens
  private lastStreamDeckPulse = -1;
  private lastPs5Colon: boolean | null = null;
  private ideCursorX = 0;
  private visualizerGrad: CanvasGradient | null = null;

  constructor() {
    // 1 / 75 (~13.3ms) locks cleanly to 60 FPS on 60Hz (every frame) and 120Hz ProMotion (every 2nd frame)
    const smoothInterval = 1 / 75;

    const uw = this.createScreen(1024, 432, smoothInterval, (t, m) => {
      this.drawUltrawide(uw.ctx, 1024, 432, t, m);
      return true;
    });
    const vert = this.createScreen(448, 768, smoothInterval, (t, m) => {
      this.drawVertical(vert.ctx, 448, 768, t, m);
      return true;
    });
    const sd = this.createScreen(320, 192, 1 / 12, (t, _m, force) =>
      this.drawStreamDeck(sd.ctx, 320, 192, t, force)
    );
    const tv = this.createScreen(1024, 576, smoothInterval, (t, _m, force) =>
      this.drawLivingTv(tv.ctx, 1024, 576, t, this.tvChannel, force)
    );

    this.screens.push(uw, vert, sd, tv);
    this.tvEntry = tv;
    this.ultrawideTexture = uw.texture;
    this.verticalTexture = vert.texture;
    this.streamDeckTexture = sd.texture;
    this.livingTvTexture = tv.texture;

    // Initial full draw so frame 1 is crisp immediately
    for (const s of this.screens) {
      s.draw(0, this.mode, true);
      s.texture.needsUpdate = true;
    }
  }

  public getMode(): ScreenMode {
    return this.mode;
  }

  public cycleMode(): ScreenMode {
    const order: ScreenMode[] = ['agenthud', 'ide', 'obs', 'visualizer'];
    this.mode = order[(order.indexOf(this.mode) + 1) % order.length];
    const nowSec = performance.now() * 0.001;
    for (const s of this.screens) {
      s.accum = 0;
      s.draw(nowSec, this.mode, true);
      s.texture.needsUpdate = true;
    }
    return this.mode;
  }

  public cycleTvChannel(): TvChannel {
    const order: TvChannel[] = ['agenthud', 'ps5', 'lofi', 'cinema'];
    this.tvChannel = order[(order.indexOf(this.tvChannel) + 1) % order.length];
    this.lastPs5Colon = null;
    this.tvEntry.accum = 0;
    this.tvEntry.draw(performance.now() * 0.001, this.mode, true);
    this.tvEntry.texture.needsUpdate = true;
    return this.tvChannel;
  }

  public update(delta: number, elapsed: number, audio?: AudioReactiveFrame): void {
    this.latestAudio = audio;
    for (const entry of this.screens) {
      entry.accum += delta;
      if (entry.accum < entry.interval) continue;
      entry.accum = 0;
      if (entry.draw(elapsed, this.mode, false)) {
        entry.texture.needsUpdate = true;
      }
    }
  }

  public dispose(): void {
    for (const s of this.screens) {
      s.texture.dispose();
    }
    this.staticCache.clear();
  }

  private createScreen(
    w: number,
    h: number,
    interval: number,
    draw: (t: number, m: ScreenMode, force: boolean) => boolean
  ): ScreenEntry {
    const canvas = document.createElement('canvas');
    canvas.width = w;
    canvas.height = h;
    const ctx = canvas.getContext('2d', { alpha: false })!;
    const texture = new THREE.CanvasTexture(canvas);
    texture.colorSpace = THREE.SRGBColorSpace;
    texture.flipY = false; // Matches Blender glTF UV convention!
    texture.anisotropy = 4;
    return { canvas, ctx, texture, interval, accum: 0, draw };
  }

  private getStaticLayer(
    key: string,
    w: number,
    h: number,
    renderStatic: (ctx: CanvasRenderingContext2D) => void
  ): HTMLCanvasElement {
    let cached = this.staticCache.get(key);
    if (!cached) {
      cached = document.createElement('canvas');
      cached.width = w;
      cached.height = h;
      const sctx = cached.getContext('2d', { alpha: false })!;
      renderStatic(sctx);
      this.staticCache.set(key, cached);
    }
    return cached;
  }

  private roundRect(ctx: CanvasRenderingContext2D, x: number, y: number, rw: number, rh: number, r: number): void {
    ctx.beginPath();
    ctx.moveTo(x + r, y);
    ctx.arcTo(x + rw, y, x + rw, y + rh, r);
    ctx.arcTo(x + rw, y + rh, x, y + rh, r);
    ctx.arcTo(x, y + rh, x, y, r);
    ctx.arcTo(x, y, x + rw, y, r);
    ctx.closePath();
  }

  private drawUltrawide(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, mode: ScreenMode): void {
    if (mode === 'agenthud') {
      const midX = 376;
      const midY = 56;
      const midW = 336;
      const midH = 348;
      const rx = 728;
      const rw = 268;
      const spY = midY + 160;

      const staticLayer = this.getStaticLayer('uw:agenthud', w, h, (sctx) => {
        // 21:9 Ultrawide Agent HUD Command Center & Brand Showcase (agenthud.app)
        const bg = sctx.createLinearGradient(0, 0, w, h);
        bg.addColorStop(0, '#050811');
        bg.addColorStop(0.5, '#0a1222');
        bg.addColorStop(1, '#060913');
        sctx.fillStyle = bg;
        sctx.fillRect(0, 0, w, h);

        // Subtle architectural grid
        sctx.strokeStyle = 'rgba(148, 163, 184, 0.045)';
        sctx.lineWidth = 1;
        sctx.beginPath();
        for (let gx = 40; gx < w; gx += 40) {
          sctx.moveTo(gx, 0);
          sctx.lineTo(gx, h);
        }
        for (let gy = 40; gy < h; gy += 40) {
          sctx.moveTo(0, gy);
          sctx.lineTo(w, gy);
        }
        sctx.stroke();

        // Soft ambient OLED glows
        const g1 = sctx.createRadialGradient(540, 160, 12, 540, 160, 290);
        g1.addColorStop(0, 'rgba(56, 189, 248, 0.22)');
        g1.addColorStop(1, 'rgba(5, 8, 17, 0)');
        sctx.fillStyle = g1;
        sctx.fillRect(0, 0, w, h);

        const g2 = sctx.createRadialGradient(170, 340, 10, 170, 340, 230);
        g2.addColorStop(0, 'rgba(245, 158, 72, 0.18)');
        g2.addColorStop(1, 'rgba(5, 8, 17, 0)');
        sctx.fillStyle = g2;
        sctx.fillRect(0, 0, w, h);

        // Top macOS Menu Bar
        sctx.fillStyle = 'rgba(8, 12, 22, 0.9)';
        sctx.fillRect(0, 0, w, 30);
        sctx.fillStyle = '#e2e8f0';
        sctx.font = '700 11px Menlo, monospace';
        sctx.fillText('● AGENT HUD', 18, 19);
        sctx.fillStyle = '#64748b';
        sctx.font = '10px Menlo, monospace';
        sctx.fillText('MACOS · WINDOWS · LINUX · IOS', 118, 19);
        sctx.fillStyle = '#38bdf8';
        sctx.font = 'bold 11px Menlo, monospace';
        sctx.fillText('agenthud.app ↗', w - 120, 19);

        // LEFT COLUMN: Brand Hero & CTA (x: 28..356)
        sctx.fillStyle = '#38bdf8';
        sctx.font = '700 11px Menlo, monospace';
        sctx.fillText('HEADS-UP DISPLAY FOR AI CODING AGENTS', 30, 86);

        sctx.fillStyle = '#ffffff';
        sctx.font = '800 44px -apple-system, BlinkMacSystemFont, sans-serif';
        sctx.fillText('Agent HUD', 28, 138);

        sctx.fillStyle = '#cbd5e1';
        sctx.font = '500 16px -apple-system, BlinkMacSystemFont, sans-serif';
        sctx.fillText('Every Agent. Every Quota. One Glance.', 30, 168);

        const bullets = [
          { col: '#f59e48', txt: 'Live Quota & Token Rings (Claude · Codex · Gemini)' },
          { col: '#38bdf8', txt: 'Floating Notch HUD + Unified Parallel Sessions' },
          { col: '#4ade80', txt: 'iPhone & Apple Watch Remote · Voice Coding' },
        ];
        bullets.forEach((b, idx) => {
          const by = 204 + idx * 34;
          sctx.fillStyle = b.col;
          sctx.beginPath();
          sctx.arc(36, by - 4, 3.8, 0, Math.PI * 2);
          sctx.fill();
          sctx.fillStyle = '#cbd5e1';
          sctx.font = '12px -apple-system, sans-serif';
          sctx.fillText(b.txt, 48, by);
        });

        // Glowing Primary CTA Pill
        const ctaX = 30;
        const ctaY = 326;
        const ctaW = 214;
        const ctaH = 44;
        const ctaGrad = sctx.createLinearGradient(ctaX, ctaY, ctaX + ctaW, ctaY + ctaH);
        ctaGrad.addColorStop(0, '#f8fafc');
        ctaGrad.addColorStop(1, '#dbeafe');
        this.roundRect(sctx, ctaX, ctaY, ctaW, ctaH, 22);
        sctx.fillStyle = ctaGrad;
        sctx.fill();
        sctx.fillStyle = '#070b14';
        sctx.font = '800 16px Menlo, monospace';
        sctx.fillText('agenthud.app  ↗', ctaX + 28, ctaY + 27);

        sctx.fillStyle = 'rgba(148, 163, 184, 0.85)';
        sctx.font = '10px Menlo, monospace';
        sctx.fillText('CLICK SCREEN TO VISIT', ctaX + 36, ctaY + 62);

        // CENTER COLUMN: Live Parallel Agent Sessions Card (x: 376..712)
        this.roundRect(sctx, midX, midY, midW, midH, 14);
        sctx.fillStyle = 'rgba(10, 16, 30, 0.88)';
        sctx.fill();
        sctx.strokeStyle = 'rgba(148, 163, 184, 0.20)';
        sctx.lineWidth = 1;
        sctx.stroke();

        sctx.fillStyle = '#94a3b8';
        sctx.font = '700 10px Menlo, monospace';
        sctx.fillText('PARALLEL AGENT SESSIONS', midX + 16, midY + 24);
        sctx.fillStyle = '#4ade80';
        sctx.fillText('● SYNCED', midX + midW - 68, midY + 24);

        const sessions = [
          {
            name: 'Claude Code',
            task: 'Refactoring WebGL2 lighting shaders',
            status: 'EDITING',
            col: '#f59e48',
            tok: '24.8k',
          },
          {
            name: 'OpenAI Codex',
            task: 'Running TypeScript & build checks',
            status: 'TESTING',
            col: '#4ade80',
            tok: '16.2k',
          },
          {
            name: 'Gemini Agent',
            task: 'Designing Tokyo Loft OLED UI',
            status: 'ACTIVE',
            col: '#38bdf8',
            tok: '31.5k',
          },
        ];
        sessions.forEach((s, i) => {
          const sy = midY + 38 + i * 68;
          this.roundRect(sctx, midX + 14, sy, midW - 28, 58, 9);
          sctx.fillStyle = 'rgba(20, 30, 52, 0.78)';
          sctx.fill();
          sctx.strokeStyle = 'rgba(148, 163, 184, 0.12)';
          sctx.stroke();

          sctx.fillStyle = s.col;
          sctx.beginPath();
          sctx.arc(midX + 28, sy + 20, 4, 0, Math.PI * 2);
          sctx.fill();

          sctx.fillStyle = '#f8fafc';
          sctx.font = '700 12px -apple-system, sans-serif';
          sctx.fillText(s.name, midX + 40, sy + 23);

          sctx.fillStyle = s.col;
          sctx.font = '700 9px Menlo, monospace';
          sctx.fillText(s.status, midX + midW - 116, sy + 22);

          sctx.fillStyle = '#94a3b8';
          sctx.font = '9px Menlo, monospace';
          sctx.fillText(s.tok, midX + midW - 58, sy + 22);

          sctx.fillStyle = '#cbd5e1';
          sctx.font = '10px -apple-system, sans-serif';
          sctx.fillText(s.task, midX + 40, sy + 42);

          sctx.fillStyle = 'rgba(255,255,255,0.08)';
          sctx.fillRect(midX + 40, sy + 49, midW - 68, 3);
        });

        // Mini Terminal Log Strip at bottom of Center Card
        const logY = midY + 250;
        this.roundRect(sctx, midX + 14, logY, midW - 28, 84, 9);
        sctx.fillStyle = '#060911';
        sctx.fill();
        sctx.font = '9.5px Menlo, monospace';
        sctx.fillStyle = '#4ade80';
        sctx.fillText('✓ [Claude] Patched DynamicScreenRenderer.ts', midX + 24, logY + 22);
        sctx.fillStyle = '#38bdf8';
        sctx.fillText('➜ [Codex]  tsc --noEmit · 0 errors (1.4s)', midX + 24, logY + 42);
        sctx.fillStyle = '#f59e48';
        sctx.fillText('📱 [iPhone] Remote approval ready · QR paired', midX + 24, logY + 62);

        // RIGHT COLUMN: Quota Rings & Live Token Throughput (x: 728..996)
        this.roundRect(sctx, rx, midY, rw, midH, 14);
        sctx.fillStyle = 'rgba(10, 16, 30, 0.88)';
        sctx.fill();
        sctx.strokeStyle = 'rgba(56, 189, 248, 0.22)';
        sctx.stroke();

        sctx.fillStyle = '#94a3b8';
        sctx.font = '700 10px Menlo, monospace';
        sctx.fillText('QUOTA & TOKEN LEDGER', rx + 16, midY + 24);

        const gauges = [
          { label: '5H QUOTA', pct: 0.82, val: '82%', col: '#38bdf8', cx: rx + 54 },
          { label: '7D LIMIT', pct: 0.68, val: '68%', col: '#f59e48', cx: rx + 134 },
          { label: 'CACHE', pct: 0.94, val: '94%', col: '#4ade80', cx: rx + 214 },
        ];
        for (const g of gauges) {
          const gy = midY + 86;
          sctx.strokeStyle = 'rgba(255,255,255,0.10)';
          sctx.lineWidth = 6;
          sctx.beginPath();
          sctx.arc(g.cx, gy, 28, 0, Math.PI * 2);
          sctx.stroke();

          sctx.strokeStyle = g.col;
          sctx.lineWidth = 6;
          sctx.beginPath();
          sctx.arc(g.cx, gy, 28, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * g.pct);
          sctx.stroke();

          sctx.fillStyle = '#f8fafc';
          sctx.font = '700 13px Menlo, monospace';
          sctx.fillText(g.val, g.cx - 12, gy + 5);

          sctx.fillStyle = '#94a3b8';
          sctx.font = '700 9px Menlo, monospace';
          sctx.fillText(g.label, g.cx - 22, gy + 46);
        }

        // Live Token Sparkline card frame & labels
        this.roundRect(sctx, rx + 16, spY, rw - 32, 92, 10);
        sctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        sctx.fill();
        sctx.fillStyle = '#64748b';
        sctx.font = '700 9px Menlo, monospace';
        sctx.fillText('TOKENS TODAY', rx + 28, spY + 20);
        sctx.fillStyle = '#f8fafc';
        sctx.font = '800 20px Menlo, monospace';
        sctx.fillText('1.84M', rx + 28, spY + 44);
        sctx.fillStyle = '#4ade80';
        sctx.font = '700 10px Menlo, monospace';
        sctx.fillText('-$14.20 cached', rx + 116, spY + 42);

        // Mobile Remote Card at bottom right
        const rmY = midY + 266;
        this.roundRect(sctx, rx + 16, rmY, rw - 32, 68, 10);
        sctx.fillStyle = 'rgba(30, 41, 59, 0.65)';
        sctx.fill();
        sctx.strokeStyle = 'rgba(74, 222, 128, 0.25)';
        sctx.lineWidth = 1;
        sctx.stroke();
        sctx.fillStyle = '#4ade80';
        sctx.font = '700 10px Menlo, monospace';
        sctx.fillText('● MOBILE REMOTE PAIRED', rx + 28, rmY + 24);
        sctx.fillStyle = '#e2e8f0';
        sctx.font = '11px -apple-system, sans-serif';
        sctx.fillText('iPhone & Apple Watch · Voice Ready', rx + 28, rmY + 46);
      });

      // Blit static UI layer & draw only animated elements at 60 FPS
      ctx.drawImage(staticLayer, 0, 0);

      // Centered Floating Notch Pill with 3 live mini quota rings
      const nw = 264;
      const nx = (w - nw) * 0.5;
      this.roundRect(ctx, nx, 4, nw, 34, 17);
      ctx.fillStyle = '#03050a';
      ctx.fill();
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.55)';
      ctx.lineWidth = 1.2;
      ctx.stroke();

      const livePulse = 0.6 + 0.4 * Math.sin(t * 3.6);
      const miniRings = [
        { cx: nx + 28, pct: 0.78 + 0.04 * Math.sin(t * 0.9), col: '#f59e48', tag: 'CL' },
        { cx: nx + 64, pct: 0.64 + 0.05 * Math.cos(t * 0.7), col: '#4ade80', tag: 'CX' },
        { cx: nx + 100, pct: 0.91 + 0.03 * Math.sin(t * 1.1), col: '#38bdf8', tag: 'GM' },
      ];
      ctx.font = 'bold 7px Menlo, monospace';
      for (const r of miniRings) {
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 2.6;
        ctx.beginPath();
        ctx.arc(r.cx, 21, 10, 0, Math.PI * 2);
        ctx.stroke();
        ctx.strokeStyle = r.col;
        ctx.beginPath();
        ctx.arc(r.cx, 21, 10, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * r.pct);
        ctx.stroke();
        ctx.fillStyle = '#e2e8f0';
        ctx.fillText(r.tag, r.cx - 4.5, 23.5);
      }
      ctx.fillStyle = `rgba(74, 222, 128, ${livePulse.toFixed(2)})`;
      ctx.beginPath();
      ctx.arc(nx + 136, 21, 3.5, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 10px Menlo, monospace';
      ctx.fillText('3 AGENTS LIVE', nx + 148, 24.5);

      // 3 Animated session progress bars
      const progs = [
        { col: '#f59e48', val: 0.45 + 0.35 * (0.5 + 0.5 * Math.sin(t * 0.85)) },
        { col: '#4ade80', val: 0.62 + 0.28 * (0.5 + 0.5 * Math.cos(t * 0.72)) },
        { col: '#38bdf8', val: 0.55 + 0.38 * (0.5 + 0.5 * Math.sin(t * 1.05 + 1.2)) },
      ];
      for (let i = 0; i < 3; i++) {
        const sy = midY + 38 + i * 68;
        ctx.fillStyle = progs[i].col;
        ctx.fillRect(midX + 40, sy + 49, (midW - 68) * progs[i].val, 3);
      }

      // Animated Token Sparkline
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2;
      ctx.beginPath();
      for (let i = 0; i <= 26; i++) {
        const u = i / 26;
        const px = rx + 28 + u * (rw - 56);
        const py = spY + 76 - (Math.sin(u * 8 + t * 2.2) * 6 + Math.cos(u * 15 - t * 1.4) * 4 + 6);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.stroke();
      return;
    }

    const hudW = 196;
    const hudX = w - hudW - 10;

    if (mode === 'visualizer') {
      const staticLayer = this.getStaticLayer('uw:visualizer', w, h, (sctx) => {
        sctx.fillStyle = '#080b12';
        sctx.fillRect(0, 0, w, h);
        this.drawUltrawideTopBar(sctx, w, 'AStudio Audio DSP — Realtime Spectrum Analyzer');
      });
      ctx.drawImage(staticLayer, 0, 0);

      const pulse = 0.55 + 0.45 * Math.sin(t * 4.0);
      ctx.fillStyle = `rgba(74, 222, 128, ${pulse.toFixed(2)})`;
      ctx.beginPath();
      ctx.arc(hudX + 12, 11, 3.2, 0, Math.PI * 2);
      ctx.fill();

      if (!this.visualizerGrad) {
        const g = ctx.createLinearGradient(0, 54, 0, h - 36);
        g.addColorStop(0, '#f29d4b');
        g.addColorStop(0.5, '#38bdf8');
        g.addColorStop(1, '#1d4ed8');
        this.visualizerGrad = g;
      }

      const bars = 48;
      const bw = (w - 80) / bars;
      const audio = this.latestAudio;
      const liveAct = audio ? audio.active : 0;
      ctx.fillStyle = this.visualizerGrad;
      for (let i = 0; i < bars; i++) {
        const fakeAmp =
          0.18 +
          0.52 * Math.abs(Math.sin(t * 2.4 + i * 0.26)) *
            (0.55 + 0.45 * Math.cos(t * 1.3 - i * 0.14));
        const specIdx = Math.min(31, Math.floor((i / bars) * 32));
        const liveAmp = audio ? Math.min(0.98, 0.08 + audio.spectrum[specIdx] * 0.92 + audio.beat * 0.12) : fakeAmp;
        const amp = fakeAmp * (1 - liveAct) + liveAmp * liveAct;
        const bh = amp * (h - 90);
        ctx.fillRect(40 + i * bw, h - 36 - bh, bw - 5, bh);
      }
      return;
    }

    // 'ide' or 'obs' mode
    const splitX = mode === 'obs' ? 430 : 650;
    const vx = splitX + 14;
    const vy = 34;
    const vw = w - splitX - 28;
    const vh = 230;

    const staticLayer = this.getStaticLayer(`uw:${mode}`, w, h, (sctx) => {
      sctx.fillStyle = '#080b12';
      sctx.fillRect(0, 0, w, h);

      const title =
        mode === 'ide'
          ? 'AStudio — LightmapMaterialPatch.ts · Vite 60FPS'
          : 'OBS Studio 31.0 — LIVE 4K60 · Bitrate 18500 kbps';
      this.drawUltrawideTopBar(sctx, w, title);

      // Left Sidebar
      sctx.fillStyle = '#0b0e16';
      sctx.fillRect(0, 22, 142, h - 38);
      sctx.fillStyle = '#1e273a';
      sctx.fillRect(142, 22, 1, h - 38);

      const files = [
        'src/',
        '  core/App.ts',
        '  core/LightmapPatch.ts',
        '  core/MoodSystem.ts',
        '  core/PostFX.ts',
        '  core/Screens.ts',
        '  interaction/Camera.ts',
        '  interaction/Collision.ts',
        'pipeline/',
        '  build_studio.py',
        '  bake_lightmaps.py',
      ];
      sctx.font = '10px Menlo, monospace';
      files.forEach((f, i) => {
        if (i === 2) {
          sctx.fillStyle = '#19253d';
          sctx.fillRect(2, 34 + i * 20, 138, 17);
        }
        sctx.fillStyle = i === 2 ? '#e2ecff' : '#7b8aa8';
        sctx.fillText(f, 10, 46 + i * 20);
      });

      // Center Code Editor
      const codeX = 156;
      const codeLines = [
        ['export function ', '#c084fc', 'decodeRGBMLightmap', '#60a5fa', '(rgbm: vec4) {', '#cbd5e1'],
        ['  const ', '#c084fc', 'irradiance', '#38bdf8', ' = rgbm.rgb * (rgbm.a * ', '#cbd5e1', '8.0', '#fb923c', ');', '#cbd5e1'],
        ['  // Cycles Direct + Indirect GI bounce', '#586782'],
        ['  return ', '#c084fc', 'mix(lmA, lmB, uMoodMix)', '#4ade80', ' * PI;', '#cbd5e1'],
        ['}', '#cbd5e1'],
        [''],
        ['class ', '#c084fc', 'GeekLoftEngine ', '#38bdf8', 'implements ', '#c084fc', 'Renderer60 {', '#fbbf24'],
        ['  private ', '#c084fc', 'toneMapping ', '#e2e8f0', '= THREE.AgXToneMapping;', '#60a5fa'],
        ['  public ', '#c084fc', 'setMood', '#60a5fa', '(target: MoodId) {', '#cbd5e1'],
        ['    this.skyline.crossFade(target, ', '#cbd5e1', '1.2', '#fb923c', ');', '#cbd5e1'],
        ['    this.pmrem.blendEnvironment(target);', '#cbd5e1'],
        ['  }', '#cbd5e1'],
        ['}', '#cbd5e1'],
      ];

      sctx.font = '11px Menlo, monospace';
      codeLines.forEach((parts, row) => {
        const y = 48 + row * 19;
        sctx.fillStyle = '#3f4c68';
        sctx.fillText(String(row + 1).padStart(2, ' '), codeX, y);
        let x = codeX + 24;
        for (let i = 0; i < parts.length; i += 2) {
          const text = parts[i];
          const color = parts[i + 1] || '#cbd5e1';
          sctx.fillStyle = color;
          sctx.fillText(text, x, y);
          x += sctx.measureText(text).width;
        }
        if (row === 9) {
          this.ideCursorX = x;
        }
      });

      // Bottom Terminal
      sctx.fillStyle = '#1d273b';
      sctx.fillRect(143, 308, splitX - 143, 1);
      sctx.fillStyle = '#06080e';
      sctx.fillRect(143, 309, splitX - 143, h - 325);
      sctx.font = '10px Menlo, monospace';
      sctx.fillStyle = '#4ade80';
      sctx.fillText('➜  AStudio git:(main) pnpm dev', 156, 330);
      sctx.fillStyle = '#38bdf8';
      sctx.fillText('  VITE v6.4.6  ready in 148 ms · Cycles RGBM Lightmaps loaded', 156, 350);
      sctx.fillStyle = '#94a3b8';
      sctx.fillText('  [OBS] Stream connected · Tokyo Edge · 0 dropped frames', 156, 390);

      // Right Split Background & Viewport Backdrop
      sctx.fillStyle = '#1e273a';
      sctx.fillRect(splitX, 22, 1, h - 38);
      sctx.fillStyle = '#0b0e17';
      sctx.fillRect(splitX + 1, 22, w - splitX - 1, h - 38);

      const vgrad = sctx.createLinearGradient(vx, vy, vx + vw, vy + vh);
      vgrad.addColorStop(0, '#0c182c');
      vgrad.addColorStop(0.6, '#172234');
      vgrad.addColorStop(1, '#2f1e1a');
      sctx.fillStyle = vgrad;
      sctx.fillRect(vx, vy, vw, vh);

      sctx.save();
      sctx.beginPath();
      sctx.rect(vx, vy, vw, vh);
      sctx.clip();
      sctx.strokeStyle = 'rgba(56, 189, 248, 0.16)';
      sctx.lineWidth = 1;
      sctx.beginPath();
      for (let gx = vx; gx < vx + vw; gx += 28) {
        sctx.moveTo(gx, vy + vh * 0.56);
        sctx.lineTo(gx + (gx - (vx + vw * 0.5)) * 0.4, vy + vh);
      }
      for (let gy = 0; gy < 5; gy++) {
        const ly = vy + vh * 0.58 + gy * 22;
        sctx.moveTo(vx, ly);
        sctx.lineTo(vx + vw, ly);
      }
      sctx.stroke();
      sctx.restore();

      // Static channel labels & VU meter tracks
      const channels = ['Mic SM7B', 'Desktop Audio', 'Discord', 'Lo-Fi BGM'];
      sctx.font = '10px Menlo, monospace';
      channels.forEach((ch, idx) => {
        const by = vy + vh + 22 + idx * 30;
        sctx.fillStyle = '#94a3b8';
        sctx.fillText(ch, vx, by);
        sctx.fillStyle = '#171f2e';
        sctx.fillRect(vx, by + 6, vw, 9);
      });

      // Status Bar
      sctx.fillStyle = '#1d4ed8';
      sctx.fillRect(0, h - 16, w, 16);
      sctx.fillStyle = '#e0f2fe';
      sctx.font = '9px Menlo, monospace';
      sctx.fillText('main*  ✓ TypeScript 5.8 · WebGL2 · 60 FPS Locked', 12, h - 5);
    });

    ctx.drawImage(staticLayer, 0, 0);

    // Top-right pulse dot
    const pulse = 0.55 + 0.45 * Math.sin(t * 4.0);
    ctx.fillStyle = `rgba(74, 222, 128, ${pulse.toFixed(2)})`;
    ctx.beginPath();
    ctx.arc(hudX + 12, 11, 3.2, 0, Math.PI * 2);
    ctx.fill();

    // Blinking cursor on active coding line
    if (Math.floor(t * 2.2) % 2 === 0) {
      ctx.fillStyle = '#38bdf8';
      ctx.fillRect(this.ideCursorX + 2, 48 + 9 * 19 - 10, 6, 13);
    }

    // Dynamic GPU render time line
    ctx.font = '10px Menlo, monospace';
    ctx.fillStyle = '#fbbf24';
    ctx.fillText(`  [GPU] 60.0 FPS · AgX ToneMapping · Render Time: ${(5.2 + Math.sin(t) * 0.4).toFixed(1)} ms`, 156, 370);

    // Rotating 3D wireframe object inside viewport
    ctx.save();
    ctx.beginPath();
    ctx.rect(vx, vy, vw, vh);
    ctx.clip();

    const cx = vx + vw * 0.52;
    const cy = vy + vh * 0.48;
    const r = 46;
    const ang = t * 0.7;
    const cosA = Math.cos(ang);
    const sinA = Math.sin(ang);
    const pts: [number, number][] = [];
    for (const sz of [-1, 1]) {
      for (const sx of [-1, 1]) {
        for (const sy of [-1, 1]) {
          const rxp = sx * cosA - sz * sinA;
          const rzp = sx * sinA + sz * cosA;
          const pyp = sy * 0.85 - rzp * 0.28;
          pts.push([cx + rxp * r, cy + pyp * r]);
        }
      }
    }
    const edges = [
      [0, 1], [1, 3], [3, 2], [2, 0],
      [4, 5], [5, 7], [7, 6], [6, 4],
      [0, 4], [1, 5], [2, 6], [3, 7],
    ];
    ctx.strokeStyle = '#60a5fa';
    ctx.lineWidth = 1.6;
    ctx.beginPath();
    for (const [a, b] of edges) {
      ctx.moveTo(pts[a][0], pts[a][1]);
      ctx.lineTo(pts[b][0], pts[b][1]);
    }
    ctx.stroke();

    // LIVE badge
    ctx.fillStyle = '#dc2626';
    ctx.fillRect(vx + 10, vy + 10, 46, 16);
    ctx.fillStyle = '#ffffff';
    ctx.font = 'bold 9px Menlo, monospace';
    ctx.fillText('● LIVE', vx + 15, vy + 21);
    ctx.restore();

    // Live animated OBS Audio Mixer VU Meters
    for (let idx = 0; idx < 4; idx++) {
      const by = vy + vh + 22 + idx * 30;
      const level = 0.25 + 0.65 * Math.abs(Math.sin(t * (3.2 + idx * 0.9) + idx * 1.7));
      const fillW = vw * level;
      ctx.fillStyle = '#22c55e';
      ctx.fillRect(vx, by + 6, Math.min(fillW, vw * 0.65), 9);
      if (fillW > vw * 0.65) {
        ctx.fillStyle = '#f59e0b';
        ctx.fillRect(vx + vw * 0.65, by + 6, Math.min(fillW - vw * 0.65, vw * 0.2), 9);
      }
      if (fillW > vw * 0.85) {
        ctx.fillStyle = '#ef4444';
        ctx.fillRect(vx + vw * 0.85, by + 6, fillW - vw * 0.85, 9);
      }
    }
  }

  private drawUltrawideTopBar(ctx: CanvasRenderingContext2D, w: number, title: string): void {
    ctx.fillStyle = '#0c101a';
    ctx.fillRect(0, 0, w, 22);
    const dots = ['#ef4444', '#f59e0b', '#22c55e'];
    dots.forEach((c, i) => {
      ctx.fillStyle = c;
      ctx.beginPath();
      ctx.arc(14 + i * 14, 11, 3.8, 0, Math.PI * 2);
      ctx.fill();
    });
    ctx.fillStyle = '#7c8aa5';
    ctx.font = '10px Menlo, monospace';
    ctx.fillText(title, 66, 14);

    // Top-right Agent HUD live notch pill frame
    const hudW = 196;
    const hudX = w - hudW - 10;
    ctx.fillStyle = '#05070c';
    ctx.fillRect(hudX, 2, hudW, 18);
    ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
    ctx.lineWidth = 1;
    ctx.strokeRect(hudX + 0.5, 2.5, hudW - 1, 17);
    ctx.fillStyle = '#e2e8f0';
    ctx.font = 'bold 9px Menlo, monospace';
    ctx.fillText('AGENT HUD', hudX + 22, 14);
    ctx.fillStyle = '#38bdf8';
    ctx.font = '9px Menlo, monospace';
    ctx.fillText('agenthud.app ↗', hudX + 94, 14);
  }

  private drawVertical(ctx: CanvasRenderingContext2D, w: number, h: number, t: number, mode: ScreenMode): void {
    if (mode === 'agenthud') {
      const staticLayer = this.getStaticLayer('vert:agenthud', w, h, (sctx) => {
        // Portrait 27" Agent HUD Live Telemetry, Quota Rings & Activity Feed
        const bg = sctx.createLinearGradient(0, 0, 0, h);
        bg.addColorStop(0, '#050811');
        bg.addColorStop(0.5, '#0a1222');
        bg.addColorStop(1, '#060913');
        sctx.fillStyle = bg;
        sctx.fillRect(0, 0, w, h);

        // Header
        sctx.fillStyle = '#0d1424';
        sctx.fillRect(0, 0, w, 46);
        sctx.fillStyle = '#f8fafc';
        sctx.font = '700 13px Menlo, monospace';
        sctx.fillText('AGENT HUD · TELEMETRY', 36, 27);
        sctx.fillStyle = '#38bdf8';
        sctx.font = '700 11px Menlo, monospace';
        sctx.fillText('agenthud.app ↗', w - 114, 27);

        // 3 Quota Ring Card frames & static labels
        const labels = ['CLAUDE', 'CODEX', 'GEMINI'];
        const vals = ['78%', '64%', '91%'];
        labels.forEach((label, i) => {
          const cx = 14 + i * 142;
          this.roundRect(sctx, cx, 60, 134, 118, 12);
          sctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
          sctx.fill();
          sctx.strokeStyle = 'rgba(148, 163, 184, 0.16)';
          sctx.lineWidth = 1;
          sctx.stroke();

          const rcx = cx + 67;
          const rcy = 110;
          sctx.strokeStyle = 'rgba(255,255,255,0.10)';
          sctx.lineWidth = 5.5;
          sctx.beginPath();
          sctx.arc(rcx, rcy, 28, 0, Math.PI * 2);
          sctx.stroke();

          sctx.fillStyle = '#f8fafc';
          sctx.font = '700 13px Menlo, monospace';
          sctx.fillText(vals[i], rcx - 12, rcy + 5);

          sctx.fillStyle = '#94a3b8';
          sctx.font = '700 10px Menlo, monospace';
          sctx.fillText(label, cx + 44, 164);
        });

        // Token Throughput & Cache Hit Graph card
        this.roundRect(sctx, 14, 192, w - 28, 148, 12);
        sctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        sctx.fill();
        sctx.strokeStyle = 'rgba(56, 189, 248, 0.18)';
        sctx.lineWidth = 1;
        sctx.stroke();

        sctx.fillStyle = '#94a3b8';
        sctx.font = '700 10px Menlo, monospace';
        sctx.fillText('LIVE TOKEN THROUGHPUT · 1.84M TODAY', 28, 214);
        sctx.fillStyle = '#4ade80';
        sctx.fillText('94.2% CACHE', w - 104, 214);

        // Live Agent Activity Stream frame
        this.roundRect(sctx, 14, 354, w - 28, 336, 12);
        sctx.fillStyle = 'rgba(13, 18, 32, 0.90)';
        sctx.fill();
        sctx.strokeStyle = 'rgba(148, 163, 184, 0.16)';
        sctx.stroke();

        sctx.fillStyle = '#151e32';
        sctx.fillRect(15, 355, w - 30, 32);
        sctx.fillStyle = '#cbd5e1';
        sctx.font = '700 11px Menlo, monospace';
        sctx.fillText('LIVE AGENT FEED · 3 SESSIONS ACTIVE', 28, 375);

        // Bottom Clickable Brand Banner
        const banGrad = sctx.createLinearGradient(14, 704, w - 14, 752);
        banGrad.addColorStop(0, '#f8fafc');
        banGrad.addColorStop(1, '#dbeafe');
        this.roundRect(sctx, 14, 704, w - 28, 48, 12);
        sctx.fillStyle = banGrad;
        sctx.fill();
        sctx.fillStyle = '#070b14';
        sctx.font = '800 15px Menlo, monospace';
        sctx.fillText('VISIT agenthud.app  ↗', 124, 733);
      });

      ctx.drawImage(staticLayer, 0, 0);

      // Header pulse dot
      const pulse = 0.6 + 0.4 * Math.sin(t * 3.5);
      ctx.fillStyle = `rgba(74, 222, 128, ${pulse.toFixed(2)})`;
      ctx.beginPath();
      ctx.arc(22, 23, 4.5, 0, Math.PI * 2);
      ctx.fill();

      // 3 Animated quota ring arcs
      const rings = [
        { pct: 0.78 + 0.03 * Math.sin(t * 0.9), col: '#f59e48' },
        { pct: 0.64 + 0.04 * Math.cos(t * 0.7), col: '#4ade80' },
        { pct: 0.91 + 0.02 * Math.sin(t * 1.1), col: '#38bdf8' },
      ];
      ctx.lineWidth = 5.5;
      for (let i = 0; i < 3; i++) {
        const rcx = 14 + i * 142 + 67;
        ctx.strokeStyle = rings[i].col;
        ctx.beginPath();
        ctx.arc(rcx, 110, 28, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * rings[i].pct);
        ctx.stroke();
      }

      // Live throughput waves
      const drawWave = (color: string, phase: number, amp: number, offset: number) => {
        ctx.strokeStyle = color;
        ctx.lineWidth = 2.2;
        ctx.beginPath();
        for (let x = 28; x < w - 28; x += 6) {
          const u = (x - 28) / (w - 56);
          const y = offset + Math.sin(u * 10 + t * 2.2 + phase) * amp + Math.cos(u * 21 - t * 1.4) * (amp * 0.35);
          if (x === 28) ctx.moveTo(x, y);
          else ctx.lineTo(x, y);
        }
        ctx.stroke();
      };
      drawWave('#38bdf8', 0, 22, 266);
      drawWave('#f59e48', 1.8, 16, 286);

      // Live Agent Activity Stream rows
      const events = [
        ['Claude Code', '#f59e48', 'Updated DynamicScreenRenderer.ts (+294 lines)'],
        ['OpenAI Codex', '#4ade80', 'tsc --noEmit & vite build passed in 9.0s'],
        ['iPhone Remote', '#38bdf8', 'Approved shell command via Watch haptic'],
        ['Gemini Agent', '#a78bfa', 'Rendered 4K OLED Agent HUD showcase'],
        ['Voice Coding', '#fbbf24', 'Transcribed prompt locally in 120ms'],
        ['Quota Guard', '#4ade80', 'Prompt cache hit 94.2% · saved $14.20'],
        ['Daily Digest', '#38bdf8', 'Generated engineering standup summary'],
      ];
      const offsetIdx = Math.floor(t * 0.45) % events.length;
      for (let i = 0; i < 6; i++) {
        const [agent, col, msg] = events[(i + offsetIdx) % events.length];
        const ry = 414 + i * 44;
        ctx.fillStyle = col;
        ctx.fillRect(26, ry - 10, 4, 26);
        ctx.font = '700 11px Menlo, monospace';
        ctx.fillText(agent, 38, ry);
        ctx.fillStyle = '#cbd5e1';
        ctx.font = '12px -apple-system, sans-serif';
        ctx.fillText(msg, 38, ry + 16);
      }
      return;
    }

    const staticLayer = this.getStaticLayer('vert:telemetry', w, h, (sctx) => {
      sctx.fillStyle = '#080b12';
      sctx.fillRect(0, 0, w, h);

      // Header
      sctx.fillStyle = '#0f1420';
      sctx.fillRect(0, 0, w, 40);
      sctx.fillStyle = '#38bdf8';
      sctx.font = 'bold 12px Menlo, monospace';
      sctx.fillText('SYSTEM TELEMETRY & LIVE CHAT', 16, 25);

      // 3 Metric Card frames
      const meta = [
        { label: 'GPU', col: '#38bdf8' },
        { label: 'TEMP', col: '#f29d4b' },
        { label: 'FPS', col: '#4ade80' },
      ];
      meta.forEach((m, i) => {
        const cx = 14 + i * 142;
        sctx.fillStyle = '#111624';
        sctx.fillRect(cx, 54, 134, 86);
        sctx.fillStyle = m.col;
        sctx.fillRect(cx, 54, 134, 3);
        sctx.fillStyle = '#8b9bb8';
        sctx.font = '10px Menlo, monospace';
        sctx.fillText(m.label, cx + 10, 76);
      });

      // Telemetry Graph box & grid
      sctx.fillStyle = '#0e1320';
      sctx.fillRect(14, 154, w - 28, 152);
      sctx.strokeStyle = '#1c2538';
      sctx.beginPath();
      for (let gy = 184; gy < 300; gy += 30) {
        sctx.moveTo(22, gy);
        sctx.lineTo(w - 22, gy);
      }
      sctx.stroke();

      // Live Stream Chat Panel frame
      sctx.fillStyle = '#0d111c';
      sctx.fillRect(14, 320, w - 28, h - 336);
      sctx.fillStyle = '#151c2d';
      sctx.fillRect(14, 320, w - 28, 30);
      sctx.fillStyle = '#cbd5e1';
      sctx.font = 'bold 11px Menlo, monospace';
      sctx.fillText('STREAM CHAT · 1,284 ONLINE', 26, 339);
    });

    ctx.drawImage(staticLayer, 0, 0);

    // 3 Metric Cards dynamic values & bars
    const metrics = [
      { val: `${Math.round(58 + Math.sin(t) * 6)}%`, col: '#38bdf8' },
      { val: `${Math.round(54 + Math.cos(t * 0.6) * 2)}°C`, col: '#f29d4b' },
      { val: '60.0', col: '#4ade80' },
    ];
    ctx.font = 'bold 22px Menlo, monospace';
    metrics.forEach((m, i) => {
      const cx = 14 + i * 142;
      ctx.fillStyle = '#f1f5f9';
      ctx.fillText(m.val, cx + 10, 108);
      ctx.fillStyle = m.col;
      for (let b = 0; b < 10; b++) {
        const bh = 6 + 16 * Math.abs(Math.sin(t * 2 + b * 0.6 + i));
        ctx.fillRect(cx + 10 + b * 11, 134 - bh, 7, bh);
      }
    });

    const drawWave = (color: string, phase: number, amp: number, offset: number) => {
      ctx.strokeStyle = color;
      ctx.lineWidth = 2.2;
      ctx.beginPath();
      for (let x = 22; x < w - 22; x += 6) {
        const u = (x - 22) / (w - 44);
        const y = offset + Math.sin(u * 10 + t * 2.2 + phase) * amp + Math.cos(u * 21 - t * 1.4) * (amp * 0.35);
        if (x === 22) ctx.moveTo(x, y);
        else ctx.lineTo(x, y);
      }
      ctx.stroke();
    };
    drawWave('#38bdf8', 0, 26, 224);
    drawWave('#f29d4b', 1.8, 18, 246);

    const msgs = [
      ['@kenji_dev', '#38bdf8', '这个清水混凝土+蓝调窗景质感太顶了！'],
      ['@arch_lina', '#f29d4b', 'Cycles 烘焙 Lightmap 跑 60fps 丝滑'],
      ['@pixel_craft', '#a78bfa', '桌上的 75% 铝坨坨键帽配色爱了'],
      ['@shibuya_io', '#4ade80', 'Herman Miller Sayl 细节还原度爆表'],
      ['@shader_god', '#f472b6', 'AgX 色调映射屏幕完全不泛白 👍'],
      ['@retro_ps5', '#fbbf24', '书架上居然还有紫色 GBC 和 PSP 哈哈'],
      ['@vfx_nora', '#38bdf8', '切换日景和黄金时刻过渡好自然！'],
      ['@dev_zen', '#4ade80', '点显示器还能切 OBS 和频谱？绝了'],
      ['@audio_max', '#f29d4b', 'Focusrite Scarlett + M-Audio 很专业'],
    ];
    const scrollOffset = Math.floor(t * 0.55) % msgs.length;
    for (let i = 0; i < 9; i++) {
      const [user, col, text] = msgs[(i + scrollOffset) % msgs.length];
      const ry = 374 + i * 42;
      ctx.fillStyle = col;
      ctx.fillRect(24, ry - 10, 4, 24);
      ctx.font = 'bold 11px Menlo, monospace';
      ctx.fillText(user, 36, ry);
      ctx.fillStyle = '#cbd5e1';
      ctx.font = '12px -apple-system, PingFang SC, sans-serif';
      ctx.fillText(text, 36, ry + 16);
    }
  }

  private drawStreamDeck(
    ctx: CanvasRenderingContext2D,
    w: number,
    h: number,
    t: number,
    force: boolean
  ): boolean {
    const pulseIdx = Math.floor(t * 1.2) % 15;
    if (!force && pulseIdx === this.lastStreamDeckPulse) {
      return false;
    }
    this.lastStreamDeckPulse = pulseIdx;

    ctx.fillStyle = '#090b10';
    ctx.fillRect(0, 0, w, h);
    const palette = [
      '#ef4444', '#38bdf8', '#22c55e', '#f59e0b', '#a855f7',
      '#06b6d4', '#f97316', '#6366f1', '#ec4899', '#14b8a6',
      '#94a3b8', '#3b82f6', '#eab308', '#4ade80', '#f43f5e',
    ];
    for (let r = 0; r < 3; r++) {
      for (let c = 0; c < 5; c++) {
        const idx = r * 5 + c;
        const x = 12 + c * 60;
        const y = 12 + r * 58;
        ctx.fillStyle = idx === pulseIdx ? '#24304a' : '#141925';
        ctx.fillRect(x, y, 52, 48);
        ctx.fillStyle = palette[idx];
        ctx.globalAlpha = idx === pulseIdx ? 1.0 : 0.78;
        ctx.fillRect(x + 12, y + 10, 28, 22);
        ctx.globalAlpha = 1.0;
        ctx.fillStyle = '#cbd5e1';
        ctx.fillRect(x + 10, y + 38, 32, 3);
      }
    }
    return true;
  }

  private drawLivingTv(
    ctx: CanvasRenderingContext2D,
    w: number,
    h: number,
    t: number,
    channel: TvChannel,
    force: boolean
  ): boolean {
    if (channel === 'agenthud') {
      const panelX = 532;
      const panelW = 436;
      const cardY = 168;
      const cardH = 354;
      const stripY = cardY + 242;

      const staticLayer = this.getStaticLayer('tv:agenthud', w, h, (sctx) => {
        // Cinema-Grade 4K OLED Brand Showcase Commercial for Agent HUD (agenthud.app)
        const bg = sctx.createLinearGradient(0, 0, w, h);
        bg.addColorStop(0, '#050811');
        bg.addColorStop(0.5, '#0b1224');
        bg.addColorStop(1, '#070a14');
        sctx.fillStyle = bg;
        sctx.fillRect(0, 0, w, h);

        // Subtle architectural grid lines
        sctx.strokeStyle = 'rgba(148, 163, 184, 0.045)';
        sctx.lineWidth = 1;
        sctx.beginPath();
        for (let gx = 48; gx < w; gx += 48) {
          sctx.moveTo(gx, 0);
          sctx.lineTo(gx, h);
        }
        for (let gy = 48; gy < h; gy += 48) {
          sctx.moveTo(0, gy);
          sctx.lineTo(w, gy);
        }
        sctx.stroke();

        // Ambient OLED aura glows
        const cyanGlow = sctx.createRadialGradient(740, 220, 16, 740, 220, 310);
        cyanGlow.addColorStop(0, 'rgba(56, 189, 248, 0.28)');
        cyanGlow.addColorStop(0.55, 'rgba(99, 102, 241, 0.12)');
        cyanGlow.addColorStop(1, 'rgba(5, 8, 17, 0)');
        sctx.fillStyle = cyanGlow;
        sctx.fillRect(0, 0, w, h);

        const amberGlow = sctx.createRadialGradient(210, 460, 12, 210, 460, 260);
        amberGlow.addColorStop(0, 'rgba(245, 158, 72, 0.22)');
        amberGlow.addColorStop(1, 'rgba(5, 8, 17, 0)');
        sctx.fillStyle = amberGlow;
        sctx.fillRect(0, 0, w, h);

        // Top Header Bar
        sctx.fillStyle = '#e2e8f0';
        sctx.font = '700 15px Menlo, monospace';
        sctx.fillText('AGENT HUD', 78, 51);

        sctx.fillStyle = 'rgba(255, 255, 255, 0.08)';
        this.roundRect(sctx, 654, 30, 314, 30, 15);
        sctx.fill();
        sctx.strokeStyle = 'rgba(148, 163, 184, 0.22)';
        sctx.lineWidth = 1;
        sctx.stroke();
        sctx.fillStyle = '#cbd5e1';
        sctx.font = '600 11px Menlo, monospace';
        sctx.fillText('MACOS · WINDOWS · LINUX · IPHONE', 678, 49);

        // Left Column: Brand Hero Copy & CTA
        sctx.fillStyle = '#38bdf8';
        sctx.font = '700 13px Menlo, monospace';
        sctx.fillText('HEADS-UP DISPLAY FOR AI CODING AGENTS', 56, 132);

        sctx.fillStyle = '#ffffff';
        sctx.font = '800 56px -apple-system, BlinkMacSystemFont, sans-serif';
        sctx.fillText('Agent HUD', 54, 198);

        sctx.fillStyle = '#cbd5e1';
        sctx.font = '500 22px -apple-system, BlinkMacSystemFont, sans-serif';
        sctx.fillText('Every Agent. Every Quota. One Glance.', 56, 238);

        const features = [
          { dot: '#f59e48', title: 'Live Quota & Token Rings', desc: 'Claude Code · Codex · Gemini · Cache & Cost' },
          { dot: '#38bdf8', title: 'Unified Parallel Sessions', desc: 'Floating Notch HUD + Instant Hover Panel' },
          { dot: '#4ade80', title: 'Mobile Remote & Voice', desc: 'Approve & steer from iPhone & Apple Watch' },
        ];
        features.forEach((f, idx) => {
          const fy = 286 + idx * 54;
          sctx.fillStyle = 'rgba(15, 23, 42, 0.72)';
          this.roundRect(sctx, 56, fy, 428, 44, 10);
          sctx.fill();
          sctx.strokeStyle = 'rgba(148, 163, 184, 0.14)';
          sctx.lineWidth = 1;
          sctx.stroke();

          sctx.fillStyle = f.dot;
          sctx.beginPath();
          sctx.arc(76, fy + 22, 4.5, 0, Math.PI * 2);
          sctx.fill();

          sctx.fillStyle = '#f8fafc';
          sctx.font = '600 14px -apple-system, sans-serif';
          sctx.fillText(f.title, 94, fy + 19);

          sctx.fillStyle = '#94a3b8';
          sctx.font = '11px Menlo, monospace';
          sctx.fillText(f.desc, 94, fy + 35);
        });

        // Glowing Primary CTA Pill
        const ctaX = 56;
        const ctaY = 470;
        const ctaW = 248;
        const ctaH = 52;
        const ctaGrad = sctx.createLinearGradient(ctaX, ctaY, ctaX + ctaW, ctaY + ctaH);
        ctaGrad.addColorStop(0, '#f8fafc');
        ctaGrad.addColorStop(1, '#dbeafe');
        this.roundRect(sctx, ctaX, ctaY, ctaW, ctaH, 26);
        sctx.fillStyle = ctaGrad;
        sctx.fill();

        sctx.fillStyle = '#070b14';
        sctx.font = '800 19px Menlo, monospace';
        sctx.fillText('agenthud.app  ↗', ctaX + 34, ctaY + 32);

        sctx.fillStyle = 'rgba(148, 163, 184, 0.85)';
        sctx.font = '12px Menlo, monospace';
        sctx.fillText('CLICK SCREEN TO OPEN', ctaX + ctaW + 18, ctaY + 31);

        // Main Dark Glass Hover Panel below the Notch
        this.roundRect(sctx, panelX, cardY, panelW, cardH, 18);
        sctx.fillStyle = 'rgba(10, 16, 30, 0.88)';
        sctx.fill();
        sctx.strokeStyle = 'rgba(148, 163, 184, 0.20)';
        sctx.lineWidth = 1.2;
        sctx.stroke();

        sctx.fillStyle = '#94a3b8';
        sctx.font = '700 11px Menlo, monospace';
        sctx.fillText('ACTIVE AGENT SESSIONS', panelX + 22, cardY + 30);
        sctx.fillStyle = '#4ade80';
        sctx.fillText('● LIVE SYNC', panelX + panelW - 96, cardY + 30);

        const sessions = [
          {
            name: 'Claude Code',
            task: 'Refactoring WebGL2 lighting pipeline',
            status: 'EDITING',
            col: '#f59e48',
            tok: '24.8k tok',
          },
          {
            name: 'OpenAI Codex',
            task: 'Running integration & type checks',
            status: 'TESTING',
            col: '#4ade80',
            tok: '16.2k tok',
          },
          {
            name: 'Gemini Agent',
            task: 'Building Tokyo Loft OLED showcase',
            status: 'ACTIVE',
            col: '#38bdf8',
            tok: '31.5k tok',
          },
        ];
        sessions.forEach((s, i) => {
          const sy = cardY + 46 + i * 62;
          this.roundRect(sctx, panelX + 18, sy, panelW - 36, 52, 10);
          sctx.fillStyle = 'rgba(20, 30, 52, 0.76)';
          sctx.fill();
          sctx.strokeStyle = 'rgba(148, 163, 184, 0.12)';
          sctx.lineWidth = 1;
          sctx.stroke();

          sctx.fillStyle = s.col;
          sctx.beginPath();
          sctx.arc(panelX + 34, sy + 20, 4.5, 0, Math.PI * 2);
          sctx.fill();

          sctx.fillStyle = '#f8fafc';
          sctx.font = '700 13px -apple-system, sans-serif';
          sctx.fillText(s.name, panelX + 48, sy + 23);

          sctx.fillStyle = s.col;
          sctx.font = '700 10px Menlo, monospace';
          sctx.fillText(s.status, panelX + panelW - 146, sy + 22);

          sctx.fillStyle = '#94a3b8';
          sctx.font = '10px Menlo, monospace';
          sctx.fillText(s.tok, panelX + panelW - 86, sy + 22);

          sctx.fillStyle = '#cbd5e1';
          sctx.font = '11px -apple-system, sans-serif';
          sctx.fillText(s.task, panelX + 48, sy + 41);

          sctx.fillStyle = 'rgba(255,255,255,0.08)';
          sctx.fillRect(panelX + panelW - 146, sy + 35, 114, 4);
        });

        // Bottom Metrics Strip inside Glass Panel
        this.roundRect(sctx, panelX + 18, stripY, panelW - 36, 94, 12);
        sctx.fillStyle = 'rgba(15, 23, 42, 0.85)';
        sctx.fill();
        sctx.strokeStyle = 'rgba(56, 189, 248, 0.18)';
        sctx.lineWidth = 1;
        sctx.stroke();

        const stats = [
          { label: '5H QUOTA', val: '82%', col: '#38bdf8' },
          { label: 'CACHE HIT', val: '94.2%', col: '#4ade80' },
          { label: 'TODAY', val: '1.84M', col: '#f59e48' },
        ];
        stats.forEach((st, i) => {
          const sx = panelX + 34 + i * 134;
          sctx.fillStyle = '#64748b';
          sctx.font = '700 10px Menlo, monospace';
          sctx.fillText(st.label, sx, stripY + 24);
          sctx.fillStyle = st.col;
          sctx.font = '800 22px Menlo, monospace';
          sctx.fillText(st.val, sx, stripY + 52);
        });
      });

      ctx.drawImage(staticLayer, 0, 0);

      // Top live pulse dot
      const livePulse = 0.6 + 0.4 * Math.sin(t * 3.5);
      ctx.fillStyle = `rgba(74, 222, 128, ${livePulse.toFixed(2)})`;
      ctx.beginPath();
      ctx.arc(62, 46, 5, 0, Math.PI * 2);
      ctx.fill();

      // Floating Dynamic Notch HUD Pill
      const notchW = 292;
      const notchX = panelX + (panelW - notchW) * 0.5;
      const notchY = 104;
      this.roundRect(ctx, notchX, notchY, notchW, 48, 24);
      ctx.fillStyle = '#04060b';
      ctx.fill();
      ctx.strokeStyle = 'rgba(56, 189, 248, 0.45)';
      ctx.lineWidth = 1.5;
      ctx.stroke();

      const notchRings = [
        { cx: notchX + 36, pct: 0.78 + 0.04 * Math.sin(t * 0.9), col: '#f59e48', label: 'CL' },
        { cx: notchX + 82, pct: 0.64 + 0.05 * Math.cos(t * 0.7), col: '#4ade80', label: 'CX' },
        { cx: notchX + 128, pct: 0.91 + 0.03 * Math.sin(t * 1.1), col: '#38bdf8', label: 'GM' },
      ];
      ctx.font = 'bold 8px Menlo, monospace';
      for (const r of notchRings) {
        ctx.strokeStyle = 'rgba(255,255,255,0.12)';
        ctx.lineWidth = 3.2;
        ctx.beginPath();
        ctx.arc(r.cx, notchY + 24, 13, 0, Math.PI * 2);
        ctx.stroke();

        ctx.strokeStyle = r.col;
        ctx.beginPath();
        ctx.arc(r.cx, notchY + 24, 13, -Math.PI / 2, -Math.PI / 2 + Math.PI * 2 * r.pct);
        ctx.stroke();

        ctx.fillStyle = '#e2e8f0';
        ctx.fillText(r.label, r.cx - 5.5, notchY + 27);
      }

      ctx.fillStyle = `rgba(74, 222, 128, ${livePulse.toFixed(2)})`;
      ctx.beginPath();
      ctx.arc(notchX + 172, notchY + 24, 4, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 12px Menlo, monospace';
      ctx.fillText('3 RUNNING', notchX + 184, notchY + 28);

      // 3 Animated session progress bars
      const progs = [
        { col: '#f59e48', val: 0.45 + 0.35 * (0.5 + 0.5 * Math.sin(t * 0.85)) },
        { col: '#4ade80', val: 0.62 + 0.28 * (0.5 + 0.5 * Math.cos(t * 0.72)) },
        { col: '#38bdf8', val: 0.55 + 0.38 * (0.5 + 0.5 * Math.sin(t * 1.05 + 1.2)) },
      ];
      for (let i = 0; i < 3; i++) {
        const sy = cardY + 46 + i * 62;
        ctx.fillStyle = progs[i].col;
        ctx.fillRect(panelX + panelW - 146, sy + 35, 114 * progs[i].val, 4);
      }

      // Animated Token Throughput Sparkline
      ctx.strokeStyle = '#38bdf8';
      ctx.lineWidth = 2;
      ctx.beginPath();
      const spLeft = panelX + 34;
      const spW = panelW - 68;
      for (let i = 0; i <= 32; i++) {
        const u = i / 32;
        const px = spLeft + u * spW;
        const py = stripY + 76 - (Math.sin(u * 9 + t * 2.2) * 5 + Math.cos(u * 17 - t * 1.4) * 3.5 + 4);
        if (i === 0) ctx.moveTo(px, py);
        else ctx.lineTo(px, py);
      }
      ctx.stroke();
      return true;
    }

    if (channel === 'lofi') {
      const staticLayer = this.getStaticLayer('tv:lofi', w, h, (sctx) => {
        const bg = sctx.createLinearGradient(0, 0, w, h);
        bg.addColorStop(0, '#120d16');
        bg.addColorStop(0.55, '#1d1420');
        bg.addColorStop(1, '#0d0b12');
        sctx.fillStyle = bg;
        sctx.fillRect(0, 0, w, h);

        const glow = sctx.createRadialGradient(290, 290, 20, 290, 290, 260);
        glow.addColorStop(0, 'rgba(245, 158, 72, 0.34)');
        glow.addColorStop(1, 'rgba(245, 158, 72, 0)');
        sctx.fillStyle = glow;
        sctx.fillRect(0, 0, w, h);

        sctx.fillStyle = '#f59e48';
        sctx.font = 'bold 13px Menlo, monospace';
        sctx.fillText('NOW PLAYING · AIRPLAY 2 · SONOS ARC', 568, 152);
        sctx.fillStyle = '#f8fafc';
        sctx.font = 'bold 38px -apple-system, sans-serif';
        sctx.fillText('Feather (feat. Cise Starr)', 568, 206);
        sctx.fillStyle = '#cbd5e1';
        sctx.font = '18px -apple-system, sans-serif';
        sctx.fillText('Nujabes · Late Night Shibuya Vinyl Mix', 568, 240);

        sctx.fillStyle = 'rgba(255,255,255,0.14)';
        this.roundRect(sctx, 568, 386, 360, 6, 3);
        sctx.fill();
        sctx.fillStyle = '#94a3b8';
        sctx.font = '13px Menlo, monospace';
        sctx.fillText('02:14', 568, 412);
        sctx.fillText('04:36', 888, 412);
      });

      ctx.drawImage(staticLayer, 0, 0);

      // Spinning LP vinyl disc peeking right out of the album sleeve
      const vx = 380;
      const vy = 288;
      ctx.save();
      ctx.translate(vx, vy);
      ctx.rotate(t * 0.9);
      ctx.fillStyle = '#0d0f13';
      ctx.beginPath();
      ctx.arc(0, 0, 148, 0, Math.PI * 2);
      ctx.fill();
      ctx.strokeStyle = 'rgba(255,255,255,0.08)';
      ctx.lineWidth = 1.2;
      for (let gr = 56; gr <= 140; gr += 10) {
        ctx.beginPath();
        ctx.arc(0, 0, gr, 0, Math.PI * 2);
        ctx.stroke();
      }
      ctx.fillStyle = '#e07a3b';
      ctx.beginPath();
      ctx.arc(0, 0, 44, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#0f1116';
      ctx.beginPath();
      ctx.arc(0, 0, 8, 0, Math.PI * 2);
      ctx.fill();
      ctx.restore();

      // Album Cover Art Sleeve (Left)
      this.roundRect(ctx, 108, 134, 286, 286, 10);
      const art = ctx.createLinearGradient(108, 134, 394, 420);
      art.addColorStop(0, '#1e3a5f');
      art.addColorStop(0.55, '#d9773b');
      art.addColorStop(1, '#1a1524');
      ctx.fillStyle = art;
      ctx.fill();
      ctx.fillStyle = 'rgba(255,244,218,0.88)';
      ctx.beginPath();
      ctx.arc(250, 248, 52, 0, Math.PI * 2);
      ctx.fill();
      ctx.fillStyle = '#11131b';
      ctx.fillRect(108, 302, 286, 118);
      ctx.fillStyle = '#f8fafc';
      ctx.font = 'bold 20px -apple-system, sans-serif';
      ctx.fillText('MODAL SOUL', 132, 348);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '14px Menlo, monospace';
      ctx.fillText('NUJABES · TOKYO 2005', 132, 374);

      // Live warm equalizer bars
      ctx.globalAlpha = 0.82;
      for (let i = 0; i < 28; i++) {
        const amp = 14 + Math.abs(Math.sin(t * 2.8 + i * 0.42)) * 46 + Math.abs(Math.cos(t * 1.9 - i * 0.25)) * 22;
        ctx.fillStyle = i < 16 ? '#f59e48' : '#38bdf8';
        ctx.fillRect(568 + i * 13, 356 - amp, 8, amp);
      }
      ctx.globalAlpha = 1.0;

      // Playback Progress Bar
      const prog = ((t * 4) % 180) / 180;
      ctx.fillStyle = '#f8fafc';
      this.roundRect(ctx, 568, 386, 80 + prog * 260, 6, 3);
      ctx.fill();
      return true;
    }

    if (channel === 'cinema') {
      const staticLayer = this.getStaticLayer('tv:cinema', w, h, (sctx) => {
        const sky = sctx.createLinearGradient(0, 0, 0, h);
        sky.addColorStop(0, '#070c18');
        sky.addColorStop(0.55, '#13203b');
        sky.addColorStop(1, '#261724');
        sctx.fillStyle = sky;
        sctx.fillRect(0, 0, w, h);

        const orbs: Array<[number, number, number, string]> = [
          [240, 260, 120, 'rgba(255, 130, 56, 0.28)'],
          [520, 210, 150, 'rgba(56, 189, 248, 0.22)'],
          [780, 290, 135, 'rgba(244, 114, 182, 0.22)'],
          [410, 390, 110, 'rgba(251, 191, 36, 0.20)'],
        ];
        for (const [ox, oy, or, col] of orbs) {
          const g = sctx.createRadialGradient(ox, oy, 8, ox, oy, or);
          g.addColorStop(0, col);
          g.addColorStop(1, 'rgba(0,0,0,0)');
          sctx.fillStyle = g;
          sctx.fillRect(0, 0, w, h);
        }

        sctx.fillStyle = '#090d16';
        for (let i = 0; i < 24; i++) {
          const bx = i * 44;
          const bh = 120 + ((i * 73) % 210);
          sctx.fillRect(bx, h - bh, 38, bh);
          sctx.fillStyle = i % 3 === 0 ? 'rgba(255,196,112,0.55)' : 'rgba(130,206,255,0.45)';
          for (let wy = h - bh + 18; wy < h - 24; wy += 16) {
            if (((i * 17 + wy) % 5) !== 0) {
              sctx.fillRect(bx + 7, wy, 9, 5);
              sctx.fillRect(bx + 21, wy, 9, 5);
            }
          }
          sctx.fillStyle = '#090d16';
        }

        sctx.fillStyle = 'rgba(248, 250, 252, 0.92)';
        sctx.font = '300 62px -apple-system, sans-serif';
        sctx.fillText('00:24', 64, 486);
        sctx.fillStyle = 'rgba(203, 213, 225, 0.78)';
        sctx.font = '16px -apple-system, sans-serif';
        sctx.fillText('SHIBUYA, TOKYO · LIGHT RAIN · 16°C', 68, 520);
      });

      ctx.drawImage(staticLayer, 0, 0);

      // Animated gentle rain streaks across glass (single batched path!)
      ctx.strokeStyle = 'rgba(200, 224, 255, 0.22)';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      for (let r = 0; r < 52; r++) {
        const rxp = ((r * 97 + t * 24) % (w + 60)) - 30;
        const ryp = ((r * 131 + t * 220) % (h + 80)) - 40;
        ctx.moveTo(rxp, ryp);
        ctx.lineTo(rxp - 4, ryp + 26);
      }
      ctx.stroke();
      return true;
    }

    // DEFAULT CHANNEL ('ps5'): Only the blinking clock colon changes (2 Hz)!
    const colonOn = Math.floor(t * 2) % 2 === 0;
    if (!force && colonOn === this.lastPs5Colon) {
      return false;
    }
    this.lastPs5Colon = colonOn;

    const staticLayer = this.getStaticLayer('tv:ps5', w, h, (sctx) => {
      const bg = sctx.createLinearGradient(0, 0, w, h);
      bg.addColorStop(0, '#0a1020');
      bg.addColorStop(0.45, '#19243d');
      bg.addColorStop(0.78, '#2c1f2e');
      bg.addColorStop(1, '#090c14');
      sctx.fillStyle = bg;
      sctx.fillRect(0, 0, w, h);

      const moon = sctx.createRadialGradient(760, 178, 12, 760, 178, 230);
      moon.addColorStop(0, 'rgba(255, 222, 168, 0.62)');
      moon.addColorStop(0.32, 'rgba(234, 122, 64, 0.28)');
      moon.addColorStop(1, 'rgba(12, 18, 34, 0)');
      sctx.fillStyle = moon;
      sctx.fillRect(0, 0, w, h);

      sctx.fillStyle = 'rgba(255, 240, 212, 0.92)';
      sctx.beginPath();
      sctx.arc(760, 178, 52, 0, Math.PI * 2);
      sctx.fill();

      sctx.fillStyle = '#151c2e';
      sctx.beginPath();
      sctx.moveTo(320, 440);
      sctx.lineTo(540, 248);
      sctx.lineTo(660, 316);
      sctx.lineTo(790, 218);
      sctx.lineTo(940, 330);
      sctx.lineTo(1024, 286);
      sctx.lineTo(1024, 576);
      sctx.lineTo(320, 576);
      sctx.closePath();
      sctx.fill();

      sctx.fillStyle = 'rgba(255, 232, 206, 0.26)';
      sctx.beginPath();
      sctx.moveTo(790, 218);
      sctx.lineTo(754, 250);
      sctx.lineTo(784, 246);
      sctx.lineTo(806, 258);
      sctx.lineTo(828, 247);
      sctx.closePath();
      sctx.fill();

      const vig = sctx.createLinearGradient(0, 0, 620, 0);
      vig.addColorStop(0, 'rgba(7, 10, 18, 0.86)');
      vig.addColorStop(0.7, 'rgba(7, 10, 18, 0.35)');
      vig.addColorStop(1, 'rgba(7, 10, 18, 0)');
      sctx.fillStyle = vig;
      sctx.fillRect(0, 0, w, h);

      sctx.fillStyle = '#ffffff';
      sctx.font = '600 18px -apple-system, sans-serif';
      sctx.fillText('Games', 54, 46);
      sctx.fillStyle = 'rgba(226, 232, 240, 0.55)';
      sctx.fillText('Media', 136, 46);
      sctx.fillStyle = '#38bdf8';
      sctx.fillRect(54, 54, 58, 2.5);

      sctx.fillStyle = 'rgba(255,255,255,0.14)';
      this.roundRect(sctx, 756, 25, 92, 26, 13);
      sctx.fill();
      sctx.fillStyle = '#e2e8f0';
      sctx.font = 'bold 11px Menlo, monospace';
      sctx.fillText('4K · HDR10', 768, 42);

      sctx.fillStyle = '#38bdf8';
      sctx.beginPath();
      sctx.arc(878, 38, 12, 0, Math.PI * 2);
      sctx.fill();
      sctx.fillStyle = '#090d16';
      sctx.font = 'bold 12px -apple-system, sans-serif';
      sctx.fillText('J', 874, 42);

      sctx.fillStyle = '#f59e48';
      sctx.font = 'bold 12px Menlo, monospace';
      sctx.fillText('PS5 PRO ENHANCED · 120HZ VRR', 54, 212);

      sctx.fillStyle = '#ffffff';
      sctx.font = '700 44px -apple-system, sans-serif';
      sctx.fillText('GHOST OF YŌTEI', 54, 262);

      sctx.fillStyle = 'rgba(226, 232, 240, 0.78)';
      sctx.font = '15px -apple-system, sans-serif';
      sctx.fillText('Resume Activity · Chapter IV — Snowfall Over Ezo  ·  Trophies 68%', 54, 294);

      this.roundRect(sctx, 54, 318, 152, 42, 21);
      sctx.fillStyle = '#f8fafc';
      sctx.fill();
      sctx.fillStyle = '#0a0f1c';
      sctx.font = '700 16px -apple-system, sans-serif';
      sctx.fillText('▶  PLAY', 92, 345);

      this.roundRect(sctx, 220, 318, 42, 42, 21);
      sctx.fillStyle = 'rgba(255, 255, 255, 0.14)';
      sctx.fill();
      sctx.fillStyle = '#f8fafc';
      sctx.font = 'bold 18px sans-serif';
      sctx.fillText('•••', 230, 345);

      const cards: Array<{ title: string; sub: string; c1: string; c2: string; accent: string }> = [
        { title: 'GHOST OF YŌTEI', sub: 'PS5', c1: '#1a2744', c2: '#d96b38', accent: '#fde68a' },
        { title: 'CYBERPUNK 2077', sub: 'PS5', c1: '#1c1836', c2: '#eab308', accent: '#38bdf8' },
        { title: 'ELDEN RING', sub: 'PS5', c1: '#142622', c2: '#b88b3a', accent: '#fef08a' },
        { title: 'GRAN TURISMO 7', sub: 'PS5', c1: '#1c2434', c2: '#dc2626', accent: '#f8fafc' },
        { title: 'SPOTIFY LO-FI', sub: 'MUSIC', c1: '#0f291e', c2: '#22c55e', accent: '#dcfce7' },
        { title: 'APPLE TV+', sub: 'CINEMA', c1: '#14171f', c2: '#475569', accent: '#e2e8f0' },
      ];

      cards.forEach((card, i) => {
        const cx = 54 + i * 156;
        const isSelected = i === 0;
        const cy = isSelected ? 394 : 408;
        const cw = isSelected ? 142 : 136;
        const ch = isSelected ? 142 : 128;

        if (isSelected) {
          sctx.strokeStyle = 'rgba(248, 250, 252, 0.92)';
          sctx.lineWidth = 3;
          this.roundRect(sctx, cx - 4, cy - 4, cw + 8, ch + 8, 14);
          sctx.stroke();
        }

        sctx.save();
        this.roundRect(sctx, cx, cy, cw, ch, 11);
        sctx.clip();
        const cg = sctx.createLinearGradient(cx, cy, cx + cw, cy + ch);
        cg.addColorStop(0, card.c1);
        cg.addColorStop(1, card.c2);
        sctx.fillStyle = cg;
        sctx.fillRect(cx, cy, cw, ch);

        sctx.fillStyle = card.accent;
        sctx.globalAlpha = 0.25;
        sctx.beginPath();
        sctx.arc(cx + cw * 0.74, cy + ch * 0.34, cw * 0.34, 0, Math.PI * 2);
        sctx.fill();
        sctx.globalAlpha = 1.0;

        sctx.fillStyle = 'rgba(8, 12, 22, 0.72)';
        sctx.fillRect(cx, cy + ch - 42, cw, 42);
        sctx.fillStyle = '#f8fafc';
        sctx.font = 'bold 11px -apple-system, sans-serif';
        sctx.fillText(card.title, cx + 10, cy + ch - 22);
        sctx.fillStyle = 'rgba(203, 213, 225, 0.72)';
        sctx.font = '10px Menlo, monospace';
        sctx.fillText(card.sub, cx + 10, cy + ch - 8);
        sctx.restore();
      });
    });

    ctx.drawImage(staticLayer, 0, 0);

    const pulseColon = colonOn ? ':' : ' ';
    ctx.fillStyle = '#f8fafc';
    ctx.font = '500 19px Menlo, monospace';
    ctx.fillText(`00${pulseColon}24`, 908, 45);
    return true;
  }
}
