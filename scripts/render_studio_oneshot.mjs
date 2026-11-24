#!/usr/bin/env node
/**
 * AStudio Geek Studio — Unbroken Continuous One-Shot Master Film ("一镜到底", ZERO CUTS!)
 *
 * Single continuous 34.0-second C1-smooth robotic cinema motion-control take (native 16:9 & 9:16 @ 60fps):
 *   0.0s –  8.8s : Left -> Right sweep | 24-Hour Lighting Cycle (Midnight -> Morning -> Noon -> Golden -> Midnight)
 *   8.8s – 16.4s : Right -> Left return sweep (seamless from Midnight!) | Whole-Studio Lighting & 6-Mode ARGB Neon Sync
 *  16.4s – 24.4s : Seamless Push-In -> 50mm f/2.8 Desktop Macro Glide ("高精度细节呈现 / High-Precision Detail") -> Deep Full-Studio Pull-Back
 *  24.4s – 34.0s : Wide Full-Studio L -> R sweep (wall-to-wall framing!) | Pure Clay & Wireframe Pause-at-50% Slider Breakdown (ONLY Final / Clay / Wire!)
 *
 * Typography: Equal-size Chinese & English titles (PingFang SC + SF Pro Display), zero overlap on 16:9 and 9:16 safe zones.
 * Audio: Custom Gemini Lyria 3.5 stereo soundtrack (-14 LUFS, AAC 256kbps 48kHz, smooth fade-in/out).
 *
 * Usage:
 *   node scripts/render_studio_oneshot.mjs --aspect=16x9 --url=http://127.0.0.1:4175/?oneshot=1
 *   node scripts/render_studio_oneshot.mjs --aspect=9x16 --url=http://127.0.0.1:4175/?oneshot=1
 */

import { spawn } from 'node:child_process';
import fs from 'node:fs/promises';
import os from 'node:os';
import path from 'node:path';

const CHROME = '/Applications/Google Chrome.app/Contents/MacOS/Google Chrome';
const FPS = 60;
const DT = 1 / FPS;
const TOTAL_DUR = 34.0;
const BREAKDOWN_START = 24.4;
const BREAKDOWN_DUR = +(TOTAL_DUR - BREAKDOWN_START).toFixed(4); // 9.6s

const args = Object.fromEntries(
  process.argv.slice(2).map((a) => {
    const eq = a.indexOf('=');
    if (eq === -1) return [a.replace(/^--/, ''), 'true'];
    return [a.slice(0, eq).replace(/^--/, ''), a.slice(eq + 1)];
  })
);

const aspect = args.aspect === '9x16' ? '9x16' : '16x9';
const isV = aspect === '9x16';
const W = isV ? 1080 : 1920;
const H = isV ? 1920 : 1080;
const APP_URL = args.url || 'http://127.0.0.1:5173/?oneshot=1';

const OUT_ROOT = path.resolve(process.cwd(), 'exports/videos/studio_oneshot');
const CLEAN_DIR = path.join(OUT_ROOT, 'clean_no_text');
const TMP_DIR = path.join(OUT_ROOT, `.tmp_${aspect}_${process.pid}`);
const BGM_FILE = path.resolve(process.cwd(), 'exports/videos/studio_oneshot/audio/bgm_tokyo_tech_ambient.mp3');

const clamp01 = (t) => Math.max(0, Math.min(1, t));
const smootherstep = (t) => {
  const x = clamp01(t);
  return x * x * x * (x * (x * 6 - 15) + 10);
};
const easeInOutSine = (t) => 0.5 - 0.5 * Math.cos(Math.PI * clamp01(t));
const lerp = (a, b, t) => a + (b - a) * t;
const lerp3 = (a, b, t) => [lerp(a[0], b[0], t), lerp(a[1], b[1], t), lerp(a[2], b[2], t)];
const dist3 = (a, b) => Math.hypot(a[0] - b[0], a[1] - b[1], a[2] - b[2]);

function evalQuad(p0, p1, p2, t) {
  const u = clamp01(t);
  const iu = 1 - u;
  return [
    iu * iu * p0[0] + 2 * iu * u * p1[0] + u * u * p2[0],
    iu * iu * p0[1] + 2 * iu * u * p1[1] + u * u * p2[1],
    iu * iu * p0[2] + 2 * iu * u * p1[2] + u * u * p2[2],
  ];
}

