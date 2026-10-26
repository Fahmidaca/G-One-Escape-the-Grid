"""The maze: generation, walls, energy cores, the exit portal and firewalls."""
import random
from collections import deque

from settings import COLS, ROWS

DIRS = ((1, 0), (-1, 0), (0, 1), (0, -1))


class World:
    def __init__(self, level, rng=None):
        self.rng = rng or random.Random()
        self.level = level
        self.cols, self.rows = COLS, ROWS
        self.wall = [[True] * COLS for _ in range(ROWS)]   # wall[y][x]

        self._carve_maze()
        # Extra openings create loops, so you can run around Ra.One.
        # Higher levels have fewer loops, which makes escaping harder.
        self._add_loops(max(0.08, 0.20 - 0.025 * (level - 1)))

        self.player_start = (1, 1)
        self.raone_start = (COLS - 2, ROWS - 2)
        self.portal = (COLS - 2, 1)
        self.firewalls = {}            # cell -> seconds left
        self.cores = self._place_cores(min(3 + level, 8))

    # ---------- queries ----------
    def in_bounds(self, c):
        return 0 <= c[0] < self.cols and 0 <= c[1] < self.rows

    def is_wall(self, c):
        return not self.in_bounds(c) or self.wall[c[1]][c[0]]

    def passable(self, c):
        return not self.is_wall(c) and c not in self.firewalls

    def floor_cells(self):
        return [(x, y) for y in range(self.rows) for x in range(self.cols) if not self.wall[y][x]]

    def distances_from(self, start):
        """Breadth-first search distance to every reachable cell (ignores firewalls)."""
        dist = {start: 0}
        queue = deque([start])
        while queue:
            c = queue.popleft()
            for dx, dy in DIRS:
                n = (c[0] + dx, c[1] + dy)
                if n not in dist and not self.is_wall(n):
                    dist[n] = dist[c] + 1
                    queue.append(n)
        return dist

    def update(self, dt):
        for cell in list(self.firewalls):
            self.firewalls[cell] -= dt
            if self.firewalls[cell] <= 0:
                del self.firewalls[cell]

    # ---------- generation ----------
    def _carve_maze(self):
        """Depth-first 'recursive backtracker': a random maze with no loops."""
        stack = [(1, 1)]
        self.wall[1][1] = False
        while stack:
            x, y = stack[-1]
            options = []
            for dx, dy in DIRS:
                nx, ny = x + 2 * dx, y + 2 * dy
                if 0 < nx < self.cols - 1 and 0 < ny < self.rows - 1 and self.wall[ny][nx]:
                    options.append((dx, dy))
            if options:
                dx, dy = self.rng.choice(options)
                self.wall[y + dy][x + dx] = False
                self.wall[y + 2 * dy][x + 2 * dx] = False
                stack.append((x + 2 * dx, y + 2 * dy))
            else:
                stack.pop()

    def _add_loops(self, chance):
        for y in range(1, self.rows - 1):
            for x in range(1, self.cols - 1):
                if not self.wall[y][x]:
                    continue
                horizontal = not self.wall[y][x - 1] and not self.wall[y][x + 1] and self.wall[y - 1][x] and self.wall[y + 1][x]
                vertical = not self.wall[y - 1][x] and not self.wall[y + 1][x] and self.wall[y][x - 1] and self.wall[y][x + 1]
                if (horizontal or vertical) and self.rng.random() < chance:
                    self.wall[y][x] = False

    def _place_cores(self, count):
        dist = self.distances_from(self.player_start)
        blocked = {self.player_start, self.raone_start, self.portal}
        candidates = [c for c, d in dist.items() if d >= 7 and c not in blocked]
        dead_ends = [c for c in candidates if sum(self.is_wall((c[0] + dx, c[1] + dy)) for dx, dy in DIRS) == 3]
        others = [c for c in candidates if c not in dead_ends]
        self.rng.shuffle(dead_ends)
        self.rng.shuffle(others)

        cores = []
        for min_gap in (6, 4, 0):
            for c in dead_ends + others:
                if len(cores) == count:
                    return set(cores)
                if c not in cores and all(abs(c[0] - o[0]) + abs(c[1] - o[1]) >= min_gap for o in cores):
                    cores.append(c)
        return set(cores)
