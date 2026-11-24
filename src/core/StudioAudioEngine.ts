import type { LightSceneMode, MoodId } from './MoodSystem';

export interface AudioReactiveFrame {
  /** 0..1 smooth blend indicating whether music is currently audible & driving visuals */
  active: number;
  /** 0..1 low-frequency kick/sub-bass energy (20–350 Hz) */
  bass: number;
  /** 0..1 mid-frequency harmonic/snare energy (350–2200 Hz) */
  mid: number;
  /** 0..1 high-frequency hi-hat/shimmer energy (2200–9000 Hz) */
  treble: number;
  /** 0..1 overall smoothed musical energy */
  energy: number;
  /** 0..1 snappy beat-onset pulse (fast attack on kick/snare flux, smooth exponential decay) */
  beat: number;
  /** 0..1 auto-leveled smooth musical pulse/breath for Ice Cyan (follows music groove, never strobes) */
  breath: number;
  /** Continuous rhythm-driven phase accumulator (advances smoothly + surges on every beat!) */
  beatPhase: number;
  /** Live 32-band normalized spectrum (0..1) for optional screen visualizer */
  spectrum: Float32Array;
}

export interface MoodTrackSpec {
  id: MoodId;
  url: string;
  label: string;
  bpm: number;
  /** Exact spectral-matched loop body duration in seconds (tail after this crossfades seamlessly into head!) */
  loopDuration: number;
}

export const MOOD_TRACKS: Record<MoodId, MoodTrackSpec> = {
  midnight: {
    id: 'midnight',
    url: '/assets/audio/midnight.mp3?v=3',
    label: '深夜 Lo-Fi',
    bpm: 83.3,
    loopDuration: 68.6,
  },
  daylight: {
    id: 'daylight',
    url: '/assets/audio/daylight.mp3?v=3',
    label: '清晨晨光',
    bpm: 83.3,
    loopDuration: 80.05,
  },
  noon: {
    id: 'noon',
    url: '/assets/audio/noon.mp3?v=3',
    label: '正午律动',
    bpm: 83.3,
    loopDuration: 69.45,
  },
  golden: {
    id: 'golden',
    url: '/assets/audio/golden.mp3?v=3',
    label: '黄昏电钢',
    bpm: 83.3,
    loopDuration: 45.55,
  },
};

const LIGHT_SCENE_CUTOFF: Record<LightSceneMode, number> = {
  bright: 18000,
  cozy: 8600,
  cinema: 4800,
};

const ALL_MOODS: MoodId[] = ['midnight', 'daylight', 'noon', 'golden'];

/** Skip MP3 encoder leading delay (~26–40ms) for 100% gapless playback */
const MP3_HEAD_OFFSET = 0.05;
/** Equal-power overlap window (seconds) at each self-loop boundary */
const LOOP_XFADE_SEC = 3.0;

interface ActiveVoice {
  source: AudioBufferSourceNode;
  gain: GainNode;
  /** AudioContext.currentTime when this voice started playing from MP3_HEAD_OFFSET */
  startedAt: number;
  /** Whether we already scheduled the next seamless loop voice */
  nextScheduled: boolean;
}

interface TrackChannel {
  mood: MoodId;
  rawBytes: ArrayBuffer | null;
  fetching: Promise<ArrayBuffer | null> | null;
  buffer: AudioBuffer | null;
  loading: Promise<AudioBuffer | null> | null;
  /** Channel master gain for mood-to-mood fade-out/fade-in */
  gain: GainNode | null;
  /** Active overlapping voices for 100% gapless self-looping */
  voices: ActiveVoice[];
  /** 0..1 logical mix weight (converted via smoothstep curve to GainNode) */
  weight: number;
}

export type AudioStateListener = (state: {
  enabled: boolean;
  unlocked: boolean;
  mood: MoodId;
  trackLabel: string;
  volume: number;
}) => void;

