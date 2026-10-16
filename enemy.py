import random
from collections import deque
from math import hypot, cos, sin, atan2, pi

from pygame import Surface, SRCALPHA, display
from pygame import draw as pgdraw
from mckPy import drawCircle
from audio import audio

FPS = 60
DT = 1.0 / FPS
GRASS_RATIO = 78.0 / 512.0   # wall thickness as a fraction of a tile (same as player.py)
MAX_CHASERS = 15

DIRS = (('N', 0, -1), ('E', 1, 0), ('S', 0, 1), ('W', -1, 0))

# speed: fraction of the player's speed | radius/sight/hold: tiles | lose: seconds
# hold: ranged/special enemies stop approaching at this distance (when they see the
# player) and wait for their attack to be ready
KINDS = {
    0: dict(name="chaser",  hp=3, color=(128, 0, 128),   radius=0.18, speed=0.80, sight=999, lose=999, hold=0),
    1: dict(name="grunt",   hp=2, color=(170, 170, 170), radius=0.15, speed=0.35, sight=3.5, lose=1.0, hold=0),
    2: dict(name="spitter", hp=3, color=(70, 200, 70),   radius=0.16, speed=0.50, sight=5.5, lose=1.2, hold=2.5),
    3: dict(name="lunger",  hp=3, color=(70, 130, 255),  radius=0.16, speed=0.55, sight=4.5, lose=1.2, hold=2.8),
    4: dict(name="brute",   hp=7, color=(255, 105, 180), radius=0.21, speed=0.45, sight=5.0, lose=2.0, hold=2.0),
    5: dict(name="hunter",  hp=5, color=(255, 140, 0),   radius=0.19, speed=0.55, sight=6.5, lose=1.5, hold=3.5),
}
SPAWN_WEIGHTS = {1: 40, 2: 26, 3: 18, 4: 10, 5: 6}   # rarity

AOE_RADIUS_CELLS = 3      # brute blast radius
HAZARD_WARN = 1.0         # seconds of telegraph
HAZARD_ACTIVE = 0.3       # seconds the hazard actually hurts
SWORD_REACH_CELLS = 1.1   # enemy sword reach
ENEMY_HIT_INVINCIBLE = 0.25


# ---------------------------------------------------------------- drawing helpers
def _scr():
    return display.get_surface()


def alpha_circle(cx, cy, r, color, alpha):
    scr = _scr()
    w, h = scr.get_size()
    x0, y0 = max(0, int(cx - r)), max(0, int(cy - r))
    x1, y1 = min(w, int(cx + r) + 1), min(h, int(cy + r) + 1)
    if x1 <= x0 or y1 <= y0 or r < 1:
        return
    s = Surface((x1 - x0, y1 - y0), SRCALPHA)
    pgdraw.circle(s, (*color, alpha), (int(cx) - x0, int(cy) - y0), int(r))
    scr.blit(s, (x0, y0))


def alpha_rect(x, y, rw, rh, color, alpha):
    scr = _scr()
    w, h = scr.get_size()
    x0, y0 = max(0, int(x)), max(0, int(y))
    x1, y1 = min(w, int(x + rw)), min(h, int(y + rh))
    if x1 <= x0 or y1 <= y0:
        return
    s = Surface((x1 - x0, y1 - y0), SRCALPHA)
    s.fill((*color, alpha))
    scr.blit(s, (x0, y0))


def alpha_poly(points, color, alpha):
    scr = _scr()
    w, h = scr.get_size()
    xs = [p[0] for p in points]
    ys = [p[1] for p in points]
    x0, y0 = max(0, int(min(xs))), max(0, int(min(ys)))
    x1, y1 = min(w, int(max(xs)) + 1), min(h, int(max(ys)) + 1)
    if x1 <= x0 or y1 <= y0:
        return
    s = Surface((x1 - x0, y1 - y0), SRCALPHA)
    pgdraw.polygon(s, (*color, alpha), [(int(px) - x0, int(py) - y0) for px, py in points])
    scr.blit(s, (x0, y0))


def sector_points(cx, cy, ang0, half_angle, radius, steps=12):
    pts = [(cx, cy)]
    for i in range(steps + 1):
        a = ang0 - half_angle + (2 * half_angle) * i / steps
        pts.append((cx + cos(a) * radius, cy + sin(a) * radius))
    return pts


