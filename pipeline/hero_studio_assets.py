"""
High-precision Blender hero asset builders for the Geek Loft Studio Vertical Slice.
Every hard surface enforces micro-bevels (2-5mm), WeightedNormal shading, and real-world scale.
Soft elements (curtains, mouse, chair contours) use Subdivision Surface & Blender Cloth Physics.
"""

import math
import bmesh
import bpy
from mathutils import Euler, Vector

from mesh_utils import (
    apply_box_uv,
    create_beveled_box,
    create_beveled_cylinder,
    create_curved_panel,
    set_smooth_with_bevel_normals,
)


def _new_group(name: str, location: tuple[float, float, float], col: bpy.types.Collection, rot_z_deg: float = 0.0) -> bpy.types.Object:
    empty = bpy.data.objects.new(name, None)
    empty.empty_display_type = "PLAIN_AXES"
    empty.empty_display_size = 0.08
    empty.location = location
    empty.rotation_euler = (0.0, 0.0, math.radians(rot_z_deg))
    col.objects.link(empty)
    return empty


def _parent_all(objs: list[bpy.types.Object], parent: bpy.types.Object) -> None:
    for o in objs:
        o.parent = parent


def create_curve_tube(
    name: str,
    points: list[tuple[float, float, float]],
    radius: float,
    material: bpy.types.Material,
    col: bpy.types.Collection,
    bevel_res: int = 8,
    convert_to_mesh: bool = True,
) -> bpy.types.Object:
    curve_data = bpy.data.curves.new(name=f"{name}_Curve", type="CURVE")
    curve_data.dimensions = "3D"
    curve_data.resolution_u = 16
    curve_data.bevel_depth = radius
    curve_data.bevel_resolution = bevel_res
    curve_data.use_fill_caps = True

    spline = curve_data.splines.new(type="NURBS")
    spline.points.add(len(points) - 1)
    for idx, pt in enumerate(points):
        spline.points[idx].co = (pt[0], pt[1], pt[2], 1.0)
    spline.use_endpoint_u = True
    spline.order_u = min(4, len(points))

    obj = bpy.data.objects.new(name, curve_data)
    col.objects.link(obj)

    if convert_to_mesh:
        bpy.context.view_layer.update()
        deps = bpy.context.evaluated_depsgraph_get()
        eval_obj = obj.evaluated_get(deps)
        mesh = bpy.data.meshes.new_from_object(eval_obj)
        mesh.name = name
        apply_box_uv(mesh, scale=4.0)
        mesh_obj = bpy.data.objects.new(name, mesh)
        mesh_obj.data.materials.append(material)
        mesh_obj.data.polygons.foreach_set("use_smooth", [True] * len(mesh_obj.data.polygons))
        col.objects.link(mesh_obj)
        bpy.data.objects.remove(obj, do_unlink=True)
        bpy.data.curves.remove(curve_data, do_unlink=True)
        return mesh_obj

    obj.data.materials.append(material)
    return obj