/** Precomputed 64-point equal-power fade curves for sample-accurate loop crossfades */
function buildEqualPowerCurves(steps = 64): { fadeIn: Float32Array; fadeOut: Float32Array } {
  const fadeIn = new Float32Array(steps);
  const fadeOut = new Float32Array(steps);
  for (let i = 0; i < steps; i++) {
    const t = i / (steps - 1);
    fadeIn[i] = Math.sin(t * Math.PI * 0.5);
    fadeOut[i] = Math.cos(t * Math.PI * 0.5);
  }
  return { fadeIn, fadeOut };
}

const LOOP_CURVES = buildEqualPowerCurves(64);

/**
 * Web Audio API Studio Soundtrack & Real-Time Rhythm Engine:
 * - True dual-voice equal-power self-looping on spectral-matched loop boundaries (zero MP3 gap, zero chord jump!)
 * - Equal-power crossfade (sin/cos energy preservation) across all 4 time-of-day moods
 * - Subtle cinematic low-pass filter sweep synced to transitions & indoor LightSceneMode (Bright / Cozy / Cinema)
 * - In-series pre-volume AnalyserNode + auto-leveled musical pulse & beat detector driving Studio ARGB marquees & PointLights
 */
export class StudioAudioEngine {
  private ctx: AudioContext | null = null;
  private masterGain: GainNode | null = null;
  private masterFilter: BiquadFilterNode | null = null;
  private analyser: AnalyserNode | null = null;
  private freqBytes: Uint8Array<ArrayBuffer> = new Uint8Array(256);

  private readonly channels = new Map<MoodId, TrackChannel>();
  private activeMood: MoodId = 'midnight';
  private lightScene: LightSceneMode = 'bright';
  private autoAdvance = true; // Auto-cycle songs when time-of-day loop is enabled

  private enabled = true; // Armed by default; auto-plays when allowed or smoothly fades in on first gesture
  private unlocked = false;
  private unlockedAt = 0;
  private masterVolume = 0.62;
  private transitionDip = 0; // 0..1 subtle filter dip during track transitions
  private readonly fadeOutSeconds = 0.9;
  private readonly fadeInSeconds = 1.0;

  // Real-time beat & auto-leveled musical pulse detector state
  private bassAvg = 0.15;
  private bassFloor = 0.08;
  private bassCeil = 0.32;
  private prevBass = 0;
  private beatCooldown = 0;
  private beatEnv = 0;
  private breathEnv = 0;
  private smoothBass = 0;
  private smoothMid = 0;
  private smoothTreble = 0;
  private smoothEnergy = 0;
  private smoothActive = 0;
  private beatPhase = 0;

  public readonly reactive: AudioReactiveFrame = {
    active: 0,
    bass: 0,
    mid: 0,
    treble: 0,
    energy: 0,
    beat: 0,
    breath: 0,
    beatPhase: 0,
    spectrum: new Float32Array(32),
  };

  private readonly onStateChange?: AudioStateListener;
  private disposed = false;

  constructor(initialMood: MoodId = 'midnight', onStateChange?: AudioStateListener) {
    this.activeMood = initialMood;
    this.onStateChange = onStateChange;

    for (const mood of ALL_MOODS) {
      this.channels.set(mood, {
        mood,
        rawBytes: null,
        fetching: null,
        buffer: null,
        loading: null,
        gain: null,
        voices: [],
        weight: mood === initialMood ? 1 : 0,
      });
    }

    // Unlock Web Audio seamlessly on the user's very first interaction anywhere in the studio.
    // iOS Safari requires `touchend` or `click` (not just `pointerdown`) to unlock AudioContext!
    window.addEventListener('pointerdown', this.handleFirstGesture, { passive: true, capture: true });
    window.addEventListener('touchend', this.handleFirstGesture, { passive: true, capture: true });
    window.addEventListener('click', this.handleFirstGesture, { passive: true, capture: true });
    window.addEventListener('keydown', this.handleFirstGesture, { passive: true, capture: true });
  }