# ---------------------------------------------------------------- geometry
class Geo:
    """Wall geometry helpers (same wall thickness as the player's collision)."""

    def __init__(self, maze, cell):
        self.maze = maze
        self.cell = cell
        self.margin = cell * GRASS_RATIO
        self.W = maze.cols * cell
        self.H = maze.rows * cell
        self.step = max(3.0, self.margin * 0.8)

    def center(self, c, r):
        return (c + 0.5) * self.cell, (r + 0.5) * self.cell

    def cell_of(self, x, y):
        c = min(max(int(x // self.cell), 0), self.maze.cols - 1)
        r = min(max(int(y // self.cell), 0), self.maze.rows - 1)
        return c, r

    def point_in_wall(self, x, y):
        m, cell = self.margin, self.cell
        if x < m or y < m or x > self.W - m or y > self.H - m:
            return True
        c, r = int(x // cell), int(y // cell)
        w = self.maze.grid[c][r].walls
        lx, ly = x - c * cell, y - r * cell
        return ((w['N'] and ly < m) or (w['S'] and ly > cell - m) or
                (w['W'] and lx < m) or (w['E'] and lx > cell - m))

    def rect_hits(self, cx, cy, half):
        """Does a square of half-size `half` centred on (cx, cy) touch a wall or the maze border?"""
        m, cell = self.margin, self.cell
        left, right, top, bottom = cx - half, cx + half, cy - half, cy + half
        if left < m or right > self.W - m or top < m or bottom > self.H - m:
            return True
        c0, c1 = max(0, int(left // cell)), min(self.maze.cols - 1, int(right // cell))
        r0, r1 = max(0, int(top // cell)), min(self.maze.rows - 1, int(bottom // cell))
        for c in range(c0, c1 + 1):
            x0 = c * cell
            for r in range(r0, r1 + 1):
                y0 = r * cell
                w = self.maze.grid[c][r].walls
                in_x = left < x0 + cell and right > x0
                in_y = top < y0 + cell and bottom > y0
                if w['N'] and in_x and top < y0 + m and bottom > y0:
                    return True
                if w['S'] and in_x and top < y0 + cell and bottom > y0 + cell - m:
                    return True
                if w['W'] and in_y and left < x0 + m and right > x0:
                    return True
                if w['E'] and in_y and left < x0 + cell and right > x0 + cell - m:
                    return True
        return False

    def line_clear(self, ax, ay, bx, by, radius=0.0):
        """Line of sight (radius 0) or 'can a body of this radius walk straight there'."""
        d = hypot(bx - ax, by - ay)
        if d < 1e-6:
            return True
        i = 1
        while i * self.step < d:
            t = i * self.step / d
            x, y = ax + (bx - ax) * t, ay + (by - ay) * t
            if radius > 0:
                if self.rect_hits(x, y, radius):
                    return False
            elif self.point_in_wall(x, y):
                return False
            i += 1
        return True


def bfs_path(maze, start, goal):
    """Cells to walk through (excluding start) to reach goal, [] if none."""
    if start == goal:
        return []
    parent = {start: None}
    q = deque([start])
    while q:
        cur = q.popleft()
        if cur == goal:
            break
        c, r = cur
        walls = maze.grid[c][r].walls
        for wall, dc, dr in DIRS:
            if not walls[wall]:
                n = (c + dc, r + dr)
                if 0 <= n[0] < maze.cols and 0 <= n[1] < maze.rows and n not in parent:
                    parent[n] = cur
                    q.append(n)
    if goal not in parent:
        return []
    path = []
    cur = goal
    while cur != start:
        path.append(cur)
        cur = parent[cur]
    path.reverse()
    return path


def bfs_distances(maze, start):
    dist = {start: 0}
    q = deque([start])
    while q:
        c, r = q.popleft()
        walls = maze.grid[c][r].walls
        for wall, dc, dr in DIRS:
            if not walls[wall]:
                n = (c + dc, r + dr)
                if 0 <= n[0] < maze.cols and 0 <= n[1] < maze.rows and n not in dist:
                    dist[n] = dist[(c, r)] + 1
                    q.append(n)
    return dist


# ---------------------------------------------------------------- enemy
class Enemy:
    def __init__(self, kind, x, y, geo, player_speed):
        info = KINDS[kind]
        self.kind = kind
        self.info = info
        self.geo = geo
        self.x, self.y = x, y
        self.hp = self.max_hp = float(info["hp"])
        self.dust_particles = []
        self.damage_particles = []
        self.death_particles = []
        self.dead = False
        self.death_timer = 0.0
        self.radius = max(5.0, geo.cell * info["radius"])
        self.half = self.radius * 0.85
        self.speed_unit = player_speed
        self.aggro = (kind == 0)
        self.lose_timer = 0.0
        self.act = None                 # current attack: dict(name, t, ...)
        self.cd = random.uniform(0.5, 1.5)
        self.inv = 0.0
        self.flash = 0.0
        self.kbx = self.kby = 0.0
        self.path = []
        self.path_timer = random.random() * 0.3
        self.slash = 0.0
        self.slash_dir = (1.0, 0.0)
        self.face = (1.0, 0.0)
        self.ai_active = True
        self.step_acc = 0.0

    def _spawn_dust(self, x, y, amount=1, color=None):
        color = self.info["color"] if color is None else color
        for _ in range(amount):
            ang = random.uniform(0.0, 2 * pi)
            speed = random.uniform(8.0, 18.0)
            self.dust_particles.append({
                "x": x,
                "y": y,
                "vx": cos(ang) * speed,
                "vy": sin(ang) * speed * 0.5,
                "life": random.uniform(0.20, 0.45),
                "size": random.uniform(2.0, 4.5),
                "color": color,
            })

    def _update_dust(self):
        keep = []
        for p in self.dust_particles:
            p["x"] += p["vx"] * DT
            p["y"] += p["vy"] * DT
            p["life"] -= DT
            p["vx"] *= 0.95
            p["vy"] += 0.18
            if p["life"] > 0:
                keep.append(p)
        self.dust_particles = keep

    # ---- movement
    def move(self, dx, dy):
        moved = False
        if dx:
            nx = self.x + dx
            if not self.geo.rect_hits(nx, self.y, self.half):
                self.x = nx
                moved = True
        if dy:
            ny = self.y + dy
            if not self.geo.rect_hits(self.x, ny, self.half):
                self.y = ny
                moved = True
        return moved

    def _spawn_damage_particles(self, x, y, amount=8, color=None):
        color = self.info["color"] if color is None else color
        for _ in range(amount):
            ang = random.uniform(0.0, 2 * pi)
            if x and y:
                pass
            speed = random.uniform(26.0, 80.0)
            self.damage_particles.append({
                "x": x,
                "y": y,
                "vx": cos(ang) * speed,
                "vy": sin(ang) * speed,
                "life": random.uniform(0.18, 0.42),
                "size": random.uniform(2.0, 5.0),
                "color": color,
            })

    def _spawn_death_particles(self, x=None, y=None, amount=18):
        x = self.x if x is None else x
        y = self.y if y is None else y
        for _ in range(amount):
            ang = random.uniform(0.0, 2 * pi)
            speed = random.uniform(18.0, 58.0)
            self.death_particles.append({
                "x": x,
                "y": y,
                "vx": cos(ang) * speed,
                "vy": sin(ang) * speed * 0.8,
                "life": random.uniform(0.35, 0.75),
                "size": random.uniform(2.5, 6.0),
                "color": (255, 130, 20),
            })

    def _update_particle_lists(self):
        for key in ("damage_particles", "death_particles"):
            keep = []
            particles = getattr(self, key)
            for p in particles:
                p["x"] += p["vx"] * DT
                p["y"] += p["vy"] * DT
                p["life"] -= DT
                p["vx"] *= 0.92
                p["vy"] *= 0.92
                p["vy"] += 0.12 if key == "death_particles" else 0.0
                if p["life"] > 0:
                    keep.append(p)
            setattr(self, key, keep)

    def take_hit(self, dmg, from_x, from_y):
        if self.inv > 0 or self.hp <= 0:
            return False
        self.hp -= dmg
        self.inv = ENEMY_HIT_INVINCIBLE
        self.flash = 0.15
        self.aggro = True
        self.lose_timer = 0.0
        self._spawn_damage_particles(self.x, self.y, amount=8, color=self.info["color"])
        audio.play("enemy_damage")
        if self.hp <= 0:
            self.dead = True
            self.death_timer = 0.7
            self._spawn_death_particles()
        d = hypot(self.x - from_x, self.y - from_y) or 1.0
        kb = self.geo.cell * (0.10 if self.kind == 0 else 0.08)  # chasers get stronger knockback
        if self.act is None or self.kind == 0:
            self.kbx = (self.x - from_x) / d * kb
            self.kby = (self.y - from_y) / d * kb
        return True

    # ---- AI
    def update(self, mgr, player):
        if self.dead:
            self.death_timer = max(0.0, self.death_timer - DT)
            self._update_particle_lists()
            return
        x0, y0 = self.x, self.y
        self._ai_update(mgr, player)
        moved = hypot(self.x - x0, self.y - y0)
        if moved > 0.25:
            self._spawn_dust(self.x, self.y, amount=1 if moved < 3 else 2)
        self._update_dust()
        self._update_particle_lists()
        self._footsteps(player, moved)

    def _footsteps(self, player, moved):
        """Footstep sounds, quieter the further the enemy is from the player."""
        if moved < 0.5 or (self.act and self.act.get('phase') == 'dash'):
            return
        self.step_acc += moved
        stride = self.geo.cell * 0.55
        if self.step_acc >= stride:
            self.step_acc -= stride
            vol = audio.falloff(hypot(player.x - self.x, player.y - self.y), self.geo.cell * 6)
            audio.play("footstep", vol * 0.8, group="enemy_step")

    def _ai_update(self, mgr, player):
        if not self.ai_active:
            return
        g = self.geo
        cell = g.cell
        self.inv = max(0.0, self.inv - DT)
        self.flash = max(0.0, self.flash - DT)
        self.cd = max(0.0, self.cd - DT)
        self.slash = max(0.0, self.slash - DT)

        if abs(self.kbx) > 0.3 or abs(self.kby) > 0.3:
            self.move(self.kbx, self.kby)
            self.kbx *= 0.82
            self.kby *= 0.82
        else:
            self.kbx = self.kby = 0.0

        dx, dy = player.x - self.x, player.y - self.y
        dist = hypot(dx, dy)
        if dist > 0:
            self.face = (dx / dist, dy / dist)

        sight = self.info["sight"] * cell
        sees = False
        if self.kind != 0 and dist <= sight:
            sees = g.line_clear(self.x, self.y, player.x, player.y)

        if self.kind != 0:
            if not self.aggro:
                if sees:                # spotted the player
                    self.aggro = True
                    self.lose_timer = 0.0
            else:
                if dist > sight:        # outside range -> eventually loses the player
                    self.lose_timer += DT
                    if self.lose_timer >= self.info["lose"]:
                        self.aggro = False
                        self.path = []
                else:
                    self.lose_timer = 0.0

        if self.act:
            self._update_act(mgr, player, dx, dy, dist)
            return
        if not self.aggro:
            return
        if sees and self.cd <= 0 and dist > 1 and self._start_attack(mgr, dx, dy, dist):
            return
        hold = self.info["hold"] * cell
        if sees and hold and dist <= hold:
            # Keep the hold distance as a movement preference, not an attack lock.
            # Enemies should still be allowed to fire their active abilities while
            # inside this range, and only drift/pivot when they must wait for cooldown.
            if self.cd <= 0 and self._start_attack(mgr, dx, dy, dist):
                return
            if self.cd > 0 and dist > 0.5:
                retreat = min(self.info["speed"] * self.speed_unit * 0.5, dist * 0.6)
                self.move(-(dx / dist) * retreat, -(dy / dist) * retreat)
            else:
                self._chase(player, dx, dy, dist)
            return
        self._chase(player, dx, dy, dist)

    def _chase(self, player, dx, dy, dist):
        g = self.geo
        speed = self.info["speed"] * self.speed_unit
        # Straight at the player whenever a body of our size fits through, otherwise follow the maze.
        if g.line_clear(self.x, self.y, player.x, player.y, self.half):
            self.path = []
            if dist > 1:
                step = min(speed, dist)
                self.move(dx / dist * step, dy / dist * step)
            return
        self.path_timer -= DT
        if self.path_timer <= 0 or not self.path:
            self.path_timer = 0.3
            self.path = bfs_path(g.maze, g.cell_of(self.x, self.y), g.cell_of(player.x, player.y))
        if not self.path:
            return
        tx, ty = g.center(*self.path[0])
        if not g.line_clear(self.x, self.y, tx, ty, self.half):
            tx, ty = g.center(*g.cell_of(self.x, self.y))      # realign via the current cell's centre
        wx, wy = tx - self.x, ty - self.y
        wd = hypot(wx, wy)
        if wd <= speed:
            self.move(wx, wy)
            if (tx, ty) == g.center(*self.path[0]):
                self.path.pop(0)
        else:
            self.move(wx / wd * speed, wy / wd * speed)

    def _start_attack(self, mgr, dx, dy, dist):
        cell = self.geo.cell
        k = self.kind
        if k in (4, 5) and dist <= cell * 1.25:
            self.act = {'name': 'sword', 'phase': 'wind', 't': 0.38, 'ux': dx / dist, 'uy': dy / dist}
            return True
        if k == 2 and cell * 0.4 < dist <= cell * 5.5:
            self.act = {'name': 'acid', 't': 0.6, 'ux': dx / dist, 'uy': dy / dist}
            return True
        if k == 3 and cell < dist <= cell * 3.5:
            self.act = {'name': 'lunge', 'phase': 'wind', 't': 0.55, 'ux': dx / dist, 'uy': dy / dist}
            return True
        if k == 4:
            choice = None
            if dist <= cell * AOE_RADIUS_CELLS:
                choice = random.choice(('aoe', 'cross'))
            elif dist <= cell * 5:
                choice = 'cross'
            if choice:
                mgr.spawn_hazard(self, choice)
                self.act = {'name': choice, 't': HAZARD_WARN + HAZARD_ACTIVE}
                return True
        if k == 5 and cell * 1.25 < dist <= cell * 6.5:
            self.act = {'name': 'spear', 't': 0.6, 'ux': dx / dist, 'uy': dy / dist}
            return True
        return False

    def _update_act(self, mgr, player, dx, dy, dist):
        a = self.act
        name = a['name']
        S = self.speed_unit
        if dist > 0 and name in ('acid', 'spear', 'lunge', 'sword') and a.get('phase') in (None, 'wind'):
            a['ux'], a['uy'] = dx / dist, dy / dist                 # keep aiming while winding up
        if name in ('acid', 'spear'):
            a['t'] -= DT
            if a['t'] <= 0:
                mgr.spawn_projectile(self, name, (a['ux'], a['uy']))
                if name == 'acid':
                    audio.play('spit', audio.falloff(dist, self.geo.cell * 8))
                self.cd = 2.0 if name == 'acid' else 1.0
                self.act = None
        elif name == 'lunge':
            a['t'] -= DT
            if a['phase'] == 'wind':
                if a['t'] <= 0:
                    a['phase'], a['t'] = 'dash', 0.4
                    audio.play('lunge', audio.falloff(dist, self.geo.cell * 8))
            elif a['phase'] == 'dash':
                moved = self.move(a['ux'] * S * 2.0, a['uy'] * S * 2.0)
                if a['t'] <= 0 or not moved:
                    a['phase'], a['t'] = 'rec', 0.7
            elif a['t'] <= 0:
                self.cd = 0.5
                self.act = None
        elif name == 'sword':
            a['t'] -= DT
            if a['phase'] == 'wind':
                if a['t'] <= 0:
                    reach = self.geo.cell * SWORD_REACH_CELLS + player.size / 2
                    if dist <= reach and (dx * a['ux'] + dy * a['uy']) / max(dist, 1e-6) >= 0.35:
                        player.hurt(1, self.x, self.y)
                    self.slash = 0.18
                    self.slash_dir = (a['ux'], a['uy'])
                    audio.play('slash', audio.falloff(dist, self.geo.cell * 8))
                    a['phase'], a['t'] = 'rec', 0.3
            elif a['t'] <= 0:
                self.cd = 1.5
                self.act = None
        else:                                                         # 'aoe' / 'cross' (hazard handles damage)
            a['t'] -= DT
            if a['t'] <= 0:
                self.cd = 3.5
                self.act = None

    # ---- drawing
    def draw(self, cam_x, cam_y, w, h):
        sx, sy = int(self.x - cam_x), int(self.y - cam_y)
        r = int(self.radius)
        if sx < -200 or sy < -200 or sx > w + 200 or sy > h + 200:
            return
        for p in self.dust_particles:
            pgdraw.circle(_scr(), p["color"], (int(p["x"] - cam_x), int(p["y"] - cam_y)), max(1, int(p["size"])))
        for p in self.damage_particles:
            pgdraw.circle(_scr(), p["color"], (int(p["x"] - cam_x), int(p["y"] - cam_y)), max(1, int(p["size"])))
        for p in self.death_particles:
            pgdraw.circle(_scr(), p["color"], (int(p["x"] - cam_x), int(p["y"] - cam_y)), max(1, int(p["size"])))
        cell = self.geo.cell
        a = self.act
        # telegraphs
        if a and not self.dead:
            ux, uy = a.get('ux', 1.0), a.get('uy', 0.0)
            nm = a['name']
            if nm == 'lunge' and a['phase'] == 'wind':
                scr = _scr()
                pgdraw.line(scr, (140, 180, 255), (sx, sy), (sx + ux * cell * 3, sy + uy * cell * 3), 3)
            elif nm == 'acid':
                p = 1 - a['t'] / 0.6
                alpha_circle(sx + ux * r, sy + uy * r, cell * 0.30 * p, (90, 230, 60), 150)
                pgdraw.line(_scr(), (120, 255, 90), (sx, sy), (sx + ux * cell * 2, sy + uy * cell * 2), 2)
            elif nm == 'spear':
                pgdraw.line(_scr(), (255, 210, 120), (sx, sy), (sx + ux * cell * 6.5, sy + uy * cell * 6.5), 2)
            elif nm == 'sword' and a['phase'] == 'wind':
                alpha_poly(sector_points(sx, sy, atan2(uy, ux), 1.1, cell * SWORD_REACH_CELLS), (255, 60, 60), 70)
            elif nm in ('aoe', 'cross'):
                pgdraw.circle(_scr(), (255, 80, 80), (sx, sy), r + 6, 3)
        if self.slash > 0 and not self.dead:
            sdx, sdy = self.slash_dir
            alpha_poly(sector_points(sx, sy, atan2(sdy, sdx), 1.1, cell * SWORD_REACH_CELLS), (255, 255, 255), 170)

        if self.dead:
            dark = (20, 20, 25)
            drawCircle(dark, sx, sy, r, outline=2, outlineColour=(6, 6, 8))
            eye = max(2, r // 5)
            ex, ey = sx + int(self.face[0] * r * 0.45), sy + int(self.face[1] * r * 0.45)
            pgdraw.line(_scr(), (230, 230, 230), (ex - eye, ey - eye), (ex + eye, ey + eye), 2)
            pgdraw.line(_scr(), (230, 230, 230), (ex - eye, ey + eye), (ex + eye, ey - eye), 2)
            return

        col = self.info["color"]
        if self.flash > 0:
            col = (255, 255, 255)
        drawCircle(col, sx, sy, r, outline=2, outlineColour=(20, 20, 20))
        ex, ey = sx + int(self.face[0] * r * 0.45), sy + int(self.face[1] * r * 0.45)
        drawCircle((255, 255, 255), ex, ey, max(2, r // 4))
        drawCircle((0, 0, 0), ex, ey, max(1, r // 8))
        if self.aggro and self.kind != 0:
            drawCircle((255, 60, 60), sx, sy - r - 14, 3)

        bw = int(r * 2.4)
        bx, by = sx - bw // 2, sy - r - 9
        scr = _scr()
        pgdraw.rect(scr, (90, 0, 0), (bx, by, bw, 4))
        pgdraw.rect(scr, (60, 220, 60), (bx, by, int(bw * max(0, self.hp) / self.max_hp), 4))


# ---------------------------------------------------------------- manager
class EnemyManager:
    def __init__(self, maze, cell, player_speed, chase_enabled=False, chase_delay=3,
                 survival=False, survival_count=12):
        self.maze = maze
        self.cell = cell
        self.geo = Geo(maze, cell)
        self.player_speed = player_speed
        self.enemies = []
        self.projectiles = []
        self.player_projectiles = []
        self.hazards = []
        self.kills = 0
        self.chase_enabled = chase_enabled
        self.chase_delay = chase_delay
        self.chase_timer = chase_delay
        if survival:
            self._place_survival_enemies(survival_count)

    # ---- spawning
    def _place_survival_enemies(self, count):
        dist = bfs_distances(self.maze, (0, 0))
        far = max(dist.values()) if dist else 0
        min_d = min(6, max(2, far // 3))
        cells = [c for c, d in dist.items() if d >= min_d]
        random.shuffle(cells)
        kinds = list(SPAWN_WEIGHTS)
        weights = [SPAWN_WEIGHTS[k] for k in kinds]
        for c, r in cells[:count]:
            kind = random.choices(kinds, weights)[0]
            x, y = self.geo.center(c, r)
            self.enemies.append(Enemy(kind, x, y, self.geo, self.player_speed))

    def spawn_chaser(self):
        x, y = self.geo.center(0, 0)
        self.enemies.append(Enemy(0, x, y, self.geo, self.player_speed))

    def spawn_projectile(self, e, name, aim):
        cell = self.cell
        S = e.speed_unit
        ux, uy = aim
        if name == 'acid':
            p = dict(kind='acid', r=cell * 0.30, speed=S * 0.7, left=cell * 7, length=0)
        else:
            p = dict(kind='spear', r=cell * 0.06, speed=S * 2.0, left=cell * 9, length=cell * 0.55)
        p.update(x=e.x + ux * e.radius, y=e.y + uy * e.radius, ux=ux, uy=uy)
        self.projectiles.append(p)

    def spawn_hazard(self, e, kind):
        c, r = self.geo.cell_of(e.x, e.y)
        self.hazards.append(dict(kind=kind, owner=e, x=e.x, y=e.y, col=c, row=r,
                                 warn=HAZARD_WARN, active=HAZARD_ACTIVE, hit=False))

    # ---- update
    def update(self, player):
        if self.chase_enabled:
            self.chase_timer -= DT
            if self.chase_timer <= 0:
                self.chase_timer = self.chase_delay
                if sum(1 for e in self.enemies if e.kind == 0) < MAX_CHASERS:
                    self.spawn_chaser()

        for e in self.enemies:
            e.update(self, player)
        self._separate()
        self._update_player_projectiles(player)
        self._player_sword(player)

        for e in self.enemies:                       # touching an enemy hurts (enemy stays alive)
            if e.hp > 0 and hypot(player.x - e.x, player.y - e.y) < e.radius + player.size * 0.5:
                player.hurt(1, e.x, e.y)

        self._update_projectiles(player)
        self._update_hazards(player)

        alive = []
        for e in self.enemies:
            if e.hp > 0:
                alive.append(e)
            elif e.dead and e.death_timer <= 0:
                self.kills += 1
            else:
                alive.append(e)
        self.enemies = alive

    def _separate(self):
        es = self.enemies
        for i in range(len(es)):
            a = es[i]
            for j in range(i + 1, len(es)):
                b = es[j]
                dx, dy = b.x - a.x, b.y - a.y
                d = hypot(dx, dy)
                min_d = (a.radius + b.radius) * 0.9
                if d < min_d:
                    if d < 0.01:
                        dx, dy, d = random.uniform(-1, 1), random.uniform(-1, 1), 1.0
                    push = (min_d - d) * 0.25
                    a.move(-dx / d * push, -dy / d * push)
                    b.move(dx / d * push, dy / d * push)

    def _player_sword(self, player):
        if player.swing_t <= 0 and player.circle_timer <= 0:
            return

        sword_dmg = 1.5 if player.hp == 1 else 1
        circle_dmg = 3 if player.hp == 1 else 2

        if player.circle_timer > 0:
            for e in self.enemies:
                if e.hp <= 0 or id(e) in player.swing_hits:
                    continue
                dx, dy = e.x - player.x, e.y - player.y
                d = hypot(dx, dy)
                if d <= player.circle_radius + e.radius:
                    player.swing_hits.add(id(e))
                    if e.take_hit(circle_dmg, player.x, player.y):
                        player.add_heal(1)
            return

        ux, uy = player.swing_dir
        reach = player.sword_reach(self.cell)
        for e in self.enemies:
            if e.hp <= 0 or id(e) in player.swing_hits:
                continue
            dx, dy = e.x - player.x, e.y - player.y
            d = hypot(dx, dy)
            inside = d <= e.radius + player.size * 0.5
            in_sector = d <= reach + e.radius and (dx * ux + dy * uy) / max(d, 1e-6) >= 0.5
            if (inside or in_sector) and (inside or self.geo.line_clear(player.x, player.y, e.x, e.y)):
                player.swing_hits.add(id(e))
                if e.take_hit(sword_dmg, player.x, player.y):
                    player.add_heal(1)

    def _update_player_projectiles(self, player):
        for shot in player.projectile_queue:
            self.player_projectiles.append(dict(
                x=shot['x'],
                y=shot['y'],
                ux=shot['ux'],
                uy=shot['uy'],
                vx=shot['vx'],
                vy=shot['vy'],
                speed=shot['speed'],
                life=shot['life'],
                width=shot['width'],
                radius=shot['radius'],
                damage=shot['damage']))
        player.projectile_queue.clear()

        keep = []
        for p in self.player_projectiles:
            p['life'] -= DT
            if p['life'] <= 0:
                continue
            p['x'] += p['vx'] * DT
            p['y'] += p['vy'] * DT

            for e in self.enemies:
                if e.hp <= 0:
                    continue
                dist = hypot(e.x - p['x'], e.y - p['y'])
                if dist <= p['width'] * 0.25 + e.radius:
                    e.take_hit(p['damage'], p['x'], p['y'])
                    break
            keep.append(p)
        self.player_projectiles = keep

    def _update_projectiles(self, player):
        keep = []
        g = self.geo
        for p in self.projectiles:
            n = int(p['speed'] // max(1.0, g.margin)) + 1
            sub = p['speed'] / n
            alive = True
            for _ in range(n):
                p['x'] += p['ux'] * sub
                p['y'] += p['uy'] * sub
                p['left'] -= sub
                if p['left'] <= 0 or g.point_in_wall(p['x'], p['y']):
                    alive = False
                    break
                if (hypot(player.x - p['x'], player.y - p['y']) <= p['r'] + player.size * 0.5
                        and g.line_clear(p['x'], p['y'], player.x, player.y)):
                    if player.hurt(1, p['x'], p['y']):
                        alive = False
                        break
            if alive:
                keep.append(p)
        self.projectiles = keep

    def _update_hazards(self, player):
        keep = []
        for h in self.hazards:
            if h['warn'] > 0:
                if h['owner'].hp <= 0:               # killed during the wind-up -> attack cancelled
                    continue
                h['warn'] -= DT
                keep.append(h)
                continue
            if not h.get('sfx'):                     # the hazard just went live
                h['sfx'] = True
                vol = audio.falloff(hypot(player.x - h['x'], player.y - h['y']), self.cell * 10)
                audio.play('enemy_hazard', vol)
            if not h['hit']:
                if h['kind'] == 'aoe':
                    inside = hypot(player.x - h['x'], player.y - h['y']) <= AOE_RADIUS_CELLS * self.cell
                else:
                    pc, pr = int(player.x // self.cell), int(player.y // self.cell)
                    inside = pc == h['col'] or pr == h['row']
                if inside and player.hurt(1, h['x'], h['y']):
                    h['hit'] = True
            h['active'] -= DT
            if h['active'] > 0:
                keep.append(h)
        self.hazards = keep

    # ---- drawing
    def draw(self, cam_x, cam_y, w, h, player=None):
        cell = self.cell
        low_hp = player is not None and player.hp <= 1
        for hz in self.hazards:
            warming = hz['warn'] > 0
            p = 1 - max(hz['warn'], 0) / HAZARD_WARN
            alpha = int(35 + 55 * p) if warming else 150
            color = (255, 90, 60) if warming else (255, 40, 20)
            if hz['kind'] == 'aoe':
                cx, cy = hz['x'] - cam_x, hz['y'] - cam_y
                rad = AOE_RADIUS_CELLS * cell
                alpha_circle(cx, cy, rad, color, alpha)
                pgdraw.circle(_scr(), (255, 120, 90), (int(cx), int(cy)), int(rad), 3)
            else:
                alpha_rect(hz['col'] * cell - cam_x, -cam_y, cell, self.geo.H, color, alpha)
                alpha_rect(-cam_x, hz['row'] * cell - cam_y, self.geo.W, cell, color, alpha)
        for e in self.enemies:
            e.draw(cam_x, cam_y, w, h)
        for p in self.player_projectiles:
            sx, sy = int(p['x'] - cam_x), int(p['y'] - cam_y)
            rad = max(4, int(p['width'] * 0.18))
            
            size = rad * 2 + 4
            proj_surf = Surface((size, size), SRCALPHA)
            
            col = (220, 80, 80) if low_hp else (120, 180, 255)
            
            pgdraw.circle(proj_surf, (*col, 150), (size // 2, size // 2), rad)
            _scr().blit(proj_surf, (sx - size // 2, sy - size // 2))
        for p in self.projectiles:
            sx, sy = p['x'] - cam_x, p['y'] - cam_y
            if p['kind'] == 'acid':
                alpha_circle(sx, sy, p['r'], (90, 230, 60), 190)
                pgdraw.circle(_scr(), (40, 150, 20), (int(sx), int(sy)), int(p['r']), 3)
            else:
                tx, ty = sx - p['ux'] * p['length'], sy - p['uy'] * p['length']
                pgdraw.line(_scr(), (230, 200, 140), (int(tx), int(ty)), (int(sx), int(sy)), 4)
                drawCircle((255, 255, 255), int(sx), int(sy), 4)
