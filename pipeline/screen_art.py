"""
Generate crisp, photorealistic textures using pure NumPy + zlib PNG encoding:
1. High-contrast OLED Ultrawide IDE + OBS Live Stream screen (1920x800)
2. Vertical System Telemetry + Live Stream Chat screen (1080x1920)
3. Minimalist ArchViz Gallery Wall Art print (1200x1600)
4. Hand-woven architectural wool rug Albedo + Height/Bump texture (1024x1024)
"""

import math
import struct
import zlib
from pathlib import Path
import numpy as np


def _write_png_rgb(path: Path, img: np.ndarray) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    h, w, _ = img.shape
    raw = b"".join(b"\x00" + img[y].tobytes() for y in range(h))

    def chunk(tag: bytes, data: bytes) -> bytes:
        crc = zlib.crc32(tag + data) & 0xFFFFFFFF
        return struct.pack(">I", len(data)) + tag + data + struct.pack(">I", crc)

    ihdr = struct.pack(">IIBBBBB", w, h, 8, 2, 0, 0, 0)
    png = b"\x89PNG\r\n\x1a\n" + chunk(b"IHDR", ihdr) + chunk(b"IDAT", zlib.compress(raw, 6)) + chunk(b"IEND", b"")
    path.write_bytes(png)


def _rect(img: np.ndarray, x0: int, y0: int, x1: int, y1: int, color: tuple[int, int, int]) -> None:
    h, w, _ = img.shape
    x0, x1 = max(0, x0), min(w, x1)
    y0, y1 = max(0, y0), min(h, y1)
    if x1 > x0 and y1 > y0:
        img[y0:y1, x0:x1] = color


def _code_line(img: np.ndarray, x: int, y: int, tokens: list[tuple[int, tuple[int, int, int]]], h: int = 8) -> None:
    cur = x
    for width, col in tokens:
        _rect(img, cur, y, cur + width, y + h, col)
        cur += width + 10


def generate_ultrawide_ide(path: Path) -> Path:
    """High-contrast deep-black OLED VS Code + Dark 3D Scene / OBS Preview (1920x800)."""
    w, h = 1920, 800
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = (8, 10, 15)  # True deep OLED black-navy

    # Title bar
    _rect(img, 0, 0, w, 32, (6, 8, 12))
    _rect(img, 18, 11, 28, 21, (220, 74, 68))
    _rect(img, 38, 11, 48, 21, (226, 174, 52))
    _rect(img, 58, 11, 68, 21, (68, 188, 92))

    # Left Activity Bar
    _rect(img, 0, 32, 50, h - 24, (7, 9, 13))
    for i in range(6):
        col = (68, 162, 255) if i == 0 else (48, 56, 72)
        _rect(img, 14, 56 + i * 52, 36, 78 + i * 52, col)

    # Explorer Sidebar
    _rect(img, 50, 32, 286, h - 24, (11, 14, 20))
    _rect(img, 286, 32, 288, h - 24, (24, 30, 44))
    file_colors = [
        (78, 168, 255), (96, 204, 138), (235, 176, 78),
        (174, 118, 255), (78, 168, 255), (96, 204, 138),
    ]
    for i in range(18):
        indent = 14 if i in (0, 5, 12) else 32
        y = 58 + i * 28
        if i == 3:
            _rect(img, 52, y - 4, 284, y + 18, (22, 31, 50))
        _rect(img, 50 + indent, y + 2, 50 + indent + 10, y + 12, file_colors[i % len(file_colors)])
        _rect(img, 50 + indent + 18, y + 3, 50 + indent + 18 + 65 + (i * 37) % 85, y + 10, (124, 138, 164))

    # Code Editor Tabs
    _rect(img, 288, 32, 1220, 68, (9, 11, 17))
    _rect(img, 288, 32, 488, 68, (14, 18, 26))
    _rect(img, 288, 32, 488, 35, (64, 168, 255))
    _rect(img, 312, 46, 452, 54, (192, 206, 232))
    _rect(img, 514, 46, 650, 54, (84, 96, 120))
    _rect(img, 696, 46, 835, 54, (84, 96, 120))

    # Vivid high-contrast syntax tokens on deep OLED background
    c_kw = (192, 108, 255)
    c_fn = (72, 172, 255)
    c_str = (118, 212, 124)
    c_num = (255, 152, 74)
    c_var = (182, 196, 222)
    c_cmt = (62, 74, 98)
    c_type = (58, 212, 210)

    patterns = [
        [(62, c_kw), (90, c_var), (40, c_kw), (125, c_str)],
        [(180, c_cmt)],
        [(52, c_kw), (110, c_fn), (75, c_type), (42, c_var)],
        [(28, c_kw), (68, c_var), (95, c_fn), (55, c_num), (70, c_type)],
        [(28, c_kw), (82, c_var), (135, c_str)],
        [(55, c_fn), (108, c_var), (46, c_num), (88, c_str)],
        [(44, c_kw), (72, c_type), (112, c_fn), (64, c_var)],
        [],
    ]
    for row in range(21):
        y = 86 + row * 22
        _rect(img, 304, y, 322, y + 7, (48, 58, 78))
        pat = patterns[row % len(patterns)]
        if pat:
            indent = 24 * ((row % 4) if (row % 8) not in (0, 2) else 0)
            _code_line(img, 350 + indent, y, pat, h=8)

    # Bottom Terminal Panel
    _rect(img, 288, 558, 1220, 560, (28, 36, 52))
    _rect(img, 288, 560, 1220, h - 24, (7, 9, 14))
    _rect(img, 308, 572, 386, 580, (192, 206, 230))
    _rect(img, 308, 584, 386, 586, (64, 168, 255))
    term_rows = [
        [(58, (64, 212, 138)), (180, (164, 178, 204)), (95, (72, 172, 255))],
        [(44, (72, 172, 255)), (240, (132, 146, 172)), (70, (248, 174, 76))],
        [(44, (64, 212, 138)), (195, (118, 212, 124)), (85, (148, 162, 188))],
        [(58, (192, 108, 255)), (160, (164, 178, 204)), (120, (58, 212, 210))],
        [(50, (64, 212, 138)), (220, (164, 178, 204))],
    ]
    for idx, t_row in enumerate(term_rows):
        _code_line(img, 308, 606 + idx * 28, t_row, h=8)

    # Right Split: Dark OBS Live Studio Viewport + Audio Mixer
    _rect(img, 1220, 32, 1222, h - 24, (28, 36, 52))
    _rect(img, 1222, 32, w, h - 24, (10, 13, 19))

    vx0, vy0, vx1, vy1 = 1246, 58, 1894, 466
    yy, xx = np.mgrid[vy0:vy1, vx0:vx1]
    nx = (xx - vx0) / float(vx1 - vx0)
    ny = (yy - vy0) / float(vy1 - vy0)
    # Deep moody cyber-architectural viewport preview (rich dark tones, NO washed-out white!)
    r = np.clip(10 + 96 * np.exp(-((nx - 0.66) ** 2 / 0.10 + (ny - 0.56) ** 2 / 0.10)) + 16 * (1 - ny), 0, 255)
    g = np.clip(14 + 54 * np.exp(-((nx - 0.30) ** 2 / 0.16 + (ny - 0.44) ** 2 / 0.14)) + 34 * np.exp(-((nx - 0.66) ** 2 / 0.10 + (ny - 0.56) ** 2 / 0.10)), 0, 255)
    b = np.clip(24 + 98 * np.exp(-((nx - 0.28) ** 2 / 0.16 + (ny - 0.44) ** 2 / 0.16)), 0, 255)
    img[vy0:vy1, vx0:vx1, 0] = r.astype(np.uint8)
    img[vy0:vy1, vx0:vx1, 1] = g.astype(np.uint8)
    img[vy0:vy1, vx0:vx1, 2] = b.astype(np.uint8)
    # Subtle 3D viewport wireframe horizon & grid lines inside preview
    for gx in range(vx0 + 40, vx1, 56):
        _rect(img, gx, vy0 + 260, gx + 1, vy1 - 12, (36, 54, 78))
    for gy in range(vy0 + 260, vy1, 32):
        _rect(img, vx0 + 12, gy, vx1 - 12, gy + 1, (36, 54, 78))

    # Crisp red LIVE badge
    _rect(img, vx0 + 18, vy0 + 18, vx0 + 92, vy0 + 42, (212, 38, 46))
    _rect(img, vx0 + 30, vy0 + 26, vx0 + 80, vy0 + 34, (245, 245, 245))

    # Audio Mixer Panel
    _rect(img, 1246, 490, 1894, 748, (14, 18, 26))
    for ch in range(4):
        by = 516 + ch * 52
        _rect(img, 1270, by, 1364, by + 9, (124, 138, 162))
        fill = int(280 + (ch * 73) % 230)
        _rect(img, 1270, by + 18, 1868, by + 31, (22, 28, 40))
        _rect(img, 1270, by + 18, 1270 + min(fill, 350), by + 31, (48, 196, 126))
        if fill > 350:
            _rect(img, 1270 + 350, by + 18, 1270 + min(fill, 450), by + 31, (236, 174, 52))
        if fill > 450:
            _rect(img, 1270 + 450, by + 18, 1270 + fill, by + 31, (226, 68, 62))

    # Bottom status bar
    _rect(img, 0, h - 24, w, h, (22, 74, 152))
    _rect(img, 18, h - 16, 135, h - 8, (206, 224, 248))
    _rect(img, w - 210, h - 16, w - 24, h - 8, (206, 224, 248))

    _write_png_rgb(path, img)
    return path