// ======================================================================================
// CONTINUOUS C1-SMOOTH ONE-SHOT CAMERA RIG (ZERO CUTS ACROSS ALL 34.0 SECONDS!)
// ======================================================================================
function evalOneShotCamera(t) {
  // Anchors tailored separately for 16:9 horizontal vs 9:16 vertical framing
  const P0_L = isV ? [-0.95, 1.48, 1.72] : [-1.10, 1.46, 1.56];
  const P0_M = isV ? [-0.15, 1.46, 1.72] : [-0.20, 1.44, 1.52];
  const P1_R = isV ? [0.56, 1.44, 1.66] : [0.66, 1.42, 1.48];
  const T0_L = [-0.24, 1.22, -1.45];
  const T1_R = [0.20, 1.22, -1.38];

  // Phase 2 Return Sweep (Right -> Left, gently showcasing bookshelf + hex + PC + desk!)
  const P2_M = isV ? [-0.18, 1.46, 1.76] : [-0.20, 1.44, 1.60];
  const P2_L = isV ? [-0.88, 1.46, 1.72] : [-1.04, 1.45, 1.56];
  const T2_M = isV ? [0.28, 1.24, -1.28] : [0.46, 1.24, -1.16];
  const T2_L = [-0.22, 1.18, -1.46];

  // Phase 3 Seamless Push-In -> Intimate 50mm Macro Glide -> Deep Wide Pull-Back!
  const P3_MAC_L = [-0.56, 1.03, -0.56];
  const P3_MAC_R = [0.24, 1.03, -0.56];
  const T3_MAC_L = [-0.28, 0.90, -1.44];
  const T3_MAC_R = [-0.08, 0.90, -1.46];

  // Phase 4 Pulled-Back Full Wall-to-Wall Studio Wide Framing (through open 3.2m portal!)
  const P4_L = isV ? [-0.42, 1.50, 2.38] : [-0.62, 1.48, 2.06];
  const P4_R = isV ? [0.34, 1.48, 2.36] : [0.44, 1.46, 2.04];
  const T4_L = [0.06, 1.24, -1.40];
  const T4_R = [0.14, 1.24, -1.40];

  const wideFov = isV ? 68 : 47;
  const macroFov = isV ? 52 : 35;
  const fullWideFov = isV ? 72 : 50;

  // Segment 1: 0.0 -> 8.8s (L -> R 24h Timelapse)
  if (t < 8.8) {
    const u = easeInOutSine(t / 8.8);
    return {
      pos: evalQuad(P0_L, P0_M, P1_R, u),
      tgt: lerp3(T0_L, T1_R, u),
      fov: wideFov,
      dof: false,
    };
  }
  // Segment 2: 8.8 -> 16.4s (R -> L Seamless Lighting & Synced Neon Return Sweep)
  if (t < 16.4) {
    const u = easeInOutSine((t - 8.8) / 7.6);
    return {
      pos: evalQuad(P1_R, P2_M, P2_L, u),
      tgt: evalQuad(T1_R, T2_M, T2_L, u),
      fov: wideFov,
      dof: false,
    };
  }
  // Segment 3A: 16.4 -> 19.4s (Seamless Push-In directly into 50mm Desktop Macro)
  if (t < 19.4) {
    const u = smootherstep((t - 16.4) / 3.0);
    const midPos = isV ? [-0.74, 1.24, 0.56] : [-0.82, 1.24, 0.48];
    const pos = evalQuad(P2_L, midPos, P3_MAC_L, u);
    const tgt = lerp3(T2_L, T3_MAC_L, u);
    const fov = lerp(wideFov, macroFov, u);
    return { pos, tgt, fov, dof: dist3(pos, tgt) < 1.85 };
  }
  // Segment 3B: 19.4 -> 21.4s (Intimate Macro Glide Left -> Right over keyboard, Stream Deck, Rubik's cube, screens!)
  if (t < 21.4) {
    const u = easeInOutSine((t - 19.4) / 2.0);
    const pos = lerp3(P3_MAC_L, P3_MAC_R, u);
    const tgt = lerp3(T3_MAC_L, T3_MAC_R, u);
    return { pos, tgt, fov: macroFov, dof: true };
  }
  // Segment 3C: 21.4 -> 24.4s (Seamless Deep Pull-Back all the way into Full Wall-to-Wall Studio Framing!)
  if (t < 24.4) {
    const u = smootherstep((t - 21.4) / 3.0);
    const midPos = isV ? [-0.08, 1.28, 0.92] : [-0.18, 1.28, 0.78];
    const pos = evalQuad(P3_MAC_R, midPos, P4_L, u);
    const tgt = lerp3(T3_MAC_R, T4_L, u);
    const fov = lerp(macroFov, fullWideFov, u);
    return { pos, tgt, fov, dof: dist3(pos, tgt) < 1.85 };
  }
  // Segment 4: 24.4 -> 34.0s (Pulled-Back Full Studio L -> R Sweep for Pure Clay & Wireframe Pause-at-50% Comparison!)
  const u = easeInOutSine((t - 24.4) / BREAKDOWN_DUR);
  return {
    pos: lerp3(P4_L, P4_R, u),
    tgt: lerp3(T4_L, T4_R, u),
    fov: fullWideFov,
    dof: false,
  };
}

function runFfmpeg(ffArgs, label = 'ffmpeg') {
  return new Promise((resolve, reject) => {
    const proc = spawn('ffmpeg', ['-y', '-loglevel', 'error', ...ffArgs], { stdio: ['ignore', 'pipe', 'pipe'] });
    let err = '';
    proc.stderr.on('data', (d) => (err += d.toString()));
    proc.on('exit', (code) => {
      if (code === 0) resolve();
      else reject(new Error(`${label} failed (${code}):\n${err}`));
    });
  });
}

