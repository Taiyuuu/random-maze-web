from mckPy import *
import os
import random
import time

# Initialize window size
WINDOW_WIDTH = 800
WINDOW_HEIGHT = 600
resize(WINDOW_WIDTH, WINDOW_HEIGHT)

# Game State Management
# States: "MENU", "OPTIONS", "GAME"
game_state = "MENU"

# Grid / Options Parameters
grid_cols = 10
grid_rows = 10
cell_size = 60  # Default cell display size in pixels

# Timer & Victory State
start_time = 0
elapsed_time = 0
game_won = False

# Asset Cache
loaded_tiles = {}

def get_tile_image(tile_name, target_size):
    cache_key = (tile_name, target_size)
    if cache_key in loaded_tiles:
        return loaded_tiles[cache_key]
    
    path = os.path.join("tiles", f"{tile_name}.png")
    
    # Load raw image first
    try:
        raw_img = image.load(path).convert_alpha()
        img = transform.smoothscale(raw_img, (int(target_size), int(target_size)))
    except Exception:
        # Fallback using standard scale if smoothscale fails
        raw_img = loadImage(path)
        img = transform.scale(raw_img, (int(target_size), int(target_size)))
        
    loaded_tiles[cache_key] = img
    return img

class Cell:
    def __init__(self, col, row):
        self.col = col
        self.row = row
        # Walls: North, East, South, West
        self.walls = {'N': True, 'E': True, 'S': True, 'W': True}
        self.visited = False

    def get_tile_type(self):
        """Determines tile filename based on wall configuration."""
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
        self.generate_maze()

    def get_cell(self, col, row):
        if 0 <= col < self.cols and 0 <= row < self.rows:
            return self.grid[col][row]
        return None

    def generate_maze(self):
        """Generates a random maze using DFS depth-first search backtracker."""
        stack = []
        
        # Mark exit cell as visited so DFS doesn't turn it into a multi-branch junction
        exit_cell = self.grid[self.cols - 1][self.rows - 1]
        exit_cell.visited = True

        start_cell = self.grid[0][0]
        start_cell.visited = True
        stack.append(start_cell)

        while stack:
            current = stack[-1]
            neighbors = []

            # Check North
            nc = self.get_cell(current.col, current.row - 1)
            if nc and not nc.visited: neighbors.append(('N', nc))
            # Check East
            ec = self.get_cell(current.col + 1, current.row)
            if ec and not ec.visited: neighbors.append(('E', ec))
            # Check South
            sc = self.get_cell(current.col, current.row + 1)
            if sc and not sc.visited: neighbors.append(('S', sc))
            # Check West
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

        # Connect exit cell to exactly one neighbor (preferring West then North)
        if self.cols > 1:
            exit_cell.walls['W'] = False
            self.grid[self.cols - 2][self.rows - 1].walls['E'] = False
        elif self.rows > 1:
            exit_cell.walls['N'] = False
            self.grid[self.cols - 1][self.rows - 2].walls['S'] = False

        # Open entrance (Top-Left North Wall) and exit (Bottom-Right South Wall)
        self.grid[0][0].walls['N'] = False
        exit_cell.walls['S'] = False

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

        # Try Horizontal Movement
        if dx != 0:
            new_x = self.x + dx
            if not self.check_collision(new_x, self.y, maze, tile_px, grass_margin):
                self.x = new_x

        # Try Vertical Movement
        if dy != 0:
            new_y = self.y + dy
            if not self.check_collision(self.x, new_y, maze, tile_px, grass_margin):
                self.y = new_y

    def check_collision(self, px, py, maze, tile_px, margin):
        player_rect = Rect(px - self.size // 2, py - self.size // 2, self.size, self.size)
        maze_w = maze.cols * tile_px
        maze_h = maze.rows * tile_px

        # Exit opening position (Bottom-Right South wall)
        exit_min_x = (maze.cols - 1) * tile_px + margin
        exit_max_x = maze.cols * tile_px - margin

        # Allow passing downward through exit opening
        is_exiting = (py > maze_h - margin) and (exit_min_x <= px <= exit_max_x)

        if not is_exiting:
            # Outer boundary checks for top, left, right, and standard bottom edge
            if px - self.size // 2 < margin or px + self.size // 2 > maze_w - margin:
                return True
            if py - self.size // 2 < margin or py + self.size // 2 > maze_h - margin:
                return True

        # Check internal cell wall collisions
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
    global maze, player, start_time, elapsed_time, game_won
    maze = Maze(grid_cols, grid_rows)
    start_x = cell_size / 2
    start_y = cell_size / 2
    player_size = int(cell_size * 0.2)
    player = Player(start_x, start_y, max(12, player_size))
    start_time = time.time()
    elapsed_time = 0
    game_won = False

# UI Helpers
def draw_button(text, x, y, w, h, bg_color="gray", txt_color="black"):
    hover = overRect(x, y, w, h)
    color = "lightgray" if hover else bg_color
    drawRect(color, x, y, w, h, corner=10)
    drawRect("black", x, y, w, h, t=2, corner=10)
    drawText(txt_color, text, x + w // 2 - len(text) * 5, y + h // 2 - 10, font=("Helvetica", 22))
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
        drawText("white", "GAME OPTIONS", 280, 60, font=("Helvetica", 36))

        # Column Adjustment
        drawText("white", f"Columns: {grid_cols}", 250, 160)
        if draw_button("-", 450, 150, 40, 40):
            grid_cols = max(3, grid_cols - 1)
        if draw_button("+", 510, 150, 40, 40):
            grid_cols = min(50, grid_cols + 1)

        # Row Adjustment
        drawText("white", f"Rows: {grid_rows}", 250, 240)
        if draw_button("-", 450, 230, 40, 40):
            grid_rows = max(3, grid_rows - 1)
        if draw_button("+", 510, 230, 40, 40):
            grid_rows = min(50, grid_rows + 1)

        # Cell Size Adjustment
        drawText("white", f"Cell Size: {cell_size}px", 250, 320)
        if draw_button("-", 450, 310, 40, 40):
            cell_size = max(20, cell_size - 20)
        if draw_button("+", 510, 310, 40, 40):
            cell_size = min(500, cell_size + 20)

        if draw_button("BACK TO MENU", 300, 440, 200, 50):
            game_state = "MENU"

    elif game_state == "GAME":
        if not game_won:
            player.update(maze, cell_size)
            elapsed_time = time.time() - start_time

            # Win Condition: Player moves completely past the exit boundary
            if player.y > (maze.rows * cell_size + player.size):
                game_won = True

        # Camera Tracking
        cam_x = player.x - WINDOW_WIDTH / 2
        cam_y = player.y - WINDOW_HEIGHT / 2

        # Draw Visible Maze Tiles
        for c in range(maze.cols):
            for r in range(maze.rows):
                tile_x = c * cell_size - cam_x
                tile_y = r * cell_size - cam_y

                if -cell_size <= tile_x <= WINDOW_WIDTH and -cell_size <= tile_y <= WINDOW_HEIGHT:
                    cell = maze.grid[c][r]
                    tile_type = cell.get_tile_type()
                    img = get_tile_image(tile_type, cell_size)
                    drawImage(img, tile_x, tile_y)

        player.draw(cam_x, cam_y)

        # HUD Timer Box
        drawRect((0, 0, 0), 20, 20, 170, 40, alpha=180)
        drawText("white", f"TIME: {elapsed_time:.1f}s", 35, 30, font=("Helvetica", 20))

        # Victory Transparent Overlay Screen
        if game_won:
            # Semi-transparent dark overlay
            drawRect((0, 0, 0), 0, 0, WINDOW_WIDTH, WINDOW_HEIGHT, alpha=180)
            
            drawText("yellow", "MAZE COMPLETED!", 220, 180, font=("Helvetica", 36))
            drawText("white", f"Final Time: {elapsed_time:.2f} seconds", 270, 250, font=("Helvetica", 24))

            if draw_button("PLAY AGAIN", 230, 330, 150, 45):
                init_game()

            if draw_button("MAIN MENU", 420, 330, 150, 45):
                game_state = "MENU"

        # Return to Menu shortcut
        if keyPressed(K_ESCAPE):
            game_state = "MENU"