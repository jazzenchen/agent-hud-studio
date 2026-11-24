import * as THREE from 'three';

export interface LightmapBlendUniforms {
  uLightMapB: { value: THREE.Texture | null };
  uLightMapMix: { value: number };
  uLightMapRange: { value: number };
  uLightMapScale: { value: number };
}

/**
 * Patches MeshStandardMaterial / MeshPhysicalMaterial to decode and smoothly cross-fade
 * two Cycles-baked 8-bit HDR RGBM Lightmaps on UV1 (TEXCOORD_1) in real time at 60 FPS!
 *
 * Also suppresses redundant diffuse IBL on lightmapped surfaces while keeping full PMREM
 * specular reflections so oak herringbone floors, walnut desks, and concrete keep physical sheen.
 */
export function patchMaterialWithRgbMLightmap(
  material: THREE.MeshStandardMaterial,
  lightMapA: THREE.Texture,
  sharedUniforms: LightmapBlendUniforms,
  intensity = 1.0
): void {
  // Remove the tiny 4x4 dummy emissive anchor that guaranteed TEXCOORD_1 export from Blender
  if (material.emissiveMap) {
    material.emissiveMap = null;
  }
  material.emissive.setRGB(0, 0, 0);
  material.emissiveIntensity = 0;

  // Bind LightMap A onto Three.js standard lightMap slot (channel 1 -> TEXCOORD_1!)
  lightMapA.channel = 1;
  material.lightMap = lightMapA;
  material.lightMapIntensity = intensity;

  material.customProgramCacheKey = () => 'archviz_rgbm_dual_lightmap_v2';

  material.onBeforeCompile = (shader) => {
    shader.uniforms.uLightMapB = sharedUniforms.uLightMapB;
    shader.uniforms.uLightMapMix = sharedUniforms.uLightMapMix;
    shader.uniforms.uLightMapRange = sharedUniforms.uLightMapRange;
    shader.uniforms.uLightMapScale = sharedUniforms.uLightMapScale;

    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <lightmap_pars_fragment>',
      /* glsl */ `
      #include <lightmap_pars_fragment>
      uniform sampler2D uLightMapB;
      uniform float uLightMapMix;
      uniform float uLightMapRange;
      uniform float uLightMapScale;

      vec3 decodeRGBMLightmap(vec4 rgbm, float maxRange) {
        vec3 decoded = rgbm.rgb * (rgbm.a * maxRange);
        return clamp(decoded, vec3(0.0), vec3(16.0));
      }
      `
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <lights_fragment_maps>',
      /* glsl */ `
      #if defined( RE_IndirectDiffuse )
        #ifdef USE_LIGHTMAP
          vec3 lmA = decodeRGBMLightmap(texture2D(lightMap, vLightMapUv), uLightMapRange);
          vec3 lmB = decodeRGBMLightmap(texture2D(uLightMapB, vLightMapUv), uLightMapRange);
          vec3 bakedDiffuse = mix(lmA, lmB, uLightMapMix) * lightMapIntensity * uLightMapScale;
          // Multiply by PI because Three.js BRDF_Lambert divides indirect irradiance by PI
          irradiance += bakedDiffuse * PI;
        #endif
        #if defined( USE_ENVMAP ) && defined( STANDARD ) && defined( ENVMAP_TYPE_CUBE_UV )
          // Tiny 3% ambient IBL fill on baked surfaces so shadow crevices never crush to pure 0
          iblIrradiance += getIBLIrradiance(geometryNormal) * 0.03;
        #endif
      #endif
      #if defined( RE_IndirectSpecular )
        #ifdef USE_ENVMAP
          radiance += getIBLRadiance(geometryViewDir, geometryNormal, material.roughness);
          #ifdef USE_CLEARCOAT
            clearcoatRadiance += getIBLRadiance(geometryViewDir, geometryClearcoatNormal, material.clearcoatRoughness);
          #endif
        #endif
      #endif
      `
    );

    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <lights_fragment_end>',
      /* glsl */ `
      #include <lights_fragment_end>
      // Cycles HDR Lightmap already includes 100% physical direct + indirect GI!
      // Keep only subtle 10% dynamic direct tint so interactive ScreenBar/RGB toggles respond naturally without double-lighting.
      reflectedLight.directDiffuse *= 0.10;
      reflectedLight.directSpecular *= 0.22;
      `
    );
  };

  material.needsUpdate = true;
}