  private removeGestureListeners(): void {
    window.removeEventListener('pointerdown', this.handleFirstGesture, true);
    window.removeEventListener('touchend', this.handleFirstGesture, true);
    window.removeEventListener('click', this.handleFirstGesture, true);
    window.removeEventListener('keydown', this.handleFirstGesture, true);
  }

  private readonly handleFirstGesture = (): void => {
    if (this.disposed) return;
    if (!this.enabled) return;
    // Call resume() synchronously inside the user gesture tick for iOS Safari WebKit compliance
    const ctx = this.initGraph();
    if (ctx && ctx.state === 'suspended') {
      void ctx.resume().catch(() => {});
    }
    void this.ensureUnlockedAndPlaying();
  };

  private initGraph(): AudioContext | null {
    if (this.ctx) return this.ctx;
    const AudioCtx =
      window.AudioContext ||
      (window as unknown as { webkitAudioContext?: typeof AudioContext }).webkitAudioContext;
    if (!AudioCtx) return null;

    // iOS 17+ Safari: switch audio session to 'playback' so music plays even when the physical mute switch is ON
    const navWithAudioSession = navigator as Navigator & { audioSession?: { type: string } };
    if (navWithAudioSession.audioSession) {
      try {
        navWithAudioSession.audioSession.type = 'playback';
      } catch {
        // ignore if unsupported
      }
    }

    const ctx = new AudioCtx();
    const filter = ctx.createBiquadFilter();
    filter.type = 'lowpass';
    filter.frequency.value = LIGHT_SCENE_CUTOFF[this.lightScene];
    filter.Q.value = 0.7;

    const analyser = ctx.createAnalyser();
    analyser.fftSize = 512;
    analyser.smoothingTimeConstant = 0.45;

    const masterGain = ctx.createGain();
    masterGain.gain.value = 0.0001; // Fade in cleanly once unlocked

    // Wire IN SERIES before masterGain:
    // Guaranteed to be actively pulled by the audio thread on every browser AND stays full-scale regardless of volume!
    filter.connect(analyser);
    analyser.connect(masterGain);
    masterGain.connect(ctx.destination);

    this.ctx = ctx;
    this.masterFilter = filter;
    this.analyser = analyser;
    this.masterGain = masterGain;
    this.freqBytes = new Uint8Array(new ArrayBuffer(analyser.frequencyBinCount));

    // Create per-mood GainNodes
    for (const ch of this.channels.values()) {
      const g = ctx.createGain();
      g.gain.value = ch.mood === this.activeMood ? 1.0 : 0.0;
      g.connect(filter);
      ch.gain = g;
    }

    return ctx;
  }

  private async ensureUnlockedAndPlaying(): Promise<void> {
    const ctx = this.initGraph();
    if (!ctx) return;

    if (ctx.state === 'suspended') {
      try {
        await ctx.resume();
      } catch {
        return;
      }
    }

    if (ctx.state !== 'running') return;

    if (!this.unlocked) {
      this.unlocked = true;
      this.unlockedAt = performance.now();
      this.removeGestureListeners();
      this.emitState();
    }

    // Load & start the active mood immediately (near-instant when prefetched!), then warm-decode remaining tracks sequentially
    await this.ensureTrackPlaying(this.activeMood);
    this.syncMasterGain(0.45);
    void this.preloadRemainingMoods();
  }

  /**
   * Attempts immediate autoplay when the scene reveals (succeeds automatically in browsers
   * with sufficient Media Engagement or autoplay permission; silently stays armed otherwise).
   */
  public tryAutoPlay(): void {
    if (this.disposed || !this.enabled || this.unlocked) return;
    const ctx = this.initGraph();
    if (!ctx) return;
    if (ctx.state === 'running') {
      void this.ensureUnlockedAndPlaying();
    } else if (ctx.state === 'suspended') {
      ctx
        .resume()
        .then(() => {
          if (!this.disposed && this.enabled && ctx.state === 'running') {
            void this.ensureUnlockedAndPlaying();
          }
        })
        .catch(() => {
          // Blocked by browser autoplay policy; handleFirstGesture stays armed
        });
    }
  }