def generate_vertical_telemetry(path: Path) -> Path:
    """Crisp 1080x1920 vertical monitor image: System Telemetry + Live Stream Chat."""
    w, h = 1080, 1920
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = (9, 11, 17)

    _rect(img, 0, 0, w, 84, (14, 17, 25))
    _rect(img, 38, 32, 290, 50, (78, 174, 255))
    _rect(img, w - 180, 26, w - 38, 58, (36, 164, 108))

    card_cols = [(64, 178, 255), (245, 134, 66), (86, 214, 138)]
    for i in range(3):
        cx0 = 36 + i * 340
        cx1 = cx0 + 318
        _rect(img, cx0, 116, cx1, 340, (15, 19, 28))
        _rect(img, cx0, 116, cx1, 122, card_cols[i])
        _rect(img, cx0 + 24, 148, cx0 + 140, 164, (132, 146, 172))
        _rect(img, cx0 + 24, 192, cx0 + 210, 232, (224, 232, 246))
        for b in range(14):
            bh = 16 + ((b * 19 + i * 31) % 58)
            bx = cx0 + 24 + b * 19
            _rect(img, bx, 320 - bh, bx + 12, 320, card_cols[i])

    _rect(img, 36, 372, w - 36, 760, (14, 18, 27))
    for gy in range(430, 740, 60):
        _rect(img, 64, gy, w - 64, gy + 2, (26, 33, 48))
    xs = np.arange(68, w - 68)
    t = (xs - 68) / float(w - 136)
    y_curve1 = (575 + 70 * np.sin(t * 14.0) + 28 * np.cos(t * 31.0)).astype(int)
    y_curve2 = (625 + 52 * np.cos(t * 11.0 + 1.2) + 22 * np.sin(t * 25.0)).astype(int)
    for x, y1, y2 in zip(xs, y_curve1, y_curve2):
        _rect(img, int(x), int(y1) - 4, int(x) + 3, int(y1) + 4, (72, 188, 255))
        _rect(img, int(x), int(y2) - 4, int(x) + 3, int(y2) + 4, (248, 126, 74))

    _rect(img, 36, 796, w - 36, h - 42, (13, 16, 24))
    _rect(img, 36, 796, w - 36, 854, (20, 24, 36))
    _rect(img, 64, 818, 310, 834, (208, 218, 236))

    badge_colors = [
        (246, 108, 82), (82, 184, 255), (168, 118, 255),
        (76, 208, 140), (245, 184, 76),
    ]
    for row in range(13):
        ry = 890 + row * 74
        bc = badge_colors[row % len(badge_colors)]
        _rect(img, 64, ry, 104, ry + 40, bc)
        _rect(img, 126, ry + 4, 260 + (row * 37) % 120, ry + 18, bc)
        msg_w = 420 + (row * 113) % 410
        _rect(img, 126, ry + 28, min(w - 72, 126 + msg_w), ry + 42, (168, 180, 204))

    _write_png_rgb(path, img)
    return path


def generate_gallery_artwork(path: Path) -> Path:
    """Minimalist mid-century Bauhaus / ArchViz gallery poster (warm linen, charcoal arch, terracotta sun)."""
    w, h = 900, 1200
    yy, xx = np.mgrid[0:h, 0:w]
    nx = xx / float(w)
    ny = yy / float(h)
    rng = np.random.default_rng(7)
    paper_grain = rng.normal(0.0, 2.5, (h, w, 1))

    # Warm archival cotton paper cream
    img = np.zeros((h, w, 3), dtype=np.float32)
    img[:, :] = (224, 214, 198)

    # Matte warm charcoal architectural arch on lower-left
    arch_mask = ((nx > 0.14) & (nx < 0.62) & (ny > 0.44) & (ny < 0.88)) | (
        ((nx - 0.38) ** 2 / (0.24 ** 2) + (ny - 0.44) ** 2 / (0.18 ** 2)) <= 1.0
    )
    img[arch_mask] = (34, 34, 36)

    # Warm burnt terracotta geometric sun circle upper-right
    sun_mask = ((nx - 0.66) ** 2 + ((ny - 0.30) * (h / w)) ** 2) <= (0.17 ** 2)
    img[sun_mask] = (182, 86, 52)

    # Warm taupe offset accent rectangle
    bar_mask = (nx > 0.56) & (nx < 0.84) & (ny > 0.58) & (ny < 0.88)
    img[bar_mask] = (146, 134, 118)

    # Crisp thin architectural line overlay
    line_mask = (np.abs(ny - 0.58) < 0.0025) & (nx > 0.14) & (nx < 0.84)
    img[line_mask] = (224, 214, 198)

    # White mat border around poster
    border = (nx < 0.06) | (nx > 0.94) | (ny < 0.05) | (ny > 0.95)
    img[border] = (238, 234, 226)

    img = np.clip(img + paper_grain, 0, 255).astype(np.uint8)
    _write_png_rgb(path, img)
    return path


def generate_stream_deck_ui(path: Path) -> Path:
    """Crisp 5x3 backlit Stream Deck MK.2 macro icon buttons."""
    w, h = 640, 384
    img = np.zeros((h, w, 3), dtype=np.uint8)
    img[:, :] = (10, 12, 16)
    palette = [
        (228, 62, 74), (62, 168, 255), (84, 212, 134), (245, 164, 52), (174, 114, 255),
        (58, 198, 210), (242, 118, 64), (112, 148, 255), (235, 78, 144), (96, 206, 178),
        (160, 172, 194), (68, 152, 240), (238, 192, 68), (110, 224, 142), (242, 92, 82),
    ]
    pad_x, pad_y = 26, 24
    cell_w, cell_h = 104, 96
    gap_x, gap_y = 17, 22
    for r in range(3):
        for c in range(5):
            x0 = pad_x + c * (cell_w + gap_x)
            y0 = pad_y + r * (cell_h + gap_y)
            col = palette[r * 5 + c]
            # Key tile dark glass frame + glowing icon core
            _rect(img, x0, y0, x0 + cell_w, y0 + cell_h, (24, 29, 40))
            _rect(img, x0 + 6, y0 + 6, x0 + cell_w - 6, y0 + cell_h - 6, (16, 20, 28))
            _rect(img, x0 + 24, y0 + 22, x0 + cell_w - 24, y0 + cell_h - 30, col)
            _rect(img, x0 + 20, y0 + cell_h - 18, x0 + cell_w - 20, y0 + cell_h - 12, (195, 206, 224))
    _write_png_rgb(path, img)
    return path


