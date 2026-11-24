import * as THREE from 'three';
import { N8AOPostPass } from 'n8ao';
import {
  BloomEffect,
  DepthOfFieldEffect,
  EffectComposer,
  EffectPass,
  RenderPass,
  SMAAEffect,
  SMAAPreset,
  ToneMappingEffect,
  ToneMappingMode,
  VignetteEffect,
} from 'postprocessing';
import { SceneRevealEffect } from './SceneRevealEffect';

export type PostFxQualityMode = 'ultra' | 'high' | 'fast';

export class PostProcessingPipeline {
  public readonly composer: EffectComposer;
  public readonly renderPass: RenderPass;
  public readonly n8ao: N8AOPostPass;
  public readonly effectPass: EffectPass;
  public readonly macroDofPass: EffectPass;
  public readonly dof: DepthOfFieldEffect;
  public readonly bloom: BloomEffect;
  public readonly vignette: VignetteEffect;
  public readonly reveal: SceneRevealEffect;
  private readonly macroBloom: BloomEffect;
  private readonly macroVignette: VignetteEffect;

  private aoAttached = false;
  private dofActive = false;
  private qualityMode: PostFxQualityMode = 'ultra';
  private preferredMsaa = 4;
  private readonly isMobile: boolean;

  // Smooth cinema lens focus-pull & bokeh ramp state (active ONLY in macro views!)
  private wantDof = false;
  private currentBokeh = 0;
  private targetBokeh = 0;
  private currentFocusDist = 1.37;
  private targetFocusDist = 1.37;

  constructor(renderer: THREE.WebGLRenderer, scene: THREE.Scene, camera: THREE.PerspectiveCamera) {
    this.isMobile =
      (typeof window !== 'undefined' && window.matchMedia?.('(pointer: coarse)').matches) ||
      /Mobi|Android|iPhone|iPad|iPod/i.test(navigator.userAgent);

    // Desktop: Hardware WebGL2 4x MSAA + SMAA ULTRA + HalfFloat Mipmap Bloom + AgX ToneMapping.
    // Mobile: 0x MSAA + SMAA MEDIUM to avoid 4x HalfFloat tile-memory bandwidth bottlenecks!
    const maxSamples = this.isMobile ? 0 : Math.min(4, renderer.capabilities.maxSamples || 4);
    this.preferredMsaa = maxSamples;
    this.composer = new EffectComposer(renderer, {
      frameBufferType: THREE.HalfFloatType,
      multisampling: maxSamples,
    });

    this.renderPass = new RenderPass(scene, camera);

    // N8AO kept ready strictly for Pure Clay mode (which has no baked lightmaps); detached during normal MSAA photo mode!
    this.n8ao = new N8AOPostPass(scene, camera, window.innerWidth, window.innerHeight);
    this.n8ao.configuration.aoRadius = 0.45;
    this.n8ao.configuration.distanceFalloff = 0.85;
    this.n8ao.configuration.intensity = 2.15;
    this.n8ao.configuration.halfRes = true;
    this.n8ao.configuration.aoSamples = 10;
    this.n8ao.configuration.denoiseSamples = 4;
    this.n8ao.configuration.denoiseRadius = 8;
    this.n8ao.configuration.gammaCorrection = false;
    this.n8ao.configuration.transparencyAware = false;
    this.n8ao.configuration.color = new THREE.Color('#090706');

    const smaa = new SMAAEffect({
      preset: this.isMobile ? SMAAPreset.MEDIUM : SMAAPreset.ULTRA,
    });

    this.bloom = new BloomEffect({
      mipmapBlur: true,
      luminanceThreshold: 1.14,
      luminanceSmoothing: 0.24,
      intensity: 0.34,
      radius: 0.54,
    });

    const toneMapping = new ToneMappingEffect({
      mode: ToneMappingMode.AGX,
    });

    this.vignette = new VignetteEffect({
      eskil: false,
      offset: 0.24,
      darkness: 0.32,
    });

    this.reveal = new SceneRevealEffect();

    this.effectPass = new EffectPass(camera, smaa, this.bloom, toneMapping, this.vignette, this.reveal);

    // Dedicated cinema macro Depth-of-Field pass (attached dynamically ONLY in Desk/PC/Pegboard Macro views!)
    // Uses world-meter focusDistance + focusRange w/ 0.75 resolution scale for creamy 50mm f/1.4 optical bokeh!
    this.dof = new DepthOfFieldEffect(camera, {
      focusDistance: 1.37,
      focusRange: 0.68,
      bokehScale: 0.0,
      resolutionScale: 0.75,
    });
    const macroSmaa = new SMAAEffect({ preset: SMAAPreset.ULTRA });
    this.macroBloom = new BloomEffect({
      mipmapBlur: true,
      luminanceThreshold: 1.14,
      luminanceSmoothing: 0.24,
      intensity: 0.34,
      radius: 0.54,
    });
    const macroToneMapping = new ToneMappingEffect({ mode: ToneMappingMode.AGX });
    this.macroVignette = new VignetteEffect({
      eskil: false,
      offset: 0.24,
      darkness: 0.34,
    });
    this.macroDofPass = new EffectPass(
      camera,
      this.dof,
      macroSmaa,
      this.macroBloom,
      macroToneMapping,
      this.macroVignette
    );

    this.composer.addPass(this.renderPass);
    this.composer.addPass(this.effectPass);
  }

  public setMoodVisuals(bloomIntensity: number, vignetteDarkness: number): void {
    this.bloom.intensity = bloomIntensity;
    this.vignette.uniforms.get('darkness')!.value = vignetteDarkness;
    this.macroBloom.intensity = bloomIntensity;
    this.macroVignette.uniforms.get('darkness')!.value = vignetteDarkness + 0.04;
  }

