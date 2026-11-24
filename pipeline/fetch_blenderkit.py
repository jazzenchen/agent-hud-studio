#!/usr/bin/env python3
"""
Fetch curated free Royalty-Free / CC0 artist-sculpted 3D models (.glb + preview thumbnails)
from the official BlenderKit public API. Cached under assets/cache/blenderkit/.
"""

import argparse
import concurrent.futures
import json
import sys
import urllib.parse
import urllib.request
import uuid
from pathlib import Path

from config import CACHE_DIR

BK_DIR = CACHE_DIR / "blenderkit"
USER_AGENT = "BlenderKit/3.12"

# Curated verified high-score free BlenderKit artist models (assetBaseId -> slot name)
BLENDERKIT_PHASE1_STUDIO = {
    "hm_sayl_chair": "2d23e6bf-73de-44c3-99ff-9b95a1a268c0",         # Herman Miller Sayl Interstellar
    "office_chair_alt": "1e29cd60-661b-4943-ab3f-8f899c4a0787",       # Ergonomic Office Chair (backup)
    "mech_keyboard_75": "9fbd4d1f-fd8e-467f-b2a3-0d44b292d017",       # Aluminum 75% Mechanical Keyboard
    "mx_mouse": "9701990b-0eac-4d85-abdf-811034e11450",               # Logitech MX4 Black Ergonomic Mouse
    "studio_speakers": "3fc7d90d-45b0-4402-8e34-5ba9fc445ba8",        # Studio HD Monitors Black Pearl
    "maudio_speakers": "b023515f-8f12-450b-a470-da241ea9adbf",        # M-Audio AV 40 Active Speakers
    "focusrite_scarlett": "b220c6c2-192a-4bd4-93a3-503d93f29381",     # Focusrite Scarlett Solo Audio Interface
    "studio_mic": "5fc24e40-72b1-42c3-8f5f-d96e69ac5957",             # Broadcast Microphone
    "gaming_pc_case": "f12815dc-6013-494e-b748-353fe5ad92a7",         # Gaming Computer Case
    "gaming_desktop": "ad75f9fe-5373-406a-9d33-6cded13cd170",         # Gaming Desktop
    "headset_black": "16e04b0a-d0e8-4855-9140-9705d9902496",          # Black Studio Headset with Stand
    "canon_5d": "a5be7449-3b42-4ae4-9275-3c67907ac973",               # Canon EOS 5D Mark IV DSLR Camera
    "ps5_console": "3de9d5be-dbb9-46d4-8bc5-a643c9a588ae",            # PlayStation 5
    "dualsense_ps5": "15b4a261-1523-48a7-8d55-5ad9c8351acf",          # PS5 DualSense Controller
    "psp_handheld": "a41f903c-f6ad-4953-8dea-821894779491",           # PlayStation Portable Collectible
    "track_lighting": "c4a31992-0e40-4ff5-bbec-06746c7ec1c3",         # Magnetic Track Lighting System
    "ikea_pegboard": "0fb644e6-7dcd-44a4-83c2-7231df5771a8",          # IKEA SKADIS Pegboard
    "monstera_big": "055d8fc0-a666-499d-aa17-bd503744e966",           # Big Monstera Deliciosa Plant
    "hanging_plant": "d487f617-ac53-4689-b65d-b78bc02daca3",          # Trailing Hanging Plant for Bookshelf
    "metal_bookshelf": "777bc958-c2cc-482c-99c5-908678cb9911",        # Minimalist Rack Shelving Bookcase
    "vinyl_player": "3e42210c-4c2c-4e74-91bd-0baa09504103",           # Modern Vinyl Record Player
    "ultrawide_odyssey": "7b456d78-f455-4b0b-946e-2d22c1f64913",      # Samsung Odyssey Curved Monitor
    "ultrawide_34": "d394c920-82dc-45e4-9790-0c8f5941b67c",           # 34-inch Curved Ultrawide Black
    "creators_pc": "483a3fad-6455-4236-bc27-d03d0bc4d715",            # Creator's Dream PC (.blend)
    "books_stack_4": "e3ebbbaf-5d2d-4d3e-859c-9de7bfa5dd25",          # Four Stacks of Modern Books
    "books_stack_1": "87b81438-9883-4787-a86d-58135ec892a5",          # Stack of Art Books
    "black_wall_socket": "849b31a5-40f4-4a38-b43d-501709460819",      # Black Wall Power Outlet
    "hifi_subwoofer": "e1b31beb-3a76-4039-a731-a68a0742aa6c",         # Hi-End Subwoofer Black Wood
    "vintage_35mm": "3ef12fa4-29a0-463f-b338-7ad3f81b654b",           # Vintage 35mm Film Camera
    "smartphone_black": "a6d503d4-f7ca-4bab-b310-98fd5ef6fb24",       # Obsidian Black Smartphone
    "gameboy_color": "24ba2d5c-0df2-4da1-b4d4-564761cb7bbc",          # Retro Game Boy Color
    "magazine_stack_1": "f5b80b2a-ae36-493d-b785-cd9dca3d25f2",       # Stacked Design Magazines
    "magazine_stack_2": "5476e76e-0c2f-49b0-889f-1c882136695e",       # Stacked Magazines Set
    "potted_plant_bk": "0b81a70a-029e-49a4-b568-5c3fa033485e",        # Modern Potted Greenery
    # Authentic Geek Studio Hardware & Collectibles (v6 Visual QC Overhaul!)
    "pc_tower_pro": "7f708a26-936e-47bb-978c-efd50980ed84",           # Real Sculpted Computer PC Tower
    "pc_fan_core": "e51c7508-03b7-49a5-98e6-84c48c5141a2",            # Real 9-Blade RGB PC Fan Core
    "studio_spotlight": "a58c0e93-2bb2-424d-b67f-4b89990d8731",       # Real Studio Softbox/Keylight on Stand
    "macintosh_1984": "f188f404-3028-4d18-841d-550c99a5c75b",         # Iconic Apple Macintosh 1984
    "mini_pc_homelab": "5d0d4d5c-bb74-4871-88ad-bbba00cff9b5",        # HomeLab Mini PC Node
    "zaku_gunpla": "ebee94b8-5e10-4b96-947b-7788145feaf5",            # Gunpla Zaku MK-II Model
    "pen_holder": "1fd8333b-4e22-4960-9fbb-2d3c9cbece14",             # Loaded Sculpted Pen & Tool Cup
    "quadcopter_drone": "9d3a59d0-6949-4d7a-a2be-aa11b4ed9df4",       # FPV / Camera Quadcopter Drone
    "screwdriver_real": "088caf04-8c48-41fd-9289-6a12f60d57af",       # Real 1-Piece Sculpted Screwdriver
}

