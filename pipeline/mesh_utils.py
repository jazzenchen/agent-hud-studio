"""
Reusable high-precision Blender bmesh modeling utilities for ArchViz.
Enforces micro-bevels, weighted normals, box-projected world-scale UVs, and clean grounding.
"""

import math
import bmesh
import bpy
from mathutils import Matrix, Vector


def ensure_collection(name: str, parent=None) -> bpy.types.Collection:
    if name in bpy.data.collections:
        return bpy.data.collections[name]
    col = bpy.data.collections.new(name)
    if parent is None:
        bpy.context.scene.collection.children.link(col)
    else:
        parent.children.link(col)
    return col


def link_object(obj: bpy.types.Object, col: bpy.types.Collection) -> bpy.types.Object:
    for existing in list(obj.users_collection):
        existing.objects.unlink(obj)
    col.objects.link(obj)
    return obj


def set_smooth_with_bevel_normals(obj: bpy.types.Object) -> None:
    """Smooth-shade faces and add WeightedNormal modifier for crisp ArchViz highlights."""
    if obj.type != "MESH" or not obj.data:
        return
    mesh = obj.data
    mesh.polygons.foreach_set("use_smooth", [True] * len(mesh.polygons))
    mesh.update()
    if "WeightedNormal" not in obj.modifiers:
        mod = obj.modifiers.new(name="WeightedNormal", type="WEIGHTED_NORMAL")
        mod.keep_sharp = True


def apply_box_uv(mesh: bpy.types.Mesh, scale: float = 1.0) -> None:
    """
    Deterministic world/local-scale triplanar box UV projection into UVMap (UV0).
    Avoids stretching on arbitrary architectural slabs, cabinets, and desks.
    """
    bm = bmesh.new()
    bm.from_mesh(mesh)
    uv_layer = bm.loops.layers.uv.verify()

    for face in bm.faces:
        n = face.normal
        ax, ay, az = abs(n.x), abs(n.y), abs(n.z)
        for loop in face.loops:
            co = loop.vert.co
            if az >= ax and az >= ay:
                u, v = co.x * scale, co.y * scale
            elif ax >= ay and ax >= az:
                u, v = co.y * scale, co.z * scale
            else:
                u, v = co.x * scale, co.z * scale
            loop[uv_layer].uv = (u, v)

    bm.to_mesh(mesh)
    bm.free()
    mesh.update()


def create_beveled_box(
    name: str,
    size: tuple[float, float, float],
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    bevel: float = 0.004,
    segments: int = 3,
    material: bpy.types.Material | None = None,
    uv_scale: float = 1.0,
    collection: bpy.types.Collection | None = None,
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
) -> bpy.types.Object:
    """Create a chamfered/beveled box with real-world box UVs and weighted normals."""
    sx, sy, sz = size
    bm = bmesh.new()
    bmesh.ops.create_cube(bm, size=1.0)
    bmesh.ops.scale(bm, vec=(sx, sy, sz), verts=bm.verts)

    if bevel > 0.0:
        max_b = min(sx, sy, sz) * 0.38
        b_width = min(bevel, max_b)
        bmesh.ops.bevel(
            bm,
            geom=list(bm.edges),
            offset=b_width,
            segments=segments,
            affect="EDGES",
            clamp_overlap=True,
            profile=0.5,
        )

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    apply_box_uv(mesh, scale=uv_scale)

    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    if material is not None:
        obj.data.materials.append(material)
    set_smooth_with_bevel_normals(obj)
    if collection is not None:
        collection.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def create_beveled_cylinder(
    name: str,
    radius: float,
    depth: float,
    vertices: int = 40,
    bevel: float = 0.002,
    segments: int = 2,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation: tuple[float, float, float] = (0.0, 0.0, 0.0),
    material: bpy.types.Material | None = None,
    uv_scale: float = 1.0,
    collection: bpy.types.Collection | None = None,
) -> bpy.types.Object:
    bm = bmesh.new()
    bmesh.ops.create_cone(
        bm,
        cap_ends=True,
        cap_tris=False,
        segments=vertices,
        radius1=radius,
        radius2=radius,
        depth=depth,
    )
    if bevel > 0.0:
        cap_edges = [
            e for e in bm.edges
            if abs(e.verts[0].co.z - e.verts[1].co.z) < 1e-4
        ]
        bmesh.ops.bevel(
            bm,
            geom=cap_edges,
            offset=min(bevel, radius * 0.35, depth * 0.35),
            segments=segments,
            affect="EDGES",
            clamp_overlap=True,
        )

    mesh = bpy.data.meshes.new(name)
    bm.to_mesh(mesh)
    bm.free()

    apply_box_uv(mesh, scale=uv_scale)
    obj = bpy.data.objects.new(name, mesh)
    obj.location = location
    obj.rotation_euler = rotation
    if material is not None:
        obj.data.materials.append(material)
    set_smooth_with_bevel_normals(obj)
    if collection is not None:
        collection.objects.link(obj)
    else:
        bpy.context.scene.collection.objects.link(obj)
    return obj


