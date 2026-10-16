"""Audio manager for the maze game.

    music : home.mp3 (menus), reg_game.mp3 (normal game), enemy_game.mp3 (game with enemies)
    sfx   : circular_slash, enemy_hazard, lunge, enemy_damage, footstep,
            heal, player_damage, slash, projectile, spit, player_death   (.mp3; .ogg/.wav also work)

Behaviour
* Music fades out/in when switching between home and in-game music, and fades out
  as soon as the game-over / maze-completed screen is shown.
* When the player is hurt: player_damage plays for a short moment, then ALL audio is
  muted and fades back to normal volume. On the last HP the damage sound is followed
  immediately by player_death with no muting.

If the mixer or a file is unavailable everything silently becomes a no-op.
"""
import os
import random
import time

import pygame

AUDIO_EXTS = (".mp3", ".ogg", ".wav")

# per-effect settings: vol = base volume, gap = min seconds between plays
SFX = {
    "circular_slash":     dict(vol=0.9),
    "enemy_hazard":       dict(vol=1.6),
    "lunge":              dict(vol=1.0),
    "enemy_damage":       dict(vol=0.9, gap=0.05),
    "footstep":           dict(vol=0.6),
    "heal":               dict(vol=0.9),
    "player_damage":      dict(vol=1.0),
    "slash":              dict(vol=0.8, gap=0.04),
    "projectile":         dict(vol=0.9),
    "spit":               dict(vol=1.8),
    "heartbeat1":         dict(vol=0.9),
    "heartbeat2":         dict(vol=0.9),
    "heartbeat3":         dict(vol=0.9),
    "player_death":       dict(vol=1.0),
    "ui_button_click":    dict(vol=0.8),
    "ui_option_click":    dict(vol=0.8),
    "ui_change_selection":dict(vol=0.7, gap=0.03),
    "save":               dict(vol=0.9),
    "boss_land":          dict(vol=1.0),
    "boss1_flame_outburst": dict(vol=1.0),
    "boss1_flame_loop":   dict(vol=0.9),
    "boss1_smash1":       dict(vol=1.0),
    "boss1_smash2":       dict(vol=1.0),
    "parry":              dict(vol=1.0),
    "boss_final_hit":     dict(vol=1.0),
    "boss_dying":         dict(vol=1.0),
    "boss_explode_clean": dict(vol=1.0),
}
GROUP_LIMITS = {"enemy_step": 3}      # max simultaneous sounds of a group

MUSIC = {"home": "home", "reg_game": "reg_game", "enemy_game": "enemy_game"}

MUSIC_VOLUME = 0.55
SWITCH_FADE_OUT = 0.7     # home <-> in-game music
SWITCH_FADE_IN = 0.9
END_FADE_OUT = 1.6        # game over / maze completed screen
DAMAGE_PLAY_TIME = 0.1    # seconds of player_damage before everything is muted
MUTE_HOLD = 0.25          # seconds of full silence after the damage sound
DUCK_FADE_IN = 2.5        # seconds to fade back to normal volume


