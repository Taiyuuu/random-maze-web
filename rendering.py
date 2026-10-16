"""Rendering helpers and image/fog caches for the maze game."""
import os
from mckPy import *
from settings_io import THEMES, DEFAULT_THEME

# Highlight colour of each season in the options menu
THEME_COLORS = {
    "default": (120, 170, 255),
    "spring": (130, 205, 95),
    "summer": (240, 200, 60),
    "autumn": (215, 115, 45),
    "winter": (140, 195, 235),
}

loaded_tiles = {}
TILE_NAMES = ["grass", "dirt", "4", "n", "e", "s", "w", "ns", "we",
              "ne", "nw", "se", "sw", "3_n", "3_e", "3_s", "3_w"]

def draw_wall_shadows(maze, light_wx, light_wy, light_sx, light_sy, cam_x, cam_y, reach_px, radius_px, cell_size):
    cs = cell_size
    rng = int(reach_px // cs) + 2
    pc, pr = int(light_wx // cs), int(light_wy // cs)
    c0, c1 = max(0, pc - rng), min(maze.cols, pc + rng + 1)
    r0, r1 = max(0, pr - rng), min(maze.rows, pr + rng + 1)
    grid = maze.grid

    def wall_h(c, rl):
        return (rl < maze.rows and grid[c][rl].walls['N']) or \
               (rl > 0 and grid[c][rl - 1].walls['S'])

    def wall_v(cl, r):
        return (cl < maze.cols and grid[cl][r].walls['W']) or \
               (cl > 0 and grid[cl - 1][r].walls['E'])

    segs = []
    for rl in range(r0, r1 + 1):
        start = None
        for c in range(c0, c1 + 1):
            w = c < c1 and wall_h(c, rl)
            if w and start is None:
                start = c
            elif not w and start is not None:
                segs.append((start * cs, rl * cs, c * cs, rl * cs))
                start = None
    for cl in range(c0, c1 + 1):
        start = None
        for r in range(r0, r1 + 1):
            w = r < r1 and wall_v(cl, r)
            if w and start is None:
                start = r
            elif not w and start is not None:
                segs.append((cl * cs, start * cs, cl * cs, r * cs))
                start = None

    far = 3000
    for x1, y1, x2, y2 in segs:
        nx = min(max(light_wx, min(x1, x2)), max(x1, x2))
        ny = min(max(light_wy, min(y1, y2)), max(y1, y2))
        if sqrt((nx - light_wx) ** 2 + (ny - light_wy) ** 2) > radius_px:
            continue
        if y1 == y2:
            x1 -= 2; x2 += 2
        else:
            y1 -= 2; y2 += 2
        ax, ay = x1 - cam_x, y1 - cam_y
        bx, by = x2 - cam_x, y2 - cam_y
        da = sqrt((ax - light_sx) ** 2 + (ay - light_sy) ** 2)
        db = sqrt((bx - light_sx) ** 2 + (by - light_sy) ** 2)
        if da < 1 or db < 1:
            continue
        pa = (ax + (ax - light_sx) / da * far, ay + (ay - light_sy) / da * far)
        pb = (bx + (bx - light_sx) / db * far, by + (by - light_sy) / db * far)
        drawPoly((0, 0, 0), [(int(ax), int(ay)), (int(bx), int(by)),
                             (int(pb[0]), int(pb[1])), (int(pa[0]), int(pa[1]))])

# Fog gradient cache
fog_cache_key = None
fog_cache_surf = None

def get_fog_surface(radius_px):
    global fog_cache_key, fog_cache_surf
    if radius_px > 1500:
        return None
    if fog_cache_key == radius_px:
        return fog_cache_surf
    base_r = 128
    base = Surface((base_r * 2, base_r * 2), SRCALPHA)
    base.fill((0, 0, 0, 255))
    inner = 0.25
    for i in range(base_r, 0, -1):
        t = i / base_r
        s = max(0.0, min(1.0, (t - inner) / (1 - inner)))
        a = int(255 * s * s * (3 - 2 * s))
        draw.circle(base, (0, 0, 0, a), (base_r, base_r), i)
    fog_cache_surf = transform.smoothscale(base, (radius_px * 2, radius_px * 2))
    fog_cache_key = radius_px
    return fog_cache_surf

def get_tile_image(tile_name, target_size, theme=None):
    """Load tiles/<theme>/<tile_name>.png (falls back to tiles/<tile_name>.png)."""
    theme = theme if theme in THEMES else DEFAULT_THEME
    cache_key = (theme, tile_name, target_size)
    if cache_key in loaded_tiles:
        return loaded_tiles[cache_key]

    paths = [os.path.join("tiles", theme, f"{tile_name}.png"),
             os.path.join("tiles", f"{tile_name}.png")]
    img = None
    for path in paths:
        try:
            raw_img = image.load(path).convert_alpha()
            img = transform.smoothscale(raw_img, (int(target_size), int(target_size)))
            break
        except Exception:
            continue
    if img is None:
        fallback = Surface((int(target_size), int(target_size)), SRCALPHA)
        fallback.fill(THEME_COLORS.get(theme, THEME_COLORS[DEFAULT_THEME]))
        img = fallback

    loaded_tiles[cache_key] = img
    return img

