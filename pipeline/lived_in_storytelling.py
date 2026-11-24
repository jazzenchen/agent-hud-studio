"""
Authentic Tokyo Penthouse Lived-In Storytelling & Architectural Realism Pass (Zones 1–5):
Transforms showroom-clean spaces into an inhabited, tactile home with zero FPS regression:
- Zone 1 Studio: Insulated Fellow Carter desk tumbler, earbuds case, tidy braided standing-desk leg cables,
  Reading Nook draped knit throw, woven footrest pouf & MUJI indoor slippers.
- Zone 2 Living: Plump cognac/linen/olive sofa throw pillows & draped armrest knit throw,
  hollow ceramic candle tray w/ glowing amber Aesop candle, Japanese whisky rocks glass w/ ice cube,
  slim aluminum Apple TV remote, sculpted wireless controller & walnut vinyl LP floor crate.
- Zone 3 Kitchen: Matte-black cast-iron skillet w/ walnut handle on induction burner, leaning walnut cutting board,
  ceramic utensil crock w/ wooden spoons, olive oil & soy cruets w/ brass spouts, barista knock-box/tamper/bean bag,
  slim under-cabinet range hood, folded linen tea towel over oven handle & Polaroid fridge magnets.
- Zone 4 Bedroom: Ajar matte-black & frosted-glass bathroom privacy door (eliminating awkward bed-to-toilet sightline!),
  framed architectural monochrome diptych art above headboard, lived-in South & North nightstands
  (MagSafe phone standby, glass water carafe & tumbler, book w/ bookmark, folded glasses, reed diffuser),
  inhabited smoked-glass wardrobe (brass rod, 11 hanging coats/shirts on hangers, folded knit stacks, storage boxes),
  MUJI bedside slippers & woven blanket basket.
- Zone 5 Spa Bath: Plush waffle bath mat in front of soaking tub, spa slippers, Aesop amber-glass pump bottles
  on walnut vanity tray, stoneware toothbrush tumbler w/ 2 toothbrushes & toothpaste, shower niche shampoo bottles,
  linear shower floor drain & matte-black wall heated towel warmer rail w/ folded taupe towel.
"""

import math
import bmesh
import bpy
from mathutils import Vector

from hero_studio_assets import _new_group, _parent_all, create_curve_tube
from materials import make_arch_glass, make_emissive, make_solid_pbr
from mesh_utils import create_beveled_box, create_beveled_cylinder
from phase3_loft_zones import _add_uv_quad, _create_lathe_mesh


def _world_bbox(obj_name: str) -> tuple[float, float, float, float, float, float] | None:
    obj = bpy.data.objects.get(obj_name)
    if not obj:
        return None
    bpy.context.view_layer.update()
    meshes = [o for o in ([obj] + list(obj.children_recursive)) if o.type == "MESH" and len(o.data.polygons) > 0]
    if not meshes:
        return None
    pts = [o.matrix_world @ Vector(c) for o in meshes for c in o.bound_box]
    return (
        min(p.x for p in pts),
        max(p.x for p in pts),
        min(p.y for p in pts),
        max(p.y for p in pts),
        min(p.z for p in pts),
        max(p.z for p in pts),
    )