def build_standing_desk(
    location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """2.24m x 0.84m solid chamfered American walnut motorized standing desk."""
    root = _new_group("Hero_StandingDesk", location, col)
    parts: list[bpy.types.Object] = []

    desk_w, desk_d, top_t = 2.24, 0.84, 0.038
    desk_h = 0.750

    # Solid walnut tabletop (top surface at Z = desk_h)
    top = create_beveled_box(
        "Desk_WalnutTop",
        (desk_w, desk_d, top_t),
        location=(0.0, 0.0, desk_h - top_t * 0.5),
        bevel=0.005,
        segments=4,
        material=mats["walnut_desk"],
        uv_scale=0.8,
        collection=col,
    )
    parts.append(top)

    # Rear recessed anodized cable grommet trim
    grommet = create_beveled_box(
        "Desk_CableGrommet",
        (0.28, 0.065, 0.006),
        location=(-0.04, desk_d * 0.5 - 0.075, desk_h - 0.001),
        bevel=0.002,
        segments=2,
        material=mats["anodized_black"],
        collection=col,
    )
    parts.append(grommet)

    # Under-desk steel support frame rails (recessed cleanly inside ±0.76m cantilevered T-legs!)
    for ry in (-0.22, 0.22):
        rail = create_beveled_box(
            f"Desk_FrameRail_{ry:+.2f}",
            (1.62, 0.045, 0.035),
            location=(0.0, ry, desk_h - top_t - 0.018),
            bevel=0.002,
            material=mats["anodized_black"],
            collection=col,
        )
        parts.append(rail)

    # Dual motorized telescopic T-legs (inward at ±0.76m -> 36cm clean architectural overhang for zero-clip PC tower!)
    for side, sx in (("L", -0.76), ("R", 0.76)):
        # Upper wider column
        parts.append(create_beveled_box(
            f"Desk_LegUpper_{side}",
            (0.076, 0.095, 0.42),
            location=(sx, 0.02, 0.50),
            bevel=0.004,
            material=mats["anodized_black"],
            collection=col,
        ))
        # Lower narrower column
        parts.append(create_beveled_box(
            f"Desk_LegLower_{side}",
            (0.064, 0.082, 0.34),
            location=(sx, 0.02, 0.21),
            bevel=0.003,
            material=mats["gunmetal"],
            collection=col,
        ))
        # Top mounting bracket
        parts.append(create_beveled_box(
            f"Desk_Bracket_{side}",
            (0.09, 0.56, 0.012),
            location=(sx, 0.0, desk_h - top_t - 0.006),
            bevel=0.002,
            material=mats["anodized_black"],
            collection=col,
        ))
        # Sleek tapered T-foot bar
        parts.append(create_beveled_box(
            f"Desk_Foot_{side}",
            (0.075, 0.68, 0.024),
            location=(sx, 0.0, 0.022),
            bevel=0.005,
            segments=3,
            material=mats["anodized_black"],
            collection=col,
        ))
        # Leveling glides
        for gy in (-0.28, 0.28):
            parts.append(create_beveled_cylinder(
                f"Desk_Glide_{side}_{gy:+.2f}",
                radius=0.022,
                depth=0.010,
                vertices=24,
                location=(sx, gy, 0.005),
                material=mats["matte_plastic"],
                collection=col,
            ))

    # Rear under-desk steel cable management tray
    parts.append(create_beveled_box(
        "Desk_CableTray",
        (1.32, 0.14, 0.075),
        location=(0.0, 0.29, desk_h - top_t - 0.075),
        bevel=0.003,
        material=mats["anodized_black"],
        collection=col,
    ))

    # Digital height-controller paddle mounted right-front underside
    parts.append(create_beveled_box(
        "Desk_HeightController",
        (0.11, 0.055, 0.022),
        location=(0.56, -desk_d * 0.5 + 0.025, desk_h - top_t - 0.012),
        bevel=0.004,
        material=mats["matte_plastic"],
        collection=col,
    ))

    # Rear indirect RGB LED diffuser strip under back edge (Interactable in Three.js)
    led_strip = create_beveled_box(
        "Interact_DeskRGBStrip",
        (2.04, 0.014, 0.012),
        location=(0.0, desk_d * 0.5 - 0.015, desk_h - top_t - 0.008),
        bevel=0.002,
        material=mats["emissive_rgb_cyan"],
        collection=col,
    )
    parts.append(led_strip)

    # Dark stitched wool desk mat
    parts.append(create_beveled_box(
        "Desk_WoolMat",
        (0.96, 0.43, 0.0045),
        location=(-0.04, -0.15, desk_h + 0.0022),
        bevel=0.002,
        segments=2,
        material=mats["desk_mat"],
        uv_scale=2.0,
        collection=col,
    ))

    _parent_all(parts, root)
    return root



def build_monitors_and_arms(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """38-inch curved OLED ultrawide + 27-inch portrait monitor on dual gas-spring aluminum arms."""
    dx, dy, _ = desk_origin
    desk_h = 0.750
    root = _new_group("Hero_MonitorRig", (dx, dy, desk_h), col)
    parts: list[bpy.types.Object] = []

    # 1. Center 38" Curved Ultrawide (89cm x 38.5cm, R = 1.8m)
    uw_body, uw_scr = create_curved_panel(
        "Monitor_Ultrawide38",
        width=0.89,
        height=0.385,
        thickness=0.016,
        curve_radius=1.80,
        segments_x=40,
        bevel=0.0025,
        material=mats["anodized_black"],
        screen_material=mats["screen_ultrawide"],
        collection=col,
    )
    uw_body.location = (-0.04, 0.24, 0.345)
    # Slight ergonomic 4° upward tilt
    uw_body.rotation_euler = (math.radians(3.5), 0.0, 0.0)
    parts.append(uw_body)

    # Rear VESA housing & articulated gas-spring arm (clamped to back of desk at Y = +0.41)
    parts.append(create_beveled_box(
        "ArmUW_Clamp", (0.095, 0.085, 0.055), location=(-0.04, 0.395, 0.025),
        bevel=0.004, material=mats["anodized_black"], collection=col,
    ))
    parts.append(create_beveled_cylinder(
        "ArmUW_Pole", radius=0.022, depth=0.35, location=(-0.04, 0.395, 0.195),
        bevel=0.002, material=mats["gunmetal"], collection=col,
    ))
    parts.append(create_curve_tube(
        "ArmUW_Link",
        [(-0.04, 0.395, 0.26), (-0.11, 0.36, 0.31), (-0.04, 0.27, 0.345)],
        radius=0.018, material=mats["anodized_black"], col=col,
    ))
    parts.append(create_beveled_box(
        "ArmUW_VesaPlate", (0.115, 0.018, 0.115), location=(-0.04, 0.262, 0.345),
        bevel=0.003, material=mats["gunmetal"], collection=col,
    ))

    # 2. Left 27" Vertical Coding/Telemetry Monitor (34.5cm x 60.5cm, angled 22° inward)
    vert_anchor = _new_group("Monitor_Vertical27_Anchor", (-0.70, 0.20, 0.365), col, rot_z_deg=-22.0)
    vert_body = create_beveled_box(
        "Monitor_Vertical27_Body",
        (0.350, 0.016, 0.610),
        location=(0.0, 0.0, 0.0),
        bevel=0.0025,
        segments=2,
        material=mats["anodized_black"],
        collection=col,
    )
    vert_body.parent = vert_anchor

    # Flat portrait OLED screen with exact [0..1] UVs facing -Y
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    sw, sh = 0.338, 0.592
    v0 = bm.verts.new((-sw * 0.5, -0.0092, -sh * 0.5 + 0.003))
    v1 = bm.verts.new((sw * 0.5, -0.0092, -sh * 0.5 + 0.003))
    v2 = bm.verts.new((sw * 0.5, -0.0092, sh * 0.5 + 0.003))
    v3 = bm.verts.new((-sw * 0.5, -0.0092, sh * 0.5 + 0.003))
    f = bm.faces.new((v0, v1, v2, v3))
    f.loops[0][uv].uv = (0.0, 0.0)
    f.loops[1][uv].uv = (1.0, 0.0)
    f.loops[2][uv].uv = (1.0, 1.0)
    f.loops[3][uv].uv = (0.0, 1.0)
    vscr_mesh = bpy.data.meshes.new("Monitor_Vertical27_Screen")
    bm.to_mesh(vscr_mesh)
    bm.free()
    vscr_obj = bpy.data.objects.new("Monitor_Vertical27_Screen", vscr_mesh)
    vscr_obj.data.materials.append(mats["screen_vertical"])
    col.objects.link(vscr_obj)
    vscr_obj.parent = vert_anchor
    parts.append(vert_anchor)

    # Vertical monitor arm
    parts.append(create_beveled_box(
        "ArmVert_Clamp", (0.085, 0.080, 0.050), location=(-0.56, 0.395, 0.022),
        bevel=0.004, material=mats["anodized_black"], collection=col,
    ))
    parts.append(create_curve_tube(
        "ArmVert_Link",
        [(-0.56, 0.395, 0.06), (-0.64, 0.38, 0.24), (-0.70, 0.22, 0.365)],
        radius=0.015, material=mats["anodized_black"], col=col,
    ))

    _parent_all(parts, root)
    return root



def build_studio_speakers(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Pair of reference studio nearfield monitors on tilted acoustic isolation stands."""
    dx, dy, _ = desk_origin
    root = _new_group("Hero_StudioSpeakers", (dx, dy, 0.750), col)
    parts: list[bpy.types.Object] = []

    configs = [("L", -0.99, 0.19, -20.0), ("R", 0.52, 0.19, 20.0)]
    for side, sx, sy, rot_z in configs:
        sp = _new_group(f"Speaker_{side}", (sx, sy, 0.0), col, rot_z_deg=rot_z)
        sub: list[bpy.types.Object] = []

        # Isolation desk stand (angled 10° upward toward listener ears)
        sub.append(create_beveled_box(
            f"Spk_{side}_Base", (0.142, 0.165, 0.010), location=(0.0, 0.0, 0.005),
            bevel=0.002, material=mats["anodized_black"], collection=col,
        ))
        for px in (-0.055, 0.055):
            sub.append(create_beveled_cylinder(
                f"Spk_{side}_Pillar_{px:+.2f}", radius=0.009, depth=0.075,
                location=(px, 0.01, 0.044), material=mats["gunmetal"], collection=col,
            ))

        # Tilted speaker cabinet
        cab_anchor = _new_group(f"Spk_{side}_CabTilt", (0.0, 0.0, 0.082), col)
        cab_anchor.rotation_euler = (math.radians(9.0), 0.0, 0.0)
        cab_parts: list[bpy.types.Object] = []

        cab_parts.append(create_beveled_box(
            f"Spk_{side}_Cabinet", (0.148, 0.185, 0.238), location=(0.0, 0.0, 0.119),
            bevel=0.012, segments=4, material=mats["matte_plastic"], collection=col,
        ))
        # Brushed aluminum front baffle inset
        cab_parts.append(create_beveled_box(
            f"Spk_{side}_Baffle", (0.132, 0.008, 0.220), location=(0.0, -0.091, 0.119),
            bevel=0.004, material=mats["anodized_black"], collection=col,
        ))
        # Hollow brushed-brass woofer trim ring (torus-style via lathe) + concave black carbon woofer cone
        bm_w = bmesh.new()
        w_profile = [
            (0.052, -0.002), (0.052, 0.004), (0.047, 0.005), (0.045, 0.001),
            (0.045, -0.002),
        ]
        w_verts = [bm_w.verts.new((r, 0.0, z)) for r, z in w_profile]
        w_edges = [bm_w.edges.new((w_verts[i], w_verts[i + 1])) for i in range(len(w_verts) - 1)]
        bmesh.ops.spin(bm_w, geom=w_verts + w_edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=44, use_merge=True)
        bmesh.ops.recalc_face_normals(bm_w, faces=bm_w.faces)
        ring_mesh = bpy.data.meshes.new(f"Spk_{side}_WooferTrim")
        bm_w.to_mesh(ring_mesh)
        bm_w.free()
        apply_box_uv(ring_mesh, scale=6.0)
        ring_obj = bpy.data.objects.new(f"Spk_{side}_WooferTrim", ring_mesh)
        ring_obj.location = (0.0, -0.095, 0.082)
        ring_obj.rotation_euler = (math.radians(90), 0.0, 0.0)
        ring_obj.data.materials.append(mats["brushed_brass"])
        set_smooth_with_bevel_normals(ring_obj)
        col.objects.link(ring_obj)
        cab_parts.append(ring_obj)

        # Concave recessed carbon woofer diaphragm
        bm_c = bmesh.new()
        c_profile = [(0.046, 0.002), (0.042, 0.004), (0.036, -0.001), (0.015, -0.013), (0.0, -0.013)]
        c_verts = [bm_c.verts.new((r, 0.0, z)) for r, z in c_profile]
        c_edges = [bm_c.edges.new((c_verts[i], c_verts[i + 1])) for i in range(len(c_verts) - 1)]
        bmesh.ops.spin(bm_c, geom=c_verts + c_edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=44, use_merge=True)
        bmesh.ops.recalc_face_normals(bm_c, faces=bm_c.faces)
        cone_mesh = bpy.data.meshes.new(f"Spk_{side}_WooferCone")
        bm_c.to_mesh(cone_mesh)
        bm_c.free()
        apply_box_uv(cone_mesh, scale=6.0)
        cone_obj = bpy.data.objects.new(f"Spk_{side}_WooferCone", cone_mesh)
        cone_obj.location = (0.0, -0.094, 0.082)
        cone_obj.rotation_euler = (math.radians(90), 0.0, 0.0)
        cone_obj.data.materials.append(mats["speaker_cone"])
        set_smooth_with_bevel_normals(cone_obj)
        col.objects.link(cone_obj)
        cab_parts.append(cone_obj)

        # Subtle metallic phase plug dome inside cone center
        cab_parts.append(create_beveled_cylinder(
            f"Spk_{side}_PhasePlug", radius=0.011, depth=0.012, vertices=28,
            location=(0.0, -0.089, 0.082), rotation=(math.radians(90), 0.0, 0.0),
            bevel=0.004, material=mats["brushed_brass"], collection=col,
        ))
        # Tweeter waveguide
        cab_parts.append(create_beveled_cylinder(
            f"Spk_{side}_TweeterRing", radius=0.025, depth=0.007, vertices=36,
            location=(0.0, -0.094, 0.175), rotation=(math.radians(90), 0.0, 0.0),
            bevel=0.002, material=mats["gunmetal"], collection=col,
        ))
        cab_parts.append(create_beveled_cylinder(
            f"Spk_{side}_TweeterDome", radius=0.014, depth=0.009, vertices=32,
            location=(0.0, -0.095, 0.175), rotation=(math.radians(90), 0.0, 0.0),
            bevel=0.004, material=mats["anodized_black"], collection=col,
        ))

        _parent_all(cab_parts, cab_anchor)
        sub.append(cab_anchor)
        _parent_all(sub, sp)
        parts.append(sp)

    _parent_all(parts, root)
    return root



def build_custom_keyboard_and_mouse(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """75% CNC anodized aluminum custom mechanical keyboard with 78 sculpted keycaps + coiled cable + ergonomic wireless mouse."""
    dx, dy, _ = desk_origin
    root = _new_group("Hero_KeyboardMouse", (dx, dy, 0.7545), col)
    parts: list[bpy.types.Object] = []

    # 1. Keyboard Anchor (6° ergonomic typing incline)
    kb = _new_group("Custom_Keyboard75", (-0.07, -0.15, 0.0), col)
    kb_tilted = _new_group("KB_TiltedFrame", (0.0, 0.0, 0.013), col)
    kb_tilted.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
    kb_tilted.parent = kb

    # CNC Aluminum case
    case = create_beveled_box(
        "KB_AluminumCase", (0.332, 0.144, 0.022), location=(0.0, 0.0, 0.0),
        bevel=0.0035, segments=3, material=mats["gunmetal"], collection=col,
    )
    case.parent = kb_tilted

    # Recessed dark plate inside case
    plate = create_beveled_box(
        "KB_SwitchPlate", (0.314, 0.126, 0.004), location=(0.0, 0.0, 0.010),
        bevel=0.001, material=mats["anodized_black"], collection=col,
    )
    plate.parent = kb_tilted

    # Subtle ambient per-key underglow diffuser strip
    glow = create_beveled_box(
        "KB_Underglow", (0.308, 0.120, 0.002), location=(0.0, 0.0, 0.0118),
        bevel=0.0, material=mats["emissive_rgb_amber"], collection=col,
    )
    glow.parent = kb_tilted

    # Brass knurled rotary volume knob top-right
    knob = create_beveled_cylinder(
        "KB_RotaryKnob", radius=0.0095, depth=0.016, vertices=28,
        location=(0.143, 0.048, 0.018), bevel=0.0018, material=mats["brushed_brass"], collection=col,
    )
    knob.parent = kb_tilted

    # Build ALL keycaps into 3 clean batched meshes (charcoal, slate, terracotta accent) for crisp geometry & low draw calls!
    pitch = 0.01905  # Exact standard 19.05mm MX switch pitch!
    rows_layout = [
        # (y_offset, [(u_width, style), ...])
        (0.048, [(1.0, "accent")] + [(1.0, "dark")] * 12 + [(1.0, "mod")]),  # F-row (knob sits at col 15)
        (0.026, [(1.0, "mod")] + [(1.0, "dark")] * 12 + [(2.0, "mod")] + [(1.0, "mod")]),  # Number row
        (0.007, [(1.5, "mod")] + [(1.0, "dark")] * 12 + [(1.5, "mod")] + [(1.0, "mod")]),  # QWERTY
        (-0.012, [(1.75, "mod")] + [(1.0, "dark")] * 11 + [(2.25, "accent")] + [(1.0, "mod")]),  # ASDF + Enter
        (-0.031, [(2.25, "mod")] + [(1.0, "dark")] * 10 + [(1.75, "mod")] + [(1.0, "mod")] + [(1.0, "mod")]),  # Shift
        (-0.050, [(1.25, "mod"), (1.25, "mod"), (1.25, "mod"), (6.25, "dark"), (1.0, "mod"), (1.0, "mod"), (1.0, "mod"), (1.0, "mod"), (1.0, "mod")]),
    ]
    bms = {"dark": bmesh.new(), "mod": bmesh.new(), "accent": bmesh.new()}
    start_x = -0.148
    for row_y, keys in rows_layout:
        cursor_u = 0.0
        for u_w, style in keys:
            kw = u_w * pitch - 0.0026
            kd = pitch - 0.0028
            kh = 0.0092
            cx = start_x + (cursor_u + u_w * 0.5) * pitch
            cursor_u += u_w

            # Tapered spherical/cherry sculpted keycap
            bm_k = bmesh.new()
            top_scale = 0.78
            hw, hd = kw * 0.5, kd * 0.5
            tw, td = hw * top_scale, hd * top_scale
            z0, z1 = 0.012, 0.012 + kh
            vb = [
                bm_k.verts.new((cx - hw, row_y - hd, z0)),
                bm_k.verts.new((cx + hw, row_y - hd, z0)),
                bm_k.verts.new((cx + hw, row_y + hd, z0)),
                bm_k.verts.new((cx - hw, row_y + hd, z0)),
            ]
            vt = [
                bm_k.verts.new((cx - tw, row_y - td, z1)),
                bm_k.verts.new((cx + tw, row_y - td, z1)),
                bm_k.verts.new((cx + tw, row_y + td, z1)),
                bm_k.verts.new((cx - tw, row_y + td, z1)),
            ]
            bm_k.faces.new((vb[0], vb[1], vt[1], vt[0]))
            bm_k.faces.new((vb[1], vb[2], vt[2], vt[1]))
            bm_k.faces.new((vb[2], vb[3], vt[3], vt[2]))
            bm_k.faces.new((vb[3], vb[0], vt[0], vt[3]))
            bm_k.faces.new((vt[0], vt[1], vt[2], vt[3]))
            bmesh.ops.bevel(bm_k, geom=list(bm_k.edges), offset=0.0012, segments=2, affect="EDGES", clamp_overlap=True)

            # Merge into material batch
            target_bm = bms[style]
            v_map = {v: target_bm.verts.new(v.co) for v in bm_k.verts}
            for f in bm_k.faces:
                try:
                    target_bm.faces.new([v_map[v] for v in f.verts])
                except ValueError:
                    pass
            bm_k.free()

    style_to_mat = {"dark": mats["keycap_dark"], "mod": mats["keycap_mod"], "accent": mats["keycap_accent"]}
    for style, bm_group in bms.items():
        bmesh.ops.recalc_face_normals(bm_group, faces=bm_group.faces)
        mesh = bpy.data.meshes.new(f"KB_Keycaps_{style}")
        bm_group.to_mesh(mesh)
        bm_group.free()
        apply_box_uv(mesh, scale=6.0)
        k_obj = bpy.data.objects.new(f"KB_Keycaps_{style}", mesh)
        k_obj.data.materials.append(style_to_mat[style])
        set_smooth_with_bevel_normals(k_obj)
        col.objects.link(k_obj)
        k_obj.parent = kb_tilted

    # Coiled Aviator USB-C Cable running cleanly from rear of keyboard to desk grommet
    coil_pts = [(-0.07, -0.075, 0.012), (-0.07, -0.03, 0.008)]
    for i in range(44):
        t = i / 43.0
        ang = t * 11.0 * 2.0 * math.pi
        x = -0.06 + t * 0.14
        y = -0.025 + 0.009 * math.cos(ang)
        z = 0.011 + 0.009 * math.sin(ang)
        coil_pts.append((x, y, z))
    coil_pts += [(0.11, -0.025, 0.008), (0.14, 0.08, 0.006), (-0.02, 0.31, 0.005)]
    parts.append(create_curve_tube("KB_CoiledCable", coil_pts, radius=0.0026, material=mats["matte_plastic"], col=col, bevel_res=6))
    # Metallic GX16 aviator connector cylinder
    parts.append(create_beveled_cylinder(
        "KB_AviatorConnector", radius=0.007, depth=0.048, vertices=24,
        location=(0.105, -0.025, 0.008), rotation=(0.0, math.radians(90), 0.0),
        bevel=0.0015, material=mats["chrome"], collection=col,
    ))
    parts.append(kb)

    # 2. Sculpted Ergonomic Wireless Mouse (Subdivision Surface shell)
    mouse_anchor = _new_group("Hero_WirelessMouse", (0.24, -0.15, 0.0), col, rot_z_deg=-8.0)
    bm_m = bmesh.new()
    bmesh.ops.create_cube(bm_m, size=1.0)
    bmesh.ops.subdivide_edges(bm_m, edges=list(bm_m.edges), cuts=2, use_grid_fill=True)
    for v in bm_m.verts:
        nx, ny, nz = v.co.x * 2.0, v.co.y * 2.0, v.co.z * 2.0  # [-1..1]
        # Organic teardrop profile: slightly wider at palm (-Y), tapered nose (+Y), domed top
        width_scale = 0.034 * (1.0 - 0.14 * max(0.0, ny))
        length_scale = 0.062
        if nz < 0:
            z_pos = 0.002
        else:
            arch = max(0.0, 1.0 - 0.55 * (nx * nx) - 0.42 * ((ny + 0.12) ** 2))
            z_pos = 0.010 + 0.031 * arch * (0.5 + 0.5 * nz)
        v.co = Vector((nx * width_scale, ny * length_scale, z_pos))
    m_mesh = bpy.data.meshes.new("Mouse_Shell")
    bm_m.to_mesh(m_mesh)
    bm_m.free()
    apply_box_uv(m_mesh, scale=8.0)
    m_obj = bpy.data.objects.new("Mouse_Shell", m_mesh)
    m_obj.data.materials.append(mats["matte_plastic"])
    subsurf = m_obj.modifiers.new("Subsurf", "SUBSURF")
    subsurf.levels = 2
    subsurf.render_levels = 2
    m_obj.data.polygons.foreach_set("use_smooth", [True] * len(m_obj.data.polygons))
    col.objects.link(m_obj)
    m_obj.parent = mouse_anchor

    wheel = create_beveled_cylinder(
        "Mouse_ScrollWheel", radius=0.0075, depth=0.006, vertices=24,
        location=(0.0, 0.031, 0.029), rotation=(0.0, math.radians(90), 0.0),
        bevel=0.001, material=mats["chrome"], collection=col,
    )
    wheel.parent = mouse_anchor
    parts.append(mouse_anchor)

    _parent_all(parts, root)
    return root



def build_broadcast_mic_and_camera(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """SM7B broadcast dynamic mic on low-profile boom arm + Sony FX3/A7S mirrorless streaming camera + Dual Key Lights."""
    dx, dy, _ = desk_origin
    root = _new_group("Hero_StreamingGear", (dx, dy, 0.750), col)
    parts: list[bpy.types.Object] = []

    # 1. Low-Profile Boom Arm + Shure SM7B Dynamic Microphone
    parts.append(create_beveled_box(
        "Mic_DeskClamp", (0.068, 0.072, 0.052), location=(-0.56, 0.38, 0.022),
        bevel=0.004, material=mats["anodized_black"], collection=col,
    ))
    parts.append(create_curve_tube(
        "Mic_BoomArm",
        [(-0.56, 0.38, 0.065), (-0.58, 0.14, 0.085), (-0.42, -0.10, 0.14), (-0.34, -0.22, 0.215)],
        radius=0.012, material=mats["anodized_black"], col=col,
    ))
    # Microphone head anchor angled cleanly toward the streamer at (0, -0.65, 0.45)
    mic = _new_group("Mic_SM7B", (-0.34, -0.22, 0.225), col, rot_z_deg=28.0)
    mic.rotation_euler.x = math.radians(16.0)
    mic_parts: list[bpy.types.Object] = []
    # U-yoke mount
    mic_parts.append(create_beveled_box(
        "Mic_YokeBase", (0.082, 0.016, 0.014), location=(0.0, 0.03, -0.012),
        bevel=0.002, material=mats["gunmetal"], collection=col,
    ))
    for ux in (-0.036, 0.036):
        mic_parts.append(create_beveled_box(
            f"Mic_YokeArm_{ux:+.2f}", (0.010, 0.018, 0.068), location=(ux, 0.03, 0.024),
            bevel=0.002, material=mats["gunmetal"], collection=col,
        ))
    # Rear XLR housing body
    mic_parts.append(create_beveled_cylinder(
        "Mic_MetalBody", radius=0.029, depth=0.105, vertices=36,
        location=(0.0, 0.035, 0.045), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.004, material=mats["anodized_black"], collection=col,
    ))
    # Front porous acoustic foam windscreen
    mic_parts.append(create_beveled_cylinder(
        "Mic_FoamWindscreen", radius=0.032, depth=0.095, vertices=36,
        location=(0.0, -0.055, 0.045), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.014, segments=4, material=mats["mic_foam"], collection=col,
    ))
    _parent_all(mic_parts, mic)
    parts.append(mic)

    # 2. Sleek Mirrorless Streaming Camera (Sony FX3/A7S style) mounted above center monitor
    parts.append(create_beveled_cylinder(
        "Cam_RiserPole", radius=0.011, depth=0.61,
        location=(-0.04, 0.35, 0.305), bevel=0.002, material=mats["anodized_black"], collection=col,
    ))
    cam = _new_group("Hero_StreamCamera", (-0.04, 0.32, 0.625), col)
    cam.rotation_euler = (math.radians(-6.0), 0.0, 0.0)
    cam_parts: list[bpy.types.Object] = []
    # Main sculpted magnesium camera body
    cam_parts.append(create_beveled_box(
        "Cam_Body", (0.128, 0.062, 0.078), location=(0.0, 0.0, 0.0),
        bevel=0.008, segments=3, material=mats["gunmetal"], collection=col,
    ))
    # Right-hand ergonomic grip bulge
    cam_parts.append(create_beveled_cylinder(
        "Cam_Grip", radius=0.024, depth=0.076, vertices=28,
        location=(-0.054, -0.014, 0.0), bevel=0.006, material=mats["leather_dark"], collection=col,
    ))
    # Top EVF/Hotshoe & glowing REC tally lamp
    cam_parts.append(create_beveled_box(
        "Cam_Hotshoe", (0.044, 0.040, 0.014), location=(0.0, 0.0, 0.044),
        bevel=0.003, material=mats["anodized_black"], collection=col,
    ))
    cam_parts.append(create_beveled_box(
        "Cam_TallyLED", (0.014, 0.004, 0.005), location=(0.036, -0.031, 0.028),
        bevel=0.001, material=mats["emissive_tally_red"], collection=col,
    ))
    # Precision multi-ring 24mm f/1.4 Prime Lens facing -Y
    cam_parts.append(create_beveled_cylinder(
        "Cam_LensBarrel1", radius=0.034, depth=0.046, vertices=44,
        location=(0.008, -0.048, -0.002), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.002, material=mats["anodized_black"], collection=col,
    ))
    cam_parts.append(create_beveled_cylinder(
        "Cam_LensFocusRing", radius=0.036, depth=0.028, vertices=44,
        location=(0.008, -0.072, -0.002), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.002, material=mats["matte_plastic"], collection=col,
    ))
    cam_parts.append(create_beveled_cylinder(
        "Cam_LensRedRing", radius=0.0355, depth=0.0035, vertices=44,
        location=(0.008, -0.088, -0.002), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.0008, material=mats["red_accent"], collection=col,
    ))
    cam_parts.append(create_beveled_cylinder(
        "Cam_LensGlass", radius=0.028, depth=0.006, vertices=36,
        location=(0.008, -0.089, -0.002), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.002, material=mats["lens_glass"], collection=col,
    ))
    _parent_all(cam_parts, cam)
    parts.append(cam)

    # 3. Dual Edge-Lit Studio Key Lights (Sleek balanced height & slim rim framing the desk)
    for side, kx, rot_z in (("L", -0.84, -22.0), ("R", 0.44, 22.0)):
        parts.append(create_beveled_cylinder(
            f"KeyLight_{side}_Pole", radius=0.009, depth=0.72,
            location=(kx, 0.37, 0.36), bevel=0.001, material=mats["anodized_black"], collection=col,
        ))
        kl = _new_group(f"Interact_KeyLight_{side}", (kx, 0.34, 0.74), col, rot_z_deg=rot_z)
        kl.rotation_euler.x = math.radians(-24.0)
        kl_housing = create_beveled_box(
            f"KeyLight_{side}_Housing", (0.260, 0.020, 0.175), location=(0.0, 0.0, 0.0),
            bevel=0.007, segments=3, material=mats["anodized_black"], collection=col,
        )
        kl_diffuser = create_beveled_box(
            f"KeyLight_{side}_Diffuser", (0.242, 0.005, 0.158), location=(0.0, -0.009, 0.0),
            bevel=0.002, material=mats["emissive_keylight"], collection=col,
        )
        kl_housing.parent = kl
        kl_diffuser.parent = kl
        parts.append(kl)

    _parent_all(parts, root)
    return root



def build_flagship_pc_tower(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Panoramic tempered-glass flagship PC tower with internal RTX GPU, AIO liquid cooler, and rotatable fans."""
    dx, dy, _ = desk_origin
    root = _new_group("Hero_PCTower", (dx + 0.89, dy + 0.08, 0.750), col, rot_z_deg=12.0)
    parts: list[bpy.types.Object] = []

    w, d, h = 0.245, 0.460, 0.465
    # Aluminum feet
    for fx in (-0.09, 0.09):
        for fy in (-0.18, 0.18):
            parts.append(create_beveled_cylinder(
                f"PC_Foot_{fx:+.2f}_{fy:+.2f}", radius=0.018, depth=0.016, vertices=24,
                location=(fx, fy, 0.008), bevel=0.003, material=mats["gunmetal"], collection=col,
            ))

    # Chassis structural frame: bottom shroud, top radiator cover, right solid backplate, rear IO wall
    parts.append(create_beveled_box("PC_Bottom", (w, d, 0.032), (0.0, 0.0, 0.032), bevel=0.004, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_Top", (w, d, 0.028), (0.0, 0.0, h - 0.014), bevel=0.004, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_RightPanel", (0.016, d, h - 0.03), (w * 0.5 - 0.008, 0.0, h * 0.5 + 0.008), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_RearPanel", (w, 0.016, h - 0.03), (0.0, d * 0.5 - 0.008, h * 0.5 + 0.008), bevel=0.003, material=mats["anodized_black"], collection=col))
    # Walnut vertical front accent slats (Fractal North aesthetic on right third of front face)
    for i in range(4):
        sx = 0.035 + i * 0.024
        parts.append(create_beveled_box(
            f"PC_FrontSlat_{i}", (0.014, 0.014, h - 0.065), (sx, -d * 0.5 + 0.007, h * 0.5 + 0.008),
            bevel=0.002, material=mats["walnut_slat"], collection=col,
        ))

    # Panoramic dark-tinted tempered glass (Left side + Left-front viewing pane)
    parts.append(create_beveled_box(
        "PC_GlassSide", (0.005, d - 0.018, h - 0.064), (-w * 0.5 + 0.004, 0.0, h * 0.5 + 0.008),
        bevel=0.001, material=mats["pc_glass"], collection=col,
    ))
    parts.append(create_beveled_box(
        "PC_GlassFront", (w * 0.55, 0.005, h - 0.064), (-w * 0.22, -d * 0.5 + 0.004, h * 0.5 + 0.008),
        bevel=0.001, material=mats["pc_glass"], collection=col,
    ))

    # Internal Motherboard tray & ATX Motherboard
    parts.append(create_beveled_box(
        "PC_Motherboard", (0.012, 0.305, 0.285), (0.072, 0.03, 0.26),
        bevel=0.002, material=mats["matte_plastic"], collection=col,
    ))
    # VRM aluminum heatsinks & 2 glowing DDR5 RAM sticks
    parts.append(create_beveled_box("PC_VRMHeatSink", (0.028, 0.055, 0.115), (0.055, 0.11, 0.32), bevel=0.003, material=mats["gunmetal"], collection=col))
    for idx, ry in enumerate((-0.052, -0.068)):
        parts.append(create_beveled_box(f"PC_RAM_{idx}", (0.038, 0.007, 0.132), (0.048, ry, 0.295), bevel=0.0015, material=mats["gunmetal"], collection=col))
        parts.append(create_beveled_box(f"PC_RAM_LED_{idx}", (0.004, 0.005, 0.126), (0.028, ry, 0.295), bevel=0.001, material=mats["emissive_rgb_cyan"], collection=col))

    # AIO CPU Cooler Pump Block (glowing infinity ring) + Dual Curved Braided Coolant Tubes
    parts.append(create_beveled_cylinder(
        "PC_AIOPump", radius=0.038, depth=0.048, vertices=36,
        location=(0.042, 0.025, 0.305), rotation=(0.0, math.radians(90), 0.0),
        bevel=0.005, material=mats["anodized_black"], collection=col,
    ))
    parts.append(create_beveled_cylinder(
        "PC_AIORingLED", radius=0.028, depth=0.004, vertices=36,
        location=(0.017, 0.025, 0.305), rotation=(0.0, math.radians(90), 0.0),
        bevel=0.001, material=mats["emissive_rgb_cyan"], collection=col,
    ))
    parts.append(create_curve_tube(
        "PC_AIOTube1", [(0.03, 0.00, 0.325), (-0.03, -0.08, 0.36), (-0.01, -0.14, 0.415)],
        radius=0.0065, material=mats["matte_plastic"], col=col,
    ))
    parts.append(create_curve_tube(
        "PC_AIOTube2", [(0.03, -0.01, 0.295), (-0.04, -0.10, 0.34), (-0.02, -0.15, 0.415)],
        radius=0.0065, material=mats["matte_plastic"], col=col,
    ))

    # Flagship RTX Triple-Slot GPU with brushed gunmetal shroud & glowing accent bar
    parts.append(create_beveled_box(
        "PC_RTX_GPU", (0.128, 0.325, 0.062), (0.005, -0.01, 0.175),
        bevel=0.005, segments=3, material=mats["gunmetal"], collection=col,
    ))
    parts.append(create_beveled_box(
        "PC_GPU_AccentBar", (0.006, 0.145, 0.008), (-0.060, -0.02, 0.188),
        bevel=0.001, material=mats["emissive_rgb_amber"], collection=col,
    ))

    # Internal subtle top white-cyan showcase LED bar so RTX GPU & AIO shine cleanly through tinted glass!
    parts.append(create_beveled_box(
        "PC_InternalLED", (0.012, d - 0.09, 0.008), (-w * 0.34, 0.0, h - 0.036),
        bevel=0.001, material=mats["emissive_pc_internal"], collection=col,
    ))

    # 3 Bottom + 1 Rear Illuminated Fans (with distinct Spin_PCFan_* hubs for 60 FPS animation in Three.js!)
    fan_positions = [
        ("Bot1", (0.0, -0.13, 0.056), (0.0, 0.0, 0.0)),
        ("Bot2", (0.0, 0.00, 0.056), (0.0, 0.0, 0.0)),
        ("Bot3", (0.0, 0.13, 0.056), (0.0, 0.0, 0.0)),
    ]
    for fname, floc, frot in fan_positions:
        # Frame + glowing halo ring
        parts.append(create_beveled_box(f"PC_FanFrame_{fname}", (0.118, 0.118, 0.022), floc, bevel=0.004, material=mats["matte_plastic"], collection=col))
        parts.append(create_beveled_box(
            f"PC_FanHalo_{fname}", (0.112, 0.112, 0.004), (floc[0], floc[1], floc[2] + 0.012),
            bevel=0.001, material=mats["emissive_pc_fan"], collection=col,
        ))
        # Rotor hub + 7 blades grouped cleanly so Three.js can spin it
        hub = create_beveled_cylinder(
            f"Spin_PCFan_{fname}", radius=0.020, depth=0.018, vertices=20,
            location=floc, rotation=frot, bevel=0.002, material=mats["emissive_pc_fan"], collection=col,
        )
        for b in range(7):
            ang = b * (2.0 * math.pi / 7.0)
            blade = create_beveled_box(
                f"PC_Blade_{fname}_{b}", (0.040, 0.015, 0.003),
                location=(math.cos(ang) * 0.032, math.sin(ang) * 0.032, 0.0),
                rotation=(math.radians(28), 0.0, ang),
                bevel=0.0008, material=mats["anodized_black"], collection=col,
            )
            blade.parent = hub
        parts.append(hub)

    _parent_all(parts, root)
    return root



def build_ergonomic_task_chair(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Herman Miller / Steelcase inspired modern ergonomic task chair.
    Sculpted contoured seat & curved lumbar backrest via Subdivision Surface + cast-aluminum 5-star base.
    """
    root = _new_group("Hero_ErgonomicChair", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []

    # 1. 5-Star Cast Aluminum Base + Twin Casters
    parts.append(create_beveled_cylinder(
        "Chair_CenterHub", radius=0.042, depth=0.075, vertices=32,
        location=(0.0, 0.0, 0.105), bevel=0.006, material=mats["gunmetal"], collection=col,
    ))
    for i in range(5):
        ang = i * (2.0 * math.pi / 5.0) + math.radians(18)
        ca, sa = math.cos(ang), math.sin(ang)
        leg_pts = [(ca * 0.032, sa * 0.032, 0.115), (ca * 0.17, sa * 0.17, 0.095), (ca * 0.315, sa * 0.315, 0.068)]
        parts.append(create_curve_tube(f"Chair_StarLeg_{i}", leg_pts, radius=0.015, material=mats["gunmetal"], col=col))
        # Twin caster wheels touching Z = 0
        parts.append(create_beveled_cylinder(
            f"Chair_CasterStem_{i}", radius=0.009, depth=0.032, vertices=16,
            location=(ca * 0.315, sa * 0.315, 0.048), material=mats["anodized_black"], collection=col,
        ))
        parts.append(create_beveled_cylinder(
            f"Chair_Wheel_{i}", radius=0.028, depth=0.038, vertices=28,
            location=(ca * 0.315, sa * 0.315, 0.028),
            rotation=(0.0, math.radians(90), ang),
            bevel=0.004, material=mats["matte_plastic"], collection=col,
        ))

    # 2. Gas Cylinder + Sculpted Tilt Mechanism Box
    parts.append(create_beveled_cylinder(
        "Chair_GasCylinder", radius=0.024, depth=0.28, vertices=32,
        location=(0.0, 0.0, 0.255), bevel=0.003, material=mats["anodized_black"], collection=col,
    ))
    parts.append(create_beveled_box(
        "Chair_TiltMechanism", (0.18, 0.26, 0.085), location=(0.0, 0.01, 0.405),
        bevel=0.014, segments=3, material=mats["anodized_black"], collection=col,
    ))

    # 3. Contoured Ergonomic Waterfall Seat Cushion (Subdivision Surface)
    bm_s = bmesh.new()
    bmesh.ops.create_cube(bm_s, size=1.0)
    bmesh.ops.subdivide_edges(bm_s, edges=list(bm_s.edges), cuts=3, use_grid_fill=True)
    for v in bm_s.verts:
        nx, ny, nz = v.co.x * 2.0, v.co.y * 2.0, v.co.z * 2.0
        # Slight side bolster lift + waterfall front drop (+Y is front facing desk!)
        bolster = 0.018 * (nx * nx)
        waterfall = -0.028 * max(0.0, ny - 0.45) ** 2
        thick = 0.032 * (1.0 - 0.18 * (nx * nx + ny * ny) * 0.5)
        v.co = Vector((nx * 0.255, ny * 0.240, 0.470 + bolster + waterfall + nz * thick))
    seat_mesh = bpy.data.meshes.new("Chair_SeatCushion")
    bm_s.to_mesh(seat_mesh)
    bm_s.free()
    apply_box_uv(seat_mesh, scale=2.5)
    seat_obj = bpy.data.objects.new("Chair_SeatCushion", seat_mesh)
    seat_obj.data.materials.append(mats["leather_dark"])
    seat_obj.modifiers.new("Subsurf", "SUBSURF").levels = 2
    seat_obj.modifiers["Subsurf"].render_levels = 2
    seat_obj.data.polygons.foreach_set("use_smooth", [True] * len(seat_obj.data.polygons))
    col.objects.link(seat_obj)
    parts.append(seat_obj)

    # 4. Cast Aluminum Twin Spine + Sculpted S-Curve Backrest (Facing +Y, located at -Y)
    for side, sx in (("L", -0.055), ("R", 0.055)):
        spine_pts = [(sx, -0.08, 0.40), (sx * 1.1, -0.26, 0.44), (sx * 1.2, -0.29, 0.68), (sx * 0.9, -0.27, 0.92)]
        parts.append(create_curve_tube(f"Chair_Spine_{side}", spine_pts, radius=0.016, material=mats["gunmetal"], col=col))

    bm_b = bmesh.new()
    bmesh.ops.create_cube(bm_b, size=1.0)
    bmesh.ops.subdivide_edges(bm_b, edges=list(bm_b.edges), cuts=3, use_grid_fill=True)
    for v in bm_b.verts:
        nx, ny, nz = v.co.x * 2.0, v.co.y * 2.0, v.co.z * 2.0  # nz in [-1..1] height
        # Taper gently toward shoulders, curve horizontally around back, S-curve lumbar forward
        half_w = 0.235 - 0.030 * max(0.0, nz)
        curve_y = 0.048 * (nx * nx)  # wraps gently around user's back toward +Y
        lumbar_y = 0.032 * math.sin((nz + 0.35) * math.pi * 0.65)
        recline_y = -0.055 * (nz + 1.0) * 0.5
        v.co = Vector((nx * half_w, -0.235 + curve_y + lumbar_y + recline_y + ny * 0.017, 0.775 + nz * 0.255))
    back_mesh = bpy.data.meshes.new("Chair_Backrest")
    bm_b.to_mesh(back_mesh)
    bm_b.free()
    apply_box_uv(back_mesh, scale=2.5)
    back_obj = bpy.data.objects.new("Chair_Backrest", back_mesh)
    back_obj.data.materials.append(mats["chair_mesh"])
    back_obj.modifiers.new("Subsurf", "SUBSURF").levels = 2
    back_obj.modifiers["Subsurf"].render_levels = 2
    back_obj.data.polygons.foreach_set("use_smooth", [True] * len(back_obj.data.polygons))
    col.objects.link(back_obj)
    parts.append(back_obj)

    # Sculpted Cast-Aluminum Perimeter Backrest Exoskeleton Ring & Lumbar Bridge
    ring_pts = [
        (-0.21, -0.22, 0.54), (-0.24, -0.23, 0.78), (-0.20, -0.27, 1.01),
        (0.0, -0.29, 1.03),
        (0.20, -0.27, 1.01), (0.24, -0.23, 0.78), (0.21, -0.22, 0.54),
        (0.0, -0.22, 0.52), (-0.21, -0.22, 0.54),
    ]
    parts.append(create_curve_tube("Chair_BackFrameRing", ring_pts, radius=0.013, material=mats["anodized_black"], col=col))
    parts.append(create_beveled_box(
        "Chair_LumbarBridge", (0.34, 0.032, 0.068), location=(0.0, -0.265, 0.675),
        bevel=0.010, segments=3, material=mats["gunmetal"], collection=col,
    ))

    # Contoured Ergonomic Headrest
    parts.append(create_beveled_cylinder(
        "Chair_HeadrestStem", radius=0.012, depth=0.11, vertices=20,
        location=(0.0, -0.305, 1.055), rotation=(math.radians(14), 0.0, 0.0),
        material=mats["gunmetal"], collection=col,
    ))
    parts.append(create_beveled_box(
        "Chair_HeadrestPad", (0.245, 0.055, 0.105), location=(0.0, -0.285, 1.125),
        rotation=(math.radians(10), 0.0, 0.0),
        bevel=0.022, segments=4, material=mats["leather_dark"], collection=col,
    ))

    # 5. Sculpted 4D Aluminum Armrests
    for side, sx in (("L", -0.295), ("R", 0.295)):
        arm_pts = [(sx * 0.58, -0.02, 0.405), (sx * 0.96, -0.02, 0.44), (sx, -0.01, 0.65)]
        parts.append(create_curve_tube(f"Chair_ArmPost_{side}", arm_pts, radius=0.014, material=mats["gunmetal"], col=col))
        parts.append(create_beveled_box(
            f"Chair_ArmPad_{side}", (0.088, 0.255, 0.026), location=(sx, 0.02, 0.665),
            bevel=0.010, segments=3, material=mats["matte_plastic"], collection=col,
        ))

    _parent_all(parts, root)
    return root



def build_wall_pegboard_and_hex(
    wall_y: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Matte-black wall pegboard with studio headphones & mini shelf + understated hexagonal acoustic/glow wall tiles."""
    root = _new_group("Hero_WallGeekDecor", (0.0, wall_y, 0.0), col)
    parts: list[bpy.types.Object] = []

    # 1. Matte-graphite steel pegboard on left side of desk wall (X = -1.62, Z = 1.62) with warm rim halo
    pb_x, pb_z = -1.62, 1.62
    parts.append(create_beveled_box(
        "Pegboard_Panel", (0.76, 0.014, 0.56), location=(pb_x, -0.036, pb_z),
        bevel=0.004, material=mats["pegboard_graphite"], collection=col,
    ))
    parts.append(create_beveled_box(
        "Pegboard_BackGlow", (0.68, 0.008, 0.48), location=(pb_x, -0.026, pb_z),
        bevel=0.001, material=mats["emissive_cove_warm"], collection=col,
    ))
    # Mini display shelf clipped to pegboard
    parts.append(create_beveled_box(
        "Pegboard_Shelf", (0.32, 0.115, 0.012), location=(pb_x + 0.16, -0.092, pb_z - 0.12),
        bevel=0.002, material=mats["walnut_desk"], collection=col,
    ))
    # Precision anodized metal peg hooks
    for hx in (-0.28, -0.06, 0.12, 0.24):
        parts.append(create_beveled_cylinder(
            f"Peg_Hook_{hx:+.2f}", radius=0.004, depth=0.045, vertices=12,
            location=(pb_x + hx, -0.056, pb_z + 0.14), rotation=(math.radians(90), 0.0, 0.0),
            material=mats["chrome"], collection=col,
        ))

    # Over-ear Studio Headphones hanging on left side of pegboard
    hp = _new_group("Prop_StudioHeadphones", (pb_x - 0.18, -0.082, pb_z + 0.02), col)
    hp_parts: list[bpy.types.Object] = []
    band_pts = [(-0.075, 0.0, 0.0), (-0.070, 0.0, 0.085), (0.0, 0.0, 0.118), (0.070, 0.0, 0.085), (0.075, 0.0, 0.0)]
    hp_parts.append(create_curve_tube("HP_Headband", band_pts, radius=0.011, material=mats["leather_dark"], col=col))
    for ex in (-0.076, 0.076):
        hp_parts.append(create_beveled_cylinder(
            f"HP_Cup_{ex:+.2f}", radius=0.044, depth=0.032, vertices=32,
            location=(ex, 0.0, -0.025), rotation=(0.0, math.radians(90), 0.0),
            bevel=0.008, material=mats["gunmetal"], collection=col,
        ))
        hp_parts.append(create_beveled_cylinder(
            f"HP_Pad_{ex:+.2f}", radius=0.042, depth=0.018, vertices=32,
            location=(ex * 0.78, 0.0, -0.025), rotation=(0.0, math.radians(90), 0.0),
            bevel=0.007, material=mats["leather_dark"], collection=col,
        ))
    _parent_all(hp_parts, hp)
    parts.append(hp)

    # 2. Geometric Acoustic/Warm-Glow Hex Tiles on right side of feature wall (X ≈ +0.85, Z ≈ 1.85)
    hex_r = 0.115
    dx_h = hex_r * 1.58
    dy_h = hex_r * 1.82
    hex_offsets = [
        (0.0, 0.0, True),
        (dx_h, dy_h * 0.5, False),
        (dx_h, -dy_h * 0.5, True),
        (dx_h * 2.0, 0.0, False),
        (-dx_h, -dy_h * 0.5, False),
    ]
    for idx, (ox, oz, lit) in enumerate(hex_offsets):
        hx = 0.72 + ox
        hz = 1.86 + oz
        # Outer dark acoustic hex body
        parts.append(create_beveled_cylinder(
            f"HexTile_Body_{idx}", radius=hex_r, depth=0.022, vertices=6,
            location=(hx, -0.036, hz), rotation=(math.radians(90), 0.0, 0.0),
            bevel=0.003, material=mats["acoustic_felt"] if not lit else mats["anodized_black"], collection=col,
        ))
        if lit:
            parts.append(create_beveled_cylinder(
                f"Interact_HexLight_{idx}", radius=hex_r * 0.84, depth=0.008, vertices=6,
                location=(hx, -0.047, hz), rotation=(math.radians(90), 0.0, 0.0),
                bevel=0.002, material=mats["emissive_hex_tile"], collection=col,
            ))

    # 3. Recessed Horizontal Architectural Wall-Graze LED behind desk (Z = 1.55)
    parts.append(create_beveled_box(
        "Interact_WallGrazeLED", (2.10, 0.012, 0.010), location=(-0.10, -0.032, 0.80),
        bevel=0.001, material=mats["emissive_rgb_amber"], collection=col,
    ))

    _parent_all(parts, root)
    return root



def build_espresso_mug(
    location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Minimalist stoneware espresso/pour-over mug on desk coaster."""
    root = _new_group("Prop_CoffeeMug", location, col)
    parts: list[bpy.types.Object] = []
    # Walnut coaster
    parts.append(create_beveled_cylinder("Mug_Coaster", 0.048, 0.006, 32, 0.0015, location=(0.0, 0.0, 0.003), material=mats["walnut_desk"], collection=col))
    # Ceramic mug body (hollow via lathe/spin)
    bm = bmesh.new()
    profile = [
        (0.0, 0.006), (0.034, 0.006), (0.038, 0.012), (0.040, 0.092),
        (0.038, 0.096), (0.034, 0.092), (0.032, 0.016), (0.0, 0.016),
    ]
    verts = [bm.verts.new((r, 0.0, z)) for r, z in profile]
    edges = [bm.edges.new((verts[i], verts[i + 1])) for i in range(len(verts) - 1)]
    bmesh.ops.spin(bm, geom=verts + edges, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=36, use_merge=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new("Mug_Body")
    bm.to_mesh(mesh)
    bm.free()
    apply_box_uv(mesh, scale=8.0)
    mug_obj = bpy.data.objects.new("Mug_Body", mesh)
    mug_obj.data.materials.append(mats["wall_warm_plaster"])
    set_smooth_with_bevel_normals(mug_obj)
    col.objects.link(mug_obj)
    parts.append(mug_obj)

    # Handle loop
    parts.append(create_curve_tube(
        "Mug_Handle", [(0.037, 0.0, 0.078), (0.062, 0.0, 0.072), (0.062, 0.0, 0.032), (0.037, 0.0, 0.026)],
        radius=0.0045, material=mats["wall_warm_plaster"], col=col,
    ))
    # Glossy dark coffee liquid meniscus
    coffee_mat = mats["anodized_black"]
    parts.append(create_beveled_cylinder("Mug_Coffee", 0.034, 0.004, 32, 0.001, location=(0.0, 0.0, 0.078), material=coffee_mat, collection=col))

    _parent_all(parts, root)
    return root



def build_cloth_simulated_curtain(
    name: str,
    x_start: float,
    x_end: float,
    y_pos: float,
    z_top: float,
    z_bottom: float,
    material: bpy.types.Material,
    col: bpy.types.Collection,
    pleat_count: int = 9,
) -> bpy.types.Object:
    """
    Create a genuinely draped sheer linen floor-to-ceiling curtain using real Blender Cloth Physics simulation,
    then bake the simulated organic drape into clean static mesh geometry.
    """
    width = abs(x_end - x_start)
    height = z_top - z_bottom
    nx, nz = 48, 36

    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    grid = []
    for iz in range(nz + 1):
        vz = iz / nz
        z = z_top - vz * height
        row = []
        for ix in range(nx + 1):
            ux = ix / nx
            # Pleated sinusoidal gathering along curtain track
            x = x_start + ux * (x_end - x_start)
            pleat_amp = 0.052 * (1.0 - 0.15 * vz)
            y = y_pos + math.sin(ux * pleat_count * math.pi) * pleat_amp
            row.append(bm.verts.new((x, y, z)))
        grid.append(row)

    for iz in range(nz):
        for ix in range(nx):
            f = bm.faces.new((grid[iz][ix], grid[iz][ix + 1], grid[iz + 1][ix + 1], grid[iz + 1][ix]))
            u0, u1 = ix / nx, (ix + 1) / nx
            v0, v1 = 1.0 - iz / nz, 1.0 - (iz + 1) / nz
            f.loops[0][uv].uv = (u0, v0)
            f.loops[1][uv].uv = (u1, v0)
            f.loops[2][uv].uv = (u1, v1)
            f.loops[3][uv].uv = (u0, v1)

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    col.objects.link(obj)

    # Pin the top row of curtain rings/hooks to the track
    pin_vg = obj.vertex_groups.new(name="PinTop")
    top_indices = list(range(nx + 1))
    pin_vg.add(top_indices, 1.0, "REPLACE")

    # Add real Blender Cloth physics simulation
    cloth_mod = obj.modifiers.new(name="Cloth", type="CLOTH")
    cs = cloth_mod.settings
    cs.quality = 6
    cs.mass = 0.22
    cs.tension_stiffness = 12.0
    cs.compression_stiffness = 12.0
    cs.bending_stiffness = 0.35
    cs.vertex_group_mass = "PinTop"
    cs.shrink_min = -0.02

    # Run 28 frames of real gravity cloth simulation to settle natural architectural folds!
    scene = bpy.context.scene
    scene.frame_start = 1
    scene.frame_end = 30
    for f_idx in range(1, 29):
        scene.frame_set(f_idx)

    # Bake evaluated cloth mesh to clean static mesh + smooth shading
    deps = bpy.context.evaluated_depsgraph_get()
    eval_obj = obj.evaluated_get(deps)
    baked_mesh = bpy.data.meshes.new_from_object(eval_obj)
    baked_mesh.name = f"{name}_Draped"
    baked_mesh.polygons.foreach_set("use_smooth", [True] * len(baked_mesh.polygons))

    obj.modifiers.remove(cloth_mod)
    old_mesh = obj.data
    obj.data = baked_mesh
    bpy.data.meshes.remove(old_mesh, do_unlink=True)
    scene.frame_set(1)

    # Add subtle subdivision for silky-smooth grazing highlights on the folds
    sub = obj.modifiers.new("Subsurf", "SUBSURF")
    sub.levels = 1
    sub.render_levels = 1
    return obj


def build_concept_a_pc_tower(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
    fan_glb_path=None,
) -> bpy.types.Object:
    """
    Concept A Iconic Matte-Black Tempered-Glass Rectangular Mid-Tower PC (Lian Li O11 Vision / H7 Flow style).
    Upgraded v6: ZERO solid cube fans! Uses 4 real sculpted 7-blade artist cooling fans (pc_fan_core.glb)
    with open hollow charcoal frames, softly glowing curved ice-cyan blades, 360mm vertical finned radiator,
    circular AIO CPU LCD telemetry gauge ('38°C'), RTX 4090 GPU with braided power cable, and DDR5 RAM!
    """
    root = _new_group("BK_CreatorsPC", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []

    w, d, h = 0.238, 0.468, 0.456
    ft_h = 0.018
    # 4 low-profile anodized rubber feet touching Z = 0
    for fx in (-w * 0.36, w * 0.36):
        for fy in (-d * 0.38, d * 0.38):
            parts.append(create_beveled_cylinder(
                f"PC_Foot_{fx:+.2f}_{fy:+.2f}", radius=0.017, depth=ft_h, vertices=20,
                location=(fx, fy, ft_h * 0.5), bevel=0.003, material=mats["matte_plastic"], collection=col,
            ))

    base_z = ft_h
    body_h = h - ft_h
    # Solid matte-black outer shell: rear-recessed PSU shroud (leaves open front 360mm fan chamber!),
    # full bottom floor plate, top ventilated cover, solid right panel, rear IO wall, and crisp O11 steel trim!
    parts.append(create_beveled_box("PC_BottomFloor", (w, d, 0.016), (0.0, 0.0, base_z + 0.008), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_BottomPSUShroud", (w - 0.014, d - 0.115, 0.088), (0.005, 0.056, base_z + 0.048), bevel=0.004, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_TopPanel", (w, d, 0.024), (0.0, 0.0, h - 0.012), bevel=0.004, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_RightSolidPanel", (0.016, d, body_h), (w * 0.5 - 0.008, 0.0, base_z + body_h * 0.5), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_RearWall", (w, 0.016, body_h), (0.0, d * 0.5 - 0.008, base_z + body_h * 0.5), bevel=0.003, material=mats["anodized_black"], collection=col))
    # O11 Dynamic front-right steel I/O column + slim top/bottom framing rails
    parts.append(create_beveled_box("PC_FrontRightStrip", (0.042, 0.018, body_h), (w * 0.5 - 0.021, -d * 0.5 + 0.009, base_z + body_h * 0.5), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_FrontTopTrim", (w, 0.018, 0.018), (0.0, -d * 0.5 + 0.009, h - 0.018), bevel=0.002, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("PC_SideBottomTrim", (0.014, d, 0.018), (-w * 0.5 + 0.007, 0.0, base_z + 0.014), bevel=0.002, material=mats["anodized_black"], collection=col))

    # Crisp dark smoked tempered glass panes (Panoramic Left + Front glass meeting cleanly at corner!)
    glass_h = body_h - 0.044
    glass_cz = base_z + 0.020 + glass_h * 0.5
    parts.append(create_beveled_box(
        "PC_GlassSide", (0.004, d - 0.020, glass_h), (-w * 0.5 + 0.004, 0.0, glass_cz),
        bevel=0.001, material=mats["pc_glass"], collection=col,
    ))
    parts.append(create_beveled_box(
        "PC_GlassFront", (w - 0.048, 0.004, glass_h), (-0.020, -d * 0.5 + 0.004, glass_cz),
        bevel=0.001, material=mats["pc_glass"], collection=col,
    ))

    # Internal dark matte ATX Motherboard, VRM Heatsinks & 4 DDR5 RAM sticks
    parts.append(create_beveled_box("PC_Motherboard", (0.012, 0.295, 0.275), (0.072, 0.045, base_z + 0.255), bevel=0.002, material=mats["matte_plastic"], collection=col))
    parts.append(create_beveled_box("PC_VRMHeatSink", (0.026, 0.056, 0.115), (0.056, 0.125, base_z + 0.315), bevel=0.003, material=mats["gunmetal"], collection=col))
    parts.append(create_beveled_box("PC_ChipsetHeatsink", (0.018, 0.095, 0.068), (0.060, -0.025, base_z + 0.165), bevel=0.003, material=mats["gunmetal"], collection=col))
    for idx, ry in enumerate((-0.025, -0.038, -0.051, -0.064)):
        parts.append(create_beveled_box(f"PC_RAM_{idx}", (0.036, 0.006, 0.126), (0.050, ry, base_z + 0.295), bevel=0.001, material=mats["gunmetal"], collection=col))
        parts.append(create_beveled_box(f"PC_RAM_LED_{idx}", (0.004, 0.004, 0.120), (0.031, ry, base_z + 0.295), bevel=0.001, material=mats["emissive_rgb_cyan"], collection=col))

    # AIO CPU Liquid Pump Block with glowing circular LCD Telemetry Gauge ('38°C') + twin braided hoses
    parts.append(create_beveled_cylinder(
        "PC_AIOPump", radius=0.035, depth=0.042, vertices=32,
        location=(0.044, 0.042, base_z + 0.305), rotation=(0.0, math.radians(90), 0.0),
        bevel=0.004, material=mats["anodized_black"], collection=col,
    ))
    # Circular UV-mapped AIO LCD screen facing -X (from -X viewing +X: +Y is LEFT u=0, -Y is RIGHT u=1!)
    bm_lcd = bmesh.new()
    uv_lcd = bm_lcd.loops.layers.uv.verify()
    lcd_r = 0.028
    segs_lcd = 28
    ring_v = []
    for k in range(segs_lcd):
        a = k * (2.0 * math.pi / segs_lcd)
        ring_v.append(bm_lcd.verts.new((0.022, 0.042 + lcd_r * math.cos(a), base_z + 0.305 + lcd_r * math.sin(a))))
    f_lcd = bm_lcd.faces.new(list(reversed(ring_v)))
    for k, loop in enumerate(f_lcd.loops):
        a = (segs_lcd - 1 - k) * (2.0 * math.pi / segs_lcd)
        loop[uv_lcd].uv = (0.5 - 0.5 * math.cos(a), 0.5 + 0.5 * math.sin(a))
    lcd_mesh = bpy.data.meshes.new("PC_AIO_LCDScreen")
    bm_lcd.to_mesh(lcd_mesh)
    bm_lcd.free()
    lcd_obj = bpy.data.objects.new("PC_AIO_LCDScreen", lcd_mesh)
    lcd_obj.data.materials.append(mats["screen_aio_lcd"])
    col.objects.link(lcd_obj)
    parts.append(lcd_obj)

    parts.append(create_curve_tube(
        "PC_AIOTube1", [(0.032, 0.015, base_z + 0.325), (-0.026, -0.055, base_z + 0.365), (-0.012, -0.135, base_z + 0.398)],
        radius=0.006, material=mats["matte_plastic"], col=col, bevel_res=5,
    ))
    parts.append(create_curve_tube(
        "PC_AIOTube2", [(0.032, 0.005, base_z + 0.295), (-0.034, -0.085, base_z + 0.345), (-0.020, -0.145, base_z + 0.395)],
        radius=0.006, material=mats["matte_plastic"], col=col, bevel_res=5,
    ))

    # Flagship Triple-Slot RTX 4090 GPU with matte gunmetal shroud, brushed backplate, subtle amber bar & braided 12VHPWR cable
    parts.append(create_beveled_box(
        "PC_RTX_GPU", (0.130, 0.305, 0.060), (0.008, 0.025, base_z + 0.188),
        bevel=0.005, segments=3, material=mats["gunmetal"], collection=col,
    ))
    parts.append(create_beveled_box(
        "PC_GPU_Backplate", (0.128, 0.302, 0.005), (0.008, 0.025, base_z + 0.220),
        bevel=0.001, material=mats["anodized_black"], collection=col,
    ))
    parts.append(create_beveled_box(
        "PC_GPU_AccentBar", (0.005, 0.138, 0.007), (-0.059, 0.012, base_z + 0.198),
        bevel=0.001, material=mats["emissive_rgb_amber"], collection=col,
    ))
    parts.append(create_curve_tube(
        "PC_GPUCable", [(-0.040, -0.040, base_z + 0.188), (-0.054, -0.062, base_z + 0.142), (-0.012, -0.056, base_z + 0.092)],
        radius=0.0075, material=mats["matte_plastic"], col=col, bevel_res=5,
    ))

    # 360mm Vertical Radiator Frame behind the 3 front intake fans (clean dark architectural fins!)
    parts.append(create_beveled_box(
        "PC_RadiatorFrame", (0.118, 0.024, 0.376), (-0.018, -d * 0.5 + 0.066, base_z + 0.214),
        bevel=0.003, material=mats["anodized_black"], collection=col,
    ))

    # === 4 REAL SCULPTED 7-BLADE ARTIST COOLING FANS (pc_fan_core.glb — ZERO SOLID CUBES!) ===
    fan_template_meshes: list[tuple[bpy.types.Mesh, bpy.types.Material, Vector]] = []
    if fan_glb_path is not None and fan_glb_path.exists():
        before = set(bpy.data.objects)
        bpy.ops.import_scene.gltf(filepath=str(fan_glb_path))
        imported_fan = [o for o in bpy.data.objects if o not in before]
        bpy.context.view_layer.update()
        f_meshes = [o for o in imported_fan if o.type == "MESH"]
        if f_meshes:
            mn = Vector((1e9, 1e9, 1e9))
            mx = Vector((-1e9, -1e9, -1e9))
            for fm in f_meshes:
                for c in fm.bound_box:
                    wc = fm.matrix_world @ Vector(c)
                    mn = Vector((min(mn.x, wc.x), min(mn.y, wc.y), min(mn.z, wc.z)))
                    mx = Vector((max(mx.x, wc.x), max(mx.y, wc.y), max(mx.z, wc.z)))
            f_center = (mn + mx) * 0.5
            f_span = max(mx.x - mn.x, mx.y - mn.y, 1e-4)
            f_scale = 0.116 / f_span  # Exact 116mm fan width!
            for fm in f_meshes:
                # Decimate heavy fan mesh cleanly (~18% -> crisp ~8k polys per fan!)
                if len(fm.data.polygons) > 3000:
                    dmod = fm.modifiers.new("FanOpt", "DECIMATE")
                    dmod.ratio = 0.18
                deps = bpy.context.evaluated_depsgraph_get()
                eval_fm = fm.evaluated_get(deps)
                baked = bpy.data.meshes.new_from_object(eval_fm, preserve_all_data_layers=True, depsgraph=deps)
                # Bake world transform + centering + scaling directly into vertices so instancing is effortless
                bm_f = bmesh.new()
                bm_f.from_mesh(baked)
                wm = fm.matrix_world
                for v in bm_f.verts:
                    p = (wm @ v.co) - f_center
                    v.co = p * f_scale
                bmesh.ops.recalc_face_normals(bm_f, faces=bm_f.faces)
                bm_f.to_mesh(baked)
                bm_f.free()
                baked.polygons.foreach_set("use_smooth", [True] * len(baked.polygons))
                is_blade = "wing" in fm.name.lower() or "blade" in fm.name.lower()
                fmat = mats["emissive_pc_fan_blade"] if is_blade else mats["anodized_black"]
                baked.materials.clear()
                baked.materials.append(fmat)
                fan_template_meshes.append((baked, fmat, Vector((0, 0, 0))))
        for o in imported_fan:
            bpy.data.objects.remove(o, do_unlink=True)

    def add_sculpted_rgb_fan(fname: str, floc: tuple[float, float, float], rot_xyz: tuple[float, float, float], glow_mat: bpy.types.Material) -> None:
        # 1. Real sculpted 7-blade fan shroud + curved blades (native axis is Z -> rotate +90° X to face -Y!)
        fan_rot = (rot_xyz[0] + math.radians(90.0), rot_xyz[1], rot_xyz[2])
        for idx_m, (tmesh, _tmat, _off) in enumerate(fan_template_meshes):
            fobj = bpy.data.objects.new(f"PC_RealFan_{fname}_{idx_m}", tmesh)
            fobj.location = floc
            fobj.rotation_euler = fan_rot
            col.objects.link(fobj)
            parts.append(fobj)
        # 2. Thin outer glowing halo ring sitting flush at front rim (radius 0.052..0.0555 — NEVER covers the 7 blades!)
        bm_r = bmesh.new()
        r_prof = [(0.0555, -0.002), (0.0555, 0.002), (0.0515, 0.002), (0.0515, -0.002), (0.0555, -0.002)]
        rv = [bm_r.verts.new((rr, 0.0, zz)) for rr, zz in r_prof]
        re = [bm_r.edges.new((rv[i], rv[i + 1])) for i in range(len(rv) - 1)]
        bmesh.ops.spin(bm_r, geom=rv + re, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=32, use_merge=True)
        bmesh.ops.recalc_face_normals(bm_r, faces=bm_r.faces)
        rmesh = bpy.data.meshes.new(f"PC_FanHalo_{fname}")
        bm_r.to_mesh(rmesh)
        bm_r.free()
        apply_box_uv(rmesh, scale=6.0)
        robj = bpy.data.objects.new(f"PC_FanHalo_{fname}", rmesh)
        robj.location = (floc[0], floc[1] - 0.013, floc[2])
        robj.rotation_euler = fan_rot
        robj.data.materials.append(glow_mat)
        set_smooth_with_bevel_normals(robj)
        col.objects.link(robj)
        parts.append(robj)

    # Rear exhaust fan + 3 stacked unobstructed Front 120mm intake fans!
    add_sculpted_rgb_fan("Rear", (-0.010, d * 0.5 - 0.032, base_z + 0.320), (0.0, 0.0, 0.0), mats["emissive_pc_fan"])
    add_sculpted_rgb_fan("FrontTop", (-0.018, -d * 0.5 + 0.034, base_z + 0.336), (0.0, 0.0, 0.0), mats["emissive_rgb_cyan"])
    add_sculpted_rgb_fan("FrontMid", (-0.018, -d * 0.5 + 0.034, base_z + 0.214), (0.0, 0.0, 0.0), mats["emissive_rgb_cyan"])
    add_sculpted_rgb_fan("FrontBot", (-0.018, -d * 0.5 + 0.034, base_z + 0.092), (0.0, 0.0, 0.0), mats["emissive_pc_fan"])

    # Subtle top interior showcase lightbar
    parts.append(create_beveled_box(
        "PC_TopLightBar", (0.010, d - 0.10, 0.006), (-w * 0.28, 0.0, h - 0.030),
        bevel=0.001, material=mats["emissive_rgb_cyan"], collection=col,
    ))

    _parent_all(parts, root)
    return root



def build_concept_a_mic_boom_arm(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Signature Concept A Matte-Black Articulated Scissor Broadcast Mic Boom Arm + Shure SM7B Dynamic Mic,
    clamped prominently to the left edge of the walnut desk and arching gracefully in front of the left speaker!
    """
    dx, dy, _ = desk_origin
    desk_h = 0.750
    root = _new_group("Hero_ConceptAMicBoom", (dx - 1.02, dy + 0.26, desk_h), col)
    parts: list[bpy.types.Object] = []

    # Heavy matte-black desk C-clamp
    parts.append(create_beveled_box("Mic_ClampTop", (0.064, 0.064, 0.022), (0.0, 0.0, 0.011), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_cylinder("Mic_ClampPost", 0.012, 0.065, 20, location=(0.0, 0.0, 0.045), bevel=0.002, material=mats["gunmetal"], collection=col))

    # Lower & upper dual scissor arm arching UP & FORWARD (-Y) cleanly over left desk & in front of left speaker!
    # Guarantees >= 15cm X-clearance & >= 20cm Y-clearance from Monitor_Ultrawide38 AND clear above speaker + MacBook!
    j0 = Vector((0.0, 0.0, 0.065))
    j1 = Vector((0.03, -0.04, 0.45))
    j2 = Vector((0.23, -0.22, 0.57))

    for off_z in (-0.014, 0.014):
        parts.append(create_curve_tube(
            f"Mic_ArmLower_{off_z:+.3f}",
            [(j0.x, j0.y, j0.z + off_z), ((j0.x + j1.x) * 0.5, (j0.y + j1.y) * 0.5, (j0.z + j1.z) * 0.5 + off_z), (j1.x, j1.y, j1.z + off_z)],
            radius=0.0068, material=mats["anodized_black"], col=col, bevel_res=5,
        ))
        parts.append(create_curve_tube(
            f"Mic_ArmUpper_{off_z:+.3f}",
            [(j1.x, j1.y, j1.z + off_z), ((j1.x + j2.x) * 0.5, (j1.y + j2.y) * 0.5, (j1.z + j2.z) * 0.5 + off_z), (j2.x, j2.y, j2.z + off_z)],
            radius=0.0064, material=mats["anodized_black"], col=col, bevel_res=5,
        ))

    # Articulated tension elbow knobs
    for jn, jp in (("Elbow", j1), ("Wrist", j2)):
        parts.append(create_beveled_cylinder(
            f"Mic_Joint_{jn}", radius=0.016, depth=0.036, vertices=22,
            location=(jp.x, jp.y, jp.z), rotation=(math.radians(90), 0.0, 0.0),
            bevel=0.003, material=mats["gunmetal"], collection=col,
        ))

    # Drop link down to SM7B mic yoke mounting knuckle (connects flush to center of Mic_YokeBar — ZERO floating gap!)
    j3 = Vector((0.23, -0.32, 0.47))
    parts.append(create_curve_tube(
        "Mic_DropLink", [(j2.x, j2.y, j2.z), (j3.x, j3.y, j3.z + 0.052)],
        radius=0.0080, material=mats["anodized_black"], col=col, bevel_res=5,
    ))
    parts.append(create_beveled_cylinder(
        "Mic_MountKnuckle", radius=0.011, depth=0.022, vertices=20,
        location=(j3.x, j3.y, j3.z + 0.050), bevel=0.002,
        material=mats["gunmetal"], collection=col,
    ))

    # Shure SM7B Broadcast Microphone angled cleanly INWARD & UP toward seated user (+28 deg -> faces +X, -Y!)
    # Real SM7B architecture: top U-yoke centered directly under drop knuckle (y=0), clamping rear of black canister,
    # with sculpted dark-charcoal acoustic foam windscreen extending cleanly forward (-Y) toward the user!
    mic = _new_group("Mic_SM7B_Head", (j3.x, j3.y, j3.z), col, rot_z_deg=28.0)
    mic.rotation_euler.x = math.radians(-10.0)
    mparts: list[bpy.types.Object] = []
    mparts.append(create_beveled_box("Mic_YokeBar", (0.080, 0.014, 0.010), (0.0, 0.0, 0.046), bevel=0.002, material=mats["anodized_black"], collection=col))
    for ux in (-0.037, 0.037):
        mparts.append(create_beveled_box(f"Mic_YokeSide_{ux:+.2f}", (0.008, 0.014, 0.064), (ux, 0.0, 0.016), bevel=0.002, material=mats["anodized_black"], collection=col))
        mparts.append(create_beveled_cylinder(f"Mic_ThumbNut_{ux:+.2f}", 0.008, 0.008, 14, 0.0015, location=(ux * 1.18, 0.0, -0.012), rotation=(0.0, math.radians(90), 0.0), material=mats["brushed_brass"], collection=col))
    mparts.append(create_beveled_cylinder(
        "Mic_Canister", radius=0.028, depth=0.104, vertices=32,
        location=(0.0, -0.016, -0.012), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.004, material=mats["anodized_black"], collection=col,
    ))
    # Signature Shure SM7B slim gunmetal grille transition ring between canister & foam windscreen
    mparts.append(create_beveled_cylinder(
        "Mic_CollarRing", radius=0.0292, depth=0.009, vertices=32,
        location=(0.0, -0.066, -0.012), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.0015, material=mats["gunmetal"], collection=col,
    ))
    mparts.append(create_beveled_cylinder(
        "Mic_RearXLRPlug", radius=0.011, depth=0.026, vertices=18,
        location=(0.0, 0.046, -0.012), rotation=(math.radians(90), 0.0, 0.0),
        bevel=0.002, material=mats["gunmetal"], collection=col,
    ))
    # Authentic smooth rounded-capsule Shure A7WS acoustic foam windscreen (ZERO stepped flat pancake cap!)
    bm_wf = bmesh.new()
    segs = 36
    # Profile in (radius, local_y_along_axis) from rear seam y=-0.066 to smoothly domed front nose y=-0.166
    wf_prof = [
        (0.0280, -0.066),
        (0.0315, -0.070),
        (0.0328, -0.080),
        (0.0332, -0.105),
        (0.0326, -0.130),
        (0.0306, -0.144),
        (0.0262, -0.154),
        (0.0195, -0.161),
        (0.0108, -0.165),
        (0.0000, -0.167),
    ]
    wf_rings = []
    for r_w, y_w in wf_prof:
        if r_w <= 1e-5:
            wf_rings.append([bm_wf.verts.new((0.0, y_w, -0.012))])
        else:
            wf_rings.append([
                bm_wf.verts.new((r_w * math.cos(2.0 * math.pi * k / segs), y_w, -0.012 + r_w * math.sin(2.0 * math.pi * k / segs)))
                for k in range(segs)
            ])
    for ri in range(len(wf_rings) - 1):
        a, b = wf_rings[ri], wf_rings[ri + 1]
        if len(b) == 1:
            for k in range(segs):
                bm_wf.faces.new((a[k], a[(k + 1) % segs], b[0]))
        else:
            for k in range(segs):
                kn = (k + 1) % segs
                bm_wf.faces.new((a[k], a[kn], b[kn], b[k]))
    # Rear cap closing cleanly against canister
    bm_wf.faces.new(list(reversed(wf_rings[0])))
    bmesh.ops.recalc_face_normals(bm_wf, faces=bm_wf.faces)
    uv_wf = bm_wf.loops.layers.uv.verify()
    for f in bm_wf.faces:
        f.smooth = True
        for lp in f.loops:
            co = lp.vert.co
            lp[uv_wf].uv = (math.atan2(co.z + 0.012, co.x) / (2.0 * math.pi) + 0.5, (co.y + 0.167) * 6.0)
    wf_mesh = bpy.data.meshes.new("Mic_WindscreenFoam")
    bm_wf.to_mesh(wf_mesh)
    bm_wf.free()
    wf_obj = bpy.data.objects.new("Mic_WindscreenFoam", wf_mesh)
    wf_obj.data.materials.append(mats["mic_foam"])
    col.objects.link(wf_obj)
    mparts.append(wf_obj)
    _parent_all(mparts, mic)
    parts.append(mic)

    # Routed matte-black XLR cable curving cleanly from clamp to rear desk grommet
    parts.append(create_curve_tube(
        "Mic_XLRCable",
        [(0.01, 0.02, 0.012), (0.18, 0.14, 0.008), (0.42, 0.22, 0.008), (0.58, 0.20, 0.014)],
        radius=0.0038, material=mats["matte_plastic"], col=col, bevel_res=5,
    ))

    _parent_all(parts, root)
    return root



def build_concept_a_track_lighting(
    center_x: float,
    y_pos: float,
    ceiling_z: float,
    span_w: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Signature Concept A Ceiling Magnetic Track Rail + 3 Matte-Black Articulated Cylindrical Spotlights
    visibly framing the top of the hero shot with warm glowing LED aperture lenses!
    """
    root = _new_group("Hero_CeilingTrackRail", (center_x, y_pos, ceiling_z), col)
    parts: list[bpy.types.Object] = []

    # Continuous matte-black anodized aluminum track bar
    parts.append(create_beveled_box(
        "Track_MainRail", (span_w, 0.042, 0.028), (0.0, 0.0, -0.014),
        bevel=0.002, material=mats["anodized_black"], collection=col,
    ))
    # 3 Sleek cylindrical articulated gallery spotlight heads
    spot_configs = [
        ("L", -span_w * 0.34, 20.0, -6.0),
        ("C", 0.0, 22.0, 0.0),
        ("R", span_w * 0.34, 20.0, 10.0),
    ]
    for sname, sx, pitch_deg, yaw_deg in spot_configs:
        parts.append(create_beveled_box(
            f"Track_Adapter_{sname}", (0.056, 0.036, 0.022), (sx, 0.0, -0.034),
            bevel=0.002, material=mats["anodized_black"], collection=col,
        ))
        parts.append(create_beveled_cylinder(
            f"Track_Stem_{sname}", radius=0.008, depth=0.045, vertices=16,
            location=(sx, 0.0, -0.060), material=mats["gunmetal"], collection=col,
        ))
        head = _new_group(f"Track_Head_{sname}", (sx, 0.0, -0.095), col, rot_z_deg=yaw_deg)
        head.rotation_euler.x = math.radians(pitch_deg)
        can = create_beveled_cylinder(
            f"Track_Can_{sname}", radius=0.028, depth=0.096, vertices=28,
            location=(0.0, 0.0, 0.0), bevel=0.004, material=mats["anodized_black"], collection=col,
        )
        lens = create_beveled_cylinder(
            f"Track_LEDLens_{sname}", radius=0.022, depth=0.006, vertices=24,
            location=(0.0, 0.0, -0.046), bevel=0.001, material=mats["emissive_track_led"], collection=col,
        )
        can.parent = head
        lens.parent = head
        parts.append(head)

    _parent_all(parts, root)
    return root



def build_concept_a_pegboard(
    location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    v6 Photorealistic Matte-Black IKEA SKADIS Pegboard (ZERO floating cylinders, ZERO stiff circle donuts!):
    - Real 3D L/J-hooks physically seated into recessed pill slots
    - Top-left wide headphone hook (physically supports BK_PegHeadset headband)
    - Top-right hooked steel display tray (holds real BK_PegGameBoy + iFixit anodized bit case)
    - Mid-center twin controller cradle hooks (physically cradle real BK_PegDualSense)
    - Mid-right vertical tool U-ring holder (holds real 1-piece BK_PegScrewdriver hanging straight down!)
    - Bottom-left & bottom-right gravity-draped teardrop braided cables pinched at hooks + velcro cable ties!
    """
    root = _new_group("Hero_ConceptAPegboard", location, col)
    parts: list[bpy.types.Object] = []

    pw, ph = 0.62, 0.66
    # Matte-black beveled steel pegboard panel spaced 22mm off concrete wall (front face at Y = -0.028)
    parts.append(create_beveled_box(
        "Peg_BoardPanel", (pw, 0.012, ph), (0.0, -0.022, 0.0),
        bevel=0.006, segments=3, material=mats["anodized_black"], collection=col,
    ))
    for sx in (-pw * 0.42, pw * 0.42):
        for sz in (-ph * 0.42, ph * 0.42):
            parts.append(create_beveled_cylinder(
                f"Peg_Spacer_{sx:+.2f}_{sz:+.2f}", radius=0.008, depth=0.022, vertices=12,
                location=(sx, -0.011, sz), rotation=(math.radians(90), 0.0, 0.0),
                material=mats["gunmetal"], collection=col,
            ))

    # Crisp batched pill-slot recesses
    bm_slots = bmesh.new()
    cols, rows = 11, 12
    for r in range(rows):
        for c in range(cols):
            if (r + c) % 2 != 0:
                continue
            sx = -pw * 0.43 + (c / (cols - 1)) * (pw * 0.86)
            sz = -ph * 0.43 + (r / (rows - 1)) * (ph * 0.86)
            mat_t = bmesh.ops.create_cube(bm_slots, size=1.0)
            for v in mat_t["verts"]:
                v.co.x = v.co.x * 0.006 + sx
                v.co.y = v.co.y * 0.003 - 0.0285
                v.co.z = v.co.z * 0.018 + sz
    bmesh.ops.recalc_face_normals(bm_slots, faces=bm_slots.faces)
    smesh = bpy.data.meshes.new("Peg_SlotGrid")
    bm_slots.to_mesh(smesh)
    bm_slots.free()
    apply_box_uv(smesh, scale=8.0)
    sobj = bpy.data.objects.new("Peg_SlotGrid", smesh)
    sobj.data.materials.append(mats["wall_concrete_seam"])
    col.objects.link(sobj)
    parts.append(sobj)

    def add_j_hook(hname: str, hx: float, hz: float, depth: float = 0.044, radius: float = 0.0034) -> None:
        pts = [
            (hx, -0.024, hz + 0.008),
            (hx, -0.029, hz),
            (hx, -0.029 - depth * 0.65, hz - 0.004),
            (hx, -0.029 - depth, hz - 0.001),
            (hx, -0.029 - depth - 0.006, hz + 0.014),
        ]
        parts.append(create_curve_tube(hname, pts, radius=radius, material=mats["gunmetal"], col=col, bevel_res=5))

    # 1. Top-Left Wide Headphone Cradle Hook (supports BK_PegHeadset headband at local x=-0.16, z=+0.22!)
    parts.append(create_beveled_box("Peg_HPHook_Back", (0.044, 0.008, 0.022), (-0.16, -0.030, 0.220), bevel=0.002, material=mats["gunmetal"], collection=col))
    parts.append(create_beveled_box("Peg_HPHook_Arm", (0.034, 0.068, 0.008), (-0.16, -0.062, 0.214), bevel=0.002, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("Peg_HPHook_Lip", (0.034, 0.008, 0.018), (-0.16, -0.094, 0.221), bevel=0.002, material=mats["anodized_black"], collection=col))

    # 2. Top-Right Hooked Matte-Steel IKEA SKADIS Mini-Shelf (holds real Game Boy Color + iFixit Mako bit kit!)
    sh_x, sh_z, sh_w, sh_d = 0.135, 0.115, 0.245, 0.082
    parts.append(create_beveled_box("Peg_ShelfBase", (sh_w, sh_d, 0.006), (sh_x, -0.028 - sh_d * 0.5, sh_z), bevel=0.0015, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("Peg_ShelfLipF", (sh_w, 0.005, 0.016), (sh_x, -0.028 - sh_d + 0.0025, sh_z + 0.008), bevel=0.001, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("Peg_ShelfBack", (sh_w, 0.006, 0.026), (sh_x, -0.030, sh_z + 0.012), bevel=0.001, material=mats["anodized_black"], collection=col))
    # Compact anodized aluminum iFixit precision bit driver case resting neatly on right half of mini-shelf
    parts.append(create_beveled_box("Peg_iFixitCase", (0.092, 0.062, 0.024), (sh_x + 0.056, -0.068, sh_z + 0.015), rotation=(0.0, 0.0, math.radians(-5.0)), bevel=0.003, material=mats["gunmetal"], collection=col))
    parts.append(create_beveled_box("Peg_iFixitStripe", (0.093, 0.010, 0.006), (sh_x + 0.056, -0.096, sh_z + 0.016), rotation=(0.0, 0.0, math.radians(-5.0)), bevel=0.001, material=mats["emissive_rgb_cyan"], collection=col))

    # 3. Mid-Center Twin Controller Cradle Hooks (physically hold real BK_PegDualSense at local x=-0.02, z=-0.035!)
    for cx_off in (-0.046, 0.046):
        add_j_hook(f"Peg_CtrlHook_{cx_off:+.3f}", -0.02 + cx_off, -0.068, depth=0.062, radius=0.0036)

    # 4. Mid-Right Vertical Tool U-Ring Holder (physically holds real 1-piece BK_PegScrewdriver hanging straight down!)
    sd_x, sd_z = 0.21, -0.04
    parts.append(create_beveled_box("Peg_ToolClampBack", (0.030, 0.008, 0.024), (sd_x, -0.030, sd_z), bevel=0.002, material=mats["gunmetal"], collection=col))
    u_pts = [
        (sd_x - 0.011, -0.032, sd_z),
        (sd_x - 0.013, -0.052, sd_z),
        (sd_x - 0.008, -0.064, sd_z),
        (sd_x + 0.008, -0.064, sd_z),
        (sd_x + 0.013, -0.052, sd_z),
        (sd_x + 0.011, -0.032, sd_z),
    ]
    parts.append(create_curve_tube("Peg_ToolURing", u_pts, radius=0.0030, material=mats["gunmetal"], col=col, bevel_res=5))

    # 5. Two Realistic Gravity-Draped Teardrop Braided Audio/USB Cables + Matte Velcro Ties!
    def add_draped_cable(cname: str, hx: float, hz: float, drop_h: float, half_w: float, cmat: bpy.types.Material) -> None:
        add_j_hook(f"{cname}_Hook", hx, hz, depth=0.046, radius=0.0034)
        for strand in range(2):
            pts = []
            n_pts = 28
            y_base = -0.044 - strand * 0.0085
            w_s = half_w * (1.0 - strand * 0.11)
            h_s = drop_h * (1.0 - strand * 0.06)
            for k in range(n_pts + 1):
                t = k / float(n_pts)
                ang = t * 2.0 * math.pi  # 0 = top pinched over hook, pi = bottom sagging belly
                # True gravity teardrop: narrow pinch at top (ang=0), fuller weighted drop toward bottom (ang=pi)!
                sag = 0.5 * (1.0 - math.cos(ang))  # 0 at top -> 1 at bottom
                pinch = 0.24 + 0.76 * (sag ** 0.72)
                px = hx + w_s * math.sin(ang) * pinch
                pz = hz - sag * h_s
                py = y_base - 0.004 * math.sin(ang * 2.0)
                pts.append((px, py, pz))
            parts.append(create_curve_tube(f"{cname}_Strand_{strand}", pts, radius=0.0042, material=cmat, col=col, bevel_res=5))
        # Matte velcro cable-tie strap cinching the top neck just below the hook!
        parts.append(create_beveled_box(
            f"{cname}_VelcroTie", (0.026, 0.022, 0.010), (hx, -0.048, hz - 0.034),
            bevel=0.002, material=mats["anodized_black"], collection=col,
        ))

    add_draped_cable("Peg_CableLeft", -0.18, -0.03, drop_h=0.22, half_w=0.056, cmat=mats["matte_plastic"])
    add_draped_cable("Peg_CableCenter", 0.06, -0.10, drop_h=0.145, half_w=0.046, cmat=mats["gunmetal"])

    _parent_all(parts, root)
    return root



def build_cascading_pothos_vines(
    pot_location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Concept A Lush Cascading Trailing Pothos Plant perched on the East Bookshelf top corner,
    with 9 organic vines and ~160 curved heart-shaped leaves draping gracefully down the black steel frame!
    Batched into 2 clean meshes (stems + leaves) = only 2 Draw Calls!
    """
    import random

    root = _new_group("Hero_CascadingPothos", pot_location, col)
    parts: list[bpy.types.Object] = []

    # Sculpted matte charcoal ceramic pot + dark soil disc
    parts.append(create_beveled_cylinder(
        "Pothos_Pot", radius=0.092, depth=0.175, vertices=28,
        location=(0.0, 0.0, 0.088), bevel=0.008, material=mats["ceramic_charcoal"], collection=col,
    ))
    parts.append(create_beveled_cylinder(
        "Pothos_Soil", radius=0.084, depth=0.012, vertices=24,
        location=(0.0, 0.0, 0.168), material=mats["wall_concrete_seam"], collection=col,
    ))

    rng = random.Random(42)
    bm_leaves = bmesh.new()

    def add_leaf(pos: Vector, fwd: Vector, scale: float, roll: float) -> None:
        # Curved heart/ovate pothos leaf (7 verts, 5 quads/tris -> silky organic curve!)
        local_pts = [
            Vector((0.0, 0.0, 0.0)),           # 0 stem base
            Vector((-0.024, 0.018, 0.004)),    # 1 left lobe
            Vector((0.024, 0.018, 0.004)),     # 2 right lobe
            Vector((-0.028, 0.052, 0.002)),    # 3 left mid
            Vector((0.028, 0.052, 0.002)),     # 4 right mid
            Vector((0.0, 0.048, -0.004)),      # 5 center vein crease
            Vector((0.0, 0.092, -0.014)),      # 6 tapered leaf tip drooping slightly
        ]
        # Build local basis pointing along `fwd`
        y_ax = fwd.normalized()
        up_ref = Vector((0.0, 0.0, 1.0)) if abs(y_ax.z) < 0.92 else Vector((1.0, 0.0, 0.0))
        x_ax = y_ax.cross(up_ref).normalized()
        z_ax = x_ax.cross(y_ax).normalized()
        cr, sr = math.cos(roll), math.sin(roll)
        rx = x_ax * cr + z_ax * sr
        rz = -x_ax * sr + z_ax * cr

        vs = [bm_leaves.verts.new(pos + (rx * p.x + y_ax * p.y + rz * p.z) * scale) for p in local_pts]
        for tri in ((0, 1, 5), (0, 5, 2), (1, 3, 5), (5, 4, 2), (3, 6, 5), (5, 6, 4)):
            try:
                bm_leaves.faces.new((vs[tri[0]], vs[tri[1]], vs[tri[2]]))
            except ValueError:
                pass

    # 1. Bushy crown of upright & arching leaves inside the pot
    for i in range(28):
        ang = rng.uniform(0.0, 2.0 * math.pi)
        r = rng.uniform(0.01, 0.075)
        p = Vector((r * math.cos(ang), r * math.sin(ang), 0.175 + rng.uniform(0.02, 0.16)))
        d = Vector((math.cos(ang) * 0.85, math.sin(ang) * 0.85, rng.uniform(0.15, 0.85)))
        add_leaf(p, d, rng.uniform(0.85, 1.35), rng.uniform(-0.4, 0.4))

    # 2. 9 Graceful cascading vines draping down the front-left (-X / -Y facing room & hero camera!)
    vine_configs = [
        # (exit_ang_deg, length_m, sway_x, sway_y)
        (165.0, 0.98, -0.10, -0.06),
        (185.0, 1.12, -0.14, -0.02),
        (202.0, 0.88, -0.08, -0.10),
        (220.0, 1.05, -0.05, -0.14),
        (240.0, 0.78, -0.02, -0.12),
        (148.0, 0.72, -0.12, 0.04),
        (195.0, 0.62, -0.18, -0.05),
        (212.0, 0.82, -0.12, -0.16),
        (175.0, 0.54, -0.09, 0.02),
    ]
    for vi, (ang_deg, length, sx, sy) in enumerate(vine_configs):
        ang = math.radians(ang_deg)
        c, s = math.cos(ang), math.sin(ang)
        stem_pts = []
        steps = 12
        for k in range(steps):
            t = k / float(steps - 1)
            if t < 0.20:
                u = t / 0.20
                px = c * (0.04 + 0.075 * u)
                py = s * (0.04 + 0.075 * u)
                pz = 0.17 + 0.055 * math.sin(u * math.pi * 0.65)
            else:
                u = (t - 0.20) / 0.80
                px = c * 0.115 + sx * u + 0.025 * math.sin(u * 5.2 + vi)
                py = s * 0.115 + sy * u + 0.022 * math.cos(u * 4.5 + vi * 1.3)
                pz = 0.215 - u * length
            stem_pts.append((px, py, pz))
            if k >= 2:
                # Attach 1-2 alternating leaves along vine facing outward toward room/camera
                for side in (-1, 1) if k % 2 == 0 else (1,):
                    lp = Vector((px, py, pz))
                    ld = Vector((c * 0.55 + side * 0.35 * (-s) + rng.uniform(-0.2, 0.2), s * 0.55 + side * 0.35 * c - 0.25, rng.uniform(-0.75, -0.15)))
                    add_leaf(lp, ld, rng.uniform(0.72, 1.15) * (1.05 - 0.28 * t), rng.uniform(-0.55, 0.55))

        parts.append(create_curve_tube(f"Pothos_Vine_{vi}", stem_pts, radius=0.0024, material=mats["plant_stem"], col=col, bevel_res=4))

    bmesh.ops.recalc_face_normals(bm_leaves, faces=bm_leaves.faces)
    lmesh = bpy.data.meshes.new("Pothos_AllLeaves")
    bm_leaves.to_mesh(lmesh)
    bm_leaves.free()
    apply_box_uv(lmesh, scale=8.0)
    lobj = bpy.data.objects.new("Pothos_AllLeaves", lmesh)
    lobj.data.materials.append(mats["plant_leaf_pothos"])
    lobj.data.polygons.foreach_set("use_smooth", [True] * len(lobj.data.polygons))
    col.objects.link(lobj)
    parts.append(lobj)

    _parent_all(parts, root)
    return root



def build_grovemade_desk_shelf(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Grovemade-inspired dark oiled walnut + matte-black steel desktop monitor shelf (1.06m x 0.225m x 0.092m).
    Grounds the desk visually, houses Focusrite Scarlett & cables cleanly underneath,
    and elevates Stream Deck & Qi smartphone cleanly on top!
    """
    dx, dy, _ = desk_origin
    desk_h = 0.750
    root = _new_group("Hero_GrovemadeShelf", (dx + 0.02, dy + 0.12, desk_h), col)
    parts: list[bpy.types.Object] = []

    sw, sd, sh = 1.06, 0.225, 0.092
    # Main chamfered solid oiled walnut top plank
    parts.append(create_beveled_box(
        "DeskShelf_WalnutTop", (sw, sd, 0.018), (0.0, 0.0, sh - 0.009),
        bevel=0.003, segments=3, material=mats["walnut_desk"], uv_scale=0.9, collection=col,
    ))
    # Lower matte-black steel organizer sub-tray suspended in center bay
    parts.append(create_beveled_box(
        "DeskShelf_SubTray", (0.44, 0.175, 0.006), (0.04, 0.01, 0.044),
        bevel=0.0015, material=mats["anodized_black"], collection=col,
    ))
    # Twin folded matte-black steel support legs with cork feet
    for side, lx in (("L", -sw * 0.42), ("R", sw * 0.42)):
        parts.append(create_beveled_box(
            f"DeskShelf_Leg_{side}", (0.016, sd - 0.024, sh - 0.018), (lx, 0.0, (sh - 0.018) * 0.5),
            bevel=0.002, material=mats["anodized_black"], collection=col,
        ))
        parts.append(create_beveled_box(
            f"DeskShelf_Foot_{side}", (0.026, sd - 0.018, 0.006), (lx, 0.0, 0.003),
            bevel=0.0015, material=mats["matte_plastic"], collection=col,
        ))

    _parent_all(parts, root)
    return root



def build_pc_rolling_caddy(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Sleek low-profile matte-black wheeled PC floor stand (elevates tower 4.4cm off wood floor for dust airflow!)."""
    root = _new_group("Hero_PCRollingCaddy", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []
    cw, cd, th = 0.275, 0.505, 0.014
    plat_z = 0.036
    parts.append(create_beveled_box("Caddy_Deck", (cw, cd, th), (0.0, 0.0, plat_z), bevel=0.003, material=mats["anodized_black"], collection=col))
    # Subtle side retaining lip rails
    for sx in (-cw * 0.5 + 0.005, cw * 0.5 - 0.005):
        parts.append(create_beveled_box(f"Caddy_Rail_{sx:+.2f}", (0.008, cd - 0.02, 0.018), (sx, 0.0, plat_z + 0.012), bevel=0.0015, material=mats["gunmetal"], collection=col))
    # 4 low-profile matte caster wheels touching Z = 0
    for wx in (-cw * 0.38, cw * 0.38):
        for wy in (-cd * 0.38, cd * 0.38):
            parts.append(create_beveled_cylinder(
                f"Caddy_Wheel_{wx:+.2f}_{wy:+.2f}", radius=0.014, depth=0.018, vertices=16,
                location=(wx, wy, 0.014), rotation=(0.0, math.radians(90), 0.0),
                bevel=0.002, material=mats["matte_plastic"], collection=col,
            ))
    _parent_all(parts, root)
    return root



def build_architectural_floor_lamp(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Minimalist 1.58m matte-black steel architectural cantilever floor lamp for the West loft window corner
    (proper vertical scale for 2.76m ceilings — replaces awkward tiny floor succulent!).
    """
    root = _new_group("Hero_ArchFloorLamp", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []

    # Heavy matte-black spun-steel circular base
    parts.append(create_beveled_cylinder("Lamp_Base", 0.145, 0.022, 32, 0.004, location=(0.0, 0.0, 0.011), material=mats["anodized_black"], collection=col))
    # Slender vertical stem + gentle forward cantilever neck
    parts.append(create_beveled_cylinder("Lamp_Stem", 0.009, 1.38, 18, 0.001, location=(0.0, 0.0, 0.71), material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_cylinder("Lamp_BrassJoint", 0.014, 0.026, 20, 0.002, location=(0.0, 0.0, 1.40), material=mats["brushed_brass"], collection=col))
    parts.append(create_curve_tube(
        "Lamp_ArmNeck", [(0.0, 0.0, 1.40), (0.0, -0.14, 1.54), (0.0, -0.28, 1.51)],
        radius=0.0075, material=mats["anodized_black"], col=col, bevel_res=5,
    ))
    # Sculpted matte-black spun conical shade (hollow via lathe)
    bm = bmesh.new()
    s_prof = [(0.022, 0.095), (0.028, 0.095), (0.115, -0.045), (0.111, -0.048), (0.024, 0.088)]
    vs = [bm.verts.new((r, 0.0, z)) for r, z in s_prof]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=32, use_merge=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    smesh = bpy.data.meshes.new("Lamp_Shade")
    bm.to_mesh(smesh)
    bm.free()
    apply_box_uv(smesh, scale=6.0)
    sobj = bpy.data.objects.new("Lamp_Shade", smesh)
    sobj.location = (0.0, -0.30, 1.43)
    sobj.rotation_euler = (math.radians(-18.0), 0.0, 0.0)
    sobj.data.materials.append(mats["anodized_black"])
    set_smooth_with_bevel_normals(sobj)
    col.objects.link(sobj)
    parts.append(sobj)
    # Warm glowing recessed diffuser bulb inside shade
    parts.append(create_beveled_cylinder(
        "Lamp_WarmBulb", 0.028, 0.032, 20, 0.012,
        location=(0.0, -0.295, 1.445), rotation=(math.radians(-18.0), 0.0, 0.0),
        material=mats["emissive_cove_warm"], collection=col,
    ))
    _parent_all(parts, root)
    return root



def build_hifi_integrated_amp(
    location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Minimalist matte-black Hi-Fi integrated stereo amplifier for the bottom tier of the curated bookshelf."""
    root = _new_group("Prop_HiFiAmp", location, col)
    parts: list[bpy.types.Object] = []
    # Oriented with front faceplate facing -X (into room!)
    d, w, h = 0.31, 0.42, 0.105
    parts.append(create_beveled_box("Amp_Chassis", (d, w, h), (0.0, 0.0, h * 0.5 + 0.012), bevel=0.003, material=mats["anodized_black"], collection=col))
    for fx in (-0.11, 0.11):
        for fy in (-0.16, 0.16):
            parts.append(create_beveled_cylinder(f"Amp_Foot_{fx:+.2f}_{fy:+.2f}", 0.018, 0.012, 18, location=(fx, fy, 0.006), material=mats["gunmetal"], collection=col))
    # Brushed gunmetal volume & source selector dials on front (-X)
    for ky, kr in ((-0.135, 0.022), (0.135, 0.016), (0.075, 0.013)):
        parts.append(create_beveled_cylinder(
            f"Amp_Dial_{ky:+.2f}", kr, 0.018, 24,
            location=(-d * 0.5 - 0.008, ky, h * 0.5 + 0.012), rotation=(0.0, math.radians(90), 0.0),
            bevel=0.002, material=mats["gunmetal"], collection=col,
        ))
    # Warm amber power LED + center brushed display strip
    parts.append(create_beveled_box("Amp_DisplayGlass", (0.006, 0.11, 0.032), (-d * 0.5 - 0.002, -0.02, h * 0.5 + 0.012), bevel=0.001, material=mats["matte_plastic"], collection=col))
    parts.append(create_beveled_cylinder("Amp_PowerLED", 0.0035, 0.004, 12, location=(-d * 0.5 - 0.003, 0.175, h * 0.5 + 0.012), rotation=(0.0, math.radians(90), 0.0), material=mats["emissive_rgb_amber"], collection=col))
    _parent_all(parts, root)
    return root



def build_leaning_framed_print(
    location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Thin matte-black framed monochrome Bauhaus print leaning casually on the bookshelf against the concrete wall."""
    root = _new_group("Prop_ShelfFramedArt", location, col)
    root.rotation_euler = (0.0, math.radians(-9.0), 0.0)  # leans gently back toward +X concrete wall!
    parts: list[bpy.types.Object] = []
    fw, fh, ft = 0.28, 0.36, 0.016
    # Outer thin frame box (facing -X)
    parts.append(create_beveled_box("Frame_Back", (ft, fw, fh), (0.0, 0.0, fh * 0.5), bevel=0.002, material=mats["anodized_black"], collection=col))
    # Mapped artwork face on -X
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    aw, ah = fw - 0.022, fh - 0.022
    f = bm.faces.new((
        bm.verts.new((-ft * 0.5 - 0.001, -aw * 0.5, 0.011)),
        bm.verts.new((-ft * 0.5 - 0.001, aw * 0.5, 0.011)),
        bm.verts.new((-ft * 0.5 - 0.001, aw * 0.5, 0.011 + ah)),
        bm.verts.new((-ft * 0.5 - 0.001, -aw * 0.5, 0.011 + ah)),
    ))
    f.loops[0][uv].uv = (0.0, 0.0); f.loops[1][uv].uv = (1.0, 0.0); f.loops[2][uv].uv = (1.0, 1.0); f.loops[3][uv].uv = (0.0, 1.0)
    amesh = bpy.data.meshes.new("Frame_ArtCanvas")
    bm.to_mesh(amesh)
    bm.free()
    aobj = bpy.data.objects.new("Frame_ArtCanvas", amesh)
    aobj.data.materials.append(mats["gallery_art"])
    col.objects.link(aobj)
    parts.append(aobj)
    _parent_all(parts, root)
    return root



def build_lived_in_desk_details(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Ergonomically authentic lived-in creator desk details:
    - Open Moleskine notebook with REAL dot-grid architectural wireframe sketch pages + brass pen on LEFT open desk zone
    - Handcrafted dark stoneware espresso mug on walnut coaster safely on RIGHT open zone (away from OLED screen & mouse!)
    - Cognac leather EDC valet tray (eyeglasses, AirPods, SSD) in far-right rear corner
    - Low-profile Qi pad on top of Grovemade shelf + DAC volume knob cleanly tucked under Grovemade shelf
    - All cables cleanly hidden BEHIND the Grovemade desk shelf!
    """
    dx, dy, _ = desk_origin
    desk_h = 0.750
    root = _new_group("Hero_LivedInDeskDetails", (dx, dy, desk_h), col)
    parts: list[bpy.types.Object] = []

    # 1. Open Moleskine Notebook + Brushed-Brass Pen cleanly on pure LEFT walnut zone (10cm clear of wool desk mat!)
    nb = _new_group("Desk_OpenNotebook", (-0.67, -0.22, 0.0048), col, rot_z_deg=-10.0)
    nb_parts: list[bpy.types.Object] = []
    nb_parts.append(create_beveled_box("NB_Cover", (0.236, 0.178, 0.005), (0.0, 0.0, 0.0025), bevel=0.002, material=mats["leather_dark"], collection=col))
    nb_parts.append(create_beveled_box("NB_PagesBaseL", (0.110, 0.168, 0.009), (-0.058, 0.0, 0.0085), rotation=(0.0, math.radians(-2.0), 0.0), bevel=0.002, material=mats["paper_cream"], collection=col))
    nb_parts.append(create_beveled_box("NB_PagesBaseR", (0.110, 0.168, 0.009), (0.058, 0.0, 0.0085), rotation=(0.0, math.radians(2.0), 0.0), bevel=0.002, material=mats["paper_cream"], collection=col))
    # Crisp UV-mapped dot-grid & wireframe sketch top sheets on both open pages!
    for side, sx, tilt_y in (("L", -0.058, -2.0), ("R", 0.058, 2.0)):
        bm_p = bmesh.new()
        uv_p = bm_p.loops.layers.uv.verify()
        pw, pd = 0.106, 0.164
        fp = bm_p.faces.new((
            bm_p.verts.new((-pw * 0.5, -pd * 0.5, 0.0)),
            bm_p.verts.new((pw * 0.5, -pd * 0.5, 0.0)),
            bm_p.verts.new((pw * 0.5, pd * 0.5, 0.0)),
            bm_p.verts.new((-pw * 0.5, pd * 0.5, 0.0)),
        ))
        fp.loops[0][uv_p].uv = (0.0, 0.0); fp.loops[1][uv_p].uv = (1.0, 0.0); fp.loops[2][uv_p].uv = (1.0, 1.0); fp.loops[3][uv_p].uv = (0.0, 1.0)
        pmesh = bpy.data.meshes.new(f"NB_PageArt_{side}")
        bm_p.to_mesh(pmesh)
        bm_p.free()
        pobj = bpy.data.objects.new(f"NB_PageArt_{side}", pmesh)
        pobj.location = (sx, 0.0, 0.0138)
        pobj.rotation_euler = (0.0, math.radians(tilt_y), 0.0)
        pobj.data.materials.append(mats["notebook_page"])
        col.objects.link(pobj)
        nb_parts.append(pobj)

    nb_parts.append(create_beveled_box("NB_Ribbon", (0.006, 0.044, 0.0015), (0.008, -0.108, 0.002), rotation=(0.0, 0.0, math.radians(-16)), bevel=0.0004, material=mats["keycap_accent"], collection=col))
    nb_parts.append(create_beveled_cylinder(
        "NB_BrassPen", radius=0.0046, depth=0.136, vertices=18,
        location=(0.056, -0.010, 0.0195), rotation=(math.radians(90), 0.0, math.radians(-24)),
        bevel=0.0015, material=mats["brushed_brass"], collection=col,
    ))
    _parent_all(nb_parts, nb)
    parts.append(nb)

    # 2. Handcrafted Dark Charcoal Ceramic Espresso Mug on Walnut Coaster — cleanly spaced between desk mat & OP-1 synth!
    mug = _new_group("Desk_DarkCeramicMug", (0.55, -0.22, 0.0), col, rot_z_deg=-42.0)
    m_parts: list[bpy.types.Object] = []
    m_parts.append(create_beveled_cylinder("Mug_WalnutCoaster", 0.048, 0.006, 28, 0.0015, location=(0.0, 0.0, 0.003), material=mats["walnut_desk"], collection=col))
    bm = bmesh.new()
    prof = [(0.0, 0.006), (0.033, 0.006), (0.038, 0.014), (0.039, 0.088), (0.037, 0.092), (0.033, 0.088), (0.031, 0.016), (0.0, 0.016)]
    vs = [bm.verts.new((r, 0.0, z)) for r, z in prof]
    es = [bm.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=32, use_merge=True)
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mmesh = bpy.data.meshes.new("DarkMug_Body")
    bm.to_mesh(mmesh)
    bm.free()
    apply_box_uv(mmesh, scale=8.0)
    mobj = bpy.data.objects.new("DarkMug_Body", mmesh)
    mobj.data.materials.append(mats["ceramic_charcoal"])
    set_smooth_with_bevel_normals(mobj)
    col.objects.link(mobj)
    m_parts.append(mobj)
    m_parts.append(create_curve_tube(
        "DarkMug_Handle", [(0.036, 0.0, 0.074), (0.059, 0.0, 0.068), (0.059, 0.0, 0.032), (0.036, 0.0, 0.026)],
        radius=0.0044, material=mats["ceramic_charcoal"], col=col, bevel_res=5,
    ))
    m_parts.append(create_beveled_cylinder("DarkMug_Coffee", 0.033, 0.004, 24, 0.001, location=(0.0, 0.0, 0.075), material=mats["anodized_black"], collection=col))
    _parent_all(m_parts, mug)
    parts.append(mug)

    # 3. Cognac Leather EDC Valet Catchall Tray tucked cleanly on FAR-RIGHT rear desk wing (ZERO overlap w/ OP-1 Field Synth!)
    tray = _new_group("Desk_LeatherEDCTray", (1.03, -0.02, 0.0), col, rot_z_deg=-6.0)
    t_parts: list[bpy.types.Object] = []
    t_parts.append(create_beveled_box("Tray_Base", (0.175, 0.125, 0.006), (0.0, 0.0, 0.003), bevel=0.002, material=mats["leather_cognac"], collection=col))
    for rx, ry, sx, sy in ((0.0, 0.060, 0.175, 0.008), (0.0, -0.060, 0.175, 0.008), (-0.084, 0.0, 0.008, 0.125), (0.084, 0.0, 0.008, 0.125)):
        t_parts.append(create_beveled_box(f"Tray_Rim_{rx:+.2f}_{ry:+.2f}", (sx, sy, 0.020), (rx, ry, 0.012), bevel=0.003, material=mats["leather_cognac"], collection=col))
    t_parts.append(create_beveled_box("EDC_AirPods", (0.056, 0.044, 0.020), (-0.038, 0.014, 0.016), rotation=(0.0, 0.0, math.radians(18)), bevel=0.008, segments=3, material=mats["white_matte"], collection=col))
    t_parts.append(create_beveled_box("EDC_PortableSSD", (0.072, 0.040, 0.009), (0.028, 0.018, 0.0105), rotation=(0.0, 0.0, math.radians(-12)), bevel=0.003, material=mats["gunmetal"], collection=col))
    for gx in (-0.024, 0.024):
        t_parts.append(create_beveled_cylinder(f"EDC_GlassRim_{gx:+.2f}", 0.019, 0.004, 24, location=(gx, -0.024, 0.010), bevel=0.001, material=mats["anodized_black"], collection=col))
    t_parts.append(create_beveled_box("EDC_GlassBridge", (0.016, 0.004, 0.004), (0.0, -0.024, 0.010), bevel=0.001, material=mats["anodized_black"], collection=col))
    t_parts.append(create_beveled_box("EDC_GlassTemple", (0.092, 0.004, 0.004), (0.0, -0.036, 0.012), rotation=(0.0, 0.0, math.radians(6)), bevel=0.001, material=mats["anodized_black"], collection=col))
    _parent_all(t_parts, tray)
    parts.append(tray)

    # 4. Low-Profile Matte-Black Puck Qi Charger on TOP of Grovemade Desk Shelf (Z = 0.092) + DAC knob tucked cleanly UNDER left bay!
    parts.append(create_beveled_cylinder("Desk_QiPad", 0.040, 0.007, 28, location=(0.24, 0.11, 0.0955), bevel=0.0025, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_cylinder("Desk_VolumeDACBase", 0.025, 0.018, 28, location=(-0.15, 0.10, 0.009), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_cylinder("Desk_VolumeDACKnob", 0.018, 0.020, 28, location=(-0.15, 0.10, 0.024), bevel=0.003, material=mats["gunmetal"], collection=col))

    # 5. Clean Hidden Rear Cables routing BEHIND the Grovemade shelf into the rear grommet (zero stray front wires!)
    parts.append(create_curve_tube(
        "Desk_Cable_ScarlettUSB",
        [(-0.32, 0.18, 0.012), (-0.28, 0.28, 0.007), (-0.08, 0.35, 0.006)],
        radius=0.0026, material=mats["matte_plastic"], col=col, bevel_res=4,
    ))

    _parent_all(parts, root)
    return root



def build_cozy_reading_nook_details(
    table_location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Round dark oiled walnut & matte-black tripod side table placed cleanly at arm's reach beside the
    inward-facing reading chair, topped with 2 real hardcover UV-mapped architecture monographs
    (with recessed cream page blocks) & a sculpted stoneware pour-over coffee cup on ceramic saucer + brass spoon.
    """
    root = _new_group("Hero_ReadingNookCozy", (0.0, 0.0, 0.0), col)
    parts: list[bpy.types.Object] = []

    tx, ty, _ = table_location
    top_z = 0.481
    parts.append(create_beveled_cylinder("SideTable_Top", 0.24, 0.022, 48, 0.004, location=(tx, ty, 0.470), material=mats["walnut_desk"], collection=col))
    parts.append(create_beveled_cylinder("SideTable_UnderCollar", 0.135, 0.010, 32, 0.002, location=(tx, ty, 0.456), material=mats["anodized_black"], collection=col))
    for i in range(3):
        a = math.radians(i * 120.0 + 25.0)
        parts.append(create_curve_tube(
            f"SideTable_Leg_{i}",
            [(tx + math.cos(a) * 0.115, ty + math.sin(a) * 0.115, 0.456), (tx + math.cos(a) * 0.175, ty + math.sin(a) * 0.175, 0.006)],
            radius=0.0095, material=mats["anodized_black"], col=col, bevel_res=6,
        ))
        # Brushed brass foot ferrules for luxury editorial touch
        parts.append(create_beveled_cylinder(
            f"SideTable_BrassFoot_{i}", 0.0102, 0.028, 18, 0.002,
            location=(tx + math.cos(a) * 0.174, ty + math.sin(a) * 0.174, 0.014),
            material=mats["brushed_brass"], collection=col,
        ))

    # 2 Real Hardcover Architecture Monographs with printed covers & recessed cream page blocks (zero plain blocks!)
    cur_z = top_z
    for bi, (bw, bd, bh, yaw, cover_mat, spine_idx) in enumerate((
        (0.215, 0.158, 0.022, 20.0, mats["vinyl_cover_1"], 6),
        (0.188, 0.140, 0.018, 8.0, mats["vinyl_cover_4"], 3),
    )):
        bg = _new_group(f"SideTable_Monograph_{bi}", (tx - 0.052 + bi * 0.006, ty + 0.040 - bi * 0.006, cur_z), col, rot_z_deg=yaw)
        b_parts: list[bpy.types.Object] = []
        # Bottom & top hardcover boards overhanging slightly past cream pages
        b_parts.append(create_beveled_box(f"STBook_{bi}_BotBoard", (bw, bd, 0.0028), (0.0, 0.0, 0.0014), bevel=0.0008, material=cover_mat, collection=col))
        b_parts.append(create_beveled_box(f"STBook_{bi}_TopBoard", (bw, bd, 0.0028), (0.0, 0.0, bh - 0.0014), bevel=0.0008, material=cover_mat, collection=col))
        # Rounded spine cap on -X edge
        b_parts.append(create_beveled_box(f"STBook_{bi}_Spine", (0.005, bd, bh), (-bw * 0.5 + 0.0025, 0.0, bh * 0.5), bevel=0.0018, material=cover_mat, collection=col))
        # Recessed cream page block inside boards
        b_parts.append(create_beveled_box(f"STBook_{bi}_Pages", (bw - 0.009, bd - 0.008, bh - 0.0054), (0.002, 0.0, bh * 0.5), bevel=0.0006, material=mats["paper_cream"], collection=col))
        # Subtle editorial cover typographic graphic plate on top hardcover
        b_parts.append(create_beveled_box(f"STBook_{bi}_CoverPlate", (bw * 0.56, bd * 0.52, 0.0008), (0.014, 0.0, bh + 0.0003), bevel=0.0002, material=mats["wall_art_rams"] if bi == 1 else mats["gallery_art"], collection=col))
        _parent_all(b_parts, bg)
        parts.append(bg)
        cur_z += bh

    # Sculpted Stoneware Pour-Over Coffee Cup + Curved Handle + Ceramic Saucer + Dark Coffee + Brass Spoon!
    cup_g = _new_group("SideTable_EspressoSet", (tx + 0.112, ty - 0.086, top_z), col, rot_z_deg=38.0)
    c_parts: list[bpy.types.Object] = []
    # Turned ceramic saucer with gently raised rim
    bm_s = bmesh.new()
    s_prof = [(0.0, 0.0), (0.036, 0.0), (0.062, 0.009), (0.064, 0.012), (0.060, 0.013), (0.034, 0.005), (0.0, 0.005)]
    vs = [bm_s.verts.new((r, 0.0, z)) for r, z in s_prof]
    es = [bm_s.edges.new((vs[i], vs[i + 1])) for i in range(len(vs) - 1)]
    bmesh.ops.spin(bm_s, geom=vs + es, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=36, use_merge=True)
    bmesh.ops.recalc_face_normals(bm_s, faces=bm_s.faces)
    smesh = bpy.data.meshes.new("SideTable_Saucer"); bm_s.to_mesh(smesh); bm_s.free()
    apply_box_uv(smesh, scale=8.0)
    sobj = bpy.data.objects.new("SideTable_Saucer", smesh)
    sobj.data.materials.append(mats["ceramic_charcoal"])
    set_smooth_with_bevel_normals(sobj)
    col.objects.link(sobj)
    c_parts.append(sobj)

    # Lathe-spun flared ceramic espresso/pour-over cup resting inside saucer well (z=0.005)
    bm_c = bmesh.new()
    c_prof = [(0.0, 0.005), (0.024, 0.005), (0.030, 0.016), (0.037, 0.068), (0.035, 0.071), (0.032, 0.067), (0.026, 0.015), (0.0, 0.015)]
    vc = [bm_c.verts.new((r, 0.0, z)) for r, z in c_prof]
    ec = [bm_c.edges.new((vc[i], vc[i + 1])) for i in range(len(vc) - 1)]
    bmesh.ops.spin(bm_c, geom=vc + ec, cent=(0, 0, 0), axis=(0, 0, 1), angle=2 * math.pi, steps=36, use_merge=True)
    bmesh.ops.recalc_face_normals(bm_c, faces=bm_c.faces)
    cmesh = bpy.data.meshes.new("SideTable_CupBody"); bm_c.to_mesh(cmesh); bm_c.free()
    apply_box_uv(cmesh, scale=8.0)
    cobj = bpy.data.objects.new("SideTable_CupBody", cmesh)
    cobj.data.materials.append(mats["ceramic_charcoal"])
    set_smooth_with_bevel_normals(cobj)
    col.objects.link(cobj)
    c_parts.append(cobj)

    # Curved stoneware cup handle + glossy dark coffee meniscus + brushed brass teaspoon on saucer rim!
    c_parts.append(create_curve_tube(
        "SideTable_CupHandle",
        [(0.034, 0.0, 0.058), (0.053, 0.0, 0.053), (0.053, 0.0, 0.026), (0.029, 0.0, 0.021)],
        radius=0.0038, material=mats["ceramic_charcoal"], col=col, bevel_res=5,
    ))
    c_parts.append(create_beveled_cylinder(
        "SideTable_CoffeeSurface", 0.031, 0.003, 24, 0.001,
        location=(0.0, 0.0, 0.058), material=mats["anodized_black"], collection=col,
    ))
    c_parts.append(create_beveled_box(
        "SideTable_BrassSpoonStem", (0.092, 0.0045, 0.0022), (-0.014, 0.044, 0.0115),
        rotation=(0.0, 0.0, math.radians(-18.0)), bevel=0.0008, material=mats["brushed_brass"], collection=col,
    ))
    c_parts.append(create_beveled_cylinder(
        "SideTable_BrassSpoonBowl", 0.010, 0.0028, 16, 0.001,
        location=(0.031, 0.030, 0.0115), material=mats["brushed_brass"], collection=col,
    ))
    _parent_all(c_parts, cup_g)
    parts.append(cup_g)

    _parent_all(parts, root)
    return root



def build_venetian_blinds(
    x_pos: float,
    y0: float,
    y1: float,
    z_bot: float,
    z_top: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
    slat_tilt_deg: float = 22.0,
) -> bpy.types.Object:
    """
    Matte-black architectural aluminum Venetian window blinds across the upper ~34% of the West loft window.
    Casts authentic horizontal sunlight shadow stripes in Golden/Daylight moods (MengTo signature!)
    while leaving the lower 66% of the Tokyo skyline completely unobstructed!
    Batched into 1 clean slat mesh + headrail/bottom rail + slim vertical ladder cords (= minimal draw calls!).
    """
    cy = (y0 + y1) * 0.5
    span_y = (y1 - y0) - 0.06
    root = _new_group("Arch_VenetianBlinds", (x_pos, cy, 0.0), col)
    parts: list[bpy.types.Object] = []

    # Top headrail cassette & weighted bottom slat rail
    parts.append(create_beveled_box("Blinds_Headrail", (0.044, span_y, 0.036), (0.0, 0.0, z_top - 0.018), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("Blinds_BottomRail", (0.032, span_y, 0.014), (0.0, 0.0, z_bot), bevel=0.002, material=mats["anodized_black"], collection=col))

    # Batched horizontal slats (single mesh = 1 draw call!)
    slat_pitch = 0.036
    slat_w = 0.028
    slat_t = 0.0018
    tilt = math.radians(slat_tilt_deg)
    ct, st = math.cos(tilt), math.sin(tilt)
    bm = bmesh.new()
    z_cur = z_bot + 0.028
    while z_cur < z_top - 0.042:
        res = bmesh.ops.create_cube(bm, size=1.0)
        for v in res["verts"]:
            lx = v.co.x * slat_w
            ly = v.co.y * span_y
            lz = v.co.z * slat_t
            # Tilt around Y so sunlight passing from -X to +X is sliced into crisp horizontal architectural bars!
            rx = lx * ct + lz * st
            rz = -lx * st + lz * ct
            v.co = Vector((rx, ly, z_cur + rz))
        z_cur += slat_pitch
    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    smesh = bpy.data.meshes.new("Blinds_SlatsBatched")
    bm.to_mesh(smesh)
    bm.free()
    apply_box_uv(smesh, scale=4.0)
    sobj = bpy.data.objects.new("Blinds_SlatsBatched", smesh)
    sobj.data.materials.append(mats["anodized_black"])
    col.objects.link(sobj)
    parts.append(sobj)

    # 4 Slim vertical black ladder cords + tilt wand on South edge
    h_drop = (z_top - 0.030) - z_bot
    z_mid = (z_top - 0.030 + z_bot) * 0.5
    for frac in (-0.38, -0.13, 0.13, 0.38):
        cy_cord = frac * span_y
        parts.append(create_beveled_cylinder(
            f"Blinds_Cord_{frac:+.2f}", radius=0.0016, depth=h_drop, vertices=8, bevel=0.0,
            location=(0.0, cy_cord, z_mid), material=mats["matte_plastic"], collection=col,
        ))
    # Matte black tilt wand hanging slightly below bottom rail on North edge
    parts.append(create_beveled_cylinder(
        "Blinds_TiltWand", radius=0.0038, depth=0.68, vertices=12, bevel=0.001,
        location=(0.022, span_y * 0.45, z_top - 0.38), material=mats["anodized_black"], collection=col,
    ))

    _parent_all(parts, root)
    return root



def build_teardown_framed_art(
    location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Grid Studio-style Game Boy DMG-01 Hardware Teardown Frame leaning back 9° on Bookshelf Tier 4."""
    root = _new_group("Prop_TeardownFrame", location, col)
    root.rotation_euler = (0.0, math.radians(-9.0), 0.0)
    parts: list[bpy.types.Object] = []
    fw, fh, ft = 0.30, 0.39, 0.018
    parts.append(create_beveled_box("Teardown_FrameBody", (ft, fw, fh), (0.0, 0.0, fh * 0.5), bevel=0.0025, material=mats["anodized_black"], collection=col))
    # Inset UV-mapped hardware teardown canvas facing -X (+Y is LEFT u=0, -Y is RIGHT u=1!)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    aw, ah = fw - 0.020, fh - 0.020
    f = bm.faces.new((
        bm.verts.new((-ft * 0.5 - 0.0012, aw * 0.5, 0.010)),
        bm.verts.new((-ft * 0.5 - 0.0012, -aw * 0.5, 0.010)),
        bm.verts.new((-ft * 0.5 - 0.0012, -aw * 0.5, 0.010 + ah)),
        bm.verts.new((-ft * 0.5 - 0.0012, aw * 0.5, 0.010 + ah)),
    ))
    f.loops[0][uv].uv = (0.0, 0.0); f.loops[1][uv].uv = (1.0, 0.0); f.loops[2][uv].uv = (1.0, 1.0); f.loops[3][uv].uv = (0.0, 1.0)
    amesh = bpy.data.meshes.new("Teardown_BlueprintCanvas")
    bm.to_mesh(amesh)
    bm.free()
    aobj = bpy.data.objects.new("Teardown_BlueprintCanvas", amesh)
    aobj.data.materials.append(mats["teardown_art"])
    col.objects.link(aobj)
    parts.append(aobj)
    _parent_all(parts, root)
    return root



def build_vinyl_display_easel(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
    cover_index: int = 0,
) -> bpy.types.Object:
    """
    Minimalist walnut & brushed-brass 'Now Playing' LP vinyl sleeve easel displaying iconic front-facing
    City-Pop / Synthwave vinyl jacket art (31.5cm x 31.5cm, zero blank pastel blocks!).
    Local orientation: Artwork faces -X (into room!).
    """
    root = _new_group(f"Prop_VinylDisplay_{cover_index}", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []

    # Grooved dark walnut easel base + brushed brass rear leaning pin
    parts.append(create_beveled_box("VinylEasel_Base", (0.068, 0.22, 0.018), (0.0, 0.0, 0.009), bevel=0.003, material=mats["walnut_desk"], collection=col))
    parts.append(create_beveled_cylinder(
        "VinylEasel_BrassLip", radius=0.004, depth=0.20, vertices=14, bevel=0.001,
        location=(-0.026, 0.0, 0.020), rotation=(math.radians(90), 0.0, 0.0),
        material=mats["brushed_brass"], collection=col,
    ))

    # 31.5cm x 31.5cm cardboard vinyl jacket leaning gently back 11° inside groove
    jacket = _new_group(f"VinylJacket_Tilt_{cover_index}", (0.006, 0.0, 0.016), col)
    jacket.rotation_euler = (0.0, math.radians(-11.0), 0.0)
    j_size, j_t = 0.312, 0.007
    j_body = create_beveled_box(f"VinylJacket_Body_{cover_index}", (j_t, j_size, j_size), (0.0, 0.0, j_size * 0.5), bevel=0.0012, material=mats["vinyl_cover_1"], collection=col)
    j_body.parent = jacket

    # Front-facing high-res UV-mapped sleeve art on -X face (+Y is LEFT u0, -Y is RIGHT u1 -> Obi strip on LEFT!)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    u0 = 0.0 if cover_index == 0 else 0.5
    u1 = 0.5 if cover_index == 0 else 1.0
    f = bm.faces.new((
        bm.verts.new((-j_t * 0.5 - 0.0008, j_size * 0.5 - 0.002, 0.002)),
        bm.verts.new((-j_t * 0.5 - 0.0008, -j_size * 0.5 + 0.002, 0.002)),
        bm.verts.new((-j_t * 0.5 - 0.0008, -j_size * 0.5 + 0.002, j_size - 0.002)),
        bm.verts.new((-j_t * 0.5 - 0.0008, j_size * 0.5 - 0.002, j_size - 0.002)),
    ))
    f.loops[0][uv].uv = (u0, 0.0); f.loops[1][uv].uv = (u1, 0.0); f.loops[2][uv].uv = (u1, 1.0); f.loops[3][uv].uv = (u0, 1.0)
    jmesh = bpy.data.meshes.new(f"VinylJacket_Art_{cover_index}")
    bm.to_mesh(jmesh)
    bm.free()
    jobj = bpy.data.objects.new(f"VinylJacket_Art_{cover_index}", jmesh)
    jobj.data.materials.append(mats["vinyl_cover_art"])
    col.objects.link(jobj)
    jobj.parent = jacket
    parts.append(jacket)

    _parent_all(parts, root)
    return root



def build_pixel_matrix_clock(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """LaMetric / Divoom matte-black pixel LED matrix clock facing -X by default (rotate rot_z_deg as needed)."""
    root = _new_group("Prop_PixelMatrixClock", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []
    cd, cw, ch = 0.044, 0.205, 0.060
    parts.append(create_beveled_box("PixelClock_Body", (cd, cw, ch), (0.0, 0.0, ch * 0.5), bevel=0.005, segments=3, material=mats["anodized_black"], collection=col))
    # Recessed top action buttons
    for by in (-0.048, 0.0, 0.048):
        parts.append(create_beveled_box(f"PixelClock_Btn_{by:+.2f}", (0.012, 0.018, 0.003), (0.0, by, ch + 0.001), bevel=0.0008, material=mats["gunmetal"], collection=col))
    # Glowing LED Matrix front face on -X (+Y is LEFT u=0, -Y is RIGHT u=1 -> reads '00:24' cleanly!)
    bm = bmesh.new()
    uv = bm.loops.layers.uv.verify()
    sw, sh = cw - 0.016, ch - 0.014
    f = bm.faces.new((
        bm.verts.new((-cd * 0.5 - 0.0008, sw * 0.5, 0.007)),
        bm.verts.new((-cd * 0.5 - 0.0008, -sw * 0.5, 0.007)),
        bm.verts.new((-cd * 0.5 - 0.0008, -sw * 0.5, 0.007 + sh)),
        bm.verts.new((-cd * 0.5 - 0.0008, sw * 0.5, 0.007 + sh)),
    ))
    f.loops[0][uv].uv = (0.0, 0.0); f.loops[1][uv].uv = (1.0, 0.0); f.loops[2][uv].uv = (1.0, 1.0); f.loops[3][uv].uv = (0.0, 1.0)
    cmesh = bpy.data.meshes.new("PixelClock_LEDMatrix")
    bm.to_mesh(cmesh)
    bm.free()
    cobj = bpy.data.objects.new("PixelClock_LEDMatrix", cmesh)
    cobj.data.materials.append(mats["screen_pixel_clock"])
    col.objects.link(cobj)
    parts.append(cobj)
    _parent_all(parts, root)
    return root



def build_uv_geek_book(
    name: str,
    size: tuple[float, float, float],
    location: tuple[float, float, float],
    spine_idx: int,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    horizontal: bool = False,
) -> bpy.types.Object:
    """
    Create a crisp hardcover geek/design book or vinyl LP sleeve mapped to column `spine_idx` (0..15)
    of `geek_book_spines.png` so EVERY spine has authentic editorial typography, bands & color coding!
    `size = (depth_x, thick_y, height_z)` for upright books (spine on -X), or `(depth_x, width_y, thick_z)` for horizontal.
    """
    sx, sy, sz = size
    u0 = (spine_idx % 16) / 16.0 + 0.002
    u1 = ((spine_idx % 16) + 1) / 16.0 - 0.002

    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=min(0.0014, min(sx, sy, sz) * 0.25), segments=2, affect="EDGES", clamp_overlap=True)
    uv_layer = bm.loops.layers.uv.verify()

    for face in bm.faces:
        n = face.normal
        # Map spine & covers cleanly into the chosen book's atlas strip [u0..u1],
        # and assign cream paper edge material (slot 1) to open page faces (+X or +Y)!
        is_pages = (not horizontal and n.x > 0.72) or (horizontal and n.y > 0.72)
        face.material_index = 1 if is_pages else 0
        for loop in face.loops:
            co = loop.vert.co
            if not horizontal:
                if abs(n.x) >= abs(n.y) and abs(n.x) >= abs(n.z):
                    # Spine (-X) or back (+X): map Y across [u0..u1], Z across [0..1]
                    t_u = (co.y / max(sy, 1e-4)) + 0.5
                    t_v = (co.z / max(sz, 1e-4)) + 0.5
                else:
                    # Front/back cover: sample solid cover tone inside [u0..u1] near spine edge
                    t_u = 0.08 + 0.84 * ((co.x / max(sx, 1e-4)) + 0.5)
                    t_v = (co.z / max(sz, 1e-4)) + 0.5
            else:
                if n.x < -0.5:
                    # Horizontal book spine facing -X: map Z thickness across [u0..u1], Y length across [0..1]
                    t_u = (co.z / max(sz, 1e-4)) + 0.5
                    t_v = (co.y / max(sy, 1e-4)) + 0.5
                else:
                    # Top/bottom cover: clean editorial color band
                    t_u = 0.10 + 0.80 * ((co.x / max(sx, 1e-4)) + 0.5)
                    t_v = (co.y / max(sy, 1e-4)) + 0.5
            loop[uv_layer].uv = (u0 + max(0.0, min(1.0, t_u)) * (u1 - u0), max(0.0, min(1.0, t_v)))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    obj.data.materials.append(mats["geek_books_atlas"])
    obj.data.materials.append(mats["paper_cream"])
    set_smooth_with_bevel_normals(obj)
    col.objects.link(obj)
    return obj


def build_organizer_pens_and_tools(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Fill our real 3-cup wire-mesh & walnut desk/shelf organizer (BK_PenOrganizer) with realistic
    angled pens, markers, brushed-brass fountain pen, Apple Pencil, and steel drafting ruler!
    """
    root = _new_group("Prop_OrganizerTools", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []
    # Cup local X offsets matching BK_PenOrganizer (scaled ~0.26m wide -> cup centers at -0.084, 0.0, +0.084)
    tool_specs = [
        # (name, x, y, z_center, radius, length, rx_deg, ry_deg, mat_key)
        ("Tool_BrassPen", -0.095, -0.008, 0.088, 0.0048, 0.145, 8.0, -14.0, "brushed_brass"),
        ("Tool_BlackPen", -0.076, 0.010, 0.084, 0.0044, 0.140, -10.0, 12.0, "anodized_black"),
        ("Tool_OrangeMarker", -0.084, -0.014, 0.082, 0.0062, 0.132, 12.0, 6.0, "keycap_accent"),
        ("Tool_WhiteStylus", -0.014, 0.008, 0.094, 0.0045, 0.162, -9.0, -11.0, "white_matte"),
        ("Tool_GunmetalPen", 0.010, -0.010, 0.086, 0.0048, 0.144, 11.0, 13.0, "gunmetal"),
        ("Tool_FineLiner", 0.002, 0.014, 0.080, 0.0038, 0.136, -12.0, 4.0, "anodized_black"),
        ("Tool_PrecisionDriver", 0.076, -0.006, 0.092, 0.0052, 0.155, 7.0, -12.0, "chrome"),
        ("Tool_ThickMarker", 0.094, 0.008, 0.080, 0.0072, 0.132, -8.0, 14.0, "matte_plastic"),
    ]
    for tname, tx, ty, tz, rad, ln, rx, ry, mk in tool_specs:
        parts.append(create_beveled_cylinder(
            tname, radius=rad, depth=ln, vertices=14, bevel=0.0012,
            location=(tx, ty, tz), rotation=(math.radians(rx), math.radians(ry), 0.0),
            material=mats[mk], collection=col,
        ))
    # Brushed steel 15cm drafting ruler leaning cleanly in right cup
    parts.append(create_beveled_box(
        "Tool_SteelRuler", (0.022, 0.0024, 0.168), (0.084, -0.012, 0.096),
        rotation=(math.radians(10.0), math.radians(-8.0), math.radians(18.0)),
        bevel=0.0005, material=mats["chrome"], collection=col,
    ))
    _parent_all(parts, root)
    return root



def build_back_wall_floating_shelf_and_slats(
    wall_y: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Upgrades the empty upper concrete back wall into an Architectural-Digest Geek Studio feature wall:
    1. Left vertical dark oiled American walnut acoustic slat panel (X = -2.14..-1.10, Z = 0.05..2.74) on dark felt!
    2. Floating solid oiled American walnut wall shelf (W=1.58m, Z=1.88m) with recessed 2700K under-shelf LED wash!
    3. Curated geek shelf accents: framed Dieter Rams / Braun industrial print, leaning Swiss vinyl art,
       mini matte-charcoal trailing plant, 4 titled pocket tech books, and clean central stage for Retro Robot & Rubik's Cube!
    """
    import random

    root = _new_group("Hero_BackWallArchitectural", (0.0, wall_y, 0.0), col)
    parts: list[bpy.types.Object] = []

    # 1. Left Feature Vertical Walnut Acoustic Slat Panel (Concept C warmth fused with Concept A concrete!)
    slat_x0, slat_x1 = -2.15, -1.10
    slat_w = slat_x1 - slat_x0
    slat_cx = (slat_x0 + slat_x1) * 0.5
    slat_h = 2.68
    parts.append(create_beveled_box(
        "WallSlats_FeltBack", (slat_w, 0.010, slat_h), (slat_cx, -0.006, 0.06 + slat_h * 0.5),
        bevel=0.001, material=mats["acoustic_felt"], collection=col,
    ))
    num_slats = 17
    pitch = slat_w / num_slats
    bm_slats = bmesh.new()
    for i in range(num_slats):
        sx = slat_x0 + (i + 0.5) * pitch
        res = bmesh.ops.create_cube(bm_slats, size=1.0)
        for v in res["verts"]:
            v.co = Vector((v.co.x * 0.034 + sx, v.co.y * 0.022 - 0.020, v.co.z * slat_h + 0.06 + slat_h * 0.5))
    bmesh.ops.bevel(bm_slats, geom=list(bm_slats.edges), offset=0.0025, segments=2, affect="EDGES", clamp_overlap=True)
    bmesh.ops.recalc_face_normals(bm_slats, faces=bm_slats.faces)
    smesh = bpy.data.meshes.new("WallSlats_WalnutBatched")
    bm_slats.to_mesh(smesh)
    bm_slats.free()
    apply_box_uv(smesh, scale=0.8)
    sobj = bpy.data.objects.new("WallSlats_WalnutBatched", smesh)
    sobj.data.materials.append(mats["walnut_slat"])
    set_smooth_with_bevel_normals(sobj)
    col.objects.link(sobj)
    parts.append(sobj)

    # 2. 3D Modular Hexagonal Honeycomb Neon Light Wall (Nanoleaf Hexagons / Govee Glide Hexa Pro style!)
    #    15 edge-connected pointy-top interlocking hexagons spanning X=-0.83..+0.64, Z=1.69..2.42 above dual monitors!
    #    Batched into 5 ultra-clean low-poly meshes (~2,000 tris total) with dual-zone RGB-syncable neon rings + frosted opal accents!
    hex_r = 0.108
    hex_gap = 0.010
    pitch_x = math.sqrt(3.0) * hex_r + hex_gap          # ~0.197m
    pitch_z = 1.5 * hex_r + hex_gap * (math.sqrt(3.0) * 0.5)  # ~0.171m
    origin_x, origin_z = -0.14, 1.97

    # 15 edge-connected organic honeycomb tiles (q, r) with dynamic negative-space cutouts:
    # Mode: 'soft' = luminous frosted opal hex diffuser + neon rim; 'core' = recessed obsidian acoustic hex core + bold neon rim!
    hex_layout: list[tuple[int, int, str]] = [
        (-2, -1, "core"), (-1, -1, "soft"), (0, -1, "core"), (2, -1, "core"),
        (-3,  0, "core"), (-1,  0, "core"), (0,  0, "soft"), (1,  0, "core"), (2,  0, "core"), (3,  0, "soft"),
        (-2,  1, "core"), ( 0,  1, "soft"), (1,  1, "core"), (3,  1, "core"),
        ( 0,  2, "core"),
    ]
    hex_centers = [
        (q, r, mode, origin_x + (q + 0.5 * r) * pitch_x, origin_z + r * pitch_z)
        for (q, r, mode) in hex_layout
    ]

    def _hex_pts(cx: float, cz: float, radius: float) -> list[tuple[float, float]]:
        # Pointy-top regular hexagon (vertex 0 at top +Z)
        return [
            (cx + radius * math.cos(math.pi * 0.5 + k * math.pi / 3.0),
             cz + radius * math.sin(math.pi * 0.5 + k * math.pi / 3.0))
            for k in range(6)
        ]

    def _add_hex_prism(bm: bmesh.types.BMesh, cx: float, cz: float, radius: float, y_back: float, y_front: float) -> None:
        pts = _hex_pts(cx, cz, radius)
        vb = [bm.verts.new((px, y_back, pz)) for (px, pz) in pts]
        vf = [bm.verts.new((px, y_front, pz)) for (px, pz) in pts]
        bm.faces.new(vf)
        bm.faces.new(list(reversed(vb)))
        for k in range(6):
            kn = (k + 1) % 6
            bm.faces.new((vb[k], vb[kn], vf[kn], vf[k]))

    def _add_hex_ring(
        bm: bmesh.types.BMesh, cx: float, cz: float,
        r_out: float, r_in: float, y_back: float, y_front: float,
    ) -> None:
        po = _hex_pts(cx, cz, r_out)
        pi = _hex_pts(cx, cz, r_in)
        ob = [bm.verts.new((px, y_back, pz)) for (px, pz) in po]
        of = [bm.verts.new((px, y_front, pz)) for (px, pz) in po]
        ib = [bm.verts.new((px, y_back, pz)) for (px, pz) in pi]
        if_ = [bm.verts.new((px, y_front, pz)) for (px, pz) in pi]
        for k in range(6):
            kn = (k + 1) % 6
            bm.faces.new((of[k], of[kn], if_[kn], if_[k]))
            bm.faces.new((ob[kn], ob[k], ib[k], ib[kn]))
            bm.faces.new((ob[k], ob[kn], of[kn], of[k]))
            bm.faces.new((if_[k], if_[kn], ib[kn], ib[k]))

    bm_chassis = bmesh.new()
    bm_core = bmesh.new()
    bm_ring_pri = bmesh.new()
    bm_ring_sec = bmesh.new()
    bm_soft = bmesh.new()

    for (q, r, mode, cx, cz) in hex_centers:
        # 3D beveled dark anodized housing mounted flush against dark charcoal concrete wall
        _add_hex_prism(bm_chassis, cx, cz, hex_r - 0.002, y_back=-0.001, y_front=-0.017)

        # Dual-tone horizontal gradient split: left/center-left -> Primary neon (cyan), right wing -> Secondary neon (coral-amber)
        ring_bm = bm_ring_pri if cx < 0.04 else bm_ring_sec
        # Bold 3D glowing neon perimeter light tube proud of chassis front
        _add_hex_ring(ring_bm, cx, cz, r_out=hex_r, r_in=hex_r - 0.014, y_back=-0.014, y_front=-0.0245)
        # Subtle backlit rear halo diffuser rim kissing the dark concrete wall
        _add_hex_ring(ring_bm, cx, cz, r_out=hex_r - 0.004, r_in=hex_r - 0.012, y_back=-0.0005, y_front=-0.005)

        if mode == "soft":
            # Softly glowing frosted opal hexagonal diffuser face (Nanoleaf accent tile!)
            _add_hex_prism(bm_soft, cx, cz, hex_r - 0.015, y_back=-0.015, y_front=-0.0225)
        else:
            # Recessed obsidian matte acoustic hex core (Govee Glide Hexa Pro contrast depth!)
            _add_hex_prism(bm_core, cx, cz, hex_r - 0.015, y_back=-0.015, y_front=-0.0192)

    # Inter-tile matte-black snap connector bridges linking every touching hex edge
    for i in range(len(hex_centers)):
        _, _, _, x1, z1 = hex_centers[i]
        for j in range(i + 1, len(hex_centers)):
            _, _, _, x2, z2 = hex_centers[j]
            dx_c, dz_c = x2 - x1, z2 - z1
            dist = math.hypot(dx_c, dz_c)
            if 0.14 < dist < pitch_x * 1.15:
                mx, mz = (x1 + x2) * 0.5, (z1 + z2) * 0.5
                ux, uz = dx_c / dist, dz_c / dist
                px_n, pz_n = -uz, ux
                hw, hl = 0.013, 0.014
                b_pts = [
                    (mx - ux * hl - px_n * hw, mz - uz * hl - pz_n * hw),
                    (mx + ux * hl - px_n * hw, mz + uz * hl - pz_n * hw),
                    (mx + ux * hl + px_n * hw, mz + uz * hl + pz_n * hw),
                    (mx - ux * hl + px_n * hw, mz - uz * hl + pz_n * hw),
                ]
                vb = [bm_chassis.verts.new((bx, -0.003, bz)) for (bx, bz) in b_pts]
                vf = [bm_chassis.verts.new((bx, -0.014, bz)) for (bx, bz) in b_pts]
                bm_chassis.faces.new(vf)
                bm_chassis.faces.new(list(reversed(vb)))
                for k in range(4):
                    kn = (k + 1) % 4
                    bm_chassis.faces.new((vb[k], vb[kn], vf[kn], vf[k]))

    hex_root = _new_group("Hero_HexNeonWall", (0.0, 0.0, 0.0), col)
    hex_parts: list[bpy.types.Object] = []
    for hname, hbm, hmat, bevel_w in (
        ("HexNeon_Chassis", bm_chassis, mats["anodized_black"], 0.0014),
        ("HexNeon_Core", bm_core, mats["hex_core_obsidian"], 0.0012),
        ("HexNeon_RingPrimary", bm_ring_pri, mats["emissive_hex_primary"], 0.0015),
        ("HexNeon_RingSecondary", bm_ring_sec, mats["emissive_hex_secondary"], 0.0015),
        ("HexNeon_SoftFaces", bm_soft, mats["emissive_hex_soft"], 0.0015),
    ):
        bmesh.ops.recalc_face_normals(hbm, faces=hbm.faces)
        if bevel_w > 0.0:
            bmesh.ops.bevel(hbm, geom=list(hbm.edges), offset=bevel_w, segments=1, affect="EDGES", clamp_overlap=True)
            bmesh.ops.recalc_face_normals(hbm, faces=hbm.faces)
        hmesh = bpy.data.meshes.new(hname)
        hbm.to_mesh(hmesh)
        hbm.free()
        apply_box_uv(hmesh, scale=2.0)
        hobj = bpy.data.objects.new(hname, hmesh)
        hobj.data.materials.append(hmat)
        col.objects.link(hobj)
        hex_parts.append(hobj)
    _parent_all(hex_parts, hex_root)
    parts.append(hex_root)

    _parent_all(parts, root)
    return root



def build_compact_desktop_printer(
    location: tuple[float, float, float],
    rot_z_deg: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Sleek matte-black Brother / Canon compact home wireless laser & photo printer facing -X,
    with rear loaded A4 paper stack, emerging printed wireframe output sheet, OLED status strip,
    plus an extra white A4 ream & green self-healing maker cutting mat beside it!
    """
    root = _new_group("Prop_DesktopLaserPrinter", location, col, rot_z_deg=rot_z_deg)
    parts: list[bpy.types.Object] = []

    # Main beveled matte-black chassis (depth_x=0.31, width_y=0.38, height_z=0.148)
    parts.append(create_beveled_box("Printer_BodyLower", (0.31, 0.38, 0.088), (0.0, 0.0, 0.044), bevel=0.007, segments=3, material=mats["matte_plastic"], collection=col))
    parts.append(create_beveled_box("Printer_BodyUpper", (0.295, 0.376, 0.062), (0.006, 0.0, 0.116), bevel=0.006, segments=3, material=mats["anodized_black"], collection=col))
    # Angled top scanner lid seam & front control bezel
    parts.append(create_beveled_box("Printer_ScannerLid", (0.285, 0.365, 0.012), (0.008, 0.0, 0.151), bevel=0.003, material=mats["gunmetal"], collection=col))
    parts.append(create_beveled_box("Printer_ControlPanel", (0.036, 0.16, 0.022), (-0.148, -0.075, 0.128), rotation=(0.0, math.radians(-32.0), 0.0), bevel=0.003, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("Printer_OLEDStrip", (0.004, 0.064, 0.012), (-0.162, -0.085, 0.132), rotation=(0.0, math.radians(-32.0), 0.0), bevel=0.001, material=mats["emissive_rgb_cyan"], collection=col))
    parts.append(create_beveled_cylinder("Printer_WifiLED", 0.003, 0.003, 12, 0.0005, location=(-0.160, -0.022, 0.131), rotation=(0.0, math.radians(58.0), 0.0), material=mats["emissive_homelab_led"], collection=col))

    # Rear tilted paper feed flap + crisp white A4 paper stack sticking out!
    parts.append(create_beveled_box("Printer_RearTray", (0.010, 0.23, 0.145), (0.142, 0.0, 0.185), rotation=(0.0, math.radians(-18.0), 0.0), bevel=0.002, material=mats["anodized_black"], collection=col))
    parts.append(create_beveled_box("Printer_RearPaperStack", (0.016, 0.210, 0.135), (0.128, 0.0, 0.180), rotation=(0.0, math.radians(-18.0), 0.0), bevel=0.001, material=mats["paper_cream"], collection=col))

    # Front output tray + freshly printed engineering diagram A4 sheet emerging!
    parts.append(create_beveled_box("Printer_FrontTray", (0.145, 0.24, 0.008), (-0.195, 0.0, 0.056), rotation=(0.0, math.radians(8.0), 0.0), bevel=0.002, material=mats["anodized_black"], collection=col))
    bm_sh = bmesh.new(); uv_sh = bm_sh.loops.layers.uv.verify()
    sw, sd = 0.175, 0.210
    f = bm_sh.faces.new((
        bm_sh.verts.new((-sw * 0.5, -sd * 0.5, 0.0)),
        bm_sh.verts.new((sw * 0.5, -sd * 0.5, 0.0)),
        bm_sh.verts.new((sw * 0.5, sd * 0.5, 0.0)),
        bm_sh.verts.new((-sw * 0.5, sd * 0.5, 0.0)),
    ))
    f.loops[0][uv_sh].uv = (0.0, 0.0); f.loops[1][uv_sh].uv = (1.0, 0.0); f.loops[2][uv_sh].uv = (1.0, 1.0); f.loops[3][uv_sh].uv = (0.0, 1.0)
    shmesh = bpy.data.meshes.new("Printer_PrintedSheet"); bm_sh.to_mesh(shmesh); bm_sh.free()
    shobj = bpy.data.objects.new("Printer_PrintedSheet", shmesh)
    shobj.location = (-0.185, 0.0, 0.064)
    shobj.rotation_euler = (0.0, math.radians(8.0), 0.0)
    shobj.data.materials.append(mats["notebook_page"])
    col.objects.link(shobj)
    parts.append(shobj)

    _parent_all(parts, root)
    return root



def _build_swept_ribbon_arm(
    name: str,
    profile_yz: list[tuple[float, float]],
    x_center: float,
    width_x: float,
    thickness: float,
    material: bpy.types.Material,
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """Extrude a smooth CNC bent-aluminum ribbon arm along a (y, z) centerline with beveled edges."""
    bm = bmesh.new()
    n = len(profile_yz)
    half_w = width_x * 0.5
    half_t = thickness * 0.5
    rings = []
    for i, (py, pz) in enumerate(profile_yz):
        if i == 0:
            ty, tz = profile_yz[1][0] - py, profile_yz[1][1] - pz
        elif i == n - 1:
            ty, tz = py - profile_yz[i - 1][0], pz - profile_yz[i - 1][1]
        else:
            ty, tz = profile_yz[i + 1][0] - profile_yz[i - 1][0], profile_yz[i + 1][1] - profile_yz[i - 1][1]
        L = max(1e-6, math.hypot(ty, tz))
        ny, nz = -tz / L, ty / L
        v0 = bm.verts.new((x_center - half_w, py - ny * half_t, pz - nz * half_t))
        v1 = bm.verts.new((x_center + half_w, py - ny * half_t, pz - nz * half_t))
        v2 = bm.verts.new((x_center + half_w, py + ny * half_t, pz + nz * half_t))
        v3 = bm.verts.new((x_center - half_w, py + ny * half_t, pz + nz * half_t))
        rings.append((v0, v1, v2, v3))

    for i in range(n - 1):
        a, b = rings[i], rings[i + 1]
        for k in range(4):
            kn = (k + 1) % 4
            bm.faces.new((a[k], a[kn], b[kn], b[k]))
    # Cap both ends
    bm.faces.new((rings[0][3], rings[0][2], rings[0][1], rings[0][0]))
    bm.faces.new((rings[-1][0], rings[-1][1], rings[-1][2], rings[-1][3]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    bmesh.ops.bevel(bm, geom=list(bm.edges), offset=0.0012, segments=2, affect="EDGES", clamp_overlap=True)
    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()
    apply_box_uv(mesh, scale=6.0)
    obj = bpy.data.objects.new(name, mesh)
    obj.data.materials.append(material)
    set_smooth_with_bevel_normals(obj)
    col.objects.link(obj)
    return obj


def build_desk_papers_laptop_stand_and_notes(
    desk_origin: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Adds rich authentic programmer/maker desk life:
    - Sculpted Twelve South Curve-inspired single-piece CNC curved anodized aluminum laptop stand
      (flowing C-profile twin cantilever arms, open cooling bridge, silicone anti-slip pads & front retaining hooks!)
      angled at 13 deg ergonomically for the Official Apple MacBook Air 15" Midnight!
    - Fanned A4 printed engineering/architecture spec sheets on left desk
    - Clean flat yellow & coral Post-it sticky notes (ZERO clipping into monitor riser edge!)
    """
    dx, dy, _ = desk_origin
    desk_h = 0.750
    root = _new_group("Hero_DeskGeekPapersAndStand", (dx, dy, desk_h), col)
    parts: list[bpy.types.Object] = []

    # 1. Sculpted CNC Curved Anodized-Aluminum Laptop Stand (Twelve South Curve / Rain Design mStand style!)
    #    Top angled plane passes cleanly through (y=0.0, z=0.095) with slope dz/dy = tan(13 deg) = +0.2309!
    ls = _new_group("Desk_LaptopStand", (-0.94, -0.08, 0.0), col, rot_z_deg=24.0)
    ls_parts: list[bpy.types.Object] = []

    # Continuous flowing C-curve side profile (base -> curved rear riser -> 13-deg tilted upper arm -> front retaining hook!)
    slope = math.tan(math.radians(13.0))
    c_profile = [
        (-0.092, 0.004),   # Front base foot
        (0.010, 0.004),
        (0.078, 0.005),    # Rear base corner entering bend
        (0.098, 0.014),
        (0.106, 0.036),    # Sweeping vertical CNC aluminum curve
        (0.105, 0.068),
        (0.098, 0.096),
        (0.082, 0.114),    # Top rear bend entering 13-deg cradle arm
        (0.045, 0.095 + 0.045 * slope),
        (0.000, 0.095),
        (-0.055, 0.095 - 0.055 * slope),
        (-0.104, 0.095 - 0.104 * slope),
        (-0.118, 0.095 - 0.114 * slope + 0.002),  # Curved front laptop retaining hook
        (-0.122, 0.095 - 0.114 * slope + 0.015),  # Front lip tip catching MacBook front edge
    ]
    for sx in (-0.094, 0.094):
        ls_parts.append(_build_swept_ribbon_arm(
            f"LaptopStand_CurveArm_{sx:+.2f}", c_profile, x_center=sx,
            width_x=0.028, thickness=0.0055, material=mats["gunmetal"], col=col,
        ))
        # Matte-black silicone anti-slip traction strip inlaid along each angled top arm
        ls_parts.append(create_beveled_box(
            f"LaptopStand_GripPad_{sx:+.2f}", (0.018, 0.185, 0.0026),
            (sx, -0.014, 0.095 - 0.014 * slope + 0.0038),
            rotation=(math.radians(13.0), 0.0, 0.0), bevel=0.0008,
            material=mats["matte_plastic"], collection=col,
        ))
        # Subtle under-base rubber desk pads
        ls_parts.append(create_beveled_box(
            f"LaptopStand_RubberFoot_{sx:+.2f}", (0.022, 0.155, 0.002),
            (sx, -0.008, 0.001), bevel=0.0006, material=mats["matte_plastic"], collection=col,
        ))

    # Swept structural crossbar tying the twin rear curves + chamfered front crossbar + cable pass-through ring
    ls_parts.append(create_beveled_box(
        "LaptopStand_RearBridge", (0.188, 0.006, 0.046), (0.0, 0.105, 0.056),
        bevel=0.002, material=mats["gunmetal"], collection=col,
    ))
    ls_parts.append(create_beveled_box(
        "LaptopStand_FrontBaseBar", (0.188, 0.026, 0.0055), (0.0, -0.080, 0.004),
        bevel=0.0018, material=mats["gunmetal"], collection=col,
    ))
    ls_parts.append(create_beveled_cylinder(
        "LaptopStand_CableGrommet", 0.015, 0.008, 20, 0.0015,
        location=(0.0, 0.105, 0.056), rotation=(math.radians(90), 0.0, 0.0),
        material=mats["anodized_black"], collection=col,
    ))
    _parent_all(ls_parts, ls)
    parts.append(ls)

    # 2. Fanned Stack of 3 Printed B5 Spec Sheets tucked neatly under the open Moleskine notebook (ZERO desk mat overlap!)
    for si, (ox, oy, oz, yaw) in enumerate((
        (-0.67, -0.22, 0.0012, -6.0),
        (-0.66, -0.21, 0.0024, -12.0),
        (-0.69, -0.23, 0.0036, -2.0),
    )):
        bm_p = bmesh.new(); uv_p = bm_p.loops.layers.uv.verify()
        pw, pd = 0.175, 0.235
        f = bm_p.faces.new((
            bm_p.verts.new((-pw * 0.5, -pd * 0.5, 0.0)),
            bm_p.verts.new((pw * 0.5, -pd * 0.5, 0.0)),
            bm_p.verts.new((pw * 0.5, pd * 0.5, 0.0)),
            bm_p.verts.new((-pw * 0.5, pd * 0.5, 0.0)),
        ))
        f.loops[0][uv_p].uv = (0.0, 0.0); f.loops[1][uv_p].uv = (1.0, 0.0); f.loops[2][uv_p].uv = (1.0, 1.0); f.loops[3][uv_p].uv = (0.0, 1.0)
        pmesh = bpy.data.meshes.new(f"Desk_A4Sheet_{si}"); bm_p.to_mesh(pmesh); bm_p.free()
        pobj = bpy.data.objects.new(f"Desk_A4Sheet_{si}", pmesh)
        pobj.location = (ox, oy, oz)
        pobj.rotation_euler = (0.0, 0.0, math.radians(yaw))
        pobj.data.materials.append(mats["notebook_page"])
        col.objects.link(pobj)
        parts.append(pobj)

    # 3. Clean Flat Post-it Sticky Pad + 2 Flat Notes resting cleanly WITH ZERO RISER CLIPPING!
    parts.append(create_beveled_box("Desk_StickyPad", (0.076, 0.076, 0.008), (-0.36, -0.27, 0.0082), rotation=(0.0, 0.0, math.radians(10.0)), bevel=0.001, material=mats["sticky_note_yellow"], collection=col))
    parts.append(create_beveled_box("Desk_StickyNote1", (0.068, 0.068, 0.0012), (-0.31, -0.19, 0.0052), rotation=(0.0, 0.0, math.radians(-8.0)), bevel=0.0003, material=mats["sticky_note_yellow"], collection=col))
    parts.append(create_beveled_box("Desk_StickyNote2", (0.062, 0.062, 0.0012), (0.48, 0.08, 0.0932), rotation=(0.0, 0.0, math.radians(14.0)), bevel=0.0003, material=mats["sticky_note_coral"], collection=col))

    _parent_all(parts, root)
    return root



def build_maker_workbench_counter(
    location: tuple[float, float, float],
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Continuous chamfered American Walnut butcher-block countertop unifying the 2 charcoal IKEA Alex
    6-drawer units along the East Maker Zone (X = 1.88, Y = -0.74, top surface at Z = 0.702m),
    topped with a green self-healing cutting mat, extra white A4 paper ream & cyan 3D-printed test cube!
    """
    root = _new_group("Hero_MakerWorkbenchTop", location, col)
    parts: list[bpy.types.Object] = []

    # Solid dark walnut workbench slab resting flush atop the two 0.674m-tall IKEA Alex drawer units
    parts.append(create_beveled_box(
        "MakerBench_WalnutTop", (0.56, 1.40, 0.028), (0.0, 0.0, 0.688),
        bevel=0.004, segments=3, material=mats["walnut_desk"], uv_scale=0.85, collection=col,
    ))
    # Subtle matte-black rear cable management lip
    parts.append(create_beveled_box(
        "MakerBench_BackLip", (0.016, 1.38, 0.038), (0.272, 0.0, 0.712),
        bevel=0.002, material=mats["anodized_black"], collection=col,
    ))
    # Green self-healing maker cutting mat on front-center workspace (Z = 0.702..0.705)
    parts.append(create_beveled_box(
        "MakerBench_CuttingMat", (0.26, 0.36, 0.003), (-0.11, 0.04, 0.7035),
        bevel=0.001, material=mats["cutting_mat_green"], collection=col,
    ))
    # Fresh ream of crisp white A4 printer paper stacked cleanly IN FRONT-LEFT of the printer (zero overlap!)
    parts.append(create_beveled_box(
        "MakerBench_A4PaperReam", (0.210, 0.260, 0.038), (-0.14, -0.22, 0.721),
        rotation=(0.0, 0.0, math.radians(-5.0)), bevel=0.0015, material=mats["paper_cream"], collection=col,
    ))
    # Matte Terracotta PLA 3D-printed prototype calibration cube sitting cleanly on cutting mat!
    parts.append(create_beveled_box(
        "MakerBench_3DPrintProto", (0.034, 0.034, 0.034), (-0.13, 0.14, 0.722),
        rotation=(0.0, 0.0, math.radians(24.0)), bevel=0.003, material=mats["keycap_accent"], collection=col,
    ))
    # Brushed steel vernier caliper resting cleanly on the green cutting mat
    parts.append(create_beveled_box(
        "MakerBench_CaliperBar", (0.014, 0.185, 0.003), (-0.12, 0.03, 0.7065),
        rotation=(0.0, 0.0, math.radians(16.0)), bevel=0.0006, material=mats["chrome"], collection=col,
    ))
    parts.append(create_beveled_box(
        "MakerBench_CaliperJaw", (0.048, 0.022, 0.004), (-0.132, -0.032, 0.707),
        rotation=(0.0, 0.0, math.radians(16.0)), bevel=0.0008, material=mats["chrome"], collection=col,
    ))

    # Floating Walnut Maker Wall Shelf above workbench (Z = 1.68m, aligning visually with Bookshelf Tier 4!)
    # East wall is at world X = +2.18, root is at X = +1.88 -> wall is at local x = +0.30!
    ms_z = 1.68
    parts.append(create_beveled_box(
        "MakerWallShelf_Plank", (0.24, 1.24, 0.028), (0.18, 0.0, ms_z),
        bevel=0.003, material=mats["walnut_desk"], uv_scale=0.85, collection=col,
    ))
    parts.append(create_beveled_box(
        "MakerWallShelf_LEDChannel", (0.014, 1.14, 0.006), (0.25, 0.0, ms_z - 0.017),
        bevel=0.001, material=mats["anodized_black"], collection=col,
    ))
    parts.append(create_beveled_box(
        "MakerWallShelf_LEDStrip", (0.008, 1.12, 0.003), (0.25, 0.0, ms_z - 0.020),
        bevel=0.0005, material=mats["emissive_shelf_led"], collection=col,
    ))
    # Curated Maker Shelf Props resting flush at Z = ms_z + 0.014 = 1.694:
    # 1. Framed Bauhaus/Gallery Blueprint leaning gently against East wall at local y = -0.32
    f_w, f_h = 0.28, 0.36
    fg = _new_group("MakerShelf_FramedPrint", (0.24, -0.32, ms_z + 0.014 + f_h * 0.5), col, rot_z_deg=0.0)
    fg.rotation_euler.y = math.radians(-6.0)
    fp = [
        create_beveled_box("MakerFrame_Back", (0.016, f_w, f_h), (0.0, 0.0, 0.0), bevel=0.002, material=mats["anodized_black"], collection=col),
    ]
    bm_fa = bmesh.new(); uv_fa = bm_fa.loops.layers.uv.verify()
    aw, ah = f_w - 0.022, f_h - 0.022
    fa = bm_fa.faces.new((
        bm_fa.verts.new((-0.009, aw * 0.5, -ah * 0.5)),
        bm_fa.verts.new((-0.009, -aw * 0.5, -ah * 0.5)),
        bm_fa.verts.new((-0.009, -aw * 0.5, ah * 0.5)),
        bm_fa.verts.new((-0.009, aw * 0.5, ah * 0.5)),
    ))
    fa.loops[0][uv_fa].uv = (0.0, 0.0); fa.loops[1][uv_fa].uv = (1.0, 0.0); fa.loops[2][uv_fa].uv = (1.0, 1.0); fa.loops[3][uv_fa].uv = (0.0, 1.0)
    famesh = bpy.data.meshes.new("MakerFrame_Canvas"); bm_fa.to_mesh(famesh); bm_fa.free()
    faobj = bpy.data.objects.new("MakerFrame_Canvas", famesh)
    faobj.data.materials.append(mats["maker_blueprint"])
    col.objects.link(faobj)
    fp.append(faobj)
    _parent_all(fp, fg)
    parts.append(fg)
    # 2. Matte-black SMD electronics component organizer box + 2 boxed filament spools at local y = +0.26..+0.46
    parts.append(create_beveled_box(
        "MakerShelf_PartsBox", (0.17, 0.26, 0.12), (0.18, 0.06, ms_z + 0.014 + 0.06),
        bevel=0.004, material=mats["alex_charcoal"], collection=col,
    ))
    parts.append(create_beveled_box(
        "MakerShelf_PartsLabel", (0.004, 0.065, 0.022), (0.094, 0.06, ms_z + 0.014 + 0.072),
        bevel=0.001, material=mats["brushed_brass"], collection=col,
    ))
    for fi, (fy, fcol) in enumerate(((0.34, mats["vinyl_cover_4"]), (0.44, mats["vinyl_cover_2"]))):
        parts.append(create_beveled_box(
            f"MakerShelf_FilamentBox_{fi}", (0.20, 0.072, 0.205), (0.18, fy, ms_z + 0.014 + 0.1025),
            bevel=0.003, material=fcol, collection=col,
        ))

    _parent_all(parts, root)
    return root



def build_studio_architectural_led_strips(
    desk_origin: tuple[float, float, float],
    wall_y: float,
    mats: dict[str, bpy.types.Material],
    col: bpy.types.Collection,
) -> bpy.types.Object:
    """
    Clean Studio ARGB Accent LED Strips (no outer wall perimeter frame — keeps North concrete & walnut clean!):
    1. Dual-tone 2.18m standing-desk rear bias LED bar (synced live with 8-mode Studio ARGB engine!)
    2. Recessed 4-sided perimeter floating halo 12mm behind the matte-black IKEA SKADIS pegboard (synced live!)
    3. East Maker 3D-printer workbench underside ARGB strip (paired directly with the 4-tier synced bookshelf LEDs!)
    """
    from materials import make_emissive

    mat_shelf_rgb = bpy.data.materials.get("Emit_StudioShelfRGB") or make_emissive(
        "Emit_StudioShelfRGB", (0.12, 0.82, 1.0), strength=3.8, roughness=0.22
    )
    mat_rgb_pri = bpy.data.materials.get("Emit_StudioStripRGB_Primary") or make_emissive(
        "Emit_StudioStripRGB_Primary", (0.12, 0.82, 1.0), strength=3.8, roughness=0.22
    )
    mat_rgb_sec = bpy.data.materials.get("Emit_StudioStripRGB_Secondary") or make_emissive(
        "Emit_StudioStripRGB_Secondary", (1.0, 0.44, 0.14), strength=3.6, roughness=0.22
    )
    mat_blk = mats["anodized_black"]

    root = _new_group("Hero_StudioArchitecturalLEDs", (0.0, 0.0, 0.0), col)
    parts: list[bpy.types.Object] = []

    def add_strip(
        name: str,
        size: tuple[float, float, float],
        loc: tuple[float, float, float],
        lens_size: tuple[float, float, float],
        lens_loc: tuple[float, float, float],
        lens_mat: bpy.types.Material,
    ) -> None:
        parts.append(create_beveled_box(f"{name}_Chan", size, loc, bevel=0.001, material=mat_blk, collection=col))
        parts.append(create_beveled_box(f"{name}_Lens", lens_size, lens_loc, bevel=0.0005, material=lens_mat, collection=col))

    # 1. 2.18m Standing-Desk Rear Dual-Tone ARGB Bias Bar (Left = Primary, Right = Secondary, full 8-mode sync!)
    dx, dy, _ = desk_origin
    desk_back_y = dy + 0.422
    desk_strip_z = 0.728
    parts.append(create_beveled_box(
        "StudioLED_DeskBias_Chan", (2.18, 0.014, 0.014), (dx, desk_back_y, desk_strip_z),
        bevel=0.001, material=mat_blk, collection=col,
    ))
    parts.append(create_beveled_box(
        "StudioLED_DeskBias_L", (1.07, 0.008, 0.008), (dx - 0.54, desk_back_y + 0.007, desk_strip_z),
        bevel=0.0005, material=mat_rgb_pri, collection=col,
    ))
    parts.append(create_beveled_box(
        "StudioLED_DeskBias_R", (1.07, 0.008, 0.008), (dx + 0.54, desk_back_y + 0.007, desk_strip_z),
        bevel=0.0005, material=mat_rgb_sec, collection=col,
    ))

    # 2. Recessed 4-Sided Perimeter Floating Halo 12mm Behind Matte-Black IKEA SKADIS Pegboard (anchor X=1.16, Y=2.04, Z=1.44)
    px, py, pz = 1.16, wall_y - 0.010, 1.44
    hw, hh = 0.285, 0.305
    parts.append(create_beveled_box("StudioLED_PegHalo_T", (hw * 2.0, 0.007, 0.007), (px, py, pz + hh), bevel=0.0005, material=mat_rgb_sec, collection=col))
    parts.append(create_beveled_box("StudioLED_PegHalo_B", (hw * 2.0, 0.007, 0.007), (px, py, pz - hh), bevel=0.0005, material=mat_rgb_sec, collection=col))
    parts.append(create_beveled_box("StudioLED_PegHalo_L", (0.007, 0.007, hh * 2.0), (px - hw, py, pz), bevel=0.0005, material=mat_rgb_sec, collection=col))
    parts.append(create_beveled_box("StudioLED_PegHalo_R", (0.007, 0.007, hh * 2.0), (px + hw, py, pz), bevel=0.0005, material=mat_rgb_sec, collection=col))

    # 3. East Maker Workbench Underside ARGB Linear Strip (continuing the synced 4-tier bookshelf neon!)
    add_strip(
        "StudioLED_MakerBench",
        (0.016, 1.38, 0.010), (1.622, -0.74, 0.666),
        (0.010, 1.34, 0.005), (1.622, -0.74, 0.660),
        mat_shelf_rgb,
    )

    _parent_all(parts, root)
    return root