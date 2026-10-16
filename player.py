"""Player movement, collision detection, and rendering."""

import random
from math import atan2, cos, sin
from mckPy import (Rect, upKey, downKey, leftKey, rightKey, drawCircle, keyPressed,
                   K_w, K_a, K_s, K_d, K_UP, K_DOWN, K_LEFT, K_RIGHT, K_SPACE)
from pygame import Surface, SRCALPHA, draw as pgdraw, display
from enemy import alpha_poly, sector_points
from audio import audio
from math import hypot

DT = 1.0 / 60
SWING_TIME = 0.18        # seconds the sword is out
SWING_COOLDOWN = 0.35    # seconds between swings
INVINCIBLE_TIME = 2.0    # seconds of invincibility after being hit
HEAL_MAX = 9             # sword hits needed to fill the heal meter
HEAL_COST = 3            # meter used per heal (1/3 of the meter = 1 HP)
HEAL_TIME = 1.0          # seconds of holding space to heal once
CIRCLE_SWING_RADIUS_MULT = 2.5
CIRCLE_COST = 2
PROJECTILE_COST = 2


DEFAULT_KEYBINDS = {
    "move_up": K_w,
    "move_down": K_s,
    "move_left": K_a,
    "move_right": K_d,
    "attack_up": K_UP,
    "attack_down": K_DOWN,
    "attack_left": K_LEFT,
    "attack_right": K_RIGHT,
    "heal": K_SPACE,
}


