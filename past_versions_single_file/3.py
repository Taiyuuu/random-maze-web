from mckPy import *
import os
import random
import time
from collections import deque

# Initialize window size
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
resize(WINDOW_WIDTH, WINDOW_HEIGHT)

# Game State Management
# States: "MENU", "OPTIONS", "GAME"
game_state = "MENU"

# Basic Grid / Cell Settings
grid_cols = 10
grid_rows = 10
cell_size = 60  # Default cell display size in pixels

# Gameplay Options Settings
opt_limited_vis = False
opt_vis_radius = 3  # Radius in cells

opt_enemy_enabled = False
opt_enemy_delay = 5  # Seconds before spawn

opt_keys_enabled = False
opt_key_count = 3  # Number of keys to collect

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
        self.speed = 4

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
        is_exiting = can_exit and (py > maze_h - margin) and (exit_min_x <= px <= exit_max_x)

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
        screen_x = int(self.x - cam_x)
        screen_y = int(self.y - cam_y)
        drawCircle("red", screen_x, screen_y, self.size // 2)

# Global Game Variables
maze = None
player = None

def init_game():
    global maze, player, start_time, elapsed_time, game_won, game_over
    global keys_collected, key_positions, enemy_spawned, enemy_x, enemy_y, player_hp
    
    maze = Maze(grid_cols, grid_rows)
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
while running():
    fill((30, 30, 40))

    if game_state == "MENU":
        drawText("white", "MAZE GENERATOR", 250, 100, font=("Helvetica", 40))

        if draw_button("START GAME", 300, 220, 200, 50):
            init_game()
            game_state = "GAME"

        if draw_button("OPTIONS", 300, 300, 200, 50):
            game_state = "OPTIONS"

        if draw_button("QUIT", 300, 380, 200, 50):
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

        # 2. Chasing Enemy
        if draw_toggle_button("Chasing Enemy", opt_enemy_enabled, 50, 230, 250, 40):
            opt_enemy_enabled = not opt_enemy_enabled
        drawText("white", f"Delay: {opt_enemy_delay}s", 320, 240)
        if draw_button("-", 450, 230, 35, 35): opt_enemy_delay = max(1, opt_enemy_delay - 1)
        if draw_button("+", 495, 230, 35, 35): opt_enemy_delay = min(60, opt_enemy_delay + 1)

        # 3. Collect Keys
        if draw_toggle_button("Find Keys", opt_keys_enabled, 50, 290, 250, 40):
            opt_keys_enabled = not opt_keys_enabled
        drawText("white", f"Keys: {opt_key_count}", 320, 300)
        if draw_button("-", 450, 290, 35, 35): opt_key_count = max(1, opt_key_count - 1)
        if draw_button("+", 495, 290, 35, 35): opt_key_count = min(15, opt_key_count + 1)

        if draw_button("BACK TO MENU", 300, 480, 200, 50):
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

        # Camera Tracking
        cam_x = player.x - WINDOW_WIDTH / 2
        cam_y = player.y - WINDOW_HEIGHT / 2

        player_cell_c = int(player.x // cell_size)
        player_cell_r = int(player.y // cell_size)

        # Draw Maze Tiles
        for c in range(maze.cols):
            for r in range(maze.rows):
                # Limited visibility distance check
                if opt_limited_vis:
                    cell_dist = sqrt((c - player_cell_c)**2 + (r - player_cell_r)**2)
                    if cell_dist > opt_vis_radius:
                        continue

                tile_x = c * cell_size - cam_x
                tile_y = r * cell_size - cam_y

                if -cell_size <= tile_x <= WINDOW_WIDTH and -cell_size <= tile_y <= WINDOW_HEIGHT:
                    cell = maze.grid[c][r]
                    tile_type = cell.get_tile_type()
                    img = get_tile_image(tile_type, cell_size)
                    drawImage(img, tile_x, tile_y)

        # Draw Collectible Keys
        if opt_keys_enabled:
            for kc, kr in key_positions:
                if opt_limited_vis:
                    if sqrt((kc - player_cell_c)**2 + (kr - player_cell_r)**2) > opt_vis_radius:
                        continue
                kx = kc * cell_size + cell_size / 2 - cam_x
                ky = kr * cell_size + cell_size / 2 - cam_y
                drawCircle("yellow", int(kx), int(ky), int(cell_size * 0.15))

        # Draw Chasing Enemy
        if opt_enemy_enabled and enemy_spawned:
            ex = int(enemy_x - cam_x)
            ey = int(enemy_y - cam_y)
            drawCircle("purple", ex, ey, int(cell_size * 0.2))

        player.draw(cam_x, cam_y)

        # Draw Darkness Vignette Overlay for Limited Vision
        if opt_limited_vis:
            vis_px = int(opt_vis_radius * cell_size)
            px_screen = int(player.x - cam_x)
            py_screen = int(player.y - cam_y)
            
            # Simple darkness ring
            drawCircle((0, 0, 0), px_screen, py_screen, vis_px + 200, t=200)

        # HUD Panel
        drawRect((0, 0, 0), 10, 10, 220, 110, alpha=180)
        drawText("white", f"TIME: {elapsed_time:.1f}s", 20, 20, font=("Helvetica", 18))
        if opt_enemy_enabled:
            drawText("red", f"HP: {'♥' * player_hp}", 20, 45, font=("Helvetica", 18))
        if opt_keys_enabled:
            drawText("yellow", f"KEYS: {keys_collected}/{opt_key_count}", 20, 70, font=("Helvetica", 18))

        # Victory Screen Overlay
        if game_won:
            drawRect((0, 0, 0), 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, alpha=180)
            drawText("yellow", "MAZE COMPLETED!", 220, 180, font=("Helvetica", 36))
            drawText("white", f"Final Time: {elapsed_time:.2f}s", 270, 250, font=("Helvetica", 24))

            if draw_button("PLAY AGAIN", 230, 330, 150, 45): init_game()
            if draw_button("MAIN MENU", 420, 330, 150, 45): game_state = "MENU"

        # Game Over Overlay
        elif game_over:
            drawRect((0, 0, 0), 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, alpha=200)
            drawText("red", "GAME OVER!", 280, 180, font=("Helvetica", 38))

            if draw_button("RETRY", 230, 330, 150, 45): init_game()
            if draw_button("MAIN MENU", 420, 330, 150, 45): game_state = "MENU"

        # Return to Menu
        if keyPressed(K_ESCAPE):
            game_state = "MENU"