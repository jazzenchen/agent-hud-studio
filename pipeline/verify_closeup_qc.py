#!/usr/bin/env python3
"""
Automated Macro Closeup QC & Zero-Clipping Collision Verification (v6).
Inspired by MengTo's per-object visual scoring workflow:
1. Checks exact 3D world-space AABB clearances (PC vs desk foot, pegboard props vs hooks, bookshelf seating)
2. Renders 5 fast Cycles Metal GPU macro/hero QC stills into renders/qc_v6/ for visual scoring before baking!
"""

import math
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from mathutils import Vector

from config import BLEND_DIR, RENDER_DIR
from lighting_presets import apply_studio_mood, configure_cycles_metal


def world_aabb(objs: list[bpy.types.Object]) -> tuple[Vector, Vector] | None:
    meshes = [o for o in objs if o.type == "MESH" and len(o.data.vertices) > 0]
    if not meshes:
        return None
    mn = Vector((1e9, 1e9, 1e9))
    mx = Vector((-1e9, -1e9, -1e9))
    for m in meshes:
        for c in m.bound_box:
            wc = m.matrix_world @ Vector(c)
            mn.x = min(mn.x, wc.x); mn.y = min(mn.y, wc.y); mn.z = min(mn.z, wc.z)
            mx.x = max(mx.x, wc.x); mx.y = max(mx.y, wc.y); mx.z = max(mx.z, wc.z)
    return mn, mx


def group_aabb(root_name: str) -> tuple[Vector, Vector] | None:
    root = bpy.data.objects.get(root_name)
    if root is None:
        return None
    objs = [root] + list(root.children_recursive)
    return world_aabb(objs)


def run_collision_audit() -> None:
    print("\n================ 3D ZERO-CLIPPING & SEATING AUDIT (v6) ================")
    bpy.context.view_layer.update()

    # 1. PC Caddy & PC Tower vs Right Desk Foot / Desk Underside / Bookshelf
    foot_r = world_aabb([o for o in (bpy.data.objects.get("Desk_Foot_R"), bpy.data.objects.get("Desk_LegLower_R")) if o])
    caddy = group_aabb("Hero_PCRollingCaddy")
    pc = group_aabb("BK_CreatorsPC")
    desk_top = world_aabb([o for o in (bpy.data.objects.get("Desk_WalnutTop"),) if o])
    if foot_r and caddy and pc and desk_top:
        gap_x_foot = caddy[0].x - foot_r[1].x
        gap_z_top = desk_top[0].z - pc[1].z
        status_x = "PASS" if gap_x_foot >= 0.08 else "FAIL (CLIP/TOO TIGHT!)"
        status_z = "PASS" if gap_z_top >= 0.14 else "FAIL"
        print(f"  [PC vs Desk_Foot_R]  foot_maxX={foot_r[1].x:+.3f}, caddy_minX={caddy[0].x:+.3f} -> gap_X = {gap_x_foot*100:+.1f} cm  [{status_x}]")
        print(f"  [PC vs Desk_Top]     pc_maxZ={pc[1].z:+.3f}, desk_minZ={desk_top[0].z:+.3f}   -> gap_Z = {gap_z_top*100:+.1f} cm  [{status_z}]")
        print(f"  [PC World Box]       X=[{pc[0].x:+.3f},{pc[1].x:+.3f}], Y=[{pc[0].y:+.3f},{pc[1].y:+.3f}], Z=[{pc[0].z:+.3f},{pc[1].z:+.3f}]")

    # 2. Pegboard Props vs Board Front Face (y ≈ 2.012)
    panel = world_aabb([o for o in (bpy.data.objects.get("Peg_BoardPanel"),) if o])
    panel_front_y = panel[0].y if panel else 2.012
    print(f"  [Pegboard Front Y]   panel_front_Y = {panel_front_y:+.3f}")
    for name in ("BK_PegHeadset", "BK_PegDualSense", "BK_PegGameBoy", "BK_PegScrewdriver"):
        bb = group_aabb(name)
        if bb:
            clip_y = bb[1].y - panel_front_y
            st = "PASS" if clip_y <= 0.015 else "WARN (Clips board!)"
            print(f"  [{name:18s}] X=[{bb[0].x:+.3f},{bb[1].x:+.3f}] Y=[{bb[0].y:+.3f},{bb[1].y:+.3f}] Z=[{bb[0].z:+.3f},{bb[1].z:+.3f}] ({st})")

    # 3. Bookshelf + Maker Bench + Desk Geek Props Seating Check
    shelf_checks = [
        ("BK_ErgoMeshChair", 0.000),
        ("Apple_MacBookAir15", 0.815),
        ("Apple_MacStudio", 1.712),
        ("Apple_MacMini", 1.800),
        ("BK_TrashBin", 0.000),
        ("BK_PS5Console", 0.152),
        ("BK_3DPrinter", 0.702),
        ("BK_FilamentSpools", 0.702),
        ("Prop_DesktopLaserPrinter", 0.702),
        ("BK_RetroRobotToy", 1.897),
        ("BK_RubikCube_Desk", 0.842),
        ("BK_Macintosh1984", 0.672),
        ("BK_ZakuGunpla", 1.712),
        ("BK_StudioKeyLight", 0.000),
    ]
    for name, expected_z in shelf_checks:
        bb = group_aabb(name)
        if bb:
            dz = (bb[0].z - expected_z) * 100.0
            st = "PASS" if abs(dz) <= 1.2 else f"CHECK (dz={dz:+.1f}cm)"
            print(f"  [{name:22s}] minZ={bb[0].z:.3f} (exp {expected_z:.3f}) maxZ={bb[1].z:.3f} X=[{bb[0].x:.2f},{bb[1].x:.2f}] Y=[{bb[0].y:.2f},{bb[1].y:.2f}] [{st}]")
        else:
            print(f"  [{name:22s}] MISSING!")
    print("=======================================================================\n")


