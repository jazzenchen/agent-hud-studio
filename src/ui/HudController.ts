import type { LightSceneMode, MoodId } from '../core/MoodSystem';
import type { PerfSnapshot, QualityTier } from '../core/PerformanceGovernor';
import type { CameraPresetId } from '../interaction/DualCameraController';
import {
  detectInitialLocale,
  saveLocale,
  TRANSLATIONS,
  type Locale,
  type TranslationBundle,
} from './i18n';

export interface HudCallbacks {
  onSelectCamera: (id: CameraPresetId) => void;
  onToggleCamPan: () => void;
  onSelectMood: (id: MoodId) => void;
  onToggleMoodCycle: () => void;
  onToggleWalk: () => void;
  onCycleScreen: () => void;
  onCycleLightScene: () => void;
  onCycleRgb: () => void;
  onToggleMusic: () => void;
  onSelectQuality: (tier: QualityTier) => void;
  onTogglePhotoMode: () => void;
  onTogglePureClay: () => void;
  onToggleLightingOnly: () => void;
  onToggleWireframe: () => void;
}

const CAM_KEYS: Partial<Record<CameraPresetId, string>> = {
  hero: '1',
  living: '2',
  kitchen: '3',
  bedroom: '4',
  bathroom: '5',
  desk: '6',
  window: '7',
};

export class HudController {
  private readonly canvasEl = document.getElementById('webgl-canvas')!;
  private readonly loadingOverlay = document.getElementById('loading-overlay')!;
  private readonly loadingBar = document.getElementById('loading-bar-fill')!;
  private readonly loadingStatus = document.getElementById('loading-status')!;
  private readonly loadingBytes = document.getElementById('loading-bytes');
  private readonly perfPill = document.getElementById('perf-pill')!;
  private readonly perfFps = document.getElementById('perf-fps')!;
  private readonly perfDetail = document.getElementById('perf-detail')!;
  private readonly viewGroup = document.getElementById('view-group')!;
  private readonly qualityGroup = document.getElementById('quality-group')!;
  private readonly langBtn = document.getElementById('lang-toggle')!;
  private readonly modeBtn = document.getElementById('mode-toggle')!;
  private readonly screenBtn = document.getElementById('screen-cycle')!;
  private readonly lightBtn = document.getElementById('light-scene-cycle')!;
  private readonly rgbBtn = document.getElementById('rgb-cycle')!;
  private readonly musicBtn = document.getElementById('music-toggle')!;
  private readonly musicLabel = document.getElementById('music-label')!;
  private readonly fpHud = document.getElementById('fp-hud')!;
  private readonly fpBanner = document.getElementById('fp-banner')!;
  private readonly hudDock = document.getElementById('hud-dock')!;
  private readonly camGroup = document.getElementById('cam-group')!;
  private readonly camPanBtn = document.getElementById('cam-pan-toggle')!;
  private readonly camPanLabel = document.getElementById('cam-pan-label')!;
  private readonly moodGroup = document.getElementById('mood-group')!;
  private readonly moodCycleBtn = document.getElementById('mood-cycle-toggle')!;
  private readonly moodCycleLabel = document.getElementById('mood-cycle-label')!;
  private readonly interactLabel = document.getElementById('interact-label')!;
  private readonly helpModal = document.getElementById('help-modal')!;
  private readonly helpTitle = document.getElementById('help-title')!;
  private readonly helpList = document.getElementById('help-list')!;
  private readonly helpToggle = document.getElementById('help-toggle')!;
  private readonly helpClose = document.getElementById('help-close')!;
  private readonly helpGotIt = document.getElementById('help-got-it');
  private readonly gestureTip = document.getElementById('gesture-tip');
  private readonly photoBtn = document.getElementById('view-photo')!;
  private readonly clayBtn = document.getElementById('view-clay')!;
  private readonly lightingBtn = document.getElementById('view-lighting')!;
  private readonly wireBtn = document.getElementById('view-wire')!;
  private readonly photoExitBtn = document.getElementById('photo-exit')!;
  private readonly modeToast = document.getElementById('mode-toast')!;
  private toastTimer = 0;

