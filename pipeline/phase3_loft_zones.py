"""
Phase 3 Full 5-Zone Tokyo Industrial Geek Loft Builder (11.6m x 7.5m x 2.76m = 87 m^2):
- Preserves perfected Zone 1 Studio & Maker Workbench (X=-2.18..+2.18, Y=-1.95..+2.05) 100% intact!
- Adds seamless continuous architectural shell, 7.5m West Loft Window + Venetian Blinds, and open portals:
  * Zone 2: Living & Console Gaming Lounge (77" OLED TV, Charcoal Modular Sofa, Walnut Coffee Table, PS5, Atmos Towers)
  * Zone 3: Open Kitchen & Dark Calacatta Marble Waterfall Espresso Bar Island (Espresso Machine, Grinder, 3 Stools, Pendant)
  * Zone 4: Master Bedroom with Matte-Black Steel & Fluted-Glass Sliding Partition (Floating JP Bed, Smoked-Glass Wardrobe)
  * Zone 5: Modern Japanese Spa Bathroom (Freestanding Soaking Tub, Walnut Vanity + Vessel Basin + Backlit Mirror, Rain Shower)
"""

import math
from pathlib import Path
import bmesh
import bpy
from mathutils import Vector

from config import CACHE_DIR, MODEL_DIR
from hero_studio_assets import (
    _new_group,
    _parent_all,
    build_venetian_blinds,
    create_curve_tube,
)
from mesh_utils import (
    create_beveled_box,
    create_beveled_cylinder,
    import_blenderkit_glb,
    import_gltf_asset,
)

BK_DIR = CACHE_DIR / "blenderkit"


def _add_uv_quad(
    name: str,
    verts_4: list[tuple[float, float, float]],
    material: bpy.types.Material,
    col: bpy.types.Collection,
) -> bpy.types.Object:
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    f = bm.faces.new([bm.verts.new(v) for v in verts_4])
    f.loops[0][uv].uv = (0.0, 0.0)
    f.loops[1][uv].uv = (1.0, 0.0)
    f.loops[2][uv].uv = (1.0, 1.0)
    f.loops[3][uv].uv = (0.0, 1.0)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj


