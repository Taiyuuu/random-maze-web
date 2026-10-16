"""UI helpers and menu rendering components."""
from mckPy import *
from audio import audio
from rendering import get_tile_image
import math
import os


_ui_images = {}
_fleur_cache = {}

def get_ui_image(name, w=0, h=0):
    key = (name, w, h)
    if key in _ui_images:
        return _ui_images[key]
    paths = [os.path.join("ui", name), os.path.join("ui", f"{name}.png"), name]
    img = None
    for p in paths:
        try:
            raw = image.load(p).convert_alpha()
            if w > 0 and h > 0:
                img = transform.smoothscale(raw, (w, h))
            else:
                img = raw
            break
        except Exception:
            continue
    if img is None:
        img = Surface((24, 24), SRCALPHA)
    _ui_images[key] = img
    return img


def draw_fleur_frame(frame_num, x, y, type="fleur", num=1, w=None, h=None):
    frame_num = round(frame_num)
    if not w or not h:
        return
    key = (frame_num, type, num, w, h)
    if key not in _fleur_cache:
        _fleur_cache[key] = get_ui_image(f"{num}{type}{frame_num}.png", w, h)
    # drawImage follows mckPy.screen, so it respects the active draw target
    drawImage(_fleur_cache[key], x, y)


# Screen position of the origin of the current draw target. When menus are drawn
# into a centred sub-area of the canvas, mouse positions must be shifted by it.
_mouse_offset = (0, 0)


def set_mouse_offset(ox, oy):
    global _mouse_offset
    _mouse_offset = (ox, oy)


def _over(x, y, w, h):
    mx, my = mouse.get_pos()
    mx -= _mouse_offset[0]
    my -= _mouse_offset[1]
    return x <= mx <= x + w and y <= my <= y + h


def _click(x, y, w, h):
    return clicked[0] and _over(x, y, w, h)


