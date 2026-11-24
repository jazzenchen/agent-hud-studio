"""
Central configuration for the Geek Loft ArchViz Blender -> Three.js pipeline.
All physical units are in meters (Blender Z-up -> glTF exports cleanly to Three.js Y-up).
"""

from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
CACHE_DIR = ROOT_DIR / "assets" / "cache"
TEX_DIR = CACHE_DIR / "textures"
HDRI_DIR = CACHE_DIR / "hdris"
MODEL_DIR = CACHE_DIR / "models"
CUSTOM_HERO_DIR = ROOT_DIR / "assets" / "custom_hero"
BLEND_DIR = ROOT_DIR / "assets" / "blend"
RENDER_DIR = ROOT_DIR / "renders"
PUBLIC_ASSETS_DIR = ROOT_DIR / "public" / "assets"

# Verified Poly Haven CC0 PBR Textures (2K JPG for crispness + fast GPU loading)
POLYHAVEN_TEXTURES = {
    "herringbone_parquet": "2k",
    "american_walnut_veneer": "2k",
    "black_walnut_veneer_01": "2k",
    "natural_walnut_veneer": "2k",
    "plaster_grey_04": "2k",
    "clay_plaster": "2k",
    "brushed_concrete_03": "2k",
    "marble_01": "2k",
    "rough_linen": "2k",
    "fabric_leather_01": "2k",
    "fabric_pattern_05": "2k",
    "metal_plate": "2k",
}

# Verified Poly Haven CC0 HDRIs (2K .hdr for Cycles GI & Three.js PMREM)
POLYHAVEN_HDRIS = {
    "aristea_wreck_puresky": "2k",   # Crisp clear daylight
    "belfast_sunset_puresky": "2k",  # Golden hour warm low sun
    "blue_lagoon_night": "2k",       # Deep cinematic twilight/night
}

# Verified Poly Haven CC0 3D Models (Phase 1 Studio Slice + Phase 3 Full Loft)
POLYHAVEN_MODELS_PHASE1 = {
    "modern_arm_chair_01": "2k",
    "desk_lamp_arm_01": "2k",
    "potted_plant_01": "2k",
    "potted_plant_04": "2k",
    "calathea_orbifolia_01": "2k",
    "book_encyclopedia_set_01": "2k",
    "office_notepads": "2k",
    "ceramic_vase_01": "2k",
    "ceramic_vase_02": "2k",
    "hanging_picture_frame_01": "2k",
    "standing_picture_frame_01": "2k",
    "rubber_duck_toy": "2k",
    "wooden_display_shelves_01": "2k",
    "modern_wooden_cabinet": "2k",
}

POLYHAVEN_MODELS_PHASE3 = {
    "sofa_02": "2k",
    "mid_century_lounge_chair": "2k",
    "Ottoman_01": "2k",
    "throw_pillows_01": "2k",
    "modern_coffee_table_01": "2k",
    "gaming_console": "2k",
    "gamepad": "2k",
    "bar_chair_round_01": "2k",
    "modern_ceiling_lamp_01": "2k",
    "pachira_aquatica_01": "2k",
    "wooden_cutting_board": "2k",
    "side_table_01": "2k",
}

# Studio Vertical Slice Dimensions (Meters, Blender Z-up: X=East, Y=North, Z=Up)
# Note: glTF exporter automatically converts Blender (X, Y, Z) -> Three.js (X, Z, -Y)
# So in Blender:
#   +Y is North (Desk Feature Wall at Y = +2.25)
#   -Y is South (Panoramic Curtain-Wall Window at Y = -2.25)
#   -X is West (Exterior/Acoustic Accent Wall at X = -2.6)
#   +X is East (Open/Glass Partition Side at X = +2.6)
STUDIO_SLICE = {
    "x_min": -2.60,
    "x_max": 2.60,
    "y_min": -2.25,   # South panoramic window wall
    "y_max": 2.25,    # North battlestation feature wall
    "height": 3.10,
    "wall_thickness": 0.22,
}

# RGBM Lightmap encoding range (max HDR irradiance stored cleanly in 8-bit RGBA PNG)
RGBM_MAX_RANGE = 8.0
LIGHTMAP_RESOLUTION = 2048