def create_curved_panel(
    name: str,
    width: float,
    height: float,
    thickness: float,
    curve_radius: float,
    segments_x: int = 36,
    bevel: float = 0.002,
    material: bpy.types.Material | None = None,
    screen_material: bpy.types.Material | None = None,
    collection: bpy.types.Collection | None = None,
) -> tuple[bpy.types.Object, bpy.types.Object]:
    """
    Create a sleek curved monitor chassis + inset curved display plane with proper [0..1] screen UVs.
    Local orientation: Screen faces -Y (toward viewer sitting at -Y), center at origin.
    """
    half_angle = (width / curve_radius) * 0.5

    # 1. Curved body shell
    bm = bmesh.new()
    front_top, front_bot, back_top, back_bot = [], [], [], []
    for i in range(segments_x + 1):
        t = i / segments_x
        ang = -half_angle + t * (2.0 * half_angle)
        # Curve bows backward (+Y) at center, wraps forward (-Y) at left/right edges
        r_front = curve_radius
        r_back = curve_radius + thickness
        cx = math.sin(ang)
        cy = math.cos(ang) - 1.0  # 0 at center, negative at edges -> edges wrap toward -Y!

        # Wait: cy = cos(ang) - 1 is NEGATIVE at edges -> wraps toward -Y (viewer). Perfect!
        fx, fy = r_front * cx, r_front * cy
        bx, by = r_back * cx, r_back * cy + thickness

        front_bot.append(bm.verts.new((fx, fy, -height * 0.5)))
        front_top.append(bm.verts.new((fx, fy, height * 0.5)))
        back_bot.append(bm.verts.new((bx, by, -height * 0.5)))
        back_top.append(bm.verts.new((bx, by, height * 0.5)))

    bm.verts.ensure_lookup_table()
    for i in range(segments_x):
        # Front face (facing -Y)
        bm.faces.new((front_bot[i], front_bot[i + 1], front_top[i + 1], front_top[i]))
        # Back face (facing +Y)
        bm.faces.new((back_bot[i + 1], back_bot[i], back_top[i], back_top[i + 1]))
        # Top face (+Z)
        bm.faces.new((front_top[i], front_top[i + 1], back_top[i + 1], back_top[i]))
        # Bottom face (-Z)
        bm.faces.new((back_bot[i], back_bot[i + 1], front_bot[i + 1], front_bot[i]))

    # Left & right end caps
    bm.faces.new((back_bot[0], front_bot[0], front_top[0], back_top[0]))
    bm.faces.new((front_bot[-1], back_bot[-1], back_top[-1], front_top[-1]))

    bmesh.ops.recalc_face_normals(bm, faces=bm.faces)
    if bevel > 0.0:
        sharp_edges = [e for e in bm.edges if e.calc_face_angle(0.0) > 0.7]
        bmesh.ops.bevel(
            bm,
            geom=sharp_edges,
            offset=bevel,
            segments=2,
            affect="EDGES",
            clamp_overlap=True,
        )

    body_mesh = bpy.data.meshes.new(f"{name}_Body")
    bm.to_mesh(body_mesh)
    bm.free()
    apply_box_uv(body_mesh, scale=2.0)

    body_obj = bpy.data.objects.new(f"{name}_Body", body_mesh)
    if material:
        body_obj.data.materials.append(material)
    set_smooth_with_bevel_normals(body_obj)

    # 2. Curved Active OLED Display Surface (inset 4mm top/sides, 14mm chin bottom, 1.2mm forward)
    bezel_side = 0.005
    bezel_top = 0.005
    bezel_bot = 0.014
    scr_w = width - 2.0 * bezel_side
    scr_h = height - bezel_top - bezel_bot
    z_bot = -height * 0.5 + bezel_bot
    z_top = height * 0.5 - bezel_top
    half_ang_s = (scr_w / curve_radius) * 0.5

    bm_s = bmesh.new()
    uv_layer = bm_s.loops.layers.uv.verify()
    s_bot, s_top = [], []
    for i in range(segments_x + 1):
        t = i / segments_x
        ang = -half_ang_s + t * (2.0 * half_ang_s)
        x = curve_radius * math.sin(ang)
        y = curve_radius * (math.cos(ang) - 1.0) - 0.0014
        s_bot.append(bm_s.verts.new((x, y, z_bot)))
        s_top.append(bm_s.verts.new((x, y, z_top)))

    for i in range(segments_x):
        f = bm_s.faces.new((s_bot[i], s_bot[i + 1], s_top[i + 1], s_top[i]))
        u0 = i / segments_x
        u1 = (i + 1) / segments_x
        f.loops[0][uv_layer].uv = (u0, 0.0)
        f.loops[1][uv_layer].uv = (u1, 0.0)
        f.loops[2][uv_layer].uv = (u1, 1.0)
        f.loops[3][uv_layer].uv = (u0, 1.0)

    bmesh.ops.recalc_face_normals(bm_s, faces=bm_s.faces)
    scr_mesh = bpy.data.meshes.new(f"{name}_Screen")
    bm_s.to_mesh(scr_mesh)
    bm_s.free()

    scr_obj = bpy.data.objects.new(f"{name}_Screen", scr_mesh)
    if screen_material:
        scr_obj.data.materials.append(screen_material)
    scr_obj.data.polygons.foreach_set("use_smooth", [True] * len(scr_obj.data.polygons))
    scr_obj.parent = body_obj

    target_col = collection or bpy.context.scene.collection
    target_col.objects.link(body_obj)
    target_col.objects.link(scr_obj)
    return body_obj, scr_obj


