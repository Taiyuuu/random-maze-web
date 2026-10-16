import pygame
import mckPy
from mckPy import *
from maze import Maze
from player import Player
from enemy import EnemyManager
from rendering import (TILE_NAMES, draw_wall_shadows, get_fog_surface, get_tile_image)
from settings_io import THEMES, DEFAULT_THEME
from settings_io import export_settings as save_settings, import_settings as read_settings
from ui import (draw_button, draw_toggle_button, draw_main_menu_background,
                get_main_menu_text_color, draw_menu_overlay, draw_collisionbox_overlay,
                get_ui_image, draw_fleur_frame, set_mouse_offset)
from commands import process_console_command
from pygame import display
from audio import audio
import os
import random
import time
import json

try:
    from console import DeveloperConsole
    console = DeveloperConsole()
    console_available = True
except ImportError:
    print("Developer console not available in this session.")
    console_available = False
    console = None

try:
    from boss import run_boss_logic, draw_boss, draw_boss_hud, reset_boss
    boss_logic_available = True
except ImportError:
    print("Boss not available in this session.")
    boss_logic_available = False
    draw_boss = draw_boss_hud = reset_boss = None

# The game renders to a fixed 16:9 logical canvas. pygame's SCALED flag stretches
# that canvas to whatever size the (resizable) window has, adds black bars to keep
# the 16:9 ratio, and converts mouse positions back to canvas coordinates.
WINDOW_WIDTH = 1280
WINDOW_HEIGHT = 720
# Menus and dialogs were laid out for 800x600; they are drawn into a sub-area
# of the canvas that is centred on screen.
UI_WIDTH = 800
UI_HEIGHT = 600
UI_OX = (WINDOW_WIDTH - UI_WIDTH) // 2
UI_OY = (WINDOW_HEIGHT - UI_HEIGHT) // 2

try:
    canvas = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT), pygame.SCALED | pygame.RESIZABLE)
except pygame.error:
    canvas = pygame.display.set_mode((WINDOW_WIDTH, WINDOW_HEIGHT))
mckPy.screen = canvas
ui_area = canvas.subsurface(pygame.Rect(UI_OX, UI_OY, UI_WIDTH, UI_HEIGHT))
display.set_caption("Maze")


def refresh_canvas():
    """Re-fetch the display surface (call after anything that can recreate it)."""
    global canvas, ui_area
    canvas = pygame.display.get_surface()
    ui_area = canvas.subsurface(pygame.Rect(UI_OX, UI_OY, UI_WIDTH, UI_HEIGHT))
    mckPy.screen = canvas


def use_full():
    """Draw on the whole 16:9 canvas (game world, HUD, backgrounds, cursor)."""
    mckPy.screen = canvas
    set_mouse_offset(0, 0)


def use_ui_area():
    """Draw on the centred 800x600 area (menu / dialog layouts)."""
    mckPy.screen = ui_area
    set_mouse_offset(UI_OX, UI_OY)


def dim(alpha):
    """Darken the whole canvas, then switch to the centred UI area for dialog content."""
    use_full()
    drawRect((0, 0, 0), 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, alpha=alpha)
    use_ui_area()


def draw_status(duration):
    use_full()
    if status_msg and (time.time() - status_timer < duration):
        drawText("yellow", status_msg, 10, WINDOW_HEIGHT - 30, font=(TRAJAN_REGULAR, 18))

game_state = "MENU"
grid_cols = 14
grid_rows = 14
cell_size = 160

opt_limited_vis = True
opt_vis_radius = 3
opt_realistic_vis = False
opt_enemy_enabled = False
opt_enemy_delay = 3
opt_keys_enabled = False
opt_key_count = 3
opt_player_speed = 7
opt_survival_mode = False
opt_survival_enemies = 100
opt_eliminate_enemies = False
opt_boss_mode = False
opt_theme = DEFAULT_THEME
opt_music_enabled = True
user_master_volume = 1.0
sfx_volume = 1.0
music_volume = 1.0
keybinds = {
    "move_up": "w",
    "move_down": "s",
    "move_left": "a",
    "move_right": "d",
    "attack_up": "up",
    "attack_down": "down",
    "attack_left": "left",
    "attack_right": "right",
    "heal": "space",
}

KEY_NAME_TO_CODE = {
    "w": K_w, "a": K_a, "s": K_s, "d": K_d,
    "up": K_UP, "down": K_DOWN, "left": K_LEFT, "right": K_RIGHT,
    "space": K_SPACE,
}
KEY_CODE_TO_NAME = {code: name for name, code in KEY_NAME_TO_CODE.items()}
keybind_waiting = None

SETTINGS_FILE = "settings.json"
MAZE_SAVE_FILE = os.path.join(os.path.dirname(os.path.abspath(__file__)), "saved_maze.json")
status_msg = ""
status_timer = 0.0

opt_import_on_start = False
try:
    with open('settings.json', 'r') as file:
        data = json.load(file)
    if data["opt_import_on_start"] == True: opt_import_on_start = True
except Exception as err:
    print(err)

show_hud = True
show_minimap = True
show_collisionbox = False
timer_paused = False
timer_paused_offset = 0.0
menu_theme_scroll = 0.0

start_time = 0
elapsed_time = 0
game_won = False
game_over = False
keys_collected = 0
key_positions = []
maze = None
player = None
manager = None
combat_active = False
survival_active = False

fleur_anim_frames = 0.0
show_quit_confirm = False
game_pause = False
return_confirm = False
options_sub_menu = None

