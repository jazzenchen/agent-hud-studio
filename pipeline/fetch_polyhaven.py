#!/usr/bin/env python3
"""
Fetch verified CC0 PBR textures, HDRIs, and 3D glTF models from Poly Haven API.
Idempotent & cached under assets/cache/.
"""

import argparse
import concurrent.futures
import json
import sys
import urllib.request
from pathlib import Path

from config import (
    HDRI_DIR,
    MODEL_DIR,
    POLYHAVEN_HDRIS,
    POLYHAVEN_MODELS_PHASE1,
    POLYHAVEN_MODELS_PHASE3,
    POLYHAVEN_TEXTURES,
    TEX_DIR,
)

USER_AGENT = "AStudio-GeekLoft-ArchViz/1.0"


def fetch_json(url: str) -> dict:
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=20) as resp:
        return json.loads(resp.read().decode("utf-8"))


def download_file(url: str, dest: Path) -> None:
    if dest.exists() and dest.stat().st_size > 0:
        return
    dest.parent.mkdir(parents=True, exist_ok=True)
    tmp = dest.with_suffix(dest.suffix + ".part")
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})
    with urllib.request.urlopen(req, timeout=60) as resp, open(tmp, "wb") as out:
        while True:
            chunk = resp.read(1024 * 64)
            if not chunk:
                break
            out.write(chunk)
    tmp.replace(dest)


def fetch_texture(asset_id: str, res: str) -> str:
    target_dir = TEX_DIR / asset_id
    marker = target_dir / ".done"
    if marker.exists():
        return f"[cached] texture:{asset_id}"

    data = fetch_json(f"https://api.polyhaven.com/files/{asset_id}")
    map_keys = ["Diffuse", "nor_gl", "Rough", "AO", "arm", "Displacement"]
    downloaded = []
    for key in map_keys:
        if key not in data:
            continue
        res_map = data[key].get(res) or data[key].get("2k") or data[key].get("1k")
        if not res_map:
            continue
        fmt = "jpg" if "jpg" in res_map else next(iter(res_map.keys()))
        url = res_map[fmt]["url"]
        ext = Path(url).suffix
        dest = target_dir / f"{key.lower()}{ext}"
        download_file(url, dest)
        downloaded.append(key)

    marker.write_text(",".join(downloaded), encoding="utf-8")
    return f"[ok] texture:{asset_id} ({','.join(downloaded)})"


def fetch_hdri(asset_id: str, res: str) -> str:
    dest = HDRI_DIR / f"{asset_id}_{res}.hdr"
    if dest.exists() and dest.stat().st_size > 0:
        return f"[cached] hdri:{asset_id}"

    data = fetch_json(f"https://api.polyhaven.com/files/{asset_id}")
    res_map = data["hdri"].get(res) or data["hdri"].get("2k")
    url = res_map["hdr"]["url"]
    download_file(url, dest)
    return f"[ok] hdri:{asset_id} ({dest.stat().st_size // 1024} KB)"


def fetch_model(asset_id: str, res: str) -> str:
    target_dir = MODEL_DIR / asset_id
    gltf_path = target_dir / f"{asset_id}.gltf"
    marker = target_dir / ".done"
    if marker.exists() and gltf_path.exists():
        return f"[cached] model:{asset_id}"

    data = fetch_json(f"https://api.polyhaven.com/files/{asset_id}")
    gltf_info = (data["gltf"].get(res) or data["gltf"].get("2k") or data["gltf"].get("1k"))["gltf"]
    download_file(gltf_info["url"], gltf_path)

    includes = gltf_info.get("include", {})
    for rel_path, info in includes.items():
        download_file(info["url"], target_dir / rel_path)

    marker.write_text(str(len(includes)), encoding="utf-8")
    return f"[ok] model:{asset_id} ({len(includes) + 1} files)"


def main() -> int:
    parser = argparse.ArgumentParser(description="Download CC0 ArchViz assets from Poly Haven.")
    parser.add_argument("--phase", choices=["1", "all"], default="1", help="Asset phase to download")
    parser.add_argument("--workers", type=int, default=6, help="Parallel download threads")
    args = parser.parse_args()

    tasks = []
    for tid, res in POLYHAVEN_TEXTURES.items():
        tasks.append(("texture", tid, res))
    for hid, res in POLYHAVEN_HDRIS.items():
        tasks.append(("hdri", hid, res))
    models = dict(POLYHAVEN_MODELS_PHASE1)
    if args.phase == "all":
        models.update(POLYHAVEN_MODELS_PHASE3)
    for mid, res in models.items():
        tasks.append(("model", mid, res))

    print(f"Fetching {len(tasks)} Poly Haven CC0 assets (phase={args.phase})...")
    failed = []
    with concurrent.futures.ThreadPoolExecutor(max_workers=args.workers) as pool:
        future_map = {}
        for kind, aid, res in tasks:
            fn = fetch_texture if kind == "texture" else (fetch_hdri if kind == "hdri" else fetch_model)
            future_map[pool.submit(fn, aid, res)] = (kind, aid)

        for fut in concurrent.futures.as_completed(future_map):
            kind, aid = future_map[fut]
            try:
                print(" ", fut.result())
            except Exception as exc:
                print(f"  [ERR] {kind}:{aid}: {exc}", file=sys.stderr)
                failed.append((kind, aid, str(exc)))

    if failed:
        print(f"\nFailed {len(failed)} assets.", file=sys.stderr)
        return 1
    print("\nAll Poly Haven CC0 assets ready!")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