def import_gltf_asset(
    gltf_path: str,
    name: str,
    collection: bpy.types.Collection,
    target_height: float | None = None,
    target_max_dim: float | None = None,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_z_deg: float = 0.0,
    ground_z: float | None = 0.0,
) -> bpy.types.Object:
    """
    Import a Poly Haven or custom glTF/GLB asset into an Anchor Empty,
    normalize real-world size cleanly, snap bottom to ground_z, and place at location.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(gltf_path))
    imported = [o for o in bpy.data.objects if o not in before]

    anchor = bpy.data.objects.new(name, None)
    anchor.empty_display_type = "PLAIN_AXES"
    anchor.empty_display_size = 0.15
    collection.objects.link(anchor)

    top_level = [o for o in imported if o.parent is None]
    for obj in imported:
        link_object(obj, collection)
    for obj in top_level:
        obj.parent = anchor

    bpy.context.view_layer.update()

    # Compute world bounding box of all mesh children
    meshes = [o for o in imported if o.type == "MESH"]
    if meshes:
        min_v = Vector((1e9, 1e9, 1e9))
        max_v = Vector((-1e9, -1e9, -1e9))
        for m in meshes:
            for corner in m.bound_box:
                wc = m.matrix_world @ Vector(corner)
                min_v.x = min(min_v.x, wc.x)
                min_v.y = min(min_v.y, wc.y)
                min_v.z = min(min_v.z, wc.z)
                max_v.x = max(max_v.x, wc.x)
                max_v.y = max(max_v.y, wc.y)
                max_v.z = max(max_v.z, wc.z)

        dims = max_v - min_v
        scale_factor = 1.0
        if target_height is not None and dims.z > 1e-4:
            scale_factor = target_height / dims.z
        elif target_max_dim is not None and max(dims.x, dims.y, dims.z) > 1e-4:
            scale_factor = target_max_dim / max(dims.x, dims.y, dims.z)

        # Center XY and snap min Z to 0 in local space by shifting top_level children
        center_xy = Vector(((min_v.x + max_v.x) * 0.5, (min_v.y + max_v.y) * 0.5, min_v.z))
        for obj in top_level:
            obj.location = (obj.location - center_xy) * scale_factor
            obj.scale = obj.scale * scale_factor

    anchor.rotation_euler = (0.0, 0.0, math.radians(rotation_z_deg))
    lx, ly, lz = location
    anchor.location = (lx, ly, ground_z if ground_z is not None else lz)
    bpy.context.view_layer.update()
    return anchor


def import_blenderkit_glb(
    glb_path: str,
    name: str,
    collection: bpy.types.Collection,
    target_height: float | None = None,
    target_width: float | None = None,
    target_max_dim: float | None = None,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_xyz_deg: tuple[float, float, float] = (0.0, 0.0, 0.0),
    ground_z: float | None = 0.0,
    exclude_substrings: tuple[str, ...] = (),
    x_side_filter: str | None = None,  # 'neg' or 'pos' to split dual-object pairs (e.g. M-Audio speakers)
    decimate_ratio: float | None = None,
) -> bpy.types.Object:
    """
    Import a vetted BlenderKit artist .glb, optionally strip demo backdrops/wires or split L/R pairs,
    normalize real-world physical scale cleanly, snap min-Z to ground_z, and place accurately.
    """
    before = set(bpy.data.objects)
    bpy.ops.import_scene.gltf(filepath=str(glb_path))
    imported = [o for o in bpy.data.objects if o not in before]
    bpy.context.view_layer.update()

    # Filter unwanted objects (e.g., studio backdrop spheres, loose demo wires, or opposite half of pair)
    to_remove = set()
    for o in imported:
        lname = o.name.lower()
        if any(sub.lower() in lname for sub in exclude_substrings):
            to_remove.add(o)
        elif x_side_filter and o.type == "MESH":
            bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
            cx = (min(v.x for v in bb) + max(v.x for v in bb)) * 0.5
            if (x_side_filter == "neg" and cx > 0.01) or (x_side_filter == "pos" and cx < -0.01):
                to_remove.add(o)

    kept = [o for o in imported if o not in to_remove]
    for o in to_remove:
        bpy.data.objects.remove(o, do_unlink=True)

    anchor = bpy.data.objects.new(name, None)
    anchor.empty_display_type = "PLAIN_AXES"
    anchor.empty_display_size = 0.08
    collection.objects.link(anchor)

    top_level = [o for o in kept if o.parent is None or o.parent not in kept]
    for obj in kept:
        link_object(obj, collection)
    for obj in top_level:
        obj.parent = anchor

    bpy.context.view_layer.update()
    meshes = [o for o in kept if o.type == "MESH"]
    if meshes:
        if decimate_ratio is not None and 0.05 < decimate_ratio < 0.99:
            for m in meshes:
                if len(m.data.polygons) > 15000:
                    mod = m.modifiers.new("AutoDecimate", "DECIMATE")
                    mod.ratio = decimate_ratio

        min_v = Vector((1e9, 1e9, 1e9))
        max_v = Vector((-1e9, -1e9, -1e9))
        for m in meshes:
            for corner in m.bound_box:
                wc = m.matrix_world @ Vector(corner)
                min_v.x = min(min_v.x, wc.x)
                min_v.y = min(min_v.y, wc.y)
                min_v.z = min(min_v.z, wc.z)
                max_v.x = max(max_v.x, wc.x)
                max_v.y = max(max_v.y, wc.y)
                max_v.z = max(max_v.z, wc.z)

        dims = max_v - min_v
        scale_factor = 1.0
        if target_height is not None and dims.z > 1e-4:
            scale_factor = target_height / dims.z
        elif target_width is not None and dims.x > 1e-4:
            scale_factor = target_width / dims.x
        elif target_max_dim is not None and max(dims.x, dims.y, dims.z) > 1e-4:
            scale_factor = target_max_dim / max(dims.x, dims.y, dims.z)

        center_xy = Vector(((min_v.x + max_v.x) * 0.5, (min_v.y + max_v.y) * 0.5, min_v.z))
        for obj in top_level:
            # Preserve existing local transform cleanly when rebasing to anchor
            world_mat = obj.matrix_world.copy()
            obj.parent = anchor
            shift = Matrix.Translation(-center_xy)
            scale_m = Matrix.Scale(scale_factor, 4)
            obj.matrix_basis = scale_m @ shift @ world_mat

    rx, ry, rz = rotation_xyz_deg
    anchor.rotation_euler = (math.radians(rx), math.radians(ry), math.radians(rz))
    lx, ly, lz = location
    anchor.location = (lx, ly, ground_z if ground_z is not None else lz)
    bpy.context.view_layer.update()
    return anchor


def import_blend_collection(
    blend_path: str,
    collection_name: str,
    name: str,
    target_col: bpy.types.Collection,
    target_height: float | None = None,
    location: tuple[float, float, float] = (0.0, 0.0, 0.0),
    rotation_z_deg: float = 0.0,
    ground_z: float | None = 0.0,
) -> bpy.types.Object:
    """Append a full artist collection from a BlenderKit .blend file, normalize height & ground it cleanly."""
    with bpy.data.libraries.load(str(blend_path), link=False) as (data_from, data_to):
        if collection_name in data_from.collections:
            data_to.collections = [collection_name]
        elif data_from.collections:
            data_to.collections = [data_from.collections[0]]

    appended_col = data_to.collections[0]
    objs = list(appended_col.all_objects)

    anchor = bpy.data.objects.new(name, None)
    anchor.empty_display_type = "PLAIN_AXES"
    anchor.empty_display_size = 0.1
    target_col.objects.link(anchor)

    top_level = [o for o in objs if o.parent is None or o.parent not in objs]
    for o in objs:
        if o.type in ("CAMERA", "LIGHT"):
            bpy.data.objects.remove(o, do_unlink=True)
            continue
        link_object(o, target_col)

    objs = [o for o in objs if o.name in bpy.data.objects]
    top_level = [o for o in top_level if o.name in bpy.data.objects]

    bpy.context.view_layer.update()
    meshes = [o for o in objs if o.type == "MESH"]
    if meshes:
        min_v = Vector((1e9, 1e9, 1e9))
        max_v = Vector((-1e9, -1e9, -1e9))
        for m in meshes:
            for corner in m.bound_box:
                wc = m.matrix_world @ Vector(corner)
                min_v.x = min(min_v.x, wc.x)
                min_v.y = min(min_v.y, wc.y)
                min_v.z = min(min_v.z, wc.z)
                max_v.x = max(max_v.x, wc.x)
                max_v.y = max(max_v.y, wc.y)
                max_v.z = max(max_v.z, wc.z)

        dims = max_v - min_v
        scale_factor = (target_height / dims.z) if (target_height and dims.z > 1e-4) else 1.0
        center_xy = Vector(((min_v.x + max_v.x) * 0.5, (min_v.y + max_v.y) * 0.5, min_v.z))
        for obj in top_level:
            world_mat = obj.matrix_world.copy()
            obj.parent = anchor
            obj.matrix_basis = Matrix.Scale(scale_factor, 4) @ Matrix.Translation(-center_xy) @ world_mat

    bpy.data.collections.remove(appended_col)
    anchor.rotation_euler = (0.0, 0.0, math.radians(rotation_z_deg))
    lx, ly, lz = location
    anchor.location = (lx, ly, ground_z if ground_z is not None else lz)
    bpy.context.view_layer.update()
    return anchor
