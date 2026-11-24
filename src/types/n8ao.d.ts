declare module 'n8ao' {
  import type * as THREE from 'three';
  import type { Pass } from 'postprocessing';

  export interface N8AOConfiguration {
    aoRadius: number;
    distanceFalloff: number;
    intensity: number;
    color: THREE.Color;
    aoSamples: number;
    denoiseSamples: number;
    denoiseRadius: number;
    denoiseIterations?: number;
    halfRes: boolean;
    gammaCorrection: boolean;
    transparencyAware?: boolean;
    colorMultiply?: boolean;
    aoTones?: number;
    renderMode?: number;
  }

  export class N8AOPostPass extends Pass {
    public configuration: N8AOConfiguration;
    constructor(
      scene: THREE.Scene,
      camera: THREE.Camera,
      width?: number,
      height?: number
    );
    public setQualityMode(mode: 'Performance' | 'Low' | 'Medium' | 'High' | 'Ultra'): void;
  }
}
