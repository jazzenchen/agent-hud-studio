"""
Cycles Metal GPU + Multi-Mood Concept A+C Industrial Geek Loft Lighting Presets
(Daylight / Golden Hour / Midnight Stream) with synchronized photorealistic City Skyline Cyclorama!
"""

import math
from pathlib import Path
import bpy

from config import CACHE_DIR, HDRI_DIR

SKY_DIR = CACHE_DIR / "sky"


def configure_cycles_metal(samples: int = 96, res_x: int = 1600, res_y: int = 900) -> None:
    scene = bpy.context.scene
    scene.render.engine = "CYCLES"
    scene.cycles.device = "GPU"

    prefs = bpy.context.preferences.addons["cycles"].preferences
    prefs.compute_device_type = "METAL"
    prefs.refresh_devices()
    for d in prefs.devices:
        d.use = d.type == "METAL"

    scene.cycles.samples = samples
    scene.cycles.use_adaptive_sampling = True
    scene.cycles.adaptive_threshold = 0.015
    scene.cycles.use_denoising = True
    scene.cycles.denoiser = "OPENIMAGEDENOISE"
    scene.cycles.denoising_input_passes = "RGB_ALBEDO_NORMAL"
    scene.cycles.max_bounces = 8
    scene.cycles.diffuse_bounces = 4
    scene.cycles.glossy_bounces = 4
    scene.cycles.transmission_bounces = 6
    scene.cycles.transparent_max_bounces = 32
    scene.cycles.sample_clamp_indirect = 8.0

    scene.render.resolution_x = res_x
    scene.render.resolution_y = res_y
    scene.render.resolution_percentage = 100
    scene.render.image_settings.file_format = "PNG"
    scene.render.image_settings.color_mode = "RGBA"

    # Cinema-grade AgX Color Management
    scene.view_settings.view_transform = "AgX"
    try:
        scene.view_settings.look = "AgX - Medium High Contrast"
    except Exception:
        try:
            scene.view_settings.look = "Medium High Contrast"
        except Exception:
            scene.view_settings.look = "None"
    scene.view_settings.exposure = 0.0


def _ensure_light(
    name: str,
    light_type: str,
    col: bpy.types.Collection,
    location: tuple[float, float, float],
    rotation_deg: tuple[float, float, float],
    energy: float,
    color: tuple[float, float, float],
    size: float = 0.3,
    size_y: float | None = None,
    spread_deg: float | None = None,
    angle_deg: float = 1.4,
    spot_size_deg: float = 44.0,
    spot_blend: float = 0.68,
) -> bpy.types.Object:
    if name in bpy.data.objects:
        obj = bpy.data.objects[name]
        ldata = obj.data
    else:
        ldata = bpy.data.lights.new(name=name, type=light_type)
        obj = bpy.data.objects.new(name=name, object_data=ldata)
        col.objects.link(obj)

    obj.location = location
    obj.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    ldata.energy = energy
    ldata.color = color
    if light_type == "AREA":
        if size_y is not None:
            ldata.shape = "RECTANGLE"
            ldata.size = size
            ldata.size_y = size_y
        else:
            ldata.shape = "DISK"
            ldata.size = size
        if spread_deg is not None and hasattr(ldata, "spread"):
            ldata.spread = math.radians(spread_deg)
    elif light_type == "SPOT":
        ldata.shadow_soft_size = size
        ldata.spot_size = math.radians(spot_size_deg)
        ldata.spot_blend = spot_blend
    elif light_type == "SUN":
        ldata.angle = math.radians(angle_deg)
    elif light_type == "POINT":
        ldata.shadow_soft_size = size
        # Never show floating white/orange light-sphere orbs inside glass enclosures!
        obj.visible_camera = False
        obj.visible_glossy = False
        obj.visible_transmission = False
    return obj


