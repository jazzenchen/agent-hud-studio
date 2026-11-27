"""
Make the master bed: turn the slept-in cloth simulation of the imported bed into a made bed.

The source linen is one mesh of cloth islands that the scene has already split into four material slots
(0 duvet, 1 throw, 2 front pillows, 3 rear shams). The throw is a large blanket left rumpled diagonally across
the duvet, and every island carries sharp sleep creases. `make_bed` removes that throw, irons the creases out of
the duvet and pillows while keeping their overall drape, and lays a flat bed runner across the foot that follows
the duvet's surface and falls a hand's width down each side.
"""

import bmesh
import bpy
from mathutils import Vector
from mathutils.bvhtree import BVHTree

SLOT_DUVET, SLOT_THROW, SLOT_FRONT, SLOT_SHAM = 0, 1, 2, 3


def _iron(bm, slots, iterations, factor=0.5):
    verts = list({v for f in bm.faces if f.material_index in slots for v in f.verts})
    for _ in range(iterations):
        bmesh.ops.smooth_vert(bm, verts=verts, factor=factor, use_axis_x=True, use_axis_y=True, use_axis_z=True)


def _resample(points, count):
    """Even arc-length resampling of a polyline."""
    acc = [0.0]
    for a, b in zip(points, points[1:]):
        acc.append(acc[-1] + (b - a).length)
    out, k = [], 0
    for i in range(count):
        d = acc[-1] * i / (count - 1)
        while k < len(acc) - 2 and acc[k + 1] < d:
            k += 1
        seg = max(1e-9, acc[k + 1] - acc[k])
        out.append(points[k].lerp(points[k + 1], min(1.0, max(0.0, (d - acc[k]) / seg))))
    return out


def make_bed(linen: bpy.types.Object, collection: bpy.types.Collection, runner_from_foot=0.30, runner_width=0.50, side_fall=0.17, stand_off=0.012):
    """Tidy `linen` in place and return the new runner object (parented beside it). Bed length runs along world X,
    head toward +X, as the scene places it."""
    throw_mat = linen.data.materials[SLOT_THROW]
    bm = bmesh.new()
    bm.from_mesh(linen.data)
    bmesh.ops.delete(bm, geom=[f for f in bm.faces if f.material_index == SLOT_THROW], context="FACES")
    _iron(bm, {SLOT_DUVET}, 60)
    _iron(bm, {SLOT_FRONT, SLOT_SHAM}, 10)
    bm.normal_update()
    bm.to_mesh(linen.data)
    linen.data.update()

    mw = linen.matrix_world
    bm.verts.ensure_lookup_table()
    index_of = {v: i for i, v in enumerate(bm.verts)}
    duvet_faces = [f for f in bm.faces if f.material_index == SLOT_DUVET]
    world = [mw @ v.co for v in bm.verts]
    tree = BVHTree.FromPolygons(world, [[index_of[v] for v in f.verts] for f in duvet_faces])
    used = {index_of[v] for f in duvet_faces for v in f.verts}
    xs = [world[i].x for i in used]
    ys = [world[i].y for i in used]
    bm.free()

    x_foot, y_lo, y_hi = min(xs), min(ys), max(ys)
    rows, across = 12, 72
    grid = []
    for r in range(rows + 1):
        x = x_foot + runner_from_foot + runner_width * r / rows
        hits = []
        n = int((y_hi - y_lo) / 0.008)
        for k in range(n + 1):
            y = y_lo + (y_hi - y_lo) * k / n
            loc, nor, _, _ = tree.ray_cast(Vector((x, y, 3.0)), Vector((0, 0, -1)))
            if loc is not None:
                hits.append((loc, nor if nor.z > 0 else -nor))
        if len(hits) < 8:
            continue
        top_z = sorted(h[0].z for h in hits)[len(hits) // 2]
        line = [loc + nor * stand_off for loc, nor in hits if loc.z > top_z - side_fall]
        grid.append(_resample(line, across))

    rb = bmesh.new()
    vgrid = [[rb.verts.new(p) for p in row] for row in grid]
    for a, b in zip(vgrid, vgrid[1:]):
        for j in range(across - 1):
            rb.faces.new((a[j], a[j + 1], b[j + 1], b[j]))
    for _ in range(6):      # a pressed runner: lose what little of the duvet's relief it inherited
        bmesh.ops.smooth_vert(rb, verts=rb.verts[:], factor=0.5, use_axis_x=True, use_axis_y=True, use_axis_z=True)
    bmesh.ops.recalc_face_normals(rb, faces=rb.faces[:])
    me = bpy.data.meshes.new(f"{linen.name}_Runner")
    rb.to_mesh(me)
    rb.free()
    for p in me.polygons:
        p.use_smooth = True
    me.materials.append(throw_mat)
    runner = bpy.data.objects.new(f"{linen.name}_Runner", me)
    collection.objects.link(runner)
    sol = runner.modifiers.new("Solidify", "SOLIDIFY")
    sol.thickness, sol.offset = 0.012, 1.0
    if linen.parent is not None:
        runner.parent = linen.parent
        runner.matrix_parent_inverse = linen.parent.matrix_world.inverted()
    return runner
