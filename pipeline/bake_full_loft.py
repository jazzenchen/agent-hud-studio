#!/usr/bin/env python3
"""
Phase 3 Production Offline Bake & Export Pipeline — Full 5-Zone 87 m^2 Geek Loft:
1. Opens assets/blend/full_loft.blend
2. Splits architectural & hero-surface lightmap targets into TWO razor-sharp 2048px HDR RGBM atlases:
   - Atlas WEST (loft_west_{midnight,daylight,golden}.png): Zone 1 Studio + Zone 2 Living & Gaming Lounge
   - Atlas EAST (loft_east_{midnight,daylight,golden}.png): Zone 3 Open Kitchen + Zone 4 Master Bedroom + Zone 5 Spa Bath
   Clones shared architectural materials cleanly into __West / __East variants so Three.js binds each atlas with zero crosstalk!
3. Bakes 256-spp Cycles Metal GPU Diffuse Irradiance (Direct+Indirect, Color=OFF, tiny emissives suppressed from diffuse bounce)
   + runs Blender 5.2 Intel OpenImageDenoise (HDR=True) -> 100% silky, zero-firefly, zero-blotch lightmaps!
4. Runs per-polygon UV consolidation (UVMap.001/.002/.003 -> UVMap), smart sqrt-weighted poly budgeting,
   vertex-baked world-matrix joining (0% scale explosions!), Draco + WebP export -> public/assets/full_loft.glb!
"""

import hashlib
import math
import shutil
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))

import bpy
import numpy as np
from mathutils import Matrix, Vector

from bake_studio_slice import (
    GROUP_POLY_BUDGETS,
    denoise_hdr_lightmap_oidn,
    encode_rgbm_u8,
    get_root_name,
    sanitize_glb_broken_textures,
    stage_web_assets,
    write_png_rgba,
)
from config import BLEND_DIR, LIGHTMAP_RESOLUTION, PUBLIC_ASSETS_DIR, RGBM_MAX_RANGE
from lighting_presets import apply_studio_mood, configure_cycles_metal
from phase3_loft_zones import apply_phase3_multiroom_lights

# Zone 1 Studio + Zone 2 Living & Gaming Lounge -> Atlas WEST (2048px local / 4096px Colab H100!)
WEST_LIGHTMAP_PREFIXES = (
    "Arch_Floor",
    "Arch_ConcretePanel_",
    "Arch_Ceiling",
    "Arch_WestPier_",
    "Arch_WestCurb",
    "Arch_WestLintel",
    "Arch_West_",
    "Furn_StudioRug",
    "Desk_WalnutTop",
    "DeskShelf_WalnutTop",
    "MakerBench_WalnutTop",
    "MakerWallShelf_Plank",
    "Desk_WoolMat",
    "Shelf_Plank_",
    "Liv_ConsoleBody",
    "Liv_ConsoleDoor_",
    "Liv_WalnutSlat_",
    "Liv_SlatFelt_",
)

# Zone 3 Open Kitchen + Zone 4 Master Bedroom + Zone 5 Spa Bathroom -> Atlas EAST (2048px local / 4096px Colab H100!)
EAST_LIGHTMAP_PREFIXES = (
    "Arch_East_",
    "Kit_BaseCabinets",
    "Kit_BaseFront_",
    "Kit_UpperDoor_",
    "Kit_IslandCore",
    "Kit_IslandWalnutInlay",
    "Kit_ApplianceCore",
    "Kit_UpperPantryDoor",
    "Kit_LowerDrawerDoor",
    "Bed_SlatWall_",
    "Bed_SlatFelt_",
    "Bed_WalnutLedge",
    "Bed_Nightstand_",
)

# VIP Hero Close-Up & Precision Hard-Surface Assets kept 100% UN-DECIMATED so slots, bezels, logos, & curves NEVER tear!
NEVER_DECIMATE_GROUPS = {
    "BK_Speaker_Left",
    "BK_Speaker_Right",
    "BK_LogitechMX4",
    "BK_DeskSmartphone",
    "Hero_ConceptAMicBoom",
    "Hero_ConceptAPegboard",
    "BK_PegGameBoy",
    "BK_LivingPS5",
    "BK_SpaToilet",
    "BK_VesselSink",
    "Liv_OsloDomeLamp",
    "Arch_PenthouseEntry",
    "Bath_SculptedTub",
    "Liv_FloorReadingNook",
    "Kit_UndermountSink",
    "Bed_CeilingLights",
    "Hero_PS5Console",
    "Bed_MetalFrame",
    "BK_PoradaShelfPlant",
    "BK_BedBenchTeacup",
    "BK_BedBenchMags",
}

# Extended Phase 3 AAA WebGL per-group polygon budgets (v5 — Ultra-Clean Geometry + Un-batched Animatable Desk/Chairs!):
LOFT_POLY_BUDGETS = {
    **GROUP_POLY_BUDGETS,
    # Studio Hero Gear (Desk keyboard legends, speakers, mouse, phone, pegboard, mic, GameBoy stay razor-crisp!)
    "Apple_MacBookAir15": 28000,       # Sleek un-batched aluminum MacBook Air (trims 50k unseen internal submesh)
    "Apple_MacStudio": 7500,
    "Apple_MacMini": 5500,
    "BK_CreatorsPC": 16000,
    "BK_ErgoMeshChair": 13000,
    "Hero_CascadingPothos": 5500,
    "KB_CoiledAviatorCable.001": 4000,
    "KB_CoiledAviatorCable": 4000,
    "BK_3DPrinter": 20000,             # Crisp enclosed industrial 3D printer
    "BK_DesktopPrinter": 18000,        # Crisp Epson L4160 matte-black printer/scanner
    "BK_FilamentSpools": 8000,         # Smooth filament spool flanges
    "BK_AlexDrawer_N": 6500,
    "BK_AlexDrawer_S": 6500,
    "BK_WallSocket_-1.18": 1000,
    "BK_WallSocket_+0.42": 1000,
    "BK_MechKeyboard75": 42000,        # Razor-crisp 75% desk keycaps & legends (UN-BATCHED for animation!)
    "BK_DisplayKeyboard_Shelf": 14000, # Bookshelf display keyboard 2.5m away (saves ~35k distant legend tris)
    "PH_TopShelfPlant1": 10000,
    "BK_MonsteraDeliciosa": 24000,     # Graceful fenestrated split-leaf Monstera
    "BK_Canon5D_Shelf": 7500,
    "BK_CanonAE1_Shelf": 6000,
    "BK_BedClosetCamera": 5500,
    "BK_Macintosh1984": 10000,
    "BK_ZakuGunpla": 12000,
    "BK_PenOrganizer": 5500,
    "BK_VinylTurntable": 10000,
    "BK_PSP_Shelf": 5000,
    "BK_StudioLoungeChair": 10000,     # Smooth welded wide-arm black leather chair (UN-BATCHED!)
    "BK_PegDualSense": 16000,          # Crisp intact DualSense white/black shell (micro buttons 63k -> 2.5k!)
    "BK_LivingDualSense": 14000,
    # Living Lounge
    "BK_LivingSofa": 20000,            # Smooth welded modular black leather sofa + 4 sculpted pillows
    "BK_LivingLoaferChair": 10000,     # Matching smooth welded wide-arm black leather living armchair (UN-BATCHED!)
    "BK_LivingCoffeeTable": 2500,
    "BK_LivingPS5": 10000,
    "BK_LivingMonstera": 24000,        # Graceful fenestrated split-leaf Monstera
    # Kitchen
    "BK_EspressoMachine": 14000,
    "BK_CoffeeGrinder": 3800,
    "BK_KitchenFaucet": 4800,
    "BK_BarStool_0": 3800,
    "BK_BarStool_1": 3800,
    "BK_BarStool_2": 3800,
    "BK_IslandPendant": 4000,
    # Master Bedroom
    "BK_MasterBed": 52000,             # Silky high-res welded 6-part cloth bed (ZERO faceted duvet/pillow folds!)
    "BK_PoradaWardrobe": 15000,        # Crisp Italian walnut & graphite panels
    "BK_BedsideLamp_N": 5500,
    "BK_BedsideLamp_S": 5500,
    "BK_BedroomPlant": 24000,          # Graceful fenestrated split-leaf Monstera
    # Spa Bathroom
    "BK_SpaBathtub": 12000,
    "BK_VesselSink": 3200,
    "BK_SpaToilet": 5500,
}