  /**
   * Prefetches MP3 bytes into memory before the user's first gesture (zero Web Audio warnings, zero network wait on click).
   * Fetches the active track first, then sequentially prefetches the remaining 3 tracks in the background.
   */
  public prefetch(): void {
    if (this.disposed) return;
    const activeCh = this.channels.get(this.activeMood);
    if (!activeCh) return;
    void this.fetchRawBytes(activeCh).then(async () => {
      for (const mood of ALL_MOODS) {
        if (this.disposed) return;
        if (mood === this.activeMood) continue;
        const ch = this.channels.get(mood);
        if (ch && !ch.buffer && !ch.rawBytes && !ch.fetching) {
          await this.fetchRawBytes(ch);
        }
      }
    });
  }

  private fetchRawBytes(ch: TrackChannel): Promise<ArrayBuffer | null> {
    if (ch.rawBytes) return Promise.resolve(ch.rawBytes);
    if (ch.fetching) return ch.fetching;

    const url = MOOD_TRACKS[ch.mood].url;
    ch.fetching = fetch(url)
      .then((res) => {
        if (!res.ok) throw new Error(`HTTP ${res.status} loading ${url}`);
        return res.arrayBuffer();
      })
      .then((arr) => {
        if (!this.disposed) {
          ch.rawBytes = arr;
        }
        return arr;
      })
      .catch((err) => {
        console.warn(`[StudioAudio] Failed to fetch track ${ch.mood}:`, err);
        ch.fetching = null;
        return null;
      });

    return ch.fetching;
  }

  private async loadBuffer(ch: TrackChannel): Promise<AudioBuffer | null> {
    if (ch.buffer) return ch.buffer;
    if (ch.loading) return ch.loading;
    const ctx = this.initGraph();
    if (!ctx) return null;

    ch.loading = this.fetchRawBytes(ch)
      .then((arr) => {
        if (!arr || arr.byteLength === 0 || this.disposed) return null;
        // Slice a fresh copy so decodeAudioData never encounters a detached ArrayBuffer
        const copy = arr.slice(0);
        ch.rawBytes = null;
        ch.fetching = null;
        return ctx.decodeAudioData(copy);
      })
      .then((buf) => {
        if (buf) ch.buffer = buf;
        return buf;
      })
      .catch((err) => {
        console.warn(`[StudioAudio] Failed to decode track ${ch.mood}:`, err);
        ch.loading = null;
        ch.fetching = null;
        ch.rawBytes = null;
        return null;
      });

    return ch.loading;
  }

  private spawnVoice(ch: TrackChannel, startAtTime: number, fadeInSec: number): ActiveVoice | null {
    if (!this.ctx || !ch.buffer || !ch.gain || this.disposed) return null;

    const src = this.ctx.createBufferSource();
    src.buffer = ch.buffer;
    src.loop = false;

    const voiceGain = this.ctx.createGain();
    if (fadeInSec > 0.01) {
      voiceGain.gain.setValueAtTime(0.0001, startAtTime);
      voiceGain.gain.setValueCurveAtTime(LOOP_CURVES.fadeIn, startAtTime, fadeInSec);
    } else {
      voiceGain.gain.setValueAtTime(1.0, startAtTime);
    }

    src.connect(voiceGain);
    voiceGain.connect(ch.gain);

    // Play starting cleanly after MP3 encoder padding
    const safeOffset = Math.min(MP3_HEAD_OFFSET, Math.max(0, ch.buffer.duration - 1));
    src.start(startAtTime, safeOffset);

    const voice: ActiveVoice = {
      source: src,
      gain: voiceGain,
      startedAt: startAtTime,
      nextScheduled: false,
    };

    src.onended = () => {
      try {
        src.disconnect();
        voiceGain.disconnect();
      } catch {
        // ignore
      }
      const idx = ch.voices.indexOf(voice);
      if (idx >= 0) ch.voices.splice(idx, 1);
    };

    ch.voices.push(voice);
    return voice;
  }