def update_cursor():
    """Hides system cursor and renders the custom cursor on menus and end screens."""
    mouse.set_visible(False)
    if game_state in ("MENU", "OPTIONS", "QUIT") or game_won or game_over or show_quit_confirm or game_pause:
        cursor_img = get_ui_image("cursor.png", 76, 76)
        mx, my = mouse.get_pos()
        canvas.blit(cursor_img, (mx - 8, my - 6))   # mouse.get_pos() is already in canvas coordinates

def apply_audio_settings():
    audio.set_user_master_volume(user_master_volume)
    audio.set_sfx_volume(sfx_volume)
    audio.set_music_volume(music_volume)
    audio.set_music_enabled(opt_music_enabled)


def apply_keybinds_to_player():
    if player is None:
        return
    mapped = {}
    for name, key_name in keybinds.items():
        code = KEY_NAME_TO_CODE.get(str(key_name).lower(), None)
        if code is not None:
            mapped[name] = code
    player.keybinds = mapped


def key_name_text(value):
    text = str(value).lower()
    if text in ("up", "down", "left", "right", "space"):
        return text.upper()
    return text.upper() if len(text) == 1 else text.upper()


def reset_game_defaults():
    global grid_cols, grid_rows, cell_size, opt_limited_vis, opt_vis_radius, opt_realistic_vis
    global opt_enemy_enabled, opt_enemy_delay, opt_keys_enabled, opt_key_count, opt_player_speed
    global opt_survival_mode, opt_survival_enemies, opt_eliminate_enemies, opt_boss_mode
    grid_cols, grid_rows, cell_size = 14, 14, 160
    opt_limited_vis, opt_vis_radius, opt_realistic_vis = True, 3, False
    opt_enemy_enabled, opt_enemy_delay = False, 3
    opt_keys_enabled, opt_key_count, opt_player_speed = False, 3, 7
    opt_survival_mode, opt_survival_enemies, opt_eliminate_enemies, opt_boss_mode = False, 100, False, False


def reset_audio_defaults():
    global user_master_volume, sfx_volume, music_volume, opt_music_enabled
    user_master_volume, sfx_volume, music_volume = 1.0, 1.0, 1.0
    opt_music_enabled = True
    apply_audio_settings()


def reset_keyboard_defaults():
    global keybinds
    keybinds = {
        "move_up": "w",
        "move_down": "s",
        "move_left": "a",
        "move_right": "d",
        "attack_up": "up",
        "attack_down": "down",
        "attack_left": "left",
        "attack_right": "right",
        "heal": "space",
    }
    apply_keybinds_to_player()


def export_settings():
    global status_msg, status_timer
    values = {name: globals()[name] for name in (
        "grid_cols", "grid_rows", "cell_size", "opt_limited_vis", "opt_vis_radius",
        "opt_realistic_vis", "opt_enemy_enabled", "opt_enemy_delay",
        "opt_keys_enabled", "opt_key_count", "opt_player_speed",
        "opt_survival_mode", "opt_survival_enemies", "opt_eliminate_enemies",
        "opt_boss_mode", "opt_theme", "opt_music_enabled", "user_master_volume", "sfx_volume",
        "opt_import_on_start", "music_volume", "keybinds")}
    _, status_msg = save_settings(values)
    status_timer = time.time()

def import_settings(msg=None):
    global status_msg, status_timer, keybinds
    data, status_msg = read_settings()
    if msg: status_msg = msg
    if data is not None:
        globals().update(data)
        if opt_survival_mode and opt_limited_vis and opt_realistic_vis:
            globals()["opt_realistic_vis"] = False
        if "keybinds" not in globals() or not isinstance(keybinds, dict):
            keybinds = {
                "move_up": "w",
                "move_down": "s",
                "move_left": "a",
                "move_right": "d",
                "attack_up": "up",
                "attack_down": "down",
                "attack_left": "left",
                "attack_right": "right",
                "heal": "space",
            }
        apply_audio_settings()
        apply_keybinds_to_player()
    status_timer = time.time()

def save_maze():
    global status_msg, status_timer
    if maze is None:
        status_msg = "No maze to save."
    else:
        try:
            with open(MAZE_SAVE_FILE, "w", encoding="utf-8") as file:
                json.dump(maze.to_dict(), file, indent=2)
            status_msg = f"Maze saved to {os.path.basename(MAZE_SAVE_FILE)}"
        except (OSError, TypeError, ValueError) as exc:
            status_msg = f"Could not save maze: {exc}"
    status_timer = time.time()

def load_saved_maze():
    global status_msg, status_timer, grid_cols, grid_rows, game_state
    try:
        with open(MAZE_SAVE_FILE, "r", encoding="utf-8") as file:
            data = json.load(file)
        loaded_maze = Maze.from_dict(data)
        grid_cols, grid_rows = loaded_maze.cols, loaded_maze.rows
        init_game(loaded_maze=loaded_maze)
        game_state = "GAME"
        status_msg = "Saved maze loaded."
    except FileNotFoundError:
        status_msg = "No saved maze found. Complete or lose a maze first, then save it."
    except (OSError, json.JSONDecodeError, TypeError, ValueError) as exc:
        status_msg = f"Could not load saved maze: {exc}"
    status_timer = time.time()

def cycle_theme():
    global opt_theme
    theme_index = THEMES.index(opt_theme)
    opt_theme = THEMES[(theme_index + 1) % len(THEMES)]

