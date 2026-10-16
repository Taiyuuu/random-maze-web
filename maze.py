"""Maze grid, generation, and pathfinding."""
from collections import deque
import random

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
            if not n: return "n"
            if not e: return "e"
            if not s: return "s"
            if not w_wall: return "w"
        elif wall_count == 2:
            if not n and not s: return "ns"
            if not e and not w_wall: return "we"
            if not n and not e: return "ne"
            if not e and not s: return "se"
            if not s and not w_wall: return "sw"
            if not w_wall and not n: return "nw"
        elif wall_count == 1:
            if n: return "3_n"
            if e: return "3_e"
            if s: return "3_s"
            if w_wall: return "3_w"
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

    def to_dict(self):
        """Return the maze layout in a JSON-serializable format."""
        return {
            "format_version": 1,
            "cols": self.cols,
            "rows": self.rows,
            "walls": [
                [dict(self.grid[c][r].walls) for r in range(self.rows)]
                for c in range(self.cols)
            ],
        }

    @classmethod
    def from_dict(cls, data):
        """Rebuild a maze from saved wall data without generating a new layout."""
        cols = data.get("cols")
        rows = data.get("rows")
        saved_walls = data.get("walls")
        if (not isinstance(cols, int) or isinstance(cols, bool) or cols < 1
                or not isinstance(rows, int) or isinstance(rows, bool) or rows < 1):
            raise ValueError("Saved maze has invalid dimensions.")
        if not isinstance(saved_walls, list) or len(saved_walls) != cols:
            raise ValueError("Saved maze has an invalid wall grid.")

        maze = cls.__new__(cls)
        maze.cols = cols
        maze.rows = rows
        maze.grid = [[Cell(c, r) for r in range(rows)] for c in range(cols)]
        maze.shortest_path = set()

        required_walls = {"N", "E", "S", "W"}
        for c in range(cols):
            if not isinstance(saved_walls[c], list) or len(saved_walls[c]) != rows:
                raise ValueError("Saved maze has an invalid wall grid.")
            for r in range(rows):
                walls = saved_walls[c][r]
                if not isinstance(walls, dict) or set(walls) != required_walls:
                    raise ValueError("Saved maze contains invalid cell data.")
                if not all(isinstance(walls[key], bool) for key in required_walls):
                    raise ValueError("Saved maze contains invalid wall values.")
                maze.grid[c][r].walls = dict(walls)

        # Validate that adjacent cells agree about shared walls.
        for c in range(cols):
            for r in range(rows):
                cell = maze.grid[c][r]
                if c + 1 < cols and cell.walls["E"] != maze.grid[c + 1][r].walls["W"]:
                    raise ValueError("Saved maze has mismatched adjacent walls.")
                if r + 1 < rows and cell.walls["S"] != maze.grid[c][r + 1].walls["N"]:
                    raise ValueError("Saved maze has mismatched adjacent walls.")

        maze.find_shortest_path()
        if not maze.shortest_path:
            raise ValueError("Saved maze has no path from start to exit.")
        return maze

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