def generate_woven_rug_textures(out_dir: Path) -> tuple[Path, Path]:
    """
    Generate an authentic Nordic/Japanese hand-loomed heathered charcoal-taupe flatweave wool rug
    with crisp woven stitched end borders & subtle geometric cross-weave (zero flat grey slab look!).
    """
    albedo_path = out_dir / "rug_woven_albedo.png"
    bump_path = out_dir / "rug_woven_bump.png"
    n = 1024
    yy, xx = np.mgrid[0:n, 0:n]
    nx = xx / float(n)
    ny = yy / float(n)
    rng = np.random.default_rng(2027)

    # Rich tactile flatweave warp & weft basket pattern + authentic variegated heather wool strands
    warp = 0.5 + 0.5 * np.sin(2.0 * np.pi * xx / 6.0)
    weft = 0.5 + 0.5 * np.sin(2.0 * np.pi * yy / 9.0 + (xx // 6) * np.pi * 0.5)
    weave = 0.55 * weft + 0.45 * warp

    # Natural wool yarn melange streaks along X (horizontal loom weft striations)
    row_var = rng.normal(0.0, 0.016, (n, 1))
    col_var = rng.normal(0.0, 0.008, (1, n))
    micro_fiber = rng.normal(0.0, 0.032, (n, n))

    # Subtle minimalist Japanese architectural woven border stripes near left/right & top/bottom edges
    edge_frame = (
        ((nx > 0.035) & (nx < 0.050))
        | ((nx > 0.950) & (nx < 0.965))
        | ((ny > 0.045) & (ny < 0.058))
        | ((ny > 0.942) & (ny < 0.955))
    )
    inner_line = (
        ((nx > 0.064) & (nx < 0.070) & (ny > 0.075) & (ny < 0.925))
        | ((nx > 0.930) & (nx < 0.936) & (ny > 0.075) & (ny < 0.925))
    )
    # Warm charcoal-taupe wool base (#262523 .. #46433E in sRGB -> cozy natural wool, never flat cold grey!)
    base_val = np.clip(0.052 + 0.042 * weave + row_var + col_var + micro_fiber * 0.40, 0.020, 0.16)
    base_val = np.where(edge_frame, np.clip(base_val * 0.62, 0.014, 0.10), base_val)
    base_val = np.where(inner_line, np.clip(base_val * 1.42, 0.040, 0.22), base_val)

    albedo = np.zeros((n, n, 3), dtype=np.uint8)
    albedo[:, :, 0] = np.clip((base_val ** (1.0 / 2.2)) * 255 * 0.80, 0, 255).astype(np.uint8)
    albedo[:, :, 1] = np.clip((base_val ** (1.0 / 2.2)) * 255 * 0.77, 0, 255).astype(np.uint8)
    albedo[:, :, 2] = np.clip((base_val ** (1.0 / 2.2)) * 255 * 0.73, 0, 255).astype(np.uint8)

    bump_val = np.clip(0.5 + 0.36 * (weave - 0.5) + micro_fiber * 2.4 + np.where(edge_frame, 0.12, 0.0), 0.0, 1.0)
    bump = np.repeat((bump_val * 255).astype(np.uint8)[:, :, None], 3, axis=2)

    _write_png_rgb(albedo_path, albedo)
    _write_png_rgb(bump_path, bump)
    return albedo_path, bump_path


def generate_notebook_pages(path: Path) -> Path:
    """Warm cream Moleskine dot-grid open notebook page with subtle engineering wireframe & notes."""
    w, h = 512, 768
    rng = np.random.default_rng(77)
    img = np.full((h, w, 3), (228, 221, 206), dtype=np.float32)
    img += rng.normal(0.0, 2.2, (h, w, 1))
    img = np.clip(img, 0, 255).astype(np.uint8)

    # Subtle dot-grid pattern (5mm Moleskine feel)
    for y in range(44, h - 36, 22):
        for x in range(36, w - 36, 22):
            img[y : y + 2, x : x + 2] = (182, 174, 158)

    # Subtle dark graphite header rule & handwritten note strokes
    _rect(img, 42, 62, 230, 67, (62, 66, 74))
    _rect(img, 42, 74, w - 48, 76, (160, 154, 142))
    for i, (ln_w, col) in enumerate((
        (310, (78, 82, 90)), (265, (86, 90, 98)), (340, (74, 78, 86)),
        (195, (92, 96, 104)), (290, (78, 82, 90)),
    )):
        ry = 104 + i * 28
        # Checkbox square
        _rect(img, 46, ry - 4, 56, ry + 6, (104, 108, 116))
        _rect(img, 48, ry - 2, 54, ry + 4, (226, 219, 204))
        if i < 3:
            _rect(img, 49, ry - 1, 53, ry + 3, (186, 86, 48))
        # Simulated cursive ink line segments
        x = 70
        while x < 70 + ln_w:
            seg = int(rng.integers(18, 52))
            _rect(img, x, ry, min(x + seg, w - 48), ry + 3, col)
            x += seg + int(rng.integers(8, 16))

    # Architectural wireframe room layout sketch box in lower half
    bx0, by0, bx1, by1 = 56, 300, w - 56, 560
    _rect(img, bx0, by0, bx1, by0 + 3, (68, 72, 80))
    _rect(img, bx0, by1 - 3, bx1, by1, (68, 72, 80))
    _rect(img, bx0, by0, bx0 + 3, by1, (68, 72, 80))
    _rect(img, bx1 - 3, by0, bx1, by1, (68, 72, 80))
    # Internal room plan sketch partitions & desk rectangle
    _rect(img, bx0 + 110, by0 + 18, bx1 - 110, by0 + 78, (112, 116, 124))
    _rect(img, bx0 + 113, by0 + 21, bx1 - 113, by0 + 75, (226, 219, 204))
    _rect(img, bx0 + 145, by0 + 115, bx1 - 145, by0 + 195, (148, 140, 128))
    _rect(img, bx0 + 148, by0 + 118, bx1 - 148, by0 + 192, (226, 219, 204))
    # Terracotta highlight annotation arrow/note
    _rect(img, bx0 + 32, by1 + 26, bx0 + 185, by1 + 31, (186, 86, 48))
    _rect(img, bx0 + 32, by1 + 48, bx0 + 290, by1 + 52, (82, 86, 94))
    _rect(img, bx0 + 32, by1 + 70, bx0 + 235, by1 + 74, (90, 94, 102))

    _write_png_rgb(path, img)
    return path


def generate_teardown_frame(path: Path) -> Path:
    """Grid Studio-style Game Boy Classic (DMG-01) exploded hardware teardown blueprint frame (1024x1360)."""
    w, h = 1024, 1360
    rng = np.random.default_rng(1989)
    img = np.full((h, w, 3), (234, 231, 224), dtype=np.float32)
    img += rng.normal(0.0, 1.8, (h, w, 1))
    img = np.clip(img, 0, 255).astype(np.uint8)

    # Outer archival matte border & crisp dark drafting border
    _rect(img, 0, 0, w, 46, (242, 240, 235))
    _rect(img, 0, h - 46, w, h, (242, 240, 235))
    _rect(img, 0, 0, 46, h, (242, 240, 235))
    _rect(img, w - 46, 0, w, h, (242, 240, 235))
    _rect(img, 54, 54, w - 54, 58, (32, 34, 38))
    _rect(img, 54, h - 58, w - 54, h - 54, (32, 34, 38))
    _rect(img, 54, 54, 58, h - 54, (32, 34, 38))
    _rect(img, w - 58, 54, w - 54, h - 54, (32, 34, 38))

    # Subtle architectural drafting grid inside
    for gx in range(96, w - 70, 64):
        _rect(img, gx, 62, gx + 1, h - 62, (214, 211, 204))
    for gy in range(96, h - 70, 64):
        _rect(img, 62, gy, w - 62, gy + 1, (214, 211, 204))

    # Header Title Strip ("GAME BOY DMG-01  //  1989")
    _rect(img, 84, 86, 460, 114, (28, 30, 34))
    _rect(img, 84, 124, 310, 134, (148, 42, 74))
    _rect(img, 760, 88, 938, 112, (56, 60, 68))
    _rect(img, 84, 152, w - 84, 155, (42, 44, 48))

    # Row 1 Left: Front Shell Silhouette with LCD Window + Speaker Slots + Button Holes
    _rect(img, 96, 186, 360, 602, (196, 194, 186))
    _rect(img, 102, 192, 354, 596, (210, 208, 200))
    _rect(img, 128, 224, 328, 388, (76, 80, 86))     # dark grey screen bezel
    _rect(img, 158, 250, 298, 366, (234, 231, 224))  # cutout opening
    _rect(img, 136, 286, 144, 294, (196, 42, 46))    # battery LED dot
    # D-pad recess & A/B recesses
    _rect(img, 154, 434, 174, 494, (162, 160, 154))
    _rect(img, 134, 454, 194, 474, (162, 160, 154))
    _rect(img, 266, 458, 296, 488, (148, 38, 76))
    _rect(img, 308, 434, 338, 464, (148, 38, 76))
    # Diagonal speaker vents
    for si in range(5):
        _rect(img, 284 + si * 12, 536, 289 + si * 12, 578, (118, 118, 114))
    _rect(img, 96, 616, 250, 626, (58, 62, 68))      # component caption

    # Row 1 Center: Olive-Green Main CPU PCB Motherboard + QFP Chip + Gold Traces + Cartridge Connector
    _rect(img, 404, 188, 668, 574, (44, 82, 54))
    _rect(img, 412, 196, 660, 566, (52, 96, 62))
    # Cartridge pin header
    _rect(img, 438, 204, 634, 254, (32, 34, 38))
    for pin in range(22):
        _rect(img, 444 + pin * 8, 210, 448 + pin * 8, 248, (206, 174, 88))
    # Sharp LR35902 CPU QFP IC Chip with silver gull-wing pins
    _rect(img, 476, 302, 588, 414, (24, 26, 30))
    _rect(img, 492, 336, 572, 348, (176, 180, 186))
    _rect(img, 502, 358, 562, 366, (124, 128, 134))
    for p in range(12):
        _rect(img, 482 + p * 9, 292, 486 + p * 9, 302, (194, 198, 204))
        _rect(img, 482 + p * 9, 414, 486 + p * 9, 424, (194, 198, 204))
        _rect(img, 466, 308 + p * 9, 476, 312 + p * 9, (194, 198, 204))
        _rect(img, 588, 308 + p * 9, 598, 312 + p * 9, (194, 198, 204))
    # Secondary RAM IC + Crystal oscillator + electrolytic capacitors + gold traces
    _rect(img, 430, 448, 514, 520, (26, 28, 32))
    _rect(img, 544, 456, 582, 504, (192, 196, 202))
    _rect(img, 608, 448, 636, 478, (32, 62, 118))
    _rect(img, 608, 496, 636, 526, (32, 62, 118))
    for tx in range(424, 650, 18):
        _rect(img, tx, 262, tx + 2, 290, (98, 146, 86))
    _rect(img, 404, 590, 564, 600, (58, 62, 68))

    # Row 1 Right: Dot-Matrix Olive-Green LCD Module + Copper Ribbon Flex + Speaker Driver
    _rect(img, 710, 194, 926, 396, (38, 40, 44))
    _rect(img, 724, 208, 912, 372, (128, 146, 86))
    _rect(img, 738, 222, 898, 358, (144, 162, 98))
    _rect(img, 774, 396, 862, 464, (198, 128, 62))   # kapton amber flex cable
    for rline in range(8):
        _rect(img, 782 + rline * 10, 398, 785 + rline * 10, 462, (154, 94, 42))
    # Round magnetic speaker driver below LCD
    yy, xx = np.mgrid[484:604, 758:878]
    dist = np.sqrt((xx - 818) ** 2 + (yy - 544) ** 2)
    spk = img[484:604, 758:878]
    spk[dist < 54] = (46, 48, 52)
    spk[(dist >= 44) & (dist < 54)] = (182, 184, 188)
    spk[dist < 22] = (158, 162, 168)
    _rect(img, 710, 616, 868, 626, (58, 62, 68))

    # Horizontal divider
    _rect(img, 84, 656, w - 84, 658, (152, 150, 144))

    # Row 2: Tactile Buttons, Daughterboard, D-Pad, Rubber Pads, Metal RF Shield
    # Left: Button & D-pad Grid Box
    _rect(img, 114, 712, 144, 812, (28, 30, 34))
    _rect(img, 79, 747, 179, 777, (28, 30, 34))
    for cx, cy in ((232, 746), (294, 746)):
        yy2, xx2 = np.mgrid[cy - 26 : cy + 26, cx - 26 : cx + 26]
        d2 = np.sqrt((xx2 - cx) ** 2 + (yy2 - cy) ** 2)
        patch = img[cy - 26 : cy + 26, cx - 26 : cx + 26]
        patch[d2 < 24] = (152, 34, 76)
        patch[d2 < 14] = (172, 46, 88)
    _rect(img, 206, 804, 256, 822, (74, 76, 82))
    _rect(img, 270, 804, 320, 822, (74, 76, 82))
    _rect(img, 96, 856, 260, 866, (58, 62, 68))

    # Center: Front Control PCB with Gold Carbon Contact Pads
    _rect(img, 396, 694, 676, 874, (48, 92, 60))
    _rect(img, 434, 738, 496, 800, (198, 166, 78))
    _rect(img, 584, 738, 646, 800, (198, 166, 78))
    _rect(img, 514, 816, 566, 844, (198, 166, 78))
    _rect(img, 396, 890, 564, 900, (58, 62, 68))

    # Right: Brushed Aluminum RF Shield Plate + Power Regulator Module
    _rect(img, 720, 696, 924, 854, (176, 180, 186))
    _rect(img, 736, 712, 908, 838, (192, 196, 202))
    _rect(img, 756, 736, 820, 804, (152, 156, 162))
    _rect(img, 720, 870, 878, 880, (58, 62, 68))

    # Row 3: Rear Shell, Battery Contacts, Screws, Link Port & Specs Footer
    _rect(img, 84, 932, w - 84, 934, (152, 150, 144))
    _rect(img, 96, 968, 356, 1188, (186, 184, 176))
    _rect(img, 128, 1002, 324, 1152, (164, 162, 154))
    # 4 Silver AA Battery Springs + 6 Precision Tri-Wing Screws laid out cleanly
    for bi in range(4):
        _rect(img, 404 + bi * 66, 982, 446 + bi * 66, 1084, (172, 176, 182))
        _rect(img, 412 + bi * 66, 1004, 438 + bi * 66, 1062, (124, 128, 134))
    for sci in range(6):
        _rect(img, 408 + sci * 44, 1126, 424 + sci * 44, 1170, (74, 78, 84))
        _rect(img, 404 + sci * 44, 1122, 428 + sci * 44, 1134, (162, 166, 172))
    # Technical Spec Sheet Block Bottom-Right
    _rect(img, 710, 976, 926, 992, (28, 30, 34))
    for srow in range(7):
        _rect(img, 710, 1012 + srow * 24, 792, 1020 + srow * 24, (108, 112, 118))
        _rect(img, 808, 1012 + srow * 24, 868 + (srow * 23) % 58, 1020 + srow * 24, (44, 48, 54))
    # Crisp Bottom Edition Colophon Bar
    _rect(img, 84, 1244, w - 84, 1247, (36, 38, 42))
    _rect(img, 84, 1264, 340, 1278, (36, 38, 42))
    _rect(img, 748, 1264, 940, 1278, (148, 42, 74))

    _write_png_rgb(path, img)
    return path


def generate_geek_book_spines(path: Path) -> Path:
    """
    16 authentic high-taste geek, computer science, industrial design & Japanese architecture book spines
    packed into 16 clean vertical UV columns (1024x512). Zero Victorian leather encyclopedias!
    """
    w, h = 1024, 512
    cols = 16
    cw = w // cols
    img = np.zeros((h, w, 3), dtype=np.uint8)
    rng = np.random.default_rng(2026)

    # (bg_rgb, band_rgb, accent_rgb, text_rgb, style)
    specs = [
        ((232, 230, 224), (192, 38, 44), (28, 30, 34), (24, 26, 30), "oreilly"),      # 0 O'Reilly DDIA
        ((228, 228, 224), (22, 124, 134), (28, 30, 34), (24, 26, 30), "oreilly"),     # 1 O'Reilly Systems
        ((24, 26, 32), (24, 26, 32), (218, 168, 58), (228, 226, 218), "mit_dark"),    # 2 Real-Time Rendering
        ((238, 236, 230), (238, 236, 230), (212, 48, 36), (22, 24, 28), "swiss"),     # 3 Dieter Rams Less But Better
        ((186, 34, 38), (242, 240, 234), (24, 26, 30), (244, 242, 238), "akira"),     # 4 AKIRA Vol. 1
        ((26, 44, 72), (26, 44, 72), (76, 178, 232), (236, 238, 242), "tech"),        # 5 PBR Book
        ((234, 228, 214), (32, 34, 38), (214, 96, 44), (28, 30, 34), "brutus"),       # 6 Casa BRUTUS Tokyo
        ((38, 40, 44), (196, 88, 38), (234, 230, 220), (232, 230, 224), "design"),    # 7 Braun Design Monograph
        ((216, 220, 224), (28, 56, 112), (228, 66, 52), (22, 24, 28), "popeye"),      # 8 POPEYE Editorial
        ((20, 22, 26), (52, 166, 184), (234, 236, 240), (218, 224, 232), "cyber"),    # 9 Ghost in the Shell Artbook
        ((226, 222, 212), (226, 222, 212), (34, 36, 40), (26, 28, 32), "swiss"),      # 10 Tadao Ando Concrete
        ((46, 58, 50), (212, 166, 72), (234, 230, 220), (234, 230, 220), "mit_dark"), # 11 SICP / Compilers
        ((204, 68, 36), (24, 26, 30), (240, 236, 228), (242, 238, 232), "akira"),     # 12 Nintendo Hardware Archive
        ((30, 34, 42), (30, 34, 42), (126, 98, 218), (226, 230, 238), "tech"),        # 13 Shader & GPU Gems
        ((224, 216, 200), (146, 62, 42), (32, 34, 38), (28, 30, 34), "brutus"),       # 14 Tokyo Architecture Map
        ((18, 20, 24), (18, 20, 24), (230, 230, 226), (214, 216, 220), "design"),     # 15 Minimalist Typo Grid
    ]

    for idx, (bg, band, acc, txt, style) in enumerate(specs):
        x0 = idx * cw
        x1 = x0 + cw
        _rect(img, x0, 0, x1, h, bg)
        # Subtle spine edge shadow for crisp book separation
        _rect(img, x0, 0, x0 + 3, h, tuple(max(0, int(c * 0.72)) for c in bg))
        _rect(img, x1 - 3, 0, x1, h, tuple(max(0, int(c * 0.72)) for c in bg))

        if style == "oreilly":
            _rect(img, x0 + 4, 0, x1 - 4, 64, band)
            _rect(img, x0 + 4, h - 72, x1 - 4, h, band)
            # Vertical title bars along spine
            _rect(img, x0 + 18, 96, x0 + 32, 336, txt)
            _rect(img, x0 + 38, 118, x0 + 45, 298, acc)
            _rect(img, x0 + 16, h - 52, x1 - 16, h - 38, (242, 242, 242))
        elif style == "swiss":
            _rect(img, x0 + 10, 48, x1 - 10, 72, acc)
            _rect(img, x0 + 20, 108, x0 + 32, 312, txt)
            _rect(img, x0 + 38, 108, x0 + 44, 246, txt)
            _rect(img, x0 + 18, h - 78, x1 - 18, h - 54, txt)
        elif style == "akira":
            _rect(img, x0 + 6, 36, x1 - 6, 124, band)
            _rect(img, x0 + 16, 56, x1 - 16, 104, acc)
            _rect(img, x0 + 20, 160, x0 + 42, 372, txt)
            _rect(img, x0 + 16, h - 76, x1 - 16, h - 42, band)
        elif style == "brutus":
            _rect(img, x0 + 4, 28, x1 - 4, 92, band)
            _rect(img, x0 + 14, 48, x1 - 14, 72, (240, 236, 228))
            _rect(img, x0 + 22, 128, x0 + 38, 348, txt)
            _rect(img, x0 + 14, 386, x1 - 14, 412, acc)
            _rect(img, x0 + 18, h - 56, x1 - 18, h - 42, txt)
        elif style in ("mit_dark", "tech", "cyber"):
            _rect(img, x0 + 4, 36, x1 - 4, 50, acc)
            _rect(img, x0 + 4, h - 86, x1 - 4, h - 76, acc)
            _rect(img, x0 + 20, 86, x0 + 34, 326, txt)
            _rect(img, x0 + 40, 112, x0 + 46, 276, acc)
            _rect(img, x0 + 18, h - 56, x1 - 18, h - 38, txt)
        else:
            _rect(img, x0 + 4, 0, x1 - 4, 110, band)
            _rect(img, x0 + 14, 44, x1 - 14, 68, acc)
            _rect(img, x0 + 22, 146, x0 + 36, 358, txt)
            _rect(img, x0 + 14, h - 68, x1 - 14, h - 46, acc)

    noise = rng.normal(0.0, 2.2, (h, w, 3))
    img = np.clip(img.astype(np.float32) + noise, 0, 255).astype(np.uint8)
    _write_png_rgb(path, img)
    return path


def generate_vinyl_album_covers(path: Path) -> Path:
    """2 iconic 512x512 Japanese City-Pop / Tokyo Lo-Fi Vinyl LP Sleeves side-by-side (1024x512)."""
    w, h = 1024, 512
    img = np.zeros((h, w, 3), dtype=np.uint8)

    # === COVER 1 (Left 0..512): "TOKYO MIDNIGHT SYNTH — VOL. 04" with classic Japanese OBI strip ===
    yy, xx = np.mgrid[0:512, 0:512]
    nx = xx / 512.0
    ny = yy / 512.0
    # Deep twilight indigo -> warm horizon amber gradient
    r = np.clip(14 + 36 * (ny ** 2) + 148 * np.exp(-((ny - 0.62) / 0.16) ** 2), 0, 255)
    g = np.clip(22 + 24 * (ny ** 2) + 74 * np.exp(-((ny - 0.62) / 0.14) ** 2), 0, 255)
    b = np.clip(58 + 72 * (1.0 - ny) + 28 * np.exp(-((ny - 0.45) / 0.25) ** 2), 0, 255)
    img[:, :512, 0] = r.astype(np.uint8)
    img[:, :512, 1] = g.astype(np.uint8)
    img[:, :512, 2] = b.astype(np.uint8)
    # Glowing geometric sunset disc sliced by retro horizontal scanlines
    sun = ((nx - 0.58) ** 2 + (ny - 0.50) ** 2) < (0.21 ** 2)
    scan = ((yy % 12) < 9) | (ny < 0.46)
    mask_sun = sun & scan
    img[:, :512][mask_sun] = (238, 122, 54)
    # Crisp dark Tokyo skyscraper silhouette along lower third
    skyline_heights = [0.74, 0.66, 0.72, 0.58, 0.68, 0.52, 0.64, 0.70, 0.60, 0.74, 0.65, 0.72]
    bw = 512 // len(skyline_heights)
    for i, bh in enumerate(skyline_heights):
        by0 = int(bh * 512)
        _rect(img, i * bw, by0, (i + 1) * bw - 2, 512, (12, 16, 26))
        # Tiny warm apartment lights inside skyline buildings
        for wy in range(by0 + 12, 496, 16):
            for wx in range(i * bw + 6, (i + 1) * bw - 10, 10):
                if (wx * 7 + wy * 13) % 5 == 0:
                    _rect(img, wx, wy, wx + 4, wy + 5, (242, 186, 98))
    # Classic Japanese Vinyl OBI Paper Strip along left edge (crisp cream + crimson graphic header)
    _rect(img, 24, 0, 104, 512, (236, 232, 222))
    _rect(img, 24, 38, 104, 118, (196, 46, 48))
    _rect(img, 42, 58, 86, 96, (238, 234, 226))
    for k in range(5):
        _rect(img, 46, 152 + k * 42, 82, 174 + k * 42, (28, 30, 36))
    _rect(img, 40, 428, 88, 444, (196, 46, 48))
    _rect(img, 40, 458, 88, 466, (38, 42, 48))
    # Bold editorial title strip top-right
    _rect(img, 140, 44, 468, 66, (238, 236, 230))
    _rect(img, 140, 78, 326, 88, (94, 188, 236))

    # === COVER 2 (Right 512..1024): Swiss Minimalist Architectural Vinyl Sleeve ===
    _rect(img, 512, 0, 1024, 512, (230, 226, 218))
    _rect(img, 548, 36, 988, 56, (26, 28, 32))
    _rect(img, 548, 68, 740, 78, (108, 110, 114))
    _rect(img, 548, 120, 790, 468, (28, 30, 34))
    _rect(img, 790, 120, 988, 318, (34, 88, 168))
    _rect(img, 790, 318, 988, 468, (206, 84, 42))
    # Concentric vinyl groove circle motif
    yy3, xx3 = np.mgrid[0:512, 512:1024]
    d3 = np.sqrt((xx3 - 768) ** 2 + (yy3 - 294) ** 2)
    ring = (np.abs(d3 - 110) < 6) | (np.abs(d3 - 72) < 4)
    img[:, 512:][ring] = (234, 230, 222)

    _write_png_rgb(path, img)
    return path


def generate_pixel_clock_ui(path: Path) -> Path:
    """LaMetric / Divoom glowing dot-matrix pixel LED clock ('00:24' + cyan equalizer bars, 512x128)."""
    w, h = 512, 128
    img = np.full((h, w, 3), (7, 8, 11), dtype=np.uint8)

    # Subtle unlit LED matrix dot grid background
    for py in range(8, h - 8, 12):
        for px in range(10, w - 10, 12):
            _rect(img, px, py, px + 7, py + 7, (15, 17, 22))

    def lit(gx: int, gy: int, col: tuple[int, int, int]) -> None:
        px = 10 + gx * 12
        py = 8 + gy * 12
        _rect(img, px, py, px + 8, py + 8, col)

    # Left live cyan audio/FPS spectrum icon (cols 1..6)
    bars = [3, 6, 8, 5, 7, 4]
    for bi, bh in enumerate(bars):
        for row in range(bh):
            col = (54, 212, 255) if row < 5 else (110, 244, 186)
            lit(1 + bi, 8 - row, col)

    # Crisp 5x7 dot-matrix digits: "00:24" in warm amber-orange LED glow
    digits = {
        "0": ["01110", "10001", "10011", "10101", "11001", "10001", "01110"],
        "2": ["01110", "10001", "00001", "00110", "01000", "10000", "11111"],
        "4": ["00010", "00110", "01010", "10010", "11111", "00010", "00010"],
        ":": ["0", "0", "1", "0", "1", "0", "0"],
    }
    text = "00:24"
    cur_x = 10
    for ch in text:
        pat = digits[ch]
        for ry, row_s in enumerate(pat):
            for rx, bit in enumerate(row_s):
                if bit == "1":
                    lit(cur_x + rx, 1 + ry, (255, 152, 54))
        cur_x += len(pat[0]) + 1

    # Subtle live green telemetry dot far right
    lit(38, 2, (64, 232, 136))
    lit(39, 2, (64, 232, 136))
    lit(38, 3, (64, 232, 136))
    lit(39, 3, (64, 232, 136))

    _write_png_rgb(path, img)
    return path


def generate_aio_lcd_ui(path: Path) -> Path:
    """Circular NZXT Kraken / HydroShift AIO CPU liquid-cooler LCD telemetry screen ('38°C', 256x256)."""
    n = 256
    img = np.full((n, n, 3), (6, 8, 12), dtype=np.uint8)
    yy, xx = np.mgrid[0:n, 0:n]
    cx, cy = n * 0.5, n * 0.5
    dist = np.sqrt((xx - cx) ** 2 + (yy - cy) ** 2)
    ang = np.arctan2(yy - cy, xx - cx)

    # Outer cyan radial temperature ring + subtle dark track
    track = (dist >= 94) & (dist <= 112)
    img[track] = (20, 32, 46)
    arc = track & ((ang < 1.1) | (ang > 2.4))
    img[arc] = (46, 206, 255)
    # Inner subtle ring
    inner = (dist >= 82) & (dist <= 85)
    img[inner] = (34, 72, 102)

    # Crisp blocky 5x7 readout "38" in ice-white/cyan center
    d38 = {
        "3": ["11110", "00001", "00001", "01110", "00001", "00001", "11110"],
        "8": ["01110", "10001", "10001", "01110", "10001", "10001", "01110"],
    }
    for ci, ch in enumerate(("3", "8")):
        ox = 74 + ci * 56
        oy = 88
        for ry, rs in enumerate(d38[ch]):
            for rx, b in enumerate(rs):
                if b == "1":
                    _rect(img, ox + rx * 9, oy + ry * 9, ox + rx * 9 + 7, oy + ry * 9 + 7, (226, 246, 255))
    # Degree dot + subtle amber "CPU" bar below
    _rect(img, 184, 90, 194, 100, (46, 206, 255))
    _rect(img, 102, 166, 154, 174, (255, 138, 56))

    _write_png_rgb(path, img)
    return path


def generate_wall_shelf_monochrome_art(path: Path) -> Path:
    """Crisp Swiss Industrial Design / Braun Dieter Rams Poster Print (800x1040) for the floating wall shelf."""
    w, h = 800, 1040
    rng = np.random.default_rng(1968)
    img = np.full((h, w, 3), (236, 233, 226), dtype=np.float32)
    img += rng.normal(0.0, 2.0, (h, w, 1))
    img = np.clip(img, 0, 255).astype(np.uint8)

    # White mat border + crisp Swiss grid lines
    _rect(img, 56, 62, w - 56, 66, (28, 30, 34))
    _rect(img, 56, 128, 430, 152, (26, 28, 32))
    _rect(img, 56, 166, 280, 178, (186, 62, 40))
    _rect(img, 56, 206, w - 56, 208, (148, 146, 140))

    # Minimalist Braun TP1 / Dieter Rams speaker-grid & concentric dial composition
    _rect(img, 76, 254, w - 76, 760, (32, 34, 38))
    _rect(img, 96, 274, w - 96, 740, (226, 223, 216))
    # Perforated speaker dot matrix on left half
    for gy in range(310, 710, 24):
        for gx in range(132, 412, 24):
            _rect(img, gx, gy, gx + 10, gy + 10, (36, 38, 42))
    # Iconic orange/charcoal precision rotary dial on right half
    yy, xx = np.mgrid[340:660, 440:720]
    d = np.sqrt((xx - 580) ** 2 + (yy - 500) ** 2)
    patch = img[340:660, 440:720]
    patch[d < 112] = (32, 34, 38)
    patch[d < 86] = (232, 229, 222)
    patch[d < 44] = (204, 72, 38)
    patch[d < 14] = (32, 34, 38)
    # Crisp bottom technical typography block
    _rect(img, 56, 816, w - 56, 818, (40, 42, 46))
    _rect(img, 56, 844, 310, 860, (34, 36, 40))
    _rect(img, 56, 876, 224, 886, (108, 110, 114))
    _rect(img, 570, 844, w - 56, 886, (204, 72, 38))
    _write_png_rgb(path, img)
    return path


def generate_arch_concrete_pbr(out_dir: Path) -> tuple[Path, Path, Path]:
    """
    Generate ultra-clean 1024px Tadao Ando / Japanese Smooth Architectural Cast Concrete ('清水混凝土')
    Albedo + Roughness + OpenGL Normal maps using pure NumPy FFT periodic filtering —
    refined neutral warm-cool stone grey (#929490), delicate formwork sheen clouds, ultra-fine micro-aggregate,
    ZERO muddy olive/stucco splotches, ZERO external dependencies!
    """
    albedo_p = out_dir / "arch_concrete_albedo.png"
    rough_p = out_dir / "arch_concrete_rough.png"
    normal_p = out_dir / "arch_concrete_normal.png"
    if albedo_p.exists() and rough_p.exists() and normal_p.exists():
        return albedo_p, rough_p, normal_p

    size = 1024
    rng = np.random.default_rng(2026)

    # Pure periodic spectral low-pass noise in frequency domain (100% seamless tiling, ultra-fast!)
    fx = np.fft.fftfreq(size)[:, None]
    fy = np.fft.fftfreq(size)[None, :]
    rad = np.sqrt(fx * fx + fy * fy)

    def _band_noise(cutoff: float, seed_shift: int) -> np.ndarray:
        r2 = np.random.default_rng(2026 + seed_shift)
        white = r2.normal(0.0, 1.0, (size, size)).astype(np.float32)
        spec = np.fft.fft2(white)
        filt = np.exp(-0.5 * (rad / cutoff) ** 2)
        filt[0, 0] = 0.0
        out = np.fft.ifft2(spec * filt).real.astype(np.float32)
        return out / max(1e-5, float(out.std()))

    n_macro = _band_noise(0.0045, 1) * 0.55 + _band_noise(0.012, 2) * 0.45
    n_mid = _band_noise(0.032, 3) * 0.60 + _band_noise(0.085, 4) * 0.40
    n_fine = rng.normal(0.0, 1.0, (size, size)).astype(np.float32)

    # Subtle horizontal formwork wood-press brushing (1.8% tonal whisper)
    row_f = np.exp(-0.5 * ((fx / 0.045) ** 2 + (fy / 0.0035) ** 2))
    row_f[0, 0] = 0.0
    row_grain = np.fft.ifft2(np.fft.fft2(rng.normal(0.0, 1.0, (size, size))) * row_f).real.astype(np.float32)
    row_grain = row_grain / max(1e-5, float(row_grain.std()))

    # Delicate cast-concrete air-bubble micro-pinholes (0.18% sparse soft dimples)
    pins = (rng.random((size, size)) > 0.9982).astype(np.float32)
    pin_f = np.exp(-0.5 * (rad / 0.14) ** 2)
    pin_mask = np.clip(np.fft.ifft2(np.fft.fft2(pins) * pin_f).real.astype(np.float32) * 3.8, 0.0, 1.0)

    # Refined smooth architectural concrete tone (neutral cool-warm stone grey ~150/255, ZERO yellow mud!)
    tone = 152.0 + n_macro * 7.2 + n_mid * 3.8 + row_grain * 2.6 + n_fine * 2.4 - pin_mask * 22.0
    r = np.clip(tone * 1.004, 92, 200)
    g = np.clip(tone * 1.000, 92, 200)
    b = np.clip(tone * 0.990, 90, 198)
    albedo = np.stack([r, g, b], axis=2).astype(np.uint8)

    # Satin-matte architectural concrete roughness (0.80..0.93)
    rough_v = np.clip(220.0 - n_macro * 8.0 + n_mid * 5.0 + pin_mask * 20.0, 196, 245).astype(np.uint8)
    rough_rgb = np.stack([rough_v, rough_v, rough_v], axis=2)

    # Subtle crisp OpenGL tangent-space Normal map (smooth cast concrete, zero coarse stucco lumps!)
    hmap = n_mid * 0.22 + row_grain * 0.10 + n_fine * 0.18 - pin_mask * 1.35
    dx = np.roll(hmap, -1, axis=1) - np.roll(hmap, 1, axis=1)
    dy = np.roll(hmap, -1, axis=0) - np.roll(hmap, 1, axis=0)
    strength = 0.45
    nx = -dx * strength
    ny = dy * strength
    nz = np.ones_like(hmap)
    inv_len = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nor = np.stack([
        np.clip((nx * inv_len * 0.5 + 0.5) * 255.0, 0, 255),
        np.clip((ny * inv_len * 0.5 + 0.5) * 255.0, 0, 255),
        np.clip((nz * inv_len * 0.5 + 0.5) * 255.0, 0, 255),
    ], axis=2).astype(np.uint8)

    _write_png_rgb(albedo_p, albedo)
    _write_png_rgb(rough_p, rough_rgb)
    _write_png_rgb(normal_p, nor)
    return albedo_p, rough_p, normal_p


def generate_stained_walnut_albedo(tex_dir: Path, out_dir: Path) -> Path:
    """
    Pre-bake rich deep oiled American Black Walnut stain directly into the 2048px wood grain texture
    using Blender's native image loader + NumPy so Cycles AND glTF/Three.js match 1:1 on desk & vertical slats!
    """
    out_p = out_dir / "walnut_oiled_albedo.png"
    if out_p.exists():
        return out_p
    import bpy

    src = tex_dir / "black_walnut_veneer_01" / "diffuse.jpg"
    im = bpy.data.images.load(str(src), check_existing=False)
    w, h = im.size[0], im.size[1]
    buf = np.empty(w * h * 4, dtype=np.float32)
    im.pixels.foreach_get(buf)
    bpy.data.images.remove(im)

    # Blender pixels are bottom-up sRGB [0..1]; flip vertically for PNG top-down
    arr = np.flipud(buf.reshape((h, w, 4))[:, :, :3])
    lin = np.power(np.clip(arr, 0.0, 1.0), 2.2)
    mean_lin = np.mean(lin, axis=(0, 1), keepdims=True)
    lin = np.clip((lin - mean_lin) * 1.30 + mean_lin, 0.005, 1.0)
    # Deep oiled American walnut linear stain
    stained_lin = np.stack([
        lin[:, :, 0] * 0.36,
        lin[:, :, 1] * 0.20,
        lin[:, :, 2] * 0.105,
    ], axis=2)
    srgb = np.power(np.clip(stained_lin, 0.0, 1.0), 1.0 / 2.2)
    _write_png_rgb(out_p, np.clip(srgb * 255.0, 0, 255).astype(np.uint8))
    return out_p


def generate_macbook_screen_ui(path: Path) -> Path:
    """Crisp macOS Sequoia Dark Mode Terminal + Architectural CAD/Render Dashboard (1600x1000) for Apple MacBook Air 15\"."""
    w, h = 1600, 1000
    img = np.zeros((h, w, 3), dtype=np.uint8)
    # Subtle deep twilight gradient wallpaper
    yy = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    img[:, :, 0] = np.clip(10 + 18 * (1.0 - yy) + 12 * xx, 0, 255).astype(np.uint8)
    img[:, :, 1] = np.clip(14 + 22 * (1.0 - yy) + 18 * np.sin(xx * 3.14), 0, 255).astype(np.uint8)
    img[:, :, 2] = np.clip(26 + 38 * (1.0 - yy) + 22 * (1.0 - xx), 0, 255).astype(np.uint8)

    # macOS Menu Bar + subtle notch silhouette at top center
    _rect(img, 0, 0, w, 30, (12, 15, 22))
    _rect(img, w // 2 - 72, 0, w // 2 + 72, 34, (4, 5, 8))
    for i, bx in enumerate((24, 68, 128, 196, 266)):
        _rect(img, bx, 11, bx + 36, 19, (186, 198, 218) if i == 0 else (112, 124, 144))
    _rect(img, w - 160, 10, w - 24, 20, (164, 178, 202))

    # Left Window: Dark macOS Terminal (H100 GPU Render & Vite Metrics)
    _rect(img, 42, 62, 824, 868, (13, 16, 23))
    _rect(img, 42, 62, 824, 100, (22, 27, 38))
    _rect(img, 60, 75, 72, 87, (235, 84, 74))
    _rect(img, 82, 75, 94, 87, (242, 184, 58))
    _rect(img, 104, 75, 116, 87, (74, 198, 98))
    _rect(img, 330, 76, 540, 86, (142, 156, 182))
    for r in range(26):
        ty = 122 + r * 27
        if r % 5 == 0:
            _rect(img, 64, ty, 128, ty + 9, (64, 214, 142))
            _rect(img, 142, ty, 380 + (r * 53) % 210, ty + 9, (198, 214, 238))
        elif r % 5 == 1:
            _rect(img, 82, ty, 180, ty + 9, (72, 174, 255))
            _rect(img, 194, ty, 520 + (r * 41) % 160, ty + 9, (132, 148, 174))
        elif r % 5 == 2:
            _rect(img, 82, ty, 240, ty + 9, (250, 168, 76))
            _rect(img, 254, ty, 490 + (r * 29) % 190, ty + 9, (164, 178, 204))
        elif r % 5 == 3:
            _rect(img, 82, ty, 150, ty + 9, (186, 118, 255))
            _rect(img, 166, ty, 440 + (r * 37) % 220, ty + 9, (118, 212, 144))

    # Right Window: Architectural Floorplan / Loft Blueprint CAD Preview!
    _rect(img, 856, 62, 1558, 868, (15, 20, 30))
    _rect(img, 856, 62, 1558, 100, (24, 30, 42))
    _rect(img, 876, 75, 888, 87, (235, 84, 74))
    _rect(img, 898, 75, 910, 87, (242, 184, 58))
    _rect(img, 920, 75, 932, 87, (74, 198, 98))
    # Subtle CAD grid lines
    for gx in range(886, 1538, 36):
        _rect(img, gx, 118, gx + 1, 740, (24, 34, 52))
    for gy in range(118, 740, 36):
        _rect(img, 886, gy, 1538, gy + 1, (24, 34, 52))
    # Loft 5-Zone CAD Outline in crisp cyan/amber blueprint vectors
    _rect(img, 930, 170, 1490, 174, (64, 198, 255))
    _rect(img, 930, 670, 1490, 674, (64, 198, 255))
    _rect(img, 930, 170, 934, 674, (64, 198, 255))
    _rect(img, 1486, 170, 1490, 674, (64, 198, 255))
    # Interior partition walls
    _rect(img, 1160, 170, 1164, 430, (248, 172, 74))
    _rect(img, 930, 430, 1340, 434, (248, 172, 74))
    _rect(img, 1340, 430, 1344, 674, (64, 198, 255))
    # Highlight active Zone 1 Studio room
    _rect(img, 946, 186, 1148, 418, (20, 42, 68))
    _rect(img, 978, 206, 1106, 254, (74, 186, 255))
    # Bottom status cards inside CAD app
    for ci, (cx0, col) in enumerate(((886, (64, 198, 255)), (1108, (74, 214, 142)), (1330, (248, 168, 76)))):
        _rect(img, cx0, 764, cx0 + 204, 842, (21, 28, 42))
        _rect(img, cx0 + 16, 782, cx0 + 110, 792, (124, 140, 166))
        _rect(img, cx0 + 16, 806, cx0 + 168, 824, col)

    # macOS Glass Dock at bottom center
    _rect(img, 420, 912, 1180, 984, (24, 30, 44))
    dock_cols = [
        (68, 168, 255), (56, 196, 128), (242, 152, 64), (178, 108, 255),
        (236, 84, 96), (62, 210, 224), (240, 202, 76), (92, 138, 255),
        (196, 206, 220), (48, 56, 74),
    ]
    for di, dc in enumerate(dock_cols):
        dx0 = 446 + di * 72
        _rect(img, dx0, 924, dx0 + 52, 972, dc)

    _write_png_rgb(path, img)
    return path


def generate_living_tv_ui(path: Path) -> Path:
    """Crisp 1920x1080 Dark PlayStation 5 / Apple TV 4K Architectural Cinema Dashboard for Zone 2 77\" OLED TV."""
    w, h = 1920, 1080
    img = np.zeros((h, w, 3), dtype=np.uint8)
    yy = np.linspace(0.0, 1.0, h, dtype=np.float32)[:, None]
    xx = np.linspace(0.0, 1.0, w, dtype=np.float32)[None, :]
    # Deep moody atmospheric cinema gradient (Tokyo dusk indigo -> warm amber horizon glow)
    r = 8 + 14 * (1.0 - yy) + 120 * np.exp(-((xx - 0.68) ** 2 / 0.14 + (yy - 0.42) ** 2 / 0.10))
    g = 11 + 16 * (1.0 - yy) + 56 * np.exp(-((xx - 0.68) ** 2 / 0.14 + (yy - 0.42) ** 2 / 0.10))
    b = 22 + 34 * (1.0 - yy) + 42 * np.exp(-((xx - 0.25) ** 2 / 0.18 + (yy - 0.35) ** 2 / 0.14))
    img[:, :, 0] = np.clip(r, 0, 255).astype(np.uint8)
    img[:, :, 1] = np.clip(g, 0, 255).astype(np.uint8)
    img[:, :, 2] = np.clip(b, 0, 255).astype(np.uint8)

    # Stylized futuristic Tokyo skyline silhouette across center cinema hero artwork
    rng = np.random.default_rng(77)
    for bx in range(0, w, 46):
        bh = int(rng.integers(140, 440))
        bw = int(rng.integers(32, 62))
        y0 = 660 - bh
        _rect(img, bx, y0, bx + bw, 660, (12, 16, 26))
        # Tiny warm cinema building windows
        for wy in range(y0 + 16, 648, 22):
            for wx in range(bx + 6, bx + bw - 8, 12):
                if rng.random() > 0.52:
                    col = (255, 186, 98) if rng.random() > 0.3 else (96, 198, 255)
                    _rect(img, wx, wy, wx + 6, wy + 10, col)

    # Bottom gradient scrim
    scrim = np.clip((yy - 0.52) / 0.48, 0.0, 1.0)
    img = (img.astype(np.float32) * (1.0 - 0.72 * scrim[:, :, None])).astype(np.uint8)

    # Top PS5 / Media navigation pills + time readout
    for i, (tx, tw) in enumerate(((88, 110), (224, 96), (346, 124))):
        _rect(img, tx, 56, tx + tw, 72, (238, 244, 255) if i == 0 else (110, 124, 148))
    _rect(img, w - 220, 54, w - 88, 76, (216, 228, 246))

    # Hero Featured Title Block (Left)
    _rect(img, 92, 430, 210, 456, (232, 108, 48))
    _rect(img, 92, 476, 610, 526, (240, 245, 252))
    _rect(img, 92, 546, 480, 564, (156, 172, 196))
    _rect(img, 92, 594, 286, 646, (238, 242, 250))  # Play CTA pill
    _rect(img, 308, 594, 446, 646, (34, 42, 58))

    # Bottom row of 6 Crisp 4K Game / Cinema Cards (selected active cyan halo on Card 0!)
    card_palettes = [
        ((32, 122, 198), (248, 162, 72)),
        ((186, 58, 54), (242, 198, 86)),
        ((46, 148, 118), (112, 226, 214)),
        ((118, 68, 182), (236, 114, 178)),
        ((192, 112, 44), (248, 212, 126)),
        ((52, 86, 148), (144, 188, 246)),
    ]
    for ci, (c1, c2) in enumerate(card_palettes):
        cx0 = 92 + ci * 292
        cy0 = 720 if ci > 0 else 704
        cw, ch = 266, 248 if ci > 0 else 264
        if ci == 0:
            _rect(img, cx0 - 5, cy0 - 5, cx0 + cw + 5, cy0 + ch + 5, (72, 198, 255))
        _rect(img, cx0, cy0, cx0 + cw, cy0 + ch, (18, 24, 36))
        _rect(img, cx0 + 12, cy0 + 12, cx0 + cw - 12, cy0 + ch - 56, c1)
        _rect(img, cx0 + 36, cy0 + 48, cx0 + cw - 36, cy0 + ch - 84, c2)
        _rect(img, cx0 + 16, cy0 + ch - 38, cx0 + cw - 72, cy0 + ch - 24, (206, 218, 236))

    _write_png_rgb(path, img)
    return path


def generate_bed_art_horizon(path: Path) -> Path:
    """Hiroshi Sugimoto-inspired serene nocturnal sea & twilight horizon fine-art monochrome print (900x1200)."""
    w, h = 900, 1200
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = xx / float(w)
    ny = yy / float(h)
    rng = np.random.default_rng(404)

    # Archival gallery mat cream border
    img = np.full((h, w, 3), (224, 220, 212), dtype=np.float32)
    in_x = (nx >= 0.10) & (nx <= 0.90)
    in_y = (ny >= 0.08) & (ny <= 0.92)
    inner = in_x & in_y

    # Subtle atmospheric horizon line at ny = 0.50 (soft misty twilight sky above, dark textured nocturnal sea below)
    dy = ny - 0.50
    sky_grad = np.clip(1.0 - np.abs(dy) * 2.1, 0.0, 1.0)
    sea_ripples = (
        np.sin(ny * 260.0 + np.sin(nx * 24.0) * 1.4) * 3.5
        + np.sin(ny * 620.0 + nx * 18.0) * 1.8
    ) * np.clip(dy * 5.0, 0.0, 1.0)
    film_grain = rng.normal(0.0, 3.2, (h, w))

    # Upper sky: soft warm silver-graphite fading up into deep charcoal; lower sea: velvety obsidian with soft horizon reflection
    upper_val = 46.0 + 74.0 * np.exp(-np.maximum(0.0, -dy) * 6.2)
    lower_val = 24.0 + 36.0 * np.exp(-np.maximum(0.0, dy) * 7.8) + sea_ripples
    val = np.where(dy < 0.0, upper_val, lower_val) + film_grain + sky_grad * 10.0

    # Cool silver-warm platinum print toning
    r = np.clip(val * 0.98, 12, 180)
    g = np.clip(val * 0.99, 12, 182)
    b = np.clip(val * 1.04, 14, 190)
    img[inner, 0] = r[inner]
    img[inner, 1] = g[inner]
    img[inner, 2] = b[inner]

    # Thin crisp graphite inner rule around artwork aperture
    ap_edge = (
        ((np.abs(nx - 0.10) < 0.0025) | (np.abs(nx - 0.90) < 0.0025)) & in_y
    ) | (
        ((np.abs(ny - 0.08) < 0.002) | (np.abs(ny - 0.92) < 0.002)) & in_x
    )
    img[ap_edge] = (72, 70, 68)

    _write_png_rgb(path, np.clip(img, 0, 255).astype(np.uint8))
    return path


def generate_bed_art_sumi(path: Path) -> Path:
    """Wabi-sabi Japanese minimalist architectural Sumi-e charcoal stone/enso diptych companion (900x1200)."""
    w, h = 900, 1200
    yy, xx = np.mgrid[0:h, 0:w].astype(np.float32)
    nx = xx / float(w)
    ny = yy / float(h)
    rng = np.random.default_rng(409)
    paper = rng.normal(0.0, 2.8, (h, w, 1))

    # Archival warm stone-cream Japanese washi paper + slightly darker inner art sheet
    img = np.full((h, w, 3), (224, 220, 212), dtype=np.float32)
    inner = (nx >= 0.10) & (nx <= 0.90) & (ny >= 0.08) & (ny <= 0.92)
    img[inner] = (198, 192, 181)

    # Organic bold Sumi-e open brushed circle (Enso) + quiet horizontal ink horizon stroke
    cx, cy = 0.50, 0.44
    ang = np.arctan2((ny - cy) * (h / float(w)), nx - cx)
    rad = np.sqrt((nx - cx) ** 2 + ((ny - cy) * (h / float(w))) ** 2)
    brush_w = 0.036 + 0.014 * np.sin(ang * 2.0 + 0.7) + 0.005 * np.sin(ang * 7.0)
    gap = np.abs(ang - 0.58) > 0.24
    ring = (np.abs(rad - 0.22) < brush_w) & gap & inner
    # Soft feathered ink bleed on brush edges
    ink_alpha = np.clip(1.0 - np.abs(rad - 0.22) / np.maximum(0.001, brush_w), 0.0, 1.0)
    ink_alpha = np.where(gap & inner, np.power(ink_alpha, 0.55), 0.0)
    dry_bristle = 0.72 + 0.28 * np.sin(rad * 420.0 + ang * 9.0)
    ink_f = np.clip(ink_alpha * dry_bristle, 0.0, 1.0)[:, :, None]
    ink_col = np.array([[[28.0, 28.0, 30.0]]], dtype=np.float32)
    img = img * (1.0 - ink_f) + ink_col * ink_f

    # Subtle architectural monolithic ground bar below
    bar = (nx > 0.24) & (nx < 0.76) & (ny > 0.76) & (ny < 0.79)
    img[bar] = (42, 40, 38)
    # Tiny vermilion traditional artist hanko seal stamp bottom-right
    seal = (nx > 0.72) & (nx < 0.76) & (ny > 0.81) & (ny < 0.84)
    img[seal] = (162, 54, 42)

    img = np.clip(img + paper, 0, 255).astype(np.uint8)
    _write_png_rgb(path, img)
    return path


def generate_maker_blueprint_art(path: Path) -> Path:
    """Hardcore Tokyo Engineer Technical Blueprint: GPU Die Floorplan & Mechanical Switch Schematic (900x1200)."""
    w, h = 900, 1200
    img = np.full((h, w, 3), (17, 22, 31), dtype=np.uint8)  # Deep architectural slate-navy blueprint

    # Subtle CAD engineering millimeter grid
    for gx in range(48, w - 48, 32):
        _rect(img, gx, 48, gx + 1, h - 48, (26, 34, 48))
    for gy in range(48, h - 48, 32):
        _rect(img, 48, gy, w - 48, gy + 1, (26, 34, 48))

    # Crisp double CAD border + title block bottom-right
    _rect(img, 44, 44, w - 44, 48, (186, 198, 216))
    _rect(img, 44, h - 48, w - 44, h - 44, (186, 198, 216))
    _rect(img, 44, 44, 48, h - 44, (186, 198, 216))
    _rect(img, w - 48, 44, w - 44, h - 44, (186, 198, 216))

    # Upper Half: Silicon GPU Die / H100 Architecture Floorplan in crisp copper-gold & ice-white traces!
    dx0, dy0, dx1, dy1 = 150, 130, 750, 610
    _rect(img, dx0, dy0, dx1, dy1, (22, 30, 44))
    _rect(img, dx0, dy0, dx1, dy0 + 3, (216, 146, 76))
    _rect(img, dx0, dy1 - 3, dx1, dy1, (216, 146, 76))
    _rect(img, dx0, dy0, dx0 + 3, dy1, (216, 146, 76))
    _rect(img, dx1 - 3, dy0, dx1, dy1, (216, 146, 76))
    # 8x6 Tensor Core SM Array blocks + central L2 cache bus
    for r in range(6):
        for c in range(8):
            bx = dx0 + 28 + c * 68
            by = dy0 + 28 + r * 72 + (14 if r >= 3 else 0)
            col = (44, 62, 88) if (r + c) % 2 == 0 else (36, 52, 74)
            _rect(img, bx, by, bx + 54, by + 56, col)
            _rect(img, bx + 6, by + 6, bx + 48, by + 10, (148, 196, 232))
            _rect(img, bx + 6, by + 44, bx + 32, by + 48, (216, 146, 76))
    # Central HBM3 / L2 interconnect spine
    _rect(img, dx0 + 22, (dy0 + dy1) // 2 - 8, dx1 - 22, (dy0 + dy1) // 2 + 8, (216, 146, 76))

    # Lower Half: Mechanical Tactile Switch Exploded Cross-Section CAD Diagram
    sx0, sy0, sx1, sy1 = 150, 680, 750, 990
    _rect(img, sx0, sy0, sx1, sy0 + 2, (124, 146, 174))
    # Keycap profile outline + MX stem cross + copper leaf contact + coiled spring
    _rect(img, 290, 720, 610, 724, (224, 232, 244))
    _rect(img, 270, 724, 274, 800, (224, 232, 244))
    _rect(img, 626, 724, 630, 800, (224, 232, 244))
    _rect(img, 270, 800, 630, 804, (224, 232, 244))
    # MX Cross Stem (terracotta-copper highlight)
    _rect(img, 434, 756, 466, 868, (228, 134, 68))
    _rect(img, 396, 818, 504, 840, (228, 134, 68))
    # Coiled spring zig-zag lines
    for si in range(7):
        sy = 876 + si * 14
        _rect(img, 418, sy, 482, sy + 3, (172, 194, 220))
    # Switch lower housing + gold PCB pins
    _rect(img, 330, 848, 570, 972, (28, 38, 54))
    _rect(img, 330, 848, 570, 851, (186, 198, 216))
    _rect(img, 330, 969, 570, 972, (186, 198, 216))
    _rect(img, 392, 972, 404, 1020, (216, 162, 74))
    _rect(img, 496, 972, 508, 1020, (216, 162, 74))

    # Bottom CAD Title Block
    _rect(img, 480, 1054, w - 62, h - 62, (24, 32, 46))
    _rect(img, 480, 1054, w - 62, 1057, (186, 198, 216))
    _rect(img, 504, 1078, 720, 1090, (216, 146, 76))
    _rect(img, 504, 1106, 780, 1114, (164, 178, 202))
    _rect(img, 504, 1126, 680, 1132, (112, 128, 152))

    _write_png_rgb(path, img)
    return path


def generate_dark_marble_pbr(tex_dir: Path, out_dir: Path) -> tuple[Path, Path, Path]:
    """
    Generate a 100% seamless monolithic 1024px Honed Italian Pietra Grey / Nero Marquina stone slab:
    Deep charcoal-basalt mineral matrix with sparse, ultra-fine diagonal geological calcite fractures
    (ZERO tile grid seams, ZERO circular contour rings, smooth honed stone roughness & normal map!).
    """
    albedo_p = out_dir / "dark_marble_slab_v3_albedo.png"
    rough_p = out_dir / "dark_marble_slab_v3_rough.png"
    nor_p = out_dir / "dark_marble_slab_v3_normal.png"
    if albedo_p.exists() and rough_p.exists() and nor_p.exists():
        return albedo_p, rough_p, nor_p

    size = 1024
    fx = np.fft.fftfreq(size)[:, None]
    fy = np.fft.fftfreq(size)[None, :]
    rad = np.sqrt(fx * fx + fy * fy)

    def _fbm(freqs: list[tuple[float, float]], seed: int) -> np.ndarray:
        r = np.random.default_rng(seed)
        acc = np.zeros((size, size), dtype=np.float32)
        for cutoff, amp in freqs:
            spec = np.fft.fft2(r.normal(0.0, 1.0, (size, size)).astype(np.float32))
            filt = np.exp(-0.5 * (rad / cutoff) ** 2)
            filt[0, 0] = 0.0
            layer = np.fft.ifft2(spec * filt).real.astype(np.float32)
            acc += (layer / max(1e-5, float(layer.std()))) * amp
        return acc

    yy, xx = np.mgrid[0:size, 0:size].astype(np.float32) / float(size)
    # Multi-scale anisotropic geological warp (gentle sweeping strata, NEVER closed contour loops!)
    warp_a = _fbm([(0.004, 0.14), (0.012, 0.055), (0.032, 0.018), (0.08, 0.005)], 711)
    warp_b = _fbm([(0.005, 0.12), (0.016, 0.045), (0.042, 0.014)], 719)
    cloud = _fbm([(0.006, 0.65), (0.022, 0.25), (0.070, 0.10)], 727)
    micro = np.random.default_rng(733).normal(0.0, 1.0, (size, size)).astype(np.float32)

    # Diagonal mineral cleavage bands (integer cycle frequencies keep seamless tiling 100% periodic!)
    d1 = np.abs(np.sin((xx * 1.0 + yy * 2.0 + warp_a) * math.pi))
    d2 = np.abs(np.sin((xx * 2.0 + yy * 1.0 + warp_b + 0.37) * math.pi))
    # Razor-thin crisp primary calcite veins + delicate secondary warm-mineral threads (sparse, gallery-grade!)
    vein_main = np.exp(-((d1 / 0.012) ** 2)) * np.clip(0.45 + 0.55 * np.sin((xx * 1.0 - yy * 1.0 + warp_b) * math.pi * 2.0), 0.15, 1.0)
    vein_fine = np.exp(-((d2 / 0.007) ** 2)) * 0.52 * np.clip(0.5 + 0.5 * np.cos((xx * 2.0 - yy * 1.0 + warp_a) * math.pi * 2.0), 0.1, 1.0)
    vein_soft = np.exp(-((d1 / 0.055) ** 2)) * 0.14  # Subtle smoky mineral halo around main fissure

    # Deep refined Pietra Grey / Nero Marquina stone base (RGB ~ 26..40, matte-satin monolithic luxury!)
    base = 30.0 + cloud * 5.2 + micro * 1.4
    r = np.clip(base * 0.99 + vein_soft * 46.0 + vein_main * 142.0 + vein_fine * 108.0, 16, 204)
    g = np.clip(base * 1.00 + vein_soft * 45.0 + vein_main * 139.0 + vein_fine * 98.0, 16, 200)
    b = np.clip(base * 1.02 + vein_soft * 44.0 + vein_main * 132.0 + vein_fine * 82.0, 18, 192)
    albedo = np.stack([r, g, b], axis=2).astype(np.uint8)

    # Smooth honed architectural stone roughness (0.26..0.38)
    rv = np.clip(78.0 - cloud * 7.0 + vein_main * 18.0 + micro * 3.0, 58, 114).astype(np.uint8)
    rough = np.stack([rv, rv, rv], axis=2)

    # Subtle natural honed stone micro-relief normal map
    hmap = cloud * 0.25 - vein_main * 0.45 + micro * 0.08
    dx = np.roll(hmap, -1, axis=1) - np.roll(hmap, 1, axis=1)
    dy = np.roll(hmap, -1, axis=0) - np.roll(hmap, 1, axis=0)
    nx_n, ny_n, nz_n = -dx * 0.32, dy * 0.32, np.ones_like(hmap)
    inv_l = 1.0 / np.sqrt(nx_n * nx_n + ny_n * ny_n + nz_n * nz_n)
    nor = np.stack([
        np.clip((nx_n * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
        np.clip((ny_n * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
        np.clip((nz_n * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
    ], axis=2).astype(np.uint8)

    _write_png_rgb(albedo_p, albedo)
    _write_png_rgb(rough_p, rough)
    _write_png_rgb(nor_p, nor)
    return albedo_p, rough_p, nor_p


def generate_spa_stone_tile_pbr(out_dir: Path) -> tuple[Path, Path]:
    """Generate 1024px Large-Format Japanese Dark Basalt / Limestone Spa Tile with ultra-crisp 2mm grout grid."""
    albedo_p = out_dir / "spa_stone_albedo.png"
    normal_p = out_dir / "spa_stone_normal.png"
    if albedo_p.exists() and normal_p.exists():
        return albedo_p, normal_p

    size = 1024
    rng = np.random.default_rng(509)
    fx = np.fft.fftfreq(size)[:, None]
    fy = np.fft.fftfreq(size)[None, :]
    rad = np.sqrt(fx * fx + fy * fy)
    cloud = np.fft.ifft2(np.fft.fft2(rng.normal(0.0, 1.0, (size, size))) * np.exp(-0.5 * (rad / 0.015) ** 2)).real.astype(np.float32)
    cloud = cloud / max(1e-5, float(cloud.std()))
    fine = rng.normal(0.0, 1.0, (size, size)).astype(np.float32)

    # 2x4 large-format architectural slate tiles with crisp 3px dark grout lines
    tile_x = np.arange(size)[None, :] % 512
    tile_y = np.arange(size)[:, None] % 256
    grout = ((tile_x < 4) | (tile_y < 4)).astype(np.float32)

    tone = 88.0 + cloud * 2.8 + fine * 1.8 - grout * 42.0
    r = np.clip(tone * 1.01, 22, 130)
    g = np.clip(tone * 1.00, 22, 130)
    b = np.clip(tone * 0.97, 20, 126)
    albedo = np.stack([r, g, b], axis=2).astype(np.uint8)

    hmap = cloud * 0.15 + fine * 0.12 - grout * 2.4
    dx = np.roll(hmap, -1, axis=1) - np.roll(hmap, 1, axis=1)
    dy = np.roll(hmap, -1, axis=0) - np.roll(hmap, 1, axis=0)
    nx, ny, nz = -dx * 0.55, dy * 0.55, np.ones_like(hmap)
    inv_l = 1.0 / np.sqrt(nx * nx + ny * ny + nz * nz)
    nor = np.stack([
        np.clip((nx * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
        np.clip((ny * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
        np.clip((nz * inv_l * 0.5 + 0.5) * 255.0, 0, 255),
    ], axis=2).astype(np.uint8)

    _write_png_rgb(albedo_p, albedo)
    _write_png_rgb(normal_p, nor)
    return albedo_p, normal_p


def generate_all_studio_screens(out_dir: Path) -> dict[str, Path]:
    from config import TEX_DIR
    rug_albedo, rug_bump = generate_woven_rug_textures(out_dir)
    conc_albedo, conc_rough, conc_normal = generate_arch_concrete_pbr(out_dir)
    walnut_oiled = generate_stained_walnut_albedo(TEX_DIR, out_dir)
    marble_albedo, marble_rough, marble_normal = generate_dark_marble_pbr(TEX_DIR, out_dir)
    spa_albedo, spa_normal = generate_spa_stone_tile_pbr(out_dir)
    return {
        "ultrawide": generate_ultrawide_ide(out_dir / "screen_ultrawide_ide.png"),
        "vertical": generate_vertical_telemetry(out_dir / "screen_vertical_telemetry.png"),
        "stream_deck": generate_stream_deck_ui(out_dir / "screen_stream_deck.png"),
        "macbook_screen": generate_macbook_screen_ui(out_dir / "screen_macbook_ui.png"),
        "living_tv": generate_living_tv_ui(out_dir / "screen_living_tv.png"),
        "wall_art": generate_gallery_artwork(out_dir / "gallery_wall_art.png"),
        "wall_art_rams": generate_wall_shelf_monochrome_art(out_dir / "wall_art_rams.png"),
        "bed_art_horizon": generate_bed_art_horizon(out_dir / "bed_art_horizon_v2.png"),
        "bed_art_sumi": generate_bed_art_sumi(out_dir / "bed_art_sumi_v2.png"),
        "bed_gallery_hero": (out_dir / "bed_gallery_hero_art.jpg") if (out_dir / "bed_gallery_hero_art.jpg").exists() else generate_bed_art_horizon(out_dir / "bed_art_horizon_v2.png"),
        "living_gallery_hero": (out_dir / "living_gallery_hero_art.jpg") if (out_dir / "living_gallery_hero_art.jpg").exists() else generate_wall_shelf_monochrome_art(out_dir / "wall_art_rams.png"),
        "maker_blueprint": generate_maker_blueprint_art(out_dir / "maker_blueprint_v2.png"),
        "teardown_frame": generate_teardown_frame(out_dir / "teardown_frame.png"),
        "geek_book_spines": generate_geek_book_spines(out_dir / "geek_book_spines.png"),
        "vinyl_album_covers": generate_vinyl_album_covers(out_dir / "vinyl_album_covers.png"),
        "pixel_clock_ui": generate_pixel_clock_ui(out_dir / "pixel_clock_ui.png"),
        "aio_lcd_ui": generate_aio_lcd_ui(out_dir / "aio_lcd_ui.png"),
        "notebook_page": generate_notebook_pages(out_dir / "notebook_pages.png"),
        "rug_albedo": rug_albedo,
        "rug_bump": rug_bump,
        "arch_concrete_albedo": conc_albedo,
        "arch_concrete_rough": conc_rough,
        "arch_concrete_normal": conc_normal,
        "walnut_oiled_albedo": walnut_oiled,
        "dark_marble_albedo": marble_albedo,
        "dark_marble_rough": marble_rough,
        "dark_marble_normal": marble_normal,
        "spa_stone_albedo": spa_albedo,
        "spa_stone_normal": spa_normal,
    }