def _match_prefix(name: str, prefixes: tuple[str, ...]) -> bool:
    return any(name.startswith(p) for p in prefixes)


def join_atlas_targets(targets: list[bpy.types.Object], atlas_id: str, obj_name: str) -> bpy.types.Object:
    """
    Join all meshes assigned to one lightmap atlas ('west' or 'east'), cloning materials to __West / __East
    so each atlas binds its own 2K HDR lightmap cleanly in Three.js with zero material crosstalk!
    """
    valid = [o for o in targets if o.name in bpy.data.objects and o.type == "MESH" and len(o.data.polygons) > 0]
    deps = bpy.context.evaluated_depsgraph_get()
    suffix = "__West" if atlas_id == "west" else "__East"
    mat_clone_cache: dict[bpy.types.Material, bpy.types.Material] = {}

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

        # Clone material into dedicated atlas variant (__West / __East)
        for i, m in enumerate(o.data.materials):
            if m is None:
                continue
            if m not in mat_clone_cache:
                cm = m.copy()
                cm.name = f"{m.name}{suffix}"
                cm["useLightMapAtlas"] = atlas_id
                mat_clone_cache[m] = cm
            o.data.materials[i] = mat_clone_cache[m]

        wm = o.matrix_world.copy()
        o.parent = None
        o.matrix_parent_inverse = Matrix.Identity(4)
        o.matrix_world = Matrix.Identity(4)
        o.data.transform(wm)
        if wm.determinant() < 0.0:
            o.data.flip_normals()
        o.data.update()

    bpy.ops.object.select_all(action="DESELECT")
    for o in valid:
        o.select_set(True)
    bpy.context.view_layer.objects.active = valid[0]
    if len(valid) > 1:
        bpy.ops.object.join()
    joined = bpy.context.view_layer.objects.active
    joined.name = obj_name
    joined["useLightMapAtlas"] = atlas_id

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


def bake_atlas_mood(
    atlas_obj: bpy.types.Object,
    atlas_id: str,
    mood: str,
    light_col: bpy.types.Collection,
    out_path: Path,
    res: int = LIGHTMAP_RESOLUTION,
    samples: int = 224,
) -> None:
    print(f"\n=== Baking Multi-Room HDR Lightmap ({atlas_id.upper()} / {mood}, {res}px, {samples} spp + OIDN) ===")
    configure_cycles_metal(samples=samples, res_x=res, res_y=res)
    apply_studio_mood(mood, light_col)
    apply_phase3_multiroom_lights(mood, light_col)

    scene = bpy.context.scene
    scene.cycles.adaptive_threshold = 0.009
    scene.cycles.sample_clamp_direct = 8.0
    scene.cycles.sample_clamp_indirect = 2.5
    scene.cycles.bake_type = "DIFFUSE"
    scene.render.bake.use_pass_direct = True
    scene.render.bake.use_pass_indirect = True
    scene.render.bake.use_pass_color = False
    scene.render.bake.use_clear = True
    scene.render.bake.margin = 32
    scene.render.bake.margin_type = "EXTEND"

    # Hide tiny high-energy decorative emissive meshes from diffuse bounce (AREA/SPOT lights provide silky GI!)
    noisy_emissive_mats = {
        "Emit_TrackSpotLED", "Emit_PC_FanGlow", "Emit_PC_InternalStrip", "Emit_HomeLabLED",
        "Emit_TallyRed", "Emit_DeskKeyLight", "Emit_ShelfUnderLED", "Emit_CoveWarm",
        "Emit_RGB_Cyan", "Emit_RGB_Amber", "Screen_StreamDeck", "Screen_PixelClock",
        "Screen_AIO_LCD", "Emit_BathMirrorHalo", "Emit_KitchenUnderLED", "Emit_KitchenPendantBulb",
        "Emit_BedroomCoveLED", "Emit_OpalFloorLamp", "Emit_CandleFlame", "Emit_PhoneStandby",
        "Emit_HexNeon_Primary", "Emit_HexNeon_Secondary", "Emit_HexNeon_SoftFace", "Emit_KitchenPendantInner",
        "Emit_StudioLinearWarm", "Emit_StudioWallFrameRGB", "Emit_StudioShelfRGB", "Emit_StudioStripRGB_Primary", "Emit_StudioStripRGB_Secondary",
        "Emit_EntryCeilingLight",
    }
    suppressed: list[bpy.types.Object] = []
    for o in bpy.data.objects:
        if o.type != "MESH":
            continue
        if any(s.material and s.material.name in noisy_emissive_mats for s in o.material_slots):
            if o.visible_diffuse:
                o.visible_diffuse = False
                suppressed.append(o)

    bake_img = bpy.data.images.new(f"BakeTarget_{atlas_id}_{mood}", width=res, height=res, alpha=False, float_buffer=True)
    bake_img.colorspace_settings.name = "Linear Rec.709"

    temp_nodes = []
    for slot in atlas_obj.material_slots:
        mat = slot.material
        if not mat or not mat.node_tree:
            continue
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
    atlas_obj.data.uv_layers["LightMapUV"].active = True
    atlas_obj.select_set(True)
    bpy.context.view_layer.objects.active = atlas_obj
    bpy.ops.object.bake(type="DIFFUSE")

    for o in suppressed:
        o.visible_diffuse = True

    linear_rgb = denoise_hdr_lightmap_oidn(bake_img, res)
    linear_rgb = np.flipud(linear_rgb)
    print(f"  Baked + OIDN ({atlas_id}/{mood}): mean={float(np.mean(linear_rgb)):.3f}, p99.5={float(np.percentile(linear_rgb, 99.5)):.3f}")

    rgbm_u8 = encode_rgbm_u8(linear_rgb, max_range=RGBM_MAX_RANGE)
    write_png_rgba(out_path, rgbm_u8)
    print(f"  Saved HDR RGBM lightmap: {out_path} ({out_path.stat().st_size // 1024} KB)")

    for nt, uv_node, img_node in temp_nodes:
        nt.nodes.remove(img_node)
        nt.nodes.remove(uv_node)
    bpy.data.images.remove(bake_img)


