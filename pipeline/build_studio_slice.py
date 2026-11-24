#!/usr/bin/env python3
"""
Studio Slice v5 — Architectural-Digest Interior Design & Curatorial Overhaul.
Fixes every spatial, ergonomic & staging flaw identified in architectural review:
1. PC & Floor Discipline: Removes stray floor speaker; aligns Matte-Black Glass PC Tower square (6 deg)
   on a low-profile wheeled matte-black PC caddy cleanly tucked beneath the right desk overhang.
2. Scale Hierarchy by West Window: Replaces tiny lonely floor succulent with a 1.58m matte-black
   architectural cantilever floor lamp casting soft 2700K corner warmth; rotates South-West reading chair
   +132 deg so it faces INVITINGLY INTO THE ROOM & window view with side table at arm's reach and tall Monstera behind.
3. Curated 2-Bay 1.76m Steel & Walnut Bookshelf: Zero glitchy stacks, zero garish oversized magenta magazines,
   zero lonely rubber duck, zero pastel Lego vinyl blocks. Organized by real-life use & Rule-of-Thirds clusters
   (Tier 1: Charcoal bins + Hi-Fi Amp + dark monographs; Tier 2: Encyclopedia books + bookends + horizontal stack +
   collector keyboard; Tier 3: Turntable + 18 deep editorial vinyl LPs right beside it + ceramic vase;
   Tier 4: Leaning framed Bauhaus print + Canon cameras + grouped retro hardware; Tier 5: Asymmetric cascading pothos + plant).
4. Ergonomic Grovemade Desk Shelf: Houses Scarlett & DAC underneath, elevates Stream Deck & flat Qi smartphone on top,
   hides cables behind shelf; left open desk holds real dot-grid wireframe Moleskine + brass pen;
   right open desk (well clear of vertical OLED & mouse!) holds dark stoneware mug on walnut coaster + cognac EDC tray.
"""

import json
import math
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bmesh
import bpy
from mathutils import Vector

from config import BLEND_DIR, CACHE_DIR, MODEL_DIR
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
    build_hifi_integrated_amp,
    build_lived_in_desk_details,
    build_maker_workbench_counter,
    build_organizer_pens_and_tools,
    build_pc_rolling_caddy,
    build_pixel_matrix_clock,
    build_standing_desk,
    build_teardown_framed_art,
    build_uv_geek_book,
    build_venetian_blinds,
    build_vinyl_display_easel,
    create_curve_tube,
)
from lighting_presets import apply_studio_mood, configure_cycles_metal
from materials import build_studio_material_palette, make_solid_pbr
from mesh_utils import (
    create_beveled_box,
    create_beveled_cylinder,
    create_curved_panel,
    ensure_collection,
    import_blenderkit_glb,
    import_gltf_asset,
)
from screen_art import generate_all_studio_screens

BK_DIR = CACHE_DIR / "blenderkit"
APPLE_DIR = CACHE_DIR / "apple_official"
SKY_DIR = CACHE_DIR / "sky"


def import_apple_usdz(
    usdz_path: Path,
    name: str,
    collection: bpy.types.Collection,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_xyz_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    scale_factor: float = 1.0,
    ground_z: float | None = None,
) -> bpy.types.Object:
    """Import an optional local .usdz model at true CAD geometry (gracefully skipped if absent)."""
    if not usdz_path.exists():
        print(f"  [skip] Optional USDZ asset not found: {usdz_path.name} (place under {APPLE_DIR} to enable)")
        anchor = bpy.data.objects.new(name, None)
        collection.objects.link(anchor)
        anchor.location = location
        return anchor

    before = set(bpy.data.objects)
    bpy.ops.wm.usd_import(filepath=str(usdz_path))
    imported = [o for o in bpy.data.objects if o not in before]

    anchor = bpy.data.objects.new(name, None)
    collection.objects.link(anchor)

    top_objs = [o for o in imported if o.parent is None or o.parent not in imported]
    for o in imported:
        for c in list(o.users_collection):
            c.objects.unlink(o)
        collection.objects.link(o)
    for o in top_objs:
        o.parent = anchor

    anchor.scale = (scale_factor, scale_factor, scale_factor)
    anchor.rotation_euler = tuple(math.radians(a) for a in rotation_xyz_deg)
    anchor.location = location
    bpy.context.view_layer.update()

    if ground_z is not None:
        meshes = [o for o in imported if o.type == "MESH"]
        if meshes:
            min_z = min((o.matrix_world @ Vector(co)).z for o in meshes for co in o.bound_box)
            anchor.location.z += (ground_z - min_z)
            bpy.context.view_layer.update()
    return anchor


def clear_scene() -> None:
    bpy.ops.wm.read_factory_settings(use_empty=True)


def style_75_keyboard_pbt(kb_anchor: bpy.types.Object) -> None:
    """Color the 84 sculpted keycaps into authentic Concept A charcoal/slate PBT + terracotta Esc, Enter & Space."""
    bpy.context.view_layer.update()
    inv_anchor = kb_anchor.matrix_world.inverted()
    keycaps = []
    legends = []
    for o in kb_anchor.children_recursive:
        if o.type != "MESH" or not o.data.materials:
            continue
        ln = o.name.lower()
        if "keycap" in ln:
            bb = [inv_anchor @ (o.matrix_world @ Vector(c)) for c in o.bound_box]
            cx = (min(v.x for v in bb) + max(v.x for v in bb)) * 0.5
            cy = (min(v.y for v in bb) + max(v.y for v in bb)) * 0.5
            wx = max(v.x for v in bb) - min(v.x for v in bb)
            keycaps.append((o, cx, cy, wx))
        elif "legend" in ln:
            bb = [inv_anchor @ (o.matrix_world @ Vector(c)) for c in o.bound_box]
            cx = (min(v.x for v in bb) + max(v.x for v in bb)) * 0.5
            cy = (min(v.y for v in bb) + max(v.y for v in bb)) * 0.5
            legends.append((o, cx, cy))

    if not keycaps:
        return
    min_x = min(k[1] for k in keycaps)
    max_x = max(k[1] for k in keycaps)
    min_y = min(k[2] for k in keycaps)
    max_y = max(k[2] for k in keycaps)
    span_x = max(1e-4, max_x - min_x)
    span_y = max(1e-4, max_y - min_y)

    def classify(cx: float, cy: float, wx: float = 0.018) -> str:
        nx = (cx - min_x) / span_x
        ny = (cy - min_y) / span_y
        if nx < 0.06 and ny > 0.88:
            return "accent"
        if 0.78 < nx < 0.92 and 0.32 < ny < 0.50:
            return "accent"
        if ny < 0.14 and wx > 0.06:
            return "accent_space"
        if 0.12 < nx < 0.78 and 0.16 < ny < 0.84:
            return "slate"
        return "charcoal"

    mat_slate = make_solid_pbr("KB_PBT_Slate", (0.14, 0.145, 0.155), roughness=0.50, metallic=0.0, micro_bump_scale=900.0, micro_bump_strength=0.02)
    mat_charcoal = make_solid_pbr("KB_PBT_Charcoal", (0.042, 0.045, 0.050), roughness=0.48, metallic=0.0, micro_bump_scale=900.0, micro_bump_strength=0.02)
    mat_accent = make_solid_pbr("KB_PBT_Terracotta", (0.76, 0.24, 0.07), roughness=0.44, metallic=0.0, micro_bump_scale=900.0, micro_bump_strength=0.02)
    mat_leg_light = make_solid_pbr("KB_Legend_Light", (0.74, 0.73, 0.70), roughness=0.42, metallic=0.0)

    style_map = {"slate": mat_slate, "charcoal": mat_charcoal, "accent": mat_accent, "accent_space": mat_accent}
    for o, cx, cy, wx in keycaps:
        o.data.materials[0] = style_map[classify(cx, cy, wx)]
    for o, _cx, _cy in legends:
        o.data.materials[0] = mat_leg_light


