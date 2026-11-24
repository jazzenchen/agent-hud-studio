import * as THREE from 'three';
import { Effect } from 'postprocessing';

const REVEAL_FRAGMENT_SHADER = /* glsl */ `
uniform float uReveal;
uniform float uTime;
uniform float uAspect;
uniform vec2 uTexelSize;

float revealHash(vec2 p) {
  return fract(sin(dot(p, vec2(127.1, 311.7))) * 43758.5453123);
}

float revealNoise(vec2 p) {
  vec2 i = floor(p);
  vec2 f = fract(p);
  vec2 u = f * f * (3.0 - 2.0 * f);
  return mix(
    mix(revealHash(i + vec2(0.0, 0.0)), revealHash(i + vec2(1.0, 0.0)), u.x),
    mix(revealHash(i + vec2(0.0, 1.0)), revealHash(i + vec2(1.0, 1.0)), u.x),
    u.y
  );
}

float revealLuma(vec3 c) {
  return dot(c, vec3(0.2126, 0.7152, 0.0722));
}

void mainImage(const in vec4 inputColor, const in vec2 uv, out vec4 outputColor) {
  if (uReveal >= 0.999) {
    outputColor = inputColor;
    return;
  }

  // Aspect-corrected radial coordinates from optical center
  vec2 delta = (uv - vec2(0.5, 0.48)) * vec2(uAspect, 1.0);
  float dist = length(delta);
  vec2 dir = dist > 0.0001 ? delta / dist : vec2(0.0, 1.0);

  // Subtle organic distortion along the wavefront so the scan ring feels alive
  float angle = atan(delta.y, delta.x);
  float waveNoise =
    (revealNoise(vec2(angle * 3.0, uTime * 0.9)) - 0.5) * 0.035 +
    (revealNoise(uv * 10.0 + uTime * 0.4) - 0.5) * 0.018;

  float maxRadius = length(vec2(0.5 * uAspect, 0.54)) + 0.22;
  float frontRadius = mix(-0.12, maxRadius, uReveal);
  float signedDist = (dist + waveNoise) - frontRadius;

  // Reveal mask: 1.0 inside revealed zone, 0.0 outside (blueprint zone)
  float revealedMask = 1.0 - smoothstep(-0.045, 0.035, signedDist);

  // Sharp cyan leading laser + softer warm amber trailing glow
  float laserCore = exp(-abs(signedDist) * 72.0);
  float laserHalo = exp(-abs(signedDist) * 16.0);
  float trailingGlow = exp(-max(0.0, -signedDist) * 9.5) * smoothstep(0.02, -0.02, signedDist);
  float waveStrength = clamp(laserHalo + trailingGlow * 0.65, 0.0, 1.0) * smoothstep(0.0, 0.06, uReveal) * smoothstep(1.0, 0.90, uReveal);

  // Chromatic aberration & subtle optical lens ripple right on the wavefront
  float caOffset = (laserCore * 0.0065 + laserHalo * 0.0022) * smoothstep(1.0, 0.85, uReveal);
  vec2 warpedUv = uv - dir * (laserHalo * 0.007 * smoothstep(1.0, 0.85, uReveal));
  float rChan = texture2D(inputBuffer, clamp(warpedUv + dir * caOffset, 0.0, 1.0)).r;
  float gChan = texture2D(inputBuffer, clamp(warpedUv, 0.0, 1.0)).g;
  float bChan = texture2D(inputBuffer, clamp(warpedUv - dir * caOffset, 0.0, 1.0)).b;
  vec3 revealedColor = vec3(rChan, gChan, bChan);

  // Subtle exposure bloom right behind the passing wave
  revealedColor *= 1.0 + trailingGlow * 0.24 * smoothstep(1.0, 0.82, uReveal);

  // Real-time Sobel edge-detection architectural CAD blueprint in the unrevealed zone
  vec2 px = uTexelSize * 1.35;
  float tl = revealLuma(texture2D(inputBuffer, clamp(uv + vec2(-px.x,  px.y), 0.0, 1.0)).rgb);
  float tc = revealLuma(texture2D(inputBuffer, clamp(uv + vec2(  0.0,  px.y), 0.0, 1.0)).rgb);
  float tr = revealLuma(texture2D(inputBuffer, clamp(uv + vec2( px.x,  px.y), 0.0, 1.0)).rgb);
  float ml = revealLuma(texture2D(inputBuffer, clamp(uv + vec2(-px.x,   0.0), 0.0, 1.0)).rgb);
  float mr = revealLuma(texture2D(inputBuffer, clamp(uv + vec2( px.x,   0.0), 0.0, 1.0)).rgb);
  float bl = revealLuma(texture2D(inputBuffer, clamp(uv + vec2(-px.x, -px.y), 0.0, 1.0)).rgb);
  float bc = revealLuma(texture2D(inputBuffer, clamp(uv + vec2(  0.0, -px.y), 0.0, 1.0)).rgb);
  float br = revealLuma(texture2D(inputBuffer, clamp(uv + vec2( px.x, -px.y), 0.0, 1.0)).rgb);

  float gx = -tl - 2.0 * ml - bl + tr + 2.0 * mr + br;
  float gy = -tl - 2.0 * tc - tr + bl + 2.0 * bc + br;
  float edge = clamp(sqrt(gx * gx + gy * gy) * 2.4, 0.0, 1.0);

  // Architectural millimeter grid overlay in blueprint zone
  vec2 gridUv = uv * vec2(uAspect, 1.0) * 28.0;
  vec2 gridFrac = abs(fract(gridUv - 0.5) - 0.5) / fwidth(gridUv);
  float gridLine = 1.0 - min(min(gridFrac.x, gridFrac.y), 1.0);
  float fineGrid = gridLine * 0.11;

  // Blueprint shading: deep obsidian + faint scene luminance ghost + glowing cyan CAD edges
  vec3 obsidian = vec3(0.024, 0.036, 0.058);
  vec3 cyan = vec3(0.22, 0.74, 0.97);
  vec3 amber = vec3(0.96, 0.62, 0.09);

  float sceneLuma = revealLuma(inputColor.rgb);
  vec3 blueprintColor = obsidian;
  blueprintColor += cyan * (edge * 0.92 + fineGrid);
  blueprintColor += mix(cyan, amber, 0.45) * pow(clamp(sceneLuma, 0.0, 1.0), 2.2) * 0.22;

  // Fade blueprint gently from deep obsidian at uReveal == 0 into crisp wireframe as scan begins
  float bpVisibility = smoothstep(0.0, 0.16, uReveal);
  blueprintColor = mix(obsidian, blueprintColor, 0.35 + 0.65 * bpVisibility);

  // Composite blueprint -> photorealistic scene + dual-tone laser wavefront
  vec3 col = mix(blueprintColor, revealedColor, revealedMask);
  vec3 waveColor = mix(amber, cyan, smoothstep(-0.02, 0.015, signedDist));
  col += waveColor * (laserCore * 1.15 + laserHalo * 0.38) * smoothstep(0.0, 0.05, uReveal) * smoothstep(1.0, 0.92, uReveal);
  col += amber * trailingGlow * 0.18 * waveStrength;

  outputColor = vec4(col, inputColor.a);
}
`;