async function launchChrome(width, height, { transparent = false } = {}) {
  const userDataDir = await fs.mkdtemp(path.join(os.tmpdir(), `astudio-oneshot-${aspect}-`));
  const flags = [
    '--headless=new',
    '--remote-debugging-port=0',
    '--remote-allow-origins=*',
    `--user-data-dir=${userDataDir}`,
    `--window-size=${width},${height}`,
    '--force-device-scale-factor=1',
    '--no-first-run',
    '--no-default-browser-check',
    '--disable-background-timer-throttling',
    '--disable-renderer-backgrounding',
  ];
  if (!transparent) {
    flags.push('--enable-webgl', '--ignore-gpu-blocklist', '--use-gl=angle', '--use-angle=metal');
  }
  flags.push('about:blank');

  const chrome = spawn(CHROME, flags, { stdio: ['ignore', 'pipe', 'pipe'] });
  const bws = await new Promise((resolve, reject) => {
    const timer = setTimeout(() => reject(new Error('Chrome startup timeout')), 20000);
    let buf = '';
    chrome.stderr.on('data', (chunk) => {
      buf += chunk.toString();
      const m = buf.match(/DevTools listening on (ws:\/\/[^\s]+)/);
      if (m) { clearTimeout(timer); resolve(m[1]); }
    });
    chrome.on('exit', (code) => { clearTimeout(timer); reject(new Error(`Chrome exited early: ${code}\n${buf}`)); });
  });

  const port = new URL(bws).port;
  const pages = await (await fetch(`http://127.0.0.1:${port}/json/list`)).json();
  const pageTarget = pages.find((p) => p.type === 'page' && p.webSocketDebuggerUrl);
  const ws = new WebSocket(pageTarget.webSocketDebuggerUrl);
  await new Promise((res, rej) => { ws.onopen = res; ws.onerror = rej; });

  let nextId = 1;
  const pending = new Map();
  ws.onmessage = (ev) => {
    const msg = JSON.parse(ev.data);
    if (msg.id && pending.has(msg.id)) {
      const { resolve, reject } = pending.get(msg.id);
      pending.delete(msg.id);
      if (msg.error) reject(new Error(msg.error.message));
      else resolve(msg.result);
    }
  };
  const send = (method, params = {}) =>
    new Promise((resolve, reject) => {
      const id = nextId++;
      pending.set(id, { resolve, reject });
      ws.send(JSON.stringify({ id, method, params }));
    });
  const evalJs = async (expression) => {
    const res = await send('Runtime.evaluate', { expression, awaitPromise: true, returnByValue: true });
    if (res.exceptionDetails) throw new Error(JSON.stringify(res.exceptionDetails));
    return res.result?.value;
  };

  await send('Page.enable');
  await send('Emulation.setDeviceMetricsOverride', { width, height, deviceScaleFactor: 1, mobile: false });
  if (transparent) {
    await send('Emulation.setDefaultBackgroundColorOverride', { color: { r: 0, g: 0, b: 0, a: 0 } });
  } else {
    await send('Page.navigate', { url: `${APP_URL}&aspect=${aspect}&ts=${Date.now()}` });
    await new Promise((r) => setTimeout(r, 800));
    for (let i = 0; i < 200; i++) {
      let ready = false;
      try {
        ready = await evalJs(`(() => {
          const ov = document.getElementById('loading-overlay');
          const st = document.getElementById('loading-status')?.textContent || '';
          const hidden = !ov || ov.classList.contains('hidden') || ov.classList.contains('is-hidden') || getComputedStyle(ov).opacity === '0';
          return Boolean(window.__ASTUDIO__?.director && (hidden || st.includes('准备就绪') || st.toLowerCase().includes('ready')));
        })()`);
      } catch {}
      if (ready) break;
      await new Promise((r) => setTimeout(r, 250));
    }
    await new Promise((r) => setTimeout(r, 400));
    await evalJs(`window.__ASTUDIO__.director.enterCapture(${width}, ${height})`);
    await new Promise((r) => setTimeout(r, 150));
  }

  return {
    send,
    evalJs,
    frameId: pageTarget.id,
    async close() {
      try { ws.close(); } catch {}
      try { chrome.kill('SIGTERM'); } catch {}
      await fs.rm(userDataDir, { recursive: true, force: true }).catch(() => {});
    },
  };
}

async function recordPass(ctx, outFile, startSec, durationSec, setupFn, onFrameFn) {
  const totalFrames = Math.round(durationSec * FPS);
  const startFrame = Math.round(startSec * FPS);
  const t0 = performance.now();

  if (setupFn) await setupFn();
  await onFrameFn(startSec, 0, true);
  await ctx.evalJs(`new Promise(r => { window.__ASTUDIO__.director.step(${DT}, ${startSec}); setTimeout(() => r(true), 4); })`);

  const ff = spawn(
    'ffmpeg',
    [
      '-y', '-loglevel', 'error',
      '-f', 'image2pipe', '-vcodec', 'mjpeg', '-framerate', String(FPS), '-i', '-',
      '-c:v', 'libx264', '-preset', 'fast', '-crf', '13', '-pix_fmt', 'yuv420p',
      '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
      outFile,
    ],
    { stdio: ['pipe', 'ignore', 'pipe'] }
  );
  let ffErr = '';
  ff.stderr.on('data', (d) => (ffErr += d.toString()));
  const ffDone = new Promise((resolve, reject) => {
    ff.on('exit', (code) => (code === 0 ? resolve() : reject(new Error(`recordPass failed (${code}):\n${ffErr}`))));
  });

  for (let i = 0; i < totalFrames; i++) {
    const absT = (startFrame + i) * DT;
    const localT = i * DT;
    await onFrameFn(absT, localT, false);
    await ctx.evalJs(
      `new Promise(r => { window.__ASTUDIO__.director.step(${DT}, ${absT.toFixed(6)}); setTimeout(() => r(true), 4); })`
    );
    const { data } = await ctx.send('Page.captureScreenshot', { format: 'jpeg', quality: 95 });
    const buf = Buffer.from(data, 'base64');
    if (!ff.stdin.write(buf)) await new Promise((r) => ff.stdin.once('drain', r));
  }

  ff.stdin.end();
  await ffDone;
  const ms = performance.now() - t0;
  console.log(`  [${aspect}] Captured ${path.basename(outFile)} (${totalFrames}f / ${durationSec.toFixed(2)}s in ${(ms / 1000).toFixed(1)}s, ${(ms / totalFrames).toFixed(1)}ms/f)`);
}

