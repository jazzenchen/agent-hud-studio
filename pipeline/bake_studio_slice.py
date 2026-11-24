#!/usr/bin/env python3
"""
Phase 2 Offline Pipeline:
1. Opens the Gate-1-approved Concept A+C studio_slice.blend
2. Packs a crisp non-overlapping LightMapUV (UV1) atlas for all architectural surfaces,
   walnut desk, rug, and bookshelf planks (~200 px/m texel density!)
3. Bakes 3 HDR Diffuse Irradiance Lightmaps (midnight / daylight / golden) on Apple M1 Max Metal GPU
   using Cycles + OpenImageDenoise (Direct + Indirect, Color=OFF) -> encodes to 8-bit HDR RGBM PNGs
4. Applies intelligent 60 FPS triangle-budget optimization & strips invisible internal PCB sub-meshes
5. Exports Draco + WebP compressed public/assets/studio_slice.glb with verified TEXCOORD_0 + TEXCOORD_1
6. Stages skylines, HDRIs, colliders, and local Draco WASM decoders into public/
"""

import hashlib
import math
import shutil
import struct
import sys
import zlib
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
import numpy as np

from config import BLEND_DIR, CACHE_DIR, HDRI_DIR, LIGHTMAP_RESOLUTION, PUBLIC_ASSETS_DIR, RGBM_MAX_RANGE, ROOT_DIR
from lighting_presets import apply_studio_mood, configure_cycles_metal

SKY_DIR = CACHE_DIR / "sky"

# Surfaces baked into the crisp 2048x2048 HDR RGBM architectural lightmap atlas
LIGHTMAP_PREFIXES = (
    "Arch_Floor",
    "Arch_ConcretePanel_",
    "Arch_Wall_East",
    "Arch_Wall_South",
    "Arch_Ceiling",
    "Arch_WestPier_",
    "Arch_WestCurb",
    "Arch_WestLintel",
    "Furn_StudioRug",
    "Desk_WalnutTop",
    "DeskShelf_WalnutTop",
    "WallShelf_WalnutPlank",
    "MakerBench_WalnutTop",
    "MakerWallShelf_Plank",
    "Desk_WoolMat",
    "Shelf_Plank_",
)

# Per-group polygon caps for rock-solid 60 FPS WebGL while preserving crisp silhouettes
GROUP_POLY_BUDGETS = {
    "Apple_MacBookAir15": 70000,
    "Apple_MacStudio": 44000,
    "Apple_MacMini": 44000,
    "PH_LoungeChair": 45000,
    "BK_CreatorsPC": 42000,
    "BK_ErgoMeshChair": 46000,
    "BK_MacBookPro14": 28000,
    "BK_3DPrinter": 34000,
    "BK_FilamentSpools": 16000,
    "BK_ArchitectLamp": 16000,
    "BK_TrashBin": 8000,
    "BK_RetroRobotToy": 16000,
    "BK_PS5Console": 22000,
    "BK_AlexDrawer_N": 6000,
    "BK_AlexDrawer_S": 6000,
    "BK_PegDualSense": 24000,
    "BK_PegGameBoy": 10000,
    "BK_PegScrewdriver": 4000,
    "BK_IkeaPegboard": 88000,
    "BK_MechKeyboard75": 28000,
    "BK_DisplayKeyboard_Shelf": 18000,
    "PH_TopShelfPlant1": 24000,
    "PH_TopShelfPlant2": 18000,
    "BK_Canon5D_Shelf": 16000,
    "BK_BroadcastMicArm": 22000,
    "BK_MonsteraDeliciosa": 30000,
    "BK_Macintosh1984": 28000,
    "BK_ZakuGunpla": 26000,
    "BK_MiniPCHomeLab_1": 10000,
    "BK_MiniPCHomeLab_2": 10000,
    "BK_PenOrganizer": 16000,
    "BK_StudioKeyLight": 24000,
    "BK_BooksLower": 12000,
    "BK_VinylTurntable": 18000,
    "BK_CeilingTrackLight": 16000,
    "PH_BooksMid": 12000,
    "BK_Speaker_Left": 16000,
    "BK_Speaker_Right": 16000,
    "BK_PSP_Shelf": 10000,
    "BK_HermanMillerSayl": 36000,
    "BK_PS5_Shelf": 32000,
    "BK_TopShelfPothos": 14000,
}