class Player:
    def __init__(self, x, y, size, speed=10, hp=3, keybinds=None):
        self.hp = hp
        self.max_hp = hp
        self.invincible = 0.0
        self.god_mode = False
        self.noclip = False
        self.heal_meter = 0
        self.heal_progress = 0.0
        self.inf_heal = False
        self.swing_t = 0.0
        self.swing_cd = 0.0
        self.swing_dir = (1.0, 0.0)
        self.swing_hits = set()
        self.parry_used_this_swing = False
        self.space_down = False
        self.space_hold_time = 0.0
        self.circle_timer = 0.0
        self.circle_radius = 0.0
        self.action_slow = 0.0
        self.projectile_queue = []
        self.kb_x = 0.0
        self.kb_y = 0.0
        self.x = x
        self.y = y
        self.size = size
        self.speed = speed
        self.off_x = 0.0
        self.off_y = 0.0
        self.step_acc = 0.0
        self.was_moving = False
        self.keybinds = dict(DEFAULT_KEYBINDS)
        self.dust_particles = []
        self.damage_particles = []
        self.low_hp_beat_timer = 0.0
        self.low_hp_waves = []
        if keybinds:
            self.keybinds.update(keybinds)

    def _key(self, binding_name):
        return keyPressed(self.keybinds.get(binding_name, DEFAULT_KEYBINDS[binding_name]))

    def _spawn_dust(self, x, y, amount=1, spread=18.0):
        for _ in range(amount):
            angle = random.uniform(0.0, 6.283185307179586)
            speed = random.uniform(8.0, 22.0)
            self.dust_particles.append({
                "x": x,
                "y": y,
                "vx": cos(angle) * speed,
                "vy": sin(angle) * speed * 0.6,
                "life": random.uniform(0.18, 0.38),
                "size": random.uniform(2.0, 4.5),
                "color": (110, 84, 62),
            })

    def _update_dust(self):
        keep = []
        for p in self.dust_particles:
            p["x"] += p["vx"] * DT
            p["y"] += p["vy"] * DT
            p["life"] -= DT
            p["vx"] *= 0.92
            p["vy"] += 0.22
            if p["life"] > 0:
                keep.append(p)
        self.dust_particles = keep

    def _spawn_damage_particles(self, x, y, amount=8, color=(0, 0, 0), from_x=None, from_y=None):
        for _ in range(amount):
            angle = random.uniform(0.0, 6.283185307179586)
            if from_x is not None and from_y is not None:
                dx = x - from_x
                dy = y - from_y
                angle = atan2(dy, dx) + random.uniform(-1.2, 1.2)
            speed = random.uniform(18.0, 64.0)
            self.damage_particles.append({
                "x": x,
                "y": y,
                "vx": cos(angle) * speed,
                "vy": sin(angle) * speed,
                "life": random.uniform(0.18, 0.42),
                "size": random.uniform(2.0, 5.0),
                "color": color,
            })

    def _update_damage_particles(self):
        keep = []
        for p in self.damage_particles:
            p["x"] += p["vx"] * DT
            p["y"] += p["vy"] * DT
            p["life"] -= DT
            p["vx"] *= 0.92
            p["vy"] *= 0.92
            if p["life"] > 0:
                keep.append(p)
        self.damage_particles = keep

    def _draw_alpha_circle(self, center, radius, color, alpha):
        if radius <= 0:
            return
        surface = display.get_surface()
        if surface is None:
            return
        size = int(radius * 2) + 4
        temp = Surface((size, size), SRCALPHA)
        pgdraw.circle(temp, (*color, alpha), (size // 2, size // 2), int(radius))
        surface.blit(temp, (int(center[0] - radius - 2), int(center[1] - radius - 2)))

    def _update_low_hp_effects(self):
        if self.hp > 1:
            self.low_hp_beat_timer = 0.0
            self.low_hp_waves = []
            return

        self.low_hp_beat_timer -= DT
        keep = []
        for wave in self.low_hp_waves:
            wave["radius"] += wave["speed"] * DT
            wave["life"] -= DT
            if wave["life"] > 0:
                keep.append(wave)
        self.low_hp_waves = keep

        if self.low_hp_beat_timer <= 0:
            self.low_hp_beat_timer = 0.65
            audio.play(random.choice(["heartbeat1", "heartbeat2", "heartbeat3"]), exempt=True)
            if len(self.low_hp_waves) < 4:
                self.low_hp_waves.append({"radius": 10, "speed": 140.0, "life": 0.55})

    def hurt(self, amount=1, from_x=None, from_y=None):
        """Take damage unless invincible. Returns True if the hit landed."""
        if self.god_mode or self.invincible > 0 or self.hp <= 0:
            return False
        self.hp -= amount
        self.invincible = INVINCIBLE_TIME
        self.heal_progress = 0.0          # being hit interrupts healing
        self._spawn_damage_particles(self.x, self.y, amount=10, color=(0, 0, 0), from_x=from_x, from_y=from_y)
        if from_x is not None and from_y is not None:
            dx = self.x - from_x
            dy = self.y - from_y
            d = hypot(dx, dy) or 1.0
            push = max(18.0, self.size * 1.2)
            self.kb_x = (dx / d) * push
            self.kb_y = (dy / d) * push
        audio.on_player_hurt(self.hp <= 0)
        return True

    def add_heal(self, amount=1):
        self.heal_meter = min(HEAL_MAX, self.heal_meter + amount)

    def _consume_heal(self, amount):
        if self.inf_heal:
            self.heal_meter = HEAL_MAX
            return
        self.heal_meter = max(0, self.heal_meter - amount)

    def _update_heal(self):
        """Hold SPACE to heal 1 HP using a third of the meter."""
        if self.inf_heal:
            self.heal_meter = HEAL_MAX
        if (self._key("heal") and self.heal_meter >= HEAL_COST
                and 0 < self.hp < self.max_hp):
            self.heal_progress += DT
            if self.heal_progress >= HEAL_TIME:
                self.hp += 1
                self._consume_heal(HEAL_COST)
                self.heal_progress = 0.0
                audio.play("heal")
        else:
            self.heal_progress = 0.0

    def move_speed_scale(self):
        scale = 1.0
        if self.heal_progress > 0:
            scale *= 0.2
        if self.circle_timer > 0:
            scale *= 0.2
        if self.invincible > 0:
            scale *= 0.6
        if self.action_slow > 0:
            scale *= 0.3
        return scale

    def sword_reach(self, tile_px):
        return tile_px * 0.6

    def _trigger_specials(self, tile_px):
        """Quick tap on SPACE triggers circle slash or directional projectile on release."""
        direction = None
        if self._key("attack_up"): direction = (0.0, -1.0)
        elif self._key("attack_down"): direction = (0.0, 1.0)
        elif self._key("attack_left"): direction = (-1.0, 0.0)
        elif self._key("attack_right"): direction = (1.0, 0.0)

        if direction is not None:
            cost = max(1, PROJECTILE_COST)
            if self.inf_heal:
                self.heal_meter = HEAL_MAX
            elif self.heal_meter < cost:
                return False
            else:
                self._consume_heal(cost)
            shot_speed = max(self.speed * 12.0, 800.0)
            self.action_slow = 0.18
            self.kb_x = -direction[0] * 12.0
            self.kb_y = -direction[1] * 12.0
            audio.play("projectile")
            proj_damage = 5 if self.hp == 1 else 3
            self.projectile_queue.append(dict(
                x=self.x, y=self.y,
                ux=direction[0], uy=direction[1],
                vx=direction[0] * shot_speed,
                vy=direction[1] * shot_speed,
                speed=shot_speed, life=1.0,
                width=tile_px * 2.0, radius=max(8.0, tile_px * 0.35), damage=proj_damage))
            return True

        if self.inf_heal:
            self.heal_meter = HEAL_MAX
        elif self.heal_meter < CIRCLE_COST:
            return False
        else:
            self._consume_heal(CIRCLE_COST)
        self.swing_t = 0.0
        self.swing_cd = 0.35
        self.swing_dir = (1.0, 0.0)
        self.swing_hits = set()
        self.parry_used_this_swing = False
        self.circle_timer = 0.18
        self.circle_radius = tile_px * CIRCLE_SWING_RADIUS_MULT * 0.6
        audio.play("circular_slash")
        return True

    def _try_swing(self):
        """Attack keys swing the sword in that direction."""
        if self.swing_cd > 0:
            return
        direction = None
        if self._key("attack_up"): direction = (0.0, -1.0)
        elif self._key("attack_down"): direction = (0.0, 1.0)
        elif self._key("attack_left"): direction = (-1.0, 0.0)
        elif self._key("attack_right"): direction = (1.0, 0.0)
        if direction:
            self.swing_dir = direction
            self.swing_t = SWING_TIME
            self.swing_cd = SWING_COOLDOWN
            self.swing_hits = set()
            self.parry_used_this_swing = False
            audio.play("slash")

    def trigger_parry(self):
        """Briefly slow the player and extend the active sword swing after a parry."""
        if self.swing_t <= 0 or self.parry_used_this_swing:
            return False
        self.parry_used_this_swing = True
        self.action_slow = max(self.action_slow, 0.35)
        self.swing_t = max(self.swing_t, 0.28)
        audio.play("parry")
        return True

    def update(self, maze, tile_px, keys_enabled=False, keys_collected=0, key_count=0, combat=False, eliminate_enemies=False, enemies_left=0):
        self.invincible = max(0.0, self.invincible - DT)
        self.swing_t = max(0.0, self.swing_t - DT)
        self.swing_cd = max(0.0, self.swing_cd - DT)
        self.circle_timer = max(0.0, self.circle_timer - DT)
        self.action_slow = max(0.0, self.action_slow - DT)
        self._update_damage_particles()
        self._update_low_hp_effects()
        self.kb_x *= 0.74
        self.kb_y *= 0.74
        if abs(self.kb_x) < 0.05:
            self.kb_x = 0.0
        if abs(self.kb_y) < 0.05:
            self.kb_y = 0.0

        space_down = self._key("heal")
        special_used = False
        if space_down and not self.space_down:
            self.space_hold_time = 0.0
        elif space_down:
            self.space_hold_time += DT
        elif self.space_down:
            if self.space_hold_time < 0.22:
                special_used = self._trigger_specials(tile_px)
            self.space_hold_time = 0.0
        self.space_down = space_down

        move_scale = self.move_speed_scale()
        dx, dy = 0, 0
        if combat:
            if self._key("move_up"): dy -= self.speed * move_scale
            if self._key("move_down"): dy += self.speed * move_scale
            if self._key("move_left"): dx -= self.speed * move_scale
            if self._key("move_right"): dx += self.speed * move_scale
            if not special_used:
                self._try_swing()
            self._update_heal()
        else:
            if self._key("move_up"): dy -= self.speed * move_scale
            if self._key("move_down"): dy += self.speed * move_scale
            if self._key("move_left"): dx -= self.speed * move_scale
            if self._key("move_right"): dx += self.speed * move_scale

        dx += self.kb_x
        dy += self.kb_y

        self._update_dust()
        grass_ratio = 78.0 / 512.0
        grass_margin = tile_px * grass_ratio

        old_x, old_y = self.x, self.y
        if dx != 0:
            new_x = self.x + dx
            if not self.check_collision(new_x, self.y, maze, tile_px, grass_margin, keys_enabled, keys_collected, key_count, eliminate_enemies, enemies_left):
                self.x = new_x

        if dy != 0:
            new_y = self.y + dy
            if not self.check_collision(self.x, new_y, maze, tile_px, grass_margin, keys_enabled, keys_collected, key_count, eliminate_enemies, enemies_left):
                self.y = new_y

        # footsteps: one step per stride walked
        moved = hypot(self.x - old_x, self.y - old_y)
        stride = tile_px * 0.8
        if moved > 0.1:
            if not self.was_moving:
                self.step_acc = stride * 0.6         # first step soon after starting to move
                self.was_moving = True
            self.step_acc += moved
            if self.step_acc >= stride:
                self.step_acc -= stride
                audio.play("footstep")
                self._spawn_dust(self.x, self.y, amount=2)
        else:
            self.was_moving = False

    def _get_tile_walls(self, c, r, maze):
        """Returns wall dictionary for standard cells or virtual boss arena/extension cells."""
        if 0 <= c < maze.cols and 0 <= r < maze.rows:
            return maze.grid[c][r].walls

        # Entrance extension (ns path)
        if c == 0 and r <= -1 and r > -5:
            return {'N': False, 'E': True, 'S': False, 'W': True}

        if c == 0 and r == -5:
            return {'N': True, 'E': True, 'S': False, 'W': True}
        
        if getattr(maze, "boss_mode_active", False):
            exit_col = maze.cols - 1
            exit_row = maze.rows + 2
            
            # Exit extension (ns path)
            if c == exit_col and r >= maze.rows and r < maze.rows + 2:
                return {'N': False, 'E': True, 'S': False, 'W': True}
            # Exit corner transition (nw)
            if c == exit_col and r == exit_row:
                return {'N': False, 'E': True, 'S': True, 'W': False}
            
            # Connecting WE path tile
            if (c == exit_col - 1 or c == exit_col - 2) and r == exit_row:
                return {'N': True, 'E': False, 'S': True, 'W': False}
            # Boss entrance open tile
            if c == exit_col - 3 and r == exit_row:
                return {'N': False, 'E': True, 'S': False, 'W': False} if getattr(maze, "boss_entrance_blocked", False) else {'N': False, 'E': False, 'S': False, 'W': False}
            
            # 5x5 Boss Arena bounds
            if exit_col - 7 <= c <= exit_col - 3 and exit_row - 2 <= r <= exit_row + 2:
                ac = c - (exit_col - 7)
                ar = r - (exit_row - 2)
                walls = {'N': False, 'E': False, 'S': False, 'W': False}
                if ar == 0: walls['N'] = True
                if ar == 4: walls['S'] = True
                if ac == 0: walls['W'] = True
                if ac == 4: walls['E'] = True
                return walls

        # Default fallback: solid boundary wall
        return {'N': False, 'E': True, 'S': False, 'W': True}

    def check_collision(self, px, py, maze, tile_px, margin, keys_enabled=False, keys_collected=0, key_count=0, eliminate_enemies=False, enemies_left=0):
        if self.noclip:
            return False
        player_rect = Rect(px - self.size // 2, py - self.size // 2, self.size, self.size)
        maze_w = maze.cols * tile_px
        maze_h = maze.rows * tile_px

        exit_min_x = (maze.cols - 1) * tile_px + margin
        exit_max_x = maze.cols * tile_px - margin

        keys_satisfied = (not keys_enabled) or (keys_collected >= key_count)
        enemies_satisfied = (not eliminate_enemies) or (enemies_left == 0)
        can_exit = keys_satisfied and enemies_satisfied
        half = self.size // 2
        is_exiting = (can_exit
                      and (py + half > maze_h - margin)
                      and (exit_min_x <= px - half)
                      and (px + half <= exit_max_x))

        extended_bounds_allowed = can_exit or getattr(maze, "boss_mode_active", False)

        if not is_exiting:
            if not extended_bounds_allowed:
                if px - self.size // 2 < margin or px + self.size // 2 > maze_w - margin:
                    return True
                if py - self.size // 2 < margin or py + self.size // 2 > maze_h - margin:
                    return True
            else:
                if px < -tile_px * 8 or px > maze_w + tile_px * 8:
                    return True
                if py < -tile_px * 6 or py > maze_h + tile_px * 6:
                    return True

        # Allow cell checks to scan outside standard grid bounds when boss mode is active
        min_c = int(px // tile_px) - 1
        max_c = int(px // tile_px) + 1
        min_r = int(py // tile_px) - 1
        max_r = int(py // tile_px) + 1
        if not extended_bounds_allowed:
            min_c = max(0, min_c)
            max_c = min(maze.cols - 1, max_c)
            min_r = max(0, min_r)
            max_r = min(maze.rows - 1, max_r)

        for c in range(min_c, max_c + 1):
            for r in range(min_r, max_r + 1):
                walls = self._get_tile_walls(c, r, maze)
                x_off = c * tile_px
                y_off = r * tile_px

                walls_to_check = []

                if walls['N']:
                    walls_to_check.append(Rect(x_off, y_off, tile_px, margin))
                if walls['S']:
                    if not (c == maze.cols - 1 and r == maze.rows - 1 and can_exit):
                        walls_to_check.append(Rect(x_off, y_off + tile_px - margin, tile_px, margin))
                if walls['W']:
                    walls_to_check.append(Rect(x_off, y_off, margin, tile_px))
                if walls['E']:
                    walls_to_check.append(Rect(x_off + tile_px - margin, y_off, margin, tile_px))

                for w_rect in walls_to_check:
                    if player_rect.colliderect(w_rect):
                        return True

        return False

    def draw(self, cam_x, cam_y, tile_px=160):
        screen_x = int(round(self.x - cam_x + self.off_x))
        screen_y = int(round(self.y - cam_y + self.off_y))
        blink = self.invincible > 0 and int(self.invincible * 16) % 2 == 0
        if not blink:
            drawCircle((64, 159, 255), screen_x, screen_y, self.size // 2)
        for p in self.dust_particles:
            pgdraw.circle(display.get_surface(), p["color"], (int(p["x"] - cam_x), int(p["y"] - cam_y)), max(1, int(p["size"])))
        for p in self.damage_particles:
            pgdraw.circle(display.get_surface(), p["color"], (int(p["x"] - cam_x), int(p["y"] - cam_y)), max(1, int(p["size"])))
        if self.hp <= 1:
            for wave in self.low_hp_waves:
                self._draw_alpha_circle((screen_x, screen_y), int(wave["radius"]), (255, 60, 60), 60)
        if self.heal_progress > 0:                # healing ring grows while holding space
            ring = self.size // 2 + 3 + int(10 * self.heal_progress / HEAL_TIME)
            pgdraw.circle(display.get_surface(), (80, 255, 120), (screen_x, screen_y), ring, 3)

        low_hp = self.hp <= 1
        if self.circle_timer > 0:
            circular_hold = 0.18
            p = 1.0 - (self.circle_timer / circular_hold)
            ang0 = -2.2
            sweep = 2.1
            arc_ang = ang0 + p * sweep
            arc_color = (255, 70, 70) if low_hp else (160, 220, 255)
            alpha_color = (255, 70, 70) if low_hp else (160, 220, 255)
            alpha_poly(sector_points(screen_x, screen_y, arc_ang, 1.2, self.circle_radius),
                       alpha_color, 70 if low_hp else 120)
            pgdraw.arc(display.get_surface(), arc_color,
                       (screen_x - self.circle_radius, screen_y - self.circle_radius,
                        self.circle_radius * 2, self.circle_radius * 2),
                       arc_ang, arc_ang + 1.2, 4)

        if self.swing_t > 0:                      # sword swing animation
            reach = self.sword_reach(tile_px)
            ang0 = atan2(self.swing_dir[1], self.swing_dir[0])
            p = 1 - self.swing_t / SWING_TIME
            sweep = 1.05
            ang = ang0 - sweep + 2 * sweep * p
            swing_fill = (255, 70, 70) if low_hp else (255, 255, 255)
            swing_line = (255, 110, 110) if low_hp else (240, 240, 255)
            swing_shadow = (150, 50, 50) if low_hp else (120, 120, 160)
            alpha_poly(sector_points(screen_x, screen_y, ang0 - sweep + sweep * p, sweep * p + 0.01, reach),
                       swing_fill, 90 if low_hp else 110)
            tip = (screen_x + cos(ang) * reach, screen_y + sin(ang) * reach)
            pgdraw.line(display.get_surface(), swing_line, (screen_x, screen_y), tip, 6)
            pgdraw.line(display.get_surface(), swing_shadow, (screen_x, screen_y), tip, 2)
