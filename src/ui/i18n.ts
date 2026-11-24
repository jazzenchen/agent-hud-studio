import type { LightSceneMode, MoodId } from '../core/MoodSystem';
import type { CameraPresetId } from '../interaction/DualCameraController';

export type Locale = 'zh' | 'en';

export function detectInitialLocale(): Locale {
  try {
    const params = new URLSearchParams(window.location.search);
    const paramLang = params.get('lang')?.trim().toLowerCase();
    if (paramLang === 'zh' || paramLang?.startsWith('zh-')) {
      return 'zh';
    }
    if (paramLang === 'en' || paramLang?.startsWith('en-')) {
      return 'en';
    }
  } catch {
    // Ignore URL parsing errors in restricted contexts
  }
  return 'en';
}

export function saveLocale(locale: Locale): void {
  try {
    const url = new URL(window.location.href);
    url.searchParams.set('lang', locale);
    window.history.replaceState(null, '', url.toString());
  } catch {
    // Ignore history API errors in restricted contexts
  }
}

export interface TranslationBundle {
  htmlLang: string;
  pageTitle: string;
  canvasAriaLabel: string;
  brandSub: string;
  perfPillTitle: string;
  loading: {
    init: string;
    mesh: string;
    loftProgress: (pct: number) => string;
    lightmaps: string;
    sky: string;
    pmrem: string;
    shaders: string;
    probes: string;
    warmup: string;
    ready: string;
    failed: (msg: string) => string;
  };
  topRight: {
    viewGroupAria: string;
    qualityGroupAria: string;
    photo: { label: string; title: string };
    clay: { label: string; title: string };
    lighting: { label: string; title: string };
    wire: { label: string; title: string };
    lang: {
      buttonText: string;
      ariaLabel: string;
      title: string;
      switchedToast: string;
    };
    help: {
      ariaLabel: string;
      title: string;
    };
  };
  photoExit: string;
  fpBanner: string;
  dock: {
    navAria: string;
    camGroupAria: string;
    moodGroupAria: string;
    cameras: Partial<Record<CameraPresetId, { label: string; title: string }>>;
    camPan: {
      label: string;
      activeTitle: string;
      pausedTitle: string;
      startedToast: string;
      stoppedToast: string;
    };
    moods: Record<MoodId, { label: string; title: string }>;
    moodCycle: {
      label: string;
      activeTitle: string;
      pausedTitle: string;
      startedToast: string;
      stoppedToast: string;
    };
    walk: { enter: string; exit: string; title: string };
    lightScene: {
      title: string;
      labels: Record<LightSceneMode, string>;
    };
    screen: { label: string; title: string };
    rgb: {
      title: (fullName: string) => string;
      toast: (fullName: string) => string;
      modes: Array<{ shortLabel: string; name: string }>;
    };
    music: {
      mutedLabel: string;
      tracks: Record<MoodId, string>;
      playingTitle: (trackLabel: string) => string;
      mutedTitle: string;
      playingToast: (trackLabel: string) => string;
      mutedToast: string;
    };
  };
  interact: {
    defaultLabel: string;
    agentHud: string;
    agentHudSite: string;
    screenBar: string;
    pcRgb: string;
    floorLamp: string;
    kitchenPendant: string;
  };
  helpModal: {
    title: string;
    closeAria: string;
    items: Array<{ lead: string; body: string }>;
  };
}