def _set_world_hdri(hdri_filename: str, strength: float, rot_z_deg: float) -> None:
    scene = bpy.context.scene
    if scene.world is None:
        scene.world = bpy.data.worlds.new("ArchViz_World")
    world = scene.world
    world.use_nodes = True
    nt = world.node_tree
    nt.nodes.clear()

    out = nt.nodes.new("ShaderNodeOutputWorld")
    bg = nt.nodes.new("ShaderNodeBackground")
    bg.inputs["Strength"].default_value = strength
    env = nt.nodes.new("ShaderNodeTexEnvironment")
    mp = nt.nodes.new("ShaderNodeMapping")
    tc = nt.nodes.new("ShaderNodeTexCoord")

    mp.inputs["Rotation"].default_value = (0.0, 0.0, math.radians(rot_z_deg))
    hdri_path = HDRI_DIR / hdri_filename
    if hdri_path.exists():
        env.image = bpy.data.images.load(str(hdri_path), check_existing=True)

    nt.links.new(tc.outputs["Generated"], mp.inputs["Vector"])
    nt.links.new(mp.outputs["Vector"], env.inputs["Vector"])
    nt.links.new(env.outputs["Color"], bg.inputs["Color"])
    nt.links.new(bg.outputs["Background"], out.inputs["Surface"])


def _set_skyline_backdrop(image_name: str, emission_strength: float) -> None:
    """Update the curved exterior City Skyline Cyclorama image & luminance per mood."""
    mat = bpy.data.materials.get("Arch_CitySkylineMat")
    if not mat or not mat.use_nodes:
        return
    img_path = SKY_DIR / image_name
    if not img_path.exists():
        return
    nt = mat.node_tree
    for n in nt.nodes:
        if n.type == "TEX_IMAGE":
            img = bpy.data.images.load(str(img_path), check_existing=True)
            img.colorspace_settings.name = "sRGB"
            n.image = img
        elif n.type == "EMISSION":
            n.inputs["Strength"].default_value = emission_strength


def _set_emissive_strength(mat_name: str, strength: float) -> None:
    mat = bpy.data.materials.get(mat_name)
    if not mat or not mat.use_nodes:
        return
    bsdf = mat.node_tree.nodes.get("Principled BSDF")
    if bsdf and "Emission Strength" in bsdf.inputs:
        bsdf.inputs["Emission Strength"].default_value = strength