def style_speaker_white_cone(spk_anchor: bpy.types.Object, white_mat: bpy.types.Material) -> None:
    """Turn M-Audio studio speaker woofer membranes into iconic Yamaha HS5 crisp satin-white cones."""
    for o in spk_anchor.children_recursive:
        if o.type == "MESH" and "medium_membrane" in o.name.lower():
            if o.data.materials:
                o.data.materials[0] = white_mat
            else:
                o.data.materials.append(white_mat)


def build_skyline_cyclorama(col: bpy.types.Collection) -> None:
    mat = bpy.data.materials.new("Arch_CitySkylineMat")
    mat.use_nodes = True
    nt = mat.node_tree
    nt.nodes.clear()
    out = nt.nodes.new("ShaderNodeOutputMaterial")
    emit = nt.nodes.new("ShaderNodeEmission")
    emit.inputs["Strength"].default_value = 1.95
    tex = nt.nodes.new("ShaderNodeTexImage")
    img_path = SKY_DIR / "skyline_midnight.jpg"
    if img_path.exists():
        img = bpy.data.images.load(str(img_path), check_existing=True)
        img.colorspace_settings.name = "sRGB"
        tex.image = img
    nt.links.new(tex.outputs["Color"], emit.inputs["Color"])
    nt.links.new(emit.outputs["Emission"], out.inputs["Surface"])

    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    segs = 28
    radius = 12.5
    z_bot, z_top = -3.8, 7.6
    ang_start = math.pi - math.radians(56.0)
    ang_end = math.pi + math.radians(56.0)
    v_bot, v_top = [], []
    for i in range(segs + 1):
        t = i / segs
        a = ang_start + t * (ang_end - ang_start)
        v_bot.append(bm.verts.new((radius * math.cos(a), radius * math.sin(a), z_bot)))
        v_top.append(bm.verts.new((radius * math.cos(a), radius * math.sin(a), z_top)))

    for i in range(segs):
        f = bm.faces.new((v_bot[i], v_bot[i + 1], v_top[i + 1], v_top[i]))
        u0, u1 = i / segs, (i + 1) / segs
        f.loops[0][uv].uv = (u0, 0.0)
        f.loops[1][uv].uv = (u1, 0.0)
        f.loops[2][uv].uv = (u1, 1.0)
        f.loops[3][uv].uv = (u0, 1.0)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Arch_CitySkylineBackdrop")
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new("Arch_CitySkylineBackdrop", mesh)
    obj.data.materials.append(mat)
    obj.data.polygons.foreach_set("use_smooth", [True] * len(obj.data.polygons))
    obj.visible_shadow = False
    obj.visible_diffuse = False
    col.objects.link(obj)