def set_camera_look_at(cam_obj: bpy.types.Object, loc: tuple[float, float, float], target: tuple[float, float, float], lens_mm: float = 35.0) -> None:
    cam_obj.location = loc
    direction = Vector(target) - Vector(loc)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam_obj.data.lens = lens_mm


def main() -> None:
    blend_path = BLEND_DIR / "studio_slice.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    run_collision_audit()

    out_dir = RENDER_DIR / "qc_v8"
    out_dir.mkdir(parents=True, exist_ok=True)
    light_col = bpy.data.collections.get("05_Lights") or bpy.context.scene.collection

    cam_data = bpy.data.cameras.new("QC_Cam")
    cam_obj = bpy.data.objects.new("QC_Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    configure_cycles_metal(samples=48, res_x=960, res_y=720)
    apply_studio_mood("midnight", light_col)

    shots = [
        # 1. Exact User Desk Close-Up (concrete wall, toed-in speakers, concave vertical monitor, mic, lamp, sticky notes)
        ("qc_01_desk_closeup.png", "midnight", (-0.18, 0.42, 1.30), (-0.14, 1.62, 1.00), 32.0),
        # 2. Left Corner + Official Apple MacBook Air 15" + Sculpted CNC Stand + Compact Fresnel Light + Dark Trash Bin + Slats
        ("qc_02_macbook_corner.png", "midnight", (-0.56, 0.36, 1.26), (-1.38, 1.44, 0.76), 28.0),
        # 3. Reading Nook Side Table (Hardcover Monographs + Stoneware Espresso Cup/Saucer/Spoon) + Armchair
        ("qc_03_reading_nook.png", "midnight", (-0.98, 0.14, 0.92), (-1.72, -0.34, 0.50), 38.0),
        # 4. East Wall (Bookshelf w/ Official Apple Mac Studio/mini + Macintosh 1984 + PS5 + Maker Workbench!)
        ("qc_04_east_wall.png", "midnight", (-0.38, -0.25, 1.32), (1.88, 0.25, 1.04), 22.0),
        # 5. Full Hero Midnight Wide Shot
        ("qc_05_hero_midnight.png", "midnight", (-0.12, -1.78, 1.34), (-0.04, 1.72, 1.18), 24.0),
    ]

    cur_mood = "midnight"
    for fname, mood, loc, target, lens in shots:
        if mood != cur_mood:
            apply_studio_mood(mood, light_col)
            cur_mood = mood
        set_camera_look_at(cam_obj, loc, target, lens_mm=lens)
        out_path = out_dir / fname
        bpy.context.scene.render.filepath = str(out_path)
        print(f"Rendering {fname} ({mood})...")
        bpy.ops.render.render(write_still=True)
        print(f"  Saved -> {out_path}")

    print("\nALL 5 MACRO QC RENDERS COMPLETE!")


if __name__ == "__main__":
    main()