  public setQualityMode(mode: PostFxQualityMode): void {
    if (mode === this.qualityMode) return;
    this.qualityMode = mode;
    this.preferredMsaa = this.isMobile ? (mode === 'ultra' ? 2 : 0) : mode === 'fast' ? 2 : 4;
    this.syncPassGraph();
  }

  public setForceAo(force: boolean): void {
    if (force === this.aoAttached) return;
    this.aoAttached = force;
    this.syncPassGraph();
  }

  /**
   * Smoothly engage or release cinematic shallow Depth of Field for Macro views (`桌面微距`, `pc`, `pegboard`).
   * While active, dynamically pulls focus onto `focusDistMeters` (camera -> orbit target) and scales focusRange
   * physically like a 50mm f/1.4 lens! Outside macro views, completely detaches DoF so WebGL2 4x MSAA stays 100% active.
   */
  public setMacroDof(enabled: boolean, focusDistMeters: number, bokehScale = 4.2, instant = false): void {
    this.wantDof = enabled && this.qualityMode !== 'fast' && !this.aoAttached;
    this.targetBokeh = this.wantDof ? bokehScale : 0;
    this.targetFocusDist = Math.max(0.35, Math.min(4.0, focusDistMeters));

    if (this.wantDof && !this.dofActive) {
      this.currentFocusDist = this.targetFocusDist;
      this.dof.cocMaterial.focusDistance = this.currentFocusDist;
      this.dof.cocMaterial.focusRange = THREE.MathUtils.clamp(this.currentFocusDist * 0.56, 0.58, 0.92);
      if (instant) {
        this.currentBokeh = this.targetBokeh;
        this.dof.bokehScale = this.currentBokeh;
      }
      this.dofActive = true;
      this.syncPassGraph();
    } else if (!this.wantDof && instant && this.dofActive) {
      this.currentBokeh = 0;
      this.dof.bokehScale = 0;
      this.dofActive = false;
      this.syncPassGraph();
    }
  }

  public updateMacroDof(delta: number): void {
    if (!this.dofActive) return;

    const focusEase = 1 - Math.exp(-9.0 * delta);
    const bokehEase = 1 - Math.exp(-(this.wantDof ? 5.2 : 11.0) * delta);

    this.currentFocusDist = THREE.MathUtils.lerp(this.currentFocusDist, this.targetFocusDist, focusEase);
    this.currentBokeh = THREE.MathUtils.lerp(this.currentBokeh, this.targetBokeh, bokehEase);

    this.dof.cocMaterial.focusDistance = this.currentFocusDist;
    // Goldilocks 50mm f/2.0 macro S-curve: flat-sharp across BOTH keyboard (1.37m) & 38" monitor (1.61m) at ~1.49m focus,
    // while cleanly blooming the back concrete wall (2.05m), hex neon, floor lamp, & skyline into creamy optical bokeh!
    this.dof.cocMaterial.focusRange = THREE.MathUtils.clamp(this.currentFocusDist * 0.56, 0.58, 0.92);
    this.dof.bokehScale = this.currentBokeh;

    // Once bokeh has smoothly faded out after leaving macro view, detach DoF pass & restore hardware 4x MSAA!
    if (!this.wantDof && this.currentBokeh < 0.06) {
      this.currentBokeh = 0;
      this.dof.bokehScale = 0;
      this.dofActive = false;
      this.syncPassGraph();
    }
  }

  private syncPassGraph(): void {
    const useDof = this.dofActive && !this.aoAttached && this.qualityMode !== 'fast';
    const needsDepthTexture = this.aoAttached || useDof;

    // WebGL2 rule: NEVER attach a depthTexture while multisampling > 0!
    // Always drop to multisampling=0 BEFORE adding N8AO/DoF, and remove all depth passes BEFORE restoring 4x MSAA!
    if (needsDepthTexture) {
      this.composer.multisampling = 0;
    }

    this.composer.removePass(this.n8ao);
    this.composer.removePass(this.effectPass);
    this.composer.removePass(this.macroDofPass);

    if (this.aoAttached) {
      this.composer.addPass(this.n8ao);
      this.composer.addPass(this.effectPass);
    } else if (useDof) {
      this.composer.addPass(this.macroDofPass);
    } else {
      this.composer.addPass(this.effectPass);
      this.composer.multisampling = this.preferredMsaa;
    }
  }

  public setMultisampling(samples: number): void {
    this.preferredMsaa = Math.max(0, Math.min(4, samples));
    if (!this.aoAttached && !this.dofActive) {
      this.composer.multisampling = this.preferredMsaa;
    }
  }

  public setSize(width: number, height: number): void {
    this.composer.setSize(width, height);
    this.n8ao.setSize(width, height);
    this.macroDofPass.setSize(width, height);
    this.reveal.setSize(width, height);
  }

  public triggerReveal(): void {
    this.reveal.start();
  }

  /**
   * Pre-compile Macro DoF & normal 4x MSAA shader pipelines once during loading screen
   * so switching to `桌面微距` for the very first time has ZERO WebGL shader-compile hitch!
   */
  public warmup(): void {
    if (!this.isMobile) {
      this.dofActive = true;
      this.dof.bokehScale = 0.0;
      this.syncPassGraph();
      this.composer.render(0.016);
    }

    this.dofActive = false;
    this.syncPassGraph();
    this.composer.render(0.016);
  }

  public render(delta: number): void {
    this.reveal.advance(delta);
    this.composer.render(delta);
  }

  public dispose(): void {
    this.composer.dispose();
  }
}
