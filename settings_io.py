"""JSON persistence for user-configurable maze settings."""
import json
from pathlib import Path

SETTINGS_FILE = "settings.json"
THEMES = ("default", "spring", "summer", "autumn", "winter")   # tile folders: tiles/<theme>/
DEFAULT_THEME = "default"
DEFAULT_SETTINGS = {
    "grid_cols": 14, "grid_rows": 14, "cell_size": 160,
    "opt_limited_vis": True, "opt_vis_radius": 3, "opt_realistic_vis": False,
    "opt_enemy_enabled": False, "opt_enemy_delay": 3,
    "opt_keys_enabled": False, "opt_key_count": 3, "opt_player_speed": 10,
    "opt_survival_mode": False, "opt_survival_enemies": 12,
    "opt_eliminate_enemies": False,
    "opt_boss_mode": False,
    "opt_theme": DEFAULT_THEME,
    "opt_music_enabled": True,
    "user_master_volume": 1.0,
    "sfx_volume": 1.0,
    "music_volume": 1.0,
    "opt_import_on_start": False,
    "keybinds": {
        "move_up": "w",
        "move_down": "s",
        "move_left": "a",
        "move_right": "d",
        "attack_up": "up",
        "attack_down": "down",
        "attack_left": "left",
        "attack_right": "right",
        "heal": "space",
    },
}


def export_settings(settings, path=SETTINGS_FILE):
    """Write settings to JSON; return (success, message)."""
    try:
        with open(path, "w", encoding="utf-8") as file:
            json.dump({key: settings[key] for key in DEFAULT_SETTINGS}, file, indent=4)
        return True, "Settings Exported Successfully!"
    except Exception as exc:
        return False, f"Export Failed: {exc}"


def import_settings(path=SETTINGS_FILE):
    """Read settings from JSON; return (settings_or_none, message)."""
    if not Path(path).exists():
        return None, "Settings File Not Found!"
    try:
        with open(path, "r", encoding="utf-8") as file:
            data = json.load(file)
        settings = {key: data.get(key, default) for key, default in DEFAULT_SETTINGS.items()}
        if settings["opt_theme"] not in THEMES:
            settings["opt_theme"] = DEFAULT_THEME
        return settings, "Settings Imported Successfully!"
    except Exception as exc:
        return None, f"Import Failed: {exc}"