def _build_pillowy_cushion(
    name: str,
    size_xyz: tuple[float, float, float],
    location: tuple[float, float, float],
    rotation_deg: tuple[float, float, float],
    material: bpy.types.Material,
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Create a tailored architectural square/lumbar sofa cushion with crisp pinched edges & soft plump core (never a gumdrop blob!)."""
    sx, sy, sz = size_xyz
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.subdivide_edges(bm, edges=bm.edges, cuts=4, use_grid_fill=True)
    for v in bm.verts:
        x, y, z = v.co.x * 2.0, v.co.y * 2.0, v.co.z * 2.0  # [-1..1]
        # Crisp pinched edge seam tapering smoothly into soft center belly + gentle designer corner ear flare
        edge_pinch = max(0.14, (1.0 - 0.82 * x * x) * (1.0 - 0.82 * z * z))
        # Subtle downward gravity settle at bottom edge so cushion hugs sofa seat cleanly
        sag_x = 1.0 + 0.04 * (1.0 - z)
        v.co.x = x * (sx * 0.5) * sag_x
        v.co.y = y * (sy * 0.5) * (0.28 + 0.86 * math.sqrt(edge_pinch))
        v.co.z = z * (sz * 0.5)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    uv = bm.loops.layers.uv.verify()
    for f in bm.faces:
        f.smooth = True
        for lp in f.loops:
            lp[uv].uv = (lp.vert.co.x / max(sx, 0.01) + 0.5, lp.vert.co.z / max(sz, 0.01) + 0.5)
    me = bpy.data.meshes.new(name)
    bm.to_mesh(me)
    bm.free()
    obj = bpy.data.objects.new(name, me)
    obj.location = location
    obj.rotation_euler = tuple(math.radians(a) for a in rotation_deg)
    obj.data.materials.append(material)
    col.objects.link(obj)
    return obj


def _build_slipper_pair(
    prefix: str,
    center: tuple[float, float, float],
    yaw_deg: float,
    sole_mat: bpy.types.Material,
    upper_mat: bpy.types.Material,
    col: bpy.types.Collection,
) -> None:
    """Build a realistic pair of MUJI-style open-toe woven house slippers placed slightly askew."""
    g = _new_group(f"{prefix}_Pair", center, col, rot_z_deg=yaw_deg)
    parts: list[bpy.types.Object] = []
    for side, ox, oy, ang in (("L", -0.068, 0.012, 8.0), ("R", 0.072, -0.018, -11.0)):
        sg = _new_group(f"{prefix}_{side}", (ox, oy, 0.0), col, rot_z_deg=ang)
        sp = [
            create_beveled_box(f"{prefix}_{side}_Sole", (0.098, 0.255, 0.014), (0.0, 0.0, 0.007), bevel=0.006, segments=3, material=sole_mat, collection=col),
            create_beveled_box(f"{prefix}_{side}_Footbed", (0.092, 0.245, 0.008), (0.0, 0.0, 0.016), bevel=0.004, segments=2, material=upper_mat, collection=col),
            # Curved vamp band over forefoot
            create_beveled_cylinder(f"{prefix}_{side}_Band", 0.048, 0.115, 20, 0.008, location=(0.0, 0.025, 0.026), rotation=(math.radians(90), 0.0, 0.0), material=upper_mat, collection=col),
        ]
        # Flatten the vamp cylinder slightly so it hugs the sole cleanly
        sp[-1].scale = (1.02, 1.0, 0.62)
        _parent_all(sp, sg)
        parts.append(sg)
    _parent_all(parts, g)


def _build_apothecary_pump_bottle(
    prefix: str,
    location: tuple[float, float, float],
    radius: float,
    body_h: float,
    bottle_mat: bpy.types.Material,
    label_mat: bpy.types.Material,
    pump_mat: bpy.types.Material,
    col: bpy.types.Collection,
    yaw_deg: float = 0.0,
) -> None:
    """Build an Aesop-style amber/dark glass pump dispenser bottle with cream apothecary label & angled nozzle."""
    g = _new_group(prefix, location, col, rot_z_deg=yaw_deg)
    prof = [
        (0.0, 0.0), (radius * 0.92, 0.0), (radius, 0.008),
        (radius, body_h * 0.78), (radius * 0.86, body_h * 0.90),
        (radius * 0.36, body_h), (radius * 0.36, body_h + 0.016), (0.0, body_h + 0.016),
    ]
    parts = [
        _create_lathe_mesh(f"{prefix}_Body", prof, (0.0, 0.0, 0.0), bottle_mat, col, segments=24),
        create_beveled_cylinder(f"{prefix}_Label", radius + 0.0008, body_h * 0.46, 24, 0.0, location=(0.0, 0.0, body_h * 0.44), material=label_mat, collection=col),
        create_beveled_cylinder(f"{prefix}_Collar", radius * 0.39, 0.020, 18, 0.002, location=(0.0, 0.0, body_h + 0.012), material=pump_mat, collection=col),
        create_beveled_cylinder(f"{prefix}_Stem", radius * 0.14, 0.024, 14, 0.001, location=(0.0, 0.0, body_h + 0.032), material=pump_mat, collection=col),
        create_beveled_box(f"{prefix}_Head", (radius * 0.46, radius * 1.15, 0.013), (0.0, radius * 0.38, body_h + 0.044), bevel=0.003, material=pump_mat, collection=col),
    ]
    _parent_all(parts, g)


def build_all_lived_in_details(
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> None:
    """Populate all 5 loft zones with lived-in architectural warmth & human presence."""
    # Dedicated curated lived-in PBR materials
    mat_oatmeal = make_solid_pbr("Prop_LinenOatmeal", (0.66, 0.61, 0.54), roughness=0.92, metallic=0.0, micro_bump_scale=420.0, micro_bump_strength=0.06)
    mat_olive = make_solid_pbr("Prop_VelvetOlive", (0.14, 0.19, 0.13), roughness=0.88, metallic=0.0, micro_bump_scale=380.0, micro_bump_strength=0.05)
    mat_camel = make_solid_pbr("Prop_WoolCamel", (0.42, 0.29, 0.18), roughness=0.88, metallic=0.0)
    mat_navy_cloth = make_solid_pbr("Prop_ClothNavy", (0.07, 0.10, 0.16), roughness=0.86, metallic=0.0)
    mat_ivory = make_solid_pbr("Prop_ClothIvory", (0.76, 0.74, 0.70), roughness=0.82, metallic=0.0)
    mat_amber_glass = make_solid_pbr("Prop_GlassAmber", (0.16, 0.065, 0.018), roughness=0.10, metallic=0.06, coat_weight=0.75)
    mat_whisky = make_solid_pbr("Prop_WhiskyAmber", (0.48, 0.20, 0.03), roughness=0.06, metallic=0.0)
    mat_candle_wax = make_solid_pbr("Prop_CandleWax", (0.82, 0.78, 0.70), roughness=0.45, metallic=0.0)
    mat_candle_flame = make_emissive("Emit_CandleFlame", (1.0, 0.62, 0.18), strength=9.0, roughness=0.2)
    mat_opal_lamp = make_emissive("Emit_OpalFloorLamp", (1.0, 0.80, 0.56), strength=2.6, roughness=0.42)
    mat_phone_standby = make_emissive("Emit_PhoneStandby", (0.92, 0.34, 0.16), strength=1.4, roughness=0.15)
    mat_cast_iron = make_solid_pbr("Prop_CastIron", (0.032, 0.033, 0.036), roughness=0.58, metallic=0.32, micro_bump_scale=680.0, micro_bump_strength=0.04)
    mat_kraft = make_solid_pbr("Prop_KraftBag", (0.46, 0.36, 0.25), roughness=0.86, metallic=0.0)
    mat_frosted_door = make_arch_glass("Arch_FrostedBathDoor", tint=(0.82, 0.86, 0.88), roughness=0.42, transmission_shadow=True)
    mat_taupe_linen = make_solid_pbr("Prop_SpaTowelStone", (0.36, 0.33, 0.30), roughness=0.95, metallic=0.0, micro_bump_scale=380.0, micro_bump_strength=0.08)
    mat_polaroid = make_solid_pbr("Prop_PolaroidPaper", (0.68, 0.66, 0.62), roughness=0.48, metallic=0.0)
    mat_espresso_wool = make_solid_pbr("Prop_WoolEspresso", (0.14, 0.10, 0.08), roughness=0.90, metallic=0.0)
    mat_greige_cloth = make_solid_pbr("Prop_ClothGreige", (0.42, 0.39, 0.35), roughness=0.88, metallic=0.0)
    mat_clear_glass = mats["shower_glass"]

    # =========================================================================
    # 1. ZONE 1 STUDIO & READING NOOK — TOKYO ARCHITECTURAL LAMP & CURATED DETAILS
    # =========================================================================
    # A. Iconic Minimalist Architectural Opal-Globe Floor Lamp (Flos IC F2 / Noguchi inspired)
    #    Replaces the absurd Hollywood stage Fresnel spotlight with refined Tokyo home lighting!
    fl_x, fl_y = -1.72, 1.44
    # Weighted honed dark-basalt cylinder base + brushed-brass foot ring + ultra-slim anodized black vertical stem
    create_beveled_cylinder("Studio_LampBase", 0.142, 0.048, 32, 0.008, location=(fl_x, fl_y, 0.024), material=mats["ceramic_charcoal"], collection=col)
    create_beveled_cylinder("Studio_LampBrassRing", 0.024, 0.016, 20, 0.002, location=(fl_x, fl_y, 0.056), material=mats["brushed_brass"], collection=col)
    create_beveled_cylinder("Studio_LampStem", 0.009, 1.48, 18, 0.001, location=(fl_x, fl_y, 0.056 + 0.74), material=mats["anodized_black"], collection=col)
    # Brushed-brass cantilevered cross-arm joint holding the warm frosted opal glass sphere cleanly beside the walnut slats!
    create_beveled_cylinder("Studio_LampJoint", 0.015, 0.038, 18, 0.003, location=(fl_x, fl_y, 1.44), material=mats["brushed_brass"], collection=col)
    create_beveled_cylinder("Studio_LampArm", 0.0075, 0.22, 16, 0.002, location=(fl_x + 0.09, fl_y - 0.05, 1.44), rotation=(0.0, math.radians(90), math.radians(-28)), material=mats["brushed_brass"], collection=col)
    create_beveled_cylinder("Studio_LampSocket", 0.024, 0.018, 20, 0.003, location=(fl_x + 0.15, fl_y - 0.085, 1.452), material=mats["brushed_brass"], collection=col)
    # Sculpted smooth warm frosted opal-glass diffuser globe (r=0.128m)
    globe_prof = [
        (0.128 * math.sin(math.pi * i / 20.0), 0.128 * (1.0 - math.cos(math.pi * i / 20.0)))
        for i in range(21)
    ]
    _create_lathe_mesh("Studio_LampOpalGlobe", globe_prof, (fl_x + 0.15, fl_y - 0.085, 1.455), mat_opal_lamp, col, segments=32)

    # B. Floating wall shelf replaced by 3D Modular Honeycomb Neon Wall (Hero_HexNeonWall) — no floating shelf props needed.

    # Matte-black insulated travel tumbler (Fellow Carter) on far-left front walnut desktop (clear of notebook!)
    tumbler_prof = [
        (0.0, 0.0), (0.034, 0.0), (0.038, 0.008), (0.038, 0.148),
        (0.035, 0.155), (0.037, 0.162), (0.036, 0.184), (0.030, 0.188), (0.0, 0.188),
    ]
    _create_lathe_mesh("Studio_InsulatedTumbler", tumbler_prof, (-1.18, 1.16, 0.750), mats["anodized_black"], col, segments=28)
    create_beveled_cylinder("Studio_TumblerRim", 0.0368, 0.005, 28, 0.001, location=(-1.18, 1.16, 0.750 + 0.156), material=mats["brushed_brass"], collection=col)

    # C. Iconic Teenage Engineering OP-1 Field Portable Synthesizer cleanly spaced on open right front walnut desk wing!
    #    (Removed duplicate Studio_EarbudsCase — EDC valet tray at +0.81,+1.44 already holds AirPods Pro w/ ZERO overlap!)
    mat_cnc_silver = make_solid_pbr("HW_OP1Aluminum", (0.64, 0.65, 0.67), roughness=0.28, metallic=0.88)
    mat_op1_blue = make_solid_pbr("HW_OP1KnobBlue", (0.18, 0.56, 0.82), roughness=0.42, metallic=0.04)
    mat_op1_ochre = make_solid_pbr("HW_OP1KnobOchre", (0.82, 0.62, 0.16), roughness=0.42, metallic=0.04)
    mat_op1_orange = make_solid_pbr("HW_OP1KnobOrange", (0.86, 0.28, 0.12), roughness=0.42, metallic=0.04)
    mat_op1_oled = make_emissive("Emit_OP1Display", (0.34, 0.86, 1.0), strength=1.8, roughness=0.18)
    op1_g = _new_group("Studio_OP1FieldSynth", (0.66, 1.22, 0.750), col, rot_z_deg=-10.0)
    op1_p = [
        create_beveled_box("OP1_Chassis", (0.288, 0.102, 0.014), (0.0, 0.0, 0.007), bevel=0.003, material=mat_cnc_silver, collection=col),
        create_beveled_box("OP1_SpeakerGrille", (0.046, 0.046, 0.002), (-0.112, 0.022, 0.0145), bevel=0.001, material=mats["anodized_black"], collection=col),
        create_beveled_box("OP1_OLEDFrame", (0.062, 0.036, 0.003), (-0.042, 0.022, 0.015), bevel=0.001, material=mats["anodized_black"], collection=col),
        create_beveled_box("OP1_OLEDScreen", (0.054, 0.028, 0.001), (-0.042, 0.022, 0.0168), bevel=0.0, material=mat_op1_oled, collection=col),
    ]
    for ki, (kx, kmat) in enumerate((
        (0.012, mat_op1_blue), (0.040, mats["keycap_mod"]), (0.068, mat_op1_ochre), (0.096, mat_op1_orange)
    )):
        op1_p.append(create_beveled_cylinder(f"OP1_Encoder_{ki}", 0.0095, 0.014, 18, 0.002, location=(kx, 0.022, 0.020), material=kmat, collection=col))
    # 14 clean white tactile piano synth keys + 10 black sharps across lower half
    for wi in range(14):
        wx_k = -0.098 + wi * 0.0165
        op1_p.append(create_beveled_box(f"OP1_WKey_{wi}", (0.014, 0.036, 0.004), (wx_k, -0.025, 0.0155), bevel=0.001, material=mat_ivory, collection=col))
        if wi % 7 not in (2, 6) and wi < 13:
            op1_p.append(create_beveled_box(f"OP1_BKey_{wi}", (0.009, 0.020, 0.006), (wx_k + 0.008, -0.014, 0.017), bevel=0.001, material=mats["anodized_black"], collection=col))
    _parent_all(op1_p, op1_g)

    # D. Sleek Matte-Black Smart-UPS Battery Backup tucked cleanly under left-rear desk leg (replaces bathroom pedal trash bin!)
    ups_g = _new_group("Studio_SmartUPS", (-1.04, 1.72, 0.0), col, rot_z_deg=6.0)
    ups_p = [
        create_beveled_box("UPS_Chassis", (0.145, 0.34, 0.245), (0.0, 0.0, 0.1225), bevel=0.005, material=mats["anodized_black"], collection=col),
        create_beveled_box("UPS_FrontBezel", (0.132, 0.012, 0.228), (0.0, -0.172, 0.1225), bevel=0.003, material=mats["matte_plastic"], collection=col),
        create_beveled_box("UPS_LCDDisplay", (0.072, 0.006, 0.034), (0.0, -0.179, 0.184), bevel=0.001, material=mats["emissive_homelab_led"], collection=col),
        create_beveled_box("UPS_VentGrille", (0.112, 0.006, 0.110), (0.0, -0.178, 0.088), bevel=0.001, material=mats["gunmetal"], collection=col),
    ]
    _parent_all(ups_p, ups_g)

    # E. Hardcore Geek 10-Inch Homelab Mini-Rack on Bookshelf Tier 1 Front Bay (replaces duplicate PS5!)
    #    Anodized black open-frame rack w/ 4-Bay Synology NAS + Ubiquiti UniFi 8-Port PoE Switch + emerald/cyan link LEDs!
    hl_g = _new_group("Studio_HomelabMiniRack", (1.89, 0.38, 0.152), col, rot_z_deg=-86.0)
    hl_p = [
        create_beveled_box("HL_BasePlate", (0.28, 0.24, 0.012), (0.0, 0.0, 0.006), bevel=0.002, material=mats["anodized_black"], collection=col),
        create_beveled_box("HL_TopPlate", (0.28, 0.24, 0.012), (0.0, 0.0, 0.348), bevel=0.002, material=mats["anodized_black"], collection=col),
    ]
    for rx in (-0.132, 0.132):
        for ry in (-0.112, 0.112):
            hl_p.append(create_beveled_box(f"HL_Post_{rx:+.2f}_{ry:+.2f}", (0.016, 0.016, 0.35), (rx, ry, 0.177), bevel=0.001, material=mats["anodized_black"], collection=col))
    # Lower 4-Bay Matte-Black Synology DiskStation NAS (Z = 0.016..0.186)
    hl_p.append(create_beveled_box("HL_NAS_Body", (0.242, 0.215, 0.165), (0.0, 0.0, 0.098), bevel=0.004, material=mats["matte_plastic"], collection=col))
    for bay in range(4):
        bx_bay = -0.075 + bay * 0.050
        hl_p.append(create_beveled_box(f"HL_NAS_Bay_{bay}", (0.042, 0.010, 0.138), (bx_bay, -0.109, 0.096), bevel=0.002, material=mats["anodized_black"], collection=col))
        hl_p.append(create_beveled_cylinder(f"HL_NAS_LED_{bay}", 0.0026, 0.004, 10, 0.0, location=(bx_bay, -0.115, 0.152), rotation=(math.radians(90), 0.0, 0.0), material=mats["emissive_homelab_led"], collection=col))
    # Upper Brushed-Aluminum Ubiquiti UniFi 8-Port Managed PoE Switch (Z = 0.23..0.28) + RJ45 Patch Ports + Link LEDs!
    hl_p.append(create_beveled_box("HL_Switch_Body", (0.254, 0.185, 0.048), (0.0, -0.01, 0.268), bevel=0.003, material=mat_cnc_silver, collection=col))
    for port in range(8):
        px_p = -0.092 + port * 0.022
        hl_p.append(create_beveled_box(f"HL_RJ45_{port}", (0.014, 0.008, 0.014), (px_p, -0.103, 0.264), bevel=0.001, material=mats["anodized_black"], collection=col))
        if port in (0, 1, 2, 4, 6):
            hl_p.append(create_beveled_cylinder(f"HL_PortLED_{port}", 0.0022, 0.004, 10, 0.0, location=(px_p, -0.105, 0.278), rotation=(math.radians(90), 0.0, 0.0), material=mats["emissive_homelab_led"] if port != 0 else mats["emissive_rgb_cyan"], collection=col))
    # Brushed-black patch panel strip above switch (Z = 0.305)
    hl_p.append(create_beveled_box("HL_PatchPanel", (0.254, 0.016, 0.032), (0.0, -0.098, 0.318), bevel=0.002, material=mats["anodized_black"], collection=col))
    _parent_all(hl_p, hl_g)

    # Tidy braided standing-desk cable bundle routed neatly down right desk leg to PC tower
    create_curve_tube(
        "Studio_DeskLegCable1",
        [(0.42, 1.78, 0.715), (0.67, 1.72, 0.66), (0.69, 1.54, 0.44), (0.71, 1.54, 0.16), (0.82, 1.58, 0.12)],
        0.0075, mats["anodized_black"], col,
    )
    create_curve_tube(
        "Studio_DeskLegCable2",
        [(0.34, 1.79, 0.715), (0.65, 1.73, 0.64), (0.675, 1.55, 0.42), (0.70, 1.56, 0.14), (0.82, 1.60, 0.10)],
        0.0055, mats["matte_plastic"], col,
    )

    # Reading Nook: Removed dated square footstool & boxy procedural slippers (now cleanly anchored by contemporary fabric lounge chair!)

    # =========================================================================
    # 2. ZONE 2 LIVING & CONSOLE LOUNGE — GALLERY ARCHITECTURE, ACCENT TABLES & COZY WARMTH
    # =========================================================================
    cx = 0.90

    # A. (Removed procedural clipping sofa pillows — BK_LivingSofa now uses real artist woven-linen fabric sofa w/ 4 sculpted organic pillows!)

    # A2. (Removed old South wall Liv_GalleryFrame — replaced by the full-height Rimadesio/Oikos Penthouse Entry Door & Foyer!)

    # A3. Sculptural Honed Dark-Marble & Brushed-Brass Martini Side Table beside the Burnt-Cognac Loafer Lounge Chair!
    mt_x, mt_y = 3.44, -3.14
    create_beveled_cylinder("Liv_MartiniBase", 0.14, 0.018, 28, 0.004, location=(mt_x, mt_y, 0.009), material=mats["dark_marble"], collection=col)
    create_beveled_cylinder("Liv_MartiniStem", 0.011, 0.50, 18, 0.002, location=(mt_x, mt_y, 0.26), material=mats["brushed_brass"], collection=col)
    create_beveled_cylinder("Liv_MartiniTop", 0.19, 0.020, 32, 0.004, location=(mt_x, mt_y, 0.52), material=mats["dark_marble"], collection=col)
    create_beveled_box("Liv_MartiniBook", (0.145, 0.195, 0.020), (mt_x - 0.052, mt_y + 0.016, 0.540), rotation=(0.0, 0.0, math.radians(-14)), bevel=0.002, material=mats["vinyl_cover_1"], collection=col)
    mcup_prof = [(0.0, 0.0), (0.024, 0.0), (0.030, 0.014), (0.031, 0.068), (0.028, 0.070), (0.025, 0.066), (0.024, 0.014), (0.018, 0.006), (0.0, 0.006)]
    _create_lathe_mesh("Liv_MartiniCup", mcup_prof, (mt_x + 0.095, mt_y - 0.056, 0.530), mats["ceramic_charcoal"], col, segments=24)

    # A4. Nested Low Round Dark-Marble Accent Coffee Table paired cleanly beside the walnut coffee table (zero overlap)!
    nt_x, nt_y = cx + 0.86, -4.06
    create_beveled_cylinder("Liv_NestedBase", 0.15, 0.31, 28, 0.004, location=(nt_x, nt_y, 0.155), material=mats["anodized_black"], collection=col)
    create_beveled_cylinder("Liv_NestedTop", 0.25, 0.028, 36, 0.005, location=(nt_x, nt_y, 0.324), material=mats["dark_marble"], collection=col)

    # B. Coffee Table Vignette (Dynamically anchored to BK_LivingCoffeeTable's exact center & top height!):
    #    Hollow stoneware tray + glowing Aesop amber candle + whisky rocks glass w/ ice + Apple TV remote + controller!
    ct_bb = _world_bbox("BK_LivingCoffeeTable")
    ct_cx = (ct_bb[0] + ct_bb[1]) * 0.5 if ct_bb else cx
    ct_cy = (ct_bb[2] + ct_bb[3]) * 0.5 if ct_bb else -4.18
    ct_top = ct_bb[5] if ct_bb else 0.424
    tray_x, tray_y = ct_cx + 0.24, ct_cy + 0.03
    tray_prof = [
        (0.0, 0.0), (0.125, 0.0), (0.138, 0.008), (0.140, 0.022),
        (0.134, 0.024), (0.128, 0.010), (0.0, 0.008),
    ]
    _create_lathe_mesh("Liv_CandleTray_Hollow", tray_prof, (tray_x, tray_y, ct_top), mats["ceramic_charcoal"], col, segments=32)
    # Amber glass scented candle + cream wax + paper label + glowing flame!
    candle_x, candle_y = tray_x - 0.022, tray_y + 0.012
    cjar_prof = [
        (0.0, 0.0), (0.036, 0.0), (0.040, 0.006), (0.040, 0.086),
        (0.037, 0.088), (0.035, 0.084), (0.035, 0.010), (0.0, 0.010),
    ]
    _create_lathe_mesh("Liv_CandleGlass", cjar_prof, (candle_x, candle_y, ct_top + 0.008), mat_amber_glass, col, segments=24)
    create_beveled_cylinder("Liv_CandleLabel", 0.0406, 0.044, 24, 0.0, location=(candle_x, candle_y, ct_top + 0.048), material=mat_polaroid, collection=col)
    create_beveled_cylinder("Liv_CandleWax", 0.0345, 0.056, 20, 0.002, location=(candle_x, candle_y, ct_top + 0.044), material=mat_candle_wax, collection=col)
    flame_prof = [(0.0, 0.0), (0.0055, 0.005), (0.0045, 0.013), (0.0015, 0.022), (0.0, 0.025)]
    _create_lathe_mesh("Liv_CandleFlame", flame_prof, (candle_x, candle_y, ct_top + 0.072), mat_candle_flame, col, segments=14)
    # Brass matchbox resting inside tray beside candle
    create_beveled_box("Liv_MatchBox", (0.056, 0.036, 0.014), (tray_x + 0.052, tray_y - 0.026, ct_top + 0.015), rotation=(0.0, 0.0, math.radians(-26)), bevel=0.002, material=mats["brushed_brass"], collection=col)

    # Japanese Crystal Whisky Rocks Glass (hollow glass + amber whisky + ice cube!) on walnut coaster
    wx_g, wy_g = ct_cx + 0.01, ct_cy + 0.14
    create_beveled_cylinder("Liv_WhiskyCoaster", 0.048, 0.005, 28, 0.0015, location=(wx_g, wy_g, ct_top + 0.0025), material=mats["walnut_desk"], collection=col)
    glass_prof = [
        (0.0, 0.0), (0.034, 0.0), (0.036, 0.014), (0.040, 0.088),
        (0.038, 0.089), (0.036, 0.086), (0.032, 0.016), (0.0, 0.016),
    ]
    _create_lathe_mesh("Liv_WhiskyGlass", glass_prof, (wx_g, wy_g, ct_top + 0.005), mat_clear_glass, col, segments=24)
    create_beveled_cylinder("Liv_WhiskyLiquid", 0.033, 0.028, 22, 0.002, location=(wx_g, wy_g, ct_top + 0.034), material=mat_whisky, collection=col)
    create_beveled_box("Liv_WhiskyIce", (0.026, 0.026, 0.024), (wx_g + 0.004, wy_g - 0.003, ct_top + 0.040), rotation=(math.radians(12), math.radians(-8), math.radians(28)), bevel=0.004, material=mat_clear_glass, collection=col)

    # Slim Brushed-Aluminum Apple TV 4K Remote resting casually on coffee table
    create_beveled_box("Liv_AppleTVRemote", (0.035, 0.136, 0.009), (ct_cx - 0.04, ct_cy - 0.14, ct_top + 0.0045), rotation=(0.0, 0.0, math.radians(18)), bevel=0.003, material=mats["gunmetal"], collection=col)
    create_beveled_cylinder("Liv_RemoteClickpad", 0.012, 0.002, 20, 0.0005, location=(ct_cx - 0.048, ct_cy - 0.112, ct_top + 0.0095), material=mats["anodized_black"], collection=col)

    # (Replaced blocky cylinder-grip procedural DualSense w/ real artist BK_LivingDualSense in phase3_loft_zones.py!)

    # C. Oiled-Walnut Slatted Vinyl LP Floor Crate beside left Hi-Fi speaker (connects Studio turntable to Living Lounge!)
    crate = _new_group("Liv_VinylCrate", (-1.18, -5.04, 0.0), col, rot_z_deg=14.0)
    cr_parts = [
        create_beveled_box("Liv_CrateBottom", (0.36, 0.34, 0.018), (0.0, 0.0, 0.009), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col),
        create_beveled_box("Liv_CrateSideL", (0.016, 0.34, 0.26), (-0.172, 0.0, 0.135), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col),
        create_beveled_box("Liv_CrateSideR", (0.016, 0.34, 0.26), (0.172, 0.0, 0.135), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col),
        create_beveled_box("Liv_CrateFront", (0.34, 0.016, 0.14), (0.0, 0.162, 0.075), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col),
        create_beveled_box("Liv_CrateBack", (0.34, 0.016, 0.26), (0.0, -0.162, 0.135), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col),
    ]
    lp_mats = [mats["vinyl_cover_1"], mats["vinyl_cover_2"], mats["vinyl_cover_3"], mats["vinyl_cover_4"], mats["vinyl_cover_5"], mats["vinyl_cover_6"]]
    for li in range(13):
        ly = -0.125 + li * 0.019
        cr_parts.append(
            create_beveled_box(
                f"Liv_CrateLP_{li:02d}", (0.312, 0.006, 0.312), (0.0, ly, 0.176),
                rotation=(math.radians(-6.0 + (li % 3) * 1.5), 0.0, 0.0),
                bevel=0.001, material=lp_mats[li % len(lp_mats)], collection=col,
            )
        )
    _parent_all(cr_parts, crate)

    # =========================================================================
    # 3. ZONE 3 OPEN KITCHEN — COOKWARE, BARISTA RITUALS & LINEN WARMTH
    # =========================================================================
    cz = 0.922
    # A. Cast-Iron Matte-Black Skillet w/ Oiled-Walnut Handle resting on rear-left induction burner!
    sk_x, sk_y = 4.14, 1.80
    skillet_prof = [
        (0.0, 0.0), (0.105, 0.0), (0.118, 0.010), (0.130, 0.044),
        (0.125, 0.046), (0.120, 0.044), (0.108, 0.010), (0.0, 0.008),
    ]
    _create_lathe_mesh("Kit_CastIronSkillet", skillet_prof, (sk_x, sk_y, 0.929), mat_cast_iron, col, segments=32)
    create_beveled_cylinder("Kit_SkilletNeck", 0.009, 0.045, 12, 0.002, location=(sk_x - 0.136, sk_y - 0.025, 0.968), rotation=(math.radians(82), 0.0, math.radians(-102)), material=mat_cast_iron, collection=col)
    create_beveled_cylinder("Kit_SkilletHandle", 0.014, 0.135, 16, 0.005, location=(sk_x - 0.215, sk_y - 0.044, 0.978), rotation=(math.radians(80), 0.0, math.radians(-102)), material=mats["walnut_desk"], collection=col)

    # B. Leaning Oiled-Walnut End-Grain Cutting Board + Ceramic Utensil Crock + Olive Oil / Soy Cruets!
    create_beveled_box(
        "Kit_CuttingBoard", (0.36, 0.026, 0.25), (5.06, 1.985, cz + 0.124),
        rotation=(math.radians(-10), 0.0, math.radians(4)),
        bevel=0.006, material=mats["walnut_desk"], uv_scale=1.1, collection=col,
    )
    # Matte-black ceramic utensil crock holding 3 wooden cooking tools
    crock_x, crock_y = 5.30, 1.72
    crock_prof = [
        (0.0, 0.0), (0.048, 0.0), (0.054, 0.014), (0.052, 0.145),
        (0.048, 0.148), (0.044, 0.142), (0.044, 0.012), (0.0, 0.012),
    ]
    _create_lathe_mesh("Kit_UtensilCrock", crock_prof, (crock_x, crock_y, cz), mats["ceramic_charcoal"], col, segments=24)
    for ui, (ux, uy, rx, ry) in enumerate(((-0.014, 0.008, 12, -10), (0.016, -0.006, -10, 14), (0.002, -0.014, -14, -6))):
        create_beveled_cylinder(
            f"Kit_WoodSpoon_{ui}", 0.0055, 0.255, 10, 0.002,
            location=(crock_x + ux, crock_y + uy, cz + 0.135),
            rotation=(math.radians(rx), math.radians(ry), 0.0),
            material=mats["walnut_desk"], collection=col,
        )
    # Olive Oil & Soy Sauce dark amber glass cruet bottles w/ brushed-brass pour spouts
    for oi, (ox, oy, bh) in enumerate(((4.84, 1.80, 0.21), (4.94, 1.74, 0.17))):
        cruet_prof = [
            (0.0, 0.0), (0.028, 0.0), (0.030, 0.008), (0.030, bh * 0.72),
            (0.012, bh * 0.90), (0.011, bh), (0.0, bh),
        ]
        _create_lathe_mesh(f"Kit_OilCruet_{oi}", cruet_prof, (ox, oy, cz), mat_amber_glass, col, segments=20)
        create_beveled_cylinder(f"Kit_OilSpout_{oi}", 0.004, 0.036, 10, 0.001, location=(ox, oy, cz + bh + 0.016), rotation=(math.radians(14), 0.0, 0.0), material=mats["brushed_brass"], collection=col)

    # C. Home Barista Espresso Rituals beside Espresso Machine (Knock-Box + Tamper + Coffee Bean Bag!)
    create_beveled_box("Kit_KnockBox", (0.11, 0.12, 0.095), (2.56, 1.56, cz + 0.0475), bevel=0.006, material=mats["anodized_black"], collection=col)
    create_beveled_cylinder("Kit_KnockBar", 0.007, 0.105, 12, 0.001, location=(2.56, 1.56, cz + 0.080), rotation=(0.0, math.radians(90), 0.0), material=mats["gunmetal"], collection=col)
    # Walnut & steel espresso tamper
    create_beveled_cylinder("Kit_TamperBase", 0.028, 0.014, 22, 0.002, location=(2.68, 1.47, cz + 0.007), material=mats["gunmetal"], collection=col)
    create_beveled_cylinder("Kit_TamperHandle", 0.016, 0.068, 18, 0.008, location=(2.68, 1.47, cz + 0.044), material=mats["walnut_desk"], collection=col)
    # Standing specialty roastery craft-paper coffee bean bag
    create_beveled_box("Kit_BeanBag", (0.092, 0.056, 0.195), (2.58, 1.84, cz + 0.0975), rotation=(0.0, 0.0, math.radians(18)), bevel=0.008, segments=2, material=mat_kraft, collection=col)
    create_beveled_box("Kit_BeanBagLabel", (0.066, 0.058, 0.088), (2.58, 1.84, cz + 0.105), rotation=(0.0, 0.0, math.radians(18)), bevel=0.001, material=mat_polaroid, collection=col)

    # D. Recessed Slim Matte-Black Under-Cabinet Range Hood Vent Panel + Acaia Lunar Espresso Scale!
    create_beveled_box("Kit_RangeHoodPanel", (0.82, 0.34, 0.022), (4.35, 1.84, 1.552), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Kit_RangeHoodFilter", (0.68, 0.24, 0.008), (4.35, 1.84, 1.540), bevel=0.001, material=mats["gunmetal"], collection=col)
    # Matte-black CNC Acaia Lunar specialty espresso scale beside Espresso Machine (X=3.14, Y=1.48)
    create_beveled_box("Kit_AcaiaScale", (0.105, 0.105, 0.015), (3.14, 1.48, cz + 0.0075), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Kit_AcaiaPad", (0.092, 0.092, 0.003), (3.14, 1.48, cz + 0.016), bevel=0.001, material=mats["matte_plastic"], collection=col)
    create_beveled_box("Kit_AcaiaLED", (0.032, 0.007, 0.001), (3.14, 1.445, cz + 0.0165), bevel=0.0, material=mats["emissive_shelf_led"], collection=col)

    # E. Minimalist Roastery Tasting Card & Tokyo Tram Gallery Ticket pinned cleanly w/ matte-black bar magnets on upper pantry!
    for pi, (px_m, pz_m, tilt, m_art) in enumerate((
        (5.76, 1.94, 1.5, mats["vinyl_cover_1"]),
        (5.96, 1.89, -2.0, mats["vinyl_cover_4"]),
    )):
        create_beveled_box(f"Kit_FridgeCard_{pi}", (0.072, 0.003, 0.102), (px_m, 1.412, pz_m), rotation=(0.0, math.radians(tilt), 0.0), bevel=0.001, material=m_art, collection=col)
        create_beveled_box(f"Kit_FridgeMagnet_{pi}", (0.028, 0.006, 0.007), (px_m, 1.408, pz_m + 0.044), rotation=(0.0, math.radians(tilt), 0.0), bevel=0.001, material=mats["brushed_brass"], collection=col)

    # =========================================================================
    # 4. ZONE 4 MASTER BEDROOM — ARCHITECTURAL PRIVACY, ART, NIGHTSTANDS & CLOSET
    # =========================================================================
    by = -3.45

    # A. ARCHITECTURAL FIX: Ajar Matte-Black Steel & Frosted-Glass Bathroom Privacy Door!
    #    Hinged on East doorway jamb (8.14, -1.45), swung -80° INWARD into Bathroom (+Y toward East toilet corner!)
    #    -> Zero bedroom intrusion, 0.82m wide open doorway, AND cleanly hides toilet behind frosted glass from bed!
    door_g = _new_group("Arch_BathPrivacyDoor", (8.14, -1.45, 0.0), col, rot_z_deg=-80.0)
    dw, dh, dt = 0.94, 2.40, 0.036
    dp = [
        create_beveled_box("BathDoor_StileHinge", (0.055, dt, dh), (-0.028, 0.0, dh * 0.5), bevel=0.002, material=mats["anodized_black"], collection=col),
        create_beveled_box("BathDoor_StileLatch", (0.055, dt, dh), (-dw + 0.028, 0.0, dh * 0.5), bevel=0.002, material=mats["anodized_black"], collection=col),
        create_beveled_box("BathDoor_RailTop", (dw, dt, 0.065), (-dw * 0.5, 0.0, dh - 0.0325), bevel=0.002, material=mats["anodized_black"], collection=col),
        create_beveled_box("BathDoor_RailBot", (dw, dt, 0.11), (-dw * 0.5, 0.0, 0.055), bevel=0.002, material=mats["anodized_black"], collection=col),
        create_beveled_box("BathDoor_RailMid", (dw - 0.10, dt, 0.032), (-dw * 0.5, 0.0, 1.02), bevel=0.002, material=mats["anodized_black"], collection=col),
        create_beveled_box("BathDoor_FrostedGlass", (dw - 0.11, 0.012, dh - 0.18), (-dw * 0.5, 0.0, dh * 0.5 + 0.02), bevel=0.0, material=mat_frosted_door, collection=col),
        # Brushed-brass lever handles on both sides
        create_beveled_cylinder("BathDoor_RoseF", 0.024, 0.058, 16, 0.002, location=(-dw + 0.068, 0.0, 1.02), rotation=(math.radians(90), 0.0, 0.0), material=mats["brushed_brass"], collection=col),
        create_beveled_box("BathDoor_LeverF", (0.12, 0.014, 0.016), (-dw + 0.125, -0.042, 1.02), bevel=0.003, material=mats["brushed_brass"], collection=col),
        create_beveled_box("BathDoor_LeverB", (0.12, 0.014, 0.016), (-dw + 0.125, 0.042, 1.02), bevel=0.003, material=mats["brushed_brass"], collection=col),
    ]
    _parent_all(dp, door_g)

    # B. Monumental Aman-Tokyo Museum Fine Art Canvas centered cleanly above the architectural walnut ledge!
    #    Uses our bespoke wabi-sabi textured plaster & charcoal horizon fine-art canvas (1.56m x 1.06m landscape!)
    az = 1.82
    aw, ah = 1.56, 1.06
    create_beveled_box("Bed_ArtFrame_Hero", (0.030, aw, ah), (9.392, by, az), bevel=0.003, material=mats["anodized_black"], collection=col)
    pw, ph = aw - 0.036, ah - 0.036
    _add_uv_quad(
        "Bed_ArtPrint_Hero",
        [
            (9.375, by + pw * 0.5, az - ph * 0.5),
            (9.375, by - pw * 0.5, az - ph * 0.5),
            (9.375, by - pw * 0.5, az + ph * 0.5),
            (9.375, by + pw * 0.5, az + ph * 0.5),
        ],
        mats["bed_gallery_hero"], col,
    )

    # C. Tailored End-of-Bed Oiled Walnut, Matte-Black Steel & Charcoal Wool Bench (X = 6.56, Y = -3.45)
    #    Styled cleanly w/ REAL artist-sculpted stacked design magazines + walnut tray + REAL glazed Japanese ceramic teacup (ZERO lumpy cushions!)
    bx_b, by_b = 6.56, by
    create_beveled_box("Bed_BenchFrame", (0.40, 1.44, 0.042), (bx_b, by_b, 0.32), bevel=0.004, material=mats["walnut_desk"], uv_scale=1.0, collection=col)
    create_beveled_box("Bed_BenchCushion", (0.42, 1.42, 0.095), (bx_b, by_b, 0.39), bevel=0.026, segments=3, material=mats["sofa_charcoal_wool"], collection=col)
    for lx in (-0.15, 0.15):
        for ly in (-0.60, 0.60):
            create_beveled_cylinder(f"Bed_BenchLeg_{lx:+.2f}_{ly:+.2f}", 0.015, 0.31, 16, 0.003, location=(bx_b + lx, by_b + ly, 0.155), material=mats["anodized_black"], collection=col)
    bench_top = 0.438
    from config import CACHE_DIR
    from phase3_loft_zones import import_blenderkit_glb
    # Sleek oiled-walnut hotel serving tray on South end w/ REAL artist hand-glazed Yunomi teacup + amber candle jar
    tr_y = by_b - 0.36
    create_beveled_box("Bed_BenchTrayBase", (0.26, 0.36, 0.010), (bx_b, tr_y, bench_top + 0.005), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col)
    for rx, ry, rw, rd in ((0, -0.174, 0.26, 0.012), (0, 0.174, 0.26, 0.012), (-0.124, 0, 0.012, 0.36), (0.124, 0, 0.012, 0.36)):
        create_beveled_box(f"Bed_BenchTrayRim_{rx:+.2f}_{ry:+.2f}", (rw, rd, 0.018), (bx_b + rx, tr_y + ry, bench_top + 0.012), bevel=0.002, material=mats["walnut_desk"], uv_scale=1.2, collection=col)
    bk_cup = CACHE_DIR / "blenderkit" / "nook_jp_teacup" / "nook_jp_teacup.glb"
    if bk_cup.exists():
        import_blenderkit_glb(
            bk_cup, "BK_BedBenchTeacup", col,
            target_height=0.082, location=(bx_b - 0.03, tr_y + 0.07, bench_top + 0.010),
            rotation_xyz_deg=(0.0, 0.0, -32.0), ground_z=bench_top + 0.010,
        )
    _create_lathe_mesh("Bed_BenchCandleJar", cjar_prof, (bx_b + 0.03, tr_y - 0.075, bench_top + 0.010), mat_amber_glass, col, segments=22)
    create_beveled_cylinder("Bed_BenchCandleLabel", 0.0405, 0.042, 22, 0.0, location=(bx_b + 0.03, tr_y - 0.075, bench_top + 0.052), material=mat_polaroid, collection=col)
    create_beveled_cylinder("Bed_BenchCandleWax", 0.034, 0.052, 18, 0.002, location=(bx_b + 0.03, tr_y - 0.075, bench_top + 0.046), material=mat_candle_wax, collection=col)
    # REAL artist-sculpted design magazine stack resting cleanly on the North half of the bench!
    bk_mags = CACHE_DIR / "blenderkit" / "magazine_stack_2" / "magazine_stack_2.glb"
    if bk_mags.exists():
        import_blenderkit_glb(
            bk_mags, "BK_BedBenchMags", col,
            target_width=0.29, location=(bx_b, by_b + 0.32, bench_top),
            rotation_xyz_deg=(0.0, 0.0, 14.0), ground_z=bench_top,
        )

    # D. Curated Headboard Ledge Props (Z = 1.138): Braun alarm clock, amber reed diffuser, B&O Beosound Level speaker!
    ledge_z = 1.138
    create_beveled_box("Bed_AlarmClockBody", (0.044, 0.132, 0.072), (9.32, by + 1.06, ledge_z + 0.036), rotation=(0.0, 0.0, math.radians(-10)), bevel=0.004, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bed_AlarmClockLED", (0.004, 0.082, 0.022), (9.297, by + 1.06, ledge_z + 0.040), rotation=(0.0, 0.0, math.radians(-10)), bevel=0.0, material=mat_phone_standby, collection=col)
    diff_prof = [(0.0, 0.0), (0.028, 0.0), (0.032, 0.014), (0.030, 0.082), (0.014, 0.098), (0.014, 0.112), (0.0, 0.112)]
    _create_lathe_mesh("Bed_ReedDiffuser", diff_prof, (9.32, by - 1.08, ledge_z), mat_amber_glass, col, segments=20)
    for ri, (rx, ry) in enumerate(((14, 8), (-12, 14), (8, -16), (-10, -8))):
        create_beveled_cylinder(
            f"Bed_ReedStick_{ri}", 0.0018, 0.21, 8, 0.0,
            location=(9.32, by - 1.08, ledge_z + 0.12),
            rotation=(math.radians(rx), math.radians(ry), 0.0),
            material=mats["anodized_black"], collection=col,
        )
    create_beveled_box("Bed_BOSpeakerBody", (0.052, 0.32, 0.21), (9.34, by - 0.82, ledge_z + 0.105), rotation=(0.0, math.radians(6), math.radians(8)), bevel=0.008, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bed_BOSpeakerGrille", (0.010, 0.29, 0.18), (9.312, by - 0.82, ledge_z + 0.105), rotation=(0.0, math.radians(6), math.radians(8)), bevel=0.002, material=mats["walnut_slat"], collection=col)

    # E. LIVED-IN NIGHTSTANDS (Z = 0.502 — personal bedtime rituals, eliminates empty hotel side tables!):
    ns_z = 0.502
    # North Nightstand: Bedside glass water carafe + inverted tumbler (9.07, -1.78) + half-read novel & glasses (9.07, -2.17)
    carafe_prof = [
        (0.0, 0.0), (0.036, 0.0), (0.042, 0.018), (0.040, 0.088),
        (0.022, 0.132), (0.025, 0.158), (0.022, 0.158), (0.019, 0.130), (0.036, 0.085), (0.0, 0.008),
    ]
    _create_lathe_mesh("Bed_WaterCarafe", carafe_prof, (9.07, -1.78, ns_z), mat_clear_glass, col, segments=24)
    tumbler_cap_prof = [(0.0, 0.0), (0.028, 0.0), (0.032, 0.062), (0.030, 0.064), (0.026, 0.006), (0.0, 0.006)]
    tcap = _create_lathe_mesh("Bed_WaterTumblerCap", tumbler_cap_prof, (9.07, -1.78, ns_z + 0.198), mat_clear_glass, col, segments=22)
    tcap.rotation_euler = (math.radians(180), 0.0, 0.0)
    create_beveled_box("Bed_NightNovel", (0.145, 0.21, 0.024), (9.08, -2.16, ns_z + 0.012), rotation=(0.0, 0.0, math.radians(-14)), bevel=0.003, material=mats["vinyl_cover_2"], collection=col)
    create_beveled_box("Bed_NovelBookmark", (0.018, 0.048, 0.002), (9.04, -2.26, ns_z + 0.014), rotation=(0.0, 0.0, math.radians(-22)), bevel=0.0, material=mat_camel, collection=col)
    # Slim folded reading glasses resting atop the bedtime novel
    for gx_o in (-0.026, 0.026):
        create_beveled_cylinder(f"Bed_GlassesRim_{gx_o:+.3f}", 0.019, 0.004, 20, 0.001, location=(9.08 + gx_o * 0.2, -2.15 + gx_o, ns_z + 0.027), material=mats["anodized_black"], collection=col)
    create_beveled_box("Bed_GlassesBridge", (0.005, 0.016, 0.004), (9.08, -2.15, ns_z + 0.027), bevel=0.001, material=mats["anodized_black"], collection=col)

    # South Nightstand: Matte-black MagSafe bedside iPhone stand w/ Standby glow (9.07, -5.10) + glowing cedarwood candle (9.07, -4.74)
    ms_g = _new_group("Bed_MagSafeStand", (9.07, -5.10, ns_z), col, rot_z_deg=24.0)
    ms_p = [
        create_beveled_cylinder("Bed_MSBase", 0.036, 0.008, 24, 0.002, location=(0.0, 0.0, 0.004), material=mats["anodized_black"], collection=col),
        create_beveled_cylinder("Bed_MSPost", 0.007, 0.088, 16, 0.002, location=(0.010, 0.0, 0.048), rotation=(0.0, math.radians(-16), 0.0), material=mats["gunmetal"], collection=col),
        create_beveled_box("Bed_MSPhone", (0.009, 0.142, 0.072), (-0.008, 0.0, 0.078), rotation=(0.0, math.radians(-22), 0.0), bevel=0.004, material=mats["anodized_black"], collection=col),
        create_beveled_box("Bed_MSPhoneOLED", (0.002, 0.132, 0.062), (-0.013, 0.0, 0.079), rotation=(0.0, math.radians(-22), 0.0), bevel=0.0, material=mat_phone_standby, collection=col),
    ]
    _parent_all(ms_p, ms_g)
    _create_lathe_mesh("Bed_NightCandleJar", cjar_prof, (9.07, -4.74, ns_z), mat_amber_glass, col, segments=22)
    create_beveled_cylinder("Bed_NightCandleLabel", 0.0405, 0.042, 22, 0.0, location=(9.07, -4.74, ns_z + 0.042), material=mat_polaroid, collection=col)
    create_beveled_cylinder("Bed_NightCandleWax", 0.034, 0.054, 18, 0.002, location=(9.07, -4.74, ns_z + 0.036), material=mat_candle_wax, collection=col)
    _create_lathe_mesh("Bed_NightCandleFlame", flame_prof, (9.07, -4.74, ns_z + 0.066), mat_candle_flame, col, segments=12)

    # F. INHABITED PORADA OPEN DRESSING NICHE (Fills ALL 3 walnut shelves X = 5.52..7.21 w/ real personal home life!):
    mat_oatmeal_knit = make_solid_pbr("Prop_KnitOatmeal", (0.64, 0.60, 0.54), roughness=0.95, metallic=0.0, micro_bump_scale=440.0, micro_bump_strength=0.08)
    mat_olive_knit = make_solid_pbr("Prop_KnitOlive", (0.24, 0.28, 0.22), roughness=0.95, metallic=0.0, micro_bump_scale=440.0, micro_bump_strength=0.08)
    mat_charcoal_bin = make_solid_pbr("Prop_WovenCharcoalBin", (0.15, 0.15, 0.155), roughness=0.93, metallic=0.0, micro_bump_scale=520.0, micro_bump_strength=0.08)
    mat_leaf_closet = make_solid_pbr("Prop_ClosetIvyLeaf", (0.11, 0.25, 0.09), roughness=0.52, metallic=0.0)
    mat_leather_dark = make_solid_pbr("Prop_LeatherCharcoal", (0.09, 0.085, 0.085), roughness=0.46, metallic=0.04)

    # --- PORADA SHELF 1 (Lower Vanity Counter Z = 0.652, Y = -5.39..-4.90) ---
    s1_z = 0.652
    # 1) Walnut & Saddle-Leather Watch / Everyday Valet Tray (X = 5.76, Y = -5.12)
    vt_x, vt_y = 5.76, -5.12
    create_beveled_box("Porada_ValetBase", (0.28, 0.19, 0.014), (vt_x, vt_y, s1_z + 0.007), bevel=0.003, material=mats["walnut_desk"], uv_scale=1.2, collection=col)
    create_beveled_box("Porada_ValetLiner", (0.255, 0.165, 0.004), (vt_x, vt_y, s1_z + 0.015), bevel=0.001, material=mats["leather_cognac"], collection=col)
    for rx, ry, rw, rd in ((0, -0.089, 0.28, 0.012), (0, 0.089, 0.28, 0.012), (-0.134, 0, 0.012, 0.19), (0.134, 0, 0.012, 0.19)):
        create_beveled_box(f"Porada_ValetRim_{rx:+.2f}_{ry:+.2f}", (rw, rd, 0.024), (vt_x + rx, vt_y + ry, s1_z + 0.014), bevel=0.002, material=mats["walnut_desk"], collection=col)
    # 2 Mechanical Wristwatches on dark leather cushions + sunglasses + brass key ring
    for wi, wx_o in enumerate((-0.075, -0.015)):
        create_beveled_box(f"Porada_WatchPillow_{wi}", (0.042, 0.068, 0.026), (vt_x + wx_o, vt_y + 0.012, s1_z + 0.029), bevel=0.008, segments=2, material=mat_leather_dark, collection=col)
        create_beveled_cylinder(f"Porada_WatchCase_{wi}", 0.019, 0.010, 24, 0.002, location=(vt_x + wx_o, vt_y + 0.012, s1_z + 0.045), material=mats["gunmetal"] if wi == 0 else mats["brushed_brass"], collection=col)
        create_beveled_cylinder(f"Porada_WatchDial_{wi}", 0.016, 0.002, 22, 0.0, location=(vt_x + wx_o, vt_y + 0.012, s1_z + 0.0505), material=mats["anodized_black"], collection=col)
    create_beveled_box("Porada_Sunglasses", (0.118, 0.042, 0.022), (vt_x + 0.062, vt_y - 0.016, s1_z + 0.027), rotation=(0.0, 0.0, math.radians(-14)), bevel=0.005, material=mats["anodized_black"], collection=col)
    create_beveled_cylinder("Porada_KeyRing", 0.014, 0.003, 18, 0.001, location=(vt_x + 0.068, vt_y + 0.046, s1_z + 0.018), material=mats["brushed_brass"], collection=col)

    # 2) Le Labo / Byredo Apothecary Perfume Trio + Incense Holder (X = 6.12..6.36, Y = -5.18)
    for fi, (fx, fy, fr, fh, fmat) in enumerate((
        (6.10, -5.20, 0.027, 0.115, mat_amber_glass),
        (6.18, -5.15, 0.023, 0.094, mat_clear_glass),
        (6.26, -5.21, 0.025, 0.104, mat_amber_glass),
    )):
        create_beveled_cylinder(f"Porada_PerfumeBody_{fi}", fr, fh * 0.72, 24, 0.004, location=(fx, fy, s1_z + fh * 0.36), material=fmat, collection=col)
        create_beveled_cylinder(f"Porada_PerfumeLabel_{fi}", fr + 0.0006, fh * 0.44, 24, 0.0, location=(fx, fy, s1_z + fh * 0.36), material=mat_polaroid, collection=col)
        create_beveled_cylinder(f"Porada_PerfumeCap_{fi}", fr * 0.56, fh * 0.24, 20, 0.003, location=(fx, fy, s1_z + fh * 0.84), material=mats["anodized_black"], collection=col)
    create_beveled_cylinder("Porada_IncenseDish", 0.044, 0.008, 24, 0.003, location=(6.35, -5.06, s1_z + 0.004), material=mats["ceramic_charcoal"], collection=col)

    # 3) Personal Leaning Framed Print (X = 6.58, Y = -5.30) + Hand-Thrown Stoneware Catchall Bowl (6.64, -5.04)
    pf_x, pf_y, pf_z = 6.58, -5.30, s1_z + 0.148
    pf_g = _new_group("Porada_LeaningFrame", (pf_x, pf_y, pf_z), col)
    pf_g.rotation_euler = (math.radians(10.0), 0.0, math.radians(-4.0))
    pf_p = [
        create_beveled_box("Porada_FrameRim", (0.24, 0.018, 0.30), (0.0, 0.0, 0.0), bevel=0.002, material=mats["anodized_black"], collection=col),
        create_beveled_box("Porada_FrameMat", (0.22, 0.008, 0.28), (0.0, 0.008, 0.0), bevel=0.0, material=mat_polaroid, collection=col),
        _add_uv_quad("Porada_FrameArt", [(0.085, 0.013, -0.11), (-0.085, 0.013, -0.11), (-0.085, 0.013, 0.11), (0.085, 0.013, 0.11)], mats["living_gallery_hero"], col),
    ]
    _parent_all(pf_p, pf_g)
    cbowl_prof = [(0.0, 0.0), (0.045, 0.0), (0.068, 0.018), (0.072, 0.044), (0.067, 0.046), (0.062, 0.042), (0.042, 0.014), (0.0, 0.012)]
    _create_lathe_mesh("Porada_CatchallBowl", cbowl_prof, (6.64, -5.04, s1_z), mats["ceramic_charcoal"], col, segments=28)

    # 4) Closed Charcoal Leather Weekend Dopp Kit / Travel Pouch + Stacked Pocket Journals (X = 6.96)
    create_beveled_box("Porada_DoppKit", (0.22, 0.115, 0.112), (6.96, -5.19, s1_z + 0.056), rotation=(0.0, 0.0, math.radians(-12)), bevel=0.022, segments=3, material=mat_leather_dark, collection=col)
    create_beveled_box("Porada_DoppZip", (0.19, 0.010, 0.006), (6.96, -5.19, s1_z + 0.113), rotation=(0.0, 0.0, math.radians(-12)), bevel=0.001, material=mats["brushed_brass"], collection=col)
    create_beveled_box("Porada_Journal1", (0.16, 0.11, 0.018), (6.94, -5.01, s1_z + 0.009), rotation=(0.0, 0.0, math.radians(6)), bevel=0.002, material=mats["vinyl_cover_1"], collection=col)
    create_beveled_box("Porada_Journal2", (0.15, 0.105, 0.016), (6.95, -5.01, s1_z + 0.026), rotation=(0.0, 0.0, math.radians(-8)), bevel=0.002, material=mat_kraft, collection=col)

    # --- PORADA SHELF 2 (Middle Display & Knitwear Shelf Z = 1.314, Y = -5.39..-5.04) ---
    s2_z = 1.314
    # 1) Two Plump Soft-Beveled Folded Knitwear / Hoodie Stacks (X = 5.76 & X = 6.08)
    for si, (sx_k, stack_mats) in enumerate((
        (5.76, [mat_olive_knit, mat_oatmeal_knit, mats["sofa_charcoal_wool"]]),
        (6.08, [mat_camel, mat_greige_cloth, mat_espresso_wool]),
    )):
        cur_z = s2_z
        for ki, kmat in enumerate(stack_mats):
            kh = 0.048 - ki * 0.003
            kw = 0.255 - ki * 0.008
            kd = 0.245 - ki * 0.006
            yaw = ((-4.0, 3.0, -2.5)[ki] if si == 0 else (3.5, -4.0, 2.0)[ki])
            create_beveled_box(
                f"Porada_KnitFold_{si}_{ki}", (kw, kd, kh), (sx_k + (ki % 2 - 0.5) * 0.008, -5.20, cur_z + kh * 0.5),
                rotation=(0.0, 0.0, math.radians(yaw)), bevel=0.018, segments=3, material=kmat, collection=col,
            )
            cur_z += kh - 0.004

    # 2) Stacked Japanese Architecture & Photo Monographs (X = 6.46, top Z = 1.402 -> pedestal for BK_BedClosetCamera!)
    cur_bz = s2_z
    for bi, (bw, bd, bh, byaw, bmat) in enumerate((
        (0.28, 0.22, 0.032, 4.0, mats["vinyl_cover_1"]),
        (0.26, 0.20, 0.028, -5.0, mats["vinyl_cover_3"]),
        (0.24, 0.19, 0.028, 2.0, mats["vinyl_cover_4"]),
    )):
        create_beveled_box(
            f"Porada_PhotoBook_{bi}", (bw, bd, bh), (6.46, -5.18, cur_bz + bh * 0.5),
            rotation=(0.0, 0.0, math.radians(byaw)), bevel=0.002, material=bmat, collection=col,
        )
        cur_bz += bh

    # 3) Folded Charcoal Knit Beanie (X = 6.76) + REAL Artist-Sculpted BlenderKit Potted Trailing Plant (ZERO boxy leaves!)
    create_beveled_box("Porada_KnitBeanie", (0.14, 0.15, 0.052), (6.76, -5.18, s2_z + 0.026), rotation=(0.0, 0.0, math.radians(16)), bevel=0.022, segments=3, material=mats["sofa_charcoal_wool"], collection=col)
    from config import CACHE_DIR
    from phase3_loft_zones import import_blenderkit_glb
    bk_potted = CACHE_DIR / "blenderkit" / "potted_plant_bk" / "potted_plant_bk.glb"
    bk_hang = CACHE_DIR / "blenderkit" / "hanging_plant" / "hanging_plant.glb"
    plant_src = bk_potted if bk_potted.exists() else bk_hang
    if plant_src.exists():
        porada_plant = import_blenderkit_glb(
            plant_src, "BK_PoradaShelfPlant", col,
            target_height=0.28, location=(7.00, -5.16, s2_z),
            rotation_xyz_deg=(0.0, 0.0, -28.0), ground_z=s2_z,
        )
        for o in porada_plant.children_recursive:
            if o.type == "MESH" and any(k in o.name.lower() for k in ("pot", "vase", "planter", "bowl", "cup")):
                o.data.materials.clear()
                o.data.materials.append(mats["ceramic_charcoal"])

    # --- PORADA SHELF 3 (Upper Storage & Travel Shelf Z = 1.738, Y = -5.39..-5.04) ---
    s3_z = 1.738
    # 1) Two Architectural Woven Charcoal-Linen Storage Boxes w/ Brass Handles & Index Cards (X = 5.76 & X = 6.14)
    for bi, bx_s in enumerate((5.76, 6.14)):
        create_beveled_box(f"Porada_StorBox_{bi}", (0.33, 0.27, 0.21), (bx_s, -5.20, s3_z + 0.105), bevel=0.006, material=mat_charcoal_bin, collection=col)
        create_beveled_box(f"Porada_StorLid_{bi}", (0.34, 0.28, 0.028), (bx_s, -5.20, s3_z + 0.204), bevel=0.004, material=mat_charcoal_bin, collection=col)
        create_beveled_box(f"Porada_StorLabel_{bi}", (0.068, 0.004, 0.032), (bx_s, -5.063, s3_z + 0.142), bevel=0.001, material=mat_polaroid, collection=col)
        create_beveled_box(f"Porada_StorPull_{bi}", (0.056, 0.012, 0.010), (bx_s, -5.060, s3_z + 0.088), bevel=0.002, material=mats["brushed_brass"], collection=col)

    # 2) Folded Extra Cream & Camel Waffle Blanket Stack (X = 6.56)
    cur_tz = s3_z
    for ti, tmat in enumerate((mat_oatmeal_knit, mat_camel, mat_oatmeal_knit)):
        th = 0.056
        create_beveled_box(f"Porada_ExtraBlanket_{ti}", (0.34, 0.26, th), (6.56, -5.20, cur_tz + th * 0.5), rotation=(0.0, 0.0, math.radians(-2.5 + ti * 2.5)), bevel=0.024, segments=3, material=tmat, collection=col)
        cur_tz += th - 0.004

    # 3) Matte-Black Grooved Aluminum Hard-Shell Gear / Travel Case (X = 6.98)
    create_beveled_box("Porada_TravelCase", (0.26, 0.21, 0.34), (6.98, -5.20, s3_z + 0.17), rotation=(0.0, 0.0, math.radians(-8)), bevel=0.016, segments=3, material=mats["anodized_black"], collection=col)
    for gz in (0.08, 0.14, 0.20, 0.26):
        create_beveled_box(f"Porada_CaseRib_{gz:.2f}", (0.264, 0.214, 0.008), (6.98, -5.20, s3_z + gz), rotation=(0.0, 0.0, math.radians(-8)), bevel=0.002, material=mats["gunmetal"], collection=col)
    create_beveled_box("Porada_CaseHandle", (0.095, 0.024, 0.024), (6.98, -5.20, s3_z + 0.352), rotation=(0.0, 0.0, math.radians(-8)), bevel=0.005, material=mats["anodized_black"], collection=col)

    # G. BEDROOM NORTH WALL ARCHITECTURAL DRESSING NOOK (Y = -1.53, X = 5.65..7.06 — Replaces crude boxy robe/tote!):
    # 1) Refined Full-Length Architectural Dressing Mirror w/ Ultra-Slim Matte-Black + Hairline Brushed-Brass Bezel + Soft Rear Halo!
    fm_g = _new_group("Bed_LeaningMirror", (6.02, -1.62, 0.0), col)
    fm_g.rotation_euler = (math.radians(-2.2), 0.0, 0.0)
    fm_p = [
        create_beveled_box("Bed_MirrorRearLED", (0.60, 0.008, 1.84), (0.0, 0.018, 0.96), bevel=0.001, material=mats["emissive_bed_cove"], collection=col),
        create_beveled_box("Bed_MirrorFrame", (0.68, 0.032, 1.92), (0.0, 0.0, 0.96), bevel=0.005, material=mats["anodized_black"], collection=col),
        create_beveled_box("Bed_MirrorBrassTrim", (0.648, 0.014, 1.888), (0.0, -0.011, 0.96), bevel=0.002, material=mats["brushed_brass"], collection=col),
        create_beveled_box("Bed_MirrorPane", (0.634, 0.008, 1.874), (0.0, -0.015, 0.96), bevel=0.0, material=mats["mirror_silver"], collection=col),
    ]
    _parent_all(fm_p, fm_g)

    # 2) Floating Oiled-Walnut & Honed Dark-Marble Dressing Valet Shelf + Sculpted Stoneware Vase & Framed Vertical Fine Art!
    vs_x, vs_y, vs_z = 6.72, -1.66, 0.84
    create_beveled_box("Bed_ValetShelfBody", (0.56, 0.24, 0.034), (vs_x, vs_y, vs_z), bevel=0.004, material=mats["walnut_desk"], uv_scale=1.0, collection=col)
    create_beveled_box("Bed_ValetShelfMarble", (0.56, 0.24, 0.014), (vs_x, vs_y, vs_z + 0.024), bevel=0.003, material=mats["dark_marble"], uv_scale=0.9, collection=col)
    for br_x in (-0.20, 0.20):
        create_beveled_box(f"Bed_ValetBracket_{br_x:+.2f}", (0.014, 0.16, 0.065), (vs_x + br_x, vs_y + 0.03, vs_z - 0.048), bevel=0.002, material=mats["brushed_brass"], collection=col)
    vtop = vs_z + 0.031
    # Hand-thrown lathe-spun matte-charcoal stoneware vase + 3 slender curved dried olive/eucalyptus branches
    nvase_prof = [
        (0.0, 0.0), (0.038, 0.0), (0.064, 0.045), (0.068, 0.105),
        (0.048, 0.168), (0.026, 0.205), (0.030, 0.224), (0.024, 0.226),
        (0.020, 0.202), (0.042, 0.150), (0.0, 0.016),
    ]
    _create_lathe_mesh("Bed_ValetVase", nvase_prof, (vs_x - 0.15, vs_y + 0.01, vtop), mats["ceramic_charcoal"], col, segments=32)
    for si, (dx_b, dy_b, h_b) in enumerate(((-0.04, -0.02, 0.44), (0.05, -0.03, 0.39), (0.01, 0.03, 0.48))):
        pts_b = [
            (vs_x - 0.15, vs_y + 0.01, vtop + 0.15),
            (vs_x - 0.15 + dx_b * 0.45, vs_y + 0.01 + dy_b * 0.5, vtop + 0.15 + h_b * 0.55),
            (vs_x - 0.15 + dx_b, vs_y + 0.01 + dy_b, vtop + 0.15 + h_b),
        ]
        create_curve_tube(f"Bed_ValetBranch_{si}", pts_b, 0.0024, mats["anodized_black"], col, bevel_res=3)
    # Brushed-brass jewelry dish + hardcover architecture monograph on right half of floating shelf
    bdish_prof = [(0.0, 0.0), (0.042, 0.0), (0.056, 0.010), (0.058, 0.018), (0.053, 0.019), (0.038, 0.006), (0.0, 0.006)]
    _create_lathe_mesh("Bed_ValetBrassDish", bdish_prof, (vs_x + 0.14, vs_y - 0.02, vtop), mats["brushed_brass"], col, segments=28)
    create_beveled_box("Bed_ValetMonograph", (0.20, 0.16, 0.024), (vs_x + 0.08, vs_y + 0.01, vtop + 0.012), rotation=(0.0, 0.0, math.radians(-6)), bevel=0.002, material=mats["vinyl_cover_4"], collection=col)

    # Framed Vertical Minimalist Sumi Ink Fine-Art Print cleanly mounted above valet shelf (Z = 1.54m)
    fa_w, fa_h = 0.40, 0.54
    create_beveled_box("Bed_NookArtFrame", (fa_w, 0.022, fa_h), (vs_x, -1.542, 1.54), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bed_NookArtMat", (fa_w - 0.028, 0.008, fa_h - 0.028), (vs_x, -1.552, 1.54), bevel=0.0, material=mat_polaroid, collection=col)
    _add_uv_quad(
        "Bed_NookArtPrint",
        [
            (vs_x - 0.14, -1.557, 1.54 - 0.20),
            (vs_x + 0.14, -1.557, 1.54 - 0.20),
            (vs_x + 0.14, -1.557, 1.54 + 0.20),
            (vs_x - 0.14, -1.557, 1.54 + 0.20),
        ],
        mats["bed_art_sumi"], col,
    )

    # =========================================================================
    # 5. ZONE 5 MODERN SPA BATHROOM — AESOP RITUALS, WOVEN BATH MAT & HEATED RAIL
    # =========================================================================
    vy = 0.18
    vz = 0.836

    # A. Clean Solid Warm-Stone Japanese Cotton Bath Mat right in front of Soaking Tub (zero noisy pattern!)
    mat_bath_mat = make_solid_pbr("Prop_BathCottonMat", (0.46, 0.44, 0.41), roughness=0.95, metallic=0.0, micro_bump_scale=460.0, micro_bump_strength=0.08)
    bmat = create_beveled_box("Bath_WaffleMat", (0.86, 0.54, 0.010), (8.28, 0.72, 0.005), bevel=0.004, segments=2, material=mat_bath_mat, uv_scale=1.0, collection=col)
    uv_bm = bmat.data.uv_layers.active
    for poly in bmat.data.polygons:
        for li in poly.loop_indices:
            v = bmat.data.vertices[bmat.data.loops[li].vertex_index].co
            uv_bm.data[li].uv = ((v.x / 0.86) + 0.5, (v.y / 0.54) + 0.5)

    # B. Aesop-Inspired Vanity Countertop (Walnut Amenity Tray + 2 Amber Pump Bottles + Toothbrush Tumbler + Spa Candle!)
    create_beveled_box("Bath_VanityTray", (0.15, 0.30, 0.012), (9.08, vy + 0.39, vz + 0.006), bevel=0.003, material=mats["walnut_desk"], uv_scale=1.2, collection=col)
    _build_apothecary_pump_bottle("Bath_AesopHandWash", (9.08, vy + 0.45, vz + 0.012), 0.030, 0.132, mat_amber_glass, mat_polaroid, mats["anodized_black"], col, yaw_deg=110.0)
    _build_apothecary_pump_bottle("Bath_AesopHandBalm", (9.09, vy + 0.36, vz + 0.012), 0.026, 0.112, mat_amber_glass, mat_polaroid, mats["anodized_black"], col, yaw_deg=92.0)

    # Hollow Stoneware Toothbrush Tumbler + 2 Angled Toothbrushes (Charcoal + Ivory) + Rolled Toothpaste Tube
    tb_x, tb_y = 9.04, vy + 0.27
    tb_prof = [
        (0.0, 0.0), (0.028, 0.0), (0.032, 0.014), (0.034, 0.098),
        (0.031, 0.100), (0.028, 0.095), (0.026, 0.012), (0.0, 0.012),
    ]
    _create_lathe_mesh("Bath_ToothbrushCup", tb_prof, (tb_x, tb_y, vz), mats["ceramic_charcoal"], col, segments=24)
    for ti, (tx_o, ty_o, ang_x, ang_y, tmat) in enumerate(((0.006, 0.005, 10, -14, mats["anodized_black"]), (-0.007, -0.006, -12, 12, mat_ivory))):
        create_beveled_cylinder(f"Bath_BrushStem_{ti}", 0.0042, 0.165, 10, 0.002, location=(tb_x + tx_o, tb_y + ty_o, vz + 0.092), rotation=(math.radians(ang_x), math.radians(ang_y), 0.0), material=tmat, collection=col)
        create_beveled_box(f"Bath_BrushBristles_{ti}", (0.009, 0.012, 0.022), (tb_x + tx_o * 2.8, tb_y + ty_o * 2.8, vz + 0.168), rotation=(math.radians(ang_x), math.radians(ang_y), 0.0), bevel=0.002, material=mat_ivory, collection=col)
    # Aluminum toothpaste tube leaning neatly inside tumbler
    create_beveled_cylinder("Bath_ToothpasteTube", 0.011, 0.115, 12, 0.003, location=(tb_x + 0.004, tb_y - 0.010, vz + 0.068), rotation=(math.radians(-14), math.radians(-8), 0.0), material=mat_polaroid, collection=col)

    # Tiny Glowing Aromatic Spa Candle beside folded vanity towels
    sc_x, sc_y = 8.99, vy - 0.24
    _create_lathe_mesh("Bath_SpaCandleJar", cjar_prof, (sc_x, sc_y, vz), mat_amber_glass, col, segments=20)
    create_beveled_cylinder("Bath_SpaCandleWax", 0.034, 0.054, 18, 0.002, location=(sc_x, sc_y, vz + 0.036), material=mat_candle_wax, collection=col)
    _create_lathe_mesh("Bath_SpaCandleFlame", flame_prof, (sc_x, sc_y, vz + 0.064), mat_candle_flame, col, segments=12)

    # B2. Architectural Matte-Black & Brushed-Brass Toilet Paper Holder + Dual-Flush Plate on Tiled South/East Toilet Walls!
    tp_x, tp_y, tp_z = 8.94, -1.365, 0.66
    create_beveled_box("Bath_TPHolderPlate", (0.145, 0.012, 0.036), (tp_x, tp_y, tp_z), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bath_TPHolderArm", (0.135, 0.075, 0.012), (tp_x, tp_y + 0.042, tp_z + 0.010), bevel=0.002, material=mats["anodized_black"], collection=col)
    create_beveled_cylinder("Bath_TPRoll", 0.052, 0.108, 24, 0.004, location=(tp_x, tp_y + 0.058, tp_z - 0.044), rotation=(0.0, math.radians(90), 0.0), material=mat_ivory, collection=col)
    create_beveled_cylinder("Bath_TPCore", 0.020, 0.112, 16, 0.001, location=(tp_x, tp_y + 0.058, tp_z - 0.044), rotation=(0.0, math.radians(90), 0.0), material=mats["anodized_black"], collection=col)
    # Recessed matte-black architectural dual-flush wall plate above toilet (East tile wall X=9.41, Y=-1.04, Z=1.04)
    create_beveled_box("Bath_FlushPlate", (0.012, 0.21, 0.135), (9.412, -1.04, 1.04), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bath_FlushBtnL", (0.014, 0.075, 0.072), (9.408, -1.00, 1.04), bevel=0.002, material=mats["gunmetal"], collection=col)
    create_beveled_box("Bath_FlushBtnS", (0.014, 0.046, 0.072), (9.408, -1.075, 1.04), bevel=0.002, material=mats["brushed_brass"], collection=col)

    # C. Inhabited Walk-In Rain Shower: Dark-Marble Niche Ledge + 3 Shampoo/Bodywash Bottles + Linear Floor Drain!
    create_beveled_box("Bath_ShowerLedge", (0.14, 0.62, 0.024), (6.61, -0.25, 1.18), bevel=0.003, material=mats["dark_marble"], uv_scale=1.0, collection=col)
    _build_apothecary_pump_bottle("Bath_Shampoo", (6.62, -0.42, 1.192), 0.030, 0.148, mat_amber_glass, mat_polaroid, mats["anodized_black"], col, yaw_deg=-90.0)
    _build_apothecary_pump_bottle("Bath_Conditioner", (6.62, -0.28, 1.192), 0.030, 0.148, mat_amber_glass, mat_polaroid, mats["anodized_black"], col, yaw_deg=-90.0)
    _build_apothecary_pump_bottle("Bath_BodyWash", (6.62, -0.14, 1.192), 0.030, 0.132, mats["anodized_black"], mat_polaroid, mats["anodized_black"], col, yaw_deg=-90.0)
    # Flush matte-black linear stainless floor drain grate inside shower enclosure
    create_beveled_box("Bath_LinearDrainFrame", (0.082, 0.72, 0.006), (6.72, -0.08, 0.003), bevel=0.001, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bath_LinearDrainSlit", (0.056, 0.68, 0.008), (6.72, -0.08, 0.0035), bevel=0.0, material=mats["gunmetal"], collection=col)

    # D. Matte-Black Heated Wall Towel Warmer Ladder Rail beside Soaking Tub + Folded Taupe Towel!
    rx_t, ry_t = 7.04, 1.98
    for side_x in (-0.22, 0.22):
        create_beveled_cylinder(f"Bath_WarmerPost_{side_x:+.2f}", 0.011, 0.96, 14, 0.002, location=(rx_t + side_x, ry_t, 1.32), material=mats["anodized_black"], collection=col)
        for mz in (0.94, 1.70):
            create_beveled_cylinder(f"Bath_WarmerMount_{side_x:+.2f}_{mz:.2f}", 0.009, 0.065, 12, 0.001, location=(rx_t + side_x, ry_t + 0.035, mz), rotation=(math.radians(90), 0.0, 0.0), material=mats["anodized_black"], collection=col)
    for bi, bz in enumerate((0.92, 1.06, 1.20, 1.34, 1.48, 1.62, 1.74)):
        create_beveled_cylinder(f"Bath_WarmerRung_{bi}", 0.008, 0.44, 12, 0.001, location=(rx_t, ry_t, bz), rotation=(0.0, math.radians(90), 0.0), material=mats["anodized_black"], collection=col)
    # Warm folded stone-taupe bath towel hung cleanly over rung Z=1.48 (muted spa tone, zero stark white square!)
    create_beveled_box("Bath_RailTowelFold", (0.34, 0.036, 0.024), (rx_t, ry_t, 1.485), bevel=0.009, segments=2, material=mat_taupe_linen, collection=col)
    create_beveled_box("Bath_RailTowelFront", (0.34, 0.016, 0.34), (rx_t, ry_t - 0.014, 1.315), bevel=0.007, segments=2, material=mat_taupe_linen, collection=col)
    create_beveled_box("Bath_RailTowelBack", (0.34, 0.014, 0.30), (rx_t, ry_t + 0.013, 1.335), bevel=0.006, segments=2, material=mat_taupe_linen, collection=col)

    # E. Aman-Tokyo Recessed Illuminated Architectural Spa Wall Niche above Soaking Tub (North wall Y = 2.02)!
    nx_b, ny_b, nz_b = 8.42, 2.015, 1.38
    create_beveled_box("Bath_NicheBack", (0.76, 0.016, 0.32), (nx_b, ny_b + 0.020, nz_b), bevel=0.002, material=mats["kitchen_matte_black"], collection=col)
    create_beveled_box("Bath_NicheTop", (0.78, 0.095, 0.022), (nx_b, ny_b - 0.020, nz_b + 0.16), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bath_NicheBot", (0.78, 0.115, 0.024), (nx_b, ny_b - 0.030, nz_b - 0.16), bevel=0.003, material=mats["dark_marble"], uv_scale=1.0, collection=col)
    create_beveled_box("Bath_NicheSideL", (0.022, 0.095, 0.34), (nx_b - 0.38, ny_b - 0.020, nz_b), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bath_NicheSideR", (0.022, 0.095, 0.34), (nx_b + 0.38, ny_b - 0.020, nz_b), bevel=0.003, material=mats["anodized_black"], collection=col)
    create_beveled_box("Bath_NicheLED", (0.70, 0.014, 0.006), (nx_b, ny_b - 0.020, nz_b + 0.146), bevel=0.001, material=mats["emissive_bath_halo"], collection=col)
    # Rolled charcoal spa towels + amber Hinoki essence bottle + dark stoneware jar inside illuminated spa niche!
    for ti, tx_n in enumerate((-0.24, -0.14)):
        create_beveled_cylinder(f"Bath_NicheTowel_{ti}", 0.044, 0.11, 20, 0.010, location=(nx_b + tx_n, ny_b - 0.022, nz_b - 0.104), rotation=(math.radians(90), 0.0, 0.0), material=mats["sofa_charcoal_wool"] if ti == 0 else mat_taupe_linen, collection=col)
    _build_apothecary_pump_bottle("Bath_NicheHinoki", (nx_b + 0.12, ny_b - 0.028, nz_b - 0.148), 0.028, 0.142, mat_amber_glass, mat_polaroid, mats["anodized_black"], col, yaw_deg=180.0)
    create_beveled_cylinder("Bath_NicheSaltJar", 0.034, 0.092, 20, 0.005, location=(nx_b + 0.24, ny_b - 0.028, nz_b - 0.102), material=mats["ceramic_charcoal"], collection=col)