function pauseWipeX(width, t1, dHalf, dPause, dEnd) {
  const t2 = +(t1 + dHalf).toFixed(4);
  const t3 = +(t2 + dPause).toFixed(4);
  const t4 = +(t3 + dEnd).toFixed(4);
  const half = (width * 0.5).toFixed(2);
  return (
    `if(lt(t\\,${t1})\\,0\\,` +
    `if(lt(t\\,${t2})\\,${half}*(1-pow(1-(t-${t1})/${dHalf}\\,3))\\,` +
    `if(lt(t\\,${t3})\\,${half}\\,` +
    `if(lt(t\\,${t4})\\,${half}*(1+pow((t-${t3})/${dEnd}\\,2)*(3-2*(t-${t3})/${dEnd}))\\,` +
    `${width}))))`
  );
}

// ======================================================================================
// EQUAL-SIZE BILINGUAL (CHINESE === ENGLISH FONT SIZE!) TRANSPARENT PLATE RENDERER
// ======================================================================================
async function renderEqualBilingualPlates(plateDir) {
  const pChrome = await launchChrome(W, H, { transparent: true });
  const renderOne = async (name, bodyHtml) => {
    const html = `<!DOCTYPE html>
<html><head><meta charset="utf-8"><style>
  * { box-sizing: border-box; margin: 0; padding: 0; }
  html, body {
    width: ${W}px; height: ${H}px; background: transparent; overflow: hidden;
    font-family: "PingFang SC", -apple-system, BlinkMacSystemFont, "SF Pro Display", "Helvetica Neue", sans-serif;
    -webkit-font-smoothing: antialiased; color: #f8f7f4;
  }
  .lower-block {
    position: absolute;
    left: ${isV ? 52 : 68}px;
    right: ${isV ? 52 : 68}px;
    bottom: ${isV ? 215 : 58}px;
    display: flex; flex-direction: column;
  }
  .lower-card {
    display: inline-flex; flex-direction: column; align-items: flex-start; gap: ${isV ? 6 : 5}px;
    padding: ${isV ? '18px 24px 20px 22px' : '16px 26px 18px 24px'};
    background: linear-gradient(135deg, rgba(10, 12, 18, 0.64), rgba(14, 17, 25, 0.46));
    border: 1px solid rgba(255, 255, 255, 0.17);
    border-left: 3.5px solid var(--accent, #ffbe78);
    border-radius: 10px;
    box-shadow: 0 12px 36px rgba(0, 0, 0, 0.44);
    max-width: ${isV ? 976 : 820}px;
  }
  /* EQUAL VISUAL WEIGHT & IDENTICAL FONT SIZE FOR CHINESE AND ENGLISH TITLES! */
  .zh-title, .en-title {
    font-size: ${isV ? 31 : 28}px;
    line-height: 1.24;
    text-shadow: 0 2px 14px rgba(0, 0, 0, 0.68);
  }
  .zh-title {
    font-weight: 600;
    letter-spacing: 0.06em;
    color: #ffffff;
  }
  .en-title {
    font-weight: 500;
    letter-spacing: 0.03em;
    color: rgba(242, 245, 252, 0.92);
  }
  .top-pill {
    position: absolute;
    ${isV ? 'bottom: 392px; left: 52px;' : 'top: 44px; right: 68px;'}
    display: inline-flex; align-items: center; gap: 11px;
    padding: ${isV ? '11px 22px' : '10px 22px'};
    background: rgba(10, 12, 18, 0.64);
    border: 1px solid rgba(255, 255, 255, 0.18);
    border-radius: 999px;
    box-shadow: 0 8px 26px rgba(0, 0, 0, 0.42);
  }
  .dot {
    width: ${isV ? 10 : 9}px; height: ${isV ? 10 : 9}px; border-radius: 50%;
    background: var(--dot, #ffbe78); box-shadow: 0 0 12px var(--dot, #ffbe78);
  }
  .pill-zh, .pill-en {
    font-size: ${isV ? 22 : 20}px;
    line-height: 1.2;
    color: #faf9f6;
  }
  .pill-zh { font-weight: 600; letter-spacing: 0.05em; }
  .pill-en { font-weight: 500; letter-spacing: 0.02em; color: rgba(242, 245, 252, 0.92); }
  .pill-sep { color: rgba(255, 255, 255, 0.36); font-size: ${isV ? 20 : 18}px; }

  /* 50/50 Split Comparison Badges straddling exact center x = 50% (Chinese === English font size!) */
  .split-wrap {
    position: absolute;
    top: ${isV ? 148 : 50}px;
    left: 0; right: 0;
  }
  .split-side {
    position: absolute; top: 0;
    display: inline-flex; flex-direction: column; gap: 4px;
    padding: ${isV ? '13px 20px' : '12px 24px'};
    background: rgba(10, 12, 18, 0.70);
    border: 1px solid rgba(255, 255, 255, 0.22);
    border-radius: 9px;
    box-shadow: 0 10px 28px rgba(0, 0, 0, 0.48);
  }
  .split-left { right: calc(50% + ${isV ? 16 : 26}px); align-items: flex-end; text-align: right; border-right: 3.5px solid var(--lcol, #ffffff); }
  .split-right { left: calc(50% + ${isV ? 16 : 26}px); align-items: flex-start; text-align: left; border-left: 3.5px solid var(--rcol, #ffbe78); }
  .split-zh, .split-en {
    font-size: ${isV ? 24 : 24}px;
    line-height: 1.2;
    color: #ffffff;
  }
  .split-zh { font-weight: 600; letter-spacing: 0.06em; }
  .split-en { font-weight: 500; letter-spacing: 0.02em; color: rgba(240, 244, 252, 0.92); }

  .hero-band {
    position: absolute;
    left: ${isV ? 52 : 68}px;
    top: ${isV ? 142 : 44}px;
    display: inline-flex; flex-direction: column; gap: 5px;
    padding: ${isV ? '15px 22px' : '13px 22px'};
    background: rgba(10, 12, 18, 0.60);
    border: 1px solid rgba(255, 255, 255, 0.16);
    border-radius: 10px;
  }
  .brand-zh, .brand-en {
    font-size: ${isV ? 25 : 22}px;
    line-height: 1.24;
  }
  .brand-zh { font-weight: 600; letter-spacing: 0.06em; color: #ffffff; }
  .brand-en { font-weight: 500; letter-spacing: 0.04em; color: #ffbe78; }
</style></head><body>${bodyHtml}</body></html>`;
    await pChrome.send('Page.setDocumentContent', { frameId: pChrome.frameId, html });
    await new Promise((r) => setTimeout(r, 35));
    const { data } = await pChrome.send('Page.captureScreenshot', { format: 'png', omitBackground: true });
    const outPng = path.join(plateDir, `${name}.png`);
    await fs.writeFile(outPng, Buffer.from(data, 'base64'));
    return outPng;
  };

  const lower = (zh, en, accent = '#ffbe78') => `
    <div class="lower-block">
      <div class="lower-card" style="--accent:${accent}">
        <div class="zh-title">${zh}</div>
        <div class="en-title">${en}</div>
      </div>
    </div>`;
  const pill = (zh, en, dot = '#ffbe78') => `
    <div class="top-pill" style="--dot:${dot}">
      <span class="dot"></span>
      <span class="pill-zh">${zh}</span>
      <span class="pill-sep">·</span>
      <span class="pill-en">${en}</span>
    </div>`;
  const split = (lZh, lEn, lCol, rZh, rEn, rCol) => `
    <div class="split-wrap">
      <div class="split-side split-left" style="--lcol:${lCol}">
        <div class="split-zh">${lZh}</div>
        <div class="split-en">${lEn}</div>
      </div>
      <div class="split-side split-right" style="--rcol:${rCol}">
        <div class="split-zh">${rZh}</div>
        <div class="split-en">${rEn}</div>
      </div>
    </div>`;
  const brand = (zh, en) => `
    <div class="hero-band">
      <div class="brand-zh">${zh}</div>
      <div class="brand-en">${en}</div>
    </div>`;

  const P = {};
  try {
    P.brand_open = await renderOne('brand_open', brand('ASTUDIO · 东京极客工作室', 'Real-Time 3D Studio'));
    P.brand_end = await renderOne('brand_end', brand('60FPS 实时可交互空间', 'Interactive WebGL2 Studio'));

    P.p1_card = await renderOne('p1_card', lower('24 小时光影流转', '24-Hour Lighting Cycle', '#ffb96b'));
    P.p1_midnight = await renderOne('p1_midnight', pill('00:30 深夜直播', 'Midnight Stream', '#4cd8ff'));
    P.p1_morning = await renderOne('p1_morning', pill('07:30 清晨日景', 'Morning Daylight', '#ffe0b3'));
    P.p1_noon = await renderOne('p1_noon', pill('12:30 正午晴空', 'High Noon', '#ffffff'));
    P.p1_golden = await renderOne('p1_golden', pill('17:45 黄金时刻', 'Golden Hour', '#ff9640'));

    P.p2_card = await renderOne('p2_card', lower('全屋灯光与霓虹联动', 'Dynamic Lighting & Neon', '#4cd8ff'));
    P.p2_bright = await renderOne('p2_bright', pill('全屋开灯 · 冰青', 'Full Bright · Cyan', '#4cd8ff'));
    P.p2_rainbow = await renderOne('p2_rainbow', pill('柔光氛围 · 彩虹', 'Cozy · Rainbow', '#ff64c8'));
    P.p2_flow = await renderOne('p2_flow', pill('柔光氛围 · 流光', 'Cozy · Aurora Flow', '#52f0c4'));
    P.p2_cinema = await renderOne('p2_cinema', pill('关灯影院 · 幻彩', 'Cinema · Chroma', '#b478ff'));
    P.p2_breath = await renderOne('p2_breath', pill('柔光氛围 · 呼吸', 'Cozy · Breathing', '#ff74a4'));

    P.p3_macro = await renderOne('p3_macro', lower('高精度细节呈现', 'High-Precision Detail', '#ffb96b'));
    P.p3_pull = await renderOne('p3_pull', lower('工作室全景呈现', 'Full Studio Showcase', '#4cd8ff'));

    P.p4_card = await renderOne('p4_card', lower('白模与线稿对比', 'Clay & Wireframe Compare', '#ffffff'));
    P.p4_split1 = await renderOne('p4_split1', split('纯白模', 'Pure Clay', '#f4f2ec', '实时实景', 'Real-Time PBR', '#4cd8ff'));
    P.p4_split2 = await renderOne('p4_split2', split('拓扑线稿', 'Wireframe', '#88d4ff', '纯白模', 'Pure Clay', '#f4f2ec'));
    P.p4_split3 = await renderOne('p4_split3', split('实时实景', 'Real-Time PBR', '#ffbe78', '拓扑线稿', 'Wireframe', '#88d4ff'));
  } finally {
    await pChrome.close();
  }
  return P;
}

