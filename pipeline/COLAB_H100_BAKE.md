# Google Colab H100 / A100 4K Cycles OptiX Lightmap Baking Guide

`pipeline/bake_full_loft.py` now supports automatic NVIDIA `OPTIX`/`CUDA` detection plus `--res 4096 --samples 512` CLI flags so you can push `assets/blend/full_loft.blend` to a cloud H100/A100 GPU and get **4K 512-spp** dual-atlas HDR RGBM lightmaps back in ~2–3 minutes (vs ~45 min locally).

## Quick One-Shot Colab Command (via `google-colab-cli` or Colab Notebook)

1. Upload `assets/blend/full_loft.blend` and the `pipeline/` directory to your Colab session (or Google Drive).
2. In a Colab GPU cell (`H100` or `A100`), install Blender 4.3/5.2 headless Linux tarball and run:

```bash
wget -q https://download.blender.org/release/Blender4.3/blender-4.3.2-linux-x64.tar.xz
tar -xf blender-4.3.2-linux-x64.tar.xz
./blender-4.3.2-linux-x64/blender --background --python-exit-code 1 \
  --python pipeline/bake_full_loft.py -- --res 4096 --samples 512
```

3. Copy the generated `public/assets/lightmaps/loft_{west,east}_{midnight,daylight,noon,golden}.png` files back into your local `public/assets/lightmaps/` directory — the Three.js app automatically loads 4K lightmaps with zero frontend code changes!