BLENDERKIT_PHASE3_LOFT = {
    "espresso_machine": "bf2b08e8-f8c1-4f7e-850c-0303ed46310b",       # Espresso Coffee Machine
    "modern_bed": "9baa9480-d651-4a99-9ea4-ac256ab4a6d7",             # Modern Sculpted Bed
    "oval_bathtub": "16bfcc74-8f53-4efe-8a0c-0f8b0c57306a",           # Freestanding Oval Bathtub
    "minimal_sofa": "198871fb-f218-4beb-a4e6-f76fa20c9fed",           # Minimal Modern Sofa
}


def api_get_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_binary(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 1024:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=120) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1024 * 64)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


def fetch_asset(slot: str, asset_base_id: str) -> str:
    slot_dir = BK_DIR / slot
    glb_path = slot_dir / f"{slot}.glb"
    thumb_path = slot_dir / "thumb.jpg"
    meta_path = slot_dir / "meta.json"

    if glb_path.exists() and glb_path.stat().st_size > 1024 and thumb_path.exists():
        return f"[cached] {slot} ({glb_path.stat().st_size // 1024} KB)"

    # Query asset record by asset_base_id
    search_url = (
        "https://www.blenderkit.com/api/v1/search/?query="
        + urllib.parse.quote(f"asset_base_id:{asset_base_id}")
    )
    data = api_get_json(search_url)
    results = data.get("results", [])
    if not results:
        raise RuntimeError(f"Asset {asset_base_id} not found")
    item = results[0]

    slot_dir.mkdir(parents=True, exist_ok=True)
    meta_path.write_text(json.dumps({
        "slot": slot,
        "name": item.get("name"),
        "assetBaseId": asset_base_id,
        "license": item.get("license"),
        "author": item.get("author", {}).get("fullName"),
        "faceCount": item.get("dictParameters", {}).get("faceCount"),
    }, indent=2), encoding="utf-8")

    # Download preview thumbnail for visual QA
    thumb_url = item.get("thumbnailMiddleUrl") or item.get("thumbnailSmallUrl")
    if thumb_url:
        download_binary(thumb_url, thumb_path)

    # Prefer GLTF/GLB (self-contained with embedded textures!), fallback to .blend
    files = {f.get("fileType"): f for f in item.get("files", [])}
    chosen = files.get("gltf") or files.get("blend")
    if not chosen:
        raise RuntimeError(f"No gltf/blend file for {slot}")

    dl_api = f"{chosen['downloadUrl']}?scene_uuid={uuid.uuid4()}"
    dl_info = api_get_json(dl_api)
    file_url = dl_info.get("filePath")
    if not file_url:
        raise RuntimeError(f"No download filePath returned for {slot}")

    ext = ".glb" if chosen["fileType"] == "gltf" else ".blend"
    out_file = slot_dir / f"{slot}{ext}"
    download_binary(file_url, out_file)
    return f"[ok] {slot}: {item.get('name')} ({out_file.stat().st_size // 1024} KB, {ext})"


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--phase", choices=["1", "all"], default="1")
    parser.add_argument("--workers", type=int, default=5)
    args = parser.parse_args()

    catalog = dict(BLENDERKIT_PHASE1_STUDIO)
    if args.phase == "all":
        catalog.update(BLENDERKIT_PHASE3_LOFT)

    print(f"Fetching {len(catalog)} free artist-sculpted BlenderKit models (phase={args.phase})...")
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        futs = {pool.submit(fetch_asset, slot, aid): slot for slot, aid in catalog.items()}
        for fut in concurrent.futures.as_completed(futs):
            slot = futs[fut]
            try:
                print(" ", fut.result())
            except Exception as exc:
                print(f"  [ERR] {slot}: {exc}", file=sys.stderr)
                failed.append((slot, str(exc)))

    if failed:
        print(f"\nFailed {len(failed)} assets: {failed}", file=sys.stderr)
        return 1
    print("\nAll BlenderKit artist assets ready!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