def draw_button(text, x, y, w, h, bg_color="gray", txt_color="white", hover_color=[(220, 220, 220), (100, 100, 100)], sound="ui_button_click", fontsize=18):
    hover = _over(x, y, w, h)
    color = txt_color
    if hover and txt_color == "white":
        color = hover_color[0]
    elif hover and txt_color == "black":
        color = hover_color[1]
    drawText(color, text, x + w // 2 - len(text) * 4, y + h // 2 - 10, font=(TRAJAN_BOLD, fontsize))
    was_clicked = _click(x, y, w, h)
    if was_clicked:
        audio.play(sound)
    return was_clicked


def draw_toggle_button(text, state, x, y, w, h, sound="ui_option_click"):
    label = f"{text}: {'ON' if state else 'OFF'}"
    color = "lightgreen" if state else "lightcoral"
    drawText(color, label, x + 15, y + h // 2 - 10, font=(TRAJAN_REGULAR, 19))
    was_clicked = _click(x, y, w, h)
    if was_clicked:
        audio.play(sound)
    return was_clicked


def draw_main_menu_background(opt_theme, menu_theme_scroll, window_width, window_height):
    tile_size = 64
    scroll_x = menu_theme_scroll
    scroll_y = menu_theme_scroll * 0.75

    ax, bx, ay, by = tile_size, 18, 12, tile_size
    det = ax * by - bx * ay

    cols, rows = [], []
    for wx in (scroll_x - tile_size, scroll_x + window_width):
        for wy in (scroll_y - tile_size, scroll_y + window_height):
            cols.append((by * wx - bx * wy) / det)
            rows.append((ax * wy - ay * wx) / det)
    c_lo, c_hi = math.floor(min(cols)) - 1, math.ceil(max(cols)) + 1
    r_lo, r_hi = math.floor(min(rows)) - 1, math.ceil(max(rows)) + 1

    for row in range(r_lo, r_hi + 1):
        for col in range(c_lo, c_hi + 1):
            x = round(col * ax + row * bx - scroll_x)
            y = round(col * ay + row * by - scroll_y)
            if x > window_width or y > window_height or x < -tile_size or y < -tile_size:
                continue
            tile_name = "grass" if ((row + col) % 3 != 0) else "dirt"
            drawImage(get_tile_image(tile_name, tile_size, opt_theme), x, y)


def get_main_menu_text_color(opt_theme):
    return "black" if opt_theme == "winter" else "white"


def draw_menu_overlay(opt_theme, window_width=800, window_height=600):
    overlay_color = (20, 20, 25) if opt_theme != "winter" else (215, 230, 245)
    drawRect(overlay_color, 0, 0, window_width, window_height, alpha=60)


def draw_collisionbox_overlay(cam_x, cam_y, maze, cell_size, manager, player):
    if maze is None:
        return

    cell = cell_size
    margin = cell * (78.0 / 512.0)

    for c in range(maze.cols):
        for r in range(maze.rows):
            x = c * cell
            y = r * cell
            cell_data = maze.grid[c][r]
            if cell_data.walls['N']:
                drawRect("lime", int(x - cam_x), int(y - cam_y), int(cell), int(margin), t=1)
            if cell_data.walls['S']:
                drawRect("lime", int(x - cam_x), int((y + cell - margin) - cam_y), int(cell), int(margin), t=1)
            if cell_data.walls['W']:
                drawRect("lime", int(x - cam_x), int(y - cam_y), int(margin), int(cell), t=1)
            if cell_data.walls['E']:
                drawRect("lime", int((x + cell - margin) - cam_x), int(y - cam_y), int(margin), int(cell), t=1)

    if manager:
        for e in manager.enemies:
            drawCircle("red", int(e.x - cam_x), int(e.y - cam_y), int(e.radius), t=1, outline=0)
        for p in manager.projectiles:
            drawCircle("red", int(p['x'] - cam_x), int(p['y'] - cam_y), max(4, int(p['r'])), t=1, outline=0)
        for p in manager.player_projectiles:
            drawCircle("cyan", int(p['x'] - cam_x), int(p['y'] - cam_y), max(4, int(p['width'] * 0.18)), t=1, outline=0)
        for hz in manager.hazards:
            if hz['kind'] == 'aoe':
                drawCircle("red", int(hz['x'] - cam_x), int(hz['y'] - cam_y), int((maze.cols / 2) * cell_size * 0.22), t=1, outline=0)
            else:
                drawRect("red", int(hz['col'] * cell - cam_x), int(-cam_y), int(cell), int(maze.rows * cell), t=1)
                drawRect("red", int(-cam_x), int(hz['row'] * cell - cam_y), int(maze.cols * cell), int(cell), t=1)

    if player:
        drawCircle("yellow", int(player.x - cam_x), int(player.y - cam_y), int(player.size * 0.5), t=1, outline=0)
        if player.swing_t > 0:
            reach = player.sword_reach(cell_size)
            ux, uy = player.swing_dir
            ang0 = atan2(uy, ux)
            sweep = 1.05
            points = [(player.x - cam_x, player.y - cam_y)]
            for i in range(13):
                t = i / 12.0
                ang = ang0 - sweep + 2 * sweep * t
                points.append((int(player.x - cam_x + cos(ang) * reach), int(player.y - cam_y + sin(ang) * reach)))
            drawPoly("cyan", points, t=1, outline=0)
        if player.circle_timer > 0:
            drawCircle("cyan", int(player.x - cam_x), int(player.y - cam_y), int(player.circle_radius), t=1, outline=0)

    exit_rect_x = int((maze.cols - 1) * cell + margin - cam_x)
    exit_rect_y = int((maze.rows * cell) - margin - cam_y)
    exit_rect_w = int(cell - (2 * margin))
    drawRect("orange", exit_rect_x, exit_rect_y + 80, exit_rect_w, int(margin), t=1)