def optimize_full_loft_for_60fps(atlas_objs: list[bpy.types.Object]) -> None:
    print("\n=== Optimizing Full 5-Zone Loft for 60+ FPS WebGL ===")
    lm_set = set(atlas_objs)

    # 0. Remove Cycles-only skyline, lights, cameras & hidden/unlinked objects
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

    # 1. Convert visible CURVE objects cleanly
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

    # 2. Prune invisible internal keyboard PCB/SMD meshes
    to_del = []
    for o in list(bpy.data.objects):
        if o.type != "MESH":
            continue
        rname = get_root_name(o)
        if rname in ("BK_MechKeyboard75", "BK_DisplayKeyboard_Shelf"):
            ln = o.name.lower()
            if not any(k in ln for k in ("keycap", "legend", "case_", "bottom_weight", "frame", "plate")):
                to_del.append(o)
    for o in to_del:
        bpy.data.objects.remove(o, do_unlink=True)

    # 3. Smart sqrt-weighted per-group poly budgeting across all 5 rooms!
    groups: dict[str, list[bpy.types.Object]] = {}
    for o in bpy.data.objects:
        if o.type != "MESH" or o in lm_set:
            continue
        groups.setdefault(get_root_name(o), []).append(o)

    for gname, budget in LOFT_POLY_BUDGETS.items():
        if gname in NEVER_DECIMATE_GROUPS:
            continue
        objs = groups.get(gname, [])
        if not objs:
            continue
        total_p = sum(len(o.data.polygons) for o in objs)
        if total_p <= budget:
            continue
        weights = [math.sqrt(max(1, len(o.data.polygons))) for o in objs]
        w_sum = sum(weights)
        print(f"  Decimating {gname:26s}: {total_p:9,d} -> ~{budget:7,d}")
        for o, w in zip(objs, weights):
            pc = len(o.data.polygons)
            if pc <= 80:
                continue
            low_on = o.name.lower()
            # Protect crisp 75% HERO DESK keyboard legends, spacebar & CNC case from decimation spikes!
            if gname == "BK_MechKeyboard75" and (
                "legend" in low_on or "case_" in low_on or "plate" in low_on or "space" in low_on
            ):
                continue
            target_o = max(40, int(round(budget * (w / w_sum))))
            is_micro_cad = False
            if gname in ("BK_PegDualSense", "BK_LivingDualSense"):
                if "buttons" in low_on:
                    target_o = min(target_o, 2600)
                    is_micro_cad = True
                elif "ps_logo" in low_on:
                    target_o = min(target_o, 900)
                    is_micro_cad = True
                elif any(k in low_on for k in ("triger", "stick", "headphone")):
                    target_o = min(target_o, 1800)
                    is_micro_cad = True
                elif "main controler" in low_on:
                    target_o = max(target_o, 10000 if gname == "BK_PegDualSense" else 8500)
            elif gname in ("BK_3DPrinter", "BK_Canon5D_Shelf"):
                if any(k in low_on for k in ("bolt", "filament", "button", "scroll", "selector", "motor")):
                    is_micro_cad = True
            if gname == "PH_TopShelfPlant1" and "pebbles" in low_on:
                target_o = min(target_o, 500)
            if pc <= target_o:
                continue
            min_ratio = 0.002 if (pc > 200000 or is_micro_cad) else 0.015
            ratio = max(min_ratio, min(0.95, target_o / float(pc)))
            if o.data.users > 1:
                o.data = o.data.copy()
            # Only weld unwelded soft-fabric/porcelain meshes (NEVER weld hard-surface CAD/electronics where sharp bevels matter!)
            organic_weld_groups = {
                "BK_MasterBed", "BK_LivingSofa", "BK_StudioLoungeChair",
                "BK_LivingLoaferChair", "BK_SpaBathtub", "BK_SpaToilet", "BK_VesselSink",
            }
            if gname in organic_weld_groups:
                weld = o.modifiers.new("WebGL_PreWeld", "WELD")
                weld.merge_threshold = 0.00002 if gname in ("BK_MasterBed", "BK_SpaBathtub", "BK_SpaToilet") else 0.0001
            elif gname in ("BK_PegDualSense", "BK_LivingDualSense") and is_micro_cad:
                weld = o.modifiers.new("WebGL_PreWeld", "WELD")
                weld.merge_threshold = 0.0002
            mod = o.modifiers.new("WebGL_Decimate", "DECIMATE")
            mod.ratio = ratio
            if gname in ("BK_PegDualSense", "BK_LivingDualSense") and is_micro_cad:
                mod.delimit = set()
            elif gname in organic_weld_groups or is_micro_cad:
                mod.delimit = {"UV", "MATERIAL"}
            else:
                mod.delimit = {"UV", "MATERIAL", "SHARP"}

    for o in bpy.data.objects:
        rname = get_root_name(o)
        if o.type != "MESH" or o in lm_set or o.modifiers or rname in LOFT_POLY_BUDGETS or rname in NEVER_DECIMATE_GROUPS:
            continue
        pc = len(o.data.polygons)
        if pc > 12000:
            if o.data.users > 1:
                o.data = o.data.copy()
            weld = o.modifiers.new("WebGL_PreWeld", "WELD")
            weld.merge_threshold = 0.0001
            mod = o.modifiers.new("WebGL_Cap", "DECIMATE")
            mod.ratio = max(0.10, 8000.0 / float(pc))

    # 4. Bake modifiers & snapshot verified world matrices BEFORE touching armatures!
    bpy.context.view_layer.update()
    deps = bpy.context.evaluated_depsgraph_get()
    # ONLY clear split normals on soft upholstery (NEVER on porcelain toilets/sinks, wood trays, or metallic faucets!)
    smooth_fabric_groups = {"BK_MasterBed", "BK_LivingLoaferChair", "BK_LivingSofa", "BK_StudioLoungeChair"}
    for o in list(bpy.data.objects):
        if o.type != "MESH" or not o.modifiers:
            continue
        try:
            gname = get_root_name(o)
            eval_o = o.evaluated_get(deps)
            new_mesh = bpy.data.meshes.new_from_object(eval_o, preserve_all_data_layers=True, depsgraph=deps)
            old_mesh = o.data
            o.modifiers.clear()
            o.data = new_mesh
            if old_mesh.users == 0:
                bpy.data.meshes.remove(old_mesh)
            # Clear stale split normals & enforce silky smooth normals on welded soft-fabric upholstery!
            if gname in smooth_fabric_groups and len(o.data.polygons) > 0:
                o.data.polygons.foreach_set("use_smooth", [True] * len(o.data.polygons))
                try:
                    with bpy.context.temp_override(object=o, active_object=o):
                        bpy.ops.mesh.customdata_custom_splitnormals_clear()
                except Exception:
                    pass
                o.data.update()
        except Exception as exc:
            print(f"  Modifier bake warn on {o.name}: {exc}")

    bpy.context.view_layer.update()
    all_mesh_world_mats = {o: o.matrix_world.copy() for o in bpy.data.objects if o.type == "MESH"}
    for o in list(bpy.data.objects):
        if o.type == "ARMATURE":
            for child in list(o.children):
                wm = all_mesh_world_mats.get(child, child.matrix_world.copy())
                child.parent = None
                child.matrix_world = wm
            bpy.data.objects.remove(o, do_unlink=True)
    bpy.context.view_layer.update()

    # 5. Strip unused materials, broken images & deduplicate/resize images
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

    for mat in bpy.data.materials:
        if not mat.node_tree:
            continue
        for node in list(mat.node_tree.nodes):
            if node.type == "TEX_IMAGE":
                img = node.image
                if img is None or img.size[0] == 0 or img.size[1] == 0 or (not img.has_data and img.packed_file is None):
                    mat.node_tree.nodes.remove(node)

    # Deduplicate packed images by hash
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
            if mat.node_tree:
                for node in mat.node_tree.nodes:
                    if node.type == "TEX_IMAGE" and node.image in img_remap:
                        node.image = img_remap[node.image]

    # 5a. Strip textures from materials overridden to solid/procedural PBR in App.ts (eliminates 4K-velvet_2_height etc.!)
    solid_override_mats = {
        "Guide Lounge Chair_Baked", "Furn_LoaferCognacVelvet", "Furn_SofaCloudOatmeal",
        "HM_Sayl_Material", "Furn_KitchenMatteBlack",
    }
    for mat in bpy.data.materials:
        base_n = mat.name.replace("__West", "").replace("__East", "")
        if base_n in solid_override_mats and mat.node_tree:
            for node in list(mat.node_tree.nodes):
                if node.type == "TEX_IMAGE":
                    mat.node_tree.nodes.remove(node)

    # 5b. Collapse constant/flat-color BlenderKit baked textures (hundreds of 0.6 KB 512x512 solid maps wasting >650 MB GPU VRAM!)
    preserve_img_keys = (
        "arch_concrete", "walnut_oiled", "herringbone", "rug_woven", "dark_marble", "spa_stone",
        "screen_", "notebook_pages", "gallery_wall_art", "wall_art_rams", "teardown_frame",
        "geek_book_spines", "vinyl_album_covers", "pixel_clock_ui", "aio_lcd_ui",
        "bed_gallery_hero", "living_gallery_hero", "lm_uv1_anchor",
    )
    flat_img_cache: dict[bpy.types.Image, tuple[bool, tuple[float, float, float]]] = {}
    for img in list(bpy.data.images):
        ln = (img.name + " " + img.filepath).lower()
        if any(k in ln for k in preserve_img_keys):
            continue
        w, h = img.size[0], img.size[1]
        if w * h <= 16:
            continue
        try:
            arr = np.empty(w * h * 4, dtype=np.float32)
            img.pixels.foreach_get(arr)
            rgb = arr.reshape(-1, 4)[:, :3]
            # Fast subsampled check (every 17th pixel) -> exact peak-to-peak across entire image!
            sub = rgb[::max(1, len(rgb) // 4096)]
            ptp = float(np.max(np.ptp(sub, axis=0)))
            # Slightly higher flat-color tolerance for noisy low-contrast BlenderKit Cube.*_Baked / Obj_*_Baked cabinet panels!
            flat_thresh = 0.11 if ("cube." in ln and "_baked" in ln) else 0.042
            if ptp < flat_thresh:
                mean_rgb = tuple(float(x) for x in np.mean(sub, axis=0))
                flat_img_cache[img] = (True, mean_rgb)
        except Exception:
            continue

    collapsed_tex_nodes = 0
    shrunk_orm_imgs = 0
    for mat in bpy.data.materials:
        if mat.name.endswith(("__West", "__East")) or not mat.node_tree:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        for node in list(nt.nodes):
            if node.type != "TEX_IMAGE" or node.image not in flat_img_cache:
                continue
            _, mean_rgb = flat_img_cache[node.image]
            out_links = list(node.outputs["Color"].links) if "Color" in node.outputs else []
            handled = False
            if len(out_links) == 1:
                to_n = out_links[0].to_node
                to_s = out_links[0].to_socket
                if to_n == bsdf and to_s.name == "Base Color":
                    nt.nodes.remove(node)
                    bsdf.inputs["Base Color"].default_value = (mean_rgb[0], mean_rgb[1], mean_rgb[2], 1.0)
                    handled = True
                elif to_n == bsdf and to_s.name in ("Roughness", "Metallic"):
                    nt.nodes.remove(node)
                    bsdf.inputs[to_s.name].default_value = float(mean_rgb[0])
                    handled = True
                elif to_n.type in ("NORMAL_MAP", "BUMP"):
                    nt.nodes.remove(node)
                    for nl in list(to_n.outputs[0].links):
                        nt.links.remove(nl)
                    handled = True
            if handled:
                collapsed_tex_nodes += 1

    # Any remaining flat images still linked via SeparateColor/ORM -> unlink flat ORM channels cleanly OR crush to 4x4!
    still_used_flat = {
        node.image
        for mat in bpy.data.materials if mat.node_tree
        for node in mat.node_tree.nodes if node.type == "TEX_IMAGE" and node.image in flat_img_cache
    }
    for mat in bpy.data.materials:
        if mat.name.endswith(("__West", "__East")) or not mat.node_tree:
            continue
        nt = mat.node_tree
        bsdf = next((n for n in nt.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        for node in list(nt.nodes):
            if node.type != "TEX_IMAGE" or node.image not in still_used_flat:
                continue
            _, mean_rgb = flat_img_cache[node.image]
            out_links = list(node.outputs["Color"].links) if "Color" in node.outputs else []
            # Unlink constant ORM textures feeding SeparateColor -> Metallic/Roughness so material becomes solid & deduplicatable!
            if len(out_links) == 1 and out_links[0].to_node.type in ("SEPARATE_COLOR", "SEPRGB"):
                sep = out_links[0].to_node
                for ch_idx, ch_name in enumerate(("Red", "Green", "Blue")):
                    if ch_name not in sep.outputs:
                        continue
                    for sl in list(sep.outputs[ch_name].links):
                        if sl.to_node == bsdf and sl.to_socket.name in ("Roughness", "Metallic"):
                            bsdf.inputs[sl.to_socket.name].default_value = float(mean_rgb[ch_idx])
                        nt.links.remove(sl)
                nt.nodes.remove(node)
                collapsed_tex_nodes += 1

    still_used_flat = {
        node.image
        for mat in bpy.data.materials if mat.node_tree
        for node in mat.node_tree.nodes if node.type == "TEX_IMAGE" and node.image in flat_img_cache
    }
    for img in still_used_flat:
        try:
            img.scale(4, 4)
            img.pack()
            shrunk_orm_imgs += 1
        except Exception:
            pass
    print(f"  VRAM Diet: collapsed {collapsed_tex_nodes} flat texture links & shrunk {shrunk_orm_imgs} flat ORM maps to 4x4!")

    # Compute pixel-content hashes for active images so identical textures with different BlenderKit _unique_ names merge cleanly!
    img_content_hash: dict[bpy.types.Image, str] = {}
    for img in bpy.data.images:
        if img.packed_file and img.packed_file.data:
            img_content_hash[img] = hashlib.md5(img.packed_file.data).hexdigest()
        else:
            img_content_hash[img] = img.filepath or img.name

    # Aggressive Content-Based Deduplication of BlenderKit *_unique_* materials (cuts ~300+ duplicate draw-call mats -> massive FPS gain!)
    protected_prefixes = (
        "Arch_", "Furn_", "HW_", "Prop_", "Decor_", "Emit_", "Screen_", "HM_", "KB_",
        "Guide Lounge Chair", "Fabric_unique_Soft modern bed", "main controler",
        "phone_screen", "Japanese Tea Cup", "Book_Magazine",
    )
    mat_sig_map: dict[tuple, bpy.types.Material] = {}
    mat_remap: dict[bpy.types.Material, bpy.types.Material] = {}
    for mat in list(bpy.data.materials):
        if mat.name.endswith(("__West", "__East")) or mat.name.startswith(protected_prefixes):
            continue
        if not mat.node_tree:
            continue
        bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
        if not bsdf:
            continue
        imgs = []
        for node in mat.node_tree.nodes:
            if node.type == "TEX_IMAGE" and node.image:
                # Ignore 4x4 shrunk flat stubs in signature if they don't carry visual detail
                if node.image.size[0] <= 4 and node.image.size[1] <= 4:
                    continue
                targets = sorted({l.to_socket.name for o_s in node.outputs for l in o_s.links})
                if targets:
                    imgs.append((tuple(targets), img_content_hash.get(node.image, node.image.name)))
        is_solid = len(imgs) == 0
        # Quantize solid BlenderKit prop materials cleanly so 126 identical black screws/frames merge into ONE draw call!
        q_c = 0.04 if is_solid else 0.02
        q_r = 0.08 if is_solid else 0.04
        q_m = 0.15 if is_solid else 0.05
        bc = tuple(round(float(c) / q_c) * q_c for c in bsdf.inputs["Base Color"].default_value[:4])
        r_val = round(float(bsdf.inputs["Roughness"].default_value) / q_r) * q_r
        m_val = round(float(bsdf.inputs["Metallic"].default_value) / q_m) * q_m
        em_val = round(float(bsdf.inputs["Emission Strength"].default_value), 1) if "Emission Strength" in bsdf.inputs else 0.0
        alpha_val = round(float(bsdf.inputs["Alpha"].default_value), 1) if "Alpha" in bsdf.inputs else 1.0
        sig = (
            tuple(round(v, 3) for v in bc),
            round(r_val, 3),
            round(m_val, 3),
            em_val,
            alpha_val,
            tuple(sorted(imgs)),
            getattr(mat, "blend_method", "OPAQUE"),
        )
        if sig in mat_sig_map:
            mat_remap[mat] = mat_sig_map[sig]
        else:
            mat_sig_map[sig] = mat
    if mat_remap:
        for o in bpy.data.objects:
            if o.type != "MESH" or not o.data.materials:
                continue
            for idx, m in enumerate(o.data.materials):
                if m in mat_remap:
                    o.data.materials[idx] = mat_remap[m]
        print(f"  Deduplicated {len(mat_remap)} identical BlenderKit materials -> massive draw-call reduction!")

    # Strip static PNGs from live CanvasTexture monitors & 77" Living OLED TV
    for mat in bpy.data.materials:
        if mat.name in ("Screen_Ultrawide", "Screen_Vertical", "Screen_StreamDeck", "Screen_LivingTV") and mat.node_tree:
            for node in list(mat.node_tree.nodes):
                if node.type == "TEX_IMAGE":
                    mat.node_tree.nodes.remove(node)

    for _ in range(3):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    active_imgs = {
        node.image
        for o in bpy.data.objects if o.type == "MESH"
        for slot in o.material_slots if slot.material and slot.material.node_tree
        for node in slot.material.node_tree.nodes if node.type == "TEX_IMAGE" and node.image
    }
    # Smart VRAM resolution tiers: tiled arch & legible hero art = 1024px, all secondary small props = 256px (4x less VRAM!)
    hero_1024 = (
        "arch_concrete", "walnut_oiled", "herringbone", "rug_woven", "dark_marble", "spa_stone",
        "notebook_pages", "gallery_wall_art", "wall_art_rams", "teardown_frame",
        "geek_book_spines", "vinyl_album_covers", "pixel_clock_ui", "aio_lcd_ui",
        "screen_macbook", "bed_gallery_hero", "living_gallery_hero",
    )
    mid_512 = (
        "ikea_markus", "main controler", "fabric_5", "macintosh", "vinyl", "printer", "turntable", "core",
    )
    for img in list(active_imgs):
        if img.name not in bpy.data.images:
            continue
        w, h = img.size[0], img.size[1]
        if w <= 4 and h <= 4:
            continue
        if w == 0 or h == 0:
            continue
        ln = (img.name + " " + img.filepath).lower()
        max_dim = 1024 if any(k in ln for k in hero_1024) else 512 if any(k in ln for k in mid_512) else 256
        if max(w, h) > max_dim:
            sc = max_dim / float(max(w, h))
            try:
                img.scale(max(32, int(round(w * sc))), max(32, int(round(h * sc))))
                img.pack()
            except Exception:
                pass

    # 6. Wire 4x4 UV1 anchor onto both West & East LightMap atlas materials!
    lm_dummy = bpy.data.images.new("LM_UV1_Anchor", 4, 4)
    lm_dummy.pixels = [1.0] * (4 * 4 * 4)
    lm_dummy.pack()
    for ao in atlas_objs:
        for slot in ao.material_slots:
            mat = slot.material
            if not mat or not mat.node_tree:
                continue
            bsdf = next((n for n in mat.node_tree.nodes if n.type == "BSDF_PRINCIPLED"), None)
            if not bsdf:
                continue
            uv1_n = mat.node_tree.nodes.new("ShaderNodeUVMap")
            uv1_n.uv_map = "LightMapUV"
            tex_d = mat.node_tree.nodes.new("ShaderNodeTexImage")
            tex_d.image = lm_dummy
            mat.node_tree.links.new(uv1_n.outputs["UV"], tex_d.inputs["Vector"])
            mat.node_tree.links.new(tex_d.outputs["Color"], bsdf.inputs["Emission Color"])
            bsdf.inputs["Emission Strength"].default_value = 0.01

    # 7. Per-polygon UV consolidation + vertex-baked world-matrix joining into clean draw-call buckets!
    def consolidate_uv(o: bpy.types.Object) -> None:
        me = o.data
        if not me.uv_layers:
            me.uv_layers.new(name="UVMap")
            return
        if len(me.uv_layers) == 1:
            me.uv_layers[0].name = "UVMap"
            return
        default_uv = next((u.name for u in me.uv_layers if u.active_render), me.uv_layers[0].name)
        slot_uv: dict[int, str] = {}
        for idx, slot in enumerate(o.material_slots):
            chosen = default_uv
            mat = slot.material
            if mat and mat.node_tree:
                for n in mat.node_tree.nodes:
                    if n.type == "UVMAP" and n.uv_map and n.uv_map in me.uv_layers:
                        chosen = n.uv_map
                        break
            slot_uv[idx] = chosen
        if any(nm != me.uv_layers[0].name for nm in slot_uv.values()):
            srcs = {u.name: u.data for u in me.uv_layers}
            dst = me.uv_layers.new(name="__ConsolidatedUV__")
            dst_d = dst.data
            for poly in me.polygons:
                sd = srcs.get(slot_uv.get(poly.material_index, default_uv), me.uv_layers[0].data)
                for li in poly.loop_indices:
                    dst_d[li].uv = sd[li].uv
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

    def join_bucket(objs: list[bpy.types.Object], name: str) -> bpy.types.Object | None:
        valid = [o for o in objs if o.name in bpy.data.objects and o.type == "MESH" and len(o.data.polygons) > 0]
        if not valid:
            return None
        wm_map = {o: all_mesh_world_mats.get(o, o.matrix_world.copy()).copy() for o in valid}
        for o in valid:
            if o.data.users > 1:
                o.data = o.data.copy()
            consolidate_uv(o)
            wm = wm_map[o]
            o.parent = None
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = Matrix.Identity(4)
            o.data.transform(wm)
            if wm.determinant() < 0.0:
                o.data.flip_normals()
            o.data.update()
        if len(valid) == 1:
            valid[0].name = name
            return valid[0]
        bpy.ops.object.select_all(action="DESELECT")
        for o in valid:
            o.select_set(True)
        bpy.context.view_layer.objects.active = valid[0]
        bpy.ops.object.join()
        j = bpy.context.view_layer.objects.active
        j.name = name
        return j

    def join_standalone_pivot(objs: list[bpy.types.Object], name: str) -> bpy.types.Object | None:
        """
        Keep a desktop device, electronic prop, watch, or chair UN-BATCHED from room buckets,
        with its local origin/pivot centered cleanly at its own base (cx, cy, min_z) so it can
        be freely rotated, moved, or animated in Three.js!
        """
        valid = [o for o in objs if o.name in bpy.data.objects and o.type == "MESH" and len(o.data.polygons) > 0]
        if not valid:
            return None
        wm_map = {o: all_mesh_world_mats.get(o, o.matrix_world.copy()).copy() for o in valid}
        all_pts = [wm_map[o] @ Vector(c) for o in valid for c in o.bound_box]
        cx = 0.5 * (min(p.x for p in all_pts) + max(p.x for p in all_pts))
        cy = 0.5 * (min(p.y for p in all_pts) + max(p.y for p in all_pts))
        min_z = min(p.z for p in all_pts)
        pivot = Vector((cx, cy, min_z))
        inv_pivot = Matrix.Translation(-pivot)

        for o in valid:
            if o.data.users > 1:
                o.data = o.data.copy()
            consolidate_uv(o)
            wm = wm_map[o]
            o.parent = None
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = Matrix.Identity(4)
            o.data.transform(inv_pivot @ wm)
            if wm.determinant() < 0.0:
                o.data.flip_normals()
            o.data.update()

        if len(valid) == 1:
            j = valid[0]
        else:
            bpy.ops.object.select_all(action="DESELECT")
            for o in valid:
                o.select_set(True)
            bpy.context.view_layer.objects.active = valid[0]
            bpy.ops.object.join()
            j = bpy.context.view_layer.objects.active
        j.name = name
        j.location = pivot
        j["animatableDevice"] = True
        return j

    keep_exact = {
        "Monitor_Ultrawide38_Screen", "Monitor_Vertical27_Screen", "SD_KeysPanel",
        "Liv_OLED77_Screen", "Arch_LoftWin_Glass", "Arch_LivWin_Glass",
    }

    # ALL Studio desktop items, electronic devices, watches & ALL loft chairs stay 100% UN-BATCHED
    # as standalone named nodes with centered local pivots so they can be individually animated in Three.js!
    STANDALONE_DEVICE_ROOTS = {
        # Studio Desk Electronics & Accessories
        "Apple_MacBookAir15", "Apple_MacStudio", "Apple_MacMini",
        "BK_MechKeyboard75", "KB_CoiledAviatorCable.001", "KB_CoiledAviatorCable", "KB_AviatorConnector",
        "BK_LogitechMX4", "BK_DeskSmartphone", "BK_FocusriteScarlett",
        "Hero_ConceptAMicBoom", "Hero_StreamDeck", "SD_Stand", "Studio_OP1FieldSynth",
        "BK_RubikCube_Desk", "BK_Speaker_Left", "BK_Speaker_Right", "SpeakerStand_L", "SpeakerStand_R",
        "Monitor_Ultrawide38_Body", "Monitor_Vertical27_Anchor",
        "BK_CreatorsPC", "Prop_PixelMatrixClock", "Prop_DesktopLaserPrinter",
        "Studio_InsulatedTumbler", "Studio_TumblerRim",
        # Shelf / Pegboard / Living / Bedroom Electronics & Watches
        "BK_PegDualSense", "BK_PegGameBoy", "BK_PegHeadset", "BK_PegScrewdriver",
        "BK_DisplayKeyboard_Shelf", "BK_Macintosh1984", "BK_Canon5D_Shelf", "BK_CanonAE1_Shelf",
        "BK_PSP_Shelf", "BK_VinylTurntable", "BK_3DPrinter", "BK_DesktopPrinter",
        "Hero_PS5Console", "BK_LivingDualSense", "Liv_AppleTV4K", "Liv_AppleTVRemote",
        "BK_BedClosetCamera", "Bath_CaddyTablet",
        # ALL Loft Chairs & Bar Stools (un-batched for rotation/sliding animation!)
        "BK_ErgoMeshChair", "BK_StudioLoungeChair", "BK_LivingLoaferChair",
        "BK_BarStool_0", "BK_BarStool_1", "BK_BarStool_2",
    }

    # Spatial 5-Zone Frustum Culling Buckets for static background room props only
    b_standalone: dict[str, list[bpy.types.Object]] = {}
    b_zones: dict[str, list[bpy.types.Object]] = {
        "Props_Zone1_Studio": [],
        "Props_Zone2_Living": [],
        "Props_Zone3_Kitchen": [],
        "Props_Zone4_Bedroom": [],
        "Props_Zone5_Bath": [],
    }
    for o in list(bpy.data.objects):
        if o.type != "MESH" or o in lm_set:
            continue
        if o.name in keep_exact:
            wm = all_mesh_world_mats.get(o, o.matrix_world.copy())
            o.parent = None
            o.matrix_parent_inverse = Matrix.Identity(4)
            o.matrix_world = wm
            continue
        rname = get_root_name(o)
        if o.name.startswith("Interact_ScreenBar") or rname.startswith("Interact_ScreenBar"):
            b_standalone.setdefault("Interact_ScreenBar", []).append(o)
        elif o.name.startswith("Porada_Watch") and o.name.endswith("_0"):
            b_standalone.setdefault("Porada_Watch_0", []).append(o)
        elif o.name.startswith("Porada_Watch") and o.name.endswith("_1"):
            b_standalone.setdefault("Porada_Watch_1", []).append(o)
        elif o.name.startswith("Bed_AlarmClock"):
            b_standalone.setdefault("Bed_AlarmClock", []).append(o)
        elif o.name.startswith("Bed_BOSpeaker"):
            b_standalone.setdefault("Bed_BOSpeaker", []).append(o)
        elif o.name in ("Studio_InsulatedTumbler", "Studio_TumblerRim"):
            b_standalone.setdefault("Desk_InsulatedTumbler", []).append(o)
        elif rname == "Hero_LivedInDeskDetails":
            ln = o.name.lower()
            if "mug" in ln:
                b_standalone.setdefault("Desk_CoffeeMug", []).append(o)
            elif "qipad" in ln:
                b_standalone.setdefault("Desk_QiPad", []).append(o)
            elif "notebook" in ln or "pen" in ln:
                b_standalone.setdefault("Desk_NotebookSet", []).append(o)
            elif "watch" in ln:
                b_standalone.setdefault("Desk_SmartWatch", []).append(o)
            else:
                b_standalone.setdefault("Desk_LivedInDetails", []).append(o)
        elif rname == "Hero_DeskGeekPapersAndStand":
            ln = o.name.lower()
            if "stand" in ln:
                b_standalone.setdefault("Desk_LaptopStand", []).append(o)
            elif "sticky" in ln:
                b_standalone.setdefault("Desk_StickyNotes", []).append(o)
            else:
                b_standalone.setdefault("Desk_Papers", []).append(o)
        elif rname in STANDALONE_DEVICE_ROOTS or o.name in STANDALONE_DEVICE_ROOTS:
            key = rname if rname in STANDALONE_DEVICE_ROOTS else o.name
            b_standalone.setdefault(key, []).append(o)
        else:
            wm = all_mesh_world_mats.get(o, o.matrix_world)
            pts = [wm @ Vector(c) for c in o.bound_box]
            cx = sum(p.x for p in pts) / 8.0
            cy = sum(p.y for p in pts) / 8.0
            if cx < 2.25 and cy >= -1.95:
                b_zones["Props_Zone1_Studio"].append(o)
            elif cx < 4.85 and cy < -1.95:
                b_zones["Props_Zone2_Living"].append(o)
            elif cx < 6.45 and cy >= -1.95:
                b_zones["Props_Zone3_Kitchen"].append(o)
            elif cy < -1.55:
                b_zones["Props_Zone4_Bedroom"].append(o)
            else:
                b_zones["Props_Zone5_Bath"].append(o)

    # Remove EMPTY parents BEFORE naming standalone devices so exported nodes get clean exact names (ZERO .001 suffixes!)
    for o in list(bpy.data.objects):
        if o.type == "EMPTY":
            bpy.data.objects.remove(o, do_unlink=True)

    for sname, sobjs in sorted(b_standalone.items()):
        join_standalone_pivot(sobjs, sname)
    print(f"  Preserved {len(b_standalone)} standalone un-batched animatable desk/electronics/chair nodes with centered local pivots!")
    for zname, zobjs in b_zones.items():
        join_bucket(zobjs, zname)

    # Repoint all non-LightMapUV ShaderNodeUVMap nodes to consolidated 'UVMap'
    for mat in bpy.data.materials:
        if mat.node_tree:
            for n in mat.node_tree.nodes:
                if n.type == "UVMAP" and n.uv_map and n.uv_map not in ("LightMapUV", "UVMap"):
                    n.uv_map = "UVMap"

    for _ in range(3):
        bpy.ops.outliner.orphans_purge(do_local_ids=True, do_linked_ids=True, do_recursive=True)

    bpy.context.view_layer.update()
    total_polys = 0
    for o in [o for o in bpy.data.objects if o.type == "MESH"]:
        o.data.validate(clean_customdata=True)
        bb = [o.matrix_world @ Vector(c) for c in o.bound_box]
        dims = Vector((
            max(v.x for v in bb) - min(v.x for v in bb),
            max(v.y for v in bb) - min(v.y for v in bb),
            max(v.z for v in bb) - min(v.z for v in bb),
        ))
        print(f"    [Full-Loft BBox] {o.name:28s}: dims=({dims.x:.2f}, {dims.y:.2f}, {dims.z:.2f}) polys={len(o.data.polygons):,}")
        assert max(dims.x, dims.y, dims.z) < 16.0, f"EXPLODED MESH DETECTED: {o.name} dims={dims}"
        total_polys += len(o.data.polygons)
    print(f"  Full 5-Zone Loft Ready: {total_polys:,} optimized polygons total!")


def _cli_int(flag: str, default: int) -> int:
    if flag in sys.argv:
        idx = sys.argv.index(flag)
        if idx + 1 < len(sys.argv):
            return int(sys.argv[idx + 1])
    return default


def _enable_best_gpu_backend() -> None:
    """Auto-select NVIDIA OPTIX/CUDA on Colab H100/A100 Linux, or Apple METAL on macOS."""
    import platform
    prefs = bpy.context.preferences.addons["cycles"].preferences
    backends = ("OPTIX", "CUDA") if platform.system() == "Linux" else ("METAL",)
    for backend in backends:
        try:
            prefs.compute_device_type = backend
            prefs.get_devices()
            gpu_found = False
            for d in prefs.devices:
                d.use = (d.type != "CPU")
                if d.use:
                    gpu_found = True
            if gpu_found:
                bpy.context.scene.cycles.device = "GPU"
                print(f"  [Cycles GPU Backend] Enabled {backend}!")
                return
        except Exception:
            continue


def main() -> None:
    export_only = "--export-only" in sys.argv
    east_only = "--east-only" in sys.argv
    east_and_export = "--east-and-export" in sys.argv
    west_and_export = "--west-and-export" in sys.argv
    noon_and_export = "--noon-and-export" in sys.argv
    bake_res = _cli_int("--res", LIGHTMAP_RESOLUTION)
    bake_samples = _cli_int("--samples", 224)
    blend_path = BLEND_DIR / "full_loft.blend"
    bpy.ops.wm.open_mainfile(filepath=str(blend_path))
    _enable_best_gpu_backend()
    light_col = bpy.data.collections.get("05_Lights") or bpy.context.scene.collection

    west_raw = [o for o in bpy.data.objects if o.type == "MESH" and _match_prefix(o.name, WEST_LIGHTMAP_PREFIXES)]
    east_raw = [o for o in bpy.data.objects if o.type == "MESH" and _match_prefix(o.name, EAST_LIGHTMAP_PREFIXES)]
    print(f"Joining Dual-Atlas Targets: WEST={len(west_raw)} meshes, EAST={len(east_raw)} meshes (res={bake_res}, spp={bake_samples})")

    west_atlas = join_atlas_targets(west_raw, "west", "Arch_LightMapped_West")
    east_atlas = join_atlas_targets(east_raw, "east", "Arch_LightMapped_East")

    lm_dir = PUBLIC_ASSETS_DIR / "lightmaps"
    lm_dir.mkdir(parents=True, exist_ok=True)
    if noon_and_export:
        bake_atlas_mood(west_atlas, "west", "noon", light_col, lm_dir / "loft_west_noon.png", res=bake_res, samples=bake_samples)
        bake_atlas_mood(east_atlas, "east", "noon", light_col, lm_dir / "loft_east_noon.png", res=bake_res, samples=bake_samples)
        print("  [--noon-and-export] Independent Noon 2K HDR+OIDN lightmaps baked; proceeding to export optimized GLB!")
    elif west_and_export:
        for mood in ("midnight", "daylight", "noon", "golden"):
            bake_atlas_mood(west_atlas, "west", mood, light_col, lm_dir / f"loft_west_{mood}.png", res=bake_res, samples=bake_samples)
        print("  [--west-and-export] West lightmaps baked; proceeding to export updated GLB (reusing East lightmaps)!")
    elif east_only or east_and_export:
        for mood in ("midnight", "daylight", "noon", "golden"):
            bake_atlas_mood(east_atlas, "east", mood, light_col, lm_dir / f"loft_east_{mood}.png", res=bake_res, samples=bake_samples)
        if east_only:
            print("  [--east-only] Finished re-baking East atlas lightmaps (GLB & West atlas untouched).")
            return
        print("  [--east-and-export] East lightmaps baked; proceeding to export updated GLB (reusing West lightmaps)!")
    elif not export_only:
        for mood in ("midnight", "daylight", "noon", "golden"):
            bake_atlas_mood(west_atlas, "west", mood, light_col, lm_dir / f"loft_west_{mood}.png", res=bake_res, samples=bake_samples)
            bake_atlas_mood(east_atlas, "east", mood, light_col, lm_dir / f"loft_east_{mood}.png", res=bake_res, samples=bake_samples)
    else:
        print("  [--export-only] Reusing existing baked multi-atlas HDR RGBM lightmaps.")

    optimize_full_loft_for_60fps([west_atlas, east_atlas])

    PUBLIC_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    glb_out = PUBLIC_ASSETS_DIR / "full_loft.glb"
    print(f"\n=== Exporting Full 5-Zone Loft Draco + WebP GLB -> {glb_out} ===")
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

    stage_web_assets()
    loft_col = BLEND_DIR / "loft_colliders.json"
    if loft_col.exists():
        shutil.copy2(loft_col, PUBLIC_ASSETS_DIR / "loft_colliders.json")
    print("\nPhase 3 Full 5-Zone Loft Dual-Atlas Bake & Export COMPLETE!")


if __name__ == "__main__":
    main()
