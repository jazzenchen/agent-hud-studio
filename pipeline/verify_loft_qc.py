#!/usr/bin/env python3
"""
Phase 3 Multi-Room Cycles Visual QC & 3D Seating Audit across all 5 Loft Zones:
1. Audits exact world-space seating & zero-clipping bounding boxes for Living, Kitchen, Bedroom & Spa Bath hero furniture!
2. Renders 5 Cycles Metal GPU QC shots into renders/qc_loft/ for strict visual verification BEFORE multi-atlas baking!
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from mathutils import Vector

from config import BLEND_DIR, RENDER_DIR
from lighting_presets import apply_studio_mood, configure_cycles_metal
from phase3_loft_zones import apply_phase3_multiroom_lights


def group_aabb(root_name: str) -> tuple[Vector, Vector] | None:
    root = bpy.data.objects.get(root_name)
    if root is None:
        return None
    objs = [root] + list(root.children_recursive)
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


def set_camera_look_at(cam_obj: bpy.types.Object, loc: tuple[float, float, float], target: tuple[float, float, float], lens_mm: float = 24.0) -> None:
    cam_obj.location = loc
    direction = Vector(target) - Vector(loc)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()
    cam_obj.data.lens = lens_mm


def main() -> None:
    bpy.ops.wm.open_mainfile(filepath=str(BLEND_DIR / "full_loft.blend"))
    bpy.context.view_layer.update()

    print("\n================ PHASE 3 FULL 5-ZONE SEATING AUDIT ================")
    checks = [
        ("BK_LivingSofa", 0.000),
        ("BK_LivingCoffeeTable", 0.000),
        ("BK_LivingPS5", 0.520),
        ("BK_LivingMonstera", 0.000),
        ("BK_EspressoMachine", 0.922),
        ("BK_CoffeeGrinder", 0.922),
        ("BK_KitchenFaucet", 0.920),
        ("BK_BarStool_0", 0.000),
        ("BK_BarStool_1", 0.000),
        ("BK_BarStool_2", 0.000),
        ("BK_IslandPendant", None),
        ("BK_MasterBed", 0.000),
        ("BK_SpaBathtub", 0.002),
        ("BK_VesselSink", 0.836),
        ("BK_SpaToilet", 0.002),
    ]
    for name, exp_z in checks:
        bb = group_aabb(name)
        if not bb:
            print(f"  [{name:22s}] MISSING!")
            continue
        if exp_z is not None:
            dz = (bb[0].z - exp_z) * 100.0
            st = "PASS" if abs(dz) <= 1.2 else f"CHECK (dz={dz:+.1f}cm)"
        else:
            st = f"maxZ={bb[1].z:.3f}"
        print(f"  [{name:22s}] X=[{bb[0].x:+.2f},{bb[1].x:+.2f}] Y=[{bb[0].y:+.2f},{bb[1].y:+.2f}] Z=[{bb[0].z:+.2f},{bb[1].z:+.2f}] [{st}]")
    print("===================================================================\n")

    out_dir = RENDER_DIR / "qc_loft"
    out_dir.mkdir(parents=True, exist_ok=True)
    light_col = bpy.data.collections.get("05_Lights") or bpy.context.scene.collection

    cam_data = bpy.data.cameras.new("LoftQC_Cam")
    cam_obj = bpy.data.objects.new("LoftQC_Cam", cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    bpy.context.scene.camera = cam_obj

    configure_cycles_metal(samples=48, res_x=960, res_y=640)
    apply_studio_mood("midnight", light_col)
    apply_phase3_multiroom_lights("midnight", light_col)

    shots = [
        # 1. Zone 2 Living & Console Gaming Lounge (77" OLED TV + Sofa + Walnut Coffee Table + West Loft Window)
        ("qc_loft_01_living.png", (3.65, -2.10, 1.38), (0.35, -4.80, 0.92), 21.0),
        # 2. Zone 3 Open Kitchen & Dark Marble Waterfall Espresso Bar Island (Stools + Espresso + Pendant)
        ("qc_loft_02_kitchen.png", (3.10, -2.55, 1.46), (4.55, 1.25, 1.05), 22.0),
        # 3. Zone 4 Master Bedroom (Fluted-Glass Steel Partition + Floating JP Platform Bed + Smoked Wardrobe)
        ("qc_loft_03_bedroom.png", (5.15, -2.05, 1.38), (8.65, -3.75, 0.90), 21.0),
        # 4. Zone 5 Modern Spa Bathroom (Freestanding Soaking Tub + Walnut Vanity + Backlit Round Mirror + Rain Shower)
        ("qc_loft_04_bathroom.png", (7.45, -1.25, 1.40), (8.45, 1.30, 0.98), 19.0),
        # 5. Architectural Cross-Loft Vista (Studio looking South through open steel portal into Living Lounge & Fluted Glass!)
        ("qc_loft_05_vista.png", (-0.85, 0.45, 1.42), (3.40, -4.10, 1.02), 20.0),
    ]

    for fname, loc, target, lens in shots:
        set_camera_look_at(cam_obj, loc, target, lens_mm=lens)
        out_path = out_dir / fname
        bpy.context.scene.render.filepath = str(out_path)
        print(f"Rendering {fname}...")
        bpy.ops.render.render(write_still=True)
        print(f"  Saved -> {out_path}")

    print("\nALL 5 MULTI-ROOM LOFT QC RENDERS COMPLETE!")


if __name__ == "__main__":
    main()
