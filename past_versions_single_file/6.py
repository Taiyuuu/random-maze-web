from mckPy import *
from collections import deque
import os
import random
import time

# Own main-loop helper (mckPy's running() hard-quits on ESC, which made it
# impossible to use ESC as "back to menu"). Closing the window still exits.
def app_running():
    display.flip()
    myClock.tick(60)
    clicked[:] = [False] * 5
    for evnt in event.get():
        if evnt.type == QUIT:
            return False
        if evnt.type == MOUSEBUTTONDOWN and evnt.button <= 5:
            clicked[evnt.button - 1] = True
    return True

# Initialize window size
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
resize(WINDOW_WIDTH, WINDOW_HEIGHT)

# Game State Management
# States: "MENU", "OPTIONS", "GAME"
game_state = "MENU"

# Basic Grid / Cell Settings
grid_cols = 14
grid_rows = 14
cell_size = 160  # Default cell display size in pixels

# Gameplay Options Settings
opt_limited_vis = True
opt_vis_radius = 3  # Radius in cells
opt_realistic_vis = False  # Walls block line of sight (needs limited visibility)

opt_enemy_enabled = False
opt_enemy_delay = 5  # Seconds before spawn

opt_keys_enabled = False
opt_key_count = 3  # Number of keys to collect

opt_player_speed = 10

# Runtime Variables
start_time = 0
elapsed_time = 0
game_won = False
game_over = False
player_hp = 3

keys_collected = 0
key_positions = []  # List of (col, row)

enemy_spawned = False
enemy_x = 0
enemy_y = 0
enemy_path = []
last_enemy_path_update = 0

# Asset Cache
loaded_tiles = {}
TILE_NAMES = ["grass", "dirt", "4", "n", "e", "s", "w", "ns", "we",
              "ne", "nw", "se", "sw", "3_n", "3_e", "3_s", "3_w"]