  private readonly camButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-cam]'));
  private readonly moodButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-mood]'));
  private readonly qualityButtons = Array.from(document.querySelectorAll<HTMLButtonElement>('[data-quality]'));

  private locale: Locale = detectInitialLocale();
  private activeMood: MoodId = 'midnight';
  private camPanActive = true;
  private moodCycleActive = true;
  private walkActive = false;
  private lightSceneMode: LightSceneMode = 'bright';
  private rgbModeIndex = 0;
  private musicEnabled = true;
  private musicPlaying = false;
  private musicMood: MoodId = 'midnight';

  constructor(callbacks: HudCallbacks) {
    this.perfPill.addEventListener('click', () => {
      this.perfPill.classList.toggle('is-compact');
    });

    this.camButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const id = btn.dataset.cam as CameraPresetId;
        callbacks.onSelectCamera(id);
      });
    });

    this.camPanBtn.addEventListener('click', () => callbacks.onToggleCamPan());

    const selectMood = (id: MoodId) => {
      this.setActiveMood(id);
      callbacks.onSelectMood(id);
    };

    this.moodButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        selectMood(btn.dataset.mood as MoodId);
      });
    });

    this.moodCycleBtn.addEventListener('click', () => callbacks.onToggleMoodCycle());

    this.qualityButtons.forEach((btn) => {
      btn.addEventListener('click', () => {
        const tier = btn.dataset.quality as QualityTier;
        this.qualityButtons.forEach((b) => b.classList.toggle('is-active', b === btn));
        callbacks.onSelectQuality(tier);
      });
    });

    this.modeBtn.addEventListener('click', () => callbacks.onToggleWalk());
    this.screenBtn.addEventListener('click', () => callbacks.onCycleScreen());
    this.lightBtn.addEventListener('click', () => callbacks.onCycleLightScene());
    this.rgbBtn.addEventListener('click', () => callbacks.onCycleRgb());
    this.musicBtn.addEventListener('click', () => callbacks.onToggleMusic());
    this.langBtn.addEventListener('click', () => this.toggleLocale());
    this.photoBtn.addEventListener('click', () => callbacks.onTogglePhotoMode());
    this.photoExitBtn.addEventListener('click', () => callbacks.onTogglePhotoMode());
    this.clayBtn.addEventListener('click', () => callbacks.onTogglePureClay());
    this.lightingBtn.addEventListener('click', () => callbacks.onToggleLightingOnly());
    this.wireBtn.addEventListener('click', () => callbacks.onToggleWireframe());

    this.helpToggle.addEventListener('click', () => {
      this.helpModal.hidden = !this.helpModal.hidden;
    });
    this.helpClose.addEventListener('click', () => {
      this.helpModal.hidden = true;
    });
    this.helpGotIt?.addEventListener('click', () => {
      this.helpModal.hidden = true;
    });
    this.helpModal.addEventListener('click', (e) => {
      if (e.target === this.helpModal) this.helpModal.hidden = true;
    });

    // Global keyboard shortcuts covering bottom-dock actions (zero conflict with WASD walk mode!):
    // 1-7: camera presets | M: 24h mood cycle | V: walk | K: light scene | T: screen | R: RGB | B: mute
    // P: photo | C: pure clay | L: lighting clay | G: wireframe | H: help
    const moodOrder: MoodId[] = ['midnight', 'daylight', 'noon', 'golden'];
    window.addEventListener('keydown', (e) => {
      if (e.metaKey || e.ctrlKey || e.altKey) return;
      if (e.code === 'KeyH') {
        this.helpModal.hidden = !this.helpModal.hidden;
      } else if (e.code === 'KeyV') {
        callbacks.onToggleWalk();
      } else if (e.code === 'KeyP') {
        callbacks.onTogglePhotoMode();
      } else if (e.code === 'Escape' && document.body.classList.contains('is-photo-mode')) {
        callbacks.onTogglePhotoMode();
      } else if (e.code === 'KeyC') {
        callbacks.onTogglePureClay();
      } else if (e.code === 'KeyL') {
        callbacks.onToggleLightingOnly();
      } else if (e.code === 'KeyG') {
        callbacks.onToggleWireframe();
      } else if (e.code === 'KeyR') {
        callbacks.onCycleRgb();
      } else if (e.code === 'KeyB') {
        callbacks.onToggleMusic();
      } else if (e.code === 'KeyK') {
        callbacks.onCycleLightScene();
      } else if (e.code === 'KeyT') {
        callbacks.onCycleScreen();
      } else if (e.code === 'KeyM') {
        const next = moodOrder[(moodOrder.indexOf(this.activeMood) + 1) % moodOrder.length];
        selectMood(next);
      } else if (e.code === 'Digit1') {
        callbacks.onSelectCamera('hero');
      } else if (e.code === 'Digit2') {
        callbacks.onSelectCamera('living');
      } else if (e.code === 'Digit3') {
        callbacks.onSelectCamera('kitchen');
      } else if (e.code === 'Digit4') {
        callbacks.onSelectCamera('bedroom');
      } else if (e.code === 'Digit5') {
        callbacks.onSelectCamera('bathroom');
      } else if (e.code === 'Digit6') {
        callbacks.onSelectCamera('desk');
      } else if (e.code === 'Digit7') {
        callbacks.onSelectCamera('window');
      }
    });

    this.applyLocale(false);
  }

  public getLocale(): Locale {
    return this.locale;
  }

  public getMessages(): TranslationBundle {
    return TRANSLATIONS[this.locale];
  }

  public setLocale(locale: Locale, notify = false): void {
    if (this.locale === locale) return;
    this.locale = locale;
    saveLocale(locale);
    this.applyLocale(notify);
  }

  public toggleLocale(): Locale {
    const next: Locale = this.locale === 'zh' ? 'en' : 'zh';
    this.setLocale(next, true);
    return next;
  }

  private applyLocale(notify: boolean): void {
    const t = TRANSLATIONS[this.locale];

    document.documentElement.lang = t.htmlLang;
    document.title = t.pageTitle;
    this.canvasEl.setAttribute('aria-label', t.canvasAriaLabel);
    this.perfPill.title = t.perfPillTitle;

    // Top-right view modes & controls
    this.viewGroup.setAttribute('aria-label', t.topRight.viewGroupAria);
    this.qualityGroup.setAttribute('aria-label', t.topRight.qualityGroupAria);

    this.photoBtn.textContent = t.topRight.photo.label;
    this.photoBtn.title = t.topRight.photo.title;
    this.clayBtn.textContent = t.topRight.clay.label;
    this.clayBtn.title = t.topRight.clay.title;
    this.lightingBtn.textContent = t.topRight.lighting.label;
    this.lightingBtn.title = t.topRight.lighting.title;
    this.wireBtn.textContent = t.topRight.wire.label;
    this.wireBtn.title = t.topRight.wire.title;

    this.langBtn.textContent = t.topRight.lang.buttonText;
    this.langBtn.setAttribute('aria-label', t.topRight.lang.ariaLabel);
    this.langBtn.title = t.topRight.lang.title;

    this.helpToggle.setAttribute('aria-label', t.topRight.help.ariaLabel);
    this.helpToggle.title = t.topRight.help.title;

    // Overlays & banners
    this.photoExitBtn.textContent = t.photoExit;
    this.fpBanner.textContent = t.fpBanner;
    this.interactLabel.textContent = t.interact.defaultLabel;

    // Bottom dock groups & buttons
    this.hudDock.setAttribute('aria-label', t.dock.navAria);
    this.camGroup.setAttribute('aria-label', t.dock.camGroupAria);
    this.moodGroup.setAttribute('aria-label', t.dock.moodGroupAria);

    this.camButtons.forEach((btn) => {
      const id = btn.dataset.cam as CameraPresetId;
      const spec = t.dock.cameras[id];
      const key = CAM_KEYS[id];
      if (!spec || !key) return;
      btn.title = spec.title;
      btn.innerHTML = `${spec.label}<kbd class="dock-kbd">${key}</kbd>`;
    });

    this.moodButtons.forEach((btn) => {
      const id = btn.dataset.mood as MoodId;
      const spec = t.dock.moods[id];
      if (!spec) return;
      btn.title = spec.title;
      btn.textContent = spec.label;
    });

    this.modeBtn.title = t.dock.walk.title;
    this.lightBtn.title = t.dock.lightScene.title;
    this.screenBtn.title = t.dock.screen.title;
    this.screenBtn.innerHTML = `${t.dock.screen.label}<kbd class="dock-kbd">T</kbd>`;

    // Help modal
    const isMobileViewport =
      window.matchMedia('(max-width: 768px)').matches || window.matchMedia('(pointer: coarse)').matches;
    const isZh = this.locale === 'zh';
    this.helpTitle.textContent = isMobileViewport
      ? isZh
        ? '触控手势指南'
        : 'Touch Gestures'
      : t.helpModal.title;
    this.helpClose.setAttribute('aria-label', t.helpModal.closeAria);

    const mobileCopy = isZh
      ? {
          orbit: ['单指拖动', '360° 自由环视视角'],
          zoom: ['双指捏合', '平滑缩放远近'],
          pan: ['双指拖动', '自由平移观察位置'],
          tap: ['轻点物体', '开关灯光与互动屏幕'],
          tip: '底部控制条可左右滑动切换机位、时段与配乐',
          cta: '开始探索',
        }
      : {
          orbit: ['1-Finger Drag', 'Rotate & look around 360°'],
          zoom: ['2-Finger Pinch', 'Zoom in & out smoothly'],
          pan: ['2-Finger Drag', 'Pan camera freely'],
          tap: ['Tap Objects', 'Toggle lights & screens'],
          tip: 'Swipe the bottom dock to switch views, moods & music',
          cta: 'Start Exploring',
        };
    (['orbit', 'zoom', 'pan', 'tap'] as const).forEach((key) => {
      const titleEl = this.helpModal.querySelector<HTMLElement>(`[data-gesture-title="${key}"]`);
      const descEl = this.helpModal.querySelector<HTMLElement>(`[data-gesture-desc="${key}"]`);
      if (titleEl) titleEl.textContent = mobileCopy[key][0];
      if (descEl) descEl.textContent = mobileCopy[key][1];
    });
    if (this.gestureTip) this.gestureTip.textContent = mobileCopy.tip;
    if (this.helpGotIt) this.helpGotIt.textContent = `♪ ${mobileCopy.cta}`;

    this.helpList.replaceChildren(
      ...t.helpModal.items.map((item) => {
        const li = document.createElement('li');
        const strong = document.createElement('strong');
        strong.textContent = item.lead;
        li.append(strong, document.createTextNode(item.body));
        return li;
      })
    );

    // Re-sync dynamic state labels
    this.renderCamPanButton(false);
    this.renderMoodCycleButton(false);
    this.renderWalkButton();
    this.renderLightSceneButton();
    this.renderRgbButton(false);
    this.renderMusicControls(false);

    if (notify) {
      this.showToast(t.topRight.lang.switchedToast);
    }
  }

  public setPhotoMode(active: boolean): void {
    document.body.classList.toggle('is-photo-mode', active);
    this.photoBtn.classList.toggle('is-active', active);
    this.photoBtn.setAttribute('aria-pressed', String(active));
    this.photoExitBtn.hidden = !active;
  }

  public setPureClayMode(active: boolean): void {
    this.clayBtn.classList.toggle('is-active', active);
    this.clayBtn.setAttribute('aria-pressed', String(active));
  }

  public setLightingOnlyMode(active: boolean): void {
    this.lightingBtn.classList.toggle('is-active', active);
    this.lightingBtn.setAttribute('aria-pressed', String(active));
  }

  public setWireframeMode(active: boolean): void {
    this.wireBtn.classList.toggle('is-active', active);
    this.wireBtn.setAttribute('aria-pressed', String(active));
  }

  public setLoading(percent: number, message: string, byteInfo?: { loaded: number; total: number }): void {
    this.loadingBar.style.width = `${Math.max(4, Math.min(100, percent))}%`;
    this.loadingStatus.textContent = message;
    if (this.loadingBytes && byteInfo) {
      const loadedMb = (byteInfo.loaded / (1024 * 1024)).toFixed(1);
      const totalMb = (Math.max(byteInfo.total, byteInfo.loaded) / (1024 * 1024)).toFixed(1);
      this.loadingBytes.textContent = `${loadedMb} / ${totalMb} MB`;
    }
  }

  public hideLoading(): void {
    this.loadingOverlay.classList.add('is-hidden');
  }

  /**
   * Both Desktop & Mobile: hides the loading curtain and opens the simplified Help/Gesture modal
   * with a "Start Exploring" CTA so one click guarantees Web Audio unlock + launches the GLSL reveal!
   */
  public showStartPrompt(onEnter: () => void): void {
    let entered = false;
    const finish = (): void => {
      if (entered) return;
      entered = true;
      window.removeEventListener('keydown', onKey);
      this.helpModal.removeEventListener('click', onBackdrop);
      this.helpModal.hidden = true;
      onEnter();
    };

    const onKey = (e: KeyboardEvent): void => {
      if (e.key === 'Enter' || e.key === ' ') {
        e.preventDefault();
        finish();
      }
    };

    const onBackdrop = (e: MouseEvent): void => {
      if (e.target === this.helpModal) {
        finish();
      }
    };

    this.hideLoading();
    this.helpModal.hidden = false;
    this.helpGotIt?.addEventListener('click', finish, { once: true });
    this.helpClose.addEventListener('click', finish, { once: true });
    this.helpModal.addEventListener('click', onBackdrop);
    window.addEventListener('keydown', onKey);
    (this.helpGotIt as HTMLButtonElement | null)?.focus();
  }

  public updatePerf(snap: PerfSnapshot): void {
    this.perfFps.textContent = `${snap.fps} FPS`;
    this.perfFps.style.color = snap.fps >= 55 ? '#4ade80' : snap.fps >= 40 ? '#fbbf24' : '#f87171';
    const triK = (snap.triangles / 1000).toFixed(0);
    this.perfDetail.textContent = `${snap.drawCalls} DC · ${triK}k △ · ${snap.pixelRatio}x`;
  }

  public setActiveCamera(id: CameraPresetId): void {
    this.camButtons.forEach((b) => b.classList.toggle('is-active', b.dataset.cam === id));
  }

  public setCamPanActive(active: boolean, notify = false): void {
    this.camPanActive = active;
    this.renderCamPanButton(notify);
  }

  private renderCamPanButton(notify: boolean): void {
    const spec = TRANSLATIONS[this.locale].dock.camPan;
    this.camPanBtn.classList.toggle('is-active', this.camPanActive);
    this.camPanBtn.setAttribute('aria-pressed', String(this.camPanActive));
    this.camPanLabel.textContent = spec.label;
    this.camPanBtn.title = this.camPanActive ? spec.activeTitle : spec.pausedTitle;
    if (notify) {
      this.showToast(this.camPanActive ? spec.startedToast : spec.stoppedToast);
    }
  }

  public setActiveMood(id: MoodId): void {
    this.activeMood = id;
    this.moodButtons.forEach((b) => b.classList.toggle('is-active', b.dataset.mood === id));
  }

  public setMoodCycleActive(active: boolean, notify = false): void {
    this.moodCycleActive = active;
    this.renderMoodCycleButton(notify);
  }

  private renderMoodCycleButton(notify: boolean): void {
    const spec = TRANSLATIONS[this.locale].dock.moodCycle;
    this.moodCycleBtn.classList.toggle('is-active', this.moodCycleActive);
    this.moodCycleBtn.setAttribute('aria-pressed', String(this.moodCycleActive));
    this.moodCycleLabel.textContent = spec.label;
    this.moodCycleBtn.title = this.moodCycleActive ? spec.activeTitle : spec.pausedTitle;
    if (notify) {
      this.showToast(this.moodCycleActive ? spec.startedToast : spec.stoppedToast);
    }
  }

  public setWalkMode(active: boolean): void {
    this.walkActive = active;
    this.renderWalkButton();
    this.fpHud.hidden = !active;
  }

  private renderWalkButton(): void {
    const t = TRANSLATIONS[this.locale];
    this.modeBtn.classList.toggle('is-active', this.walkActive);
    this.modeBtn.setAttribute('aria-pressed', String(this.walkActive));
    this.modeBtn.innerHTML = `${this.walkActive ? t.dock.walk.exit : t.dock.walk.enter}<kbd class="dock-kbd">V</kbd>`;
  }

  public setLightSceneLabel(mode: LightSceneMode): void {
    this.lightSceneMode = mode;
    this.renderLightSceneButton();
  }

  private renderLightSceneButton(): void {
    const t = TRANSLATIONS[this.locale];
    const label = t.dock.lightScene.labels[this.lightSceneMode];
    this.lightBtn.innerHTML = `${label}<kbd class="dock-kbd">K</kbd>`;
    this.lightBtn.classList.toggle('is-active', this.lightSceneMode !== 'cinema');
  }

  public setRgbMode(modeIndex: number, notify = true): void {
    this.rgbModeIndex = modeIndex;
    this.renderRgbButton(notify);
  }

  private renderRgbButton(notify: boolean): void {
    const t = TRANSLATIONS[this.locale];
    const modes = t.dock.rgb.modes;
    const spec = modes[this.rgbModeIndex % modes.length] ?? modes[0];
    this.rgbBtn.innerHTML = `${spec.shortLabel}<kbd class="dock-kbd">R</kbd>`;
    this.rgbBtn.title = t.dock.rgb.title(spec.name);
    this.rgbBtn.classList.toggle('is-active', this.rgbModeIndex !== 5);
    if (notify) {
      this.showToast(t.dock.rgb.toast(spec.name));
    }
  }

  public setMusicState(enabled: boolean, playing: boolean, mood: MoodId, notify = false): void {
    this.musicEnabled = enabled;
    this.musicPlaying = playing;
    this.musicMood = mood;
    this.renderMusicControls(notify);
  }

  private renderMusicControls(notify: boolean): void {
    const t = TRANSLATIONS[this.locale];
    const trackLabel = t.dock.music.tracks[this.musicMood];
    const muted = !this.musicEnabled;

    // Bottom dock music pill
    this.musicBtn.classList.toggle('is-active', this.musicEnabled);
    this.musicBtn.classList.toggle('is-playing', this.musicPlaying);
    this.musicBtn.setAttribute('aria-pressed', String(muted));
    this.musicLabel.textContent = this.musicEnabled ? trackLabel : t.dock.music.mutedLabel;
    this.musicBtn.title = this.musicEnabled
      ? t.dock.music.playingTitle(trackLabel)
      : t.dock.music.mutedTitle;

    if (notify) {
      this.showToast(this.musicEnabled ? t.dock.music.playingToast(trackLabel) : t.dock.music.mutedToast);
    }
  }

  public showToast(text: string): void {
    this.modeToast.textContent = text;
    this.modeToast.hidden = false;
    this.modeToast.classList.add('is-visible');
    window.clearTimeout(this.toastTimer);
    this.toastTimer = window.setTimeout(() => {
      this.modeToast.classList.remove('is-visible');
    }, 1800);
  }
}