export const TRANSLATIONS: Record<Locale, TranslationBundle> = {
  zh: {
    htmlLang: 'zh-CN',
    pageTitle: 'AgentHUD Studio · 极客工业风 Loft 3D 写实空间',
    canvasAriaLabel: '极客公寓 3D 交互场景',
    brandSub: '5-ZONE PENTHOUSE',
    perfPillTitle: '点击展开/收起渲染遥测',
    loading: {
      init: '正在初始化 WebGL2 / AgX 渲染管线…',
      mesh: '正在加载工业级 Draco 写实场景网格…',
      loftProgress: (pct) => `正在加载全屋五空间极客 Loft (${pct}%)…`,
      lightmaps: '正在加载全屋四时段双图集 2K HDR + OIDN 光照贴图…',
      sky: '正在加载四时段东京高空天际线全景…',
      pmrem: '正在烘焙 Poly Haven 真实环境反射 (PMREM)…',
      shaders: '正在注入 Cycles HDR 光照贴图着色器与动态屏幕…',
      probes: '正在预烘焙四时段 × 4 空间室内反射探针 (零闪屏平滑过渡)…',
      warmup: '正在预编译 4× MSAA 与微距景深光学着色器…',
      ready: '准备就绪',
      failed: (msg) => `加载失败: ${msg}`,
    },
    topRight: {
      viewGroupAria: '渲染检视模式',
      qualityGroupAria: '画质档位',
      photo: { label: '纯净摄影', title: '隐藏界面，纯净摄影视角 (P)' },
      clay: { label: '纯白模', title: '纯白模建筑模型检视：全局统一石膏白模，隐藏天空盒 (C)' },
      lighting: { label: '白模光照', title: '白模光照检视：隐藏材质纹理与天空盒，仅查看 Cycles GI 烘焙 (L)' },
      wire: { label: '线框', title: '网格线框检视：隐藏天空盒，查看几何拓扑 (G)' },
      lang: {
        buttonText: 'EN',
        ariaLabel: '切换到英文界面',
        title: 'Switch to English',
        switchedToast: '已切换为中文',
      },
      help: {
        ariaLabel: '操作指南',
        title: '操作指南 (H)',
      },
    },
    photoExit: '退出摄影模式 (P / ESC)',
    fpBanner: '第一人称漫游 · WASD 移动 · Shift 加速 · 鼠标环视 · ESC / V 退出',
    dock: {
      navAria: '场景控制栏',
      camGroupAria: '预设机位',
      moodGroupAria: '时段光照',
      cameras: {
        hero: { label: '书房工位', title: '书房工位 (1)' },
        living: { label: '客厅主机', title: '客厅主机 (2)' },
        kitchen: { label: '咖啡厨房', title: '咖啡厨房 (3)' },
        bedroom: { label: '长虹主卧', title: '长虹主卧 (4)' },
        bathroom: { label: '极简卫浴', title: '极简卫浴 (5)' },
        desk: { label: '桌面微距', title: '桌面微距·浅景深 (6)' },
        window: { label: '窗景露台', title: '窗景露台 (7)' },
      },
      camPan: {
        label: '扫镜',
        activeTitle: '镜头沿圆弧缓慢扫镜中 · 点击停止（拖拽镜头会暂停片刻后从新角度继续）',
        pausedTitle: '镜头缓慢扫镜已停止 · 点击开启',
        startedToast: '镜头扫镜 · 已开启',
        stoppedToast: '镜头扫镜 · 已停止',
      },
      moods: {
        midnight: { label: '深夜直播', title: '深夜直播 (M 轮换)' },
        daylight: { label: '清晨日景', title: '清晨日景 (M 轮换)' },
        noon: { label: '正午晴空', title: '正午晴空 (M 轮换)' },
        golden: { label: '黄金时刻', title: '黄金时刻 (M 轮换)' },
      },
      moodCycle: {
        label: '循环',
        activeTitle: '时段自动循环中 · 点击停止（选择任意时段也会手动停止）',
        pausedTitle: '时段自动循环已暂停 · 点击开启',
        startedToast: '时段自动循环 · 已开启',
        stoppedToast: '时段自动循环 · 已停止',
      },
      walk: {
        enter: '漫游模式',
        exit: '退出漫游',
        title: '切换第一人称 WASD 漫游 (V)',
      },
      lightScene: {
        title: '切换全屋照明场景：全屋开灯 / 柔光氛围 / 关灯影院 (K)',
        labels: {
          bright: '全屋开灯',
          cozy: '柔光氛围',
          cinema: '关灯影院',
        },
      },
      screen: {
        label: '切屏',
        title: '切换电脑屏幕 Agent HUD / IDE / OBS 直播 / 频谱界面 (T)',
      },
      rgb: {
        title: (fullName) => `工作室全联动霓虹灯效：${fullName} (按 R 切换 6 种模式)`,
        toast: (fullName) => `霓虹联动 · ${fullName}`,
        modes: [
          { shortLabel: '冰青', name: '赛博双色 · 固定色 (1/6)' },
          { shortLabel: '彩虹', name: '彩虹跑马 · 全屋追光 (2/6)' },
          { shortLabel: '流光', name: '赛博流光 · 三色液态流动 (3/6)' },
          { shortLabel: '变换', name: '幻彩变换 · 全屋同步渐变 (4/6)' },
          { shortLabel: '呼吸', name: '深空呼吸 · 紫粉电影脉冲 (5/6)' },
          { shortLabel: '暖白', name: '极简暖白 · 画廊固定色 (6/6)' },
        ],
      },
      music: {
        mutedLabel: '静音',
        tracks: {
          midnight: '深夜 Lo-Fi',
          daylight: '清晨钢琴',
          noon: '正午律动',
          golden: '黄昏电钢',
        },
        playingTitle: (trackLabel) => `正在播放时段配乐：${trackLabel}（与跑马灯节奏实时同步 · 按 B 静音）`,
        mutedTitle: '时段配乐已静音（按 B 开启）',
        playingToast: (trackLabel) => `音乐联动 · ${trackLabel}`,
        mutedToast: '音乐已静音',
      },
    },
    interact: {
      defaultLabel: '点击交互',
      agentHud: '点击访问 Agent HUD (agenthud.app) ↗',
      agentHudSite: '点击访问 Agent HUD 官网 (agenthud.app) ↗',
      screenBar: '点击开关桌面屏幕挂灯',
      pcRgb: '点击切换工作室 6 种全联动霓虹灯效 (R)',
      floorLamp: '点击切换全屋照明：全屋开灯 / 柔光氛围 / 关灯影院 (K)',
      kitchenPendant: '点击切换全屋照明场景 (K)',
    },
    helpModal: {
      title: '快速操作指南',
      closeAria: '关闭操作指南',
      items: [
        { lead: '鼠标拖拽 / 滚轮', body: '：左键环视、滚轮缩放、右键平移（按 V 切换 WASD 漫游）' },
        { lead: '数字 1~7 · 快捷键 M', body: '：切换全屋 7 个电影机位与 24 小时四时段光照' },
        { lead: '点击场景物体', body: '：点电脑或电视直达 agenthud.app，点灯具开关照明' },
        { lead: 'K / R / B / P', body: '：K 切照明 · R 切霓虹 · B 开关配乐 · P 纯净摄影' },
      ],
    },
  },
  en: {
    htmlLang: 'en',
    pageTitle: 'AgentHUD Studio · Geek Industrial Loft 3D Showcase',
    canvasAriaLabel: 'Geek Industrial Loft 3D interactive scene',
    brandSub: '5-ZONE PENTHOUSE',
    perfPillTitle: 'Click to expand or collapse render telemetry',
    loading: {
      init: 'Initializing WebGL2 / AgX rendering pipeline…',
      mesh: 'Loading industrial Draco photorealistic scene mesh…',
      loftProgress: (pct) => `Loading 5-zone Geek Loft (${pct}%)…`,
      lightmaps: 'Loading 4-mood dual-atlas 2K HDR + OIDN lightmaps…',
      sky: 'Loading 4-mood Tokyo skyline panoramas…',
      pmrem: 'Baking Poly Haven real-time environment reflections (PMREM)…',
      shaders: 'Injecting Cycles HDR lightmap shaders & live screens…',
      probes: 'Pre-baking 4-mood × 4-zone indoor reflection probes…',
      warmup: 'Pre-compiling 4× MSAA & macro depth-of-field shaders…',
      ready: 'Ready',
      failed: (msg) => `Load failed: ${msg}`,
    },
    topRight: {
      viewGroupAria: 'Render inspection modes',
      qualityGroupAria: 'Quality presets',
      photo: { label: 'Photo', title: 'Hide HUD for clean photography view (P)' },
      clay: { label: 'Clay', title: 'Pure clay architectural maquette view, hiding skybox (C)' },
      lighting: { label: 'Lighting', title: 'Lighting-only GI view: hide textures & skybox, inspect Cycles GI bake (L)' },
      wire: { label: 'Wire', title: 'Wireframe topology view, hiding skybox (G)' },
      lang: {
        buttonText: '中文',
        ariaLabel: 'Switch to Chinese interface',
        title: '切换为中文界面',
        switchedToast: 'Switched to English',
      },
      help: {
        ariaLabel: 'Controls & shortcuts',
        title: 'Controls & Shortcuts (H)',
      },
    },
    photoExit: 'Exit Photo Mode (P / ESC)',
    fpBanner: 'First-Person Walk · WASD Move · Shift Sprint · Mouse Look · ESC / V Exit',
    dock: {
      navAria: 'Scene control dock',
      camGroupAria: 'Camera presets',
      moodGroupAria: 'Time-of-day lighting',
      cameras: {
        hero: { label: 'Studio', title: 'Studio Desk (1)' },
        living: { label: 'Living', title: 'Living Room & TV (2)' },
        kitchen: { label: 'Kitchen', title: 'Coffee Kitchen (3)' },
        bedroom: { label: 'Bedroom', title: 'Master Bedroom (4)' },
        bathroom: { label: 'Bath', title: 'Minimalist Spa Bath (5)' },
        desk: { label: 'Macro', title: 'Desk Macro · Shallow DoF (6)' },
        window: { label: 'View', title: 'Window Terrace (7)' },
      },
      camPan: {
        label: 'Pan',
        activeTitle: 'Slow camera arc sweep active · Click to stop (dragging pauses briefly, then resumes from your angle)',
        pausedTitle: 'Slow camera arc sweep stopped · Click to start',
        startedToast: 'Camera Sweep · Started',
        stoppedToast: 'Camera Sweep · Stopped',
      },
      moods: {
        midnight: { label: 'Midnight', title: 'Midnight Stream (M cycle)' },
        daylight: { label: 'Morning', title: 'Morning Daylight (M cycle)' },
        noon: { label: 'Noon', title: 'Clear Noon (M cycle)' },
        golden: { label: 'Golden', title: 'Golden Hour (M cycle)' },
      },
      moodCycle: {
        label: 'Auto',
        activeTitle: 'Auto-cycling time of day · Click to stop (selecting a time also stops it)',
        pausedTitle: 'Time-of-day auto cycle paused · Click to start',
        startedToast: 'Time Cycle · Started',
        stoppedToast: 'Time Cycle · Stopped',
      },
      walk: {
        enter: 'Walk',
        exit: 'Exit Walk',
        title: 'Toggle First-Person WASD Walk Mode (V)',
      },
      lightScene: {
        title: 'Cycle indoor lighting: All Lights / Cozy Mood / Cinema (K)',
        labels: {
          bright: 'Lights On',
          cozy: 'Cozy',
          cinema: 'Cinema',
        },
      },
      screen: {
        label: 'Screen',
        title: 'Cycle monitor displays: Agent HUD / IDE / OBS / Spectrum (T)',
      },
      rgb: {
        title: (fullName) => `Studio synced neon lighting: ${fullName} (Press R for 6 modes)`,
        toast: (fullName) => `Neon Sync · ${fullName}`,
        modes: [
          { shortLabel: 'Cyber', name: 'Cyber Dual-Tone · Static (1/6)' },
          { shortLabel: 'Rainbow', name: 'Rainbow Marquee · Full Chase (2/6)' },
          { shortLabel: 'Liquid', name: 'Synthwave Flow · Tri-Color (3/6)' },
          { shortLabel: 'Morph', name: 'Spectrum Morph · Synced (4/6)' },
          { shortLabel: 'Pulse', name: 'Cyber Pulse · Breathing (5/6)' },
          { shortLabel: 'Warm', name: 'Gallery Warm · Static (6/6)' },
        ],
      },
      music: {
        mutedLabel: 'Muted',
        tracks: {
          midnight: 'Midnight Lo-Fi',
          daylight: 'Morning Piano',
          noon: 'Noon Groove',
          golden: 'Golden Rhodes',
        },
        playingTitle: (trackLabel) => `Playing soundtrack: ${trackLabel} (synced with neon rhythm · Press B to mute)`,
        mutedTitle: 'Soundtrack muted (Press B to unmute)',
        playingToast: (trackLabel) => `Audio Sync · ${trackLabel}`,
        mutedToast: 'Audio Muted',
      },
    },
    interact: {
      defaultLabel: 'Click to interact',
      agentHud: 'Visit Agent HUD (agenthud.app) ↗',
      agentHudSite: 'Visit Agent HUD Website (agenthud.app) ↗',
      screenBar: 'Toggle desk monitor light bar',
      pcRgb: 'Cycle 6 studio synced neon modes (R)',
      floorLamp: 'Cycle indoor lighting: Lights On / Cozy / Cinema (K)',
      kitchenPendant: 'Cycle indoor lighting scene (K)',
    },
    helpModal: {
      title: 'Quick Controls',
      closeAria: 'Close controls guide',
      items: [
        { lead: 'Drag / Scroll', body: ': Left-drag to orbit, scroll to zoom, right-drag to pan (V for WASD walk)' },
        { lead: 'Keys 1~7 · M', body: ': Switch 7 cinematic views and 24h lighting moods' },
        { lead: 'Click Objects', body: ': Click screens or TV for agenthud.app; click lamps to toggle lights' },
        { lead: 'K / R / B / P', body: ': K lights · R neon modes · B music · P clean photo mode' },
      ],
    },
  },
};