  private async ensureTrackPlaying(mood: MoodId): Promise<void> {
    const ch = this.channels.get(mood);
    if (!ch || !this.ctx || !ch.gain) return;
    const buf = await this.loadBuffer(ch);
    if (!buf || this.disposed || ch.voices.length > 0) return;

    this.spawnVoice(ch, this.ctx.currentTime, 0);
  }

  private stopChannelVoices(ch: TrackChannel): void {
    if (ch.voices.length === 0) return;
    for (const v of ch.voices) {
      try {
        v.source.onended = null;
        v.source.stop();
        v.source.disconnect();
        v.gain.disconnect();
      } catch {
        // ignore
      }
    }
    ch.voices = [];
  }

  /**
   * Maintains active track playback boundaries:
   * - When autoAdvance is enabled (time-of-day loop mode), smoothly advances to the next track at song end.
   * - Otherwise schedules sample-accurate equal-power 3.0s self-loops on spectral-matched boundaries.
   */
  private maintainSeamlessLoops(): void {
    if (!this.ctx || this.ctx.state !== 'running') return;
    const now = this.ctx.currentTime;

    for (const ch of this.channels.values()) {
      if (!ch.buffer || ch.voices.length === 0) continue;
      if (ch.mood !== this.activeMood) continue;

      const spec = MOOD_TRACKS[ch.mood];
      const maxPlayable = Math.max(4, ch.buffer.duration - MP3_HEAD_OFFSET - LOOP_XFADE_SEC);
      const loopDur = Math.min(spec.loopDuration, maxPlayable);

      for (const voice of ch.voices) {
        if (voice.nextScheduled) continue;
        const wrapAt = voice.startedAt + loopDur;

        if (this.autoAdvance && this.enabled && this.unlocked) {
          if (now >= wrapAt - this.fadeOutSeconds) {
            voice.nextScheduled = true;
            const nextIdx = (ALL_MOODS.indexOf(this.activeMood) + 1) % ALL_MOODS.length;
            this.setMood(ALL_MOODS[nextIdx]);
            return;
          }
          continue;
        }

        // Schedule the next seamless self-loop voice 0.35s ahead of the wrap point for sample-accurate timing
        if (now >= wrapAt - 0.35) {
          voice.nextScheduled = true;
          const xfadeStart = Math.max(now + 0.02, wrapAt);
          const xfadeDur = Math.min(
            LOOP_XFADE_SEC,
            Math.max(0.5, ch.buffer.duration - MP3_HEAD_OFFSET - loopDur)
          );

          // Fade out the matched tail of the outgoing voice
          voice.gain.gain.cancelScheduledValues(xfadeStart);
          voice.gain.gain.setValueAtTime(1.0, xfadeStart);
          voice.gain.gain.setValueCurveAtTime(LOOP_CURVES.fadeOut, xfadeStart, xfadeDur);
          try {
            voice.source.stop(xfadeStart + xfadeDur + 0.05);
          } catch {
            // ignore
          }

          // Spawn & equal-power fade in the matched head of the next cycle
          this.spawnVoice(ch, xfadeStart, xfadeDur);
        }
      }
    }
  }

  private async preloadRemainingMoods(): Promise<void> {
    for (const mood of ALL_MOODS) {
      if (this.disposed) return;
      if (mood === this.activeMood) continue;
      const ch = this.channels.get(mood);
      if (ch && !ch.buffer && !ch.loading) {
        await this.loadBuffer(ch);
      }
    }
  }

  private syncMasterGain(rampSec = 0.35): void {
    if (!this.ctx || !this.masterGain) return;
    const now = this.ctx.currentTime;
    const target = this.enabled && this.unlocked ? this.masterVolume : 0.0001;
    this.masterGain.gain.cancelScheduledValues(now);
    this.masterGain.gain.setTargetAtTime(target, now, Math.max(0.04, rampSec * 0.33));
  }

  public setAutoAdvance(enabled: boolean): void {
    this.autoAdvance = enabled;
  }