async function main() {
  await fs.mkdir(OUT_ROOT, { recursive: true });
  await fs.mkdir(CLEAN_DIR, { recursive: true });
  await fs.mkdir(TMP_DIR, { recursive: true });

  console.log(`\n=== [${aspect}] Launching Metal Chrome for 34s Unbroken One-Shot Studio Master (${W}x${H} @ ${FPS}fps) ===`);
  const ctx = await launchChrome(W, H);

  const finalPassFile = path.join(TMP_DIR, 'pass_final_34s.mp4');
  const clayPassFile = path.join(TMP_DIR, 'pass_clay_p4.mp4');
  const wirePassFile = path.join(TMP_DIR, 'pass_wire_p4.mp4');
  const cleanOneShotFile = path.join(CLEAN_DIR, `studio_oneshot_clean_${aspect}.mp4`);
  const masterOutFile = path.join(OUT_ROOT, `studio_oneshot_${aspect}.mp4`);

  // Timeline event cues during the unbroken 34.0s Final pass!
  const cues = [
    // Phase 1 (0.0 -> 8.8s): 24h cycle arriving cleanly into Midnight!
    { sec: 0.40, fn: `d.setMoodTransitionDuration(1.85); d.setMood('daylight');` },
    { sec: 2.50, fn: `d.setMoodTransitionDuration(1.85); d.setMood('noon');` },
    { sec: 4.60, fn: `d.setMoodTransitionDuration(1.85); d.setMood('golden');` },
    { sec: 6.70, fn: `d.setMoodTransitionDuration(1.80); d.setMood('midnight');` },
    // Phase 2 (8.8 -> 16.4s): Seamless transition directly into Midnight Lighting + Synced ARGB Neon!
    { sec: 10.00, fn: `d.setLightScene('cozy'); d.setRgbMode(1);` },
    { sec: 11.40, fn: `d.setLightScene('cozy'); d.setRgbMode(2);` },
    { sec: 12.80, fn: `d.setLightScene('cinema'); d.setRgbMode(3);` },
    { sec: 14.10, fn: `d.setLightScene('cozy'); d.setRgbMode(4);` },
    { sec: 15.30, fn: `d.setLightScene('bright'); d.setRgbMode(0);` },
    // Phase 3 (16.4 -> 24.4s): Seamless Push-In -> Macro -> Pull-Back (subtle rainbow glimmer at macro, cyber cyan on full reveal!)
    { sec: 19.60, fn: `d.setRgbMode(1);` },
    { sec: 21.80, fn: `d.setRgbMode(0);` },
  ];
  const fired = new Set();

  try {
    // PASS 1: Entire continuous 34.0s Final Studio One-Shot!
    await recordPass(
      ctx,
      finalPassFile,
      0.0,
      TOTAL_DUR,
      async () => {
        await ctx.evalJs(`(() => {
          const d = window.__ASTUDIO__.director;
          d.setRenderMode('final');
          d.setLightScene('bright');
          d.setMacroDof(false, 1.5, 3.0);
          d.snapMood('midnight');
          d.setRgbMode(0);
        })()`);
      },
      async (absT) => {
        const cam = evalOneShotCamera(absT);
        let extra = '';
        for (let i = 0; i < cues.length; i++) {
          if (!fired.has(i) && absT >= cues[i].sec) {
            fired.add(i);
            extra += cues[i].fn;
          }
        }
        const fd = dist3(cam.pos, cam.tgt) + 0.08;
        await ctx.evalJs(
          `(() => { const d = window.__ASTUDIO__.director; ${extra} ` +
            `d.setMacroDof(${cam.dof}, ${fd.toFixed(3)}, 3.35); ` +
            `d.setCamera(${JSON.stringify(cam.pos)}, ${JSON.stringify(cam.tgt)}, ${cam.fov.toFixed(3)}); })()`
        );
      }
    );

    // PASS 2: Pixel-locked Pure Clay pass strictly on Phase 4 (24.4s -> 34.0s, 9.6s!)
    await recordPass(
      ctx,
      clayPassFile,
      BREAKDOWN_START,
      BREAKDOWN_DUR,
      async () => {
        await ctx.evalJs(`(() => {
          const d = window.__ASTUDIO__.director;
          d.setMacroDof(false, 1.5, 3.0);
          d.snapMood('midnight');
          d.setLightScene('bright');
          d.setRgbMode(0);
          d.setRenderMode('clay');
        })()`);
      },
      async (absT) => {
        const cam = evalOneShotCamera(absT);
        await ctx.evalJs(
          `window.__ASTUDIO__.director.setCamera(${JSON.stringify(cam.pos)}, ${JSON.stringify(cam.tgt)}, ${cam.fov.toFixed(3)})`
        );
      }
    );

    // PASS 3: Pixel-locked Wireframe pass strictly on Phase 4 (24.4s -> 34.0s, 9.6s!)
    await recordPass(
      ctx,
      wirePassFile,
      BREAKDOWN_START,
      BREAKDOWN_DUR,
      async () => {
        await ctx.evalJs(`(() => {
          const d = window.__ASTUDIO__.director;
          d.setMacroDof(false, 1.5, 3.0);
          d.snapMood('midnight');
          d.setLightScene('bright');
          d.setRgbMode(0);
          d.setRenderMode('wire');
        })()`);
      },
      async (absT) => {
        const cam = evalOneShotCamera(absT);
        await ctx.evalJs(
          `window.__ASTUDIO__.director.setCamera(${JSON.stringify(cam.pos)}, ${JSON.stringify(cam.tgt)}, ${cam.fov.toFixed(3)})`
        );
      }
    );
  } finally {
    await ctx.close();
  }

  // Step A: Composite the 3 Pause-at-50% Clay & Wireframe wipes seamlessly onto [24.4s .. 34.0s] -> Textless Clean One-Shot + Music!
  // Local timestamps inside Phase 4 (t = 0.0 -> 9.6s corresponds to global 24.4s -> 34.0s):
  //   Wipe 1 (Final -> Pure Clay):  0.45 -> 1.10 (50%) | PAUSE 1.10..2.20 | 2.20 -> 2.85 (100%)
  //   Wipe 2 (Pure Clay -> Wire):   3.45 -> 4.10 (50%) | PAUSE 4.10..5.20 | 5.20 -> 5.85 (100%)
  //   Wipe 3 (Wire -> Final):       6.45 -> 7.10 (50%) | PAUSE 7.10..8.10 | 8.10 -> 8.70 (100%) -> 9.60 full beauty!
  const x1 = pauseWipeX(W, 0.45, 0.65, 1.10, 0.65);
  const x2 = pauseWipeX(W, 3.45, 0.65, 1.10, 0.65);
  const x3 = pauseWipeX(W, 6.45, 0.65, 1.00, 0.60);
  const barW = 4;

  const p4CompFile = path.join(TMP_DIR, 'p4_pause_comp.mp4');
  const p4Filter = [
    `[0:v]trim=start=${BREAKDOWN_START}:duration=${BREAKDOWN_DUR},setpts=PTS-STARTPTS,format=rgb24,split=2[fin_open][fin_close]`,
    `[1:v]format=rgb24[clay_rgb]`,
    `[2:v]format=rgb24[wire_rgb]`,
    `color=c=white:s=2x2:r=${FPS}:d=${BREAKDOWN_DUR},format=gray,lut=y=255,scale=${W}:${H}:flags=neighbor[mw]`,
    `color=c=black:s=2x2:r=${FPS}:d=${BREAKDOWN_DUR},format=gray,lut=y=0,scale=${W}:${H}:flags=neighbor[mb]`,
    `[mw][mb]hstack=inputs=2,split=3[m2w_1][m2w_2][m2w_3]`,
    `color=c=white@0.96:s=${barW}x${H}:r=${FPS}:d=${BREAKDOWN_DUR},split=3[bar1][bar2][bar3]`,
    `color=c=black@0.35:s=${barW + 4}x${H}:r=${FPS}:d=${BREAKDOWN_DUR},split=3[sh1][sh2][sh3]`,

    `[m2w_1]crop=w=${W}:h=${H}:x='${W}-(${x1})':y=0[mask1]`,
    `[clay_rgb][mask1]alphamerge[clay_a]`,
    `[fin_open][clay_a]overlay=0:0:shortest=1[s1_raw]`,
    `[s1_raw][sh1]overlay=x='(${x1})-4':y=0:enable='between(t,0.45,2.85)'[s1_sh]`,
    `[s1_sh][bar1]overlay=x='(${x1})-2':y=0:enable='between(t,0.45,2.85)'[s1]`,

    `[m2w_2]crop=w=${W}:h=${H}:x='${W}-(${x2})':y=0[mask2]`,
    `[wire_rgb][mask2]alphamerge[wire_a]`,
    `[s1][wire_a]overlay=0:0:shortest=1[s2_raw]`,
    `[s2_raw][sh2]overlay=x='(${x2})-4':y=0:enable='between(t,3.45,5.85)'[s2_sh]`,
    `[s2_sh][bar2]overlay=x='(${x2})-2':y=0:enable='between(t,3.45,5.85)'[s2]`,

    `[m2w_3]crop=w=${W}:h=${H}:x='${W}-(${x3})':y=0[mask3]`,
    `[fin_close][mask3]alphamerge[fin_a]`,
    `[s2][fin_a]overlay=0:0:shortest=1[s3_raw]`,
    `[s3_raw][sh3]overlay=x='(${x3})-4':y=0:enable='between(t,6.45,8.70)'[s3_sh]`,
    `[s3_sh][bar3]overlay=x='(${x3})-2':y=0:enable='between(t,6.45,8.70)'[out]`,
  ].join(';');

  await runFfmpeg(
    [
      '-i', finalPassFile, '-i', clayPassFile, '-i', wirePassFile,
      '-filter_complex', p4Filter, '-map', '[out]',
      '-r', String(FPS), '-c:v', 'libx264', '-preset', 'fast', '-crf', '13', '-pix_fmt', 'yuv420p',
      '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
      p4CompFile,
    ],
    'oneshot_p4_pause_wipe'
  );

  // Seamlessly splice [0.0..24.4s] + [p4_pause_comp 9.6s] with ZERO cut/frame-drop (exact 1464f + 576f = 2040f = 34.000s!) + Lyria 3.5 BGM!
  await runFfmpeg(
    [
      '-i', finalPassFile,
      '-i', p4CompFile,
      '-ss', '11.0', '-t', String(TOTAL_DUR + 0.2), '-i', BGM_FILE,
      '-filter_complex',
      `[0:v]trim=start=0:duration=${BREAKDOWN_START},setpts=PTS-STARTPTS[vhead];` +
        `[1:v]setpts=PTS-STARTPTS[vtail];` +
        `[vhead][vtail]concat=n=2:v=1:a=0,fade=t=in:st=0:d=0.45,fade=t=out:st=${(TOTAL_DUR - 0.65).toFixed(3)}:d=0.65,scale=in_range=full:out_range=tv:out_color_matrix=bt709,format=yuv420p[vclean];` +
        `[2:a]aresample=48000,loudnorm=I=-14:TP=-1.5:LRA=11,afade=t=in:st=0:d=0.55,afade=t=out:st=${(TOTAL_DUR - 1.85).toFixed(3)}:d=1.85[aclean]`,
      '-map', '[vclean]', '-map', '[aclean]', '-shortest',
      '-r', String(FPS), '-c:v', 'libx264', '-profile:v', 'high', '-level:v', '4.2', '-preset', 'fast', '-crf', '17',
      '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
      '-c:a', 'aac', '-b:a', '256k', '-ar', '48000', '-ac', '2', '-movflags', '+faststart',
      cleanOneShotFile,
    ],
    'oneshot_clean_splice'
  );
  console.log(`  [${aspect}] Clean textless one-shot ready: ${cleanOneShotFile}`);

  // Step B: Render Equal-Size Bilingual PNG Plates & Burn Cleanly onto the 34.0s One-Shot!
  const plateDir = path.join(TMP_DIR, 'plates');
  await fs.mkdir(plateDir, { recursive: true });
  const P = await renderEqualBilingualPlates(plateDir);

  const overlays = [
    // Brand opening (left top) & finale signoff
    { file: P.brand_open, start: 0.35, end: 3.40, fadeIn: 0.35, fadeOut: 0.35 },

    // Phase 1 (0.0 -> 8.8s): 24h Lighting Cycle
    { file: P.p1_card, start: 0.35, end: 8.55 },
    { file: P.p1_midnight, start: 0.30, end: 1.45, fadeIn: 0.22, fadeOut: 0.22 },
    { file: P.p1_morning, start: 1.50, end: 3.55, fadeIn: 0.22, fadeOut: 0.22 },
    { file: P.p1_noon, start: 3.60, end: 5.65, fadeIn: 0.22, fadeOut: 0.22 },
    { file: P.p1_golden, start: 5.70, end: 7.55, fadeIn: 0.22, fadeOut: 0.22 },
    { file: P.p1_midnight, start: 7.60, end: 8.75, fadeIn: 0.22, fadeOut: 0.20 },

    // Phase 2 (8.8 -> 16.4s): Seamless Midnight -> Dynamic Lighting & Synced Neon!
    { file: P.p2_card, start: 8.85, end: 16.25 },
    { file: P.p2_bright, start: 8.80, end: 9.95, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.p2_rainbow, start: 10.00, end: 11.35, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.p2_flow, start: 11.40, end: 12.75, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.p2_cinema, start: 12.80, end: 14.05, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.p2_breath, start: 14.10, end: 15.25, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.p2_bright, start: 15.30, end: 16.30, fadeIn: 0.20, fadeOut: 0.25 },

    // Phase 3 (16.4 -> 24.4s): Seamless Push-In Macro ("高精度细节呈现 / High-Precision Detail") -> Pull-Back Reveal!
    { file: P.p3_macro, start: 17.00, end: 21.65, fadeIn: 0.30, fadeOut: 0.30 },
    { file: P.p3_pull, start: 21.85, end: 24.25, fadeIn: 0.28, fadeOut: 0.28 },

    // Phase 4 (24.4 -> 34.0s): Pulled-Back Full Studio Clay & Wireframe Pause-at-50% Breakdown!
    { file: P.p4_card, start: 24.55, end: 33.40, fadeIn: 0.28, fadeOut: 0.35 },
    { file: P.p4_split1, start: 25.45, end: 26.70, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.p4_split2, start: 28.45, end: 29.70, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.p4_split3, start: 31.45, end: 32.58, fadeIn: 0.20, fadeOut: 0.20 },
    { file: P.brand_end, start: 32.65, end: 33.75, fadeIn: 0.25, fadeOut: 0.35 },
  ];

  const ovInputs = ['-i', cleanOneShotFile];
  const ovParts = [];
  let prev = '[0:v]';
  overlays.forEach((ov, i) => {
    const idx = i + 1;
    ovInputs.push('-loop', '1', '-t', TOTAL_DUR.toFixed(3), '-i', ov.file);
    const fi = ov.fadeIn ?? 0.28;
    const fo = ov.fadeOut ?? 0.28;
    const foSt = Math.max(ov.start + 0.05, ov.end - fo);
    ovParts.push(
      `[${idx}:v]format=rgba,fade=t=in:st=${ov.start.toFixed(3)}:d=${fi.toFixed(3)}:alpha=1,` +
        `fade=t=out:st=${foSt.toFixed(3)}:d=${fo.toFixed(3)}:alpha=1[ov${i}]`
    );
    const next = i === overlays.length - 1 ? '[vfinal]' : `[c${i}]`;
    ovParts.push(
      `${prev}[ov${i}]overlay=0:0:eof_action=pass:enable='between(t,${ov.start.toFixed(3)},${ov.end.toFixed(3)})'${next}`
    );
    prev = next;
  });

  await runFfmpeg(
    [
      ...ovInputs,
      '-filter_complex', ovParts.join(';'),
      '-map', '[vfinal]', '-map', '0:a',
      '-r', String(FPS), '-c:v', 'libx264', '-profile:v', 'high', '-level:v', '4.2', '-preset', 'fast', '-crf', '17',
      '-pix_fmt', 'yuv420p', '-color_range', 'tv', '-colorspace', 'bt709', '-color_primaries', 'bt709', '-color_trc', 'bt709',
      '-c:a', 'copy', '-movflags', '+faststart',
      masterOutFile,
    ],
    `oneshot_burn_bilingual(${aspect})`
  );

  const st = await fs.stat(masterOutFile);
  console.log(`==> ONE-SHOT MASTER READY [${aspect}]: ${masterOutFile} (${(st.size / (1024 * 1024)).toFixed(2)} MB, ${TOTAL_DUR.toFixed(2)}s)`);
  await fs.rm(TMP_DIR, { recursive: true, force: true }).catch(() => {});
}

main().catch((e) => {
  console.error(e);
  process.exit(1);
});