def apply_studio_mood(mood: str, light_col: bpy.types.Collection) -> None:
    """
    Concept A v4 Lighting Presets (4.36m x 4.00m x 2.76m tight cozy studio loft):
    - West Steel-Grid Window at X = -2.18 with curved City Skyline Cyclorama outside
    - 3 sculpted gallery ceiling track spotlights aligned directly under the 3 visible track cans (Z = 2.60)
    - Midnight emphasizes RICH WARM AMBER-GOLD (2950K) concrete light cones + desk halo vs localized deep cobalt window twilight!
    """
    assert mood in ("daylight", "noon", "golden", "midnight")

    if mood == "noon":
        # High-Noon (~12:30 PM Tokyo Clear Summer Sky): steep ~60 deg blazing pure-white zenith sun + bright blue-sky bounce!
        _set_world_hdri("aristea_wreck_puresky_2k.hdr", strength=1.95, rot_z_deg=185.0)
        _set_skyline_backdrop("skyline_daylight.jpg", emission_strength=2.6)
        bpy.context.scene.view_settings.exposure = 0.08

        _ensure_light(
            "Light_Sun", "SUN", light_col,
            location=(-4.0, -0.6, 5.5), rotation_deg=(8.0, -32.0, 0.0),
            energy=12.5, color=(1.0, 0.995, 0.985), angle_deg=0.65,
        )
        _ensure_light(
            "Light_WestWindowPortal", "AREA", light_col,
            location=(-2.06, 0.04, 1.40), rotation_deg=(0.0, -90.0, 0.0),
            energy=340.0, color=(0.88, 0.95, 1.0), size=2.4, size_y=3.5, spread_deg=128.0,
        )
        _ensure_light("Light_TrackSpot_L", "SPOT", light_col, (-1.15, 1.08, 2.60), (34.0, 0.0, -4.0), 10.0, (1.0, 0.94, 0.86), size=0.18, spot_size_deg=96.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_C", "SPOT", light_col, (-0.06, 1.08, 2.60), (34.0, 0.0, 0.0), 12.0, (1.0, 0.94, 0.86), size=0.18, spot_size_deg=98.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_R", "SPOT", light_col, (1.03, 1.08, 2.60), (34.0, 0.0, 8.0), 10.0, (1.0, 0.94, 0.86), size=0.18, spot_size_deg=96.0, spot_blend=1.0)
        _ensure_light("Light_ShelfSpot", "SPOT", light_col, (1.18, 0.90, 2.60), (0.0, -32.0, 0.0), 12.0, (1.0, 0.92, 0.82), size=0.14, spot_size_deg=76.0, spot_blend=0.95)
        _ensure_light("Light_MakerBenchSpot", "SPOT", light_col, (1.08, -0.74, 2.60), (0.0, -34.0, 0.0), 14.0, (1.0, 0.92, 0.84), size=0.14, spot_size_deg=76.0, spot_blend=0.95)
        _ensure_light("Light_HexNeonWash_L", "AREA", light_col, (-0.42, 1.93, 1.96), (-90.0, 0.0, 0.0), 3.0, (0.14, 0.82, 1.0), size=0.68, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_HexNeonWash_R", "AREA", light_col, (0.28, 1.93, 2.02), (-90.0, 0.0, 0.0), 2.5, (1.0, 0.46, 0.18), size=0.62, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_MakerShelfWash", "AREA", light_col, (2.08, -0.74, 1.63), (0.0, -12.0, 0.0), 4.0, (1.0, 0.86, 0.66), size=0.06, size_y=1.10, spread_deg=118.0)

        _ensure_light("Light_ScreenBar", "AREA", light_col, (-0.30, 1.62, 1.32), (24.0, 0.0, 0.0), 3.0, (1.0, 0.92, 0.80), size=0.46, size_y=0.04, spread_deg=70.0)
        _ensure_light("Light_DeskBiasHalo", "AREA", light_col, (-0.28, 1.84, 1.12), (-90.0, 0.0, 0.0), 3.0, (1.0, 0.78, 0.52), size=0.85, size_y=0.14, spread_deg=115.0)
        _ensure_light("Light_FloorLamp", "SPOT", light_col, (-1.60, 1.46, 1.40), (65.0, 0.0, -62.0), 0.0, (1.0, 0.84, 0.62), size=0.08, spot_size_deg=68.0, spot_blend=0.85)
        _ensure_light("Light_PCGlow", "POINT", light_col, (0.82, 1.38, 0.28), (0.0, 0.0, 0.0), 5.0, (0.12, 0.86, 1.0), size=0.10)
        _ensure_light("Light_PCWarm", "POINT", light_col, (0.86, 1.44, 0.18), (0.0, 0.0, 0.0), 2.0, (1.0, 0.48, 0.16), size=0.08)

        _set_emissive_strength("Emit_CoveWarm", 0.6)
        _set_emissive_strength("Emit_TrackSpotLED", 2.0)
        _set_emissive_strength("Emit_DeskKeyLight", 0.5)
        _set_emissive_strength("Emit_ShelfUnderLED", 0.4)
        _set_emissive_strength("Emit_RGB_Cyan", 1.8)
        _set_emissive_strength("Emit_RGB_Amber", 1.4)
        _set_emissive_strength("Emit_PC_FanGlow", 1.8)
        _set_emissive_strength("Screen_Ultrawide", 1.80)
        _set_emissive_strength("Screen_Vertical", 1.80)
        _set_emissive_strength("Screen_StreamDeck", 1.8)

    elif mood == "daylight":
        _set_world_hdri("aristea_wreck_puresky_2k.hdr", strength=1.45, rot_z_deg=210.0)
        _set_skyline_backdrop("skyline_daylight.jpg", emission_strength=2.2)
        bpy.context.scene.view_settings.exposure = 0.05

        _ensure_light(
            "Light_Sun", "SUN", light_col,
            location=(-5.0, -1.5, 4.5), rotation_deg=(18.0, -54.0, 0.0),
            energy=7.2, color=(1.0, 0.97, 0.92), angle_deg=0.95,
        )
        _ensure_light(
            "Light_WestWindowPortal", "AREA", light_col,
            location=(-2.06, 0.04, 1.40), rotation_deg=(0.0, -90.0, 0.0),
            energy=210.0, color=(0.88, 0.95, 1.0), size=2.4, size_y=3.5, spread_deg=122.0,
        )
        _ensure_light("Light_TrackSpot_L", "SPOT", light_col, (-1.15, 1.08, 2.60), (34.0, 0.0, -4.0), 18.0, (1.0, 0.90, 0.76), size=0.18, spot_size_deg=96.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_C", "SPOT", light_col, (-0.06, 1.08, 2.60), (34.0, 0.0, 0.0), 24.0, (1.0, 0.90, 0.76), size=0.18, spot_size_deg=98.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_R", "SPOT", light_col, (1.03, 1.08, 2.60), (34.0, 0.0, 8.0), 20.0, (1.0, 0.90, 0.76), size=0.18, spot_size_deg=96.0, spot_blend=1.0)
        _ensure_light("Light_ShelfSpot", "SPOT", light_col, (1.18, 0.90, 2.60), (0.0, -32.0, 0.0), 22.0, (1.0, 0.88, 0.72), size=0.14, spot_size_deg=76.0, spot_blend=0.95)
        _ensure_light("Light_MakerBenchSpot", "SPOT", light_col, (1.08, -0.74, 2.60), (0.0, -34.0, 0.0), 24.0, (1.0, 0.88, 0.74), size=0.14, spot_size_deg=76.0, spot_blend=0.95)
        _ensure_light("Light_HexNeonWash_L", "AREA", light_col, (-0.42, 1.93, 1.96), (-90.0, 0.0, 0.0), 6.0, (0.14, 0.82, 1.0), size=0.68, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_HexNeonWash_R", "AREA", light_col, (0.28, 1.93, 2.02), (-90.0, 0.0, 0.0), 5.0, (1.0, 0.46, 0.18), size=0.62, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_MakerShelfWash", "AREA", light_col, (2.08, -0.74, 1.63), (0.0, -12.0, 0.0), 8.0, (1.0, 0.82, 0.56), size=0.06, size_y=1.10, spread_deg=118.0)

        _ensure_light("Light_ScreenBar", "AREA", light_col, (-0.30, 1.62, 1.32), (24.0, 0.0, 0.0), 8.0, (1.0, 0.88, 0.72), size=0.46, size_y=0.04, spread_deg=70.0)
        _ensure_light("Light_DeskBiasHalo", "AREA", light_col, (-0.28, 1.84, 1.12), (-90.0, 0.0, 0.0), 8.0, (1.0, 0.72, 0.42), size=0.85, size_y=0.14, spread_deg=115.0)
        _ensure_light("Light_FloorLamp", "SPOT", light_col, (-1.60, 1.46, 1.40), (65.0, 0.0, -62.0), 0.0, (1.0, 0.84, 0.62), size=0.08, spot_size_deg=68.0, spot_blend=0.85)
        _ensure_light("Light_PCGlow", "POINT", light_col, (0.82, 1.38, 0.28), (0.0, 0.0, 0.0), 10.0, (0.12, 0.86, 1.0), size=0.10)
        _ensure_light("Light_PCWarm", "POINT", light_col, (0.86, 1.44, 0.18), (0.0, 0.0, 0.0), 4.0, (1.0, 0.48, 0.16), size=0.08)

        _set_emissive_strength("Emit_CoveWarm", 1.2)
        _set_emissive_strength("Emit_TrackSpotLED", 4.0)
        _set_emissive_strength("Emit_DeskKeyLight", 0.9)
        _set_emissive_strength("Emit_ShelfUnderLED", 0.8)
        _set_emissive_strength("Emit_RGB_Cyan", 2.4)
        _set_emissive_strength("Emit_RGB_Amber", 1.8)
        _set_emissive_strength("Emit_PC_FanGlow", 2.2)
        _set_emissive_strength("Screen_Ultrawide", 1.70)
        _set_emissive_strength("Screen_Vertical", 1.70)
        _set_emissive_strength("Screen_StreamDeck", 1.8)

    elif mood == "golden":
        _set_world_hdri("belfast_sunset_puresky_2k.hdr", strength=1.15, rot_z_deg=155.0)
        _set_skyline_backdrop("skyline_golden.jpg", emission_strength=2.1)
        bpy.context.scene.view_settings.exposure = 0.06

        # Crisp low-angle Golden Sun raking through the upper Venetian blinds to cast architectural stripes!
        _ensure_light(
            "Light_Sun", "SUN", light_col,
            location=(-5.0, -2.0, 2.0), rotation_deg=(16.0, -68.0, 0.0),
            energy=7.6, color=(1.0, 0.56, 0.24), angle_deg=0.85,
        )
        _ensure_light(
            "Light_WestWindowPortal", "AREA", light_col,
            location=(-2.06, 0.04, 1.40), rotation_deg=(0.0, -90.0, 0.0),
            energy=96.0, color=(1.0, 0.70, 0.42), size=2.4, size_y=3.5, spread_deg=118.0,
        )
        _ensure_light("Light_TrackSpot_L", "SPOT", light_col, (-1.15, 1.08, 2.60), (34.0, 0.0, -4.0), 54.0, (1.0, 0.78, 0.50), size=0.20, spot_size_deg=102.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_C", "SPOT", light_col, (-0.06, 1.08, 2.60), (34.0, 0.0, 0.0), 76.0, (1.0, 0.78, 0.50), size=0.20, spot_size_deg=104.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_R", "SPOT", light_col, (1.03, 1.08, 2.60), (34.0, 0.0, 8.0), 60.0, (1.0, 0.78, 0.50), size=0.20, spot_size_deg=102.0, spot_blend=1.0)
        _ensure_light("Light_ShelfSpot", "SPOT", light_col, (1.18, 0.90, 2.60), (0.0, -32.0, 0.0), 54.0, (1.0, 0.76, 0.46), size=0.14, spot_size_deg=78.0, spot_blend=0.95)
        _ensure_light("Light_MakerBenchSpot", "SPOT", light_col, (1.08, -0.74, 2.60), (0.0, -34.0, 0.0), 52.0, (1.0, 0.78, 0.48), size=0.14, spot_size_deg=78.0, spot_blend=0.95)
        _ensure_light("Light_HexNeonWash_L", "AREA", light_col, (-0.42, 1.93, 1.96), (-90.0, 0.0, 0.0), 16.0, (0.14, 0.82, 1.0), size=0.68, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_HexNeonWash_R", "AREA", light_col, (0.28, 1.93, 2.02), (-90.0, 0.0, 0.0), 15.0, (1.0, 0.46, 0.18), size=0.62, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_MakerShelfWash", "AREA", light_col, (2.08, -0.74, 1.63), (0.0, -12.0, 0.0), 18.0, (1.0, 0.76, 0.44), size=0.06, size_y=1.10, spread_deg=118.0)

        _ensure_light("Light_ScreenBar", "AREA", light_col, (-0.30, 1.62, 1.32), (24.0, 0.0, 0.0), 18.0, (1.0, 0.84, 0.60), size=0.46, size_y=0.04, spread_deg=68.0)
        _ensure_light("Light_DeskBiasHalo", "AREA", light_col, (-0.28, 1.84, 1.12), (-90.0, 0.0, 0.0), 34.0, (1.0, 0.68, 0.34), size=0.88, size_y=0.14, spread_deg=115.0)
        _ensure_light("Light_FloorLamp", "SPOT", light_col, (-1.60, 1.46, 1.40), (65.0, 0.0, -62.0), 22.0, (1.0, 0.80, 0.52), size=0.08, spot_size_deg=68.0, spot_blend=0.85)
        _ensure_light("Light_PCGlow", "POINT", light_col, (0.82, 1.38, 0.28), (0.0, 0.0, 0.0), 14.0, (0.12, 0.86, 1.0), size=0.10)
        _ensure_light("Light_PCWarm", "POINT", light_col, (0.86, 1.44, 0.18), (0.0, 0.0, 0.0), 6.0, (1.0, 0.48, 0.16), size=0.08)

        _set_emissive_strength("Emit_CoveWarm", 4.0)
        _set_emissive_strength("Emit_TrackSpotLED", 10.0)
        _set_emissive_strength("Emit_DeskKeyLight", 2.0)
        _set_emissive_strength("Emit_ShelfUnderLED", 2.2)
        _set_emissive_strength("Emit_RGB_Cyan", 3.2)
        _set_emissive_strength("Emit_RGB_Amber", 2.8)
        _set_emissive_strength("Emit_PC_FanGlow", 2.8)
        _set_emissive_strength("Screen_Ultrawide", 1.65)
        _set_emissive_strength("Screen_Vertical", 1.65)
        _set_emissive_strength("Screen_StreamDeck", 2.2)

    else:  # midnight — EXACT CONCEPT A: Warm 2950K Concrete Track Cones + Golden Monitor Halo vs Localized Cobalt Window Twilight!
        _set_world_hdri("blue_lagoon_night_2k.hdr", strength=0.18, rot_z_deg=250.0)
        _set_skyline_backdrop("skyline_midnight.jpg", emission_strength=2.05)
        bpy.context.scene.view_settings.exposure = 0.20

        # Subtle cool twilight moon-rim grazing the West window mullions & Venetian blinds (never turns wall blue!)
        _ensure_light(
            "Light_Sun", "SUN", light_col,
            location=(-5.0, -1.0, 3.0), rotation_deg=(16.0, -56.0, 0.0),
            energy=0.22, color=(0.18, 0.46, 1.0), angle_deg=4.5,
        )
        # Tight localized cobalt twilight spill at West window (42W, 95° spread -> keeps concrete center warm golden!)
        _ensure_light(
            "Light_WestWindowPortal", "AREA", light_col,
            location=(-2.08, 0.04, 1.40), rotation_deg=(0.0, -90.0, 0.0),
            energy=42.0, color=(0.14, 0.44, 1.0), size=2.3, size_y=3.4, spread_deg=95.0,
        )
        # Silky Feathered Warm 2950K Architectural Gallery Track Wash (ZERO harsh black spotlight arcs!)
        _ensure_light("Light_TrackSpot_L", "SPOT", light_col, (-1.15, 1.08, 2.60), (36.0, 0.0, -4.0), 135.0, (1.0, 0.82, 0.56), size=0.22, spot_size_deg=106.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_C", "SPOT", light_col, (-0.06, 1.08, 2.60), (36.0, 0.0, 0.0), 155.0, (1.0, 0.83, 0.58), size=0.22, spot_size_deg=108.0, spot_blend=1.0)
        _ensure_light("Light_TrackSpot_R", "SPOT", light_col, (1.03, 1.08, 2.60), (36.0, 0.0, 8.0), 140.0, (1.0, 0.82, 0.56), size=0.22, spot_size_deg=106.0, spot_blend=1.0)
        # Warm architectural accents grazing the Geek Bookshelf & East Maker 3D Printer Workbench (rot_y=-34 aims +X toward East wall!)
        _ensure_light("Light_ShelfSpot", "SPOT", light_col, (1.18, 0.90, 2.60), (0.0, -34.0, 0.0), 105.0, (1.0, 0.80, 0.52), size=0.16, spot_size_deg=82.0, spot_blend=0.98)
        _ensure_light("Light_MakerBenchSpot", "SPOT", light_col, (1.08, -0.74, 2.58), (0.0, -34.0, 0.0), 115.0, (1.0, 0.82, 0.56), size=0.18, spot_size_deg=84.0, spot_blend=0.98)
        # Soft Dual-Tone Honeycomb Neon Wall-Grazing Glows onto the Deep Charcoal Concrete Back Wall!
        _ensure_light("Light_HexNeonWash_L", "AREA", light_col, (-0.42, 1.93, 1.96), (-90.0, 0.0, 0.0), 24.0, (0.14, 0.82, 1.0), size=0.68, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_HexNeonWash_R", "AREA", light_col, (0.28, 1.93, 2.02), (-90.0, 0.0, 0.0), 22.0, (1.0, 0.46, 0.18), size=0.62, size_y=0.44, spread_deg=115.0)
        _ensure_light("Light_MakerShelfWash", "AREA", light_col, (2.08, -0.74, 1.63), (0.0, -12.0, 0.0), 26.0, (1.0, 0.76, 0.44), size=0.06, size_y=1.10, spread_deg=118.0)

        # Warm BenQ ScreenBar asymmetric desk pool + rich warm amber monitor wall-bias halo + cinema barn-door key fill!
        _ensure_light("Light_ScreenBar", "AREA", light_col, (-0.30, 1.62, 1.34), (24.0, 0.0, 0.0), 26.0, (1.0, 0.83, 0.58), size=0.46, size_y=0.04, spread_deg=64.0)
        _ensure_light("Light_DeskBiasHalo", "AREA", light_col, (-0.28, 1.84, 1.14), (-90.0, 0.0, 0.0), 62.0, (1.0, 0.68, 0.36), size=0.92, size_y=0.14, spread_deg=118.0)
        _ensure_light("Light_FloorLamp", "SPOT", light_col, (-1.60, 1.46, 1.40), (65.0, 0.0, -62.0), 36.0, (1.0, 0.82, 0.58), size=0.08, spot_size_deg=68.0, spot_blend=0.88)
        # Controlled Localized Cyan-Teal + Warm Amber PC Tower interior & floor glow (square-aligned at x=0.86!)
        _ensure_light("Light_PCGlow", "POINT", light_col, (0.82, 1.38, 0.28), (0.0, 0.0, 0.0), 9.0, (0.08, 0.84, 1.0), size=0.09)
        _ensure_light("Light_PCWarm", "POINT", light_col, (0.86, 1.44, 0.18), (0.0, 0.0, 0.0), 3.8, (1.0, 0.50, 0.16), size=0.07)

        _set_emissive_strength("Emit_CoveWarm", 5.2)
        _set_emissive_strength("Emit_TrackSpotLED", 15.0)
        _set_emissive_strength("Emit_DeskKeyLight", 3.2)
        _set_emissive_strength("Emit_ShelfUnderLED", 2.8)
        _set_emissive_strength("Emit_RGB_Cyan", 2.6)
        _set_emissive_strength("Emit_RGB_Amber", 2.4)
        _set_emissive_strength("Emit_PC_FanGlow", 2.6)
        _set_emissive_strength("Screen_Ultrawide", 1.72)
        _set_emissive_strength("Screen_Vertical", 1.72)
        _set_emissive_strength("Screen_StreamDeck", 2.4)
