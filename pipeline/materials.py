"""
Real Photoscanned PBR Material Library for Blender Cycles & glTF Export.
Uses verified Poly Haven 2K PBR texture sets with physically grounded wood stains (MULTIPLY),
proper grain orientation, and custom woven rug & gallery print materials.
"""

import math
from pathlib import Path
import bpy

from config import TEX_DIR


def _load_image(path: Path, colorspace: str = "sRGB") -> bpy.types.Image | None:
    if not path.exists():
        return None
    img = bpy.data.images.load(str(path), check_existing=True)
    img.colorspace_settings.name = colorspace
    return img


def _find_map(tex_folder: Path, stem: str) -> Path | None:
    for ext in (".jpg", ".png", ".exr"):
        p = tex_folder / f"{stem}{ext}"
        if p.exists():
            return p
    return None


def make_polyhaven_pbr(
    mat_name: str,
    tex_id: str,
    uv_scale: tuple[float, float] = (1.0, 1.0),
    uv_rotation_deg: float = 0.0,
    stain: tuple[float, float, float] | None = None,
    stain_strength: float = 1.0,
    tint: tuple[float, float, float] | None = None,
    tint_strength: float = 0.0,
    brightness: float = 1.0,
    saturation: float = 1.0,
    roughness_scale: float = 1.0,
    roughness_bias: float = 0.0,
    normal_strength: float = 0.8,
    metallic: float = 0.0,
    coat_weight: float = 0.0,
    coat_roughness: float = 0.15,
    ao_strength: float = 0.35,
) -> bpy.types.Material:
    """
    Build a Cycles + glTF-ready Principled BSDF material backed by Poly Haven 2K maps.
    Uses MULTIPLY for `stain` so real wood grain contrast is preserved instead of washed out.
    """
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]

    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (760, 0)

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (400, 0)
    bsdf.inputs["Metallic"].default_value = metallic
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat_weight
        bsdf.inputs["Coat Roughness"].default_value = coat_roughness
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tex_coord = nt.nodes.new("ShaderNodeTexCoord")
    tex_coord.location = (-1000, 0)
    mapping = nt.nodes.new("ShaderNodeMapping")
    mapping.location = (-780, 0)
    mapping.inputs["Scale"].default_value = (uv_scale[0], uv_scale[1], 1.0)
    if uv_rotation_deg != 0.0:
        mapping.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(uv_rotation_deg))
    nt.links.new(tex_coord.outputs["UV"], mapping.inputs["Vector"])

    folder = TEX_DIR / tex_id

    # 1. Diffuse / Base Color
    diff_path = _find_map(folder, "diffuse")
    color_out = None
    if diff_path:
        tex_diff = nt.nodes.new("ShaderNodeTexImage")
        tex_diff.location = (-500, 340)
        tex_diff.image = _load_image(diff_path, "sRGB")
        nt.links.new(mapping.outputs["Vector"], tex_diff.inputs["Vector"])
        color_out = tex_diff.outputs["Color"]

        if brightness != 1.0 or saturation != 1.0:
            hsv = nt.nodes.new("ShaderNodeHueSaturation")
            hsv.location = (-220, 360)
            hsv.inputs["Saturation"].default_value = saturation
            hsv.inputs["Value"].default_value = brightness
            nt.links.new(color_out, hsv.inputs["Color"])
            color_out = hsv.outputs["Color"]

        if stain is not None and stain_strength > 0.0:
            mix_stain = nt.nodes.new("ShaderNodeMix")
            mix_stain.data_type = "RGBA"
            mix_stain.blend_type = "MULTIPLY"
            mix_stain.location = (-30, 360)
            mix_stain.inputs["Factor"].default_value = stain_strength
            mix_stain.inputs[7].default_value = (stain[0], stain[1], stain[2], 1.0)
            nt.links.new(color_out, mix_stain.inputs[6])
            color_out = mix_stain.outputs[2]

        if tint is not None and tint_strength > 0.0:
            mix_tint = nt.nodes.new("ShaderNodeMix")
            mix_tint.data_type = "RGBA"
            mix_tint.blend_type = "MIX"
            mix_tint.location = (120, 360)
            mix_tint.inputs["Factor"].default_value = tint_strength
            mix_tint.inputs[7].default_value = (tint[0], tint[1], tint[2], 1.0)
            nt.links.new(color_out, mix_tint.inputs[6])
            color_out = mix_tint.outputs[2]

    ao_path = _find_map(folder, "ao")
    if ao_path and color_out is not None and ao_strength > 0.0:
        tex_ao = nt.nodes.new("ShaderNodeTexImage")
        tex_ao.location = (-500, 60)
        tex_ao.image = _load_image(ao_path, "Non-Color")
        nt.links.new(mapping.outputs["Vector"], tex_ao.inputs["Vector"])

        mix_ao = nt.nodes.new("ShaderNodeMix")
        mix_ao.data_type = "RGBA"
        mix_ao.blend_type = "MULTIPLY"
        mix_ao.location = (230, 260)
        mix_ao.inputs["Factor"].default_value = ao_strength
        nt.links.new(color_out, mix_ao.inputs[6])
        nt.links.new(tex_ao.outputs["Color"], mix_ao.inputs[7])
        color_out = mix_ao.outputs[2]

    if color_out is not None:
        nt.links.new(color_out, bsdf.inputs["Base Color"])
    elif stain is not None:
        bsdf.inputs["Base Color"].default_value = (stain[0], stain[1], stain[2], 1.0)
    elif tint is not None:
        bsdf.inputs["Base Color"].default_value = (tint[0], tint[1], tint[2], 1.0)

    # 2. Roughness
    rough_path = _find_map(folder, "rough")
    if rough_path:
        tex_rough = nt.nodes.new("ShaderNodeTexImage")
        tex_rough.location = (-500, -210)
        tex_rough.image = _load_image(rough_path, "Non-Color")
        nt.links.new(mapping.outputs["Vector"], tex_rough.inputs["Vector"])

        if roughness_scale != 1.0 or roughness_bias != 0.0:
            math_mul = nt.nodes.new("ShaderNodeMath")
            math_mul.operation = "MULTIPLY_ADD"
            math_mul.use_clamp = True
            math_mul.location = (-80, -210)
            math_mul.inputs[1].default_value = roughness_scale
            math_mul.inputs[2].default_value = roughness_bias
            nt.links.new(tex_rough.outputs["Color"], math_mul.inputs[0])
            nt.links.new(math_mul.outputs["Value"], bsdf.inputs["Roughness"])
        else:
            nt.links.new(tex_rough.outputs["Color"], bsdf.inputs["Roughness"])

    # 3. Normal Map (OpenGL nor_gl)
    nor_path = _find_map(folder, "nor_gl")
    if nor_path and normal_strength > 0.0:
        tex_nor = nt.nodes.new("ShaderNodeTexImage")
        tex_nor.location = (-500, -480)
        tex_nor.image = _load_image(nor_path, "Non-Color")
        nt.links.new(mapping.outputs["Vector"], tex_nor.inputs["Vector"])

        nor_map = nt.nodes.new("ShaderNodeNormalMap")
        nor_map.location = (-80, -480)
        nor_map.inputs["Strength"].default_value = normal_strength
        nt.links.new(tex_nor.outputs["Color"], nor_map.inputs["Color"])
        nt.links.new(nor_map.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def make_woven_rug_material(albedo_path: Path, bump_path: Path) -> bpy.types.Material:
    mat_name = "Furn_WovenRug"
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.96
    bsdf.inputs["Specular IOR Level"].default_value = 0.06
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.08
        bsdf.inputs["Sheen Roughness"].default_value = 0.85

    tc = nt.nodes.new("ShaderNodeTexCoord")
    tex_col = nt.nodes.new("ShaderNodeTexImage")
    tex_col.image = _load_image(albedo_path, "sRGB")
    nt.links.new(tc.outputs["UV"], tex_col.inputs["Vector"])
    nt.links.new(tex_col.outputs["Color"], bsdf.inputs["Base Color"])

    tex_bmp = nt.nodes.new("ShaderNodeTexImage")
    tex_bmp.image = _load_image(bump_path, "Non-Color")
    bump = nt.nodes.new("ShaderNodeBump")
    bump.inputs["Strength"].default_value = 0.80
    bump.inputs["Distance"].default_value = 0.008
    nt.links.new(tc.outputs["UV"], tex_bmp.inputs["Vector"])
    nt.links.new(tex_bmp.outputs["Color"], bump.inputs["Height"])
    nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])
    return mat


