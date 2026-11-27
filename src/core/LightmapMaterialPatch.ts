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
/**
 * Kitchen fill. The kitchen sits deepest in the plan and bakes well over a stop darker than the living room it opens
 * onto, so its baked irradiance gets a gain. The mask is a soft-edged box in world XZ so the open edges toward the
 * studio and living room blend with no seam; both atlases use it, since the floor crosses the atlas boundary.
 */
export const KITCHEN_FILL_GAIN = { value: 2.4 };

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

  material.customProgramCacheKey = () => 'archviz_rgbm_dual_lightmap_v3';

  material.onBeforeCompile = (shader) => {
    shader.uniforms.uLightMapB = sharedUniforms.uLightMapB;
    shader.uniforms.uLightMapMix = sharedUniforms.uLightMapMix;
    shader.uniforms.uLightMapRange = sharedUniforms.uLightMapRange;
    shader.uniforms.uLightMapScale = sharedUniforms.uLightMapScale;
    shader.uniforms.uKitchenFill = KITCHEN_FILL_GAIN;

    shader.vertexShader = shader.vertexShader
      .replace('#include <common>', '#include <common>\nvarying vec3 vLmWorldPos;')
      .replace(
        '#include <project_vertex>',
        '#include <project_vertex>\nvLmWorldPos = (modelMatrix * vec4(transformed, 1.0)).xyz;'
      );

    shader.fragmentShader = shader.fragmentShader.replace(
      '#include <lightmap_pars_fragment>',
      /* glsl */ `
      #include <lightmap_pars_fragment>
      uniform sampler2D uLightMapB;
      uniform float uLightMapMix;
      uniform float uLightMapRange;
      uniform float uLightMapScale;
      uniform float uKitchenFill;
      varying vec3 vLmWorldPos;

      // 1 inside the kitchen (x 2.4..6.4, z -2.05..1.5), fading to 0 across its open west and south edges.
      float kitchenFillMask(vec3 p) {
        float west = smoothstep(1.9, 2.9, p.x);
        float east = 1.0 - smoothstep(6.38, 6.46, p.x);
        float south = 1.0 - smoothstep(1.0, 2.0, p.z);
        return west * east * south;
      }

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
          bakedDiffuse *= mix(1.0, uKitchenFill, kitchenFillMask(vLmWorldPos));
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