def _add_horizontal_book_stack(
    prefix: str,
    base_loc: tuple[float, float, float],
    dims_list: list[tuple[float, float, float, float]],
    spine_indices: list[int],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> float:
    """Create a realistic horizontal stack of real UV-mapped design/tech art monographs; returns top Z."""
    bx, by, cur_z = base_loc
    for idx, (d, w, t, yaw_deg) in enumerate(dims_list):
        build_uv_geek_book(
            f"{prefix}_{idx}", (d, w, t),
            (bx + (idx % 2 - 0.5) * 0.008, by + ((idx + 1) % 2 - 0.5) * 0.008, cur_z + t * 0.5),
            spine_idx=spine_indices[idx % len(spine_indices)],
            mats=mats, col=col,
            rotation=(0.0, 0.0, math.radians(yaw_deg)),
            horizontal=True,
        )
        cur_z += t
    return cur_z


def build_concept_a_architecture(mats: dict[str, bpy.types.Material], col: bpy.types.Collection) -> list[dict]:
    """
    Cozy architectural proportions (4.36m W x 4.00m D x 2.76m H) with curated 2-bay 1.76m East Bookshelf.
    """
    x0, x1 = -2.18, 2.18
    y0, y1 = -1.95, 2.05
    h = 2.76
    wt = 0.22
    w = x1 - x0
    d = y1 - y0
    cx = (x0 + x1) * 0.5
    cy = (y0 + y1) * 0.5

    # 1. Herringbone Oak Parquet Floor
    create_beveled_box("Arch_Floor", (w + wt * 2, d + wt * 2, 0.14), (cx, cy, -0.07), bevel=0.002, material=mats["floor_parquet"], uv_scale=1.0, collection=col)

    # 2. Raw Cast Concrete Ceiling + Flush Architectural Matte-Black Linear AC Slot Diffuser (replaces rusty pipe!) + Corner Electrical Conduit
    create_beveled_box("Arch_Ceiling", (w + wt * 2, d + wt * 2, 0.16), (cx, cy, h + 0.08), bevel=0.002, material=mats["ceiling_plaster"], uv_scale=1.0, collection=col)
    create_beveled_box("Arch_LinearAC_Frame", (2.10, 0.072, 0.014), (cx, y0 + 0.34, h - 0.007), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_LinearAC_Blade", (2.02, 0.012, 0.016), (cx, y0 + 0.34, h - 0.008), bevel=0.001, material=mats["gunmetal"], collection=col)
    create_beveled_cylinder("Arch_Conduit_Pipe", 0.011, h - 0.08, 16, location=(x0 + 0.06, y1 - 0.025, h * 0.5), material=mats["anodized_black"], collection=col)
    for cz in (0.45, 1.38, 2.32):
        create_beveled_box(f"Arch_Conduit_Clamp_{cz:.2f}", (0.036, 0.026, 0.016), (x0 + 0.06, y1 - 0.020, cz), bevel=0.002, material=mats["anodized_black"], collection=col)

    # 3. North Feature Wall — 4x2 Board-Formed Architectural Concrete Panels with 4mm Reveals & Tie Holes
    create_beveled_box("Arch_WallNorth_Back", (w + wt * 2, wt, h), (cx, y1 + wt * 0.5 + 0.006, h * 0.5), bevel=0.0, material=mats["wall_concrete_seam"], collection=col)
    panel_cols = [(-2.18, -1.093), (-1.087, -0.003), (0.003, 1.087), (1.093, 2.18)]
    panel_rows = [(0.0, 1.377), (1.383, h)]
    for ci, (px0, px1) in enumerate(panel_cols):
        for ri, (pz0, pz1) in enumerate(panel_rows):
            pw, ph = px1 - px0, pz1 - pz0
            pcx, pcz = (px0 + px1) * 0.5, (pz0 + pz1) * 0.5
            create_beveled_box(f"Arch_ConcretePanel_{ci}_{ri}", (pw, 0.016, ph), (pcx, y1 + 0.004, pcz), bevel=0.003, segments=2, material=mats["wall_dark_concrete"], uv_scale=0.95, collection=col)

    # 4. East & South Concrete Walls + Slim Black Baseboards
    create_beveled_box("Arch_Wall_East", (wt, d + wt * 2, h), (x1 + wt * 0.5, cy, h * 0.5), bevel=0.004, material=mats["wall_concrete"], uv_scale=0.95, collection=col)
    create_beveled_box("Arch_Wall_South", (w + wt * 2, wt, h), (cx, y0 - wt * 0.5, h * 0.5), bevel=0.004, material=mats["wall_microcement"], uv_scale=1.0, collection=col)
    create_beveled_box("Arch_Baseboard_N", (w, 0.010, 0.048), (cx, y1 - 0.009, 0.024), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_Baseboard_E", (0.010, d, 0.048), (x1 - 0.005, cy, 0.024), bevel=0.002, material=mats["anodized_black"], collection=col)

    # 5. West Wall — Full-Height Matte-Black Steel-Grid Industrial Loft Window (4x4 Crisp Grid)
    win_y0, win_y1 = -1.84, 1.92
    win_z0, win_z1 = 0.06, 2.68
    create_beveled_box("Arch_WestPier_S", (wt, win_y0 - y0 + wt, h), (x0 - wt * 0.5, (y0 - wt + win_y0) * 0.5, h * 0.5), bevel=0.004, material=mats["wall_concrete"], collection=col)
    create_beveled_box("Arch_WestPier_N", (wt, y1 + wt - win_y1, h), (x0 - wt * 0.5, (win_y1 + y1 + wt) * 0.5, h * 0.5), bevel=0.004, material=mats["wall_concrete"], collection=col)
    create_beveled_box("Arch_WestCurb", (wt, win_y1 - win_y0, win_z0), (x0 - wt * 0.5, (win_y0 + win_y1) * 0.5, win_z0 * 0.5), bevel=0.003, material=mats["wall_concrete"], collection=col)
    create_beveled_box("Arch_WestLintel", (wt, win_y1 - win_y0, h - win_z1), (x0 - wt * 0.5, (win_y0 + win_y1) * 0.5, (win_z1 + h) * 0.5), bevel=0.003, material=mats["wall_concrete"], collection=col)

    fx = x0 - wt * 0.42
    win_w = win_y1 - win_y0
    win_h = win_z1 - win_z0
    win_cy = (win_y0 + win_y1) * 0.5
    create_beveled_box("Arch_LoftWin_FrameBot", (0.084, win_w, 0.044), (fx, win_cy, win_z0 + 0.022), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_LoftWin_FrameTop", (0.084, win_w, 0.044), (fx, win_cy, win_z1 - 0.022), bevel=0.003, material=mats["anodized_black"], collection=col)
    for i in range(5):
        my = win_y0 + (i / 4.0) * win_w
        thick = 0.048 if i in (0, 2, 4) else 0.032
        create_beveled_box(f"Arch_LoftWin_V_{i}", (0.084 if i in (0, 2, 4) else 0.058, thick, win_h), (fx, my, (win_z0 + win_z1) * 0.5), bevel=0.003, material=mats["anodized_black"], collection=col)
    for j in range(1, 5):
        mz = win_z0 + (j / 5.0) * win_h
        create_beveled_box(f"Arch_LoftWin_H_{j}", (0.056, win_w, 0.028), (fx, win_cy, mz), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_LoftWin_Glass", (0.008, win_w - 0.04, win_h - 0.04), (fx, win_cy, (win_z0 + win_z1) * 0.5), bevel=0.0, material=mats["window_glass"], collection=col)

    # Matte-Black Slatted Venetian Blinds on Upper 42% of West Loft Window (dramatic MengTo golden sunlight stripes!)
    build_venetian_blinds(x_pos=x0 + 0.032, y0=win_y0, y1=win_y1, z_bot=1.56, z_top=2.66, mats=mats, col=col, slat_tilt_deg=24.0)

    # 6. Thin 6mm Hand-Loomed Japanese Heathered Charcoal-Taupe Wool Rug tucked cleanly 41cm UNDER front desk feet!
    # Quiet SOLID matte warm-charcoal woven wool rug (zero busy checkerboard pattern!)
    from materials import make_solid_pbr
    mat_studio_rug = make_solid_pbr("Furn_StudioRugCharcoal", (0.16, 0.16, 0.165), roughness=0.95, metallic=0.0, micro_bump_scale=480.0, micro_bump_strength=0.08)
    rug = create_beveled_box("Furn_StudioRug", (2.66, 2.02, 0.006), (-0.20, 0.44, 0.003), bevel=0.0025, segments=2, material=mat_studio_rug, uv_scale=1.0, collection=col)
    uv_layer = rug.data.uv_layers.active
    for poly in rug.data.polygons:
        for li in poly.loop_indices:
            v = rug.data.vertices[rug.data.loops[li].vertex_index].co
            uv_layer.data[li].uv = ((v.x / 2.66) + 0.5, (v.y / 2.02) + 0.5)

    # 7. Curated 2-Bay 1.76m Matte-Black Steel & Dark Walnut Geek Gallery Bookshelf (X = +1.94, Y = 0.14..1.90)
    sh_x, sh_y0, sh_y1 = 1.94, 0.14, 1.90
    sh_d, sh_w, sh_cy, sh_h = 0.42, sh_y1 - sh_y0, (sh_y0 + sh_y1) * 0.5, 2.24
    for py in (sh_y0, sh_cy, sh_y1):
        for px in (sh_x - sh_d * 0.5, sh_x + sh_d * 0.5):
            create_beveled_box(f"Shelf_Post_{px:.2f}_{py:+.2f}", (0.022, 0.022, sh_h), (px, py, sh_h * 0.5), bevel=0.002, material=mats["anodized_black"], collection=col)
    from materials import make_emissive
    mat_studio_shelf_rgb = bpy.data.materials.get("Emit_StudioShelfRGB") or make_emissive(
        "Emit_StudioShelfRGB", (0.12, 0.82, 1.0), strength=3.8, roughness=0.22
    )
    for idx, sz in enumerate((0.14, 0.66, 1.18, 1.70, 2.20)):
        create_beveled_box(f"Shelf_Plank_{idx}", (sh_d - 0.01, sh_w - 0.01, 0.024), (sh_x, sh_cy, sz), bevel=0.003, material=mats["walnut_desk"], uv_scale=0.8, collection=col)
        create_beveled_box(f"Shelf_RailBack_{idx}", (0.014, sh_w, 0.014), (sh_x + sh_d * 0.5, sh_cy, sz), bevel=0.002, material=mats["anodized_black"], collection=col)
        # Recessed front-under aluminum ARGB LED gallery diffuser bar beneath Planks 1..4 (synced with Studio 8-mode neon!)
        if idx >= 1:
            create_beveled_box(f"Shelf_LEDChannel_{idx}", (0.016, sh_w - 0.06, 0.008), (sh_x - 0.14, sh_cy, sz - 0.016), bevel=0.001, material=mats["anodized_black"], collection=col)
            create_beveled_box(f"Shelf_LEDStrip_{idx}", (0.010, sh_w - 0.08, 0.005), (sh_x - 0.14, sh_cy, sz - 0.0205), bevel=0.0005, material=mat_studio_shelf_rgb, collection=col)

    # === 100% AUTHENTIC GEEK BOOKSHELF CURATION v6 (ZERO Airbnb vases, ZERO Victorian encyclopedias, ZERO boho art!) ===
    rng = random.Random(66)

    # TIER 1 (Z = 0.152 — Heavy Anchors + PlayStation 5 Console!):
    # Front bay (Y = 0.14..1.02): PlayStation 5 at Y = 0.36 + 1 Charcoal Felt Gear Bin at Y = 0.78!
    create_beveled_box("Prop_StorageBin_+0.78", (0.34, 0.36, 0.28), (sh_x - 0.01, 0.78, 0.152 + 0.14), bevel=0.008, material=mats["acoustic_felt"], collection=col)
    create_beveled_box("Prop_BinHandle_+0.78", (0.012, 0.095, 0.022), (sh_x - 0.18, 0.78, 0.152 + 0.19), bevel=0.003, material=mats["brushed_brass"], collection=col)
    # Back bay (Y = 1.02..1.90): Hi-Fi Integrated Stereo Amplifier (Y = 1.60) + Horizontal Stack of 3 Real Design/Arch Monographs (Y = 1.19)
    build_hifi_integrated_amp((sh_x - 0.02, 1.60, 0.152), mats, col)
    _add_horizontal_book_stack(
        "Shelf1_MonographStack", (sh_x - 0.02, 1.19, 0.152),
        [(0.30, 0.24, 0.036, 2.0), (0.28, 0.22, 0.030, -3.5), (0.26, 0.21, 0.028, 1.5)],
        [10, 6, 3], mats, col,
    )

    # TIER 2 (Z = 0.672 — Collector Keyboard + Wire-Mesh Pen/Tool Organizer + Real CS/Design Books + Apple Macintosh 1984!):
    # Front bay: Horizontal 2-book riser under angled 75% custom keyboard (Y = 0.42); BK_PenOrganizer sits at Y = 0.80!
    _add_horizontal_book_stack(
        "Shelf2_KbRiser", (sh_x - 0.03, 0.42, 0.672),
        [(0.26, 0.34, 0.026, 1.5), (0.24, 0.31, 0.022, -2.0)],
        [2, 5], mats, col,
    )
    # Back bay left (Y = 1.08..1.34): 8 Real Printed-Spine Tech/Design/Manga Books (O'Reilly, PBR, Dieter Rams, AKIRA, Casa BRUTUS!)
    book_specs = [
        # (spine_idx, depth, thick, height)
        (0, 0.20, 0.034, 0.245),  # O'Reilly DDIA
        (1, 0.195, 0.030, 0.240), # O'Reilly Systems
        (2, 0.21, 0.036, 0.255),  # Real-Time Rendering
        (5, 0.215, 0.038, 0.260), # PBR Book
        (3, 0.22, 0.028, 0.268),  # Dieter Rams
        (4, 0.19, 0.032, 0.250),  # AKIRA Vol. 1
        (6, 0.21, 0.022, 0.275),  # Casa BRUTUS
        (7, 0.20, 0.028, 0.242),  # Braun Monograph
    ]
    cur_by = 1.09
    for bi, (s_idx, bd, bt, bh) in enumerate(book_specs):
        build_uv_geek_book(
            f"Shelf2_GeekBook_{bi}", (bd, bt, bh),
            (sh_x - 0.02 + rng.uniform(-0.008, 0.008), cur_by + bt * 0.5, 0.672 + bh * 0.5),
            spine_idx=s_idx, mats=mats, col=col,
        )
        cur_by += bt + 0.0025
    create_beveled_box("Shelf2_BookendM", (0.15, 0.006, 0.17), (sh_x - 0.02, cur_by + 0.006, 0.672 + 0.085), bevel=0.001, material=mats["anodized_black"], collection=col)
    # (Apple Macintosh 1984 CRT centerpiece sits in Back bay right at Y = 1.63!)

    # TIER 3 (Z = 1.192 — Eye-Level Audio, Vinyl & Pixel Clock Vignette!):
    # Front bay: Vinyl Turntable at Y = 0.50 + LaMetric/Divoom Pixel Matrix LED Clock at Y = 0.87!
    build_pixel_matrix_clock((sh_x - 0.06, 0.87, 1.192), rot_z_deg=-8.0, mats=mats, col=col)
    # Back bay: Front-Facing Displayed Vinyl LP Sleeve ('TOKYO MIDNIGHT SYNTH' w/ Obi strip!) at Y = 1.24 + 16 Printed-Spine Dark LPs!
    build_vinyl_display_easel((sh_x - 0.03, 1.24, 1.192), rot_z_deg=14.0, mats=mats, col=col, cover_index=0)
    lp_spines = [2, 9, 15, 5, 7, 13, 11, 2, 4, 8, 15, 9, 6, 12, 5, 14]
    for vi in range(16):
        vy = 1.49 + vi * 0.022
        vh = rng.uniform(0.308, 0.318)
        vd = rng.uniform(0.308, 0.320)
        lean = math.radians(rng.uniform(-1.2, 1.2)) if vi > 1 else math.radians(-8.0)
        build_uv_geek_book(
            f"Prop_PrintedVinylLP_{vi:02d}", (vd, 0.0072, vh),
            (sh_x - 0.02 + rng.uniform(-0.006, 0.006), vy, 1.192 + vh * 0.5),
            spine_idx=lp_spines[vi % len(lp_spines)], mats=mats, col=col,
            rotation=(lean, 0.0, 0.0),
        )
    create_beveled_box("Shelf3_VinylBookend", (0.20, 0.006, 0.20), (sh_x - 0.02, 1.45, 1.192 + 0.10), bevel=0.001, material=mats["anodized_black"], collection=col)

    # TIER 4 (Z = 1.712 — Hardware Teardown Frame, HomeLab Mini-PC Cluster, Cameras & Gundam Zaku MK-II!):
    # Back bay: Grid Studio Game Boy DMG-01 Hardware Teardown Frame leaning cleanly behind Canon cameras!
    build_teardown_framed_art((sh_x + 0.085, 1.52, 1.712), mats, col)
    _add_horizontal_book_stack(
        "Shelf4_CamRiser", (sh_x - 0.04, 1.24, 1.712),
        [(0.24, 0.28, 0.028, 2.5), (0.22, 0.25, 0.022, -2.0)],
        [14, 15], mats, col,
    )
    # Front bay: HomeLab dual-node LED status strip & rear Ethernet patch loop at Y = 0.72 (Zaku at Y=0.45, PSP at Y=0.92)
    create_curve_tube(
        "HomeLab_PatchCable",
        [(sh_x + 0.075, 0.70, 1.735), (sh_x + 0.115, 0.72, 1.768), (sh_x + 0.075, 0.74, 1.805)],
        radius=0.0032, material=mats["matte_plastic"], col=col, bevel_res=4,
    )
    for nz in (1.724, 1.792):
        create_beveled_cylinder(
            f"HomeLab_StatusLED_{nz:.3f}", radius=0.0028, depth=0.003, vertices=10, bevel=0.0005,
            location=(sh_x - 0.095, 0.765, nz), rotation=(0.0, math.radians(90), 0.0),
            material=mats["emissive_homelab_led"], collection=col,
        )

    colliders = [
        {"name": "room_bounds", "type": "bounds", "minX": x0 + 0.34, "maxX": x1 - 0.34, "minZ": -y1 + 0.34, "maxZ": -y0 - 0.34},
        {"name": "standing_desk", "type": "box", "minX": -1.35, "maxX": 1.05, "minZ": -1.92, "maxZ": -0.98},
        {"name": "east_bookshelf", "type": "box", "minX": 1.62, "maxX": 2.18, "minZ": -1.96, "maxZ": -0.05},
        {"name": "maker_workbench", "type": "box", "minX": 1.54, "maxX": 2.18, "minZ": 0.02, "maxZ": 1.52},
        {"name": "lounge_chair", "type": "box", "minX": -2.05, "maxX": -0.88, "minZ": 0.45, "maxZ": 1.80},
    ]
    return colliders


def build_monitors_screenbar_and_streamdeck(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> None:
    dx, dy, _ = desk_origin
    desk_h = 0.750
    shelf_top_z = desk_h + 0.092  # Exact top of Grovemade desk shelf!

    # 1. Center 38" Curved Ultrawide OLED + Arm + BenQ ScreenBar
    uw_body, _ = create_curved_panel(
        "Monitor_Ultrawide38", width=0.89, height=0.385, thickness=0.015, curve_radius=1.80,
        segments_x=40, bevel=0.0025, material=mats["anodized_black"], screen_material=mats["screen_ultrawide"], collection=col,
    )
    uw_body.location = (dx - 0.08, dy + 0.25, desk_h + 0.385)
    uw_body.rotation_euler = (math.radians(2.5), 0.0, 0.0)

    create_beveled_box("ArmUW_Clamp", (0.09, 0.08, 0.05), (dx - 0.08, dy + 0.40, desk_h + 0.024), bevel=0.004, material=mats["anodized_black"], collection=col)
    create_beveled_cylinder("ArmUW_Pole", 0.020, 0.38, location=(dx - 0.08, dy + 0.40, desk_h + 0.21), bevel=0.002, material=mats["gunmetal"], collection=col)
    create_curve_tube("ArmUW_Link", [(dx - 0.08, dy + 0.40, desk_h + 0.30), (dx - 0.14, dy + 0.36, desk_h + 0.35), (dx - 0.08, dy + 0.28, desk_h + 0.385)], 0.016, mats["anodized_black"], col)

    sb_z = desk_h + 0.592
    create_beveled_cylinder("Interact_ScreenBar_Tube", 0.012, 0.48, 28, location=(dx - 0.08, dy + 0.225, sb_z), rotation=(0.0, math.radians(90), 0.0), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Interact_ScreenBar_Clamp", (0.085, 0.058, 0.036), (dx - 0.08, dy + 0.255, sb_z - 0.012), bevel=0.004, material=mats["gunmetal"], collection=col)
    create_beveled_box("Interact_ScreenBar_LED", (0.44, 0.008, 0.006), (dx - 0.08, dy + 0.222, sb_z - 0.010), bevel=0.001, material=mats["emissive_cove_warm"], collection=col)

    # 2. Tightly-Abutted Right 27" Vertical Monitor (rot_z=-14 deg wraps CONCAVE INWARD toward user!)
    vx, vy, vz = dx + 0.53, dy + 0.21, desk_h + 0.415
    vert_anchor = bpy.data.objects.new("Monitor_Vertical27_Anchor", None)
    vert_anchor.location = (vx, vy, vz)
    vert_anchor.rotation_euler = (0.0, 0.0, math.radians(-14.0))
    col.objects.link(vert_anchor)
    vert_body = create_beveled_box("Monitor_Vertical27_Body", (0.342, 0.015, 0.585), (0.0, 0.0, 0.0), bevel=0.0025, segments=2, material=mats["anodized_black"], collection=col)
    vert_body.parent = vert_anchor
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    sw, sh = 0.330, 0.568
    f = bm.faces.new((
        bm.verts.new((-sw * 0.5, -0.0088, -sh * 0.5 + 0.003)),
        bm.verts.new((sw * 0.5, -0.0088, -sh * 0.5 + 0.003)),
        bm.verts.new((sw * 0.5, -0.0088, sh * 0.5 + 0.003)),
        bm.verts.new((-sw * 0.5, -0.0088, sh * 0.5 + 0.003)),
    ))
    f.loops[0][uv].uv = (0.0, 0.0); f.loops[1][uv].uv = (1.0, 0.0); f.loops[2][uv].uv = (1.0, 1.0); f.loops[3][uv].uv = (0.0, 1.0)
    vscr_mesh = bpy.data.meshes.new("Monitor_Vertical27_Screen")
    bm.to_mesh(vscr_mesh); bm.free()
    vscr_obj = bpy.data.objects.new("Monitor_Vertical27_Screen", vscr_mesh)
    vscr_obj.data.materials.append(mats["screen_vertical"])
    col.objects.link(vscr_obj)
    vscr_obj.parent = vert_anchor
    create_beveled_box("ArmVert_Clamp", (0.08, 0.075, 0.048), (dx + 0.44, dy + 0.395, desk_h + 0.022), bevel=0.004, material=mats["anodized_black"], collection=col)
    create_curve_tube("ArmVert_Link", [(dx + 0.44, dy + 0.395, desk_h + 0.06), (dx + 0.50, dy + 0.36, desk_h + 0.28), (vx, vy + 0.02, vz)], 0.015, mats["anodized_black"], col)

    # 3. Compact Elgato Stream Deck MK.2 seated cleanly ON TOP of the Grovemade Walnut Desk Shelf!
    sd_anchor = bpy.data.objects.new("Hero_StreamDeck", None)
    sd_anchor.location = (dx - 0.14, dy + 0.10, shelf_top_z + 0.036)
    sd_anchor.rotation_euler = (math.radians(-46.0), 0.0, 0.0)
    col.objects.link(sd_anchor)
    sd_body = create_beveled_box("SD_Body", (0.104, 0.018, 0.072), (0.0, 0.0, 0.0), bevel=0.005, segments=3, material=mats["matte_plastic"], collection=col)
    sd_body.parent = sd_anchor
    create_beveled_box("SD_Stand", (0.084, 0.056, 0.036), (dx - 0.14, dy + 0.118, shelf_top_z + 0.018), bevel=0.004, material=mats["anodized_black"], collection=col)
    bm_sd = bmesh.new(); uv_sd = bm_sd.loops.layers.uv.verify()
    sdw, sdh = 0.092, 0.058
    fsd = bm_sd.faces.new((
        bm_sd.verts.new((-sdw * 0.5, -0.010, -sdh * 0.5)),
        bm_sd.verts.new((sdw * 0.5, -0.010, -sdh * 0.5)),
        bm_sd.verts.new((sdw * 0.5, -0.010, sdh * 0.5)),
        bm_sd.verts.new((-sdw * 0.5, -0.010, sdh * 0.5)),
    ))
    fsd.loops[0][uv_sd].uv = (0.0, 0.0); fsd.loops[1][uv_sd].uv = (1.0, 0.0); fsd.loops[2][uv_sd].uv = (1.0, 1.0); fsd.loops[3][uv_sd].uv = (0.0, 1.0)
    sd_mesh = bpy.data.meshes.new("SD_KeysPanel"); bm_sd.to_mesh(sd_mesh); bm_sd.free()
    sd_scr = bpy.data.objects.new("SD_KeysPanel", sd_mesh)
    sd_scr.data.materials.append(mats["screen_stream_deck"])
    col.objects.link(sd_scr); sd_scr.parent = sd_anchor

    # 4. Studio Monitor Isolation Stands flanking the dual-monitor cockpit (TOED INWARD toward seated listener!)
    for side, sx, rot_z in (("L", dx - 0.74, 15.0), ("R", dx + 0.87, -15.0)):
        st = bpy.data.objects.new(f"SpeakerStand_{side}", None)
        st.location = (sx, dy + 0.18, desk_h)
        st.rotation_euler = (0.0, 0.0, math.radians(rot_z))
        col.objects.link(st)
        for o in (
            create_beveled_box(f"SpkStand_{side}_Base", (0.165, 0.195, 0.010), (0.0, 0.0, 0.005), bevel=0.002, material=mats["anodized_black"], collection=col),
            create_beveled_box(f"SpkStand_{side}_Col", (0.036, 0.055, 0.145), (0.0, 0.01, 0.077), bevel=0.003, material=mats["anodized_black"], collection=col),
            create_beveled_box(f"SpkStand_{side}_Top", (0.160, 0.188, 0.008), (0.0, 0.0, 0.150), bevel=0.002, material=mats["anodized_black"], collection=col),
        ):
            o.parent = st

    # 5. Coiled Aviator USB-C Keyboard Cable tucked cleanly straight UNDER the Grovemade shelf!
    coil_pts = [(dx - 0.14, dy - 0.08, desk_h + 0.018), (dx - 0.14, dy - 0.02, desk_h + 0.010)]
    for i in range(44):
        t = i / 43.0
        ang = t * 11.0 * 2.0 * math.pi
        coil_pts.append((dx - 0.13 + t * 0.13, dy - 0.015 + 0.008 * math.cos(ang), desk_h + 0.012 + 0.008 * math.sin(ang)))
    coil_pts += [(dx + 0.03, dy - 0.015, desk_h + 0.010), (dx + 0.03, dy + 0.12, desk_h + 0.007), (dx - 0.04, dy + 0.34, desk_h + 0.006)]
    create_curve_tube("KB_CoiledAviatorCable", coil_pts, radius=0.0026, material=mats["matte_plastic"], col=col, bevel_res=5)
    create_beveled_cylinder("KB_AviatorConnector", 0.0065, 0.044, 20, location=(dx + 0.02, dy - 0.015, desk_h + 0.010), rotation=(0.0, math.radians(90), 0.0), bevel=0.0015, material=mats["chrome"], collection=col)


def place_real_artist_models(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col_bk: bpy.types.Collection,
    col_ph: bpy.types.Collection,
) -> None:
    dx, dy, _ = desk_origin
    desk_h = 0.750
    shelf_top_z = desk_h + 0.092
    bk = lambda slot: BK_DIR / slot / f"{slot}.glb"
    ph = lambda aid: MODEL_DIR / aid / f"{aid}.gltf"

    # === 1. DESK HERO PERIPHERALS ===
    kb_hero = import_blenderkit_glb(
        bk("mech_keyboard_75"), "BK_MechKeyboard75", col_bk,
        target_width=0.325, location=(dx - 0.08, dy - 0.15, desk_h + 0.0045),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=desk_h + 0.0045,
    )
    style_75_keyboard_pbt(kb_hero)

    import_blenderkit_glb(
        bk("mx_mouse"), "BK_LogitechMX4", col_bk,
        target_height=0.048, location=(dx + 0.21, dy - 0.15, desk_h + 0.0045),
        rotation_xyz_deg=(0.0, 0.0, -7.0), ground_z=desk_h + 0.0045,
    )
    # Focusrite Scarlett Solo cleanly centered & unobstructed UNDER the left cubby of the Grovemade desk shelf!
    import_blenderkit_glb(
        bk("focusrite_scarlett"), "BK_FocusriteScarlett", col_bk,
        target_width=0.130, location=(dx - 0.24, dy + 0.09, desk_h),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=desk_h,
    )
    # Dimmed Always-On OLED Smartphone resting flat on Qi pad ON TOP of the Grovemade desk shelf!
    phone = import_blenderkit_glb(
        bk("smartphone_black"), "BK_DeskSmartphone", col_bk,
        target_max_dim=0.145, location=(dx + 0.24, dy + 0.11, shelf_top_z + 0.007),
        rotation_xyz_deg=(0.0, 0.0, -10.0), ground_z=shelf_top_z + 0.007,
    )
    for obj in phone.children_recursive:
        if obj.type == "MESH" and obj.data.materials:
            for m in obj.data.materials:
                if m and "screen" in m.name.lower() and m.use_nodes:
                    bsdf = m.node_tree.nodes.get("Principled BSDF")
                    if bsdf and "Emission Strength" in bsdf.inputs:
                        bsdf.inputs["Emission Strength"].default_value = 0.18

    # Yamaha HS5-Style White-Cone Studio Monitors on Isolation Stands (TOED INWARD +15 / -15 deg toward user!)
    # Exclude 33 tiny hidden back screws (53k polys!) so front baffle & tweeter waveguide stay 100% un-decimated & razor-crisp!
    spk_l = import_blenderkit_glb(
        bk("maudio_speakers"), "BK_Speaker_Left", col_bk,
        target_height=0.232, location=(dx - 0.74, dy + 0.18, desk_h + 0.154),
        rotation_xyz_deg=(0.0, 0.0, 15.0), ground_z=desk_h + 0.154,
        exclude_substrings=("wire", "grid", "screw"), x_side_filter="neg",
    )
    style_speaker_white_cone(spk_l, mats["speaker_white_cone"])

    spk_r = import_blenderkit_glb(
        bk("maudio_speakers"), "BK_Speaker_Right", col_bk,
        target_height=0.232, location=(dx + 0.87, dy + 0.18, desk_h + 0.154),
        rotation_xyz_deg=(0.0, 0.0, -15.0), ground_z=desk_h + 0.154,
        exclude_substrings=("wire", "grid", "screw"), x_side_filter="pos",
    )
    style_speaker_white_cone(spk_r, mats["speaker_white_cone"])

    # === PEGBOARD REAL ARTIST HARDWARE (Physically resting ON 3D IKEA SKADIS hooks & mini-shelf!) ===
    # Pegboard anchor is (1.16, 2.04, 1.44):
    # 1. Studio Headphones resting directly on top-left wide headphone cradle hook (hook at x=1.00, y=1.978, z=1.654)
    import_blenderkit_glb(
        bk("headset_black"), "BK_PegHeadset", col_bk,
        target_height=0.205, location=(1.00, 1.976, 1.454),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=1.454,
        exclude_substrings=("stand", "base", "holder", "support"),
    )
    # 2. Real PS5 DualSense Controller seated inside mid-center twin cradle hooks (NO pre-decimation!)
    import_blenderkit_glb(
        bk("dualsense_ps5"), "BK_PegDualSense", col_bk,
        target_max_dim=0.160, location=(1.14, 2.006, 1.428),
        rotation_xyz_deg=(90.0, 0.0, 0.0), ground_z=None,
        exclude_substrings=("plane",),
    )
    # 3. Real Game Boy Color standing upright on top-right hooked steel mini-shelf (shelf top z=1.558)
    import_blenderkit_glb(
        bk("gameboy_color"), "BK_PegGameBoy", col_bk,
        target_max_dim=0.125, location=(1.235, 1.992, 1.621),
        rotation_xyz_deg=(90.0, 0.0, 0.0), ground_z=None,
    )
    # 4. Real 1-Piece Screwdriver hanging straight vertically inside mid-right tool U-ring (x=1.37, y=1.992, z=1.40)
    import_blenderkit_glb(
        bk("screwdriver_real"), "BK_PegScrewdriver", col_bk,
        target_max_dim=0.205, location=(1.37, 2.006, 1.375),
        rotation_xyz_deg=(90.0, 0.0, 0.0), ground_z=None,
    )

    # Clean Non-Scanned CAD-Modeled IKEA Markus Black Leather & Mesh High-Back Ergonomic Chair
    # Angled naturally left-rear (like someone stepped away for coffee) so the 49" Ultrawide & custom 75% keyboard stay unobstructed!
    import_blenderkit_glb(
        bk("markus_chair"), "BK_ErgoMeshChair", col_bk,
        target_height=1.18, location=(dx - 0.54, dy - 0.86, 0.0),
        rotation_xyz_deg=(0.0, 0.0, 126.0), ground_z=0.0,
    )

    # OFFICIAL APPLE.COM CAD MODEL: MacBook Air 15" Midnight resting flush on sculpted CNC Curved Aluminum Stand (13 deg tilt)!
    mb_air = import_apple_usdz(
        APPLE_DIR / "apple_macbook_air_15_midnight.usdz", "Apple_MacBookAir15", col_bk,
        location=(dx - 0.94, dy - 0.08, desk_h + 0.107),
        rotation_xyz_deg=(13.0, 0.0, 24.0), scale_factor=0.96, ground_z=None,
    )
    # Replace wallpaper on official Apple Retina display mesh (IcBMnlsGrUWaSql) with crisp macOS Terminal + CAD UI!
    for obj in mb_air.children_recursive:
        if obj.type == "MESH" and obj.name == "IcBMnlsGrUWaSql":
            obj.data.materials.clear()
            obj.data.materials.append(mats["screen_macbook"])

    # Unsolved Rubik's Cube resting right on the Grovemade Walnut Desk Shelf!
    import_blenderkit_glb(
        bk("rubik_cube"), "BK_RubikCube_Desk", col_bk,
        target_height=0.058, location=(dx + 0.40, dy + 0.11, shelf_top_z),
        rotation_xyz_deg=(0.0, 0.0, 32.0), ground_z=shelf_top_z,
    )
    # Removed cluttered right-edge Architect Scissor Lamp (redundant w/ ScreenBar + Flos IC Floor Lamp + Track Spots)
    # Removed bulky round grey bathroom-style Pedal Trash Bin next to walnut slats -> replaced w/ matte-black APC UPS & OP-1 synth in lived_in_storytelling!
    # Removed duplicate PS5 on Bookshelf Tier 1 (Zone 2 Living Room already owns the Midnight Black PS5!) -> replaced w/ 10" Geek Homelab Mini-Rack!

    # === HARDCORE MAKER WORKBENCH ZONE (East Front Wall: Double Matte-Charcoal IKEA Alex + 3D Printer + Filaments!) ===
    for slot_name, ay in (("BK_AlexDrawer_N", -0.39), ("BK_AlexDrawer_S", -1.09)):
        alex = import_blenderkit_glb(
            bk("ikea_alex_wide"), slot_name, col_bk,
            target_height=0.674, location=(1.88, ay, 0.0),
            rotation_xyz_deg=(0.0, 0.0, -90.0), ground_z=0.0,
        )
        for obj in alex.children_recursive:
            if obj.type == "MESH":
                obj.data.materials.clear()
                obj.data.materials.append(mats["alex_charcoal"])

    # Real Creality CR-10S Pro FDM 3D Printer (orange PLA spool on top!) resting on walnut maker bench (Z = 0.702)!
    import_blenderkit_glb(
        bk("printer_3d"), "BK_3DPrinter", col_bk,
        target_height=0.58, location=(1.88, -0.34, 0.702),
        rotation_xyz_deg=(0.0, 0.0, -84.0), ground_z=0.702,
        exclude_substrings=("220v cable",),
    )
    # 3 Stacked Real PLA Filament Spools cleanly centered behind cutting mat!
    import_blenderkit_glb(
        bk("filament_spools"), "BK_FilamentSpools", col_bk,
        target_width=0.31, location=(1.96, -0.78, 0.702),
        rotation_xyz_deg=(0.0, 0.0, -18.0), ground_z=0.702,
    )

    # Minimalist Flush 86mm Matte-Black Architectural Dual-Outlet + USB-C Wall Plates (crisp bevels, ZERO decimation artifacts!)
    for sx in (-1.18, 0.42):
        wy = 2.043
        wz = 0.32
        create_beveled_box(f"Arch_OutletPlate_{sx:+.2f}", (0.086, 0.009, 0.086), (sx, wy, wz), bevel=0.002, material=mats["anodized_black"], collection=col_bk)
        create_beveled_box(f"Arch_OutletInner_{sx:+.2f}", (0.068, 0.006, 0.068), (sx, wy - 0.003, wz), bevel=0.0015, material=mats["matte_plastic"], collection=col_bk)
        # Upper 2-pin slots + lower angled 3-pin architectural outlet slots + USB-C port
        for dx_s in (-0.010, 0.010):
            create_beveled_box(f"Arch_OutletPin2_{sx:+.2f}_{dx_s:+.3f}", (0.0035, 0.004, 0.011), (sx + dx_s, wy - 0.0055, wz + 0.016), bevel=0.0, material=mats["wall_concrete_seam"], collection=col_bk)
        create_beveled_box(f"Arch_OutletPinG_{sx:+.2f}", (0.0035, 0.004, 0.010), (sx, wy - 0.0055, wz - 0.006), bevel=0.0, material=mats["wall_concrete_seam"], collection=col_bk)
        for dx_s, rot_y in ((-0.011, 28.0), (0.011, -28.0)):
            create_beveled_box(f"Arch_OutletPin3_{sx:+.2f}_{dx_s:+.3f}", (0.0035, 0.004, 0.010), (sx + dx_s, wy - 0.0055, wz - 0.018), rotation=(0.0, math.radians(rot_y), 0.0), bevel=0.0, material=mats["wall_concrete_seam"], collection=col_bk)
        create_beveled_box(f"Arch_OutletUSBC_{sx:+.2f}", (0.009, 0.004, 0.0035), (sx + 0.022, wy - 0.0055, wz + 0.016), bevel=0.0005, material=mats["gunmetal"], collection=col_bk)

    # === 2. REAL GEEK GALLERY BOOKSHELF v8 (X = 1.92, Y = 0.14..1.90 — Official Apple Mac Studio + Mac mini!) ===
    sh_x = 1.92
    # TIER 5 (Top Z = 2.212): Sculptural top plant with RECOLORED matte-charcoal planter (ZERO orange garden terracotta!)
    top_plant = import_gltf_asset(
        ph("potted_plant_01"), "PH_TopShelfPlant1", col_ph,
        target_height=0.48, location=(sh_x - 0.02, 1.44, 2.212), rotation_z_deg=25.0, ground_z=2.212,
    )
    for obj in top_plant.children_recursive:
        if obj.type == "MESH" and obj.data.materials:
            for i, m in enumerate(obj.data.materials):
                if m and any(k in (obj.name.lower() + " " + m.name.lower()) for k in ("pot", "terracotta", "clay", "vase")):
                    obj.data.materials[i] = mats["ceramic_charcoal"]

    # TIER 4 (Z = 1.712): Grid Studio Teardown Frame + Canon 5D & AE-1 + Official Apple Mac Studio/mini + Gundam Zaku MK-II + PSP!
    import_blenderkit_glb(
        bk("canon_5d"), "BK_Canon5D_Shelf", col_bk,
        target_height=0.135, location=(sh_x - 0.05, 1.24, 1.762),
        rotation_xyz_deg=(0.0, 0.0, -68.0), ground_z=1.762,
    )
    import_blenderkit_glb(
        bk("vintage_35mm"), "BK_CanonAE1_Shelf", col_bk,
        target_height=0.11, location=(sh_x - 0.07, 1.56, 1.712),
        rotation_xyz_deg=(0.0, 0.0, -104.0), ground_z=1.712,
    )
    # Iconic Master-Grade Gundam Zaku MK-II Collectible (centered boldly inside front bay, clear of pothos vines!)
    import_blenderkit_glb(
        bk("zaku_gunpla"), "BK_ZakuGunpla", col_bk,
        target_height=0.255, location=(sh_x - 0.04, 0.43, 1.712),
        rotation_xyz_deg=(0.0, 0.0, -108.0), ground_z=1.712,
        exclude_substrings=("icosphere",),
    )
    # OFFICIAL APPLE.COM CAD MODELS: Stacked Mac Studio + Mac mini HomeLab Cluster facing -X directly into the room!
    import_apple_usdz(
        APPLE_DIR / "apple_mac_studio.usdz", "Apple_MacStudio", col_bk,
        location=(sh_x - 0.01, 0.71, 1.712), rotation_xyz_deg=(0.0, 0.0, -90.0), scale_factor=0.92, ground_z=1.712,
    )
    import_apple_usdz(
        APPLE_DIR / "apple_mac_mini.usdz", "Apple_MacMini", col_bk,
        location=(sh_x - 0.01, 0.71, 1.800), rotation_xyz_deg=(0.0, 0.0, -86.0), scale_factor=0.95, ground_z=1.800,
    )
    import_blenderkit_glb(
        bk("psp_handheld"), "BK_PSP_Shelf", col_bk,
        target_max_dim=0.155, location=(sh_x - 0.07, 0.94, 1.712),
        rotation_xyz_deg=(0.0, 0.0, -72.0), ground_z=1.712,
    )

    # TIER 3 (Z = 1.192 — Eye-Level Audio Vignette): Vinyl Turntable + Pixel Matrix Clock + Front-Facing LP Easel + Printed Dark LPs!
    import_blenderkit_glb(
        bk("vinyl_player"), "BK_VinylTurntable", col_bk,
        target_width=0.40, location=(sh_x - 0.02, 0.50, 1.192),
        rotation_xyz_deg=(0.0, 0.0, -90.0), ground_z=1.192,
    )

    # TIER 2 (Z = 0.672 — Apple Macintosh 1984 Centerpiece + Real CS/Design Books + Wire-Mesh Pen Organizer + Custom Keyboard!):
    import_blenderkit_glb(
        bk("macintosh_1984"), "BK_Macintosh1984", col_bk,
        target_height=0.34, location=(sh_x - 0.01, 1.62, 0.672),
        rotation_xyz_deg=(0.0, 0.0, -78.0), ground_z=0.672,
        exclude_substrings=("keyboard", "mouse", "cable"),
    )
    import_blenderkit_glb(
        bk("pen_holder"), "BK_PenOrganizer", col_bk,
        target_width=0.255, location=(sh_x - 0.04, 0.80, 0.672),
        rotation_xyz_deg=(0.0, 0.0, -84.0), ground_z=0.672,
    )
    build_organizer_pens_and_tools((sh_x - 0.04, 0.80, 0.672), rot_z_deg=-84.0, mats=mats, col=col_bk)

    kb_disp = import_blenderkit_glb(
        bk("mech_keyboard_75"), "BK_DisplayKeyboard_Shelf", col_bk,
        target_width=0.325, location=(sh_x - 0.07, 0.42, 0.77),
        rotation_xyz_deg=(46.0, 0.0, -90.0), ground_z=0.732,
    )
    style_75_keyboard_pbt(kb_disp)

    # === 3. REMOVED STAGE FRESNEL SPOTLIGHT (Replaced by Tokyo Minimalist Opal-Globe Floor Lamp in lived_in_storytelling!) ===

    # === 4. CONTEMPORARY TOKYO WEST WINDOW READING NOOK (Monstera pulled clear + modern plush fabric lounge chair!) ===
    import_blenderkit_glb(
        bk("monstera_big"), "BK_MonsteraDeliciosa", col_bk,
        target_height=1.42, location=(-1.66, -1.16, 0.0),
        rotation_xyz_deg=(0.0, 0.0, 58.0), ground_z=0.0,
    )
    guide_p = bk("chair_guide_mod")
    import_blenderkit_glb(
        guide_p if guide_p.exists() else bk("chair_loafer_velvet"),
        "BK_StudioLoungeChair", col_bk,
        target_width=0.82, location=(-1.24, -0.84, 0.0),
        rotation_xyz_deg=(0.0, 0.0, 132.0), ground_z=0.0,
    )


def build_studio_slice() -> Path:
    clear_scene()
    configure_cycles_metal(samples=96)

    screen_images = generate_all_studio_screens(CACHE_DIR / "screens")
    mats = build_studio_material_palette(screen_images)

    col_arch = ensure_collection("01_Architecture")
    col_hero = ensure_collection("02_Desk_And_Displays")
    col_bk = ensure_collection("03_BlenderKit_Artists")
    col_ph = ensure_collection("04_PolyHaven_CC0")
    col_lights = ensure_collection("05_Lights")

    colliders = build_concept_a_architecture(mats, col_arch)
    build_skyline_cyclorama(col_arch)

    desk_origin = (-0.22, 1.46, 0.0)
    build_standing_desk(desk_origin, mats, col_hero)
    build_grovemade_desk_shelf(desk_origin, mats, col_hero)
    build_monitors_screenbar_and_streamdeck(desk_origin, mats, col_hero)
    build_concept_a_mic_boom_arm(desk_origin, mats, col_hero)
    build_lived_in_desk_details(desk_origin, mats, col_hero)
    build_desk_papers_laptop_stand_and_notes(desk_origin, mats, col_hero)

    # Warm Architectural Back Wall: Left Vertical Walnut Acoustic Slats + 1.58m Floating Walnut Shelf + 2700K Wash!
    build_back_wall_floating_shelf_and_slats(wall_y=2.04, mats=mats, col=col_hero)

    # East Maker Workbench Countertop (unifying Double Charcoal IKEA Alex Drawers) + Compact Wireless Laser Printer!
    build_maker_workbench_counter(location=(1.88, -0.74, 0.0), mats=mats, col=col_hero)
    build_compact_desktop_printer(location=(1.88, -1.16, 0.702), rot_z_deg=0.0, mats=mats, col=col_hero)

    # PC Tower neatly aligned SQUARE (0 deg) on rolling matte-black PC floor caddy with 14.4cm ZERO-CLIP clearance from Desk_Foot_R!
    pc_loc = (0.86, 1.48, 0.0)
    build_pc_rolling_caddy(location=pc_loc, rot_z_deg=0.0, mats=mats, col=col_hero)
    build_concept_a_pc_tower(
        location=(pc_loc[0], pc_loc[1], 0.043), rot_z_deg=0.0, mats=mats, col=col_hero,
        fan_glb_path=BK_DIR / "pc_fan_core" / "pc_fan_core.glb",
    )

    # Visible Ceiling Magnetic Track Rail + 3 Glowing Matte-Black Cylindrical Spotlights
    build_concept_a_track_lighting(center_x=-0.06, y_pos=1.08, ceiling_z=2.76, span_w=3.20, mats=mats, col=col_hero)

    # Crisp Matte-Black IKEA SKADIS Pegboard (aligned with real artist headset, DualSense, Game Boy & 1-piece screwdriver!)
    build_concept_a_pegboard(location=(1.16, 2.04, 1.44), mats=mats, col=col_hero)

    # Lush Cascading Trailing Pothos Vines on top-front corner of the curated 2-bay bookshelf!
    build_cascading_pothos_vines(pot_location=(1.82, 0.34, 2.212), mats=mats, col=col_hero)

    # Walnut Tripod Side Table positioned cleanly at arm's reach beside the inward-facing reading chair (zero overlap)!
    build_cozy_reading_nook_details(table_location=(-1.74, -0.16, 0.0), mats=mats, col=col_hero)

    place_real_artist_models(desk_origin, mats, col_bk, col_ph)
    apply_studio_mood("midnight", col_lights)

    BLEND_DIR.mkdir(parents=True, exist_ok=True)
    (BLEND_DIR / "studio_colliders.json").write_text(json.dumps(colliders, indent=2), encoding="utf-8")

    try:
        bpy.ops.file.pack_all()
    except Exception as exc:
        print("Pack warning:", exc)

    out_blend = BLEND_DIR / "studio_slice.blend"
    bpy.ops.wm.save_as_mainfile(filepath=str(out_blend))

    mesh_objs = [o for o in bpy.data.objects if o.type == "MESH"]
    total_polys = sum(len(o.data.polygons) for o in mesh_objs)
    print(f"BUILT Studio Slice v6 (Authentic Geek + Artist Hardware + Venetian Blinds) studio_slice.blend: {len(mesh_objs)} mesh objects, {total_polys:,} base polygons.")
    return out_blend


if __name__ == "__main__":
    build_studio_slice()
