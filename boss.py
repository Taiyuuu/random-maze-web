"""Boss arena controller: intro cinematic, combat patterns, parries, and death sequence."""
import math
import random
import pygame
from audio import audio
from player import HEAL_MAX
from mckPy import drawText

INTRO_DURATION = 5.0
SHAKE_INTENSITY = 8.0


def _clamp(value, low, high):
    return max(low, min(high, value))


def _distance(x1, y1, x2, y2):
    return math.hypot(x2 - x1, y2 - y1)


class BossManager:
    """State machine for boss one. Damage is counted in individual hit points (100 total)."""
    def __init__(self):
        self.reset()

    def reset(self):
        self.state = "WAITING"  # WAITING, INTRO, ACTIVE, DYING, DEAD
        self.timer = 0.0
        self.hp = 100
        self.max_hp = 100
        self.x = self.y = 0.0
        self.radius = 0.0
        self.dust_particles = []
        self.intro_player_pos = None
        self.attack = None
        self.attack_timer = 0.0
        self.attack_data = {}
        self.projectiles = []
        self.hazards = []
        self.clones = []
        self.hurt_flash = 0.0
        self.death_stage = 0
        self.death_timer = 0.0
        self.parry_flash = 0.0
        self.landed = False
        self._corridor_music_suppressed = False
        self._outro_started = False

    def _arena(self, maze, cell_size):
        exit_col = maze.cols - 1
        exit_row = maze.rows + 2
        cx = (exit_col - 5 + 0.5) * cell_size
        cy = (exit_row + 0.5) * cell_size
        half_w = 2.45 * cell_size
        half_h = 1.95 * cell_size
        return cx, cy, half_w, half_h

    def _keep_in_arena(self, x, y, cx, cy, hw, hh, margin=20):
        return (_clamp(x, cx - hw + margin, cx + hw - margin),
                _clamp(y, cy - hh + margin, cy + hh - margin))

    def _spawn_dust(self, x, y, amount=2):
        for _ in range(amount):
            ang = random.uniform(0.0, math.tau)
            speed = random.uniform(12.0, 26.0)
            self.dust_particles.append({
                "x": x,
                "y": y,
                "vx": math.cos(ang) * speed,
                "vy": math.sin(ang) * speed * 0.55,
                "life": random.uniform(0.25, 0.5),
                "size": random.uniform(3.0, 6.0),
                "color": (125, 90, 70),
            })

    def _update_dust(self, dt):
        keep = []
        for p in self.dust_particles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
            p["vx"] *= 0.92
            p["vy"] += 0.2
            if p["life"] > 0:
                keep.append(p)
        self.dust_particles = keep

    def _hurt_player(self, player, from_x, from_y):
        if player is not None:
            player.hurt(1, from_x=from_x, from_y=from_y)

    def _parry_or_hit_player(self, player, x, y, radius):
        """Parry active boss hitboxes with a live sword swing; otherwise deal contact damage."""
        if player is None:
            return False
        reach = player.sword_reach(160)
        d = _distance(player.x, player.y, x, y)
        if player.swing_t > 0 and d <= reach + radius + player.size * 0.5:
            if player.trigger_parry():
                self.parry_flash = 0.22
        if d <= radius + player.size * 0.5:
            self._hurt_player(player, x, y)
            return True
        return False

    def _start_attack(self, player, cell_size, cx, cy, hw, hh):
        choices = ["outburst", "flame_loop", "smash1", "smash2", "lunge", "escape"]
        self.attack = random.choice(choices)
        self.attack_timer = 0.0
        self.attack_data = {}
        if self.attack == "outburst":
            dx, dy = player.x - self.x, player.y - self.y
            base = math.atan2(dy, dx)
            # Five narrow lanes; the gaps between lanes are intentionally visible.
            self.attack_data["lanes"] = [base + (i - 2) * 0.24 for i in range(5)]
            for ang in self.attack_data["lanes"]:
                self.projectiles.append({"x": self.x, "y": self.y, "vx": math.cos(ang) * cell_size * 4.0,
                                         "vy": math.sin(ang) * cell_size * 4.0, "r": cell_size * 0.10,
                                         "life": 0.95, "kind": "flame", "parryable": False})
            audio.play("boss1_flame_outburst")
        elif self.attack == "flame_loop":
            self.attack_data["next_shot"] = 0.0
            self.attack_data["angle"] = random.random() * math.tau
            self.x, self.y = cx, cy
            audio.play_looping_sfx("boss1_flame_loop")
        elif self.attack == "smash1":
            self.hazards = []
            for _ in range(6):
                hx = random.uniform(cx - hw * 0.78, cx + hw * 0.78)
                hy = random.uniform(cy - hh * 0.78, cy + hh * 0.78)
                self.hazards.append({"x": hx, "y": hy, "r": cell_size * 0.48, "warn": 0.72, "life": 0.55, "active": False, "hit": False})
            audio.play("boss1_smash1")
        elif self.attack == "smash2":
            hx = random.uniform(cx - hw * 0.78, cx + hw * 0.78)
            hy = random.uniform(cy - hh * 0.78, cy + hh * 0.78)
            self.hazards = [{"x": hx, "y": hy, "r": cell_size * 2.0, "warn": 0.92, "life": 0.65, "active": False, "hit": False}]
            audio.play("boss1_smash2")
        elif self.attack == "lunge":
            self.attack_data.update(stage="random_aim", next_stage=0.45, count=0)
        elif self.attack == "escape":
            self.attack_data.update(stage="shrink", destination=self._keep_in_arena(
                random.uniform(cx-hw, cx+hw), random.uniform(cy-hh, cy+hh), cx, cy, hw, hh))
            self.clones = []

    def _apply_boss_hit(self, damage, hit_x=None, hit_y=None, heal_on_hit=False):
        if damage <= 0 or self.hp <= 0:
            return False
        self.hp = max(0, self.hp - damage)
        self.hurt_flash = 0.10
        audio.play("enemy_damage")
        if heal_on_hit and self.hp > 0:
            # Damage from sword / circle swings charges the heal meter like normal enemies.
            pass
        if self.hp <= 0:
            self.state = "DYING"
            self.death_stage = 0
            self.death_timer = 0.0
            if self.attack == "flame_loop":
                audio.stop_looping_sfx("boss1_flame_loop")
            self.attack = None
            self.projectiles.clear()
            self.hazards.clear()
            audio.fade_boss_music(0.45)
        return True

    def _update_boss_damage(self, player, cell_size, manager=None):
        self.hurt_flash = max(0.0, self.hurt_flash - 1/60)
        if player is None:
            return

        if player.circle_timer > 0 and id(self) not in player.swing_hits:
            dx, dy = self.x - player.x, self.y - player.y
            dist = math.hypot(dx, dy)
            if dist <= player.circle_radius + self.radius + player.size * 0.5:
                player.swing_hits.add(id(self))
                if self._apply_boss_hit(2, player.x, player.y, heal_on_hit=True):
                    player.add_heal(1)
                return

        if player.swing_t > 0 and id(self) not in player.swing_hits:
            reach = player.sword_reach(cell_size)
            dx, dy = self.x - player.x, self.y - player.y
            dist = math.hypot(dx, dy)
            if dist <= reach + self.radius + player.size * 0.5:
                if dist > 0:
                    ux, uy = dx / dist, dy / dist
                    dot = ux * player.swing_dir[0] + uy * player.swing_dir[1]
                    if dot < 0.18:
                        return
                player.swing_hits.add(id(self))
                if self._apply_boss_hit(1, player.x, player.y, heal_on_hit=True):
                    player.add_heal(1)
                return

        all_shots = list(player.projectile_queue)
        if manager and hasattr(manager, "player_projectiles"):
            all_shots.extend(manager.player_projectiles)

        for shot in all_shots:
            if shot is None:
                continue
            dx, dy = self.x - shot["x"], self.y - shot["y"]
            dist = math.hypot(dx, dy)
            if dist <= self.radius + shot.get("radius", 12.0):
                if shot in player.projectile_queue:
                    player.projectile_queue.remove(shot)
                if manager and hasattr(manager, "player_projectiles") and shot in manager.player_projectiles:
                    manager.player_projectiles.remove(shot)
                if self._apply_boss_hit(shot.get("damage", 3), shot["x"], shot["y"]):
                    pass
                return

    def _update_projectiles(self, player, dt, cell_size):
        alive = []
        for p in self.projectiles:
            p["x"] += p["vx"] * dt
            p["y"] += p["vy"] * dt
            p["life"] -= dt
            if p["life"] <= 0:
                continue
            d = _distance(player.x, player.y, p["x"], p["y"])
            if p.get("parryable") and player.swing_t > 0 and d <= player.sword_reach(cell_size) + p["r"] + player.size * 0.5:
                if player.trigger_parry():
                    self.parry_flash = 0.22
                # A live sword deflects the projectile even if this swing already parried once.
                continue
            if d <= p["r"] + player.size * 0.5:
                self._hurt_player(player, p["x"], p["y"])
                continue
            alive.append(p)
        self.projectiles = alive

    def _update_hazards(self, player, dt, cell_size=160):
        remaining = []
        for h in self.hazards:
            if not h["active"]:
                h["warn"] -= dt
                if h["warn"] <= 0:
                    h["active"] = True
            else:
                h["life"] -= dt
                d = _distance(player.x, player.y, h["x"], h["y"])
                if player.swing_t > 0 and d <= player.sword_reach(cell_size) + h["r"]:
                    if player.trigger_parry():
                        self.parry_flash = 0.22
                if not h["hit"] and d <= h["r"] + player.size * 0.5:
                    self._hurt_player(player, h["x"], h["y"])
                    h["hit"] = True
                if h["life"] <= 0:
                    continue
            remaining.append(h)
        self.hazards = remaining

    def _update_attack(self, player, dt, cell_size, cx, cy, hw, hh):
        if not self.attack:
            self.attack_timer += dt
            if self.attack_timer >= 0.6:
                self._start_attack(player, cell_size, cx, cy, hw, hh)
            return
        self.attack_timer += dt
        if self.attack == "outburst":
            if self.attack_timer > 1.05:
                self.attack = None; self.attack_timer = 0
        elif self.attack == "flame_loop":
            self.x, self.y = cx, cy
            self.attack_data["next_shot"] -= dt
            if self.attack_data["next_shot"] <= 0:
                a = self.attack_data["angle"]
                self.projectiles.append({"x": self.x, "y": self.y,
                    "vx": math.cos(a) * cell_size * 2.8, "vy": math.sin(a) * cell_size * 2.8,
                    "r": cell_size * 0.2, "life": 1.5, "kind": "fireball", "parryable": False})
                self.attack_data["angle"] = (a + 2.399963229728653) % math.tau
                self.attack_data["next_shot"] = 0.105
            if self.attack_timer >= 2.25:
                audio.stop_looping_sfx("boss1_flame_loop")
                self.attack = None; self.attack_timer = 0
        elif self.attack in ("smash1", "smash2"):
            if self.attack_timer >= 2.1 or not self.hazards:
                self.attack = None; self.attack_timer = 0; self.hazards = []
        elif self.attack == "lunge":
            data = self.attack_data
            data["next_stage"] -= dt
            if data["stage"] == "random_aim":
                if data["next_stage"] <= 0:
                    ang = random.uniform(0, math.tau)
                    data["direction"] = (math.cos(ang), math.sin(ang))
                    data["stage"] = "random_lunge"
                    data["next_stage"] = 0.28
                    data["swing_angle"] = ang
            elif data["stage"] == "random_lunge":
                ux, uy = data["direction"]
                self.x, self.y = self._keep_in_arena(self.x + ux * cell_size * 4.8 * dt,
                    self.y + uy * cell_size * 4.8 * dt, cx, cy, hw, hh, self.radius)
                if data["next_stage"] <= 0:
                    data["stage"] = "aim"; data["next_stage"] = 0.45
            elif data["stage"] == "aim":
                if data["next_stage"] <= 0:
                    ang = math.atan2(player.y - self.y, player.x - self.x)
                    data["direction"] = (math.cos(ang), math.sin(ang))
                    data["swing_angle"] = ang
                    data["stage"] = "player_lunge"; data["next_stage"] = 0.32
            elif data["stage"] == "player_lunge":
                ux, uy = data["direction"]
                self.x, self.y = self._keep_in_arena(self.x + ux * cell_size * 5.2 * dt,
                    self.y + uy * cell_size * 5.2 * dt, cx, cy, hw, hh, self.radius)
                if _distance(player.x, player.y, self.x, self.y) < self.radius + player.size:
                    # Lunge swing is a parryable melee hitbox.
                    if player.swing_t > 0:
                        if player.trigger_parry():
                            self.parry_flash = 0.22
                    else:
                        self._hurt_player(player, self.x, self.y)
                if data["next_stage"] <= 0:
                    data["stage"] = "random_aim"; data["next_stage"] = 0.35
                    data["count"] += 1
                    if data["count"] >= 2:
                        self.attack = None; self.attack_timer = 0
        elif self.attack == "escape":
            data = self.attack_data
            if data["stage"] == "shrink" and self.attack_timer >= 0.28:
                old_x, old_y = self.x, self.y
                self.clones = [{"x": old_x, "y": old_y, "life": 0.5},
                               {"x": data["destination"][0], "y": data["destination"][1], "life": 0.5}]
                self.x, self.y = data["destination"]
                data["stage"] = "grow"
                self.attack_timer = 0.0
            elif data["stage"] == "grow" and self.attack_timer >= 0.32:
                self.attack = None; self.attack_timer = 0

    def update(self, context):
        player, maze = context["player"], context["maze"]
        cell_size = context["cell_size"]
        manager = context.get("manager")
        dt = max(0.0, min(0.05, context.get("dt", 1/60)))
        old_x, old_y = self.x, self.y
        if player is not None and player.hp <= 0:
            audio.stop_looping_sfx("boss1_flame_loop")
            audio.fade_boss_music(0.08)
            return
        cx, cy, hw, hh = self._arena(maze, cell_size)
        if self.state == "WAITING":
            # Entering the final corridor silences maze tracks permanently for this round.
            in_corridor = (player.y >= maze.rows * cell_size - cell_size * 0.15 and
                           player.x >= (maze.cols - 1.8) * cell_size)
            if in_corridor and not self._corridor_music_suppressed:
                audio.suppress_maze_music()
                self._corridor_music_suppressed = True
            if _distance(player.x, player.y, cx, cy) < cell_size * 1.2:
                self.state = "INTRO"
                self.timer = INTRO_DURATION
                self.x, self.y = cx, cy
                self.radius = cell_size * 0.42
                # Keep the player frozen in a safe spot away from the landing point.
                self.intro_player_pos = (cx + cell_size * 1.35, cy + cell_size * 0.25)
                player.x, player.y = self.intro_player_pos
                player.hp = 8
                player.max_hp = 8
                player.heal_meter = HEAL_MAX
                player.heal_progress = 0.0
                audio.stop_boss_music()
                audio.play("boss_suspence")
                context["combat_active"] = True
                context["maze"].boss_entrance_blocked = True
                context["show_hud"] = False
                context["show_minimap"] = False
                context["camera_shake"] = (0, 0)
        elif self.state == "INTRO":
            self.timer = self.timer - dt
            self.x, self.y = cx, cy
            player.x, player.y = self.intro_player_pos
            progress = 1.0 - self.timer / INTRO_DURATION
            if not self.landed: self.radius = cell_size * (1.8 - 1.38 * progress)
            intensity = SHAKE_INTENSITY * (self.timer / INTRO_DURATION)
            context["camera_shake"] = (random.uniform(-intensity, intensity), random.uniform(-intensity, intensity))
            if self.timer <= 0 and not self.landed:
                context["camera_shake"] = (0, 0)
                audio.play("boss_land")
                self.radius = cell_size * 0.42
                self.landed = True
            if self.timer <= -1:
                self.landed = False
                self.state = "ACTIVE"
                audio.play_boss_music("boss1_music", loop=True)
        elif self.state == "ACTIVE":
            self.radius = cell_size * 0.42
            self.parry_flash = max(0.0, self.parry_flash - dt)
            if player is not None and _distance(player.x, player.y, self.x, self.y) <= self.radius + player.size * 0.5:
                self._hurt_player(player, self.x, self.y)
            self._update_boss_damage(player, cell_size, manager)
            if self.state == "DYING":
                return
            self._update_attack(player, dt, cell_size, cx, cy, hw, hh)
            self._update_projectiles(player, dt, cell_size)
            self._update_hazards(player, dt, cell_size)
            for clone in self.clones:
                clone["life"] -= dt
            self.clones = [c for c in self.clones if c["life"] > 0]
        elif self.state == "DYING":
            self.death_timer += dt
            # 0: fade music; 1: cinematic outro + final impact; 2: delayed death; 3: explosion.
            if self.death_stage == 0 and audio.boss_fade_remaining <= 0:
                audio.play_boss_music("boss1_music_end", loop=False)
                audio.play("boss_final_hit")
                self.death_stage = 1
                self.death_timer = 0.0
            elif self.death_stage == 1 and self.death_timer >= 1.0:
                audio.play("boss_dying")
                self.death_stage = 2
                self.death_timer = 0.0
            elif self.death_stage == 2 and self.death_timer >= 3.0:
                audio.play("boss_explode_clean")
                self.death_stage = 3
                self.death_timer = 0.0
            elif self.death_stage == 3 and self.death_timer >= 0.55:
                self.state = "DEAD"
                context["game_won_ref"]()
        if self.state in ("INTRO", "ACTIVE"):
            moved = _distance(old_x, old_y, self.x, self.y)
            if moved > 0.25:
                self._spawn_dust(self.x, self.y, amount=2)
        self._update_dust(dt)
        context["boss_state"] = self.state

    def draw(self, context, cam_x, cam_y):
        surface = pygame.display.get_surface()
        if surface is None or self.state in ("WAITING", "DEAD"):
            return
        cell = context["cell_size"]
        for p in self.dust_particles:
            pygame.draw.circle(surface, p["color"], (int(p["x"] - cam_x), int(p["y"] - cam_y)), max(1, int(p["size"])))
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        if self.state == "INTRO":
            progress = 1.0 - self.timer / INTRO_DURATION
            # Layered translucent ellipses approximate a soft shadow whose blur shrinks on impact.
            shadow_r = int(self.radius * (1.65 - 0.75 * progress))
            for i in range(9, 0, -1):
                rr = max(2, int(shadow_r * i / 9))
                alpha = int(8 + 15 * (1 - i / 9))
                layer = pygame.Surface((rr * 2 + 4, rr + 4), pygame.SRCALPHA)
                pygame.draw.ellipse(layer, (0, 0, 0, alpha), (2, 2, rr * 2, rr))
                surface.blit(layer, (sx - rr - 2, sy + int(self.radius * 0.48)))
        for clone in self.clones:
            a = max(0, min(150, int(150 * clone["life"] / 0.5)))
            pygame.draw.circle(surface, (180, 40, 55), (int(clone["x"]-cam_x), int(clone["y"]-cam_y)), max(2, int(cell * 0.16)))
        # Telegraph circles are hollow while warning and filled while active.
        for h in self.hazards:
            hx, hy = int(h["x"]-cam_x), int(h["y"]-cam_y)
            col = (255, 110, 35) if not h["active"] else (255, 45, 15)
            pygame.draw.circle(surface, col, (hx, hy), max(2, int(h["r"])), 4 if not h["active"] else 0)
        for p in self.projectiles:
            col = (255, 105, 25) if p["kind"] == "flame" else (255, 205, 65)
            pygame.draw.circle(surface, col, (int(p["x"]-cam_x), int(p["y"]-cam_y)), max(3, int(p["r"])))
            pygame.draw.circle(surface, (255, 245, 190), (int(p["x"]-cam_x), int(p["y"]-cam_y)), max(1, int(p["r"]*0.42)))
        if self.state == "DYING":
            pulse = 1.0 + 0.18 * math.sin(self.death_timer * 22)
            radius = max(1, int(self.radius * pulse * max(0.05, 1 - self.death_timer * 0.08)))
        elif self.attack == "escape" and self.attack_data.get("stage") == "shrink":
            radius = max(2, int(self.radius * max(0.03, 1 - self.attack_timer / 0.28)))
        else:
            radius = max(2, int(self.radius))
        color = (255, 70, 65) if self.hurt_flash <= 0 else (255, 220, 210)
        pygame.draw.circle(surface, (85, 0, 0), (sx, sy), radius + 4)
        pygame.draw.circle(surface, color, (sx, sy), radius)
        eye_r = max(2, int(radius * 0.12))
        eye_dx = int(radius * 0.32)
        eye_y = sy - int(radius * 0.14)
        pygame.draw.circle(surface, (255, 245, 220), (sx-eye_dx, eye_y), eye_r)
        pygame.draw.circle(surface, (255, 245, 220), (sx+eye_dx, eye_y), eye_r)
        pupil_r = max(1, eye_r // 2)
        pygame.draw.circle(surface, (35, 0, 0), (sx-eye_dx, eye_y), pupil_r)
        pygame.draw.circle(surface, (35, 0, 0), (sx+eye_dx, eye_y), pupil_r)
        if self.attack == "lunge" and self.attack_data.get("stage") in ("random_lunge", "player_lunge"):
            angle = self.attack_data.get("swing_angle", 0.0)
            start = (sx + int(math.cos(angle) * radius * 0.45), sy + int(math.sin(angle) * radius * 0.45))
            end = (sx + int(math.cos(angle) * (radius + cell * 0.72)), sy + int(math.sin(angle) * (radius + cell * 0.72)))
            pygame.draw.line(surface, (255, 235, 185), start, end, max(4, int(cell * 0.09)))
            pygame.draw.line(surface, (255, 95, 35), start, end, max(2, int(cell * 0.035)))

    def draw_hud(self, width=800):
        if self.state not in ("ACTIVE", "DYING"):
            return
        surface = pygame.display.get_surface()
        if surface is None:
            return
        bar_w = min(560, width - 80)
        x = (width - bar_w) // 2
        y = 18
        pygame.draw.rect(surface, (30, 10, 12), (x-3, y-3, bar_w+6, 25), border_radius=6)
        pygame.draw.rect(surface, (65, 20, 25), (x, y, bar_w, 19), border_radius=4)
        fill = int(bar_w * self.hp / self.max_hp)
        if fill > 0:
            pygame.draw.rect(surface, (225, 35, 45), (x, y, fill, 19), border_radius=4)
        pygame.draw.rect(surface, (255, 190, 190), (x, y, bar_w, 19), 2, border_radius=4)


boss_manager = BossManager()

def reset_boss():
    boss_manager.reset()

def run_boss_logic(context):
    boss_manager.update(context)
def draw_boss(context, cam_x, cam_y):
    boss_manager.draw(context, cam_x, cam_y)
def draw_boss_hud(width=800):
    boss_manager.draw_hud(width)
