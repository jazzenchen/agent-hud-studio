#!/usr/bin/env python3
"""
Quality Gate #1 v2 Renderer — Concept A+C Industrial Concrete Geek Loft.
Renders 4 high-resolution Cycles Metal GPU beauty shots matching Concept A's exact framing:
1. Signature Concept A Midnight Twilight Frontal Hero (West Grid Window + Raw Concrete + Loaded Bookshelf)
2. Intimate Desk Macro Closeup (Real BlenderKit 75% Keyboard, MX4 Mouse, Scarlett Solo, Stream Deck, M-Audio, Boom Mic)
3. Crisp Natural Afternoon Daylight (West Steel Window Sunlight across Raw Concrete & Herringbone Oak)
4. Golden Hour Bookshelf & Lounge Angle (Monstera, Leather Chair, PS5, Canon 5D, Vinyl Turntable, Hanging Plant)
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
from mathutils import Vector

from config import BLEND_DIR, RENDER_DIR
from lighting_presets import apply_studio_mood, configure_cycles_metal


def make_camera(
    name: str,
    location: tuple[float, float, float],
    target: tuple[float, float, float],
    lens_mm: float = 24.0,
    dof_fstop: float | None = None,
) -> bpy.types.Object:
    cam_data = bpy.data.cameras.new(name)
    cam_data.lens = lens_mm
    cam_data.sensor_width = 36.0
    cam_data.clip_start = 0.05
    cam_data.clip_end = 250.0

    cam_obj = bpy.data.objects.new(name, cam_data)
    bpy.context.scene.collection.objects.link(cam_obj)
    cam_obj.location = Vector(location)

    direction = Vector(target) - Vector(location)
    cam_obj.rotation_euler = direction.to_track_quat("-Z", "Y").to_euler()

    if dof_fstop is not None:
        cam_data.dof.use_dof = True
        cam_data.dof.focus_distance = direction.length
        cam_data.dof.aperture_fstop = dof_fstop
    return cam_obj


def main() -> None:
    quick = "--quick" in sys.argv
    blend_path = BLEND_DIR / "studio_slice.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    out_dir = RENDER_DIR / "gate1_v4"
    out_dir.mkdir(parents=True, exist_ok=True)
    light_col = bpy.data.collections.get("05_Lights") or bpy.context.scene.collection

    configure_cycles_metal(samples=64 if quick else 96, res_x=1280 if quick else 1600, res_y=720 if quick else 900)

    # 1. Exact Concept A Frontal Hero (West Grid Window left 23%, Track Rail top 8%, Desk+Mic+PC center, Bookshelf+Vines right 21%!)
    cam_concept_a = make_camera(
        "Cam_ConceptA_Hero",
        location=(0.0, -1.78, 1.24),
        target=(-0.02, 1.48, 1.32),
        lens_mm=19.5,
    )
    # 2. Lived-In Desk Macro Closeup (Keyboard, MX4, Scarlett, Moleskine+Brass Pen, Dark Ceramic Mug, EDC Tray, Boom Mic!)
    cam_desk = make_camera(
        "Cam_DeskCloseup",
        location=(0.56, 0.42, 1.20),
        target=(-0.18, 1.42, 0.94),
        lens_mm=34.0,
        dof_fstop=4.5,
    )
    # 3. Diagonal East Bookshelf + Cascading Pothos Vines + PC Tower
    cam_shelf = make_camera(
        "Cam_BookshelfGeek",
        location=(-1.25, -1.35, 1.32),
        target=(1.55, 0.72, 1.18),
        lens_mm=26.0,
    )

    shots = [
        ("01_concept_a_midnight_hero.png", "midnight", cam_concept_a),
        ("02_desk_closeup_lived_in.png", "midnight", cam_desk),
    ]
    if not quick:
        shots += [
            ("03_concept_a_daylight_hero.png", "daylight", cam_concept_a),
            ("04_golden_bookshelf_lounge.png", "golden", cam_shelf),
        ]

    scene = bpy.context.scene
    for filename, mood, cam in shots:
        print(f"\n=== Rendering {filename} (mood={mood}) ===")
        apply_studio_mood(mood, light_col)
        scene.camera = cam
        scene.render.filepath = str(out_dir / filename)
        bpy.ops.render.render(write_still=True)

    print(f"\nAll Gate 1 v4 renders saved to {out_dir}")


if __name__ == "__main__":
    main()