  public setMood(mood: MoodId): void {
    if (this.activeMood === mood) return;
    this.activeMood = mood;
    this.transitionDip = 1.0; // Trigger subtle cinematic filter sweep during fade-out/fade-in

    if (!this.unlocked) {
      for (const ch of this.channels.values()) {
        ch.weight = ch.mood === mood ? 1 : 0;
        if (ch.gain && this.ctx) {
          ch.gain.gain.setValueAtTime(ch.weight, this.ctx.currentTime);
        }
      }
    } else if (this.enabled) {
      const targetCh = this.channels.get(mood);
      if (targetCh && !targetCh.buffer && !targetCh.loading) {
        void this.loadBuffer(targetCh);
      }
    }
    this.emitState();
  }

  public setLightScene(mode: LightSceneMode): void {
    this.lightScene = mode;
  }

  public toggleEnabled(): boolean {
    // If audio is still locked or was JUST unlocked by this very click's pointerdown,
    // treat the click as "turn ON / play" instead of immediately muting it!
    if (!this.unlocked || (this.enabled && performance.now() - this.unlockedAt < 450)) {
      this.enabled = true;
      void this.ensureUnlockedAndPlaying();
      this.emitState();
      return this.enabled;
    }
    this.enabled = !this.enabled;
    if (this.enabled) {
      void this.ensureUnlockedAndPlaying();
    } else {
      this.syncMasterGain(0.35);
    }
    this.emitState();
    return this.enabled;
  }

  public setVolume(v: number): void {
    this.masterVolume = Math.max(0, Math.min(1, v));
    this.syncMasterGain(0.15);
    this.emitState();
  }

  public isPlaying(): boolean {
    return this.enabled && this.unlocked;
  }

  public getState() {
    return {
      enabled: this.enabled,
      unlocked: this.unlocked,
      mood: this.activeMood,
      trackLabel: MOOD_TRACKS[this.activeMood].label,
      volume: this.masterVolume,
    };
  }

  private emitState(): void {
    this.onStateChange?.(this.getState());
  }