def draw_wall_shadows(maze, light_wx, light_wy, light_sx, light_sy, cam_x, cam_y, reach_px, radius_px):
    """Realistic visibility: everything hidden behind walls (as seen from the
    light) is covered with black. Each wall run on a cell border casts a
    shadow quad away from the light."""
    cs = cell_size
    rng = int(reach_px // cs) + 2
    pc, pr = int(light_wx // cs), int(light_wy // cs)
    c0, c1 = max(0, pc - rng), min(maze.cols, pc + rng + 1)   # cells [c0, c1)
    r0, r1 = max(0, pr - rng), min(maze.rows, pr + rng + 1)
    grid = maze.grid

    def wall_h(c, rl):   # wall on horizontal grid line rl above/below column c
        return (rl < maze.rows and grid[c][rl].walls['N']) or \
               (rl > 0 and grid[c][rl - 1].walls['S'])

    def wall_v(cl, r):   # wall on vertical grid line cl left/right of row r
        return (cl < maze.cols and grid[cl][r].walls['W']) or \
               (cl > 0 and grid[cl - 1][r].walls['E'])

    segs = []
    for rl in range(r0, r1 + 1):                 # merge horizontal runs
        start = None
        for c in range(c0, c1 + 1):
            w = c < c1 and wall_h(c, rl)
            if w and start is None:
                start = c
            elif not w and start is not None:
                segs.append((start * cs, rl * cs, c * cs, rl * cs))
                start = None
    for cl in range(c0, c1 + 1):                 # merge vertical runs
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
        # walls entirely outside the visibility radius cannot affect anything we see
        nx = min(max(light_wx, min(x1, x2)), max(x1, x2))
        ny = min(max(light_wy, min(y1, y2)), max(y1, y2))
        if sqrt((nx - light_wx) ** 2 + (ny - light_wy) ** 2) > radius_px:
            continue
        # extend slightly so neighbouring shadows overlap (no hairline gaps)
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
    """Radial gradient: clear near the centre, smoothly fading to black at radius_px."""
    global fog_cache_key, fog_cache_surf
    if radius_px > 1500:      # fog would be practically invisible on screen
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
        a = int(255 * s * s * (3 - 2 * s))   # smoothstep
        draw.circle(base, (0, 0, 0, a), (base_r, base_r), i)
    fog_cache_surf = transform.smoothscale(base, (radius_px * 2, radius_px * 2))
    fog_cache_key = radius_px
    return fog_cache_surf

def get_tile_image(tile_name, target_size):
    cache_key = (tile_name, target_size)
    if cache_key in loaded_tiles:
        return loaded_tiles[cache_key]
    
    path = os.path.join("tiles", f"{tile_name}.png")
    
    try:
        raw_img = image.load(path).convert_alpha()
        img = transform.smoothscale(raw_img, (int(target_size), int(target_size)))
    except Exception:
        raw_img = loadImage(path)
        img = transform.scale(raw_img, (int(target_size), int(target_size)))
        
    loaded_tiles[cache_key] = img
    return img

class Cell:
    def __init__(self, col, row):
        self.col = col
        self.row = row
        self.walls = {'N': True, 'E': True, 'S': True, 'W': True}
        self.visited = False

    def get_tile_type(self):
        w = self.walls
        n, e, s, w_wall = w['N'], w['E'], w['S'], w['W']
        wall_count = sum([n, e, s, w_wall])

        if wall_count == 4:
            return "grass"
        elif wall_count == 3:
            if not n: return "s"
            if not e: return "w"
            if not s: return "n"
            if not w_wall: return "e"
        elif wall_count == 2:
            if not n and not s: return "ns"
            if not e and not w_wall: return "we"
            if not n and not e: return "sw"
            if not e and not s: return "nw"
            if not s and not w_wall: return "ne"
            if not w_wall and not n: return "se"
        elif wall_count == 1:
            if n: return "3_s"
            if e: return "3_w"
            if s: return "3_n"
            if w_wall: return "3_e"
        elif wall_count == 0:
            return "4"
        return "dirt"

class Maze:
    def __init__(self, cols, rows):
        self.cols = cols
        self.rows = rows
        self.grid = [[Cell(c, r) for r in range(rows)] for c in range(cols)]
        self.shortest_path = set()
        self.generate_maze()

    def get_cell(self, col, row):
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[col][row]
        return None

    def generate_maze(self):
        stack = []
        
        exit_cell = self.grid[self.cols - 1][self.rows - 1]
        exit_cell.visited = True

        start_cell = self.grid[0][0]
        start_cell.visited = True
        stack.append(start_cell)

        while stack:
            current = stack[-1]
            neighbors = []

            nc = self.get_cell(current.col, current.row - 1)
            if nc and not nc.visited: neighbors.append(('N', nc))
            ec = self.get_cell(current.col + 1, current.row)
            if ec and not ec.visited: neighbors.append(('E', ec))
            sc = self.get_cell(current.col, current.row + 1)
            if sc and not sc.visited: neighbors.append(('S', sc))
            wc = self.get_cell(current.col - 1, current.row)
            if wc and not wc.visited: neighbors.append(('W', wc))

            if neighbors:
                direction, next_cell = random.choice(neighbors)
                if direction == 'N':
                    current.walls['N'] = False
                    next_cell.walls['S'] = False
                elif direction == 'E':
                    current.walls['E'] = False
                    next_cell.walls['W'] = False
                elif direction == 'S':
                    current.walls['S'] = False
                    next_cell.walls['N'] = False
                elif direction == 'W':
                    current.walls['W'] = False
                    next_cell.walls['E'] = False

                next_cell.visited = True
                stack.append(next_cell)
            else:
                stack.pop()

        if self.cols > 1:
            exit_cell.walls['W'] = False
            self.grid[self.cols - 2][self.rows - 1].walls['E'] = False
        elif self.rows > 1:
            exit_cell.walls['N'] = False
            self.grid[self.cols - 1][self.rows - 2].walls['S'] = False

        self.grid[0][0].walls['N'] = False
        exit_cell.walls['S'] = False

        self.find_shortest_path()

    def find_shortest_path(self):
        """BFS to find the shortest path from start (0,0) to exit (cols-1, rows-1)."""
        queue = deque([((0, 0), [(0, 0)])])
        visited = {(0, 0)}

        while queue:
            (c, r), path = queue.popleft()
            if c == self.cols - 1 and r == self.rows - 1:
                self.shortest_path = set(path)
                return

            cell = self.grid[c][r]
            dirs = [('N', 0, -1), ('E', 1, 0), ('S', 0, 1), ('W', -1, 0)]
            for wall, dc, dr in dirs:
                if not cell.walls[wall]:
                    nc, nr = c + dc, r + dr
                    if 0 <= nc < self.cols and 0 <= nr < self.rows and (nc, nr) not in visited:
                        visited.add((nc, nr))
                        queue.append(((nc, nr), path + [(nc, nr)]))

    def get_bfs_path(self, start_pos, target_pos):
        """Pathfinding algorithm used by chasing enemy."""
        sc, sr = start_pos
        tc, tr = target_pos
        if (sc, sr) == (tc, tr):
            return []

        queue = deque([((sc, sr), [])])
        visited = {(sc, sr)}

        while queue:
            (c, r), path = queue.popleft()
            if (c, r) == (tc, tr):
                return path

            cell = self.grid[c][r]
            dirs = [('N', 0, -1), ('E', 1, 0), ('S', 0, 1), ('W', -1, 0)]
            for wall, dc, dr in dirs:
                if not cell.walls[wall]:
                    nc, nr = c + dc, r + dr
                    if 0 <= nc < self.cols and 0 <= nr < self.rows and (nc, nr) not in visited:
                        visited.add((nc, nr))
                        queue.append(((nc, nr), path + [(nc, nr)]))
        return []

class Player:
    def __init__(self, x, y, size):
        self.x = x
        self.y = y
        self.size = size
        self.speed = opt_player_speed
        self.off_x = 0.0
        self.off_y = 0.0

    def update(self, maze, tile_px):
        dx, dy = 0, 0
        if upKey(): dy -= self.speed
        if downKey(): dy += self.speed
        if leftKey(): dx -= self.speed
        if rightKey(): dx += self.speed

        grass_ratio = 78.0 / 512.0
        grass_margin = tile_px * grass_ratio

        if dx != 0:
            new_x = self.x + dx
            if not self.check_collision(new_x, self.y, maze, tile_px, grass_margin):
                self.x = new_x

        if dy != 0:
            new_y = self.y + dy
            if not self.check_collision(self.x, new_y, maze, tile_px, grass_margin):
                self.y = new_y

    def check_collision(self, px, py, maze, tile_px, margin):
        player_rect = Rect(px - self.size // 2, py - self.size // 2, self.size, self.size)
        maze_w = maze.cols * tile_px
        maze_h = maze.rows * tile_px

        exit_min_x = (maze.cols - 1) * tile_px + margin
        exit_max_x = maze.cols * tile_px - margin

        # Check if exit is unlocked
        can_exit = (not opt_keys_enabled) or (keys_collected >= opt_key_count)
        half = self.size // 2
        is_exiting = (can_exit
                      and (py + half > maze_h - margin)
                      and (exit_min_x <= px - half)
                      and (px + half <= exit_max_x))

        if not is_exiting:
            if px - self.size // 2 < margin or px + self.size // 2 > maze_w - margin:
                return True
            if py - self.size // 2 < margin or py + self.size // 2 > maze_h - margin:
                return True

        min_c = max(0, int(px // tile_px) - 1)
        max_c = min(maze.cols - 1, int(px // tile_px) + 1)
        min_r = max(0, int(py // tile_px) - 1)
        max_r = min(maze.rows - 1, int(py // tile_px) + 1)

        for c in range(min_c, max_c + 1):
            for r in range(min_r, max_r + 1):
                cell = maze.grid[c][r]
                x_off = c * tile_px
                y_off = r * tile_px

                walls_to_check = []

                if cell.walls['N']:
                    walls_to_check.append(Rect(x_off, y_off, tile_px, margin))
                if cell.walls['S']:
                    # Re-block south exit if keys are missing
                    if not (c == maze.cols - 1 and r == maze.rows - 1 and can_exit):
                        walls_to_check.append(Rect(x_off, y_off + tile_px - margin, tile_px, margin))
                if cell.walls['W']:
                    walls_to_check.append(Rect(x_off, y_off, margin, tile_px))
                if cell.walls['E']:
                    walls_to_check.append(Rect(x_off + tile_px - margin, y_off, margin, tile_px))

                for w_rect in walls_to_check:
                    if player_rect.colliderect(w_rect):
                        return True

        return False

    def draw(self, cam_x, cam_y):
        screen_x = int(round(self.x - cam_x + self.off_x))
        screen_y = int(round(self.y - cam_y + self.off_y))
        drawCircle("red", screen_x, screen_y, self.size // 2)

# Global Game Variables
maze = None
player = None

def init_game():
    global maze, player, start_time, elapsed_time, game_won, game_over
    global keys_collected, key_positions, enemy_spawned, enemy_x, enemy_y, player_hp
    
    maze = Maze(grid_cols, grid_rows)
    for name in TILE_NAMES:           # preload so nothing loads mid-game
        get_tile_image(name, cell_size)
    start_x = cell_size / 2
    start_y = cell_size / 2
    player_size = int(cell_size * 0.2)
    player = Player(start_x, start_y, max(12, player_size))
    
    start_time = time.time()
    elapsed_time = 0
    game_won = False
    game_over = False
    player_hp = 3

    # Key Placement (excluding shortest path)
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

    # Chasing Enemy Setup
    enemy_spawned = False
    enemy_x = cell_size / 2
    enemy_y = cell_size / 2

# UI Helpers
def draw_button(text, x, y, w, h, bg_color="gray", txt_color="black"):
    hover = overRect(x, y, w, h)
    color = "lightgray" if hover else bg_color
    drawRect(color, x, y, w, h, corner=10)
    drawRect("black", x, y, w, h, t=2, corner=10)
    drawText(txt_color, text, x + w // 2 - len(text) * 5, y + h // 2 - 10, font=("Helvetica", 20))
    return clickOnRect(x, y, w, h)

def draw_toggle_button(text, state, x, y, w, h):
    color = "darkgreen" if state else "darkred"
    label = f"{text}: {'ON' if state else 'OFF'}"
    drawRect(color, x, y, w, h, corner=10)
    drawRect("black", x, y, w, h, t=2, corner=10)
    drawText("white", label, x + 15, y + h // 2 - 10, font=("Helvetica", 18))
    return clickOnRect(x, y, w, h)

# Main Game Loop
esc_prev = True   # ignore ESC held at startup
quit_requested = False
while app_running():
    fill((30, 30, 40))
    esc_down = keyPressed(K_ESCAPE)
    esc_just = esc_down and not esc_prev
    esc_prev = esc_down

    if game_state == "MENU":
        drawText("white", "MAZE GENERATOR", 250, 100, font=("Helvetica", 40))

        if draw_button("START GAME", 300, 220, 200, 50):
            init_game()
            game_state = "GAME"

        if draw_button("OPTIONS", 300, 300, 200, 50):
            game_state = "OPTIONS"

        if draw_button("QUIT", 300, 380, 200, 50) or esc_just:
            break

    elif game_state == "OPTIONS":
        drawText("white", "GAME OPTIONS", 280, 40, font=("Helvetica", 32))

        # Size Settings
        drawText("white", f"Cols: {grid_cols}", 50, 110)
        if draw_button("-", 150, 100, 35, 35): grid_cols = max(3, grid_cols - 1)
        if draw_button("+", 195, 100, 35, 35): grid_cols = min(50, grid_cols + 1)

        drawText("white", f"Rows: {grid_rows}", 250, 110)
        if draw_button("-", 350, 100, 35, 35): grid_rows = max(3, grid_rows - 1)
        if draw_button("+", 395, 100, 35, 35): grid_rows = min(50, grid_rows + 1)

        drawText("white", f"Tile: {cell_size}px", 450, 110)
        if draw_button("-", 580, 100, 35, 35): cell_size = max(20, cell_size - 10)
        if draw_button("+", 625, 100, 35, 35): cell_size = min(500, cell_size + 10)

        # 1. Limited Visibility
        if draw_toggle_button("Fog Vision", opt_limited_vis, 50, 170, 250, 40):
            opt_limited_vis = not opt_limited_vis
        drawText("white", f"Radius: {opt_vis_radius}", 320, 180)
        if draw_button("-", 450, 170, 35, 35): opt_vis_radius = max(1, opt_vis_radius - 1)
        if draw_button("+", 495, 170, 35, 35): opt_vis_radius = min(15, opt_vis_radius + 1)

        # 1b. Realistic Visibility (only usable together with Fog Vision)
        if opt_limited_vis:
            if draw_toggle_button("Realistic Vis", opt_realistic_vis, 50, 220, 250, 40):
                opt_realistic_vis = not opt_realistic_vis
        else:
            drawRect((70, 70, 70), 50, 220, 250, 40, corner=10)
            drawRect("black", 50, 220, 250, 40, t=2, corner=10)
            drawText((150, 150, 150), "Realistic Vis: needs Fog", 65, 230, font=("Helvetica", 18))

        # 2. Chasing Enemy
        if draw_toggle_button("Chasing Enemy", opt_enemy_enabled, 50, 280, 250, 40):
            opt_enemy_enabled = not opt_enemy_enabled
        drawText("white", f"Delay: {opt_enemy_delay}s", 320, 290)
        if draw_button("-", 450, 280, 35, 35): opt_enemy_delay = max(1, opt_enemy_delay - 1)
        if draw_button("+", 495, 280, 35, 35): opt_enemy_delay = min(60, opt_enemy_delay + 1)

        # 3. Collect Keys
        if draw_toggle_button("Find Keys", opt_keys_enabled, 50, 340, 250, 40):
            opt_keys_enabled = not opt_keys_enabled
        drawText("white", f"Keys: {opt_key_count}", 320, 350)
        if draw_button("-", 450, 340, 35, 35): opt_key_count = max(1, opt_key_count - 1)
        if draw_button("+", 495, 340, 35, 35): opt_key_count = min(15, opt_key_count + 1)

        drawText("white", f"Player Speed: {opt_player_speed}", 50, 405)
        if draw_button("-", 320, 395, 35, 35):
            opt_player_speed = max(1, opt_player_speed - 1)
        if draw_button("+", 365, 395, 35, 35):
            opt_player_speed = min(15, opt_player_speed + 1)

        if draw_button("BACK TO MENU", 300, 480, 200, 50) or esc_just:
            game_state = "MENU"

    elif game_state == "GAME":
        if not game_won and not game_over:
            player.update(maze, cell_size)
            elapsed_time = time.time() - start_time

            # Key Pickup Check
            if opt_keys_enabled:
                p_cell = (int(player.x // cell_size), int(player.y // cell_size))
                if p_cell in key_positions:
                    key_positions.remove(p_cell)
                    keys_collected += 1

            # Enemy Spawn & Movement
            if opt_enemy_enabled:
                if not enemy_spawned and elapsed_time >= opt_enemy_delay:
                    enemy_spawned = True
                    enemy_x = cell_size / 2
                    enemy_y = cell_size / 2

                if enemy_spawned:
                    p_cell = (int(player.x // cell_size), int(player.y // cell_size))
                    e_cell = (int(enemy_x // cell_size), int(enemy_y // cell_size))

                    if time.time() - last_enemy_path_update > 0.2:
                        enemy_path = maze.get_bfs_path(e_cell, p_cell)
                        last_enemy_path_update = time.time()

                    # Move enemy toward next node along path at player's speed
                    if enemy_path:
                        next_c, next_r = enemy_path[0]
                        target_x = next_c * cell_size + cell_size / 2
                        target_y = next_r * cell_size + cell_size / 2

                        edx = target_x - enemy_x
                        edy = target_y - enemy_y
                        dist = sqrt(edx**2 + edy**2)

                        if dist < player.speed:
                            enemy_x = target_x
                            enemy_y = target_y
                        else:
                            enemy_x += (edx / dist) * player.speed
                            enemy_y += (edy / dist) * player.speed

                    # Check collision with player
                    e_dist = sqrt((player.x - enemy_x)**2 + (player.y - enemy_y)**2)
                    if e_dist < (player.size / 2 + cell_size * 0.15):
                        player_hp -= 1
                        enemy_spawned = False
                        if player_hp <= 0:
                            game_over = True

            # Win Condition Check
            if player.y > (maze.rows * cell_size + player.size):
                game_won = True

        # Camera Tracking (integer camera avoids 1px seams between tiles)
        cam_x = int(round(player.x - WINDOW_WIDTH / 2))
        cam_y = int(round(player.y - WINDOW_HEIGHT / 2))

        # Draw every tile on screen; cells outside the maze are plain grass
        first_c = cam_x // cell_size
        last_c = (cam_x + WINDOW_WIDTH) // cell_size
        first_r = cam_y // cell_size
        last_r = (cam_y + WINDOW_HEIGHT) // cell_size
        for c in range(first_c, last_c + 1):
            for r in range(first_r, last_r + 1):
                if 0 <= c < maze.cols and 0 <= r < maze.rows:
                    tile_type = maze.grid[c][r].get_tile_type()
                else:
                    tile_type = "grass"
                drawImage(get_tile_image(tile_type, cell_size),
                          c * cell_size - cam_x, r * cell_size - cam_y)

        # Draw Collectible Keys
        if opt_keys_enabled:
            for kc, kr in key_positions:
                kx = kc * cell_size + cell_size / 2 - cam_x
                ky = kr * cell_size + cell_size / 2 - cam_y
                drawCircle("yellow", int(kx), int(ky), int(cell_size * 0.15))

        # Draw Chasing Enemy
        if opt_enemy_enabled and enemy_spawned:
            ex = int(enemy_x - cam_x)
            ey = int(enemy_y - cam_y)
            drawCircle("purple", ex, ey, int(cell_size * 0.2))

        # Realistic visibility: hide everything behind walls
        if opt_limited_vis and opt_realistic_vis:
            draw_wall_shadows(
                maze, player.x + player.off_x, player.y + player.off_y,
                int(round(player.x - cam_x + player.off_x)),
                int(round(player.y - cam_y + player.off_y)),
                cam_x, cam_y, min(opt_vis_radius * cell_size, 520),
                opt_vis_radius * cell_size)

        player.draw(cam_x, cam_y)

        # Fog: smooth brightness falloff around the player
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

        # HUD Panel
        drawRect((0, 0, 0), 10, 10, 220, 125, alpha=180)
        drawText("white", f"TIME: {elapsed_time:.1f}s", 20, 20, font=("Helvetica", 18))
        if opt_enemy_enabled:
            drawText("red", f"HP: {'♥' * player_hp}", 20, 45, font=("Helvetica", 18))
        if opt_keys_enabled:
            drawText("yellow", f"KEYS: {keys_collected}/{opt_key_count}", 20, 70, font=("Helvetica", 18))

        drawText("lightgray", "ESC: back to menu", 20, 105, font=("Helvetica", 14))

        # Minimap: maze rectangle + player dot (bottom-right)
        mm_scale = min(140 / maze.cols, 140 / maze.rows)
        mm_w, mm_h = int(maze.cols * mm_scale), int(maze.rows * mm_scale)
        mm_x, mm_y = WINDOW_WIDTH - 15 - mm_w, WINDOW_HEIGHT - 15 - mm_h
        drawRect("white", mm_x, mm_y, mm_w, mm_h, t=2)
        fx = min(max(player.x / (maze.cols * cell_size), 0), 1)
        fy = min(max(player.y / (maze.rows * cell_size), 0), 1)
        drawCircle("red", int(mm_x + fx * mm_w), int(mm_y + fy * mm_h), 4)

        # Victory Screen Overlay
        if game_won:
            drawRect((0, 0, 0), 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, alpha=180)
            drawText("yellow", "MAZE COMPLETED!", 220, 180, font=("Helvetica", 36))
            drawText("white", f"Final Time: {elapsed_time:.2f}s", 270, 250, font=("Helvetica", 24))

            if draw_button("PLAY AGAIN", 130, 330, 170, 45): init_game()
            if draw_button("MAIN MENU", 315, 330, 170, 45): game_state = "MENU"
            if draw_button("QUIT", 500, 330, 170, 45): quit_requested = True

        # Game Over Overlay
        elif game_over:
            drawRect((0, 0, 0), 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, alpha=200)
            drawText("red", "GAME OVER!", 280, 180, font=("Helvetica", 38))

            if draw_button("RETRY", 130, 330, 170, 45): init_game()
            if draw_button("MAIN MENU", 315, 330, 170, 45): game_state = "MENU"
            if draw_button("QUIT", 500, 330, 170, 45): quit_requested = True

        # Return to Menu
        if esc_just:
            game_state = "MENU"
        if quit_requested:
            break

quit()