def init_game(loaded_maze=None):
    global maze, player, start_time, elapsed_time, game_won, game_over
    global keys_collected, key_positions, manager, combat_active, survival_active
    global show_hud, show_minimap
    
    audio.reset_round()
    if boss_logic_available:
        reset_boss()
    audio.play("ui_button_click")
    maze = loaded_maze if loaded_maze is not None else Maze(grid_cols, grid_rows)
    maze.boss_entrance_blocked = False
    for name in TILE_NAMES:
        get_tile_image(name, cell_size, opt_theme)
    start_x = cell_size / 2
    start_y = cell_size / 2
    player_size = int(cell_size * 0.2)
    realistic_on = opt_limited_vis and opt_realistic_vis
    survival_active = opt_survival_mode and not realistic_on
    combat_active = opt_enemy_enabled or survival_active
    player = Player(start_x, start_y, max(12, player_size), speed=opt_player_speed,
                    hp=5 if survival_active else 3)
    manager = EnemyManager(maze, cell_size, opt_player_speed,
                           chase_enabled=opt_enemy_enabled, chase_delay=opt_enemy_delay,
                           survival=survival_active, survival_count=opt_survival_enemies)
    
    start_time = time.time()
    elapsed_time = 0
    game_won = False
    game_over = False
    show_hud = True
    show_minimap = True
    keys_collected = 0
    key_positions = []
    if opt_keys_enabled:
        available_cells = []
        for c in range(maze.cols):
            for r in range(maze.rows):
                if (c, r) not in maze.shortest_path and (c, r) != (0, 0):
                    available_cells.append((c, r))
        num_keys = min(opt_key_count, len(available_cells))
        key_positions = random.sample(available_cells, num_keys)

def custom_running():
    global show_quit_confirm, fleur_anim_frames, game_state, keybind_waiting, status_msg
    display.flip()
    myClock.tick(60)
    clicked[:] = [False] * 5
    for evnt in event.get():
        if evnt.type == QUIT and not show_quit_confirm:
            audio.play("ui_button_click")
            show_quit_confirm = True
            fleur_anim_frames = 0
            if game_state == "GAME":
                audio.set_master_volume(0.2)
                console.active = False
            elif game_state == "OPTIONS":
                game_state = "MENU"
        if evnt.type == KEYDOWN and evnt.key == K_F11:
            display.toggle_fullscreen()
            refresh_canvas()
            continue
        if evnt.type == KEYDOWN:
            if keybind_waiting is not None:
                if evnt.key == K_ESCAPE:
                    keybind_waiting = None
                else:
                    key_name = KEY_CODE_TO_NAME.get(evnt.key)
                    if key_name is None:
                        key_name = evnt.unicode.lower() if evnt.unicode else ""
                    if key_name:
                        keybinds[keybind_waiting] = key_name
                        apply_keybinds_to_player()
                        status_msg = f"{keybind_waiting} bound to {key_name.upper()}"
                    keybind_waiting = None
                    continue
            if evnt.key == K_BACKQUOTE and console_available:
                console.toggle()
            elif console_available and console.active:
                res = console.handle_event(evnt)
                if res:
                    context = {
                        "game_state": game_state,
                        "player": player,
                        "manager": manager,
                        "maze": maze,
                        "console": console,
                        "console_available": console_available,
                        "init_game_func": init_game,
                        "game_over": game_over,
                        "game_won": game_won,
                        "start_time": start_time,
                        "elapsed_time": elapsed_time,
                        "timer_paused": timer_paused,
                        "timer_paused_offset": timer_paused_offset,
                        "opt_theme": opt_theme,
                        "cell_size": cell_size,
                        "show_hud": show_hud,
                        "show_minimap": show_minimap
                    }
                    process_console_command(res, context)
                    for key in ("game_state", "game_over", "game_won", "start_time", "elapsed_time",
                                "timer_paused", "timer_paused_offset", "opt_theme", "cell_size",
                                "show_hud", "show_minimap", "show_collisionbox"):
                        if key in context:
                            globals()[key] = context[key]
        if evnt.type == MOUSEBUTTONDOWN and evnt.button <= 5:
            clicked[evnt.button - 1] = True
    return True

esc_prev = True
_boss_last_frame = time.perf_counter()
if opt_import_on_start:
    import_settings("Applied Settings Successfully On Start-Up!")
    audio.play("save")
