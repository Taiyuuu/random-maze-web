"""Console command processor and helper utilities."""
import time
from player import HEAL_MAX
from rendering import TILE_NAMES, get_tile_image
from settings_io import THEMES

def parse_bool(value):
    if isinstance(value, bool):
        return value
    if isinstance(value, (int, float)):
        return value != 0
    s = str(value).strip().lower()
    return s in ("1", "true", "yes", "on")

def process_console_command(cmd, context):
    parts = cmd.split()
    if not parts:
        return
    c = parts[0].lower()
    result = None
    ok = False

    player = context["player"]
    manager = context["manager"]
    maze = context["maze"]
    console = context["console"]
    console_available = context["console_available"]

    try:
        if c == "noclip" and len(parts) > 1 and player:
            player.noclip = parse_bool(parts[1])
            result = f"Noclip set to {player.noclip}"
            ok = True
        elif c == "load" and len(parts) > 1:
            val = int(parts[1])
            if val == 0:
                context["game_state"] = "MENU"
            elif val == 1:
                context["game_state"] = "OPTIONS"
            elif val == 2:
                context["init_game_func"]()
                context["game_state"] = "GAME"
            elif val == 3:
                context["game_over"] = True
                context["game_state"] = "GAME"
            elif val == 4:
                context["game_won"] = True
                context["game_state"] = "GAME"
            result = f"Loaded state {val}"
            ok = True
        elif c == "reload":
            if context["game_state"] == "GAME":
                context["init_game_func"]()
            result = "Reloaded successfully"
            ok = True
        elif c == "inv" and len(parts) > 1 and player:
            player.god_mode = parse_bool(parts[1])
            result = f"Invincibility (God mode) set to {player.god_mode}"
            ok = True
        elif c == "timer" and len(parts) > 1:
            arg = parts[1]
            if arg == "reset":
                context["start_time"] = time.time()
                context["elapsed_time"] = 0
                context["timer_paused_offset"] = 0
            elif arg == "pause":
                context["timer_paused"] = True
            elif arg == "resume":
                context["timer_paused"] = False
            else:
                val = float(arg)
                context["start_time"] -= val
            result = f"Timer command '{arg}' executed"
            ok = True
        elif c == "kill" and len(parts) > 1 and manager and player:
            target = parts[1]
            if target == "@s":
                player.hp = 0
                context["game_over"] = True
                result = "Killed self (@s)"
            elif target == "@n" and manager.enemies:
                nearest = min(manager.enemies, key=lambda e: (e.x - player.x)**2 + (e.y - player.y)**2)
                nearest.hp = 0
                result = "Killed nearest enemy (@n)"
            elif target == "@a" and manager.enemies:
                for e in manager.enemies:
                    e.hp = 0
                result = "Killed all enemies (@a)"
            else:
                result = "Unknown or invalid kill target"
        elif c == "hp" and len(parts) > 1 and player:
            val = int(parts[1])
            player.hp = max(0, min(player.max_hp, player.hp + val))
            if player.hp <= 0:
                context["game_over"] = True
            result = f"HP adjusted by {val}. Current HP: {player.hp}"
            ok = True
        elif c == "ai" and len(parts) > 1 and manager:
            target = parts[1]
            val = int(parts[2]) if len(parts) > 2 else 0
            if target == "@a":
                for e in manager.enemies:
                    e.ai_active = bool(val)
                result = f"All enemy AI set to {bool(val)}"
            elif target == "@n" and manager.enemies:
                nearest = min(manager.enemies, key=lambda e: (e.x - player.x)**2 + (e.y - player.y)**2)
                nearest.ai_active = bool(val)
                result = f"Nearest enemy AI set to {bool(val)}"
            else:
                result = "Unknown or invalid AI target"
            ok = True
        elif c == "inf_heal":
            if player:
                if len(parts) > 1:
                    player.inf_heal = parse_bool(parts[1])
                    result = f"Infinite heal set to {player.inf_heal}"
                else:
                    player.inf_heal = not player.inf_heal
                    result = f"Infinite heal toggled to {player.inf_heal}"
                if player.inf_heal:
                    player.heal_meter = HEAL_MAX
                ok = True
            else:
                result = "Player not initialized"
        elif c == "theme":
            if len(parts) == 1:
                result = "Theme usage: theme <0-4> or theme <name>"
            else:
                value = parts[1].lower()
                theme_name = None
                try:
                    idx = int(value)
                    if 0 <= idx < len(THEMES):
                        theme_name = THEMES[idx]
                    else:
                        raise ValueError
                except ValueError:
                    if value in THEMES:
                        theme_name = value
                    else:
                        result = f"Theme must be 0-{len(THEMES)-1} or one of: {', '.join(THEMES)}"
                        theme_name = None
                if theme_name is not None:
                    context["opt_theme"] = theme_name
                    for name in TILE_NAMES:
                        get_tile_image(name, context["cell_size"], theme_name)
                    result = f"Theme set to {theme_name}"
                    ok = True
        elif c == "setzoom":
            if len(parts) == 1:
                result = "Usage: setzoom <size> or setzoom <width> <height>"
            else:
                try:
                    if len(parts) == 2:
                        new_size = int(parts[1])
                        context["cell_size"] = max(20, min(500, new_size))
                    else:
                        width = int(parts[1])
                        height = int(parts[2])
                        context["cell_size"] = max(20, min(500, max(width, height)))
                    for name in TILE_NAMES:
                        get_tile_image(name, context["cell_size"], context["opt_theme"])
                    if player and maze:
                        player.x = min(player.x, maze.cols * context["cell_size"])
                        player.y = min(player.y, maze.rows * context["cell_size"])
                    result = f"Cell size set to {context['cell_size']}px"
                    ok = True
                except ValueError:
                    result = "Usage: setzoom <size> or setzoom <width> <height>"
        elif c in ("hud", "panel"):
            hp_before = player.hp if player else None
            heal_before = player.heal_meter if player else None
            if len(parts) > 1:
                context["show_hud"] = parse_bool(parts[1])
                result = f"HUD panel set to {context['show_hud']}"
            else:
                context["show_hud"] = not context["show_hud"]
                result = f"HUD panel toggled to {context['show_hud']}"
            if player:
                player.hp = hp_before if hp_before is not None else player.hp
                player.heal_meter = heal_before if heal_before is not None else player.heal_meter
            ok = True
        elif c in ("minimap", "map"):
            if len(parts) > 1:
                context["show_minimap"] = parse_bool(parts[1])
                result = f"Minimap set to {context['show_minimap']}"
            else:
                context["show_minimap"] = not context["show_minimap"]
                result = f"Minimap toggled to {context['show_minimap']}"
            ok = True
        elif c == "collisionbox":
            if len(parts) > 1:
                context["show_collisionbox"] = parse_bool(parts[1])
                result = f"Collision boxes set to {context['show_collisionbox']}"
            else:
                context["show_collisionbox"] = not context.get("show_collisionbox", False)
                result = f"Collision boxes toggled to {context['show_collisionbox']}"
            ok = True
        else:
            result = "Unknown or invalid command"
    except Exception as e:
        result = f"Error: {e}"

    if console_available and console:
        console.record_result(cmd, ok, result)