class AudioManager:
    def __init__(self):
        self.enabled = False
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init()
            pygame.mixer.set_num_channels(32)
            self.enabled = True
        except Exception:
            self.enabled = False

        self._dirs = [os.path.join(os.path.dirname(os.path.abspath(__file__)), "audio"),
                      os.path.join(os.getcwd(), "audio"), "audio"]
        self._sounds = {}
        self._last_play = {}
        self._active = []            # dicts: ch, snd, base, exempt, group
        self.duck = 1.0              # master multiplier used by the hurt mute/fade
        self._mute_hold = 0.0
        self._hurt = None
        self._death_started = False
        self.music_track = None
        self.music_gain = 0.0
        self.music_enabled = True
        self._last_time = None
        self.master_volume = 1.0
        self.user_master_volume = 1.0
        self.sfx_volume = 1.0
        self.music_volume = 1.0
        self.boss_music_suppressed = False
        self.boss_music_override = False
        self.boss_fade_remaining = 0.0
        self.boss_fade_duration = 0.0
        self.boss_track_loop = False
        self._boss_loop_channels = {}

    def set_master_volume(self, vol):
        self.master_volume = max(0.0, min(1.0, float(vol)))
        try:
            pygame.mixer.music.set_volume(MUSIC_VOLUME * self.music_volume * self.user_master_volume * self.music_gain * self.duck * self.master_volume)
        except Exception:
            pass

    def set_user_master_volume(self, vol):
        self.user_master_volume = max(0.0, min(1.0, float(vol)))
        try:
            pygame.mixer.music.set_volume(MUSIC_VOLUME * self.music_volume * self.user_master_volume * self.music_gain * self.duck * self.master_volume)
        except Exception:
            pass

    def set_sfx_volume(self, vol):
        self.sfx_volume = max(0.0, min(1.0, float(vol)))

    def set_music_volume(self, vol):
        self.music_volume = max(0.0, min(1.0, float(vol)))
        try:
            pygame.mixer.music.set_volume(MUSIC_VOLUME * self.music_volume * self.user_master_volume * self.music_gain * self.duck * self.master_volume)
        except Exception:
            pass

    def set_music_enabled(self, enabled):
        self.music_enabled = bool(enabled)
        if not self.music_enabled:
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            self.music_track = None
            self.music_gain = 0.0

    # ---------------------------------------------------------------- files
    def _find(self, stem):
        for d in self._dirs:
            for ext in AUDIO_EXTS:
                path = os.path.join(d, stem + ext)
                if os.path.isfile(path):
                    return path
        return None

    def _get_sound_name(self, name):
        if name != "slash":
            return name
        candidates = [f"slash{i}" for i in range(1, 4)]
        available = [item for item in candidates if self._find(item) is not None]
        if available:
            return random.choice(available)
        return name

    def _get_sound(self, name):
        sound_name = self._get_sound_name(name)
        if sound_name not in self._sounds:
            snd = None
            path = self._find(sound_name)
            if path:
                try:
                    snd = pygame.mixer.Sound(path)
                except Exception:
                    snd = None
            self._sounds[sound_name] = snd
        return self._sounds[sound_name]

    # ---------------------------------------------------------------- sfx
    @staticmethod
    def falloff(dist, max_dist):
        """1.0 at the player, 0.0 at max_dist (quadratic)."""
        if max_dist <= 0 or dist >= max_dist:
            return 0.0
        return (1.0 - dist / max_dist) ** 2

    def _prune(self):
        self._active = [a for a in self._active
                        if a["ch"].get_busy() and a["ch"].get_sound() is a["snd"]]

    def play(self, name, volume=1.0, exempt=False, group=None):
        """Play a sound effect. `exempt` sounds ignore the hurt mute. Returns the channel."""
        if not self.enabled:
            return None
        snd = self._get_sound(name)
        if snd is None:
            return None
        group = group or name
        cfg = SFX.get(name, {})
        now = time.perf_counter()
        gap = cfg.get("gap", 0.0)
        if gap and now - self._last_play.get(group, -9.0) < gap:
            return None
        limit = GROUP_LIMITS.get(group)
        if limit:
            self._prune()
            if sum(1 for a in self._active if a["group"] == group) >= limit:
                return None
        base = max(0.0, min(1.0, volume * cfg.get("vol", 1.0)))
        if base <= 0.01:
            return None
        ch = snd.play()
        if ch is None:
            return None
        effective = base * self.user_master_volume * self.sfx_volume * (1.0 if exempt else self.duck) * self.master_volume
        ch.set_volume(effective)
        self._last_play[group] = now
        self._active.append(dict(ch=ch, snd=snd, base=base, exempt=exempt, group=group))
        return ch

    # ---------------------------------------------------------------- player hurt / death
    def on_player_hurt(self, lethal):
        """Call when the player actually loses HP."""
        if not self.enabled:
            return
        snd = self._get_sound("player_damage")
        window = min(snd.get_length(), DAMAGE_PLAY_TIME) if snd else 0.0
        ch = self.play("player_damage", exempt=True)
        self._hurt = dict(t=window, ch=ch, lethal=lethal)
        if lethal:
            self._death_started = True

    def reset_round(self):
        """Call when a new round starts."""
        self.boss_music_suppressed = False
        self.boss_music_override = False
        self.boss_fade_remaining = 0.0
        self.boss_fade_duration = 0.0
        self._boss_loop_channels = {}
        self._hurt = None
        self._death_started = False
        self._mute_hold = 0.0
        self.duck = 1.0
        if self.enabled:
            pygame.mixer.stop()
        self._active = []

    def stop_all(self):
        if self.enabled:
            try:
                pygame.mixer.stop()
                pygame.mixer.music.stop()
            except Exception:
                pass

    # ------------------------------------------------------------ boss audio
    def suppress_maze_music(self):
        """Fade out normal maze music and prevent it restarting for this round."""
        self.boss_music_suppressed = True

    def stop_boss_music(self):
        """Stop any boss-specific music and clear the override so menu/game music can resume."""
        self.boss_music_override = False
        self.boss_fade_remaining = 0.0
        self.boss_fade_duration = 0.0
        self.music_gain = 0.0
        self.music_track = None
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass

    def play_boss_music(self, stem="boss1_music", loop=True):
        """Take exclusive ownership of the music channel for boss tracks."""
        if not self.enabled or not self.music_enabled:
            self.boss_music_override = True
            self.music_track = stem
            return
        path = self._find(stem)
        self.boss_music_override = True
        self.boss_fade_remaining = 0.0
        self.boss_fade_duration = 0.0
        self.music_track = stem
        self.music_gain = 1.0
        self.boss_track_loop = bool(loop)
        if not path:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.play(loops=-1 if loop else 0)
        except Exception:
            pass

    def fade_boss_music(self, duration=0.5):
        """Fade the current boss track to silence; returns whether fade is complete."""
        if not self.enabled or not self.music_enabled:
            self.boss_fade_duration = 0.0
            self.boss_fade_remaining = 0.0
            self.music_gain = 0.0
            try:
                pygame.mixer.music.stop()
            except Exception:
                pass
            return
        self.boss_fade_duration = max(0.01, float(duration))
        self.boss_fade_remaining = self.boss_fade_duration

    def play_looping_sfx(self, name, volume=1.0):
        """Start a named SFX on loop, returning its channel; repeated calls are ignored."""
        if not self.enabled:
            return None
        current = self._boss_loop_channels.get(name)
        if current is not None and current.get_busy():
            return current
        snd = self._get_sound(name)
        if snd is None:
            return None
        try:
            ch = snd.play(loops=-1)
            if ch is not None:
                cfg = SFX.get(name, {})
                ch.set_volume(max(0.0, min(1.0, volume * cfg.get("vol", 1.0) * self.user_master_volume * self.sfx_volume * self.master_volume)))
                self._boss_loop_channels[name] = ch
            return ch
        except Exception:
            return None

    def stop_looping_sfx(self, name, fade_ms=120):
        ch = self._boss_loop_channels.pop(name, None)
        if ch is not None:
            try:
                ch.fadeout(fade_ms)
            except Exception:
                pass

    def update_boss_music(self, dt):
        if self.boss_fade_remaining > 0:
            self.boss_fade_remaining = max(0.0, self.boss_fade_remaining - dt)
            self.music_gain = self.boss_fade_remaining / max(0.01, self.boss_fade_duration)
            if self.boss_fade_remaining <= 0:
                try:
                    pygame.mixer.music.stop()
                except Exception:
                    pass
                self.music_gain = 0.0
        try:
            pygame.mixer.music.set_volume(MUSIC_VOLUME * self.music_volume * self.user_master_volume * self.music_gain * self.duck * self.master_volume)
        except Exception:
            pass

    # ---------------------------------------------------------------- music
    @staticmethod
    def _desired_track(state, combat, game_over, game_won):
        if state in ("MENU", "OPTIONS"):
            return "home"
        if state == "GAME":
            if game_over or game_won:
                return None                       # fade out on the end screen
            return "enemy_game" if combat else "reg_game"
        return None

    def _start_music(self, track):
        self.music_track = track                  # even if loading fails (avoid retrying every frame)
        self.music_gain = 0.0
        path = self._find(MUSIC[track])
        if not path:
            return
        try:
            pygame.mixer.music.load(path)
            pygame.mixer.music.set_volume(0.0)
            pygame.mixer.music.play(loops=-1)
        except Exception:
            pass

    def _stop_music(self):
        try:
            pygame.mixer.music.stop()
        except Exception:
            pass
        self.music_track = None
        self.music_gain = 0.0

    # ---------------------------------------------------------------- per-frame update
    def update(self, state, combat=False, game_over=False, game_won=False, dt=None):
        if not self.enabled:
            return
        now = time.perf_counter()
        if dt is None:
            dt = 0.0 if self._last_time is None else min(0.1, now - self._last_time)
        self._last_time = now

        if state in ("MENU", "OPTIONS"):
            self.boss_music_suppressed = False  # <--- Fixes main menu music resume
            if self.boss_music_override:
                self.stop_boss_music()

        # death without a hurt (e.g. console commands)
        if game_over and not self._death_started:
            self._death_started = True
            self.play("player_death", exempt=True)
            self.stop_boss_music()

        # hurt: damage sound for a moment, then mute everything and fade back in
        if self._hurt:
            self._hurt["t"] -= dt
            if self._hurt["t"] <= 0:
                ch = self._hurt["ch"]
                if ch is not None:
                    ch.fadeout(80)
                if self._hurt["lethal"]:
                    self.play("player_death", exempt=True)     # no volume change
                else:
                    self.duck = 0.0
                    self._mute_hold = MUTE_HOLD
                self._hurt = None

        if self._mute_hold > 0:
            self._mute_hold -= dt
            self.duck = 0.0
        elif self.duck < 1.0:
            self.duck = min(1.0, self.duck + dt / DUCK_FADE_IN)

        if not self.music_enabled:
            if self.music_track is not None:
                self._stop_music()
        elif self.boss_music_override:
            self.update_boss_music(dt)
        else:
            # background music with fades; once the boss corridor is reached,
            # normal tracks stay disabled until the next round starts.
            target = None if self.boss_music_suppressed else self._desired_track(state, combat, game_over, game_won)
            if self.music_track != target:
                if self.music_track is not None and self.music_gain > 0:
                    out_time = END_FADE_OUT if target is None else SWITCH_FADE_OUT
                    self.music_gain = max(0.0, self.music_gain - dt / out_time)
                if self.music_track is None or self.music_gain <= 0:
                    self._stop_music()
                    if target is not None:
                        self._start_music(target)
            elif self.music_track is not None:
                self.music_gain = min(1.0, self.music_gain + dt / SWITCH_FADE_IN)
            try:
                pygame.mixer.music.set_volume(MUSIC_VOLUME * self.music_volume * self.user_master_volume * self.music_volume * self.user_master_volume * self.music_gain * self.duck * self.master_volume)
            except Exception:
                pass

        # apply the master duck to the sounds that are playing
        self._prune()
        for a in self._active:
            a["ch"].set_volume(a["base"] * (1.0 if a["exempt"] else self.duck))


audio = AudioManager()