def _create_lathe_mesh(
    name: str,
    profile_rz: list[tuple[float, float]],
    location: tuple[float, float, float],
    material: bpy.types.Material,
    col: bpy.types.Collection,
    segments: int = 32,
) -> bpy.types.Object:
    """Create a smooth lathe-spun hollow or solid rotational mesh from (radius, z) profile points."""
    bm = bmesh.new()
    rings: list[list[bmesh.types.BMVert]] = []
    for r, z in profile_rz:
        if r <= 1e-5:
            v = bm.verts.new((0.0, 0.0, z))
            rings.append([v])
        else:
            ring = [
                bm.verts.new((r * math.cos(2.0 * math.pi * i / segments), r * math.sin(2.0 * math.pi * i / segments), z))
                for i in range(segments)
            ]
            rings.append(ring)

    for ri in range(len(rings) - 1):
        a, b = rings[ri], rings[ri + 1]
        if len(a) == 1 and len(b) > 1:
            for i in range(segments):
                bm.faces.new((a[0], b[i], b[(i + 1) % segments]))
        elif len(a) > 1 and len(b) == 1:
            for i in range(segments):
                bm.faces.new((a[i], a[(i + 1) % segments], b[0]))
        elif len(a) > 1 and len(b) > 1:
            for i in range(segments):
                j = (i + 1) % segments
                bm.faces.new((a[i], a[j], b[j], b[i]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        f.smooth = True
        for lp in f.loops:
            co = lp.vert.co
            lp[uv].uv = (math.atan2(co.y, co.x) / (2.0 * math.pi) + 0.5, co.z * 2.5)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj


def _recolor_hierarchy(root: bpy.types.Object, mat: bpy.types.Material, match_substrings: tuple[str, ...] | None = None) -> None:
    for o in root.children_recursive:
        if o.type != "MESH":
            continue
        if match_substrings is None:
            o.data.materials.clear()
            o.data.materials.append(mat)
        else:
            for i, m in enumerate(list(o.data.materials)):
                lname = (o.name + " " + (m.name if m else "")).lower()
                if any(k in lname for k in match_substrings):
                    o.data.materials[i] = mat


def build_loft_extended_architecture(
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> list[dict]:
    """
    Replaces Studio-only South/East closure walls with the full 11.6m x 7.5m 5-zone architectural shell,
    keeping Zone 1 Studio North wall, West window, floor & bookshelf wall 100% aligned!
    Names objects with `West_` or `East_` prefixes for crisp dual-atlas 2048px HDR OIDN lightmapping!
    """
    h = 2.76
    wt = 0.22
    # Remove closed Studio-only South/East walls AND Studio-only overlapping Floor/Ceiling slabs
    # so the entire 5-zone Loft uses 100% MATHEMATICALLY DISJOINT, ZERO-OVERLAP, ZERO-Z-FIGHTING floors & ceilings!
    for old_name in ("Arch_Wall_South", "Arch_Wall_East", "Arch_Baseboard_E", "Arch_Floor", "Arch_Ceiling"):
        old = bpy.data.objects.get(old_name)
        if old:
            bpy.data.objects.remove(old, do_unlink=True)

    # === 1. STUDIO <-> LIVING ARCHITECTURAL PORTAL (Y = -1.95) & STUDIO/KITCHEN SPINE (X = +2.18) ===
    # Spine wall behind Studio Bookshelf & Maker Workbench (Y = -1.60..+2.05, West face = +2.18, East face = +2.36!)
    create_beveled_box("Arch_West_SpineWall_W", (0.09, 3.70, h), (2.225, 0.25, h * 0.5), bevel=0.004, material=mats["wall_concrete"], uv_scale=0.85, collection=col)
    create_beveled_box("Arch_East_SpineWall_E", (0.09, 3.70, h), (2.315, 0.25, h * 0.5), bevel=0.004, material=mats["wall_concrete"], uv_scale=0.85, collection=col)
    create_beveled_box("Arch_Baseboard_SpineW", (0.010, 3.65, 0.048), (2.175, 0.225, 0.024), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_Baseboard_SpineE", (0.010, 3.65, 0.048), (2.365, 0.225, 0.024), bevel=0.002, material=mats["anodized_black"], collection=col)

    # Studio <-> Living wide 3.20m open portal at Y = -1.95:
    # Continuous FULL-WIDTH lintel beam (Z = 2.48..2.76) resting flush ON TOP of both piers (Z = 0..2.48) -> ZERO left/right seam step!
    create_beveled_box("Arch_West_PortalPierL", (0.68, 0.18, 2.48), (-1.84, -1.95, 1.24), bevel=0.0, material=mats["wall_concrete"], uv_scale=0.8, collection=col)
    create_beveled_box("Arch_West_PortalPierR", (0.66, 0.18, 2.48), (2.03, -1.95, 1.24), bevel=0.0, material=mats["wall_concrete"], uv_scale=0.8, collection=col)
    create_beveled_box("Arch_West_PortalHeader", (4.54, 0.18, 0.28), (0.09, -1.95, 2.62), bevel=0.0, material=mats["wall_concrete"], uv_scale=0.8, collection=col)
    # Crisp matte-black steel portal reveal casing (exact 3.20m opening X = -1.50..+1.70)
    create_beveled_box("Arch_PortalSteel_L", (0.024, 0.20, 2.48), (-1.49, -1.95, 1.24), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_PortalSteel_R", (0.024, 0.20, 2.48), (1.69, -1.95, 1.24), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_PortalSteel_Top", (3.20, 0.20, 0.028), (0.10, -1.95, 2.47), bevel=0.002, material=mats["anodized_black"], collection=col)

    # === 2. MATHEMATICALLY DISJOINT, ZERO-OVERLAP, ZERO-Z-FIGHTING FULL-LOFT FLOORS & CEILINGS ===
    # West Atlas:
    #   Studio Floor:  X = [-2.22, +2.40] (w=4.62, cx=+0.09), Y = [-1.95, +2.06] (d=4.01, cy=+0.055)
    #   Living Floor:  X = [-2.22, +4.68] (w=6.90, cx=+1.23), Y = [-5.46, -1.95] (d=3.51, cy=-3.705)
    #   -> Meets Studio at EXACT Y = -1.950 (0.000mm overlap, 0.000mm gap!)
    create_beveled_box("Arch_West_FloorStudio", (4.62, 4.01, 0.14), (0.09, 0.055, -0.07), bevel=0.0, material=mats["floor_parquet"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_West_CeilingStudio", (4.62, 4.01, 0.16), (0.09, 0.055, h + 0.08), bevel=0.0, material=mats["ceiling_plaster"], uv_scale=0.65, collection=col)
    create_beveled_box("Arch_West_FloorLiving", (6.90, 3.51, 0.14), (1.23, -3.705, -0.07), bevel=0.0, material=mats["floor_parquet"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_West_CeilingLiving", (6.90, 3.51, 0.16), (1.23, -3.705, h + 0.08), bevel=0.0, material=mats["ceiling_plaster"], uv_scale=0.65, collection=col)
    # South Concrete Feature Wall (Zone 2 Living TV Wall: X = -2.18..+4.68, Y = -5.45)
    create_beveled_box("Arch_West_WallSouthLiving", (7.10, wt, h), (1.25, -5.45 - wt * 0.5, h * 0.5), bevel=0.004, material=mats["wall_concrete"], uv_scale=0.80, collection=col)
    create_beveled_box("Arch_Baseboard_SouthLiving", (6.86, 0.010, 0.048), (1.25, -5.445, 0.024), bevel=0.002, material=mats["anodized_black"], collection=col)

    # Continuous West Floor-to-Ceiling Matte-Black Steel-Grid Loft Window along Living Lounge (Y = -5.32..-2.06)!
    x0 = -2.18
    wy0, wy1 = -5.32, -2.06
    wz0, wz1 = 0.06, 2.68
    ww, wh, wcy = wy1 - wy0, wz1 - wz0, (wy0 + wy1) * 0.5
    create_beveled_box("Arch_West_LivPierS", (wt, 0.35, h), (x0 - wt * 0.5, -5.46, h * 0.5), bevel=0.004, material=mats["wall_concrete"], collection=col)
    create_beveled_box("Arch_West_LivCurb", (wt, ww, wz0), (x0 - wt * 0.5, wcy, wz0 * 0.5), bevel=0.003, material=mats["wall_concrete"], collection=col)
    create_beveled_box("Arch_West_LivLintel", (wt, ww, h - wz1), (x0 - wt * 0.5, wcy, (wz1 + h) * 0.5), bevel=0.003, material=mats["wall_concrete"], collection=col)

    fx = x0 - wt * 0.42
    create_beveled_box("Arch_LivWin_Bot", (0.084, ww, 0.044), (fx, wcy, wz0 + 0.022), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_LivWin_Top", (0.084, ww, 0.044), (fx, wcy, wz1 - 0.022), bevel=0.003, material=mats["anodized_black"], collection=col)
    for i in range(5):
        my = wy0 + (i / 4.0) * ww
        thick = 0.048 if i in (0, 2, 4) else 0.032
        create_beveled_box(f"Arch_LivWin_V_{i}", (0.084 if i in (0, 2, 4) else 0.058, thick, wh), (fx, my, (wz0 + wz1) * 0.5), bevel=0.003, material=mats["anodized_black"], collection=col)
    for j in range(1, 5):
        mz = wz0 + (j / 5.0) * wh
        create_beveled_box(f"Arch_LivWin_H_{j}", (0.056, ww, 0.028), (fx, wcy, mz), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_LivWin_Glass", (0.008, ww - 0.04, wh - 0.04), (fx, wcy, (wz0 + wz1) * 0.5), bevel=0.0, material=mats["window_glass"], collection=col)
    build_venetian_blinds(x_pos=x0 + 0.032, y0=wy0, y1=wy1, z_bot=1.72, z_top=2.66, mats=mats, col=col, slat_tilt_deg=22.0)

    # === 3. ZONE 3 OPEN KITCHEN, ZONE 4 MASTER BEDROOM & ZONE 5 SPA BATHROOM SHELL (Atlas: East) ===
    # 100% MATHEMATICALLY DISJOINT, ZERO-OVERLAP, ZERO-GAP East Floors & Ceilings (ALL top Z = 0.000, ZERO threshold seam in kitchen!):
    #   KitWest (unbroken Kitchen + Corridor!): X = [+2.40, +4.68] (w=2.28, cx=+3.54), Y = [-1.95, +2.06] (d=4.01, cy=+0.055)
    #   KitEast:                                X = [+4.68, +6.46] (w=1.78, cx=+5.57), Y = [-1.45, +2.06] (d=3.51, cy=+0.305)
    #   Bedroom:                                X = [+4.68, +9.44] (w=4.76, cx=+7.06), Y = [-5.46, -1.45] (d=4.01, cy=-3.455)
    #   Bath:                                   X = [+6.46, +9.44] (w=2.98, cx=+7.95), Y = [-1.45, +2.06] (d=3.51, cy=+0.305)
    create_beveled_box("Arch_East_FloorKitWest", (2.28, 4.01, 0.14), (3.54, 0.055, -0.07), bevel=0.0, material=mats["floor_parquet"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_FloorKitEast", (1.78, 3.51, 0.14), (5.57, 0.305, -0.07), bevel=0.0, material=mats["floor_parquet"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_FloorBedroom", (4.76, 4.01, 0.14), (7.06, -3.455, -0.07), bevel=0.0, material=mats["floor_parquet"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_FloorBath", (2.98, 3.51, 0.14), (7.95, 0.305, -0.07), bevel=0.0, material=mats["spa_stone_tile"], uv_scale=0.85, collection=col)

    # Matching 100% Zero-Overlap East Ceilings!
    create_beveled_box("Arch_East_CeilingKitWest", (2.28, 4.01, 0.16), (3.54, 0.055, h + 0.08), bevel=0.0, material=mats["ceiling_plaster"], uv_scale=0.65, collection=col)
    create_beveled_box("Arch_East_CeilingKitEast", (1.78, 3.51, 0.16), (5.57, 0.305, h + 0.08), bevel=0.0, material=mats["ceiling_plaster"], uv_scale=0.65, collection=col)
    create_beveled_box("Arch_East_CeilingBedroom", (4.76, 4.01, 0.16), (7.06, -3.455, h + 0.08), bevel=0.0, material=mats["ceiling_plaster"], uv_scale=0.65, collection=col)
    create_beveled_box("Arch_East_CeilingBath", (2.98, 3.51, 0.16), (7.95, 0.305, h + 0.08), bevel=0.0, material=mats["ceiling_plaster"], uv_scale=0.65, collection=col)

    # Outer Perimeter Walls (North Kitchen/Bath Y=+2.05, East Bedroom/Bath X=+9.42, South Bedroom Y=-5.45)
    create_beveled_box("Arch_East_WallNorthKitchen", (4.20, wt, h), (4.28, 2.05 + wt * 0.5, h * 0.5), bevel=0.004, material=mats["wall_concrete"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_WallNorthBath", (3.16, wt, h), (7.94, 2.05 + wt * 0.5, h * 0.5), bevel=0.004, material=mats["spa_stone_tile"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_WallEastBed", (wt, 4.04, h), (9.42 + wt * 0.5, -3.45, h * 0.5), bevel=0.004, material=mats["wall_microcement"], uv_scale=0.80, collection=col)
    create_beveled_box("Arch_East_WallEastBath", (wt, 3.54, h), (9.42 + wt * 0.5, 0.30, h * 0.5), bevel=0.004, material=mats["spa_stone_tile"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_WallSouthBed", (4.96, wt, h), (7.05, -5.45 - wt * 0.5, h * 0.5), bevel=0.004, material=mats["wall_microcement"], uv_scale=0.80, collection=col)

    # Kitchen <-> Spa Bathroom Divider Wall (X = +6.38..+6.54, Y = -1.45..+2.05)
    create_beveled_box("Arch_East_WallKitBath_W", (0.08, 3.54, h), (6.42, 0.30, h * 0.5), bevel=0.003, material=mats["wall_concrete"], uv_scale=0.80, collection=col)
    create_beveled_box("Arch_East_WallKitBath_E", (0.08, 3.54, h), (6.50, 0.30, h * 0.5), bevel=0.003, material=mats["spa_stone_tile"], uv_scale=0.82, collection=col)

    # Master Bedroom <-> Spa Bathroom Divider Wall (Y = -1.45, Open Doorway at X = 7.15..8.15!)
    # Split cleanly into Bedroom-facing microcement half (Y=-1.49) & Bathroom-facing dark-slate tile half (Y=-1.41)
    # so ALL 4 interior bathroom walls around toilet, shower & tub are 100% cohesive dark-slate spa tile!
    create_beveled_box("Arch_East_BathWallS_L_Bed", (0.78, 0.08, h), (6.77, -1.49, h * 0.5), bevel=0.002, material=mats["wall_microcement"], uv_scale=0.80, collection=col)
    create_beveled_box("Arch_East_BathWallS_L_Tile", (0.78, 0.08, h), (6.77, -1.41, h * 0.5), bevel=0.002, material=mats["spa_stone_tile"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_BathWallS_R_Bed", (1.28, 0.08, h), (8.79, -1.49, h * 0.5), bevel=0.002, material=mats["wall_microcement"], uv_scale=0.80, collection=col)
    create_beveled_box("Arch_East_BathWallS_R_Tile", (1.28, 0.08, h), (8.79, -1.41, h * 0.5), bevel=0.002, material=mats["spa_stone_tile"], uv_scale=0.82, collection=col)
    create_beveled_box("Arch_East_BathDoorHeader_Bed", (1.02, 0.08, 0.32), (7.66, -1.49, 2.60), bevel=0.002, material=mats["wall_microcement"], uv_scale=0.80, collection=col)
    create_beveled_box("Arch_East_BathDoorHeader_Tile", (1.02, 0.08, 0.32), (7.66, -1.41, 2.60), bevel=0.002, material=mats["spa_stone_tile"], uv_scale=0.82, collection=col)
    # Matte-black minimalist bathroom doorway casing
    create_beveled_box("Arch_BathDoorFrame_L", (0.024, 0.18, 2.44), (7.16, -1.45, 1.22), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_BathDoorFrame_R", (0.024, 0.18, 2.44), (8.16, -1.45, 1.22), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_BathDoorFrame_T", (1.02, 0.18, 0.024), (7.66, -1.45, 2.44), bevel=0.002, material=mats["anodized_black"], collection=col)

    # Kitchen <-> Master Bedroom North Header Partition (Y = -1.45, X = +4.68..+6.38)
    create_beveled_box("Arch_East_WallKitBed", (1.72, 0.16, h), (5.54, -1.45, h * 0.5), bevel=0.003, material=mats["wall_concrete"], uv_scale=0.80, collection=col)

    # === 4. SIGNATURE BLACK-STEEL & FLUTED-GLASS SLIDING BEDROOM PARTITION (X = +4.68, Y = -5.45..-1.45) ===
    # Fixed fluted-glass 3-bay section: Y = -5.45..-3.15; Open walk-through doorway: Y = -3.15..-1.55!
    px = 4.68
    create_beveled_box("Arch_Fluted_TopTrack", (0.075, 4.02, 0.055), (px, -3.45, h - 0.028), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_Fluted_BotTrack", (0.055, 2.34, 0.032), (px, -4.30, 0.016), bevel=0.002, material=mats["anodized_black"], collection=col)
    for fy in (-5.44, -4.68, -3.92, -3.15, -1.53):
        create_beveled_box(f"Arch_Fluted_Post_{fy:+.2f}", (0.048, 0.036, h - 0.04), (px, fy, (h - 0.04) * 0.5), bevel=0.002, material=mats["anodized_black"], collection=col)
    for fz in (0.92, 1.84):
        create_beveled_box(f"Arch_Fluted_Bar_{fz:.2f}", (0.042, 2.30, 0.026), (px, -4.30, fz), bevel=0.002, material=mats["anodized_black"], collection=col)
    # Sculpted vertical reeded/fluted architectural glass ribs across the fixed 2.30m bay!
    create_beveled_box("Arch_Fluted_GlassSheet", (0.012, 2.26, h - 0.10), (px, -4.30, h * 0.5), bevel=0.0, material=mats["fluted_glass"], collection=col)
    for ri in range(36):
        ry = -5.40 + (ri + 0.5) * (2.22 / 36.0)
        create_beveled_cylinder(f"Arch_Fluted_Rib_{ri:02d}", 0.014, h - 0.12, 8, 0.0, location=(px, ry, h * 0.5), material=mats["fluted_glass"], collection=col)
    # Open sliding steel & fluted-glass door leaf parked neatly beside the fixed bay (X = +4.62, Y = -4.25..-3.18)
    create_beveled_box("Arch_FlutedSlide_FrameL", (0.036, 0.036, h - 0.08), (px - 0.06, -4.22, h * 0.5 - 0.02), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_FlutedSlide_FrameR", (0.036, 0.036, h - 0.08), (px - 0.06, -3.18, h * 0.5 - 0.02), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Arch_FlutedSlide_Handle", (0.056, 0.020, 0.36), (px - 0.06, -3.25, 1.08), bevel=0.003, material=mats["brushed_brass"], collection=col)
    create_beveled_box("Arch_FlutedSlide_Glass", (0.010, 1.00, h - 0.14), (px - 0.06, -3.70, h * 0.5 - 0.02), bevel=0.0, material=mats["fluted_glass"], collection=col)

    # Full Multi-Room Walkable Colliders (Three.js Z = -Blender Y!)
    # Tightly matched to exact furniture & wall footprints so EVERY doorway & 360-deg island/sofa loop is 100% walkable!
    colliders = [
        {"name": "loft_outer_bounds", "type": "bounds", "minX": -1.96, "maxX": 9.20, "minZ": -1.85, "maxZ": 5.24},
        # Studio furniture
        {"name": "standing_desk", "type": "box", "minX": -1.36, "maxX": 0.92, "minZ": -1.98, "maxZ": -1.04},
        {"name": "studio_bookshelf_spine", "type": "box", "minX": 1.76, "maxX": 2.38, "minZ": -2.02, "maxZ": 1.54},
        {"name": "studio_lounge_chair", "type": "box", "minX": -1.98, "maxX": -1.04, "minZ": 0.58, "maxZ": 1.54},
        # Studio <-> Living portal piers (Y=-1.95 -> Z=+1.95)
        {"name": "portal_pier_w", "type": "box", "minX": -2.20, "maxX": -1.48, "minZ": 1.84, "maxZ": 2.06},
        {"name": "portal_pier_e", "type": "box", "minX": 1.44, "maxX": 2.34, "minZ": 1.84, "maxZ": 2.06},
        # Living Lounge furniture (open walkways on West, East, North behind sofa & South in front of OLED TV!)
        {"name": "living_sofa", "type": "box", "minX": -0.45, "maxX": 2.25, "minZ": 2.52, "maxZ": 3.44},
        {"name": "living_loafer_chair", "type": "box", "minX": 2.52, "maxX": 3.36, "minZ": 3.06, "maxZ": 3.90},
        {"name": "entry_foyer_console", "type": "box", "minX": 2.74, "maxX": 3.44, "minZ": 5.04, "maxZ": 5.45},
        {"name": "living_coffee_table", "type": "box", "minX": 0.37, "maxX": 1.43, "minZ": 3.86, "maxZ": 4.58},
        {"name": "living_nested_table", "type": "box", "minX": 1.50, "maxX": 2.02, "minZ": 3.84, "maxZ": 4.34},
        {"name": "living_media_console", "type": "box", "minX": -0.90, "maxX": 2.75, "minZ": 4.96, "maxZ": 5.45},
        # Kitchen cabinetry & marble waterfall island (full 360-deg walkable loop around island!)
        {"name": "kitchen_north_counter", "type": "box", "minX": 2.42, "maxX": 6.38, "minZ": -2.05, "maxZ": -1.36},
        {"name": "kitchen_marble_island", "type": "box", "minX": 2.98, "maxX": 5.52, "minZ": -0.30, "maxZ": 0.86},
        # Fluted glass wall fixed section (X=4.68, Z=3.16..5.45; wide 1.62m open sliding doorway Z=1.54..3.16!)
        {"name": "fluted_glass_fixed", "type": "box", "minX": 4.58, "maxX": 4.78, "minZ": 3.16, "maxZ": 5.45},
        # Kitchen <-> Bath & Bedroom <-> Bath walls (wide 1.00m doorway X=7.16..8.16 at Z=1.45 open!)
        {"name": "wall_kit_bath", "type": "box", "minX": 6.36, "maxX": 6.56, "minZ": -2.05, "maxZ": 1.54},
        {"name": "wall_kit_bed", "type": "box", "minX": 4.66, "maxX": 6.46, "minZ": 1.37, "maxZ": 1.54},
        {"name": "wall_bath_door_l", "type": "box", "minX": 6.42, "maxX": 7.16, "minZ": 1.37, "maxZ": 1.54},
        {"name": "wall_bath_door_r", "type": "box", "minX": 8.16, "maxX": 9.45, "minZ": 1.37, "maxZ": 1.54},
        # Bedroom bed, bench & Porada Italian wardrobe (wide walkway to Spa Bathroom + 1.54m promenade by fluted glass!)
        {"name": "master_bed", "type": "box", "minX": 7.06, "maxX": 9.42, "minZ": 2.38, "maxZ": 4.52},
        {"name": "bedroom_bench", "type": "box", "minX": 6.34, "maxX": 6.78, "minZ": 2.72, "maxZ": 4.18},
        {"name": "bedroom_wardrobe", "type": "box", "minX": 4.94, "maxX": 8.32, "minZ": 4.82, "maxZ": 5.45},
        # Spa Bathroom fixtures (exact shower glass X=7.30..7.42, Z=-0.48..+0.64 -> wide open walk-in shower & tub access!)
        {"name": "spa_bathtub", "type": "box", "minX": 7.56, "maxX": 9.22, "minZ": -1.85, "maxZ": -1.04},
        {"name": "spa_vanity", "type": "box", "minX": 8.86, "maxX": 9.42, "minZ": -0.78, "maxZ": 0.42},
        {"name": "spa_shower_glass", "type": "box", "minX": 7.30, "maxX": 7.42, "minZ": -0.48, "maxZ": 0.64},
    ]
    return colliders


def build_zone2_living_lounge(
    mats: dict[str, bpy.types.Material],
    col_hero: bpy.types.Collection,
    col_bk: bpy.types.Collection,
) -> None:
    """Zone 2 — Living & Console Gaming Lounge (X=-2.18..+4.68, Y=-5.45..-1.95)."""
    bk = lambda slot: BK_DIR / slot / f"{slot}.glb"
    cx = 0.90  # Centered cleanly on the main lounge axis!

    # 1. South Concrete Feature Wall Vertical Walnut Acoustic Slat Wings flanking the 77" OLED TV
    for side, sx0, sx1 in (("L", -0.95, -0.25), ("R", 2.05, 2.75)):
        create_beveled_box(f"Liv_SlatFelt_{side}", (sx1 - sx0, 0.012, 2.66), ((sx0 + sx1) * 0.5, -5.435, 1.38), bevel=0.001, material=mats["acoustic_felt"], collection=col_hero)
        count = 14
        step = (sx1 - sx0) / count
        for i in range(count):
            sx = sx0 + (i + 0.5) * step
            create_beveled_box(f"Liv_WalnutSlat_{side}_{i:02d}", (step * 0.54, 0.024, 2.66), (sx, -5.418, 1.38), bevel=0.002, material=mats["walnut_slat"], uv_scale=1.0, collection=col_hero)

    # 2. 77" Wall-Mounted Ultra-Slim OLED Cinema TV (1.72m x 0.97m) facing +Y toward Sofa!
    tv_z = 1.34
    create_beveled_box("Liv_OLED77_Body", (1.72, 0.022, 0.97), (cx, -5.40, tv_z), bevel=0.003, material=mats["anodized_black"], collection=col_hero)
    create_beveled_box("Liv_OLED77_BiasLED", (1.54, 0.010, 0.80), (cx, -5.425, tv_z), bevel=0.002, material=mats["emissive_shelf_led"], collection=col_hero)
    # Screen quad facing +Y (looking from +Y toward -Y: +X is left u=0, -X is right u=1!)
    sw, sh = 1.69, 0.945
    _add_uv_quad(
        "Liv_OLED77_Screen",
        [
            (cx + sw * 0.5, -5.387, tv_z - sh * 0.5),
            (cx - sw * 0.5, -5.387, tv_z - sh * 0.5),
            (cx - sw * 0.5, -5.387, tv_z + sh * 0.5),
            (cx + sw * 0.5, -5.387, tv_z + sh * 0.5),
        ],
        mats["screen_living_tv"],
        col_hero,
    )

    # 3. 2.60m Floating Dark Oiled Walnut Media Console + Recessed 2700K Under-Glow + Sonos Arc Soundbar!
    create_beveled_box("Arch_West_MediaConsoleTop", (2.62, 0.44, 0.032), (cx, -5.21, 0.504), bevel=0.004, material=mats["walnut_desk"], uv_scale=0.85, collection=col_hero)
    create_beveled_box("Liv_ConsoleBody", (2.58, 0.41, 0.25), (cx, -5.22, 0.365), bevel=0.004, material=mats["kitchen_matte_black"], collection=col_hero)
    for di in range(4):
        dx = cx - 0.96 + di * 0.64
        create_beveled_box(f"Liv_ConsoleDoor_{di}", (0.61, 0.018, 0.23), (dx, -5.01, 0.365), bevel=0.003, material=mats["walnut_desk"], uv_scale=0.9, collection=col_hero)
    create_beveled_box("Liv_ConsoleUnderLED", (2.30, 0.016, 0.006), (cx, -5.20, 0.235), bevel=0.001, material=mats["emissive_shelf_led"], collection=col_hero)
    # Sonos Arc Dolby Atmos Matte-Black Soundbar centered atop media console
    create_beveled_box("Liv_SonosArc", (1.14, 0.11, 0.082), (cx, -5.16, 0.561), bevel=0.022, segments=3, material=mats["matte_plastic"], collection=col_hero)

    # 4. Pair of Sculpted Matte-Black & Walnut Hi-Fi Floorstanding Atmos Towers flanking media console!
    for side, tx in (("L", cx - 1.56), ("R", cx + 1.56)):
        g = _new_group(f"Liv_HiFiTower_{side}", (tx, -5.18, 0.0), col_hero, rot_z_deg=10.0 if side == "L" else -10.0)
        tp = [
            create_beveled_box(f"TowerPlinth_{side}", (0.28, 0.34, 0.024), (0.0, 0.0, 0.012), bevel=0.004, material=mats["anodized_black"], collection=col_hero),
            create_beveled_box(f"TowerCab_{side}", (0.23, 0.29, 1.04), (0.0, 0.0, 0.544), bevel=0.008, material=mats["walnut_desk"], uv_scale=1.0, collection=col_hero),
            create_beveled_box(f"TowerBaffle_{side}", (0.21, 0.018, 1.00), (0.0, 0.146, 0.544), bevel=0.004, material=mats["matte_plastic"], collection=col_hero),
        ]
        from materials import make_solid_pbr
        kevlar_cone = make_solid_pbr("HW_SpeakerKevlarCone", (0.11, 0.115, 0.125), roughness=0.58, metallic=0.12)
        for wz, wr, wmat in ((0.88, 0.024, mats["brushed_brass"]), (0.68, 0.066, kevlar_cone), (0.46, 0.066, kevlar_cone)):
            # Audiophile matte-black rubber surround + satin dark Kevlar woofer cone + brushed-brass phase plug!
            if wr > 0.05:
                tp.append(create_beveled_cylinder(f"TowerSurround_{side}_{wz:.2f}", wr + 0.009, 0.012, 24, 0.004, location=(0.0, 0.151, wz), rotation=(math.radians(90), 0.0, 0.0), material=mats["anodized_black"], collection=col_hero))
                tp.append(create_beveled_cylinder(f"TowerCap_{side}_{wz:.2f}", 0.017, 0.018, 20, 0.006, location=(0.0, 0.158, wz), rotation=(math.radians(90), 0.0, 0.0), material=mats["brushed_brass"], collection=col_hero))
            tp.append(create_beveled_cylinder(f"TowerDriver_{side}_{wz:.2f}", wr, 0.014, 24, 0.003, location=(0.0, 0.154, wz), rotation=(math.radians(90), 0.0, 0.0), material=wmat, collection=col_hero))
        _parent_all(tp, g)

    # 5. Sculpted Smooth Double-Curved Sony PlayStation 5 (100% crisp PBR white faceplates + glossy piano-black core
    #    + recessed inner front cyan LED collar strips + vertical stand — replaces crusty low-res single-atlas PS5!)
    from materials import make_emissive, make_solid_pbr
    mat_ps5_white = make_solid_pbr("Furn_PS5WhiteShell", (0.84, 0.835, 0.82), roughness=0.40, metallic=0.0, micro_bump_scale=900.0, micro_bump_strength=0.015)
    mat_ps5_piano = make_solid_pbr("Furn_PS5PianoCore", (0.018, 0.020, 0.024), roughness=0.14, metallic=0.08, coat_weight=0.65)
    ps5_g = _new_group("Hero_PS5Console", (cx + 1.04, -5.18, 0.520), col_hero, rot_z_deg=-16.0)
    ps5_p: list[bpy.types.Object] = [
        # Circular matte-black Sony vertical display stand
        create_beveled_cylinder("PS5_StandBase", 0.072, 0.014, 32, 0.004, location=(0.0, 0.0, 0.007), material=mats["anodized_black"], collection=col_hero),
    ]
    # Sculpted curved piano-black central core (faces +Y forward into living lounge! H=0.355m, D=0.225m, W=0.062m)
    def _build_ps5_wing(name: str, side: float, mat: bpy.types.Material) -> bpy.types.Object:
        bm = bmesh.new()
        nz, ny = 18, 12
        grid_in = []
        grid_out = []
        for iz in range(nz + 1):
            vz = iz / nz  # 0 (bottom) .. 1 (top)
            z = 0.012 + vz * 0.378
            # Iconic PS5 silhouette: subtly wider & gracefully flared outward at top collar + slight front overhang!
            flare_x = 0.003 + 0.018 * (vz ** 2.2)
            y_front = 0.118 + 0.022 * math.sin(vz * math.pi * 0.85) + 0.014 * (vz ** 2.0)
            y_back = -0.112 - 0.014 * (vz ** 1.6)
            row_in = []
            row_out = []
            for iy in range(ny + 1):
                vy = iy / ny  # 0 (back) .. 1 (front)
                y = y_back + vy * (y_front - y_back)
                # Subtle organic belly curve along front-to-back axis (slightly fuller on disc/right side!)
                belly = math.sin(vy * math.pi) * (0.010 if side < 0 else 0.015 * (1.0 - 0.4 * vz))
                # Iconic flared wing tip curve near top-front corner!
                wing_flare = flare_x * (0.35 + 0.65 * (vy ** 1.4))
                x_inner = side * (0.032 + belly + wing_flare)
                x_outer = x_inner + side * 0.0055
                row_in.append(bm.verts.new((x_inner, y, z)))
                row_out.append(bm.verts.new((x_outer, y, z)))
            grid_in.append(row_in)
            grid_out.append(row_out)
        for iz in range(nz):
            for iy in range(ny):
                if side > 0:
                    bm.faces.new((grid_out[iz][iy], grid_out[iz][iy+1], grid_out[iz+1][iy+1], grid_out[iz+1][iy]))
                    bm.faces.new((grid_in[iz][iy], grid_in[iz+1][iy], grid_in[iz+1][iy+1], grid_in[iz][iy+1]))
                else:
                    bm.faces.new((grid_out[iz][iy], grid_out[iz+1][iy], grid_out[iz+1][iy+1], grid_out[iz][iy+1]))
                    bm.faces.new((grid_in[iz][iy], grid_in[iz][iy+1], grid_in[iz+1][iy+1], grid_in[iz+1][iy]))
        # Stitch all 4 perimeter rims watertight!
        for iz in range(nz):
            for iy in (0, ny):
                bm.faces.new((grid_in[iz][iy], grid_out[iz][iy], grid_out[iz+1][iy], grid_in[iz+1][iy]))
        for iy in range(ny):
            for iz in (0, nz):
                bm.faces.new((grid_in[iz][iy], grid_out[iz][iy], grid_out[iz][iy+1], grid_in[iz][iy+1]))
        bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
        me = bpy.data.meshes.new(name)
        bm.to_mesh(me)
        bm.free()
        for p in me.polygons:
            p.use_smooth = True
        o = bpy.data.objects.new(name, me)
        col_hero.objects.link(o)
        o.data.materials.append(mat)
        return o

    ps5_p.append(create_beveled_box("PS5_PianoCore", (0.062, 0.224, 0.352), (0.0, 0.002, 0.014 + 0.176), bevel=0.014, segments=4, material=mat_ps5_piano, collection=col_hero))
    ps5_p.append(_build_ps5_wing("PS5_WhiteWingL", -1.0, mat_ps5_white))
    ps5_p.append(_build_ps5_wing("PS5_WhiteWingR", +1.0, mat_ps5_white))
    # Subtle recessed front cooling fin louvers + twin razor-thin 2.2mm glowing ice-blue LED strips INSIDE the front V-creases!
    for fz in range(11):
        ps5_p.append(create_beveled_box(f"PS5_VentFin_{fz:02d}", (0.072, 0.024, 0.004), (0.0, 0.106, 0.225 + fz * 0.0125), bevel=0.001, material=mats["anodized_black"], collection=col_hero))
    for side_s in (-1.0, 1.0):
        ps5_p.append(create_beveled_box(
            f"PS5_InnerLED_{'L' if side_s < 0 else 'R'}",
            (0.0026, 0.006, 0.195),
            (side_s * 0.0315, 0.112, 0.258),
            rotation=(math.radians(-4.5), math.radians(side_s * 2.8), 0.0),
            bevel=0.0005, material=mats["emissive_rgb_cyan"], collection=col_hero,
        ))
    # Tiny front USB-C & USB-A port bezel details on forward-facing piano-black face (+Y)
    ps5_p.append(create_beveled_box("PS5_FrontUSBC", (0.012, 0.004, 0.004), (0.0, 0.114, 0.115), bevel=0.001, material=mats["gunmetal"], collection=col_hero))
    ps5_p.append(create_beveled_box("PS5_FrontUSBA", (0.014, 0.004, 0.006), (0.0, 0.114, 0.095), bevel=0.001, material=mats["gunmetal"], collection=col_hero))
    _parent_all(ps5_p, ps5_g)
    # Matte-black Apple TV 4K + small anodized DAC/streamer on left side of media console to balance the PS5!
    create_beveled_box("Liv_AppleTV4K", (0.095, 0.095, 0.031), (cx - 0.96, -5.15, 0.5355), bevel=0.008, segments=3, material=mats["anodized_black"], collection=col_hero)
    create_beveled_box("Liv_AppleTVLED", (0.008, 0.003, 0.004), (cx - 0.96, -5.102, 0.528), bevel=0.0, material=mats["emissive_pc_internal"], collection=col_hero)

    # 5b. Plush Designer Channel-Tufted Fabric Sofa (native front -Y):
    #     Clean SOLID warm off-white / light oatmeal cloud bouclé (ZERO busy checkered pattern!) so it pops crisply
    #     against the warm oak floor & quiet solid dark-charcoal wool rug, paired w/ solid matte accent pillows!
    sofa = import_blenderkit_glb(
        bk("sofa_fabric_mod"), "BK_LivingSofa", col_bk,
        target_width=2.74, location=(cx, -2.98, 0.0),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=0.0,
    )
    # Restore authentic Italian modular sofa vertical & depth proportions (H=0.85m, seat ~0.43m, D=1.02m -> matches 0.74m armchair & 0.37m table!)
    bpy.context.view_layer.update()
    s_meshes = [o for o in sofa.children_recursive if o.type == "MESH"]
    if s_meshes:
        spts = [o.matrix_world @ Vector(c) for o in s_meshes for c in o.bound_box]
        sh = max(p.z for p in spts) - min(p.z for p in spts)
        sd = max(p.y for p in spts) - min(p.y for p in spts)
        if sh > 0.2:
            sofa.scale.z *= (0.85 / sh)
        if sd > 0.2:
            sofa.scale.y *= (1.02 / sd)
        bpy.context.view_layer.update()
        spts = [o.matrix_world @ Vector(c) for o in s_meshes for c in o.bound_box]
        sofa.location.z -= min(p.z for p in spts)
        sofa.location.y += (-2.98 - (min(p.y for p in spts) + max(p.y for p in spts)) * 0.5)
        bpy.context.view_layer.update()
    mat_sofa_boucle = make_solid_pbr(
        "Furn_SofaCloudOatmeal", (0.68, 0.65, 0.60),
        roughness=0.94, metallic=0.0, micro_bump_scale=460.0, micro_bump_strength=0.07,
    )
    pillow_mats = [
        make_solid_pbr("Furn_SofaPillowSageGrey", (0.34, 0.36, 0.34), roughness=0.94, metallic=0.0, micro_bump_scale=420.0, micro_bump_strength=0.06),
        make_solid_pbr("Furn_SofaPillowCognac", (0.36, 0.145, 0.068), roughness=0.91, metallic=0.0, micro_bump_scale=420.0, micro_bump_strength=0.06),
        make_solid_pbr("Furn_SofaPillowCharcoal", (0.14, 0.138, 0.135), roughness=0.94, metallic=0.0, micro_bump_scale=420.0, micro_bump_strength=0.07),
        make_solid_pbr("Furn_SofaPillowWarmTaupe", (0.44, 0.41, 0.37), roughness=0.93, metallic=0.0, micro_bump_scale=420.0, micro_bump_strength=0.06),
    ]
    p_idx = 0
    for o in sofa.children_recursive:
        if o.type != "MESH":
            continue
        o.data.materials.clear()
        if "pillow" in o.name.lower():
            o.data.materials.append(pillow_mats[p_idx % len(pillow_mats)])
            p_idx += 1
        else:
            o.data.materials.append(mat_sofa_boucle)

    # 5c. Sculpted Seamless Lathe-Spun Brushed-Brass Architectural Mushroom Dome Floor Lamp (Flos Atollo / Oslo style!)
    #     Clean minimalist architectural negative space beside the sofa & West panoramic Tokyo skyline window!
    mat_lamp_bulb = bpy.data.materials.get("Emit_OpalFloorLamp") or make_emissive(
        "Emit_OpalFloorLamp", (1.0, 0.80, 0.50), strength=3.4, roughness=0.35
    )
    lx_o, ly_o = -1.02, -2.86
    oslo_g = _new_group("Liv_OsloDomeLamp", (lx_o, ly_o, 0.0), col_hero)
    oslo_p = [
        # Weighted honed dark-marble cylinder base + brushed-brass foot collar + slender brushed-brass stem
        create_beveled_cylinder("Oslo_BaseMarble", 0.145, 0.044, 40, 0.008, location=(0.0, 0.0, 0.022), material=mats["dark_marble"], collection=col_hero),
        create_beveled_cylinder("Oslo_BaseCollar", 0.032, 0.022, 28, 0.004, location=(0.0, 0.0, 0.052), material=mats["brushed_brass"], collection=col_hero),
        create_beveled_cylinder("Oslo_Stem", 0.011, 1.30, 24, 0.002, location=(0.0, 0.0, 0.055 + 0.65), material=mats["brushed_brass"], collection=col_hero),
        create_beveled_cylinder("Oslo_TopFinial", 0.018, 0.018, 24, 0.005, location=(0.0, 0.0, 1.565), material=mats["brushed_brass"], collection=col_hero),
        # Delicate vertical brushed-brass pull-chain cord + solid brass teardrop bead hanging cleanly under dome!
        create_beveled_cylinder("Oslo_PullChain", 0.0018, 0.19, 8, 0.0, location=(0.038, -0.022, 1.24), material=mats["brushed_brass"], collection=col_hero),
        create_beveled_cylinder("Oslo_PullBead", 0.0075, 0.016, 16, 0.004, location=(0.038, -0.022, 1.142), material=mats["brushed_brass"], collection=col_hero),
    ]
    # Seamless 48-segment double-walled lathe-spun satin brushed-brass mushroom dome (Z = 1.30..1.56, R = 0.215m)
    dome_prof = [
        (0.000, 1.560), (0.045, 1.558), (0.095, 1.550), (0.142, 1.532),
        (0.178, 1.502), (0.200, 1.462), (0.212, 1.412), (0.216, 1.358),
        (0.214, 1.312), (0.210, 1.302), (0.204, 1.304), (0.206, 1.356),
        (0.194, 1.454), (0.165, 1.498), (0.115, 1.534), (0.000, 1.546),
    ]
    oslo_p.append(_create_lathe_mesh("Oslo_BrassDome", dome_prof, (0.0, 0.0, 0.0), mats["brushed_brass"], col_hero, segments=48))
    # Warm glowing frosted opal glass inner diffuser sphere nested cleanly inside the brass dome
    opal_prof = [
        (0.088 * math.sin(math.pi * i / 16.0), 1.335 + 0.088 * (1.0 - math.cos(math.pi * i / 16.0)))
        for i in range(17)
    ]
    oslo_p.append(_create_lathe_mesh("Oslo_OpalDiffuser", opal_prof, (0.0, 0.0, 0.0), mat_lamp_bulb, col_hero, segments=32))
    _parent_all(oslo_p, oslo_g)

    # 5d. Matching Modern Minimalist Wide-Arm Lounge Armchair (nudged slightly NW to open spacious Penthouse Entry Foyer!)
    mat_armchair_leather = make_solid_pbr(
        "Furn_LoaferCognacVelvet", (0.04, 0.042, 0.048),
        roughness=0.44, metallic=0.04, micro_bump_scale=520.0, micro_bump_strength=0.04,
    )
    loafer = import_blenderkit_glb(
        bk("chair_guide_mod"), "BK_LivingLoaferChair", col_bk,
        target_width=0.90, location=(2.94, -3.48, 0.0),
        rotation_xyz_deg=(0.0, 0.0, -76.0), ground_z=0.0,
    )
    for o in loafer.children_recursive:
        if o.type == "MESH":
            o.data.materials.clear()
            o.data.materials.append(mat_armchair_leather)

    # 5e. PROPORTIONAL TOKYO LUXURY ARMORED ENTRY DOOR (2.22m x 0.96m) & UNIFIED 2.265m FOYER WARDROBE/NICHE!
    #     - Realistic residential armored entry height (2.22m leaf, 2.265m lintel -> ~50cm exposed concrete transom above!)
    #     - Shifted West to dx_e = 3.94 -> clean 19.6cm exposed concrete wall pier separating door portal from fluted-glass partition (X=4.68)!
    #     - Unified 2.265m datum line aligning the entry door lintel and built-in foyer wardrobe/valet niche cleanly!
    #     - Door-only honed dark-marble Genkan stone (X=3.49..4.48, Y=-5.44..-4.74 -> clear of BOTH living rug X<=3.46 & fluted glass X=4.68!)
    ent_g = _new_group("Arch_PenthouseEntry", (0.0, 0.0, 0.0), col_hero)
    ent_p: list[bpy.types.Object] = []
    mat_entry_door = make_solid_pbr(
        "Furn_EntryArmoredMatte", (0.042, 0.044, 0.048),
        roughness=0.66, metallic=0.14, micro_bump_scale=620.0, micro_bump_strength=0.03,
    )
    dx_e, dy_e = 4.00, -5.44
    dw_e, dh_e = 1.06, 2.22  # Balanced foyer entry door (8cm reveal to foyer wardrobe West + 9cm concrete pier to fluted glass East!)

    # 1) Recessed matte-black shadow-gap steel portal surround (X=3.43..4.57, Z=0..2.265) — clean monolithic frame, ZERO awkward door-edge LED strip!
    ent_p.append(create_beveled_box("Entry_PortalL", (0.040, 0.095, dh_e + 0.045), (dx_e - dw_e * 0.5 - 0.020, dy_e + 0.030, (dh_e + 0.045) * 0.5), bevel=0.002, material=mats["anodized_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_PortalR", (0.040, 0.095, dh_e + 0.045), (dx_e + dw_e * 0.5 + 0.020, dy_e + 0.030, (dh_e + 0.045) * 0.5), bevel=0.002, material=mats["anodized_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_PortalT", (dw_e + 0.080, 0.095, 0.045), (dx_e, dy_e + 0.030, dh_e + 0.0225), bevel=0.002, material=mats["anodized_black"], collection=col_hero))

    # Monolithic matte powder-coated armored steel pivot door leaf (ZERO harsh circular specular glare!)
    ent_p.append(create_beveled_box("Entry_DoorLeaf", (dw_e - 0.012, 0.062, dh_e - 0.010), (dx_e, dy_e + 0.015, dh_e * 0.5), bevel=0.003, material=mat_entry_door, collection=col_hero))
    # Subtle recessed vertical oiled-walnut handle channel along latch stile
    ch_x = dx_e - 0.33
    ent_p.append(create_beveled_box("Entry_HandleChannel", (0.096, 0.010, dh_e - 0.08), (ch_x, dy_e + 0.048, dh_e * 0.5), bevel=0.002, material=mats["walnut_slat"], uv_scale=0.90, collection=col_hero))
    for tx_c in (-0.050, 0.050):
        ent_p.append(create_beveled_box(f"Entry_ChannelTrim_{tx_c:+.3f}", (0.005, 0.012, dh_e - 0.08), (ch_x + tx_c, dy_e + 0.049, dh_e * 0.5), bevel=0.001, material=mats["anodized_black"], collection=col_hero))
    # Proportional 1.10m brushed-brass vertical pull bar (Z = 0.62..1.72) + ergonomic recessed biometric smart lock (Z = 1.04)
    ent_p.append(create_beveled_cylinder("Entry_PullBar", 0.010, 1.10, 22, 0.003, location=(ch_x, dy_e + 0.094, 1.17), material=mats["brushed_brass"], collection=col_hero))
    for hz in (0.72, 1.62):
        ent_p.append(create_beveled_cylinder(f"Entry_PullPost_{hz:.2f}", 0.008, 0.048, 16, 0.002, location=(ch_x, dy_e + 0.070, hz), rotation=(math.radians(90), 0.0, 0.0), material=mats["brushed_brass"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_SmartLockBody", (0.048, 0.014, 0.195), (ch_x - 0.096, dy_e + 0.052, 1.04), bevel=0.004, material=mats["induction_glass"], collection=col_hero))
    ent_p.append(create_beveled_cylinder("Entry_SmartLockSensor", 0.009, 0.004, 18, 0.001, location=(ch_x - 0.096, dy_e + 0.060, 1.090), rotation=(math.radians(90), 0.0, 0.0), material=mats["brushed_brass"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_SmartLockLED", (0.020, 0.003, 0.004), (ch_x - 0.096, dy_e + 0.060, 1.062), bevel=0.0, material=mats["emissive_homelab_led"], collection=col_hero))

    # 2) Precision Portal-Aligned Honed Japanese Kuro-Mikage Dark Basalt Genkan Stone (X = 3.430..4.570, centered symmetrically on dx_e = 4.00!)
    #    Main slab begins FLUSH against the front face of BOTH black portal posts (Y = -5.362..-4.742) with ZERO post clipping or overhang,
    #    plus a clean door-threshold stone sill tucked strictly between the inner jambs (X = 3.470..4.530, Y = -5.440..-5.362)!
    mat_genkan_basalt = make_solid_pbr(
        "Furn_GenkanBasaltMatte", (0.075, 0.078, 0.084),
        roughness=0.80, metallic=0.02, micro_bump_scale=520.0, micro_bump_strength=0.08,
    )
    ent_p.append(create_beveled_box("Entry_GenkanStone", (1.140, 0.620, 0.005), (dx_e, -5.052, 0.0025), bevel=0.0012, material=mat_genkan_basalt, uv_scale=0.85, collection=col_hero))
    ent_p.append(create_beveled_box("Entry_GenkanSill", (dw_e, 0.078, 0.005), (dx_e, -5.401, 0.0025), bevel=0.0010, material=mat_genkan_basalt, uv_scale=0.85, collection=col_hero))
    ent_p.append(create_beveled_box("Entry_GenkanTrimN", (1.150, 0.005, 0.006), (dx_e, -4.7395, 0.003), bevel=0.001, material=mats["anodized_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_GenkanTrimW", (0.005, 0.625, 0.006), (dx_e - 0.5725, -5.052, 0.003), bevel=0.001, material=mats["anodized_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_GenkanTrimE", (0.005, 0.625, 0.006), (dx_e + 0.5725, -5.052, 0.003), bevel=0.001, material=mats["anodized_black"], collection=col_hero))

    # 2b) Recessed Architectural Entryway Ceiling Welcome Downlight centered directly above the Genkan Foyer (X = 4.00, Y = -4.98, Z = 2.76m)!
    mat_entry_downlight = bpy.data.materials.get("Emit_EntryCeilingLight") or make_emissive(
        "Emit_EntryCeilingLight", (1.0, 0.84, 0.58), strength=4.8, roughness=0.24
    )
    ent_p.append(create_beveled_cylinder("Entry_DownlightBezel", 0.076, 0.014, 32, 0.002, location=(dx_e, -4.98, 2.754), material=mats["anodized_black"], collection=col_hero))
    ent_p.append(create_beveled_cylinder("Entry_DownlightBaffle", 0.058, 0.016, 28, 0.0015, location=(dx_e, -4.98, 2.753), material=mats["brushed_brass"], collection=col_hero))
    ent_p.append(create_beveled_cylinder("Entry_DownlightLens", 0.048, 0.008, 28, 0.001, location=(dx_e, -4.98, 2.750), material=mat_entry_downlight, collection=col_hero))

    # 3) Matching 2.265m Datum Built-In Foyer Wardrobe & Illuminated Dark-Marble Key Valet Niche (X = 2.83..3.35)!
    #    Leaves clean 8cm concrete reveal to TV walnut slats (2.75) & 7cm reveal to door portal (3.42), aligned cleanly at Z = 2.265m!
    fc_x, fc_y, fc_w, fc_d = 3.09, -5.26, 0.52, 0.36
    ent_p.append(create_beveled_box("Entry_ClosetToeKick", (fc_w - 0.02, fc_d - 0.06, 0.08), (fc_x, fc_y - 0.03, 0.04), bevel=0.002, material=mats["anodized_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_ClosetFootLED", (fc_w - 0.08, 0.014, 0.006), (fc_x, fc_y + 0.12, 0.082), bevel=0.001, material=mats["emissive_shelf_led"], collection=col_hero))
    # Lower handleless matte-black shoe cabinet (Z = 0.08..0.82) + dark marble counter slab
    ent_p.append(create_beveled_box("Entry_ShoeCab", (fc_w, fc_d, 0.72), (fc_x, fc_y, 0.44), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_ShoeDoor", (fc_w - 0.016, 0.018, 0.70), (fc_x, fc_y + fc_d * 0.5 + 0.008, 0.44), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_NicheMarbleBot", (fc_w, fc_d + 0.01, 0.024), (fc_x, fc_y + 0.005, 0.812), bevel=0.003, material=mats["dark_marble"], uv_scale=0.80, collection=col_hero))
    # Illuminated Architectural Valet Niche (Z = 0.824..1.44): oiled-walnut back lining + top concealed 2700K wash LED!
    ent_p.append(create_beveled_box("Entry_NicheBack", (fc_w - 0.04, 0.018, 0.62), (fc_x, fc_y - fc_d * 0.5 + 0.012, 1.134), bevel=0.002, material=mats["walnut_desk"], uv_scale=0.95, collection=col_hero))
    ent_p.append(create_beveled_box("Entry_NicheSideL", (0.024, fc_d, 0.62), (fc_x - fc_w * 0.5 + 0.012, fc_y, 1.134), bevel=0.002, material=mats["kitchen_matte_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_NicheSideR", (0.024, fc_d, 0.62), (fc_x + fc_w * 0.5 - 0.012, fc_y, 1.134), bevel=0.002, material=mats["kitchen_matte_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_NicheTopLED", (fc_w - 0.10, 0.016, 0.006), (fc_x, fc_y + 0.04, 1.434), bevel=0.001, material=mats["emissive_shelf_led"], collection=col_hero))
    ev_prof = [(0.0, 0.0), (0.034, 0.0), (0.052, 0.040), (0.054, 0.090), (0.034, 0.148), (0.022, 0.174), (0.026, 0.186), (0.020, 0.188), (0.016, 0.170), (0.034, 0.118), (0.0, 0.014)]
    ent_p.append(_create_lathe_mesh("Entry_NicheVase", ev_prof, (fc_x - 0.115, fc_y - 0.02, 0.824), mats["ceramic_charcoal"], col_hero, segments=28))
    kd_prof = [(0.0, 0.0), (0.044, 0.0), (0.060, 0.010), (0.062, 0.017), (0.056, 0.018), (0.040, 0.007), (0.0, 0.007)]
    ent_p.append(_create_lathe_mesh("Entry_KeyDish", kd_prof, (fc_x + 0.10, fc_y + 0.03, 0.824), mats["brushed_brass"], col_hero, segments=28))
    mat_intercom_ui = bpy.data.materials.get("Emit_IntercomDisplay") or make_emissive(
        "Emit_IntercomDisplay", (0.24, 0.32, 0.42), strength=0.38, roughness=0.22
    )
    ent_p.append(create_beveled_box("Entry_IntercomBody", (0.115, 0.014, 0.148), (fc_x + 0.115, fc_y - fc_d * 0.5 + 0.028, 1.21), bevel=0.003, material=mats["anodized_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_IntercomScreen", (0.092, 0.004, 0.072), (fc_x + 0.115, fc_y - fc_d * 0.5 + 0.036, 1.236), bevel=0.001, material=mat_intercom_ui, collection=col_hero))
    # Upper flush matte-black coat cabinet aligned strictly to the 2.265m entry door lintel datum (Z = 1.44..2.265)!
    ent_p.append(create_beveled_box("Entry_UpperCab", (fc_w, fc_d, 0.825), (fc_x, fc_y, 1.8525), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_UpperDoor", (fc_w - 0.016, 0.018, 0.805), (fc_x, fc_y + fc_d * 0.5 + 0.008, 1.8525), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero))
    ent_p.append(create_beveled_box("Entry_UpperBrassReveal", (0.007, 0.016, 0.42), (fc_x + fc_w * 0.5 - 0.024, fc_y + fc_d * 0.5 + 0.018, 1.74), bevel=0.001, material=mats["brushed_brass"], collection=col_hero))
    _parent_all(ent_p, ent_g)

    # Sleek rectangular walnut coffee table (1.06m x 0.72m x 0.37m) centered at Y=-4.22 -> sits comfortably below 0.43m sofa seat!
    ct = import_blenderkit_glb(
        bk("coffee_table_walnut"), "BK_LivingCoffeeTable", col_bk,
        target_width=1.06, location=(cx, -4.22, 0.0),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=0.0,
    )
    ct.scale.y *= 0.68
    ct.scale.z *= 0.87
    bpy.context.view_layer.update()
    ct_m0 = [o for o in ct.children_recursive if o.type == "MESH"]
    if ct_m0:
        ct.location.z -= min((o.matrix_world @ Vector(c)).z for o in ct_m0 for c in o.bound_box)
        bpy.context.view_layer.update()
    _recolor_hierarchy(ct, mats["walnut_desk"])
    ct_meshes = [o for o in ct.children_recursive if o.type == "MESH"]
    ct_top = max((o.matrix_world @ Vector(c)).z for o in ct_meshes for c in o.bound_box) if ct_meshes else 0.424
    # Coffee table curated styling: stacked art monographs + real artist PS5 DualSense controller (exclude backdrop plane!)
    create_beveled_box("Liv_CoffeeBook1", (0.28, 0.22, 0.028), (cx - 0.25, -4.24, ct_top + 0.014), rotation=(0.0, 0.0, math.radians(12)), bevel=0.002, material=mats["vinyl_cover_1"], collection=col_hero)
    create_beveled_box("Liv_CoffeeBook2", (0.24, 0.19, 0.022), (cx - 0.24, -4.23, ct_top + 0.039), rotation=(0.0, 0.0, math.radians(-6)), bevel=0.002, material=mats["vinyl_cover_4"], collection=col_hero)
    import_blenderkit_glb(
        bk("dualsense_ps5"), "BK_LivingDualSense", col_bk,
        target_max_dim=0.165, location=(cx + 0.24, -4.44, ct_top),
        rotation_xyz_deg=(0.0, 0.0, 22.0), ground_z=ct_top,
        exclude_substrings=("plane",),
    )

    # Large Quiet SOLID Matte Charcoal-Basalt Wool Living Area Rug (ZERO noisy checkered pattern — creates crisp
    # luxury tonal contrast between warm brown oak parquet floor, dark slate rug, and bright light-oatmeal cloud sofa!)
    mat_living_rug = make_solid_pbr(
        "Furn_LivingRugCharcoal", (0.14, 0.14, 0.145),
        roughness=0.95, metallic=0.0, micro_bump_scale=480.0, micro_bump_strength=0.09,
    )
    create_beveled_box("Arch_West_LivingRug", (4.48, 2.74, 0.006), (1.22, -3.65, 0.003), bevel=0.0025, segments=2, material=mat_living_rug, uv_scale=1.0, collection=col_hero)

    # Sunny South-West Corner Tall Monstera + Minimalist Matte-Black Ceiling Track Rail over Lounge!
    import_blenderkit_glb(
        bk("monstera_big"), "BK_LivingMonstera", col_bk,
        target_height=1.62, location=(-1.58, -4.80, 0.0),
        rotation_xyz_deg=(0.0, 0.0, 48.0), ground_z=0.0,
    )
    from mathutils import Euler
    create_beveled_box("Liv_TrackRail", (3.20, 0.042, 0.024), (cx, -3.80, 2.748), bevel=0.002, material=mats["anodized_black"], collection=col_hero)
    for tx in (cx - 1.15, cx, cx + 1.15):
        lrot = (math.radians(22), 0.0, 0.0)
        lpos = Vector((tx, -3.80, 2.67))
        lled = lpos + Euler(lrot, "XYZ").to_matrix() @ Vector((0.0, 0.0, -0.050))
        create_beveled_cylinder(f"Liv_TrackSpot_{tx:+.2f}", 0.028, 0.105, 18, 0.003, location=tuple(lpos), rotation=lrot, material=mats["anodized_black"], collection=col_hero)
        create_beveled_cylinder(f"Liv_TrackLED_{tx:+.2f}", 0.022, 0.006, 16, 0.001, location=tuple(lled), rotation=lrot, material=mats["emissive_track_led"], collection=col_hero)


def build_zone3_open_kitchen(
    mats: dict[str, bpy.types.Material],
    col_hero: bpy.types.Collection,
    col_bk: bpy.types.Collection,
) -> None:
    """Zone 3 — Open Kitchen & Honed Dark Calacatta Marble Waterfall Espresso Bar Island (X=+2.36..+6.38, Y=-1.45..+2.05)."""
    bk = lambda slot: BK_DIR / slot / f"{slot}.glb"

    # 1. North Back-Wall Handleless Matte-Black Base Cabinetry + Dark Calacatta Marble Counter & Backsplash!
    #    X = +2.44..+5.48 (3.04m counter run), Y = +1.40..+2.04 (0.64m deep)
    create_beveled_box("Kit_BaseCabinets", (3.04, 0.62, 0.88), (3.96, 1.73, 0.44), bevel=0.004, material=mats["kitchen_matte_black"], collection=col_hero)
    for i in range(5):
        dx = 2.74 + i * 0.608
        create_beveled_box(f"Kit_BaseFront_{i}", (0.596, 0.018, 0.84), (dx, 1.412, 0.44), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero)
    # Continuous Dark Calacatta Marble Back Countertop (Z = 0.88..0.92) + Full-Height Marble Backsplash (Z = 0.92..1.56)
    create_beveled_box("Arch_East_KitCounterMarble", (3.06, 0.65, 0.042), (3.96, 1.72, 0.901), bevel=0.004, material=mats["dark_marble"], uv_scale=0.75, collection=col_hero)
    create_beveled_box("Arch_East_KitBacksplash", (3.06, 0.022, 0.66), (3.96, 2.035, 1.25), bevel=0.002, material=mats["dark_marble"], uv_scale=0.75, collection=col_hero)

    # Flush Black-Glass 4-Zone Induction Cooktop + Subtle Ceramic Ring Guides
    create_beveled_box("Kit_InductionGlass", (0.76, 0.50, 0.008), (4.35, 1.70, 0.924), bevel=0.002, material=mats["induction_glass"], collection=col_hero)
    for bx, by, br in ((4.14, 1.80, 0.085), (4.54, 1.80, 0.105), (4.14, 1.60, 0.095), (4.54, 1.60, 0.075)):
        create_beveled_cylinder(f"Kit_Burner_{bx:.2f}_{by:.2f}", br, 0.002, 24, 0.0, location=(bx, by, 0.929), material=mats["gunmetal"], collection=col_hero)

    # Upper Oiled American Walnut Handleless Wall Cabinets (Z = 1.56..2.50) + Continuous 2700K Under-Cabinet LED Wash!
    create_beveled_box("Arch_East_KitUpperWalnut", (3.04, 0.36, 0.94), (3.96, 1.86, 2.03), bevel=0.004, material=mats["walnut_desk"], uv_scale=0.85, collection=col_hero)
    for i in range(5):
        dx = 2.74 + i * 0.608
        create_beveled_box(f"Kit_UpperDoor_{i}", (0.596, 0.018, 0.92), (dx, 1.672, 2.03), bevel=0.003, material=mats["walnut_desk"], uv_scale=0.85, collection=col_hero)
    create_beveled_box("Kit_UnderCabLED", (2.90, 0.018, 0.006), (3.96, 1.88, 1.556), bevel=0.001, material=mats["emissive_kitchen_led"], collection=col_hero)

    # East Built-In Gaggenau/Miele Obsidian Matte-Black Appliance Column (X = +5.50..+6.34, Z = 0..2.50):
    # Architectural 3-module split (upper pantry, brushed-gunmetal recessed steam oven w/ warm amber display, lower drawer)!
    create_beveled_box("Kit_ApplianceCore", (0.84, 0.60, 2.50), (5.92, 1.74, 1.25), bevel=0.004, material=mats["kitchen_matte_black"], collection=col_hero)
    create_beveled_box("Kit_UpperPantryDoor", (0.81, 0.022, 0.88), (5.92, 1.425, 2.04), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero)
    create_beveled_box("Kit_LowerDrawerDoor", (0.81, 0.022, 0.80), (5.92, 1.425, 0.42), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero)
    # Recessed Gaggenau brushed-gunmetal steam oven fascia + smoked black-glass door + rotary dials + warm amber clock bar!
    create_beveled_box("Kit_OvenBezel", (0.76, 0.026, 0.70), (5.92, 1.424, 1.20), bevel=0.004, material=mats["gunmetal"], collection=col_hero)
    create_beveled_box("Kit_OvenControlStrip", (0.72, 0.016, 0.11), (5.92, 1.408, 1.48), bevel=0.002, material=mats["anodized_black"], collection=col_hero)
    for d_off in (-0.22, 0.22):
        create_beveled_cylinder(f"Kit_OvenDial_{d_off:+.2f}", 0.020, 0.020, 22, 0.003, location=(5.92 + d_off, 1.394, 1.48), rotation=(math.radians(90), 0.0, 0.0), material=mats["gunmetal"], collection=col_hero)
    create_beveled_box("Kit_OvenClockLED", (0.088, 0.005, 0.018), (5.92, 1.399, 1.48), bevel=0.001, material=mats["emissive_shelf_led"], collection=col_hero)
    create_beveled_box("Kit_OvenGlass", (0.66, 0.018, 0.52), (5.92, 1.404, 1.14), bevel=0.003, material=mats["induction_glass"], collection=col_hero)
    create_beveled_box("Kit_OvenHandle", (0.56, 0.020, 0.015), (5.92, 1.376, 1.365), bevel=0.003, material=mats["anodized_black"], collection=col_hero)
    # Slim vertical brushed-brass reveal handle along West edge of built-in appliance tower
    create_beveled_box("Kit_FridgePull", (0.012, 0.024, 0.84), (5.535, 1.408, 2.04), bevel=0.002, material=mats["brushed_brass"], collection=col_hero)

    # 2. Dedicated Specialty Barista Station (Real Artist Espresso Machine + CNC Grinder + Ceramic Cups!)
    import_blenderkit_glb(
        bk("espresso_machine"), "BK_EspressoMachine", col_bk,
        target_height=0.39, location=(2.88, 1.66, 0.922),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=0.922,
    )
    import_blenderkit_glb(
        bk("coffee_grinder_cnc"), "BK_CoffeeGrinder", col_bk,
        target_height=0.22, location=(3.28, 1.70, 0.922),
        rotation_xyz_deg=(0.0, 0.0, -24.0), ground_z=0.922,
    )
    # Matte-black gooseneck pour-over kettle & stacked dark stoneware espresso cups beside grinder
    create_beveled_cylinder("Kit_PourOverKettle", 0.056, 0.135, 24, 0.006, location=(3.56, 1.70, 0.922 + 0.068), material=mats["anodized_black"], collection=col_hero)
    create_curve_tube("Kit_KettleSpout", [(3.56 - 0.05, 1.70, 0.95), (3.48, 1.64, 0.99), (3.44, 1.60, 1.055)], 0.006, mats["anodized_black"], col_hero)
    for ci, cx_c in enumerate((3.36, 3.45)):
        create_beveled_cylinder(f"Kit_EspressoCup_{ci}", 0.028, 0.054, 20, 0.003, location=(cx_c, 1.54, 0.922 + 0.027), material=mats["ceramic_charcoal"], collection=col_hero)

    # 3. 2.52m Honed Dark Calacatta Marble Waterfall Espresso Bar Island (X = +4.25, Y = -0.18, Z = 0..0.92)
    #    WITH REAL 20cm DEEP RECESSED UNDERMOUNT PREP SINK CUTOUT! (4 seamless marble slabs + hollow cabinet pocket!)
    ix, iy = 4.25, -0.18
    # Island top outer bounds: X = [2.98, 5.52], Y = [-0.66, +0.30], Z = [0.868, 0.920]
    # Real sink cutout bounds: X = [4.46, 5.00] (w=0.54, cx=4.73), Y = [-0.30, +0.06] (d=0.36, cy=-0.12)
    sx_s, sy_s, sw_s, sd_s = ix + 0.48, iy + 0.06, 0.54, 0.36
    create_beveled_box("Arch_East_IslandTop_W", (1.48, 0.96, 0.052), (3.72, iy, 0.894), bevel=0.004, material=mats["dark_marble"], uv_scale=0.65, collection=col_hero)
    create_beveled_box("Arch_East_IslandTop_E", (0.52, 0.96, 0.052), (5.26, iy, 0.894), bevel=0.004, material=mats["dark_marble"], uv_scale=0.65, collection=col_hero)
    create_beveled_box("Arch_East_IslandTop_N", (0.54, 0.24, 0.052), (sx_s, 0.18, 0.894), bevel=0.003, material=mats["dark_marble"], uv_scale=0.65, collection=col_hero)
    create_beveled_box("Arch_East_IslandTop_S", (0.54, 0.36, 0.052), (sx_s, -0.48, 0.894), bevel=0.003, material=mats["dark_marble"], uv_scale=0.65, collection=col_hero)
    create_beveled_box("Arch_East_IslandFallL", (0.052, 0.96, 0.89), (ix - 1.244, iy, 0.445), bevel=0.004, material=mats["dark_marble"], uv_scale=0.65, collection=col_hero)
    create_beveled_box("Arch_East_IslandFallR", (0.052, 0.96, 0.89), (ix + 1.244, iy, 0.445), bevel=0.004, material=mats["dark_marble"], uv_scale=0.65, collection=col_hero)
    # Recessed matte-black island cabinet core notched cleanly below Z=0.68 beneath the 20cm deep sink!
    create_beveled_box("Kit_IslandCore_L", (1.40, 0.62, 0.87), (3.74, iy + 0.16, 0.435), bevel=0.004, material=mats["kitchen_matte_black"], collection=col_hero)
    create_beveled_box("Kit_IslandCore_R", (0.44, 0.62, 0.87), (5.24, iy + 0.16, 0.435), bevel=0.004, material=mats["kitchen_matte_black"], collection=col_hero)
    create_beveled_box("Kit_IslandCore_UnderSink", (0.58, 0.62, 0.68), (sx_s, iy + 0.16, 0.34), bevel=0.003, material=mats["kitchen_matte_black"], collection=col_hero)
    create_beveled_box("Kit_IslandCore_BackRail", (0.58, 0.21, 0.19), (sx_s, 0.185, 0.775), bevel=0.002, material=mats["kitchen_matte_black"], collection=col_hero)
    create_beveled_box("Kit_IslandWalnutInlay", (2.42, 0.024, 0.82), (ix, iy - 0.155, 0.44), bevel=0.003, material=mats["walnut_slat"], uv_scale=1.0, collection=col_hero)

    # Real 20cm Deep Brushed-Gunmetal Undermount Kitchen Sink Basin (Z = 0.70..0.916) + Stainless Basket Strainer Drain + Overflow!
    from materials import make_solid_pbr
    mat_sink_metal = make_solid_pbr("HW_SinkBrushedGunmetal", (0.14, 0.145, 0.155), roughness=0.34, metallic=0.86, micro_bump_scale=520.0, micro_bump_strength=0.02)
    mat_drain_steel = make_solid_pbr("HW_SinkDrainSteel", (0.56, 0.58, 0.60), roughness=0.28, metallic=0.92)
    sink_g = _new_group("Kit_UndermountSink", (sx_s, sy_s, 0.0), col_hero)
    sink_p = [
        # Recessed brushed-gunmetal sink bottom (Z = 0.702..0.714) & 4 seamless inner basin walls (Z = 0.708..0.892)
        create_beveled_box("Sink_Floor", (sw_s + 0.016, sd_s + 0.016, 0.014), (0.0, 0.0, 0.707), bevel=0.002, material=mat_sink_metal, collection=col_hero),
        create_beveled_box("Sink_WallW", (0.012, sd_s + 0.016, 0.192), (-sw_s * 0.5 + 0.004, 0.0, 0.804), bevel=0.002, material=mat_sink_metal, collection=col_hero),
        create_beveled_box("Sink_WallE", (0.012, sd_s + 0.016, 0.192), (sw_s * 0.5 - 0.004, 0.0, 0.804), bevel=0.002, material=mat_sink_metal, collection=col_hero),
        create_beveled_box("Sink_WallN", (sw_s + 0.016, 0.012, 0.192), (0.0, sd_s * 0.5 - 0.004, 0.804), bevel=0.002, material=mat_sink_metal, collection=col_hero),
        create_beveled_box("Sink_WallS", (sw_s + 0.016, 0.012, 0.192), (0.0, -sd_s * 0.5 + 0.004, 0.804), bevel=0.002, material=mat_sink_metal, collection=col_hero),
        # Fine brushed stainless flange collar tucked cleanly inside the marble edge + recessed stainless basket drain & overflow slot!
        create_beveled_box("Sink_TrimW", (0.010, sd_s, 0.006), (-sw_s * 0.5 + 0.005, 0.0, 0.894), bevel=0.001, material=mat_sink_metal, collection=col_hero),
        create_beveled_box("Sink_TrimE", (0.010, sd_s, 0.006), (sw_s * 0.5 - 0.005, 0.0, 0.894), bevel=0.001, material=mat_sink_metal, collection=col_hero),
        create_beveled_cylinder("Sink_DrainFlange", 0.048, 0.005, 28, 0.0015, location=(0.06, 0.02, 0.715), material=mat_drain_steel, collection=col_hero),
        create_beveled_cylinder("Sink_DrainWell", 0.036, 0.006, 24, 0.001, location=(0.06, 0.02, 0.716), material=mats["anodized_black"], collection=col_hero),
        create_beveled_cylinder("Sink_DrainCap", 0.022, 0.007, 20, 0.0015, location=(0.06, 0.02, 0.718), material=mat_drain_steel, collection=col_hero),
        create_beveled_box("Sink_OverflowSlot", (0.044, 0.004, 0.012), (0.0, sd_s * 0.5 - 0.011, 0.848), bevel=0.001, material=mats["anodized_black"], collection=col_hero),
    ]
    _parent_all(sink_p, sink_g)
    import_blenderkit_glb(
        bk("kitchen_faucet_black"), "BK_KitchenFaucet", col_bk,
        target_height=0.39, location=(sx_s, iy + 0.32, 0.920),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=0.920,
        exclude_substrings=("torus",),
    )
    # Curated Japanese Specialty Coffee & Fruit Vignette on West half of marble waterfall island (Z=0.920):
    # 1) Sculpted Hollow Lathe-Spun Matte-Stoneware Fruit Bowl + 3 organic citrus / pear fruits inside!
    mat_citrus = make_solid_pbr("Prop_CitrusMandarin", (0.76, 0.28, 0.045), roughness=0.48, metallic=0.0)
    mat_pear = make_solid_pbr("Prop_PearOlive", (0.30, 0.40, 0.11), roughness=0.44, metallic=0.0)
    mat_coffee_liq = make_solid_pbr("Prop_EspressoLiquid", (0.045, 0.018, 0.008), roughness=0.08, metallic=0.0)
    mat_stoneware = make_solid_pbr("Prop_StonewareIvory", (0.68, 0.65, 0.60), roughness=0.58, metallic=0.0)

    bx_b, by_b = ix - 0.74, iy + 0.02
    bowl_profile = [
        (0.0, 0.0), (0.056, 0.0), (0.066, 0.012), (0.105, 0.030), (0.132, 0.058),
        (0.138, 0.082), (0.131, 0.086), (0.124, 0.082), (0.118, 0.056),
        (0.092, 0.032), (0.052, 0.016), (0.0, 0.014),
    ]
    _create_lathe_mesh("Kit_FruitBowl_Hollow", bowl_profile, (bx_b, by_b, 0.920), mats["ceramic_charcoal"], col_hero, segments=36)
    # 2 mandarin oranges + 1 green-gold pear nestled naturally inside the hollow bowl!
    citrus_prof = [
        (0.0, 0.0), (0.022, 0.004), (0.036, 0.018), (0.040, 0.034),
        (0.035, 0.050), (0.020, 0.062), (0.0, 0.064),
    ]
    pear_prof = [
        (0.0, 0.0), (0.020, 0.005), (0.035, 0.022), (0.034, 0.042),
        (0.022, 0.064), (0.015, 0.080), (0.006, 0.092), (0.0, 0.094),
    ]
    _create_lathe_mesh("Kit_Fruit_Mandarin1", citrus_prof, (bx_b - 0.042, by_b + 0.016, 0.935), mat_citrus, col_hero, segments=20)
    _create_lathe_mesh("Kit_Fruit_Mandarin2", citrus_prof, (bx_b + 0.036, by_b - 0.024, 0.935), mat_citrus, col_hero, segments=20)
    pear_o = _create_lathe_mesh("Kit_Fruit_Pear", pear_prof, (bx_b + 0.010, by_b + 0.032, 0.937), mat_pear, col_hero, segments=20)
    pear_o.rotation_euler = (math.radians(16), math.radians(-12), math.radians(24))
    create_beveled_cylinder("Kit_PearStem", 0.0025, 0.018, 8, 0.0, location=(bx_b + 0.002, by_b + 0.048, 1.032), rotation=(math.radians(18), 0.0, 0.0), material=mats["anodized_black"], collection=col_hero)

    # 2) Oiled-Walnut Specialty Pour-Over Coffee Tasting Tray (Chemex Glass Carafe + 2 Hollow Stoneware Cups!)
    tx_t, ty_t = ix - 0.28, iy - 0.06
    create_beveled_box("Kit_CoffeeTray_Base", (0.34, 0.22, 0.012), (tx_t, ty_t, 0.926), bevel=0.003, material=mats["walnut_desk"], uv_scale=1.2, collection=col_hero)
    for rx, ry, rw, rd in ((0.0, -0.104, 0.34, 0.012), (0.0, 0.104, 0.34, 0.012), (-0.164, 0.0, 0.012, 0.22), (0.164, 0.0, 0.012, 0.22)):
        create_beveled_box(f"Kit_TrayRim_{rx:+.2f}_{ry:+.2f}", (rw, rd, 0.018), (tx_t + rx, ty_t + ry, 0.935), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col_hero)
    # Hourglass Glass Pour-Over Chemex Carafe (hollow glass body + dark brewed coffee inside + oiled-walnut neck collar!)
    chemex_x, chemex_y = tx_t - 0.075, ty_t + 0.008
    chemex_prof = [
        (0.0, 0.0), (0.056, 0.0), (0.064, 0.022), (0.058, 0.068), (0.036, 0.118),
        (0.030, 0.145), (0.044, 0.185), (0.058, 0.215), (0.054, 0.216), (0.027, 0.145),
        (0.054, 0.068), (0.058, 0.022), (0.050, 0.005), (0.0, 0.005),
    ]
    _create_lathe_mesh("Kit_Chemex_Glass", chemex_prof, (chemex_x, chemex_y, 0.932), mats["shower_glass"], col_hero, segments=28)
    coffee_fill_prof = [(0.0, 0.006), (0.050, 0.006), (0.057, 0.024), (0.052, 0.064), (0.0, 0.064)]
    _create_lathe_mesh("Kit_Chemex_Coffee", coffee_fill_prof, (chemex_x, chemex_y, 0.932), mat_coffee_liq, col_hero, segments=24)
    collar_prof = [(0.031, 0.122), (0.038, 0.122), (0.036, 0.156), (0.031, 0.156)]
    _create_lathe_mesh("Kit_Chemex_Collar", collar_prof, (chemex_x, chemex_y, 0.932), mats["walnut_desk"], col_hero, segments=24)
    create_beveled_cylinder("Kit_Chemex_Tie", 0.0385, 0.005, 24, 0.001, location=(chemex_x, chemex_y, 0.932 + 0.139), material=mats["leather_cognac"], collection=col_hero)
    # Two Sculpted Hollow Matte-Ivory Stoneware Tasting Cups with Dark Coffee Surface & Saucers!
    cup_prof = [
        (0.0, 0.0), (0.024, 0.0), (0.032, 0.018), (0.036, 0.058), (0.033, 0.060),
        (0.030, 0.056), (0.027, 0.018), (0.020, 0.006), (0.0, 0.006),
    ]
    saucer_prof = [(0.0, 0.0), (0.042, 0.0), (0.054, 0.009), (0.052, 0.011), (0.038, 0.004), (0.0, 0.004)]
    for ci, (cx_off, cy_off) in enumerate(((0.068, 0.038), (0.088, -0.044))):
        cx_p, cy_p = tx_t + cx_off, ty_t + cy_off
        _create_lathe_mesh(f"Kit_IslandSaucer_{ci}", saucer_prof, (cx_p, cy_p, 0.932), mat_stoneware, col_hero, segments=24)
        _create_lathe_mesh(f"Kit_IslandCup_{ci}", cup_prof, (cx_p, cy_p, 0.936), mat_stoneware, col_hero, segments=24)
        create_beveled_cylinder(f"Kit_IslandCoffee_{ci}", 0.029, 0.003, 20, 0.0, location=(cx_p, cy_p, 0.936 + 0.046), material=mat_coffee_liq, collection=col_hero)

    # 4. Three Matte-Black Steel & Matte-Satin Oiled American Walnut Bar Stools tucked cleanly along South overhang (Y = -0.78)!
    #    Replaces the harsh glossy zebra-streaked source seat texture with matching oiled American walnut + clean world-scale UVs!
    for si, sx in enumerate((ix - 0.72, ix, ix + 0.72)):
        stool = import_blenderkit_glb(
            bk("bar_stool_dark"), f"BK_BarStool_{si}", col_bk,
            target_height=0.67, location=(sx, iy - 0.58, 0.0),
            rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=0.0,
        )
        for o in stool.children_recursive:
            if o.type != "MESH":
                continue
            mnames = " ".join((s.material.name.lower() if s.material else "") for s in o.material_slots)
            if "wood" in mnames or "ebony" in mnames or "seat" in o.name.lower() or "top" in o.name.lower() and "bolt" not in o.name.lower():
                o.data.materials.clear()
                o.data.materials.append(mats["walnut_desk"])
                uv_l = o.data.uv_layers.active or o.data.uv_layers.new(name="UVMap")
                for poly in o.data.polygons:
                    n = poly.normal
                    ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
                    for li in poly.loop_indices:
                        co = o.data.vertices[o.data.loops[li].vertex_index].co
                        if az >= ax and az >= ay:
                            uv_l.data[li].uv = (co.x * 1.15, co.y * 1.15)
                        elif ax >= ay:
                            uv_l.data[li].uv = (co.y * 1.15, co.z * 1.15)
                        else:
                            uv_l.data[li].uv = (co.x * 1.15, co.z * 1.15)
            else:
                o.data.materials.clear()
                o.data.materials.append(mats["anodized_black"])

    # 5. Architectural Trio of Sculpted Matte-Black & Brushed-Brass Conical Island Pendant Lamps!
    #    Replaces the weird floating ring+rod fixture with 3 crisp designer pendants aligned cleanly above the 3 barstools!
    create_beveled_box("Kit_PendantCanopy", (1.76, 0.072, 0.028), (ix, iy, 2.746), bevel=0.004, material=mats["anodized_black"], collection=col_hero)
    shade_outer_prof = [
        (0.016, 0.215), (0.028, 0.205), (0.048, 0.160), (0.092, 0.082),
        (0.132, 0.012), (0.136, 0.002), (0.130, 0.0), (0.125, 0.010),
        (0.086, 0.078), (0.043, 0.155), (0.022, 0.198), (0.0, 0.202),
    ]
    shade_inner_prof = [
        (0.0, 0.194), (0.021, 0.190), (0.042, 0.150), (0.084, 0.076), (0.123, 0.011),
        (0.121, 0.010), (0.082, 0.074), (0.040, 0.148), (0.019, 0.188), (0.0, 0.191),
    ]
    from materials import make_emissive
    mat_pend_bulb = make_emissive("Emit_KitchenPendantBulb", (1.0, 0.80, 0.50), strength=6.5, roughness=0.25)
    # Uniform warm golden self-illuminated inner brass cone across ALL 3 pendants so left/center/right match 100% evenly!
    mat_pend_inner = make_emissive("Emit_KitchenPendantInner", (1.0, 0.74, 0.38), strength=1.45, roughness=0.38)
    bulb_prof = [
        (0.0, 0.0), (0.022, 0.005), (0.038, 0.020), (0.042, 0.040),
        (0.030, 0.062), (0.014, 0.076), (0.0, 0.078),
    ]
    for pi, px_p in enumerate((ix - 0.72, ix, ix + 0.72)):
        # Ceiling strain-relief grommet + slim matte-black braided cord + brushed-brass neck collar
        create_beveled_cylinder(f"Kit_PendGrommet_{pi}", 0.014, 0.018, 16, 0.002, location=(px_p, iy, 2.725), material=mats["brushed_brass"], collection=col_hero)
        create_beveled_cylinder(f"Kit_PendCord_{pi}", 0.0038, 0.56, 10, 0.0, location=(px_p, iy, 2.45), material=mats["anodized_black"], collection=col_hero)
        create_beveled_cylinder(f"Kit_PendNeck_{pi}", 0.018, 0.046, 20, 0.003, location=(px_p, iy, 2.165), material=mats["brushed_brass"], collection=col_hero)
        # Sculpted matte-black anodized spun-metal conical bell shade + uniform glowing warm brass inner reflector + warm opal bulb!
        _create_lathe_mesh(f"Kit_PendShade_{pi}", shade_outer_prof, (px_p, iy, 1.935), mats["anodized_black"], col_hero, segments=36)
        _create_lathe_mesh(f"Kit_PendBrassInner_{pi}", shade_inner_prof, (px_p, iy, 1.938), mat_pend_inner, col_hero, segments=32)
        _create_lathe_mesh(f"Kit_PendBulb_{pi}", bulb_prof, (px_p, iy, 1.950), mat_pend_bulb, col_hero, segments=20)


def build_zone4_master_bedroom(
    mats: dict[str, bpy.types.Material],
    col_hero: bpy.types.Collection,
    col_bk: bpy.types.Collection,
) -> None:
    """Zone 4 — Aman-Tokyo Architectural Master Suite: Fluted Walnut Feature Wall, Plush Fabric Bed, Porada Closet & Opal Lamps."""
    from materials import make_emissive, make_solid_pbr

    bk = lambda slot: BK_DIR / slot / f"{slot}.glb"
    by = -3.45

    # 1. East 3D Architectural Feature Wall (X = +9.42):
    #    Twin 3D milled vertical oiled-walnut acoustic slat wings flanking a raw cast-concrete central gallery alcove
    #    (Y = -4.65..-2.25) + floating walnut architectural ledge w/ concealed 2700K indirect under-wash (ZERO neon outlines!).
    for side, sy0, sy1 in (("N", -2.25, -1.52), ("S", -5.38, -4.65)):
        create_beveled_box(
            f"Bed_SlatFelt_{side}", (0.012, sy1 - sy0, 2.70), (9.412, (sy0 + sy1) * 0.5, 1.35),
            bevel=0.001, material=mats["acoustic_felt"], collection=col_hero,
        )
        count = 14
        step = (sy1 - sy0) / count
        for i in range(count):
            sy = sy0 + (i + 0.5) * step
            create_beveled_box(
                f"Bed_SlatWall_{side}_{i:02d}", (0.024, step * 0.54, 2.70), (9.394, sy, 1.35),
                bevel=0.002, material=mats["walnut_slat"], uv_scale=1.0, collection=col_hero,
            )

    # Floating oiled-walnut headboard display ledge (top flush Z = 1.138 matching lived_in_storytelling props!)
    create_beveled_box(
        "Bed_WalnutLedge", (0.15, 2.40, 0.036), (9.345, by, 1.120),
        bevel=0.004, material=mats["walnut_desk"], uv_scale=0.85, collection=col_hero,
    )
    # Concealed 2700K indirect LED strip tucked cleanly UNDER the rear lip of the walnut ledge
    create_beveled_box(
        "Bed_LedgeHiddenLED", (0.010, 2.24, 0.006), (9.398, by, 1.098),
        bevel=0.001, material=mats["emissive_bed_cove"], collection=col_hero,
    )

    # 2. Ultra-Plush Cloth-Wrinkled Charcoal-Grey Upholstered Fabric Bed:
    #    Exclude internal sub-floor 'Frame' mesh (Z=-0.647 bug in source GLB!) so bed sits 100% FLUSH at Z=0.000,
    #    headboard top Z=0.93m cleanly beneath floating walnut ledge (Z=1.102), headboard flush against East wall X=+9.38!
    bed_path = bk("bed_soft_fabric") if bk("bed_soft_fabric").exists() else bk("platform_bed_jp")
    bed = import_blenderkit_glb(
        bed_path, "BK_MasterBed", col_bk,
        target_width=1.96, location=(8.24, by, 0.0),
        rotation_xyz_deg=(0.0, 0.0, -90.0), ground_z=0.0,
        exclude_substrings=("frame",),
    )
    bpy.context.view_layer.update()
    b_meshes = [o for o in bed.children_recursive if o.type == "MESH"]
    if b_meshes:
        # Re-normalize North-South width (Y) to exact 1.96m Luxury King, ground Z=0.000, snap headboard flush to East wall X=9.38!
        all_pts = [o.matrix_world @ Vector(c) for o in b_meshes for c in o.bound_box]
        cur_w = max(p.y for p in all_pts) - min(p.y for p in all_pts)
        if cur_w > 0.2:
            bed.scale *= (1.96 / cur_w)
            bpy.context.view_layer.update()
        all_pts = [o.matrix_world @ Vector(c) for o in b_meshes for c in o.bound_box]
        max_x = max(p.x for p in all_pts)
        mid_y = (min(p.y for p in all_pts) + max(p.y for p in all_pts)) * 0.5
        min_z = min(p.z for p in all_pts)
        bed.location.x += (9.38 - max_x)
        bed.location.y += (by - mid_y)
        bed.location.z -= min_z
        bpy.context.view_layer.update()

        # Dress BK_MasterBed in authentic tactile 5-star matte hotel fabrics (fixes broken black-baked Linen_bake_clr!):
        # 1) Heathered charcoal velvet frame: keep crisp 4K fabric texture, force matte Metallic=0, Roughness=0.92, Coat=0!
        # 2) Linen cloth simulation: weld unwelded triangle soup at 1e-5 into exact 6 cloth islands:
        #    comp[0] = Belgian stone-ivory duvet, comp[1] = draped deep charcoal wool throw,
        #    2 rear headboard shams = warm greige linen, 2 front pillows = crisp warm-ivory matte percale cotton!
        mat_duvet = make_solid_pbr("Furn_BedDuvetLinen", (0.68, 0.65, 0.61), roughness=0.94, metallic=0.0, micro_bump_scale=440.0, micro_bump_strength=0.06)
        mat_throw = make_solid_pbr("Furn_BedThrowCharcoal", (0.11, 0.11, 0.12), roughness=0.95, metallic=0.0, micro_bump_scale=400.0, micro_bump_strength=0.07)
        mat_pil_front = make_solid_pbr("Furn_BedPillowIvory", (0.78, 0.76, 0.72), roughness=0.93, metallic=0.0, micro_bump_scale=440.0, micro_bump_strength=0.05)
        mat_pil_rear = make_solid_pbr("Furn_BedPillowWarmTaupe", (0.44, 0.41, 0.37), roughness=0.94, metallic=0.0, micro_bump_scale=420.0, micro_bump_strength=0.06)

        for o in b_meshes:
            on = o.name.lower()
            if "linen" in on:
                import bmesh
                bm = bmesh.new()
                bm.from_mesh(o.data)
                bmesh.ops.remove_doubles(bm, verts=bm.verts, dist=0.00001)
                bm.verts.ensure_lookup_table()
                bm.faces.ensure_lookup_table()
                visited = set()
                islands = []
                for v in bm.verts:
                    if v.index in visited:
                        continue
                    stack = [v]
                    visited.add(v.index)
                    iverts = []
                    while stack:
                        cur = stack.pop()
                        iverts.append(cur)
                        for e in cur.link_edges:
                            ov = e.other_vert(cur)
                            if ov.index not in visited:
                                visited.add(ov.index)
                                stack.append(ov)
                    mean_x = sum((o.matrix_world @ u.co).x for u in iverts) / max(1, len(iverts))
                    islands.append((len(iverts), mean_x, iverts))
                islands.sort(key=lambda t: t[0], reverse=True)
                # Map vertex -> material slot index: 0=duvet, 1=charcoal throw, 2=ivory front pillows, 3=taupe rear shams
                vert_slot: dict[int, int] = {}
                pillows = []
                for idx, (vcnt, mx, iverts) in enumerate(islands):
                    if idx == 0:
                        for u in iverts:
                            vert_slot[u.index] = 0
                    elif idx == 1:
                        for u in iverts:
                            vert_slot[u.index] = 1
                    else:
                        pillows.append((mx, iverts))
                # Sort pillows by world X descending: 2 furthest-East (closest to headboard) = rear taupe shams, rest = front ivory!
                pillows.sort(key=lambda t: t[0], reverse=True)
                for pi, (_, iverts) in enumerate(pillows):
                    s_id = 3 if pi < 2 else 2
                    for u in iverts:
                        vert_slot[u.index] = s_id
                for f in bm.faces:
                    f.material_index = vert_slot.get(f.verts[0].index, 0)
                    f.smooth = True
                o.data.materials.clear()
                for m_slot in (mat_duvet, mat_throw, mat_pil_front, mat_pil_rear):
                    o.data.materials.append(m_slot)
                bm.to_mesh(o.data)
                bm.free()
                o.data.update()
            else:
                # Re-parent ALL children (Linen duvet/pillows!) to `bed` preserving EXACT world matrix BEFORE deleting velvet frame & tiny white brand tag!
                for ch in list(o.children):
                    wm = ch.matrix_world.copy()
                    ch.parent = bed
                    ch.matrix_world = wm
                bpy.context.view_layer.update()
                bpy.data.objects.remove(o, do_unlink=True)

        # Build Sleek Japanese-Industrial Matte-Black Anodized Steel & Brushed-Gunmetal Architectural Platform Bed Frame
        # + Tailored Luxury Hotel Box-Mattress bridging cleanly between the steel platform deck and the sculpted duvet (ZERO hover gap!)
        linen_meshes = [o for o in bed.children_recursive if o.type == "MESH"]
        if linen_meshes:
            lpts = [o.matrix_world @ Vector(c) for o in linen_meshes for c in o.bound_box]
            lx0, lx1 = min(p.x for p in lpts), max(p.x for p in lpts)
            ly0, ly1 = min(p.y for p in lpts), max(p.y for p in lpts)
            lz0 = min(p.z for p in lpts)
            # Note: `Linen` has a draped charcoal throw corner hanging slightly lower on one side, while the duvet base sits ~0.41m!
            # Compute mattress top strictly from the duvet underside (25th-percentile Z of linen vertices!) so zero floating air gap exists!
            all_lz = sorted((o.matrix_world @ v.co).z for o in linen_meshes for v in o.data.vertices)
            duvet_underside_z = all_lz[int(len(all_lz) * 0.12)] if all_lz else (lz0 + 0.14)
            plat_z = max(0.22, duvet_underside_z - 0.17)

            mat_bed_steel = make_solid_pbr("HW_BedFrameDarkSteel", (0.062, 0.065, 0.072), roughness=0.34, metallic=0.88, micro_bump_scale=520.0, micro_bump_strength=0.015)
            mat_bed_trim = make_solid_pbr("HW_BedFrameBrushedGunmetal", (0.18, 0.19, 0.205), roughness=0.28, metallic=0.92)
            mat_mattress = make_solid_pbr("Furn_BedMattressCotton", (0.72, 0.70, 0.66), roughness=0.94, metallic=0.0, micro_bump_scale=480.0, micro_bump_strength=0.06)
            mf_g = _new_group("Bed_MetalFrame", (0.0, 0.0, 0.0), col_hero)
            fx0 = max(7.10, lx0 - 0.02)
            fx1 = 9.37
            fy0 = ly0 - 0.025
            fy1 = ly1 + 0.025
            fw_x = fx1 - fx0
            fw_y = fy1 - fy0
            fcx = (fx0 + fx1) * 0.5
            fcy = (fy0 + fy1) * 0.5
            rail_h = 0.135
            rail_z = plat_z + 0.012  # Hugs the lower edge of the luxury box-mattress cleanly!
            matt_h = (duvet_underside_z + 0.06) - (plat_z - 0.01)
            matt_zc = (plat_z - 0.01) + matt_h * 0.5
            mf_p = [
                # Tailored plush luxury hotel box-mattress seated solidly inside the steel platform rails & seamlessly supporting the duvet!
                create_beveled_box("BedFrame_Mattress", (fw_x - 0.07, fw_y - 0.07, matt_h), (fcx, fcy, matt_zc), bevel=0.024, segments=3, material=mat_mattress, collection=col_hero),
                # Crisp chamfered dark anodized-steel perimeter rails (West footboard, North & South side rails, East back rail)
                create_beveled_box("BedFrame_RailW", (0.044, fw_y + 0.008, rail_h), (fx0, fcy, rail_z), bevel=0.005, material=mat_bed_steel, collection=col_hero),
                create_beveled_box("BedFrame_RailN", (fw_x, 0.044, rail_h), (fcx, fy1, rail_z), bevel=0.005, material=mat_bed_steel, collection=col_hero),
                create_beveled_box("BedFrame_RailS", (fw_x, 0.044, rail_h), (fcx, fy0, rail_z), bevel=0.005, material=mat_bed_steel, collection=col_hero),
                create_beveled_box("BedFrame_RailE", (0.044, fw_y + 0.008, rail_h), (fx1, fcy, rail_z), bevel=0.005, material=mat_bed_steel, collection=col_hero),
                # Hairline brushed-gunmetal inlay trim running along outer perimeter of steel rails
                create_beveled_box("BedFrame_TrimW", (0.006, fw_y + 0.012, 0.012), (fx0 - 0.022, fcy, rail_z + 0.036), bevel=0.001, material=mat_bed_trim, collection=col_hero),
                create_beveled_box("BedFrame_TrimN", (fw_x + 0.006, 0.006, 0.012), (fcx, fy1 + 0.022, rail_z + 0.036), bevel=0.001, material=mat_bed_trim, collection=col_hero),
                create_beveled_box("BedFrame_TrimS", (fw_x + 0.006, 0.006, 0.012), (fcx, fy0 - 0.022, rail_z + 0.036), bevel=0.001, material=mat_bed_trim, collection=col_hero),
                # Solid matte-black recessed steel mattress deck + subtle 2700K under-bed floating halo strip
                create_beveled_box("BedFrame_Deck", (fw_x - 0.04, fw_y - 0.04, 0.032), (fcx, fcy, plat_z - 0.012), bevel=0.002, material=mats["anodized_black"], collection=col_hero),
                create_beveled_box("BedFrame_UnderLED", (fw_x - 0.34, fw_y - 0.34, 0.006), (fcx, fcy, rail_z - rail_h * 0.5 - 0.004), bevel=0.0, material=mats["emissive_shelf_led"], collection=col_hero),
            ]
            # 4 recessed architectural tubular steel corner legs (Z = 0.0..rail bottom) w/ brushed-gunmetal foot ferrules
            leg_h = max(0.08, rail_z - rail_h * 0.5 + 0.01)
            for leg_x in (fx0 + 0.14, fx1 - 0.14):
                for leg_y in (fy0 + 0.14, fy1 - 0.14):
                    mf_p.append(create_beveled_box(f"BedFrame_Leg_{leg_x:.2f}_{leg_y:.2f}", (0.042, 0.042, leg_h), (leg_x, leg_y, leg_h * 0.5), bevel=0.004, material=mat_bed_steel, collection=col_hero))
                    mf_p.append(create_beveled_box(f"BedFrame_Foot_{leg_x:.2f}_{leg_y:.2f}", (0.046, 0.046, 0.016), (leg_x, leg_y, 0.008), bevel=0.002, material=mat_bed_trim, collection=col_hero))
            # Minimalist Japanese-Industrial Brushed-Steel Architectural Headboard Frame behind pillows (X = 9.35, Z = 0.24..1.05)!
            hb_x = 9.35
            mf_p.append(create_beveled_box("BedFrame_HBPostN", (0.036, 0.036, 0.84), (hb_x, fy1 - 0.01, 0.64), bevel=0.004, material=mat_bed_steel, collection=col_hero))
            mf_p.append(create_beveled_box("BedFrame_HBPostS", (0.036, 0.036, 0.84), (hb_x, fy0 + 0.01, 0.64), bevel=0.004, material=mat_bed_steel, collection=col_hero))
            mf_p.append(create_beveled_box("BedFrame_HBTopBar", (0.038, fw_y + 0.01, 0.038), (hb_x, fcy, 1.045), bevel=0.005, material=mat_bed_steel, collection=col_hero))
            mf_p.append(create_beveled_box("BedFrame_HBTopTrim", (0.042, fw_y - 0.04, 0.008), (hb_x - 0.002, fcy, 1.045), bevel=0.001, material=mat_bed_trim, collection=col_hero))
            # Sleek horizontal brushed-steel architectural headboard bars + matte dark charcoal-steel backing plate
            for hbz in (0.48, 0.66, 0.84):
                mf_p.append(create_beveled_box(f"BedFrame_HBBar_{hbz:.2f}", (0.022, fw_y - 0.02, 0.024), (hb_x, fcy, hbz), bevel=0.003, material=mat_bed_trim if hbz == 0.84 else mat_bed_steel, collection=col_hero))
            _parent_all(mf_p, mf_g)

    # 3. Twin Bespoke Floating Oiled-Walnut & Honed-Dark-Marble Nightstands + Italian Cantilevered Opal Bedside Lamps!
    mat_lamp_bulb = bpy.data.materials.get("Emit_BedsideLampBulb") or make_emissive(
        "Emit_BedsideLampBulb", (1.0, 0.78, 0.48), strength=3.6, roughness=0.32
    )
    for side, ny, lrot in (("N", -1.98, -60.0), ("S", -4.92, 160.0)):
        # Floating architectural walnut drawer case (Z = 0.28..0.48) + honed dark marble top (Z = 0.48..0.50) + brass pull
        create_beveled_box(
            f"Bed_Nightstand_Body_{side}", (0.40, 0.54, 0.20), (9.19, ny, 0.38),
            bevel=0.004, material=mats["walnut_desk"], uv_scale=0.90, collection=col_hero,
        )
        create_beveled_box(
            f"Bed_Nightstand_Top_{side}", (0.42, 0.56, 0.022), (9.18, ny, 0.491),
            bevel=0.004, material=mats["dark_marble"], uv_scale=0.80, collection=col_hero,
        )
        create_beveled_box(
            f"Bed_Nightstand_Pull_{side}", (0.012, 0.18, 0.010), (8.985, ny, 0.425),
            bevel=0.002, material=mats["brushed_brass"], collection=col_hero,
        )
        lamp = import_blenderkit_glb(
            bk("bedside_lamp_arch"), f"BK_BedsideLamp_{side}", col_bk,
            target_height=0.42, location=(9.15, ny, 0.502),
            rotation_xyz_deg=(0.0, 0.0, lrot), ground_z=0.502,
        )
        for o in lamp.children_recursive:
            if o.type == "MESH" and ("球体" in o.name or o.name == "NURBS 路径"):
                o.data.materials.clear()
                o.data.materials.append(mat_lamp_bulb)

    # 4. Quiet Solid Warm-Greige Woven Bouclé Bedroom Rug (ZERO striped moiré, anchors bed + end-of-bed bench!)
    mat_bed_rug = make_solid_pbr(
        "Furn_BedBoucleRug", (0.34, 0.32, 0.29),
        roughness=0.95, metallic=0.0, micro_bump_scale=460.0, micro_bump_strength=0.08,
    )
    create_beveled_box(
        "Arch_East_BedroomRug", (2.98, 3.36, 0.006), (7.72, by, 0.003),
        bevel=0.0025, segments=2, material=mat_bed_rug, uv_scale=1.0, collection=col_hero,
    )

    # 5. My Closet by Porada — Italian Oiled Walnut & Matte Graphite Architectural Master Wardrobe (South wall Y = -5.42)!
    #    Modular trim removes ONLY the duplicate leftmost double-door unit (native max_x <= -1.525) along the exact factory seam,
    #    preserving 1 double-door graphite unit + 1.95m backlit walnut shelf/drawer niche + 1 single-door unit at TRUE height!
    porada = import_blenderkit_glb(
        bk("wardrobe_porada"), "BK_PoradaWardrobe", col_bk,
        target_height=2.38, location=(6.62, -5.14, 0.0),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=0.0,
    )
    bpy.context.view_layer.update()
    # Trim leftmost duplicate bay in native pre-rotation coordinates along the exact factory seam!
    p_meshes = [o for o in porada.children_recursive if o.type == "MESH"]
    inv_root = porada.matrix_world.inverted()
    all_raw = [inv_root @ (o.matrix_world @ Vector(c)) for o in p_meshes for c in o.bound_box]
    if all_raw:
        raw_min_x = min(p.x for p in all_raw)
        raw_max_x = max(p.x for p in all_raw)
        # Leftmost duplicate double-door unit occupies the first 1.198m of the 4.941m total native span (ratio = 0.2425)!
        cut_raw_x = raw_min_x + (raw_max_x - raw_min_x) * 0.2425
        for o in list(p_meshes):
            pts_o = [inv_root @ (o.matrix_world @ Vector(c)) for c in o.bound_box]
            if max(p.x for p in pts_o) <= cut_raw_x:
                bpy.data.objects.remove(o, do_unlink=True)
    # Now rotate 180 deg so open backlit walnut shelves & matte-graphite doors face NORTH (+Y) into the bedroom!
    porada.rotation_euler.z = math.radians(180.0)
    bpy.context.view_layer.update()
    rem_meshes = [o for o in porada.children_recursive if o.type == "MESH"]
    if rem_meshes:
        pts_w = [o.matrix_world @ Vector(c) for o in rem_meshes for c in o.bound_box]
        cur_w = max(p.x for p in pts_w) - min(p.x for p in pts_w)
        if cur_w > 0.5:
            porada.scale *= (3.32 / cur_w)
            bpy.context.view_layer.update()
        pts_w = [o.matrix_world @ Vector(c) for o in rem_meshes for c in o.bound_box]
        mid_x = (min(p.x for p in pts_w) + max(p.x for p in pts_w)) * 0.5
        min_y = min(p.y for p in pts_w)
        min_z = min(p.z for p in pts_w)
        porada.location.x += (6.62 - mid_x)
        porada.location.y += (-5.42 - min_y)
        porada.location.z -= min_z
        bpy.context.view_layer.update()

        # Replace stark white-grey shelf tops w/ continuous oiled American walnut + raise satin-matte roughness on back panels
        # so the Porada dressing niche feels warm & architectural with ZERO specular hotspot glare!
        for o in rem_meshes:
            on = o.name.lower()
            if any(k in on for k in ("cube 230.002", "cube 230.003", "obj_000233.013", "obj_000233.014")):
                o.data.materials.clear()
                o.data.materials.append(mats["walnut_desk"])
                uv_l = o.data.uv_layers.active or o.data.uv_layers.new(name="UVMap")
                for poly in o.data.polygons:
                    for li in poly.loop_indices:
                        co = o.data.vertices[o.data.loops[li].vertex_index].co
                        uv_l.data[li].uv = (co.x * 0.95, co.y * 0.95)
            else:
                for slot in o.material_slots:
                    m = slot.material
                    if m and m.node_tree:
                        bsdf = next((n for n in m.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
                        if bsdf:
                            if not bsdf.inputs["Roughness"].is_linked:
                                bsdf.inputs["Roughness"].default_value = max(0.68, bsdf.inputs["Roughness"].default_value)
                            if "Specular IOR Level" in bsdf.inputs and not bsdf.inputs["Specular IOR Level"].is_linked:
                                bsdf.inputs["Specular IOR Level"].default_value = min(0.24, bsdf.inputs["Specular IOR Level"].default_value)

    # Personal Vintage 35mm Film Camera displayed atop the Porada middle-shelf photography monographs (Z = 1.314 + 0.088)
    import_blenderkit_glb(
        bk("vintage_35mm"), "BK_BedClosetCamera", col_bk,
        target_height=0.105, location=(6.46, -5.16, 1.402),
        rotation_xyz_deg=(0.0, 0.0, 22.0), ground_z=1.402,
    )

    # 6. Lush Corner Indoor Greenery in North-West Bedroom Entrance Corner (clear of fluted glass & doorway!)
    bed_plant = import_blenderkit_glb(
        bk("monstera_big"), "BK_BedroomPlant", col_bk,
        target_height=1.24, location=(5.26, -1.96, 0.0),
        rotation_xyz_deg=(0.0, 0.0, -38.0), ground_z=0.0,
    )
    for o in bed_plant.children_recursive:
        if o.type == "MESH" and any(k in o.name.lower() for k in ("pot", "vase", "planter", "cylinder")):
            o.data.materials.clear()
            o.data.materials.append(mats["ceramic_charcoal"])

    # 7. Master Bedroom Minimalist Architectural Ceiling Lighting (Recessed Matte-Black Magnetic Track + Art Wall-Wash Downlights!)
    #    Matches Zone 1 Studio & Zone 2 Living track aesthetic; synced cleanly to whole-home Lutron dimmer (`emissive_track_led`)!
    bcl_g = _new_group("Bed_CeilingLights", (0.0, 0.0, 0.0), col_hero)
    bcl_p: list[bpy.types.Object] = [
        # 2.36m slender matte-black magnetic track rail centered along bedroom ceiling walkway (X=7.05, Y=-3.45, Z=2.748)
        create_beveled_box("Bed_TrackRail", (0.042, 2.36, 0.024), (7.05, -3.45, 2.748), bevel=0.002, material=mats["anodized_black"], collection=col_hero),
    ]
    from mathutils import Euler
    for bty, aim_y in ((-4.32, -16.0), (-3.45, 0.0), (-2.58, 16.0)):
        brot = (math.radians(aim_y), math.radians(-18.0), 0.0)
        bpos = Vector((7.05, bty, 2.676))
        bled = bpos + Euler(brot, "XYZ").to_matrix() @ Vector((0.0, 0.0, -0.047))
        bcl_p.append(create_beveled_cylinder(f"Bed_TrackSpot_{bty:+.2f}", 0.028, 0.098, 20, 0.003, location=tuple(bpos), rotation=brot, material=mats["anodized_black"], collection=col_hero))
        bcl_p.append(create_beveled_cylinder(f"Bed_TrackLED_{bty:+.2f}", 0.022, 0.006, 18, 0.001, location=tuple(bled), rotation=brot, material=mats["emissive_track_led"], collection=col_hero))
    # Twin trimless matte-black anti-glare recessed architectural ceiling downlights washing the framed headboard art & bed!
    for dly in (-2.78, -4.12):
        bcl_p.append(create_beveled_cylinder(f"Bed_DownlightRing_{dly:+.2f}", 0.044, 0.012, 24, 0.002, location=(8.50, dly, 2.754), material=mats["anodized_black"], collection=col_hero))
        bcl_p.append(create_beveled_cylinder(f"Bed_DownlightLED_{dly:+.2f}", 0.030, 0.006, 20, 0.001, location=(8.50, dly, 2.747), material=mats["emissive_track_led"], collection=col_hero))
    _parent_all(bcl_p, bcl_g)


def build_zone5_spa_bathroom(
    mats: dict[str, bpy.types.Material],
    col_hero: bpy.types.Collection,
    col_bk: bpy.types.Collection,
) -> None:
    """Zone 5 — Modern Japanese Dark-Slate Spa Bathroom (X=+6.54..+9.42, Y=-1.45..+2.05)."""
    bk = lambda slot: BK_DIR / slot / f"{slot}.glb"

    # 1. Mathematically Seamless Elliptical Stone-Resin Freestanding Soaking Tub + Flat-Beveled Oiled Walnut Bath Caddy
    #    + Real Matte-Black Floor Filler Faucet & Soft Draped Towel! (Import full GLB first so faucet/towel keep EXACT 1:1 scale,
    #    then delete ONLY the lumpy Cube.014 tub & wavy Bathtub Tray!)
    from materials import make_solid_pbr
    tub = import_blenderkit_glb(
        bk("spa_bathtub_blackfaucet"), "BK_SpaBathtub", col_bk,
        target_width=1.64, location=(8.38, 1.48, 0.002),
        rotation_xyz_deg=(0.0, 0.0, 0.0), ground_z=0.002,
    )
    # Keep ONLY the matte-black floor filler faucet (FillerMaterial) by MATERIAL NAME
    # (100% immune to Blender .001/.014 object renumbering — removes old lumpy tub, clipping old towel, & old wavy tray/tablet!)
    keep_tub_mats = ("fillermaterial",)
    for o in list(tub.children_recursive):
        if o.type != "MESH":
            continue
        mnames = " ".join((s.material.name.lower() if s.material else "") for s in o.material_slots)
        if not any(k in mnames for k in keep_tub_mats):
            bpy.data.objects.remove(o, do_unlink=True)
    # Build classic, timeless contemporary rectangular-with-rounded-corners freestanding soaking tub (Toto / Kohler / Aman style!)
    # Straight gently tapered walls + generous 24cm rounded corners + thin crisp rim + flat floor (ZERO egg distortion, ZERO dents!)
    mat_tub_stone = make_solid_pbr("Furn_SpaTubStoneResin", (0.86, 0.855, 0.845), roughness=0.22, metallic=0.0)
    tub_cx, tub_cy, tub_z0 = 8.38, 1.44, 0.002
    bm_tub = bmesh.new()

    def _rounded_rect_ring(hx: float, hy: float, r_c: float, corner_segs: int = 10) -> list[tuple[float, float]]:
        r = min(r_c, hx * 0.92, hy * 0.92)
        dx_r, dy_r = hx - r, hy - r
        pts: list[tuple[float, float]] = []
        # 4 rounded corners + 2 midpoint subdivisions along each long straight side for silky specular shading!
        corners = [
            (dx_r, dy_r, 0.0, math.pi * 0.5),
            (-dx_r, dy_r, math.pi * 0.5, math.pi),
            (-dx_r, -dy_r, math.pi, math.pi * 1.5),
            (dx_r, -dy_r, math.pi * 1.5, math.pi * 2.0),
        ]
        for ci, (cx_c, cy_c, a0, a1) in enumerate(corners):
            for k in range(corner_segs + 1):
                ang = a0 + (a1 - a0) * (k / corner_segs)
                pts.append((cx_c + r * math.cos(ang), cy_c + r * math.sin(ang)))
            # Insert intermediate edge vertices along straight sides
            if ci in (0, 2):
                y_edge = hy if ci == 0 else -hy
                x_dir = -1.0 if ci == 0 else 1.0
                for s in (0.33, 0.67):
                    pts.append((x_dir * (2.0 * s - 1.0) * dx_r, y_edge))
        return pts

    # Cross-section profile (half_len_x, half_wid_y, corner_r, height_z) — clean classic architectural bathtub!
    tub_prof = [
        (0.000, 0.000, 0.00, 0.000),
        (0.740, 0.320, 0.21, 0.000),
        (0.765, 0.335, 0.22, 0.020),
        (0.785, 0.348, 0.23, 0.140),
        (0.802, 0.360, 0.24, 0.320),
        (0.816, 0.372, 0.245, 0.490),
        (0.820, 0.376, 0.248, 0.542),
        (0.812, 0.368, 0.242, 0.556),
        (0.795, 0.354, 0.232, 0.558),
        (0.780, 0.340, 0.224, 0.546),
        (0.772, 0.332, 0.220, 0.515),
        (0.735, 0.312, 0.205, 0.370),
        (0.675, 0.286, 0.185, 0.210),
        (0.610, 0.260, 0.165, 0.105),
        (0.550, 0.238, 0.145, 0.074),
        (0.000, 0.000, 0.00, 0.070),
    ]
    t_rings = []
    ring_len = 0
    for hx, hy, rc, tz in tub_prof:
        if hx <= 1e-5:
            t_rings.append([bm_tub.verts.new((0.0, 0.0, tz))])
        else:
            rpts = _rounded_rect_ring(hx, hy, rc, corner_segs=10)
            ring_len = len(rpts)
            t_rings.append([bm_tub.verts.new((px, py, tz)) for (px, py) in rpts])
    for ri in range(len(t_rings) - 1):
        a, b = t_rings[ri], t_rings[ri + 1]
        if len(a) == 1:
            for k in range(ring_len):
                bm_tub.faces.new((a[0], b[(k + 1) % ring_len], b[k]))
        elif len(b) == 1:
            for k in range(ring_len):
                bm_tub.faces.new((a[k], a[(k + 1) % ring_len], b[0]))
        else:
            for k in range(ring_len):
                kn = (k + 1) % ring_len
                bm_tub.faces.new((a[k], a[kn], b[kn], b[k]))
    bmesh.ops.recalc_face_normals(bm_tub, faces=bm_tub.faces)
    uv_t = bm_tub.loops.layers.uv.verify()
    for f in bm_tub.faces:
        f.smooth = True
        for lp in f.loops:
            co = lp.vert.co
            lp[uv_t].uv = (co.x * 0.6 + 0.5, co.y * 0.6 + 0.5)
    tmesh = bpy.data.meshes.new("Bath_SculptedTub")
    bm_tub.to_mesh(tmesh)
    bm_tub.free()
    tobj = bpy.data.objects.new("Bath_SculptedTub", tmesh)
    tobj.location = (tub_cx, tub_cy, tub_z0)
    tobj.data.materials.append(mat_tub_stone)
    col_hero.objects.link(tobj)
    # Flush matte-white architectural pop-up drain cap centered cleanly on inner basin floor!
    create_beveled_cylinder("Bath_TubDrainCap", 0.036, 0.008, 28, 0.003, location=(tub_cx, tub_cy, tub_z0 + 0.074), material=mat_tub_stone, collection=col_hero)

    # Strictly FLAT-SHADED Beveled Oiled-Walnut Bath Caddy Bridge resting cleanly across the tub rim (Z = 0.558)!
    # ZERO wavy ceramic specular distortion on wood!
    mat_tub_amber = make_solid_pbr("Prop_TubAmberGlass", (0.16, 0.065, 0.018), roughness=0.14, metallic=0.05)
    cy_x, cy_y, cy_z = tub_cx + 0.28, tub_cy, tub_z0 + 0.568
    create_beveled_box("Bath_WalnutCaddy", (0.22, 0.78, 0.022), (cy_x, cy_y, cy_z), bevel=0.003, segments=2, material=mats["walnut_desk"], uv_scale=1.1, collection=col_hero)
    # Subtle side cleats beneath caddy locking against inner tub rim
    for cl_y in (-0.31, 0.31):
        create_beveled_box(f"Bath_CaddyCleat_{cl_y:+.2f}", (0.18, 0.018, 0.016), (cy_x, cy_y + cl_y, cy_z - 0.018), bevel=0.002, material=mats["walnut_desk"], collection=col_hero)
    # Curated spa caddy styling: charcoal stoneware bath-salt jar + angled matte-black e-reader/tablet + 2 amber Aesop oil bottles!
    create_beveled_cylinder("Bath_CaddyJar", 0.036, 0.044, 24, 0.004, location=(cy_x - 0.01, cy_y + 0.22, cy_z + 0.033), material=mats["ceramic_charcoal"], collection=col_hero)
    create_beveled_box("Bath_CaddyTablet", (0.008, 0.195, 0.135), (cy_x + 0.03, cy_y + 0.02, cy_z + 0.076), rotation=(0.0, math.radians(-16), 0.0), bevel=0.003, material=mats["matte_plastic"], collection=col_hero)
    for bi, (by_o, br, bh) in enumerate(((-0.18, 0.022, 0.095), (-0.24, 0.018, 0.072))):
        create_beveled_cylinder(f"Bath_CaddyBottle_{bi}", br, bh, 20, 0.004, location=(cy_x + 0.01, cy_y + by_o, cy_z + 0.011 + bh * 0.5), material=mat_tub_amber, collection=col_hero)
        create_beveled_cylinder(f"Bath_CaddyCap_{bi}", br * 0.45, 0.016, 16, 0.002, location=(cy_x + 0.01, cy_y + by_o, cy_z + 0.011 + bh + 0.008), material=mats["anodized_black"], collection=col_hero)
    # Warm 2700K architectural ceiling cove wash floating above soaking tub!
    create_beveled_box("Bath_TubCoveLED", (2.40, 0.024, 0.012), (8.10, 1.98, 2.71), bevel=0.001, material=mats["emissive_bath_halo"], collection=col_hero)

    # 2. Floating Oiled Walnut Spa Vanity + Dark Marble Top + Sculpted Stone Vessel Basin + Backlit Circular LED Mirror!
    #    Shifted North to vy=+0.18 (1.16m wide -> Y=-0.40..+0.76) for generous 45cm clear separation from toilet (Y=-1.05)!
    vy = 0.18
    create_beveled_box("Arch_East_BathVanityWalnut", (0.50, 1.14, 0.28), (9.16, vy, 0.66), bevel=0.004, material=mats["walnut_desk"], uv_scale=0.85, collection=col_hero)
    create_beveled_box("Arch_East_BathVanityMarble", (0.52, 1.16, 0.036), (9.15, vy, 0.818), bevel=0.004, material=mats["dark_marble"], uv_scale=0.75, collection=col_hero)
    create_beveled_box("Bath_VanityUnderLED", (0.016, 1.04, 0.008), (9.02, vy, 0.516), bevel=0.001, material=mats["emissive_bath_halo"], collection=col_hero)

    import_blenderkit_glb(
        bk("vessel_sink_stone"), "BK_VesselSink", col_bk,
        target_width=0.60, location=(9.13, vy, 0.836),
        rotation_xyz_deg=(0.0, 0.0, -90.0), ground_z=0.836,
    )
    # Folded charcoal & warm stone-taupe spa towels beside vessel basin (centered cleanly inside 1.16m vanity top!)
    from materials import make_solid_pbr
    mat_spa_towel_taupe = make_solid_pbr("Prop_SpaTowelStone", (0.34, 0.32, 0.30), roughness=0.95, metallic=0.0, micro_bump_scale=360.0, micro_bump_strength=0.08)
    create_beveled_box("Bath_TowelStack1", (0.24, 0.30, 0.044), (9.11, vy - 0.39, 0.836 + 0.022), bevel=0.014, segments=3, material=mats["sofa_charcoal_wool"], collection=col_hero)
    create_beveled_box("Bath_TowelStack2", (0.22, 0.26, 0.040), (9.11, vy - 0.39, 0.836 + 0.062), bevel=0.014, segments=3, material=mat_spa_towel_taupe, collection=col_hero)

    # Large Circular Backlit 2700K Architectural LED Mirror (pulled 1.4cm proud of East slate tile -> FULL 360-deg halo ring!)
    create_beveled_cylinder(
        "Bath_MirrorHaloLED", 0.456, 0.016, 48, 0.004,
        location=(9.392, vy, 1.58), rotation=(0.0, math.radians(90), 0.0),
        material=mats["emissive_bath_halo"], collection=col_hero,
    )
    create_beveled_cylinder(
        "Bath_MirrorFrame", 0.440, 0.018, 48, 0.004,
        location=(9.368, vy, 1.58), rotation=(0.0, math.radians(90), 0.0),
        material=mats["anodized_black"], collection=col_hero,
    )
    create_beveled_cylinder(
        "Bath_MirrorGlass", 0.428, 0.008, 48, 0.001,
        location=(9.358, vy, 1.58), rotation=(0.0, math.radians(90), 0.0),
        material=mats["mirror_silver"], collection=col_hero,
    )

    # 3. Walk-In Frameless Smoked-Glass Rain Shower Enclosure (West Spa Corner: X = 6.54..7.36, Y = -0.68..+0.48 — clear of tub!)
    create_beveled_box("Bath_ShowerCurb", (0.84, 0.055, 0.042), (6.96, -0.68, 0.022), bevel=0.004, material=mats["dark_marble"], collection=col_hero)
    create_beveled_box("Bath_ShowerGlassPanel", (0.012, 1.12, 2.38), (7.36, -0.08, 1.20), bevel=0.0, material=mats["shower_glass"], collection=col_hero)
    create_beveled_box("Bath_ShowerFrameV1", (0.028, 0.028, 2.40), (7.36, 0.48, 1.20), bevel=0.002, material=mats["anodized_black"], collection=col_hero)
    create_beveled_box("Bath_ShowerFrameV2", (0.028, 0.028, 2.40), (7.36, -0.64, 1.20), bevel=0.002, material=mats["anodized_black"], collection=col_hero)
    create_beveled_box("Bath_ShowerStabilizer", (0.82, 0.022, 0.022), (6.95, -0.64, 2.38), bevel=0.002, material=mats["anodized_black"], collection=col_hero)
    # Matte-black ceiling rain-shower head + wall mixer valve + warm recessed shampoo niche!
    create_beveled_cylinder("Bath_RainStem", 0.012, 0.24, 16, 0.002, location=(6.98, 0.08, 2.64), material=mats["anodized_black"], collection=col_hero)
    create_beveled_box("Bath_RainHead", (0.30, 0.30, 0.014), (6.98, 0.08, 2.515), bevel=0.004, material=mats["anodized_black"], collection=col_hero)
    create_beveled_box("Bath_ShowerMixerPlate", (0.018, 0.14, 0.24), (6.555, 0.08, 1.14), bevel=0.003, material=mats["anodized_black"], collection=col_hero)
    create_beveled_cylinder("Bath_ShowerMixerKnob", 0.024, 0.048, 20, 0.003, location=(6.585, 0.08, 1.14), rotation=(0.0, math.radians(90), 0.0), material=mats["brushed_brass"], collection=col_hero)
    create_beveled_box("Bath_NicheLED", (0.010, 0.56, 0.008), (6.56, -0.25, 1.48), bevel=0.001, material=mats["emissive_bath_halo"], collection=col_hero)

    # 4. Minimalist One-Piece Modern Toilet tucked cleanly near South-East privacy corner!
    import_blenderkit_glb(
        bk("modern_toilet"), "BK_SpaToilet", col_bk,
        target_height=0.72, location=(9.06, -1.04, 0.002),
        rotation_xyz_deg=(0.0, 0.0, -90.0), ground_z=0.002,
    )


def apply_phase3_multiroom_lights(mood: str, light_col: bpy.types.Collection) -> None:
    """
    Synchronizes architectural lighting across Zones 2–5 (Living, Kitchen, Bedroom, Spa Bath)
    with the existing Zone 1 Studio mood (midnight / golden / daylight)!
    """
    from lighting_presets import _ensure_light, _set_emissive_strength

    if mood == "noon":
        # High-Noon (~12:30 PM): bright crisp sky portals across Living & Studio, naturally subdued warm indoor fixtures!
        _ensure_light("Light_Z2_WestPortal", "AREA", light_col, (-2.06, -3.68, 1.40), (0.0, -90.0, 0.0), 340.0, (0.88, 0.95, 1.0), size=2.4, size_y=3.2, spread_deg=128.0)
        _ensure_light("Light_Z2_TrackC", "SPOT", light_col, (0.90, -3.70, 2.60), (0.0, 0.0, 0.0), 18.0, (1.0, 0.95, 0.88), size=0.22, spot_size_deg=108.0, spot_blend=1.0)
        _ensure_light("Light_Z3_IslandPendant", "AREA", light_col, (4.25, -0.18, 2.00), (0.0, 0.0, 0.0), 36.0, (1.0, 0.95, 0.88), size=1.40, size_y=0.22, spread_deg=118.0)
        _ensure_light("Light_Z3_UnderCab", "AREA", light_col, (3.96, 1.82, 1.52), (0.0, 0.0, 0.0), 14.0, (1.0, 0.92, 0.80), size=2.60, size_y=0.12, spread_deg=115.0)
        _ensure_light("Light_Z4_BedCove", "AREA", light_col, (7.85, -3.45, 2.55), (0.0, 0.0, 0.0), 62.0, (0.98, 0.96, 0.94), size=2.40, size_y=2.80, spread_deg=134.0)
        _ensure_light("Light_Z4_BedsideN", "POINT", light_col, (8.72, -1.98, 0.78), (0.0, 0.0, 0.0), 6.0, (1.0, 0.88, 0.70), size=0.22)
        _ensure_light("Light_Z4_BedsideS", "POINT", light_col, (8.72, -4.92, 0.78), (0.0, 0.0, 0.0), 6.0, (1.0, 0.88, 0.70), size=0.22)
        _ensure_light("Light_Z4_WardrobeNiche", "AREA", light_col, (6.45, -4.98, 1.80), (0.0, 0.0, 0.0), 14.0, (1.0, 0.88, 0.72), size=1.40, size_y=0.26, spread_deg=122.0)
        _ensure_light("Light_Z5_BathMain", "AREA", light_col, (7.95, 0.30, 2.62), (0.0, 0.0, 0.0), 82.0, (1.0, 0.96, 0.92), size=1.80, size_y=2.20, spread_deg=125.0)
        m_l = _ensure_light("Light_Z5_MirrorHalo", "AREA", light_col, (9.35, 0.18, 1.58), (0.0, -90.0, 0.0), 18.0, (1.0, 0.90, 0.76), size=0.68, size_y=0.68, spread_deg=120.0)
        m_l.visible_camera = False; m_l.visible_glossy = False
        _set_emissive_strength("Emit_BathMirrorHalo", 2.2)
        _set_emissive_strength("Emit_KitchenUnderLED", 1.4)
        _set_emissive_strength("Emit_BedroomCoveLED", 1.2)

    elif mood == "daylight":
        # Living Lounge West Window Portal + soft ambient fill
        _ensure_light("Light_Z2_WestPortal", "AREA", light_col, (-2.06, -3.68, 1.40), (0.0, -90.0, 0.0), 210.0, (0.88, 0.95, 1.0), size=2.4, size_y=3.2, spread_deg=124.0)
        _ensure_light("Light_Z2_TrackC", "SPOT", light_col, (0.90, -3.70, 2.60), (0.0, 0.0, 0.0), 32.0, (1.0, 0.92, 0.80), size=0.22, spot_size_deg=108.0, spot_blend=1.0)
        _ensure_light("Light_Z3_IslandPendant", "AREA", light_col, (4.25, -0.18, 2.00), (0.0, 0.0, 0.0), 48.0, (1.0, 0.92, 0.80), size=1.40, size_y=0.22, spread_deg=118.0)
        _ensure_light("Light_Z3_UnderCab", "AREA", light_col, (3.96, 1.82, 1.52), (0.0, 0.0, 0.0), 22.0, (1.0, 0.88, 0.72), size=2.60, size_y=0.12, spread_deg=115.0)
        _ensure_light("Light_Z4_BedCove", "AREA", light_col, (7.85, -3.45, 2.55), (0.0, 0.0, 0.0), 68.0, (1.0, 0.90, 0.78), size=2.40, size_y=2.80, spread_deg=132.0)
        _ensure_light("Light_Z4_BedsideN", "POINT", light_col, (8.72, -1.98, 0.78), (0.0, 0.0, 0.0), 10.0, (1.0, 0.84, 0.62), size=0.22)
        _ensure_light("Light_Z4_BedsideS", "POINT", light_col, (8.72, -4.92, 0.78), (0.0, 0.0, 0.0), 10.0, (1.0, 0.84, 0.62), size=0.22)
        _ensure_light("Light_Z4_WardrobeNiche", "AREA", light_col, (6.45, -4.98, 1.80), (0.0, 0.0, 0.0), 18.0, (1.0, 0.84, 0.60), size=1.40, size_y=0.26, spread_deg=122.0)
        _ensure_light("Light_Z5_BathMain", "AREA", light_col, (7.95, 0.30, 2.62), (0.0, 0.0, 0.0), 75.0, (1.0, 0.94, 0.86), size=1.80, size_y=2.20, spread_deg=125.0)
        m_l = _ensure_light("Light_Z5_MirrorHalo", "AREA", light_col, (9.35, 0.18, 1.58), (0.0, -90.0, 0.0), 24.0, (1.0, 0.86, 0.66), size=0.68, size_y=0.68, spread_deg=120.0)
        m_l.visible_camera = False; m_l.visible_glossy = False
        _set_emissive_strength("Emit_BathMirrorHalo", 2.8)
        _set_emissive_strength("Emit_KitchenUnderLED", 2.0)
        _set_emissive_strength("Emit_BedroomCoveLED", 1.8)

    elif mood == "golden":
        _ensure_light("Light_Z2_WestPortal", "AREA", light_col, (-2.06, -3.68, 1.40), (0.0, -90.0, 0.0), 108.0, (1.0, 0.68, 0.40), size=2.4, size_y=3.2, spread_deg=120.0)
        _ensure_light("Light_Z2_TrackC", "SPOT", light_col, (0.90, -3.70, 2.60), (0.0, 0.0, 0.0), 82.0, (1.0, 0.80, 0.54), size=0.24, spot_size_deg=110.0, spot_blend=1.0)
        _ensure_light("Light_Z3_IslandPendant", "AREA", light_col, (4.25, -0.18, 2.00), (0.0, 0.0, 0.0), 88.0, (1.0, 0.80, 0.52), size=1.40, size_y=0.22, spread_deg=122.0)
        _ensure_light("Light_Z3_UnderCab", "AREA", light_col, (3.96, 1.82, 1.52), (0.0, 0.0, 0.0), 38.0, (1.0, 0.78, 0.48), size=2.60, size_y=0.12, spread_deg=118.0)
        _ensure_light("Light_Z4_BedCove", "AREA", light_col, (7.85, -3.45, 2.55), (0.0, 0.0, 0.0), 78.0, (1.0, 0.78, 0.50), size=2.40, size_y=2.80, spread_deg=132.0)
        _ensure_light("Light_Z4_BedsideN", "POINT", light_col, (8.72, -1.98, 0.78), (0.0, 0.0, 0.0), 18.0, (1.0, 0.74, 0.42), size=0.22)
        _ensure_light("Light_Z4_BedsideS", "POINT", light_col, (8.72, -4.92, 0.78), (0.0, 0.0, 0.0), 18.0, (1.0, 0.74, 0.42), size=0.22)
        _ensure_light("Light_Z4_WardrobeNiche", "AREA", light_col, (6.45, -4.98, 1.80), (0.0, 0.0, 0.0), 26.0, (1.0, 0.76, 0.46), size=1.40, size_y=0.26, spread_deg=122.0)
        _ensure_light("Light_Z5_BathMain", "AREA", light_col, (7.95, 0.30, 2.62), (0.0, 0.0, 0.0), 72.0, (1.0, 0.84, 0.62), size=1.80, size_y=2.20, spread_deg=125.0)
        m_l = _ensure_light("Light_Z5_MirrorHalo", "AREA", light_col, (9.35, 0.18, 1.58), (0.0, -90.0, 0.0), 42.0, (1.0, 0.78, 0.48), size=0.68, size_y=0.68, spread_deg=120.0)
        m_l.visible_camera = False; m_l.visible_glossy = False
        _set_emissive_strength("Emit_BathMirrorHalo", 4.6)
        _set_emissive_strength("Emit_KitchenUnderLED", 3.4)
        _set_emissive_strength("Emit_BedroomCoveLED", 3.0)

    else:  # midnight — Intimate Architectural Digest 2700K Warm Pools vs Cool Twilight Window Glow!
        _ensure_light("Light_Z2_WestPortal", "AREA", light_col, (-2.08, -3.68, 1.40), (0.0, -90.0, 0.0), 40.0, (0.14, 0.44, 1.0), size=2.3, size_y=3.2, spread_deg=96.0)
        _ensure_light("Light_Z2_TrackC", "SPOT", light_col, (0.90, -3.65, 2.60), (0.0, 0.0, 0.0), 135.0, (1.0, 0.82, 0.56), size=0.26, spot_size_deg=114.0, spot_blend=1.0)
        _ensure_light("Light_Z2_TVBias", "AREA", light_col, (0.90, -5.36, 1.34), (90.0, 0.0, 0.0), 48.0, (1.0, 0.72, 0.42), size=1.45, size_y=0.65, spread_deg=120.0)
        _ensure_light("Light_Z3_IslandPendant", "AREA", light_col, (4.25, -0.18, 2.00), (0.0, 0.0, 0.0), 118.0, (1.0, 0.80, 0.52), size=1.45, size_y=0.24, spread_deg=124.0)
        _ensure_light("Light_Z3_UnderCab", "AREA", light_col, (3.96, 1.82, 1.52), (0.0, 0.0, 0.0), 48.0, (1.0, 0.78, 0.48), size=2.65, size_y=0.14, spread_deg=118.0)
        _ensure_light("Light_Z4_BedCove", "AREA", light_col, (7.85, -3.45, 2.55), (0.0, 0.0, 0.0), 76.0, (1.0, 0.76, 0.48), size=2.40, size_y=2.80, spread_deg=132.0)
        _ensure_light("Light_Z4_BedsideN", "POINT", light_col, (8.72, -1.98, 0.78), (0.0, 0.0, 0.0), 22.0, (1.0, 0.74, 0.42), size=0.22)
        _ensure_light("Light_Z4_BedsideS", "POINT", light_col, (8.72, -4.92, 0.78), (0.0, 0.0, 0.0), 22.0, (1.0, 0.74, 0.42), size=0.22)
        _ensure_light("Light_Z4_WardrobeNiche", "AREA", light_col, (6.45, -4.98, 1.80), (0.0, 0.0, 0.0), 30.0, (1.0, 0.74, 0.44), size=1.40, size_y=0.26, spread_deg=122.0)
        _ensure_light("Light_Z5_BathMain", "AREA", light_col, (7.95, 0.30, 2.62), (0.0, 0.0, 0.0), 82.0, (1.0, 0.82, 0.56), size=1.80, size_y=2.20, spread_deg=128.0)
        m_l = _ensure_light("Light_Z5_MirrorHalo", "AREA", light_col, (9.35, 0.18, 1.58), (0.0, -90.0, 0.0), 54.0, (1.0, 0.78, 0.46), size=0.68, size_y=0.68, spread_deg=120.0)
        m_l.visible_camera = False; m_l.visible_glossy = False
        _set_emissive_strength("Emit_BathMirrorHalo", 5.8)
        _set_emissive_strength("Emit_KitchenUnderLED", 4.2)
        _set_emissive_strength("Emit_BedroomCoveLED", 3.4)