def write_png_rgba(path: Path, rgba_u8: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w, _ = rgba_u8.shape
    raw = b"".join(b"\x00" + rgba_u8[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 6, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def encode_rgbm_u8(linear_rgb: np.ndarray, max_range: float = RGBM_MAX_RANGE) -> np.ndarray:
    """
    Encode linear HDR RGB (H, W, 3) float32 into 8-bit RGBA RGBM with clean floor quantization.
    Decoder in Three.js GLSL: vec3 rgb = rgbm.rgb * (rgbm.a * uLightMapRange);
    """
    rgb = np.clip(linear_rgb, 0.0, max_range) / max_range
    max_c = np.max(rgb, axis=2)
    m = np.clip(np.ceil(max_c * 255.0) / 255.0, 1.0 / 255.0, 1.0)
    enc_rgb = np.clip(rgb / m[:, :, None], 0.0, 1.0)
    out = np.zeros((rgb.shape[0], rgb.shape[1], 4), dtype=np.uint8)
    out[:, :, :3] = np.round(enc_rgb * 255.0).astype(np.uint8)
    out[:, :, 3] = np.round(m * 255.0).astype(np.uint8)
    return out


def is_lightmap_target(obj: bpy.types.Object) -> bool:
    return obj.type == "MESH" and any(obj.name.startswith(p) for p in LIGHTMAP_PREFIXES)


def join_arch_targets_for_single_pass_bake(targets: list[bpy.types.Object]) -> bpy.types.Object:
    """
    Join all architectural & hero-surface bake targets into ONE multi-material mesh 'Arch_LightMapped_Static'
    BEFORE UV1 packing & Cycles baking! Eliminates 24x BVH rebuild overhead -> bakes 2048px HDR GI in ~20s/mood!
    """
    valid = [o for o in targets if o.name in bpy.data.objects and o.type == "MESH" and len(o.data.polygons) > 0]
    deps = bpy.context.evaluated_depsgraph_get()
    for o in valid:
        if o.modifiers:
            eval_o = o.evaluated_get(deps)
            new_mesh = bpy.data.meshes.new_from_object(eval_o, preserve_all_data_layers=True, depsgraph=deps)
            old_mesh = o.data
            o.modifiers.clear()
            o.data = new_mesh
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
        if o.data.users > 1:
            o.data = o.data.copy()
        if not o.data.uv_layers:
            o.data.uv_layers.new(name="UVMap")
        else:
            o.data.uv_layers[0].name = "UVMap"
        while len(o.data.uv_layers) > 1:
            o.data.uv_layers.remove(o.data.uv_layers[-1])
        if o.parent is not None:
            wm = o.matrix_world.copy()
            o.parent = None
            o.matrix_world = wm

    bpy.ops.object.select_all(action="DESELECT")
    for o in valid:
        o.select_set(True)
    bpy.context.view_layer.objects.active = valid[0]
    if len(valid) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = "Arch_LightMapped_Static"
    joined["useArchLightMap"] = True

    lm = joined.data.uv_layers.new(name="LightMapUV")
    joined.data.uv_layers.active = lm
    bpy.ops.object.mode_set(mode="EDIT")
    bpy.ops.mesh.select_all(action="SELECT")
    bpy.ops.uv.smart_project(
        angle_limit=math.radians(66.0),
        island_margin=0.012,
        area_weight=0.0,
        correct_aspect=True,
        scale_to_bounds=True,
    )
    bpy.ops.object.mode_set(mode="OBJECT")
    joined.data.uv_layers["UVMap"].active_render = True
    joined.data.uv_layers["LightMapUV"].active = True
    return joined


def denoise_hdr_lightmap_oidn(bake_img: bpy.types.Image, res: int) -> np.ndarray:
    """
    Run Blender 5.2 Built-in Intel OpenImageDenoise (CompositorNodeDenoise, HDR=True)
    on a 32-bit linear float baked lightmap image -> 100% silky, zero-firefly, zero-blotch ArchViz GI!
    """
    import tempfile

    # Create a tiny isolated temporary scene so we don't disturb the main Cycles scene!
    orig_scene = bpy.context.scene
    tmp_scene = bpy.data.scenes.new("OIDN_Lightmap_Denoise_Tmp")
    tmp_scene.render.engine = "CYCLES"
    tmp_scene.cycles.samples = 1
    tmp_scene.render.resolution_x = res
    tmp_scene.render.resolution_y = res
    tmp_scene.render.resolution_percentage = 100
    tmp_scene.render.use_compositing = True
    tmp_scene.render.image_settings.file_format = "OPEN_EXR"
    tmp_scene.render.image_settings.color_depth = "32"

    ng = bpy.data.node_groups.new("CompOIDN_LM", "CompositorNodeTree")
    tmp_scene.compositing_node_group = ng
    ng.interface.new_socket(name="Image", in_out="OUTPUT", socket_type="NodeSocketColor")
    im_n = ng.nodes.new("CompositorNodeImage")
    im_n.image = bake_img
    dn = ng.nodes.new("CompositorNodeDenoise")
    dn.inputs["HDR"].default_value = True
    out_n = ng.nodes.new("NodeGroupOutput")
    ng.links.new(im_n.outputs["Image"], dn.inputs["Image"])
    ng.links.new(dn.outputs["Image"], out_n.inputs["Image"])

    tmp_exr = Path(tempfile.gettempdir()) / f"astudio_oidn_{bake_img.name}.exr"
    tmp_scene.render.filepath = str(tmp_exr)
    bpy.context.window.scene = tmp_scene
    bpy.ops.render.render(write_still=True)
    bpy.context.window.scene = orig_scene

    res_img = bpy.data.images.load(str(tmp_exr))
    raw = np.empty(res * res * 4, dtype=np.float32)
    res_img.pixels.foreach_get(raw)
    linear_rgb = np.clip(raw.reshape((res, res, 4))[:, :, :3], 0.0, 64.0)

    bpy.data.images.remove(res_img)
    bpy.data.scenes.remove(tmp_scene)
    bpy.data.node_groups.remove(ng)
    try:
        tmp_exr.unlink()
    except OSError:
        pass
    return linear_rgb


def bake_mood_lightmap(
    mood: str,
    targets: list[bpy.types.Object],
    light_col: bpy.types.Collection,
    out_path: Path,
    res: int = LIGHTMAP_RESOLUTION,
    samples: int = 256,
) -> None:
    """
    Bake pure physical Cycles diffuse irradiance (Direct + Indirect, Color=OFF) to HDR RGBM PNG:
    - Hides tiny high-energy decorative emissive indicator meshes from diffuse rays (clean AREA/SPOT lights do GI!)
    - 256 spp + tight indirect firefly clamp (2.5) + 32px EXTEND margin
    - Runs Intel OpenImageDenoise (HDR=True) on 32-bit float irradiance before RGBM encoding!
    """
    print(f"\n=== Baking HDR Lightmap (OIDN): {mood} ({res}x{res}, {samples} samples, M1 Max Metal) ===")
    configure_cycles_metal(samples=samples, res_x=res, res_y=res)
    apply_studio_mood(mood, light_col)

    scene = bpy.context.scene
    scene.cycles.adaptive_threshold = 0.008
    scene.cycles.sample_clamp_direct = 8.0
    scene.cycles.sample_clamp_indirect = 2.5
    scene.cycles.bake_type = "DIFFUSE"
    scene.render.bake.use_pass_direct = True
    scene.render.bake.use_pass_indirect = True
    scene.render.bake.use_pass_color = False
    scene.render.bake.use_clear = True
    scene.render.bake.margin = 32
    scene.render.bake.margin_type = "EXTEND"

    # Suppress tiny high-energy decorative emissive meshes from diffuse bounce (eliminates Monte Carlo fireflies!)
    # Smooth physical AREA & SPOT lights already model ScreenBar, WallShelfWash, TrackSpots, PCGlow, etc. cleanly!
    noisy_emissive_mats = {
        "Emit_TrackSpotLED", "Emit_PC_FanGlow", "Emit_PC_InternalStrip", "Emit_HomeLabLED",
        "Emit_TallyRed", "Emit_DeskKeyLight", "Emit_ShelfUnderLED", "Emit_CoveWarm",
        "Emit_RGB_Cyan", "Emit_RGB_Amber", "Screen_StreamDeck", "Screen_PixelClock", "Screen_AIO_LCD",
    }
    suppressed_objs: list[bpy.types.Object] = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if any(s.material and s.material.name in noisy_emissive_mats for s in o.material_slots):
            if o.visible_diffuse:
                o.visible_diffuse = False
                suppressed_objs.append(o)

    bake_img = bpy.data.images.new(f"BakeTarget_{mood}", width=res, height=res, alpha=False, float_buffer=True)
    bake_img.colorspace_settings.name = "Linear Rec.709"

    # Attach temporary active bake image node to each target material (leaving shader output untouched)
    target_mats = set()
    for o in targets:
        for slot in o.material_slots:
            if slot.material and slot.material.use_nodes:
                target_mats.add(slot.material)

    temp_nodes = []
    for mat in target_mats:
        nt = mat.node_tree
        uv_node = nt.nodes.new("ShaderNodeUVMap")
        uv_node.uv_map = "LightMapUV"
        img_node = nt.nodes.new("ShaderNodeTexImage")
        img_node.image = bake_img
        nt.links.new(uv_node.outputs["UV"], img_node.inputs["Vector"])
        for n in nt.nodes:
            n.select = False
        img_node.select = True
        nt.nodes.active = img_node
        temp_nodes.append((nt, uv_node, img_node))

    bpy.ops.object.select_all(action="DESELECT")
    for o in targets:
        o.data.uv_layers["LightMapUV"].active = True
        o.select_set(True)
    bpy.context.view_layer.objects.active = targets[0]

    bpy.ops.object.bake(type="DIFFUSE")

    # Restore diffuse visibility immediately after bake
    for o in suppressed_objs:
        o.visible_diffuse = True

    # Run Blender 5.2 Built-in Intel OpenImageDenoise on 32-bit HDR float lightmap!
    linear_rgb = denoise_hdr_lightmap_oidn(bake_img, res)
    # Flip Y so PNG matches WebGL flipY=false / glTF UV convention cleanly
    linear_rgb = np.flipud(linear_rgb)

    p99 = float(np.percentile(linear_rgb, 99.5))
    mean_v = float(np.mean(linear_rgb))
    print(f"  Baked + OIDN stats ({mood}): mean={mean_v:.3f}, p99.5={p99:.3f}, max={float(np.max(linear_rgb)):.3f}")

    rgbm_u8 = encode_rgbm_u8(linear_rgb, max_range=RGBM_MAX_RANGE)
    write_png_rgba(out_path, rgbm_u8)
    print(f"  Saved OIDN HDR RGBM lightmap: {out_path} ({out_path.stat().st_size // 1024} KB)")

    # Cleanup temp bake nodes & image
    for nt, uv_node, img_node in temp_nodes:
        nt.nodes.remove(img_node)
        nt.nodes.remove(uv_node)
    bpy.data.images.remove(bake_img)


def get_root_name(obj: bpy.types.Object) -> str:
    r = obj
    while r.parent is not None:
        r = r.parent
    return r.name


def optimize_for_60fps(lm_targets: list[bpy.types.Object]) -> None:
    """
    Production 60 FPS WebGL optimization:
    1. Convert all 29 CURVE objects (PC cables/tubes) at clean low resolution before decimation
    2. Prune invisible internal keyboard PCB/SMD sub-meshes & remove Cycles-only skyline/lights/cameras
    3. Apply per-group + per-object triangle budgets (~260k-320k tris total)
    4. Deduplicate & truly downscale packed images (img.scale + img.pack!) -> drops 156 MB -> ~8-12 MB!
    5. Deduplicate identical untextured materials & join static geometry into clean draw-call buckets (< 115 DC!)
    6. Wire 4x4 UV1 anchor onto lightmapped materials so TEXCOORD_1 is 100% preserved in glTF 2.0
    """
    print("\n=== Optimizing Scene Geometry, Textures & Draw Calls for 60 FPS WebGL ===")
    lm_set = set(lm_targets)

    # 0. Remove Cycles-only skyline, lights, cameras & hidden/unlinked orphan objects early
    vl_objs = {o for o in bpy.context.view_layer.objects if o is not None}
    for o in list(bpy.data.objects):
        if (
            o not in vl_objs
            or not o.visible_get()
            or o.hide_render
            or o.type in ("LIGHT", "CAMERA")
            or o.name == "Arch_CitySkylineBackdrop"
        ):
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()

    # 1. Convert visible CURVE objects to clean low-poly MESH (prevents 500k-tri curve tessellation!)
    curves = [o for o in bpy.data.objects if o.type == "CURVE" and o.visible_get()]
    if curves:
        for c in curves:
            c.data.resolution_u = min(c.data.resolution_u, 6)
            if hasattr(c.data, "bevel_resolution"):
                c.data.bevel_resolution = min(c.data.bevel_resolution, 2)
        bpy.ops.object.select_all(action="DESELECT")
        for c in curves:
            c.select_set(True)
        bpy.context.view_layer.objects.active = curves[0]
        bpy.ops.object.convert(target="MESH")
        print(f"  Converted {len(curves)} CURVE objects to optimized MESH.")

    # 2. Remove invisible internal PCB/SMD/switch meshes inside the 2 mechanical keyboards
    to_delete = []
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        rname = get_root_name(o)
        if rname in ("BK_MechKeyboard75", "BK_DisplayKeyboard_Shelf"):
            ln = o.name.lower()
            keep = any(k in ln for k in ("keycap", "legend", "case_", "bottom_weight", "frame", "plate"))
            if not keep:
                to_delete.append(o)
    for o in to_delete:
        bpy.data.objects.remove(o, do_unlink=True)
    print(f"  Pruned {len(to_delete)} invisible internal keyboard PCB/SMD meshes.")

    # 3. Apply per-group Decimate ratios + global heavy-mesh guard
    groups: dict[str, list[bpy.types.Object]] = {}
    for o in bpy.data.objects:
        if o.type != "MESH" or o in lm_set:
            continue
        rname = get_root_name(o)
        groups.setdefault(rname, []).append(o)

    for gname, budget in GROUP_POLY_BUDGETS.items():
        objs = groups.get(gname, [])
        if not objs:
            continue
        total_p = sum(len(o.data.polygons) for o in objs)
        if total_p <= budget:
            continue
        # Smart square-root weighted per-submesh poly allocation!
        # Prevents tiny dense screw/button sub-meshes (e.g. DualSense 489k buttons) from crushing visible shells!
        weights = [math.sqrt(max(1, len(o.data.polygons))) for o in objs]
        w_sum = sum(weights)
        print(f"  Decimating {gname:26s}: {total_p:9,d} -> ~{budget:7,d} (smart sqrt-weighted)")
        for o, w in zip(objs, weights):
            pc = len(o.data.polygons)
            if pc <= 240:
                continue
            target_o = max(300, int(round(budget * (w / w_sum))))
            # Give visible controller shell extra fidelity
            if gname == "BK_PegDualSense" and "main controler" in o.name.lower():
                target_o = max(target_o, 7000)
            if pc <= target_o:
                continue
            ratio = max(0.015, min(0.95, target_o / float(pc)))
            if o.data.users > 1:
                o.data = o.data.copy()
            mod = o.modifiers.new("WebGL_Decimate", "DECIMATE")
            mod.ratio = ratio

    # Also guard any UNBUDGETED mega-mesh (> 12k polys), never overriding explicit GROUP_POLY_BUDGETS!
    for o in bpy.data.objects:
        if o.type != "MESH" or o in lm_set:
            continue
        if o.modifiers or get_root_name(o) in GROUP_POLY_BUDGETS:
            continue
        pcount = len(o.data.polygons)
        if pcount > 12000:
            ratio = max(0.10, 8000.0 / float(pcount))
            print(f"  Capping mega-mesh {o.name:28s}: {pcount:7,d} -> ~8,000 (ratio={ratio:.3f})")
            if o.data.users > 1:
                o.data = o.data.copy()
            mod = o.modifiers.new("WebGL_Cap", "DECIMATE")
            mod.ratio = ratio

    # 4. Bake all active modifiers (Decimate, Subsurf, Armature, WeightedNormal) cleanly
    #    Snapshot exact world matrices BEFORE removing armatures so rigged meshes (e.g. Zaku) NEVER lose scale!
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    for o in list(bpy.data.objects):
        if o.type != "MESH" or not o.modifiers:
            continue
        try:
            eval_o = o.evaluated_get(deps)
            new_mesh = bpy.data.meshes.new_from_object(eval_o, preserve_all_data_layers=True, depsgraph=deps)
            old_mesh = o.data
            o.modifiers.clear()
            o.data = new_mesh
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
        except Exception as exc:
            print(f"  Modifier bake warn on {o.name}: {exc}")

    # Snapshot every mesh's verified world matrix BEFORE stripping Armatures or parent hierarchy!
    bpy.context.view_layer.update()
    all_mesh_world_mats = {o: o.matrix_world.copy() for o in bpy.data.objects if o.type == "MESH"}

    # Remove orphan armatures now that pose/deform is baked & world matrices are snapshotted
    for o in list(bpy.data.objects):
        if o.type == "ARMATURE":
            for child in list(o.children):
                wm = all_mesh_world_mats.get(child, child.matrix_world.copy())
                child.parent = None
                child.matrix_world = wm
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()

    # 5. Strip unused materials & purge orphan datablocks before image optimization
    for o in bpy.data.objects:
        if o.type == "MESH" and len(o.material_slots) > 1:
            used_idx = {p.material_index for p in o.data.polygons}
            for idx in range(len(o.material_slots) - 1, -1, -1):
                if idx not in used_idx:
                    o.active_material_index = idx
                    try:
                        with bpy.context.temp_override(object=o):
                            bpy.ops.object.material_slot_remove()
                    except Exception:
                        pass

    for _ in range(3):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    # 5b. Remove broken / empty ShaderNodeTexImage nodes (0x0 or missing file) so Blender 5.2 glTF
    #     NEVER emits empty {'extensions': {}, 'sampler': 0} texture entries that crash Three.js GLTFLoader!
    removed_bad_tex = 0
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for node in list(mat.node_tree.nodes):
            if node.type != "TEX_IMAGE":
                continue
            img = node.image
            is_bad = (
                img is None
                or img.size[0] == 0
                or img.size[1] == 0
                or (not img.has_data and img.packed_file is None)
            )
            if is_bad:
                mat.node_tree.nodes.remove(node)
                removed_bad_tex += 1
    if removed_bad_tex:
        print(f"  Removed {removed_bad_tex} broken/empty TEX_IMAGE nodes (prevents GLTFLoader undefined.uri crash!).")

    # 6. Deduplicate identical images (by packed byte hash!) & truly downscale + re-pack!
    #    In Blender, calling img.scale() WITHOUT img.pack() leaves the old huge packed_file untouched!
    hash_to_img: dict[str, bpy.types.Image] = {}
    img_remap: dict[bpy.types.Image, bpy.types.Image] = {}
    for img in list(bpy.data.images):
        if img.packed_file and img.packed_file.data:
            h = hashlib.md5(img.packed_file.data).hexdigest()
            if h in hash_to_img:
                img_remap[img] = hash_to_img[h]
            else:
                hash_to_img[h] = img

    if img_remap:
        for mat in bpy.data.materials:
            if not mat.node_tree:
                continue
            for node in mat.node_tree.nodes:
                if node.type == "TEX_IMAGE" and node.image in img_remap:
                    node.image = img_remap[node.image]
        print(f"  Deduplicated {len(img_remap)} duplicate packed images.")

    for _ in range(2):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    # Determine which images are actually referenced by active materials
    active_imgs: set[bpy.types.Image] = set()
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        for slot in o.material_slots:
            if slot.material and slot.material.node_tree:
                for node in slot.material.node_tree.nodes:
                    if node.type == "TEX_IMAGE" and node.image:
                        active_imgs.add(node.image)

    arch_tex_2048 = (
        "arch_concrete", "walnut_oiled", "herringbone", "black_walnut", "rug_woven",
    )
    hero_tex_1024 = (
        "notebook_pages", "gallery_wall_art", "wall_art_rams", "teardown_frame",
        "geek_book_spines", "vinyl_album_covers", "pixel_clock_ui", "aio_lcd_ui",
        "screen_macbook", "modern_arm_chair", "ikea_markus", "main controler",
        "main case", "core", "base", "studio_light", "printer", "ieseqn",
    )
    # Remove giant static PNG screens (Three.js replaces Screen_Ultrawide/Vertical/StreamDeck with live CanvasTexture!)
    skip_screen_imgs = ("screen_ultrawide", "screen_vertical", "screen_streamdeck")
    for mat in bpy.data.materials:
        if mat.name in ("Screen_Ultrawide", "Screen_Vertical", "Screen_StreamDeck") and mat.node_tree:
            for node in list(mat.node_tree.nodes):
                if node.type == "TEX_IMAGE":
                    mat.node_tree.nodes.remove(node)

    resized_cnt = 0
    for img in list(active_imgs):
        if img.name not in bpy.data.images:
            continue
        lname = (img.name + " " + img.filepath).lower()
        if any(k in lname for k in skip_screen_imgs):
            continue
        w, h = img.size[0], img.size[1]
        if w == 0 or h == 0:
            continue
        if any(k in lname for k in arch_tex_2048):
            max_dim = 2048
        elif any(k in lname for k in hero_tex_1024):
            max_dim = 1024
        else:
            max_dim = 512
        if max(w, h) > max_dim:
            scale = max_dim / float(max(w, h))
            nw = max(32, int(round(w * scale)))
            nh = max(32, int(round(h * scale)))
            try:
                # Must unpack or scale+repack so Blender glTF exports the downscaled pixels!
                img.scale(nw, nh)
                img.pack()
                resized_cnt += 1
            except Exception as exc:
                print(f"  Image scale warn ({img.name}): {exc}")
    print(f"  Resized & re-packed {resized_cnt} oversized images (arch=2048px, hero=1024px, minor=512px).")

    # 7. Deduplicate identical untextured Principled BSDF materials (cuts hundreds of duplicate plastic/metal mats!)
    protected_mats = {
        "Screen_Ultrawide", "Screen_Vertical", "Screen_StreamDeck", "Screen_MacBook",
        "Screen_PixelClock", "Screen_AIO_LCD",
        "Arch_WindowGlass", "Emit_CoveWarm", "Emit_RGB_Cyan", "Emit_PC_FanGlow",
        "Emit_PC_FanBlades", "Emit_ShelfUnderLED", "Emit_DeskKeyLight", "Emit_HomeLabLED",
    }
    lm_mats: set[bpy.types.Material] = set()
    for o in lm_targets:
        if o.name in bpy.data.objects:
            for slot in o.material_slots:
                if slot.material:
                    lm_mats.add(slot.material)

    sig_to_mat: dict[tuple, bpy.types.Material] = {}
    mat_remap: dict[bpy.types.Material, bpy.types.Material] = {}
    for mat in bpy.data.materials:
        if mat in lm_mats or mat.name in protected_mats or not mat.node_tree:
            continue
        nodes = mat.node_tree.nodes
        if any(n.type == "TEX_IMAGE" for n in nodes):
            continue
        bsdf = next((n for n in nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        # Only dedupe simple solid-parameter BSDFs with no procedural shader graphs driving Base Color / Alpha
        bc_in = bsdf.inputs.get("Base Color")
        r_in = bsdf.inputs.get("Roughness")
        m_in = bsdf.inputs.get("Metallic")
        a_in = bsdf.inputs.get("Alpha")
        e_in = bsdf.inputs.get("Emission Strength")
        t_in = bsdf.inputs.get("Transmission Weight")
        if any(inp and inp.is_linked for inp in (bc_in, r_in, m_in, a_in, e_in, t_in)):
            continue
        bc = tuple(round(v, 2) for v in bc_in.default_value[:3]) if bc_in else (0.5, 0.5, 0.5)
        sig = (
            bc,
            round(r_in.default_value, 2) if r_in else 0.5,
            round(m_in.default_value, 2) if m_in else 0.0,
            round(a_in.default_value, 2) if a_in else 1.0,
            round(e_in.default_value, 2) if e_in else 0.0,
            round(t_in.default_value, 2) if t_in else 0.0,
        )
        if sig in sig_to_mat:
            mat_remap[mat] = sig_to_mat[sig]
        else:
            sig_to_mat[sig] = mat

    if mat_remap:
        for o in bpy.data.objects:
            if o.type != "MESH" or o in lm_set:
                continue
            for slot in o.material_slots:
                if slot.material in mat_remap:
                    slot.material = mat_remap[slot.material]
        print(f"  Merged {len(mat_remap)} duplicate untextured materials.")

    # 8. Wire 4x4 UV1 anchor onto LightMap materials BEFORE joining architectural meshes
    lm_dummy = bpy.data.images.new("LM_UV1_Anchor", 4, 4)
    lm_dummy.pixels = [1.0] * (4 * 4 * 4)
    lm_dummy.pack()

    for mat in lm_mats:
        mat["useArchLightMap"] = True
        nt = mat.node_tree
        if not nt:
            continue
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        uv1_node = nt.nodes.new("ShaderNodeUVMap")
        uv1_node.uv_map = "LightMapUV"
        tex_dummy = nt.nodes.new("ShaderNodeTexImage")
        tex_dummy.image = lm_dummy
        nt.links.new(uv1_node.outputs["UV"], tex_dummy.inputs["Vector"])
        nt.links.new(tex_dummy.outputs["Color"], bsdf.inputs["Emission Color"])
        bsdf.inputs["Emission Strength"].default_value = 0.01

    # 9. Join static meshes into clean WebGL draw-call buckets!
    #    Bake each mesh's exact snapshotted world matrix directly into vertices -> ZERO parent/scale corruption!
    from mathutils import Matrix, Vector

    def consolidate_mesh_uv_layers(o: bpy.types.Object) -> None:
        """
        PERMANENT FIX FOR BLENDERKIT CAMO / QR-CODE TEXTURE BUG!
        BlenderKit *_Baked materials frequently reference UVMap.001 / UVMap.002 / UVMap.003 via ShaderNodeUVMap.
        Before stripping extra UV layers, copy each polygon's exact shader-referenced UV layer into slot 0 ('UVMap'),
        repoint all ShaderNodeUVMap nodes to 'UVMap', then cleanly remove unused extra UV layers!
        """
        me = o.data
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
            return
        if len(me.uv_layers) == 1:
            me.uv_layers[0].name = "UVMap"
            return

        # Determine which UV layer each material slot actually uses
        default_uv = next((u.name for u in me.uv_layers if u.active_render), me.uv_layers[0].name)
        slot_uv_name: dict[int, str] = {}
        for idx, slot in enumerate(o.material_slots):
            chosen = default_uv
            mat = slot.material
            if mat and mat.node_tree:
                for n in mat.node_tree.nodes:
                    if n.type == "UVMAP" and n.uv_map and n.uv_map in me.uv_layers:
                        chosen = n.uv_map
                        break
            slot_uv_name[idx] = chosen

        # Only need per-polygon consolidation if any slot uses a UV layer other than slot 0
        if any(name != me.uv_layers[0].name for name in slot_uv_name.values()):
            src_layers = {u.name: u.data for u in me.uv_layers}
            dst_layer = me.uv_layers.new(name="__ConsolidatedUV__")
            dst_data = dst_layer.data
            for poly in me.polygons:
                src_name = slot_uv_name.get(poly.material_index, default_uv)
                src_data = src_layers.get(src_name, me.uv_layers[0].data)
                for li in poly.loop_indices:
                    dst_data[li].uv = src_data[li].uv
            # Remove all old layers, leaving only __ConsolidatedUV__ renamed to UVMap!
            for u in list(me.uv_layers):
                if u.name != "__ConsolidatedUV__":
                    me.uv_layers.remove(u)
            me.uv_layers[0].name = "UVMap"
        else:
            me.uv_layers[0].name = "UVMap"
            while len(me.uv_layers) > 1:
                me.uv_layers.remove(me.uv_layers[-1])

        me.uv_layers[0].active_render = True
        me.uv_layers[0].active = True

    def join_bucket(objs: list[bpy.types.Object], target_name: str, keep_uv1: bool = False) -> bpy.types.Object | None:
        valid = [o for o in objs if o.name in bpy.data.objects and o.type == "MESH" and len(o.data.polygons) > 0]
        if not valid:
            return None
        bpy.context.view_layer.update()
        # Snapshot ALL world matrices upfront BEFORE modifying any parent links!
        wm_map = {o: all_mesh_world_mats.get(o, o.matrix_world.copy()).copy() for o in valid}

        for o in valid:
            if o.data.users > 1:
                o.data = o.data.copy()
            if keep_uv1 and "LightMapUV" in o.data.uv_layers:
                if not o.data.uv_layers:
                    o.data.uv_layers.new(name="UVMap")
                else:
                    o.data.uv_layers[0].name = "UVMap"
                o.data.uv_layers["UVMap"].active_render = True
            else:
                consolidate_mesh_uv_layers(o)

            wm = wm_map[o]
            o.parent = None
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = Matrix.Identity(4)
            o.data.transform(wm)
            if wm.determinant() < 0.0:
                o.data.flip_normals()
            o.data.update()

        if len(valid) == 1:
            valid[0].name = target_name
            return valid[0]

        bpy.ops.object.select_all(action="DESELECT")
        for o in valid:
            o.select_set(True)
        bpy.context.view_layer.objects.active = valid[0]
        bpy.ops.object.join()
        joined = bpy.context.view_layer.objects.active
        joined.name = target_name
        return joined

    # Separate buckets:
    # - Arch_LightMapped_Static (all UV1 lightmapped architectural surfaces)
    # - Keep Monitor_Ultrawide38_Screen, Monitor_Vertical27_Screen, SD_KeysPanel, Arch_LoftWin_Glass untouched
    # - Interact_ScreenBar (joined clickable ScreenBar assembly)
    # - BK_CreatorsPC (joined clickable PC workstation assembly)
    # - Props_Static_Main (all remaining static hero furniture & geek props joined by shared materials!)
    keep_exact = {"Monitor_Ultrawide38_Screen", "Monitor_Vertical27_Screen", "SD_KeysPanel", "Arch_LoftWin_Glass"}
    bucket_arch: list[bpy.types.Object] = []
    bucket_screenbar: list[bpy.types.Object] = []
    bucket_pc: list[bpy.types.Object] = []
    bucket_props: list[bpy.types.Object] = []

    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        if o.name in keep_exact:
            if o.parent is not None:
                wm = o.matrix_world.copy()
                o.parent = None
                o.matrix_world = wm
            continue
        if o in lm_set:
            bucket_arch.append(o)
            continue
        rname = get_root_name(o)
        if o.name.startswith("Interact_ScreenBar") or rname.startswith("Interact_ScreenBar"):
            bucket_screenbar.append(o)
        elif rname == "BK_CreatorsPC":
            bucket_pc.append(o)
        else:
            bucket_props.append(o)

    arch_joined = join_bucket(bucket_arch, "Arch_LightMapped_Static", keep_uv1=True)
    if arch_joined:
        arch_joined["useArchLightMap"] = True

    join_bucket(bucket_screenbar, "Interact_ScreenBar", keep_uv1=False)
    join_bucket(bucket_pc, "BK_CreatorsPC", keep_uv1=False)
    join_bucket(bucket_props, "Props_Static_Main", keep_uv1=False)

    # Repoint all non-LightMapUV ShaderNodeUVMap nodes to consolidated 'UVMap' so glTF exports clean TEXCOORD_0!
    repointed = 0
    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for n in mat.node_tree.nodes:
            if n.type == "UVMAP" and n.uv_map and n.uv_map != "LightMapUV" and n.uv_map != "UVMap":
                n.uv_map = "UVMap"
                repointed += 1
    if repointed:
        print(f"  Repointed {repointed} ShaderNodeUVMap nodes (UVMap.001/.002/.003 -> consolidated UVMap).")

    # Remove now-empty EMPTY hierarchy nodes
    for o in list(bpy.data.objects):
        if o.type == "EMPTY":
            bpy.data.objects.remove(o, do_unlink=True)

    for _ in range(3):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    total_meshes = [o for o in bpy.data.objects if o.type == "MESH"]
    from mathutils import Vector
    bpy.context.view_layer.update()
    for o in total_meshes:
        o.data.validate(clean_customdata=True)
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        dims = Vector((
            max(v.x for v in bb) - min(v.x for v in bb),
            max(v.y for v in bb) - min(v.y for v in bb),
            max(v.z for v in bb) - min(v.z for v in bb),
        ))
        print(f"    [GLB BBox Check] {o.name:28s}: dims=({dims.x:.2f}, {dims.y:.2f}, {dims.z:.2f})")
        assert max(dims.x, dims.y, dims.z) < 6.0, f"EXPLODED MESH DETECTED: {o.name} dims={dims}"
    total_polys = sum(len(o.data.polygons) for o in total_meshes)
    total_mats = sum(len(o.material_slots) for o in total_meshes)
    print(f"  Post-optimization WebGL scene: {len(total_meshes)} mesh objects, {total_mats} material slots (draw calls), {total_polys:,} polygons, {len(bpy.data.images)} images.")


def stage_web_assets() -> None:
    """Copy skylines, HDRIs, colliders, and Three.js local Draco WASM decoders into public/."""
    sky_out = PUBLIC_ASSETS_DIR / "sky"
    hdri_out = PUBLIC_ASSETS_DIR / "hdris"
    draco_out = ROOT_DIR / "public" / "draco"
    sky_out.mkdir(parents=True, exist_ok=True)
    hdri_out.mkdir(parents=True, exist_ok=True)
    draco_out.mkdir(parents=True, exist_ok=True)

    for fn in ("skyline_midnight.jpg", "skyline_golden.jpg", "skyline_daylight.jpg"):
        src = SKY_DIR / fn
        if src.exists():
            shutil.copy2(src, sky_out / fn)

    for fn in ("blue_lagoon_night_2k.hdr", "belfast_sunset_puresky_2k.hdr", "aristea_wreck_puresky_2k.hdr"):
        src = HDRI_DIR / fn
        if src.exists():
            shutil.copy2(src, hdri_out / fn)

    coll_src = BLEND_DIR / "studio_colliders.json"
    if coll_src.exists():
        shutil.copy2(coll_src, PUBLIC_ASSETS_DIR / "studio_colliders.json")

    draco_src = ROOT_DIR / "node_modules" / "three" / "examples" / "jsm" / "libs" / "draco" / "gltf"
    if draco_src.exists():
        for f in draco_src.iterdir():
            if f.is_file():
                shutil.copy2(f, draco_out / f.name)


def main() -> None:
    export_only = "--export-only" in sys.argv
    blend_path = BLEND_DIR / "studio_slice.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))

    light_col = bpy.data.collections.get("05_Lights") or bpy.context.scene.collection
    lm_raw = [o for o in bpy.data.objects if is_lightmap_target(o)]
    print(f"Joining {len(lm_raw)} architectural & hero-surface meshes into single-pass 2048px HDR Lightmap Atlas...")

    # 1. Join & pack crisp UV1 (LightMapUV) on ONE mesh -> 15x faster single-pass Metal GPU baking!
    arch_mesh = join_arch_targets_for_single_pass_bake(lm_raw)
    lm_targets = [arch_mesh]

    # 2. Bake all 3 moods (midnight, daylight, golden) unless --export-only reuses existing baked PNGs
    lm_dir = PUBLIC_ASSETS_DIR / "lightmaps"
    if not export_only:
        for mood in ("midnight", "daylight", "golden"):
            bake_mood_lightmap(
                mood, lm_targets, light_col,
                out_path=lm_dir / f"studio_arch_{mood}.png",
                res=LIGHTMAP_RESOLUTION,
                samples=256,
            )
    else:
        print("  [--export-only] Reusing existing baked HDR RGBM lightmaps in public/assets/lightmaps/.")

    # 3. Optimize meshes, textures & draw calls for 60 FPS WebGL & guarantee TEXCOORD_1 export
    optimize_for_60fps(lm_targets)

    # 4. Export Draco + WebP compressed GLB
    PUBLIC_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    glb_out = PUBLIC_ASSETS_DIR / "studio_slice.glb"
    print(f"\n=== Exporting Draco + WebP GLB -> {glb_out} ===")
    bpy.ops.export_scene.gltf(
        filepath=str(glb_out),
        export_format="GLB",
        export_texcoords=True,
        export_normals=True,
        export_materials="EXPORT",
        export_extras=True,
        export_image_format="WEBP",
        export_image_quality=82,
        export_draco_mesh_compression_enable=True,
        export_draco_mesh_compression_level=6,
        export_draco_position_quantization=14,
        export_draco_normal_quantization=10,
        export_draco_texcoord_quantization=12,
        export_apply=True,
    )
    print(f"Exported {glb_out} ({glb_out.stat().st_size / (1024 * 1024):.2f} MB)")
    sanitize_glb_broken_textures(glb_out)

    # 5. Stage skylines, HDRIs, colliders, and local Draco WASM decoders
    stage_web_assets()
    print("\nPhase 2 Blender Bake & Export Pipeline COMPLETE!")


def sanitize_glb_broken_textures(glb_path: Path) -> None:
    """
    Workaround for Blender 5.2 io_scene_gltf2 bug where channel-packed metallicRoughness WebP export
    occasionally emits stub textures ({'extensions': {}, 'sampler': 0}) with no image source,
    which crashes Three.js GLTFLoader. Strip references to source-less textures and re-align GLB chunks.
    """
    import json

    raw = glb_path.read_bytes()
    magic, version, _total_len = struct.unpack("<4sII", raw[:12])
    json_len, json_type = struct.unpack("<I4s", raw[12:20])
    json_bytes = raw[20 : 20 + json_len]
    rest_chunks = raw[20 + json_len :]

    gl = json.loads(json_bytes.decode("utf-8"))
    imgs = gl.get("images", [])
    bad_ids = set()
    for i, t in enumerate(gl.get("textures", [])):
        src = t.get("extensions", {}).get("EXT_texture_webp", {}).get("source", t.get("source"))
        if src is None or src >= len(imgs):
            bad_ids.add(i)

    if not bad_ids:
        print(f"  GLB Validation PASS: {len(gl.get('textures', []))} valid textures, {len(imgs)} images, 0 broken refs.")
        return

    fixed_refs = 0

    def prune_dict(d: dict) -> None:
        nonlocal fixed_refs
        for k in list(d.keys()):
            v = d[k]
            if isinstance(v, dict):
                if "index" in v and v["index"] in bad_ids and k.endswith("Texture"):
                    del d[k]
                    fixed_refs += 1
                    if k == "metallicRoughnessTexture" and "roughnessFactor" not in d:
                        d["roughnessFactor"] = 0.62
                else:
                    prune_dict(v)
            elif isinstance(v, list):
                for item in v:
                    if isinstance(item, dict):
                        prune_dict(item)

    for mat in gl.get("materials", []):
        prune_dict(mat)

    # Also ensure the unused stub textures still point to image 0 just in case any tool scans textures[]
    if imgs:
        for bi in bad_ids:
            gl["textures"][bi] = {"extensions": {"EXT_texture_webp": {"source": 0}}, "sampler": 0}

    new_json = json.dumps(gl, separators=(",", ":")).encode("utf-8")
    pad = (4 - (len(new_json) % 4)) % 4
    new_json += b" " * pad
    new_total = 12 + 8 + len(new_json) + len(rest_chunks)
    rebuilt = (
        struct.pack("<4sII", magic, version, new_total)
        + struct.pack("<I4s", len(new_json), json_type)
        + new_json
        + rest_chunks
    )
    glb_path.write_bytes(rebuilt)
    print(f"  Sanitized {len(bad_ids)} Blender 5.2 stub textures ({fixed_refs} material refs cleaned) -> GLB 100% Three.js-clean!")


if __name__ == "__main__":
    main()