while custom_running():
    _boss_now = time.perf_counter()
    _frame_dt = min(0.05, max(0.0, _boss_now - _boss_last_frame))
    _boss_last_frame = _boss_now
    use_full()
    fill((30, 30, 40))
    audio.update(game_state, combat_active, game_over, game_won)
    esc_down = keyPressed(K_ESCAPE)
    esc_just = esc_down and not esc_prev
    esc_prev = esc_down

    if esc_just:
        audio.play("ui_button_click")

    if game_state == "MENU":
        menu_theme_scroll += 0.8
        draw_main_menu_background(opt_theme, menu_theme_scroll, WINDOW_WIDTH, WINDOW_HEIGHT)
        draw_menu_overlay(opt_theme, WINDOW_WIDTH, WINDOW_HEIGHT)
        use_ui_area()
        menu_text_color = get_main_menu_text_color(opt_theme)
        if not show_quit_confirm:
            fleur_anim_frames += 0.5 if fleur_anim_frames < 15 else 0
            draw_fleur_frame(min(5, fleur_anim_frames), 255, 75, num=5, w=300, h=45)
            drawText(menu_text_color, "RANDOM MAZE", 100, 120, font=(TRAJAN_BOLD, 70))
            draw_fleur_frame(fleur_anim_frames, 255, 190, num=4, w=300, h=75)

            if draw_button("START GAME", 280, 300, 200, 50, txt_color=menu_text_color):
                init_game()
                game_state = "GAME"
                game_pause, show_quit_confirm, console.active, return_confirm = False, False, False, False
            if draw_button("LOAD SAVED MAZE", 280, 350, 200, 50, txt_color=menu_text_color):
                audio.play("ui_button_click")
                load_saved_maze()
                game_pause, show_quit_confirm, console.active, return_confirm = False, False, False, False
            if draw_button("OPTIONS", 280, 400, 200, 50, txt_color=menu_text_color):
                game_state = "OPTIONS"
                fleur_anim_frames = 0
            if draw_button(f"THEME: {opt_theme.upper()}", 280, 450, 200, 40, txt_color=menu_text_color, sound="ui_option_click"):
                cycle_theme()
            if draw_button("QUIT", 280, 500, 200, 50, txt_color=menu_text_color) or esc_just:
                show_quit_confirm = True
                fleur_anim_frames = 0
        else:
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            draw_fleur_frame(fleur_anim_frames, 150, 200, w=480, h=40)
            drawText(menu_text_color, "Quit Game?", 300, 255, font=(TRAJAN_BOLD, 30))
            if draw_button("Yes", 280, 320, 200, 40, txt_color=menu_text_color, fontsize=25):
                audio.play("ui_button_click")
                break
            if draw_button("No", 280, 370, 200, 50, txt_color=menu_text_color, sound="ui_button_click", fontsize=25) or esc_just:
                show_quit_confirm = False
                fleur_anim_frames = 0

        draw_status(4.0)

    elif game_state == "OPTIONS":
        menu_theme_scroll += 0.8
        draw_main_menu_background(opt_theme, menu_theme_scroll, WINDOW_WIDTH, WINDOW_HEIGHT)
        draw_menu_overlay(opt_theme, WINDOW_WIDTH, WINDOW_HEIGHT)
        use_ui_area()
        menu_text_color = get_main_menu_text_color(opt_theme)

        if options_sub_menu == None:
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            drawText(menu_text_color, "OPTIONS", 315, 110, font=(TRAJAN_BOLD, 32))
            draw_fleur_frame(fleur_anim_frames, 150, 60, w=480, h=40)
            if draw_button("Game", 320, 170, 100, 40, txt_color=menu_text_color, sound="ui_button_click", fontsize=25):
                options_sub_menu = "game"
                fleur_anim_frames = 0
            if draw_button("Audio", 320, 220, 100, 40, txt_color=menu_text_color, sound="ui_button_click", fontsize=25):
                options_sub_menu = "audio"
                fleur_anim_frames = 0
            if draw_button("Keyboard", 290, 270, 150, 40, txt_color=menu_text_color, sound="ui_button_click", fontsize=25):
                options_sub_menu = "keyboard"
                fleur_anim_frames = 0

            if draw_button("EXPORT SETTINGS", 130, 460, 210, 45, bg_color="darkblue", txt_color="white", sound="ui_option_click"):
                export_settings()
                audio.play("save")
            if draw_button("IMPORT SETTINGS", 360, 460, 210, 45, bg_color="darkmagenta", txt_color="white", sound="ui_option_click"):
                import_settings()
                audio.play("save")

            if draw_toggle_button("Import On Start-up", opt_import_on_start, 460, 510, 250, 40, sound="ui_option_click"):
                opt_import_on_start = not opt_import_on_start
            
            if draw_button("BACK", 285, 510, 200, 45, txt_color=menu_text_color) or esc_just:
                game_state = "MENU"
                fleur_anim_frames = 0

        elif options_sub_menu == "game":
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            drawText(menu_text_color, "GAME", 335, 110, font=(TRAJAN_BOLD, 32))
            draw_fleur_frame(fleur_anim_frames, 150, 60, w=480, h=40)
            drawText(menu_text_color, f"Cols: {grid_cols}", 565, 180)
            if draw_button("-", 695, 170, 35, 35, txt_color=menu_text_color, sound="ui_option_click"): grid_cols = max(3, grid_cols - 1)
            if draw_button("+", 740, 170, 35, 35, txt_color=menu_text_color, sound="ui_option_click"): grid_cols = min(50, grid_cols + 1)

            drawText(menu_text_color, f"Rows: {grid_rows}", 565, 250)
            if draw_button("-", 695, 240, 35, 35, txt_color=menu_text_color, sound="ui_option_click"): grid_rows = max(3, grid_rows - 1)
            if draw_button("+", 740, 240, 35, 35, txt_color=menu_text_color, sound="ui_option_click"): grid_rows = min(50, grid_rows + 1)

            drawText(menu_text_color, f"Tile: {cell_size}px", 565, 320)
            if draw_button("-", 695, 310, 35, 35, txt_color=menu_text_color, sound="ui_option_click"): cell_size = max(20, cell_size - 10)
            if draw_button("+", 740, 310, 35, 35, txt_color=menu_text_color, sound="ui_option_click"): cell_size = min(500, cell_size + 10)

            if draw_toggle_button("Fog Vision", opt_limited_vis, 50, 165, 250, 40, sound="ui_option_click"):
                opt_limited_vis = not opt_limited_vis
            drawText("white", f"Radius: {opt_vis_radius}", 320, 175)
            if draw_button("-", 450, 165, 35, 35, sound="ui_option_click"): opt_vis_radius = max(1, opt_vis_radius - 1)
            if draw_button("+", 495, 165, 35, 35, sound="ui_option_click"): opt_vis_radius = min(15, opt_vis_radius + 1)

            realistic_eff = opt_limited_vis and opt_realistic_vis
            if opt_limited_vis and not opt_survival_mode:
                if draw_toggle_button("Realistic Vis", opt_realistic_vis, 50, 202, 250, 40, sound="ui_option_click"):
                    opt_realistic_vis = not opt_realistic_vis
            else:
                msg = "Realistic Vis: needs Fog" if not opt_limited_vis else "Realistic: off in Survival"
                drawText((150, 150, 150), msg, 65, 212, font=(TRAJAN_REGULAR, 20))

            if draw_toggle_button("Chasing Enemy", opt_enemy_enabled, 50, 244, 250, 40, sound="ui_option_click"):
                opt_enemy_enabled = not opt_enemy_enabled
            drawText("white", f"Delay: {opt_enemy_delay}s", 320, 254)
            if draw_button("-", 450, 244, 35, 35, sound="ui_option_click"): opt_enemy_delay = max(1, opt_enemy_delay - 1)
            if draw_button("+", 495, 244, 35, 35, sound="ui_option_click"): opt_enemy_delay = min(60, opt_enemy_delay + 1)

            if not realistic_eff:
                if draw_toggle_button("Survival Mode", opt_survival_mode, 50, 286, 250, 40, sound="ui_option_click"):
                    opt_survival_mode = not opt_survival_mode
                drawText("white", f"Enemies: {opt_survival_enemies}", 310, 296)
                if draw_button("-", 450, 286, 35, 35, sound="ui_option_click"): opt_survival_enemies = max(1, opt_survival_enemies - 1)
                if draw_button("+", 495, 286, 35, 35, sound="ui_option_click"): opt_survival_enemies = min(grid_cols * grid_rows, opt_survival_enemies + 1)

                if opt_survival_mode:
                    if draw_toggle_button("Eliminate All", opt_eliminate_enemies, 50, 328, 250, 40, sound="ui_option_click"):
                        opt_eliminate_enemies = not opt_eliminate_enemies
            else:
                drawText((150, 150, 150), "Survival: turn off Realistic", 65, 296, font=(TRAJAN_REGULAR, 18))

            if draw_toggle_button("Final Boss", opt_boss_mode, 50, 370, 250, 40, sound="ui_option_click"):
                opt_boss_mode = not opt_boss_mode
            if draw_toggle_button("Find Keys", opt_keys_enabled, 50, 412, 250, 40, sound="ui_option_click"):
                opt_keys_enabled = not opt_keys_enabled
            drawText("white", f"Keys: {opt_key_count}", 320, 422)
            if draw_button("-", 450, 412, 35, 35, sound="ui_option_click"): opt_key_count = max(1, opt_key_count - 1)
            if draw_button("+", 495, 412, 35, 35, sound="ui_option_click"): opt_key_count = min(15, opt_key_count + 1)

            drawText("white", f"Player Speed: {opt_player_speed}", 565, 395)
            if draw_button("-", 610, 415, 35, 35, sound="ui_option_click"): opt_player_speed = max(1, opt_player_speed - 1)
            if draw_button("+", 655, 415, 35, 35, sound="ui_option_click"): opt_player_speed = min(15, opt_player_speed + 1)

            if draw_button("Reset Default", 290, 465, 180, 35, txt_color=menu_text_color, sound="ui_option_click"):
                reset_game_defaults()

            if draw_button("BACK", 285, 510, 200, 45, txt_color=menu_text_color) or esc_just:
                options_sub_menu = None
                fleur_anim_frames = 0

        elif options_sub_menu == "audio":
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            drawText(menu_text_color, "AUDIO", 330, 110, font=(TRAJAN_BOLD, 32))
            draw_fleur_frame(fleur_anim_frames, 150, 60, w=480, h=40)

            drawText(menu_text_color, f"Master Volume: {round(user_master_volume * 100)}%", 150, 210)
            if draw_button("-", 450, 200, 35, 35, sound="ui_option_click"): user_master_volume = max(0.0, user_master_volume - 0.1)
            if draw_button("+", 495, 200, 35, 35, sound="ui_option_click"): user_master_volume = min(1.0, user_master_volume + 0.1)
            if draw_button("Reset", 565, 200, 100, 35, sound="ui_option_click"): user_master_volume = 1.0
            apply_audio_settings()

            drawText(menu_text_color, f"Sound Volume: {round(sfx_volume * 100)}%", 150, 270)
            if draw_button("-", 450, 260, 35, 35, sound="ui_option_click"): sfx_volume = max(0.0, sfx_volume - 0.1)
            if draw_button("+", 495, 260, 35, 35, sound="ui_option_click"): sfx_volume = min(1.0, sfx_volume + 0.1)
            if draw_button("Reset", 565, 260, 100, 35, sound="ui_option_click"): sfx_volume = 1.0
            apply_audio_settings()

            drawText(menu_text_color, f"Music Volume: {round(music_volume* 100)}%", 150, 330)
            if draw_button("-", 450, 320, 35, 35, sound="ui_option_click"): music_volume = max(0.0, music_volume - 0.1)
            if draw_button("+", 495, 320, 35, 35, sound="ui_option_click"): music_volume = min(1.0, music_volume + 0.1)
            if draw_button("Reset", 565, 320, 100, 35, sound="ui_option_click"): music_volume = 1.0
            apply_audio_settings()

            if draw_toggle_button("Music Enabled", opt_music_enabled, 290, 400, 250, 40, sound="ui_option_click"):
                opt_music_enabled = not opt_music_enabled
                audio.set_music_enabled(opt_music_enabled)

            if draw_button("Reset Default", 290, 465, 180, 35, txt_color=menu_text_color, sound="ui_option_click"):
                reset_audio_defaults()

            if draw_button("BACK", 285, 510, 200, 45, txt_color=menu_text_color) or esc_just:
                options_sub_menu = None
                fleur_anim_frames = 0

        elif options_sub_menu == "keyboard":
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            drawText(menu_text_color, "KEYBOARD", 300, 110, font=(TRAJAN_BOLD, 32))
            draw_fleur_frame(fleur_anim_frames, 150, 60, w=480, h=40)

            binding_rows = [
                ("Move Up", "move_up", 100, 200),
                ("Move Down", "move_down", 100, 240),
                ("Move Left", "move_left", 100, 280),
                ("Move Right", "move_right", 100, 320),
                ("Attack Up", "attack_up", 440, 200),
                ("Attack Down", "attack_down", 440, 240),
                ("Attack Left", "attack_left", 440, 280),
                ("Attack Right", "attack_right", 440, 320),
                ("Heal", "heal", 290, 370),
            ]
            for label, bind_name, x, y in binding_rows:
                drawText(menu_text_color, label, x, y)
                key_label = key_name_text(keybinds.get(bind_name, "w"))
                btn_w = 70 if bind_name == "heal" else 90
                if draw_button(key_label, x + 165, y, btn_w, 35, txt_color=menu_text_color, fontsize=16, sound="ui_option_click"):
                    keybind_waiting = bind_name
                    status_msg = f"Press a key for {label}"
                    status_timer = time.time()

            if draw_button("Reset Default", 290, 465, 180, 35, txt_color=menu_text_color, sound="ui_option_click"):
                reset_keyboard_defaults()

            if draw_button("BACK", 285, 510, 200, 45, txt_color=menu_text_color) or esc_just:
                options_sub_menu = None
                fleur_anim_frames = 0

        draw_status(3.0)


    elif game_state == "GAME":
        if not (console_available and console.active) and not show_quit_confirm and not game_won and not game_over and not game_pause:
            if not timer_paused:
                elapsed_time = time.time() - start_time
            
            player.update(maze, cell_size, keys_enabled=opt_keys_enabled,
                          keys_collected=keys_collected, key_count=opt_key_count,
                          combat=combat_active,
                          eliminate_enemies=opt_eliminate_enemies and survival_active,
                          enemies_left=len(manager.enemies) if manager else 0)

            if opt_keys_enabled:
                p_cell = (int(player.x // cell_size), int(player.y // cell_size))
                if p_cell in key_positions:
                    key_positions.remove(p_cell)
                    keys_collected += 1

            if combat_active:
                manager.update(player)
                if player.hp <= 0:
                    game_over = True

            if player.y > (maze.rows * cell_size + player.size) and not opt_boss_mode:
                game_won = True

        camera_shake_offset = (0, 0)
        boss_context = {"player": player, "maze": maze, "cell_size": cell_size}

        if opt_boss_mode and boss_logic_available and not game_over and not game_won and not game_pause and not show_quit_confirm:
            boss_context = {
                "player": player,
                "manager": manager,
                "maze": maze,
                "cell_size": cell_size,
                "combat_active": combat_active,
                "show_hud": show_hud,
                "show_minimap": show_minimap,
                "game_won_ref": lambda: globals().update({"game_won": True}),
                "dt": _frame_dt
            }
            # Pass dictionary container for camera shake and state overrides
            shake_container = {}
            boss_context["camera_shake"] = (0, 0)
            
            run_boss_logic(boss_context)
            
            # Apply modifications back to main scope
            combat_active = boss_context["combat_active"]
            show_hud = boss_context["show_hud"]
            show_minimap = boss_context["show_minimap"]
            camera_shake_offset = boss_context.get("camera_shake", (0, 0))

        cam_x = int(round(player.x - WINDOW_WIDTH / 2 + camera_shake_offset[0]))
        cam_y = int(round(player.y - WINDOW_HEIGHT / 2 + camera_shake_offset[1]))

        first_c = cam_x // cell_size
        last_c = (cam_x + WINDOW_WIDTH) // cell_size
        first_r = cam_y // cell_size
        last_r = (cam_y + WINDOW_HEIGHT) // cell_size
        
        # Enable flag on maze for collision check reference
        maze.boss_mode_active = opt_boss_mode

        for c in range(first_c, last_c + 1):
            for r in range(first_r, last_r + 1):
                tile_type = "grass"
                if 0 <= c < maze.cols and 0 <= r < maze.rows:
                    tile_type = maze.grid[c][r].get_tile_type()
                else:
                    # Entrance extension
                    if c == 0 and r <= -1 and r > -8:
                        tile_type = "ns"
                    # Exit extension leading to boss arena
                    elif c == maze.cols - 1 and r >= maze.rows and r < maze.rows + 2:
                        tile_type = "ns"
                    elif c == maze.cols - 1 and r == maze.rows + 2:
                        tile_type = "nw" if opt_boss_mode else "n"
                    
                    # Boss Arena (5x5 area extending left via 'we' tile from maze exit)
                    elif opt_boss_mode:
                        exit_col = maze.cols - 1
                        exit_row = maze.rows + 2
                        
                        # Connecting WE tile directly left of the exit corner
                        if (c == exit_col - 1 or c == exit_col - 2) and r == exit_row:
                            tile_type = "we"
                        # Boss entrance tile directly to the left of the WE tile
                        elif c == exit_col - 3 and r == exit_row:
                            tile_type = "wall_e" if getattr(maze, "boss_entrance_blocked", False) else "boss_entrance"
                        # 5x5 Arena bounds (extending further left and up/down)
                        elif exit_col - 7 <= c <= exit_col - 3 and exit_row - 2 <= r <= exit_row + 2:
                            arena_local_c = c - (exit_col - 7)
                            arena_local_r = r - (exit_row - 2)
                            
                            # Determine walls and corners for the 5x5 arena
                            if arena_local_r == 0 and arena_local_c == 0: tile_type = "se_"
                            elif arena_local_r == 0 and arena_local_c == 4: tile_type = "sw_"
                            elif arena_local_r == 4 and arena_local_c == 0: tile_type = "ne_"
                            elif arena_local_r == 4 and arena_local_c == 4: tile_type = "nw_"
                            elif arena_local_r == 0: tile_type = "wall_n"
                            elif arena_local_r == 4: tile_type = "wall_s"
                            elif arena_local_c == 0: tile_type = "wall_w"
                            elif arena_local_c == 4: tile_type = "wall_e"
                            else: tile_type = "dirt" # Open interior floor
                            
                drawImage(get_tile_image(tile_type, cell_size, opt_theme),
                          c * cell_size - cam_x, r * cell_size - cam_y)

        if opt_keys_enabled:
            for kc, kr in key_positions:
                kx = kc * cell_size + cell_size / 2 - cam_x
                ky = kr * cell_size + cell_size / 2 - cam_y
                drawCircle("yellow", int(kx), int(ky), int(cell_size * 0.15))

        if combat_active:
            manager.draw(cam_x, cam_y, WINDOW_WIDTH, WINDOW_HEIGHT, player)

        if opt_limited_vis and opt_realistic_vis and not survival_active:
            draw_wall_shadows(
                maze, player.x + player.off_x, player.y + player.off_y,
                int(round(player.x - cam_x + player.off_x)),
                int(round(player.y - cam_y + player.off_y)),
                cam_x, cam_y, min(opt_vis_radius * cell_size, 520),
                opt_vis_radius * cell_size, cell_size)

        if opt_boss_mode and boss_logic_available:
            draw_boss(boss_context, cam_x, cam_y)

        player.draw(cam_x, cam_y, cell_size)

        if opt_limited_vis:
            vis_px = int(opt_vis_radius * cell_size)
            lx = int(round(player.x - cam_x + player.off_x))
            ly = int(round(player.y - cam_y + player.off_y))
            fog = get_fog_surface(vis_px)
            if fog is not None:
                drawImage(fog, lx - vis_px, ly - vis_px)
                top, bottom = ly - vis_px, ly + vis_px
                left, right = lx - vis_px, lx + vis_px
                if top > 0:
                    drawRect((0, 0, 0), 0, 0, WINDOW_WIDTH, top)
                if bottom < WINDOW_HEIGHT:
                    drawRect((0, 0, 0), 0, bottom, WINDOW_WIDTH, WINDOW_HEIGHT - bottom)
                y0, y1 = max(0, top), min(WINDOW_HEIGHT, bottom)
                if left > 0 and y1 > y0:
                    drawRect((0, 0, 0), 0, y0, left, y1 - y0)
                if right < WINDOW_WIDTH and y1 > y0:
                    drawRect((0, 0, 0), right, y0, WINDOW_WIDTH - right, y1 - y0)

        if show_hud:
            if combat_active:
                drawRect((0, 0, 0), 10, 10, 220, 195, alpha=50)
            else:
                drawRect((0, 0, 0), 10, 10, 220, 125, alpha=50)
            drawText("white", f"TIME: {elapsed_time:.1f}s", 20, 20, font=(TRAJAN_REGULAR, 18))
            if combat_active:
                drawText("red", f"HP: {'❤' * max(0, player.hp)}", 20, 45, font=(TRAJAN_REGULAR, 18))
            if opt_keys_enabled:
                drawText("yellow", f"KEYS: {keys_collected}/{opt_key_count}", 20, 70, font=(TRAJAN_REGULAR, 18))
            if combat_active:
                drawText("white", f"KILLS: {manager.kills}", 20, 95, font=(TRAJAN_REGULAR, 18))
                drawRect((60, 0, 0), 20, 120, 180, 12)
                drawRect((80, 220, 120) if player.heal_meter >= 3 else (50, 130, 80),
                         20, 120, int(180 * player.heal_meter / 9), 12)
                for i in (1, 2):
                    drawRect("white", 20 + 60 * i - 1, 120, 2, 12)
                drawRect("white", 20, 120, 180, 12, t=1)
                drawText("lightgray", "WASD move, arrows attack", 20, 140, font=(TRAJAN_REGULAR, 11))
                drawText("lightgray", "Hold SPACE: heal (3 hits = 1 HP)", 20, 157, font=(TRAJAN_REGULAR, 11))
                drawText("lightgray", "ESC: back to menu", 20, 174, font=(TRAJAN_REGULAR, 19))
            else:
                drawText("lightgray", "ESC: back to menu", 20, 105, font=(TRAJAN_REGULAR, 19))
        else:
            if combat_active:
                drawText("red", f"HP: {'❤' * max(0, player.hp)}", 20, 20, font=(TRAJAN_REGULAR, 18))
                drawRect((60, 0, 0), 20, 45, 180, 12)
                drawRect((80, 220, 120) if player.heal_meter >= 3 else (50, 130, 80),
                            20, 45, int(180 * player.heal_meter / 9), 12)
                for i in (1, 2):
                    drawRect("white", 20 + 60 * i - 1, 45, 2, 12)
                drawRect("white", 20, 45, 180, 12, t=1)

        if player.hp <= 1:
            drawRect((255, 0, 0), 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, alpha=45)

        if opt_boss_mode and boss_logic_available:
            draw_boss_hud(WINDOW_WIDTH)

        if show_minimap:
            mm_scale = min(140 / maze.cols, 140 / maze.rows)
            mm_w, mm_h = int(maze.cols * mm_scale), int(maze.rows * mm_scale)
            mm_x, mm_y = WINDOW_WIDTH - 15 - mm_w, WINDOW_HEIGHT - 15 - mm_h
            drawRect("white", mm_x, mm_y, mm_w, mm_h, t=2)
            fx = min(max(player.x / (maze.cols * cell_size), 0), 1)
            fy = min(max(player.y / (maze.rows * cell_size), 0), 1)
            drawCircle((64, 159, 255), int(mm_x + fx * mm_w), int(mm_y + fy * mm_h), 4)

        if show_collisionbox:
            draw_collisionbox_overlay(cam_x, cam_y, maze, cell_size, manager, player)

        if show_quit_confirm:
            dim(180)
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            draw_fleur_frame(fleur_anim_frames, 150, 200, w=480, h=40)
            drawText("white", "Quit Game?", 300, 255, font=(TRAJAN_BOLD, 30))
            if draw_button("Yes", 280, 320, 200, 40, fontsize=25):
                audio.play("ui_button_click")
                break
            if draw_button("No", 280, 370, 200, 50, sound="ui_button_click", fontsize=25):
                show_quit_confirm = False
                if not game_pause: audio.set_master_volume(1.0)
            elif esc_just:
                show_quit_confirm = False
                esc_just = False
                if not game_pause: audio.set_master_volume(1.0)

        if return_confirm and not show_quit_confirm:
            dim(180)
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            draw_fleur_frame(fleur_anim_frames, 150, 200, w=480, h=40)
            drawText("white", "Return to Main Menu?", 210, 255, font=(TRAJAN_BOLD, 30))
            drawText("white", "(Progress will not be saved.)", 225, 295, font=(TRAJAN_BOLD, 20))
            if draw_button("Yes", 280, 320, 200, 40, fontsize=25):
                audio.play("ui_button_click")
                game_state = "MENU"
            if draw_button("No", 280, 370, 200, 50, sound="ui_button_click", fontsize=25):
                return_confirm = False
                if not game_pause: audio.set_master_volume(1.0)
            elif esc_just:
                return_confirm = False
                esc_just = False
                if not game_pause: audio.set_master_volume(1.0)

        if esc_just and not game_pause and not game_won and not game_over:
            game_pause, fleur_anim_frames, esc_just, console.active = True, 0, False, False
            audio.set_master_volume(0.2)
        if game_pause and not show_quit_confirm and not return_confirm:
            dim(180)
            fleur_anim_frames += 0.5 if fleur_anim_frames < 9 else 0
            draw_fleur_frame(fleur_anim_frames, 335, 400, num=2, w=152, h=33)
            draw_fleur_frame(fleur_anim_frames, 300, 180, num=3, w=213, h=62)
            if draw_button("Continue", 275, 250, 180, 40, fontsize=25) or esc_just:
                audio.play("ui_button_click")
                game_pause = False
                audio.set_master_volume(1.0)
            if draw_button("Main Menu", 265, 300, 200, 40, sound="ui_button_click", fontsize=25):
                return_confirm = True
                fleur_anim_frames = 0
                audio.set_master_volume(1.0)
            if draw_button("Quit", 360, 350, 70, 40, sound="ui_button_click", fontsize=25):
                show_quit_confirm, fleur_anim_frames = True, 0

        if game_won and not show_quit_confirm and not return_confirm:
            dim(180)
            win_txt = "CONGRATULATIONS" if opt_boss_mode else "MAZE COMPLETED"
            drawText("white", win_txt, 220, 180, font=(TRAJAN_BOLD, 36))
            drawText("white", f"Final Time: {elapsed_time:.2f}s", 270, 250, font=(TRAJAN_REGULAR, 24))

            if draw_button("SAVE MAZE", 315, 285, 170, 40, bg_color="darkblue", txt_color="white"):
                save_maze()
                audio.play("save")
            if draw_button("PLAY AGAIN", 130, 345, 170, 45): init_game()
            if draw_button("MAIN MENU", 315, 345, 170, 45): game_state, fleur_anim_frames = "MENU", 0
            if draw_button("QUIT", 500, 345, 170, 45): show_quit_confirm, fleur_anim_frames = True, 0

        elif game_over and not show_quit_confirm and not return_confirm:
            dim(255)
            drawText("red", "YOU DIED!", 280, 180, font=(TRAJAN_BOLD, 38))

            if draw_button("SAVE MAZE", 315, 285, 170, 40, bg_color="darkblue", txt_color="white"):
                save_maze()
                audio.play("save")
            if draw_button("RETRY", 130, 345, 170, 45): init_game()
            if draw_button("MAIN MENU", 315, 345, 170, 45): game_state, fleur_anim_frames = "MENU", 0
            if draw_button("QUIT", 500, 345, 170, 45): show_quit_confirm, fleur_anim_frames = True, 0

        draw_status(4.0)

        if console_available:
            console.draw(WINDOW_WIDTH, WINDOW_HEIGHT)

        if esc_just and not show_quit_confirm and not game_pause and not (console_available and console.active) and (game_won or game_over):
            game_state = "MENU"
            fleur_anim_frames = 0

    update_cursor()

time.sleep(0.2)
audio.stop_all()
quit()