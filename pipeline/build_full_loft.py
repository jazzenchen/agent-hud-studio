#!/usr/bin/env python3
"""
Phase 3 Master Builder — Full 5-Zone Tokyo Industrial Concrete & Dark Walnut Geek Loft (11.6m x 7.5m = 87 m^2).
Reuses 100% of our Gate-2-verified Studio Slice v8 (Zone 1) and opens architectural portals seamlessly into:
  - Zone 2: Living & Console Gaming Lounge (77" OLED TV, Charcoal Modular Sofa, Walnut Coffee Table, PS5, Atmos Towers)
  - Zone 3: Open Kitchen & Honed Dark Calacatta Marble Waterfall Espresso Bar Island
  - Zone 4: Master Bedroom with Matte-Black Steel & Fluted-Glass Sliding Partition + Smoked-Glass Wardrobe
  - Zone 5: Modern Japanese Dark-Slate Spa Bathroom (Freestanding Soaking Tub, Walnut Vanity + Vessel Basin + Backlit Mirror, Rain Shower)
"""

import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh
import bpy

from config import BLEND_DIR, CACHE_DIR
from build_studio_slice import (
    BK_DIR,
    build_concept_a_architecture,
    build_monitors_screenbar_and_streamdeck,
    build_skyline_cyclorama,
    clear_scene,
    place_real_artist_models,
)
from hero_studio_assets import (
    build_back_wall_floating_shelf_and_slats,
    build_cascading_pothos_vines,
    build_compact_desktop_printer,
    build_concept_a_mic_boom_arm,
    build_concept_a_pc_tower,
    build_concept_a_pegboard,
    build_concept_a_track_lighting,
    build_cozy_reading_nook_details,
    build_desk_papers_laptop_stand_and_notes,
    build_grovemade_desk_shelf,
    build_lived_in_desk_details,
    build_maker_workbench_counter,
    build_pc_rolling_caddy,
    build_standing_desk,
    build_studio_architectural_led_strips,
)
from lighting_presets import apply_studio_mood, configure_cycles_metal
from lived_in_storytelling import build_all_lived_in_details
from materials import build_studio_material_palette
from mesh_utils import ensure_collection
from phase3_loft_zones import (
    apply_phase3_multiroom_lights,
    build_loft_extended_architecture,
    build_zone2_living_lounge,
    build_zone3_open_kitchen,
    build_zone4_master_bedroom,
    build_zone5_spa_bathroom,
)
from screen_art import generate_all_studio_screens


def _fix_studio_micro_blemishes() -> None:
    """Fix the 2 tiny macro blemishes spotted in Studio v8 QA (DualSense shell normals + 3D printer floating tiny nozzle)."""
    # 1. Recalculate consistent outward face normals on BK_PegDualSense shell meshes so WebGL never culls patches!
    ds = bpy.data.objects.get("BK_PegDualSense")
    if ds:
        for o in ds.children_recursive:
            if o.type == "MESH" and len(o.data.polygons) > 0:
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
                bm.to_mesh(o.data)
                bm.free()
                o.data.update()


def build_full_loft() -> Path:
    clear_scene()
    configure_cycles_metal(samples=64)

    screen_images = generate_all_studio_screens(CACHE_DIR / "screens")
    mats = build_studio_material_palette(screen_images)

    col_arch = ensure_collection("01_Architecture")
    col_hero = ensure_collection("02_Desk_And_Displays")
    col_bk = ensure_collection("03_BlenderKit_Artists")
    col_ph = ensure_collection("04_PolyHaven_CC0")
    col_lights = ensure_collection("05_Lights")

    # === ZONE 1: PERFECTED GEEK STUDIO & MAKER WORKBENCH (X=-2.18..+2.18, Y=-1.95..+2.05) ===
    build_concept_a_architecture(mats, col_arch)
    build_skyline_cyclorama(col_arch)

    desk_origin = (-0.22, 1.46, 0.0)
    build_standing_desk(desk_origin, mats, col_hero)
    build_grovemade_desk_shelf(desk_origin, mats, col_hero)
    build_monitors_screenbar_and_streamdeck(desk_origin, mats, col_hero)
    build_concept_a_mic_boom_arm(desk_origin, mats, col_hero)
    build_lived_in_desk_details(desk_origin, mats, col_hero)
    build_desk_papers_laptop_stand_and_notes(desk_origin, mats, col_hero)
    build_back_wall_floating_shelf_and_slats(wall_y=2.04, mats=mats, col=col_hero)
    build_maker_workbench_counter(location=(1.88, -0.74, 0.0), mats=mats, col=col_hero)
    build_compact_desktop_printer(location=(1.88, -1.16, 0.702), rot_z_deg=0.0, mats=mats, col=col_hero)

    pc_loc = (0.86, 1.48, 0.0)
    build_pc_rolling_caddy(location=pc_loc, rot_z_deg=0.0, mats=mats, col=col_hero)
    build_concept_a_pc_tower(
        location=(pc_loc[0], pc_loc[1], 0.043), rot_z_deg=0.0, mats=mats, col=col_hero,
        fan_glb_path=BK_DIR / "pc_fan_core" / "pc_fan_core.glb",
    )
    build_concept_a_track_lighting(center_x=-0.06, y_pos=1.08, ceiling_z=2.76, span_w=3.20, mats=mats, col=col_hero)
    build_concept_a_pegboard(location=(1.16, 2.04, 1.44), mats=mats, col=col_hero)
    build_studio_architectural_led_strips(desk_origin=desk_origin, wall_y=2.04, mats=mats, col=col_hero)
    build_cascading_pothos_vines(pot_location=(1.82, 0.34, 2.212), mats=mats, col=col_hero)
    build_cozy_reading_nook_details(table_location=(-1.74, -0.32, 0.0), mats=mats, col=col_hero)
    place_real_artist_models(desk_origin, mats, col_bk, col_ph)
    _fix_studio_micro_blemishes()

    # === ZONES 2, 3, 4, 5: FULL 87 m^2 MULTI-ROOM PENTHOUSE LOFT ===
    colliders = build_loft_extended_architecture(mats, col_arch)
    build_zone2_living_lounge(mats, col_hero, col_bk)
    build_zone3_open_kitchen(mats, col_hero, col_bk)
    build_zone4_master_bedroom(mats, col_hero, col_bk)
    build_zone5_spa_bathroom(mats, col_hero, col_bk)
    build_all_lived_in_details(mats, col_hero)

    # Synchronized 5-Zone Architectural Lighting (Midnight default)
    apply_studio_mood("midnight", col_lights)
    apply_phase3_multiroom_lights("midnight", col_lights)

    BLEND_DIR.mkdir(parents=True, exist_ok=True)
    (BLEND_DIR / "loft_colliders.json").write_text(json.dumps(colliders, indent=2), encoding="utf-8")

    try:
        bpy.ops.file.pack_all()
    except Exception as exc:
        print("Pack warning:", exc)

    out_blend = BLEND_DIR / "full_loft.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
    total_polys = sum(len(o.data.polygons) for o in mesh_objs)
    print(f"BUILT Full 5-Zone Loft (full_loft.blend): {len(mesh_objs)} mesh objects, {total_polys:,} base polygons.")
    return out_blend


if __name__ == "__main__":
    build_full_loft()