  /**
   * Called every animation frame from GeekLoftApp.loop:
   * 1. Maintains sample-accurate overlapping seamless self-loops on all active tracks
   * 2. Smoothly updates equal-power crossfade weights across all 4 mood channels
   * 3. Smoothly sweeps master lowpass filter for LightSceneMode & transition warmth
   * 4. Runs real-time FFT + auto-leveled musical pulse & beat detection for Studio neon marquees & PointLights
   */
  public update(delta: number): AudioReactiveFrame {
    const dt = Math.min(Math.max(delta, 0.001), 0.05);

    this.maintainSeamlessLoops();

    // 1. Sequential fade-out -> fade-in across mood channels (clean 渐弱 -> 渐强 transition!)
    const fadeOutStep = dt / this.fadeOutSeconds;
    const fadeInStep = dt / this.fadeInSeconds;
    const now = this.ctx ? this.ctx.currentTime : 0;

    let maxOtherWeight = 0;
    for (const ch of this.channels.values()) {
      if (ch.mood === this.activeMood) continue;
      if (ch.weight > 0) {
        ch.weight = Math.max(0, ch.weight - fadeOutStep);
      }
      if (ch.weight > maxOtherWeight) {
        maxOtherWeight = ch.weight;
      }
      if (ch.weight === 0 && ch.voices.length > 0) {
        this.stopChannelVoices(ch);
      }
      if (ch.gain && this.ctx) {
        const smoothGain = ch.weight * ch.weight * (3 - 2 * ch.weight);
        ch.gain.gain.setTargetAtTime(smoothGain, now, 0.025);
      }
    }

    const activeCh = this.channels.get(this.activeMood);
    if (activeCh) {
      if (maxOtherWeight <= 0.05) {
        if (this.unlocked && this.enabled && activeCh.voices.length === 0) {
          if (activeCh.buffer) {
            this.spawnVoice(activeCh, now, 0);
          } else if (!activeCh.loading) {
            void this.loadBuffer(activeCh);
          }
        }
        if (activeCh.voices.length > 0 || !this.unlocked) {
          activeCh.weight = Math.min(1, activeCh.weight + fadeInStep);
        }
      }
      if (activeCh.gain && this.ctx) {
        const smoothGain = activeCh.weight * activeCh.weight * (3 - 2 * activeCh.weight);
        activeCh.gain.gain.setTargetAtTime(smoothGain, now, 0.025);
      }
    }

    // 2. Smooth master filter cutoff (indoor light scene tone + gentle dip during crossfade)
    this.transitionDip = Math.max(0, this.transitionDip - dt * 0.85);
    if (this.masterFilter && this.ctx) {
      const baseCutoff = LIGHT_SCENE_CUTOFF[this.lightScene];
      const dipCurve = Math.sin(this.transitionDip * Math.PI);
      const targetFreq = Math.max(1800, baseCutoff * (1 - dipCurve * 0.36));
      this.masterFilter.frequency.setTargetAtTime(targetFreq, now, 0.12);
    }

    // 3. Real-time FFT + Auto-Leveled Musical Pulse & Beat Detector
    const audible = this.enabled && this.unlocked && this.analyser !== null && this.ctx?.state === 'running';
    this.smoothActive += ((audible ? 1 : 0) - this.smoothActive) * (1 - Math.exp(-dt * 4.5));

    if (audible && this.analyser) {
      this.analyser.getByteFrequencyData(this.freqBytes);

      // Frequency bands (fftSize=512 -> 256 bins, ~86-93 Hz/bin)
      let bassSum = 0;
      for (let i = 0; i <= 4; i++) bassSum += this.freqBytes[i];
      const rawBass = bassSum / (5 * 255);

      let midSum = 0;
      for (let i = 5; i <= 22; i++) midSum += this.freqBytes[i];
      const rawMid = midSum / (18 * 255);

      let trebleSum = 0;
      for (let i = 23; i <= 90; i++) trebleSum += this.freqBytes[i];
      const rawTreble = trebleSum / (68 * 255);

      const rawEnergy = rawBass * 0.48 + rawMid * 0.36 + rawTreble * 0.16;

      const normBass = Math.min(1, Math.pow(rawBass * 1.45, 1.08));
      const normMid = Math.min(1, Math.pow(rawMid * 1.55, 1.08));
      const normTreble = Math.min(1, Math.pow(rawTreble * 1.85, 1.05));
      const normEnergy = Math.min(1, rawEnergy * 1.5);

      // Adaptive low-end onset beat detector
      this.bassAvg += (normBass - this.bassAvg) * (1 - Math.exp(-dt * 1.8));
      const bassFlux = Math.max(0, normBass - this.prevBass);
      this.prevBass = normBass;

      const overAvg = normBass - this.bassAvg * 1.04;
      this.beatCooldown = Math.max(0, this.beatCooldown - dt);
      const beatStrength =
        overAvg > 0.014 && bassFlux > 0.005
          ? Math.min(1, overAvg * 4.5 + bassFlux * 3.8)
          : 0;

      if (beatStrength > 0.14 && this.beatCooldown <= 0) {
        this.beatEnv = Math.max(this.beatEnv, Math.min(1, 0.55 + beatStrength * 0.45));
        this.beatCooldown = 0.20;
      } else {
        this.beatEnv *= Math.exp(-dt * 6.0);
      }

      // Rolling auto-gain envelope on (bass + mid) so Ice Cyan ALWAYS pulses visibly with the music groove
      // on every track (soft morning piano OR punchy midnight Lo-Fi), with tasteful damping (never strobes!)
      const grooveSignal = normBass * 0.72 + normMid * 0.28;
      // Floor tracks quiet troughs; ceiling tracks peaks, both relaxing slowly toward grooveSignal
      if (grooveSignal < this.bassFloor) {
        this.bassFloor += (grooveSignal - this.bassFloor) * (1 - Math.exp(-dt * 4.0));
      } else {
        this.bassFloor += (grooveSignal - this.bassFloor) * (1 - Math.exp(-dt * 0.45));
      }
      if (grooveSignal > this.bassCeil) {
        this.bassCeil += (grooveSignal - this.bassCeil) * (1 - Math.exp(-dt * 6.0));
      } else {
        this.bassCeil += (grooveSignal - this.bassCeil) * (1 - Math.exp(-dt * 0.55));
      }
      const span = Math.max(0.08, this.bassCeil - this.bassFloor);
      const relGroove = Math.max(0, Math.min(1, (grooveSignal - this.bassFloor) / span));
      const pulseTarget = Math.min(1, relGroove * 0.75 + this.beatEnv * 0.45);
      // Responsive upward pulse (rate 11), smooth controlled settle (rate 4.2) -> musical bounce without harsh strobing
      const pulseRate = pulseTarget > this.breathEnv ? 11.0 : 4.2;
      this.breathEnv += (pulseTarget - this.breathEnv) * (1 - Math.exp(-dt * pulseRate));

      // Fast attack, smooth release for visual bands
      const atk = 1 - Math.exp(-dt * 18.0);
      const rel = 1 - Math.exp(-dt * 7.5);
      this.smoothBass += (normBass - this.smoothBass) * (normBass > this.smoothBass ? atk : rel);
      this.smoothMid += (normMid - this.smoothMid) * (normMid > this.smoothMid ? atk : rel);
      this.smoothTreble += (normTreble - this.smoothTreble) * (normTreble > this.smoothTreble ? atk : rel);
      this.smoothEnergy += (normEnergy - this.smoothEnergy) * (1 - Math.exp(-dt * 8.0));

      // Fill 32-band spectrum for ultrawide screen visualizer
      const spec = this.reactive.spectrum;
      for (let b = 0; b < 32; b++) {
        const idx0 = Math.floor(Math.pow(b / 32, 1.45) * 108);
        const idx1 = Math.max(idx0 + 1, Math.floor(Math.pow((b + 1) / 32, 1.45) * 108));
        let peak = 0;
        for (let k = idx0; k < idx1 && k < this.freqBytes.length; k++) {
          if (this.freqBytes[k] > peak) peak = this.freqBytes[k];
        }
        const val = peak / 255;
        spec[b] += (val - spec[b]) * (val > spec[b] ? 0.55 : 0.22);
      }
    } else {
      const decay = Math.exp(-dt * 6.0);
      this.smoothBass *= decay;
      this.smoothMid *= decay;
      this.smoothTreble *= decay;
      this.smoothEnergy *= decay;
      this.beatEnv *= decay;
      this.breathEnv *= decay;
      for (let b = 0; b < 32; b++) {
        this.reactive.spectrum[b] *= decay;
      }
    }

    const bpmRate = MOOD_TRACKS[this.activeMood].bpm / 60;
    const rhythmBoost = 1.0 + this.smoothActive * (this.smoothBass * 0.55 + this.beatEnv * 1.15);
    this.beatPhase += dt * bpmRate * rhythmBoost;

    this.reactive.active = this.smoothActive;
    this.reactive.bass = this.smoothBass;
    this.reactive.mid = this.smoothMid;
    this.reactive.treble = this.smoothTreble;
    this.reactive.energy = this.smoothEnergy;
    this.reactive.beat = this.beatEnv;
    this.reactive.breath = this.breathEnv;
    this.reactive.beatPhase = this.beatPhase;

    return this.reactive;
  }

  public dispose(): void {
    this.disposed = true;
    this.removeGestureListeners();
    for (const ch of this.channels.values()) {
      for (const v of ch.voices) {
        try {
          v.source.stop();
          v.source.disconnect();
          v.gain.disconnect();
        } catch {
          // ignore
        }
      }
      ch.voices = [];
      try {
        ch.gain?.disconnect();
      } catch {
        // ignore
      }
      ch.gain = null;
    }
    this.masterFilter?.disconnect();
    this.masterGain?.disconnect();
    this.analyser?.disconnect();
    if (this.ctx) {
      void this.ctx.close();
      this.ctx = null;
    }
  }
}