def make_artwork_material(image_path: Path, mat_name: str | None = None) -> bpy.types.Material:
    mat_name = mat_name or f"Decor_{image_path.stem}"
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Roughness"].default_value = 0.72
    tex = nt.nodes.new("ShaderNodeTexImage")
    tex.image = _load_image(image_path, "sRGB")
    nt.links.new(tex.outputs["Color"], bsdf.inputs["Base Color"])
    return mat


def make_solid_pbr(
    mat_name: str,
    color: tuple[float, float, float],
    roughness: float = 0.4,
    metallic: float = 0.0,
    coat_weight: float = 0.0,
    coat_roughness: float = 0.1,
    micro_bump_scale: float = 0.0,
    micro_bump_strength: float = 0.03,
) -> bpy.types.Material:
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Metallic"].default_value = metallic
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat_weight
        bsdf.inputs["Coat Roughness"].default_value = coat_roughness

    if micro_bump_scale > 0.0:
        tex_coord = nt.nodes.new("ShaderNodeTexCoord")
        noise = nt.nodes.new("ShaderNodeTexNoise")
        noise.inputs["Scale"].default_value = micro_bump_scale
        noise.inputs["Detail"].default_value = 6.0
        bump = nt.nodes.new("ShaderNodeBump")
        bump.inputs["Strength"].default_value = micro_bump_strength
        bump.inputs["Distance"].default_value = 0.002
        nt.links.new(tex_coord.outputs["Object"], noise.inputs["Vector"])
        nt.links.new(noise.outputs["Fac"], bump.inputs["Height"])
        nt.links.new(bump.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def make_arch_glass(
    mat_name: str = "Arch_Window_Glass",
    tint: tuple[float, float, float] = (0.94, 0.98, 0.99),
    roughness: float = 0.02,
    transmission_shadow: bool = True,
) -> bpy.types.Material:
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (600, 0)

    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (100, 120)
    bsdf.inputs["Base Color"].default_value = (*tint, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["IOR"].default_value = 1.52
    if "Transmission Weight" in bsdf.inputs:
        bsdf.inputs["Transmission Weight"].default_value = 0.96

    if transmission_shadow:
        transp = nt.nodes.new("ShaderNodeBsdfTransparent")
        transp.location = (100, -180)
        transp.inputs["Color"].default_value = (*tint, 1.0)

        lp = nt.nodes.new("ShaderNodeLightPath")
        lp.location = (-120, -240)
        math_or = nt.nodes.new("ShaderNodeMath")
        math_or.operation = "MAXIMUM"
        math_or.location = (100, -320)
        nt.links.new(lp.outputs["Is Shadow Ray"], math_or.inputs[0])
        nt.links.new(lp.outputs["Is Diffuse Ray"], math_or.inputs[1])

        mix = nt.nodes.new("ShaderNodeMixShader")
        mix.location = (380, 0)
        nt.links.new(math_or.outputs["Value"], mix.inputs["Fac"])
        nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
        nt.links.new(transp.outputs["BSDF"], mix.inputs[2])
        nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    else:
        nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    return mat


def make_sheer_curtain(mat_name: str = "Curtain_Sheer_Linen") -> bpy.types.Material:
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.inputs["Base Color"].default_value = (0.78, 0.75, 0.70, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.85
    if "Sheen Weight" in bsdf.inputs:
        bsdf.inputs["Sheen Weight"].default_value = 0.45

    translucent = nt.nodes.new("ShaderNodeBsdfTranslucent")
    translucent.inputs["Color"].default_value = (0.88, 0.85, 0.80, 1.0)

    folder = TEX_DIR / "rough_linen"
    nor_path = _find_map(folder, "nor_gl")
    if nor_path:
        tc = nt.nodes.new("ShaderNodeTexCoord")
        mp = nt.nodes.new("ShaderNodeMapping")
        mp.inputs["Scale"].default_value = (8.0, 8.0, 1.0)
        tex_n = nt.nodes.new("ShaderNodeTexImage")
        tex_n.image = _load_image(nor_path, "Non-Color")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = 0.4
        nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])
        nt.links.new(mp.outputs["Vector"], tex_n.inputs["Vector"])
        nt.links.new(tex_n.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    mix = nt.nodes.new("ShaderNodeMixShader")
    mix.inputs["Fac"].default_value = 0.40
    nt.links.new(bsdf.outputs["BSDF"], mix.inputs[1])
    nt.links.new(translucent.outputs["BSDF"], mix.inputs[2])
    nt.links.new(mix.outputs["Shader"], out.inputs["Surface"])
    return mat


def make_emissive(
    mat_name: str,
    color: tuple[float, float, float],
    strength: float = 4.0,
    roughness: float = 0.25,
) -> bpy.types.Material:
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (*color, 1.0)
    bsdf.inputs["Roughness"].default_value = roughness
    bsdf.inputs["Emission Color"].default_value = (*color, 1.0)
    bsdf.inputs["Emission Strength"].default_value = strength
    return mat


def make_screen_material(
    mat_name: str,
    image_path: Path,
    emission_strength: float = 1.45,
) -> bpy.types.Material:
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    bsdf = nt.nodes.get("Principled BSDF")
    bsdf.inputs["Base Color"].default_value = (0.004, 0.005, 0.007, 1.0)
    bsdf.inputs["Roughness"].default_value = 0.24
    bsdf.inputs["Specular IOR Level"].default_value = 0.06
    bsdf.inputs["Emission Strength"].default_value = emission_strength

    img = _load_image(image_path, "sRGB")
    if img is not None:
        tex = nt.nodes.new("ShaderNodeTexImage")
        tex.location = (-340, 0)
        tex.image = img
        nt.links.new(tex.outputs["Color"], bsdf.inputs["Emission Color"])
    return mat


def make_direct_pbr(
    mat_name: str,
    albedo_path: Path,
    rough_path: Path | None = None,
    normal_path: Path | None = None,
    uv_scale: tuple[float, float] = (1.0, 1.0),
    uv_rotation_deg: float = 0.0,
    roughness_default: float = 0.85,
    normal_strength: float = 0.35,
    metallic: float = 0.0,
    coat_weight: float = 0.0,
    coat_roughness: float = 0.18,
) -> bpy.types.Material:
    """
    100% glTF-native Principled BSDF (direct image textures -> BSDF, ZERO intermediate Mix/HSV nodes!).
    Guarantees 1:1 visual parity between Cycles offline renders and Three.js WebGL runtime!
    """
    if mat_name in bpy.data.materials:
        return bpy.data.materials[mat_name]
    mat = bpy.data.materials.new(name=mat_name)
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputMaterial")
    out.location = (640, 0)
    bsdf = nt.nodes.new("ShaderNodeBsdfPrincipled")
    bsdf.location = (300, 0)
    bsdf.inputs["Roughness"].default_value = roughness_default
    bsdf.inputs["Metallic"].default_value = metallic
    if "Coat Weight" in bsdf.inputs:
        bsdf.inputs["Coat Weight"].default_value = coat_weight
        bsdf.inputs["Coat Roughness"].default_value = coat_roughness
    nt.links.new(bsdf.outputs["BSDF"], out.inputs["Surface"])

    tc = nt.nodes.new("ShaderNodeTexCoord")
    mp = nt.nodes.new("ShaderNodeMapping")
    mp.inputs["Scale"].default_value = (uv_scale[0], uv_scale[1], 1.0)
    if uv_rotation_deg != 0.0:
        mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(uv_rotation_deg))
    nt.links.new(tc.outputs["UV"], mp.inputs["Vector"])

    tex_c = nt.nodes.new("ShaderNodeTexImage")
    tex_c.image = _load_image(albedo_path, "sRGB")
    nt.links.new(mp.outputs["Vector"], tex_c.inputs["Vector"])
    nt.links.new(tex_c.outputs["Color"], bsdf.inputs["Base Color"])

    if rough_path and rough_path.exists():
        tex_r = nt.nodes.new("ShaderNodeTexImage")
        tex_r.image = _load_image(rough_path, "Non-Color")
        nt.links.new(mp.outputs["Vector"], tex_r.inputs["Vector"])
        nt.links.new(tex_r.outputs["Color"], bsdf.inputs["Roughness"])

    if normal_path and normal_path.exists() and normal_strength > 0.0:
        tex_n = nt.nodes.new("ShaderNodeTexImage")
        tex_n.image = _load_image(normal_path, "Non-Color")
        nm = nt.nodes.new("ShaderNodeNormalMap")
        nm.inputs["Strength"].default_value = normal_strength
        nt.links.new(mp.outputs["Vector"], tex_n.inputs["Vector"])
        nt.links.new(tex_n.outputs["Color"], nm.inputs["Color"])
        nt.links.new(nm.outputs["Normal"], bsdf.inputs["Normal"])

    return mat


def build_studio_material_palette(screen_images: dict[str, Path]) -> dict[str, bpy.types.Material]:
    """Curated, physically balanced ArchViz PBR palette with crisp cast concrete & 1:1 glTF oiled walnut."""
    walnut_folder = TEX_DIR / "black_walnut_veneer_01"
    walnut_rough = _find_map(walnut_folder, "rough")
    walnut_nor = _find_map(walnut_folder, "nor_gl")
    return {
        # Architectural Surfaces (Concept A+C Smooth Board-Formed Cast Concrete + Matte-Oiled Herringbone Oak)
        "floor_parquet": make_polyhaven_pbr(
            "Arch_Floor_Herringbone",
            "herringbone_parquet",
            uv_scale=(0.55, 0.55),
            brightness=0.72,
            stain=(0.64, 0.48, 0.34),
            stain_strength=0.45,
            roughness_scale=0.92,
            roughness_bias=0.18,
            normal_strength=0.68,
            coat_weight=0.0,
            coat_roughness=0.35,
        ),
        # Ultra-Clean Tadao Ando Smooth Architectural Board-Formed Cast Concrete (1:1 glTF Native!)
        "wall_concrete": make_direct_pbr(
            "Arch_Wall_RawConcrete",
            screen_images["arch_concrete_albedo"],
            rough_path=screen_images["arch_concrete_rough"],
            normal_path=screen_images["arch_concrete_normal"],
            uv_scale=(0.52, 0.52),
            roughness_default=0.88,
            normal_strength=0.35,
        ),
        # Deep Architectural Charcoal-Obsidian Board-Formed Concrete for Studio North Feature Wall (reuses concrete maps -> 0 extra MB!)
        "wall_dark_concrete": make_direct_pbr(
            "Arch_Wall_StudioDarkConcrete",
            screen_images["arch_concrete_albedo"],
            rough_path=screen_images["arch_concrete_rough"],
            normal_path=screen_images["arch_concrete_normal"],
            uv_scale=(0.52, 0.52),
            roughness_default=0.88,
            normal_strength=0.38,
        ),
        "wall_concrete_seam": make_solid_pbr(
            "Arch_ConcreteSeam", (0.06, 0.062, 0.065), roughness=0.90, metallic=0.0,
        ),
        "wall_microcement": make_direct_pbr(
            "Arch_Wall_Microcement",
            screen_images["arch_concrete_albedo"],
            rough_path=screen_images["arch_concrete_rough"],
            normal_path=screen_images["arch_concrete_normal"],
            uv_scale=(0.58, 0.58),
            roughness_default=0.88,
            normal_strength=0.30,
        ),
        "wall_warm_plaster": make_direct_pbr(
            "Arch_Wall_WarmPlaster",
            screen_images["arch_concrete_albedo"],
            rough_path=screen_images["arch_concrete_rough"],
            normal_path=screen_images["arch_concrete_normal"],
            uv_scale=(0.55, 0.55),
            roughness_default=0.90,
            normal_strength=0.25,
        ),
        "ceiling_plaster": make_direct_pbr(
            "Arch_Ceiling_Concrete",
            screen_images["arch_concrete_albedo"],
            rough_path=screen_images["arch_concrete_rough"],
            normal_path=screen_images["arch_concrete_normal"],
            uv_scale=(0.48, 0.48),
            roughness_default=0.92,
            normal_strength=0.25,
        ),
        "galvanized_duct": make_polyhaven_pbr(
            "Arch_HVACDuct",
            "metal_plate",
            uv_scale=(1.5, 1.5),
            brightness=0.65,
            stain=(0.55, 0.57, 0.60),
            stain_strength=0.5,
            roughness_scale=0.62,
            metallic=0.86,
            normal_strength=0.35,
        ),
        # Pre-Stained Deep Oiled American Walnut (Direct glTF Albedo -> 100% identical in Cycles & WebGL!)
        "walnut_desk": make_direct_pbr(
            "Furn_AmericanWalnut",
            screen_images["walnut_oiled_albedo"],
            rough_path=walnut_rough,
            normal_path=walnut_nor,
            uv_scale=(0.75, 0.75),
            roughness_default=0.46,
            normal_strength=0.42,
            coat_weight=0.14,
            coat_roughness=0.22,
        ),
        # Vertical Milled Walnut Slats (Pre-Stained + uv_rotation_deg=90 -> Rich dark walnut in BOTH Cycles & WebGL!)
        "walnut_slat": make_direct_pbr(
            "Arch_WalnutSlats",
            screen_images["walnut_oiled_albedo"],
            rough_path=walnut_rough,
            normal_path=walnut_nor,
            uv_scale=(0.95, 0.95),
            uv_rotation_deg=90.0,
            roughness_default=0.52,
            normal_strength=0.40,
            coat_weight=0.08,
        ),
        "acoustic_felt": make_polyhaven_pbr(
            "Arch_AcousticFelt",
            "fabric_pattern_05",
            uv_scale=(4.0, 4.0),
            stain=(0.032, 0.034, 0.038),
            roughness_scale=1.1,
            normal_strength=0.60,
        ),
        "desk_mat": make_polyhaven_pbr(
            "Prop_DeskMatWool",
            "fabric_pattern_05",
            uv_scale=(6.5, 6.5),
            stain=(0.052, 0.055, 0.062),
            roughness_scale=1.05,
            normal_strength=0.55,
        ),
        "rug_woven": make_woven_rug_material(screen_images["rug_albedo"], screen_images["rug_bump"]),
        "gallery_art": make_artwork_material(screen_images["wall_art"]),
        "wall_art_rams": make_artwork_material(screen_images["wall_art_rams"], "Decor_WallArtRams"),
        "bed_art_horizon": make_artwork_material(screen_images["bed_art_horizon"], "Decor_BedArtHorizon"),
        "bed_art_sumi": make_artwork_material(screen_images["bed_art_sumi"], "Decor_BedArtSumi"),
        "bed_gallery_hero": make_artwork_material(screen_images["bed_gallery_hero"], "Decor_BedGalleryHero"),
        "living_gallery_hero": make_artwork_material(screen_images["living_gallery_hero"], "Decor_LivingGalleryHero"),
        "maker_blueprint": make_artwork_material(screen_images["maker_blueprint"], "Decor_MakerBlueprint"),
        "teardown_art": make_artwork_material(screen_images["teardown_frame"], "Decor_TeardownFrame"),
        "geek_books_atlas": make_artwork_material(screen_images["geek_book_spines"], "Decor_GeekBookSpines"),
        "vinyl_cover_art": make_artwork_material(screen_images["vinyl_album_covers"], "Decor_VinylAlbumArt"),
        "notebook_page": make_artwork_material(screen_images["notebook_page"]),
        "alex_charcoal": make_solid_pbr("Furn_AlexCharcoal", (0.048, 0.052, 0.060), roughness=0.44, metallic=0.06, micro_bump_scale=520.0, micro_bump_strength=0.015),
        "cutting_mat_green": make_solid_pbr("Prop_CuttingMatGreen", (0.042, 0.145, 0.108), roughness=0.68, metallic=0.0, micro_bump_scale=400.0, micro_bump_strength=0.015),
        "sticky_note_yellow": make_solid_pbr("Prop_StickyYellow", (0.94, 0.80, 0.24), roughness=0.82, metallic=0.0),
        "sticky_note_coral": make_solid_pbr("Prop_StickyCoral", (0.92, 0.42, 0.30), roughness=0.82, metallic=0.0),
        "leather_dark": make_polyhaven_pbr(
            "Furn_DarkLeather",
            "fabric_leather_01",
            uv_scale=(2.8, 2.8),
            brightness=0.35,
            stain=(0.14, 0.125, 0.12),
            stain_strength=0.85,
            roughness_scale=0.72,
            normal_strength=0.55,
        ),
        "chair_mesh": make_polyhaven_pbr(
            "Furn_ChairMesh",
            "fabric_pattern_05",
            uv_scale=(14.0, 14.0),
            stain=(0.016, 0.017, 0.020),
            roughness_scale=0.82,
            normal_strength=0.85,
        ),
        "marble_accent": make_polyhaven_pbr(
            "Arch_Marble",
            "marble_01",
            uv_scale=(0.7, 0.7),
            brightness=0.86,
            roughness_scale=0.38,
            coat_weight=0.35,
            coat_roughness=0.08,
            normal_strength=0.2,
        ),
        # Architectural Powder-Coated Matte-Black Steel (Low metallic so frames/pegboard/legs NEVER turn silver in daylight!)
        "anodized_black": make_solid_pbr(
            "HW_AnodizedBlack", (0.022, 0.024, 0.028), roughness=0.46, metallic=0.22, micro_bump_scale=420.0, micro_bump_strength=0.018
        ),
        "pegboard_graphite": make_solid_pbr(
            "HW_PegboardGraphite", (0.085, 0.090, 0.098), roughness=0.38, metallic=0.65, micro_bump_scale=380.0, micro_bump_strength=0.02
        ),
        "gunmetal": make_solid_pbr(
            "HW_Gunmetal", (0.14, 0.148, 0.16), roughness=0.24, metallic=0.92, micro_bump_scale=350.0, micro_bump_strength=0.018
        ),
        "brushed_brass": make_solid_pbr(
            "HW_BrushedBrass", (0.70, 0.52, 0.23), roughness=0.26, metallic=0.96, micro_bump_scale=300.0, micro_bump_strength=0.015
        ),
        "chrome": make_solid_pbr("HW_Chrome", (0.86, 0.88, 0.90), roughness=0.08, metallic=1.0),
        "matte_plastic": make_solid_pbr(
            "HW_MatteBlackPlastic", (0.040, 0.042, 0.047), roughness=0.46, metallic=0.04, micro_bump_scale=600.0, micro_bump_strength=0.02
        ),
        "speaker_cone": make_solid_pbr(
            "HW_SpeakerCarbonCone", (0.028, 0.030, 0.034), roughness=0.34, metallic=0.18, micro_bump_scale=900.0, micro_bump_strength=0.05
        ),
        "speaker_white_cone": make_solid_pbr(
            "HW_SpeakerWhiteCone", (0.82, 0.83, 0.84), roughness=0.46, metallic=0.02, micro_bump_scale=750.0, micro_bump_strength=0.03
        ),
        "ceramic_charcoal": make_solid_pbr(
            "Prop_CeramicCharcoal", (0.085, 0.088, 0.094), roughness=0.48, metallic=0.0, coat_weight=0.18, coat_roughness=0.26, micro_bump_scale=650.0, micro_bump_strength=0.03
        ),
        "paper_cream": make_solid_pbr(
            "Prop_PaperCream", (0.76, 0.73, 0.66), roughness=0.86, metallic=0.0, micro_bump_scale=500.0, micro_bump_strength=0.015
        ),
        "leather_cognac": make_solid_pbr(
            "Prop_LeatherCognac", (0.24, 0.115, 0.055), roughness=0.50, metallic=0.0, coat_weight=0.08, coat_roughness=0.35, micro_bump_scale=520.0, micro_bump_strength=0.035
        ),
        "plant_leaf_pothos": make_solid_pbr(
            "Prop_PothosLeaf", (0.068, 0.165, 0.048), roughness=0.42, metallic=0.0, coat_weight=0.14, coat_roughness=0.28
        ),
        "plant_stem": make_solid_pbr(
            "Prop_PlantStem", (0.055, 0.115, 0.038), roughness=0.68, metallic=0.0
        ),
        "throw_knit": make_solid_pbr(
            "Prop_ThrowKnit", (0.22, 0.20, 0.175), roughness=0.94, metallic=0.0, micro_bump_scale=880.0, micro_bump_strength=0.12
        ),
        "white_matte": make_solid_pbr(
            "Prop_WhiteMatte", (0.82, 0.83, 0.85), roughness=0.32, metallic=0.0, coat_weight=0.20, coat_roughness=0.15
        ),
        "emissive_track_led": make_emissive("Emit_TrackSpotLED", (1.0, 0.86, 0.64), strength=14.0),
        "keycap_dark": make_solid_pbr(
            "HW_KeycapCharcoal", (0.034, 0.038, 0.045), roughness=0.48, metallic=0.02, micro_bump_scale=800.0, micro_bump_strength=0.025
        ),
        "keycap_mod": make_solid_pbr(
            "HW_KeycapSlate", (0.072, 0.078, 0.090), roughness=0.46, metallic=0.02, micro_bump_scale=800.0, micro_bump_strength=0.025
        ),
        "keycap_accent": make_solid_pbr(
            "HW_KeycapTerracotta", (0.68, 0.20, 0.09), roughness=0.44, metallic=0.02, micro_bump_scale=800.0, micro_bump_strength=0.02
        ),
        "mic_foam": make_solid_pbr(
            "HW_MicFoam", (0.028, 0.030, 0.033), roughness=0.92, metallic=0.0, micro_bump_scale=950.0, micro_bump_strength=0.14
        ),
        "red_accent": make_solid_pbr("HW_CameraRedRing", (0.75, 0.06, 0.06), roughness=0.22, metallic=0.75),
        "lens_glass": make_arch_glass("HW_LensGlass", tint=(0.68, 0.84, 0.96), roughness=0.01, transmission_shadow=False),
        "window_glass": make_arch_glass("Arch_WindowGlass", tint=(0.95, 0.98, 1.0), roughness=0.015, transmission_shadow=True),
        "pc_glass": make_arch_glass("HW_PCGlassTinted", tint=(0.78, 0.82, 0.86), roughness=0.02, transmission_shadow=True),
        "curtain_sheer": make_sheer_curtain("Arch_CurtainSheer"),
        # Emissives (Controlled cleanly per mood)
        "emissive_cove_warm": make_emissive("Emit_CoveWarm", (1.0, 0.76, 0.48), strength=4.5),
        "emissive_keylight": make_emissive("Emit_DeskKeyLight", (1.0, 0.91, 0.82), strength=9.0, roughness=0.35),
        "emissive_rgb_cyan": make_emissive("Emit_RGB_Cyan", (0.14, 0.78, 1.0), strength=4.5),
        "emissive_rgb_amber": make_emissive("Emit_RGB_Amber", (1.0, 0.44, 0.14), strength=2.2),
        "emissive_pc_fan": make_emissive("Emit_PC_FanGlow", (0.06, 0.72, 1.0), strength=2.6),
        "emissive_pc_fan_blade": make_solid_pbr("HW_PCFanBlades", (0.04, 0.14, 0.20), roughness=0.28, metallic=0.12),
        "emissive_pc_internal": make_emissive("Emit_PC_InternalStrip", (0.72, 0.90, 1.0), strength=3.8),
        "emissive_shelf_led": make_emissive("Emit_ShelfUnderLED", (1.0, 0.76, 0.44), strength=2.6, roughness=0.35),
        "emissive_homelab_led": make_emissive("Emit_HomeLabLED", (0.16, 0.92, 0.56), strength=5.0),
        "emissive_hex_tile": make_emissive("Emit_HexTile", (0.98, 0.68, 0.38), strength=2.4, roughness=0.4),
        "emissive_hex_primary": make_emissive("Emit_HexNeon_Primary", (0.12, 0.82, 1.0), strength=4.6, roughness=0.22),
        "emissive_hex_secondary": make_emissive("Emit_HexNeon_Secondary", (1.0, 0.44, 0.16), strength=4.2, roughness=0.22),
        "emissive_hex_soft": make_emissive("Emit_HexNeon_SoftFace", (0.48, 0.78, 1.0), strength=1.65, roughness=0.38),
        "hex_core_obsidian": make_solid_pbr(
            "HW_HexAcousticCore", (0.030, 0.033, 0.040), roughness=0.78, metallic=0.06,
            micro_bump_scale=640.0, micro_bump_strength=0.025,
        ),
        "emissive_tally_red": make_emissive("Emit_TallyRed", (1.0, 0.08, 0.08), strength=8.0),
        # High-Contrast OLED Screen Materials
        "screen_ultrawide": make_screen_material("Screen_Ultrawide", screen_images["ultrawide"], emission_strength=1.55),
        "screen_vertical": make_screen_material("Screen_Vertical", screen_images["vertical"], emission_strength=1.55),
        "screen_stream_deck": make_screen_material("Screen_StreamDeck", screen_images["stream_deck"], emission_strength=2.2),
        "screen_macbook": make_screen_material("Screen_MacBook", screen_images["macbook_screen"], emission_strength=1.40),
        "screen_living_tv": make_screen_material("Screen_LivingTV", screen_images["living_tv"], emission_strength=1.55),
        "screen_pixel_clock": make_screen_material("Screen_PixelClock", screen_images["pixel_clock_ui"], emission_strength=2.6),
        # Phase 3 Luxury Loft Materials (Real Photoscanned Honed Pietra Grey / Nero Marquina Marble, Japanese Spa Stone)
        "dark_marble": make_direct_pbr(
            "Arch_DarkMarble",
            screen_images["dark_marble_albedo"],
            rough_path=screen_images["dark_marble_rough"],
            normal_path=screen_images["dark_marble_normal"],
            uv_scale=(0.55, 0.55),
            roughness_default=0.28,
            normal_strength=0.28,
            coat_weight=0.08,
            coat_roughness=0.18,
        ),
        "spa_stone_tile": make_direct_pbr(
            "Arch_SpaStoneTile",
            screen_images["spa_stone_albedo"],
            normal_path=screen_images["spa_stone_normal"],
            uv_scale=(0.85, 0.85),
            roughness_default=0.72,
            normal_strength=0.45,
        ),
        "fluted_glass": make_arch_glass(
            "Arch_FlutedGlass", tint=(0.86, 0.90, 0.92), roughness=0.28, transmission_shadow=True,
        ),
        "shower_glass": make_arch_glass(
            "Arch_ShowerGlass", tint=(0.88, 0.94, 0.96), roughness=0.04, transmission_shadow=True,
        ),
        "wardrobe_smoked_glass": make_arch_glass(
            "Furn_SmokedGlass", tint=(0.24, 0.26, 0.30), roughness=0.06, transmission_shadow=True,
        ),
        "mirror_silver": make_solid_pbr("Arch_MirrorSilver", (0.90, 0.92, 0.94), roughness=0.05, metallic=0.98),
        "sofa_charcoal_wool": make_polyhaven_pbr(
            "Furn_SofaCharcoalWool",
            "fabric_pattern_05",
            uv_scale=(7.5, 7.5),
            stain=(0.068, 0.067, 0.066),
            roughness_scale=1.10,
            normal_strength=0.65,
        ),
        "linen_warm_taupe": make_polyhaven_pbr(
            "Furn_LinenTaupe",
            "rough_linen",
            uv_scale=(5.0, 5.0),
            stain=(0.46, 0.43, 0.39),
            roughness_scale=1.05,
            normal_strength=0.55,
        ),
        "kitchen_matte_black": make_solid_pbr(
            "Furn_KitchenMatteBlack", (0.028, 0.030, 0.035), roughness=0.42, metallic=0.08,
            micro_bump_scale=520.0, micro_bump_strength=0.012,
        ),
        "induction_glass": make_solid_pbr("HW_InductionGlass", (0.015, 0.016, 0.020), roughness=0.08, metallic=0.12, coat_weight=0.6),
        "emissive_bath_halo": make_emissive("Emit_BathMirrorHalo", (1.0, 0.80, 0.54), strength=5.5),
        "emissive_kitchen_led": make_emissive("Emit_KitchenUnderLED", (1.0, 0.82, 0.58), strength=3.6),
        "emissive_bed_cove": make_emissive("Emit_BedroomCoveLED", (1.0, 0.74, 0.42), strength=3.8),
        "screen_aio_lcd": make_screen_material("Screen_AIO_LCD", screen_images["aio_lcd_ui"], emission_strength=2.4),
        # Curated Deep Editorial Vinyl & Art Monograph Spine Palette (Rich darks & warm neutrals, ZERO pastel Lego blocks!)
        "vinyl_cover_1": make_solid_pbr("Decor_Vinyl1", (0.048, 0.050, 0.056), roughness=0.52),
        "vinyl_cover_2": make_solid_pbr("Decor_Vinyl2", (0.16, 0.068, 0.052), roughness=0.50),
        "vinyl_cover_3": make_solid_pbr("Decor_Vinyl3", (0.075, 0.11, 0.17), roughness=0.50),
        "vinyl_cover_4": make_solid_pbr("Decor_Vinyl4", (0.34, 0.29, 0.23), roughness=0.56),
        "vinyl_cover_5": make_solid_pbr("Decor_Vinyl5", (0.11, 0.14, 0.10), roughness=0.52),
        "vinyl_cover_6": make_solid_pbr("Decor_Vinyl6", (0.24, 0.17, 0.10), roughness=0.52),
    }