export class SceneRevealEffect extends Effect {
  private active = false;
  private elapsed = 0;
  private readonly duration = 2.05;

  constructor() {
    super('SceneRevealEffect', REVEAL_FRAGMENT_SHADER, {
      uniforms: new Map<string, THREE.Uniform<unknown>>([
        ['uReveal', new THREE.Uniform(1.0)],
        ['uTime', new THREE.Uniform(0.0)],
        ['uAspect', new THREE.Uniform(window.innerWidth / Math.max(1, window.innerHeight))],
        [
          'uTexelSize',
          new THREE.Uniform(
            new THREE.Vector2(1 / Math.max(1, window.innerWidth), 1 / Math.max(1, window.innerHeight))
          ),
        ],
      ]),
    });
  }

  public setSize(width: number, height: number): void {
    const w = Math.max(1, width);
    const h = Math.max(1, height);
    this.uniforms.get('uAspect')!.value = w / h;
    (this.uniforms.get('uTexelSize')!.value as THREE.Vector2).set(1 / w, 1 / h);
  }

  public start(): void {
    this.active = true;
    this.elapsed = 0;
    this.uniforms.get('uReveal')!.value = 0.0;
    this.uniforms.get('uTime')!.value = 0.0;
  }

  public isActive(): boolean {
    return this.active;
  }

  public advance(delta: number): void {
    if (!this.active) return;
    // Clamp delta so any initial frame spike doesn't jump past the blueprint beat
    const dt = Math.min(delta, 0.05);
    this.elapsed += dt;
    this.uniforms.get('uTime')!.value = this.elapsed;

    const rawT = Math.min(1.0, this.elapsed / this.duration);
    // Smooth cinematic curve: brief blueprint beat, accelerating sweep, silky settle
    const eased =
      rawT < 0.5
        ? 4.0 * rawT * rawT * rawT
        : 1.0 - Math.pow(-2.0 * rawT + 2.0, 3.0) / 2.0;

    this.uniforms.get('uReveal')!.value = eased;

    if (rawT >= 1.0) {
      this.active = false;
      this.uniforms.get('uReveal')!.value = 1.0;
    }
  }
}
