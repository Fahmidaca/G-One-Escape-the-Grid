"""
A* search on a grid. Ra.One uses this to hunt the player.

    f(n) = g(n) + h(n)

    g(n)  number of moves from the start to cell n (each move costs 1)
    h(n)  Manhattan distance from n to the goal: |dx| + |dy|

On a grid where you can only move up, down, left or right, the Manhattan
distance never overestimates the real distance. That makes it an
admissible heuristic, so A* always returns a shortest path.

The same function also runs two other searches, so the game can compare
them live (press H in the game):

    Dijkstra   f = g        (no heuristic: explores in every direction)
    Greedy     f = h        (ignores the cost so far: fast, not always shortest)

Run this file on its own to see all three on a small maze:
    python astar.py
"""
import heapq
import time
from dataclasses import dataclass

DIRECTIONS = ((1, 0), (-1, 0), (0, 1), (0, -1))

# mode: (label, weight of g, weight of h)
MODES = {
    "astar": ("A*  f = g + h", 1, 1),
    "dijkstra": ("Dijkstra  f = g", 1, 0),
    "greedy": ("Greedy  f = h", 0, 1),
}
MODE_ORDER = ["astar", "dijkstra", "greedy"]


def manhattan(a, b):
    return abs(a[0] - b[0]) + abs(a[1] - b[1])


@dataclass
class SearchResult:
    path: list          # cells from start to goal, [] if no path
    explored: list      # the closed set, in the order cells were expanded
    frontier: list      # cells still waiting in the open set
    time_ms: float
    mode: str = "astar"

    @property
    def found(self):
        return len(self.path) > 0


def find_path(start, goal, passable, mode="astar"):
    """Search from start to goal. passable(cell) says whether a cell can be entered."""
    _, wg, wh = MODES[mode]
    t0 = time.perf_counter()

    h0 = manhattan(start, goal)
    # Heap entries: (f, h, tie-breaker, cell). On equal f, the smaller h wins,
    # which keeps the search heading towards the goal.
    open_heap = [(wh * h0, h0, 0, start)]
    g_cost = {start: 0}
    parent = {}
    closed = set()
    explored = []
    counter = 0

    while open_heap:
        _, _, _, node = heapq.heappop(open_heap)
        if node in closed:
            continue
        closed.add(node)
        explored.append(node)

        if node == goal:
            path = [node]
            while node in parent:
                node = parent[node]
                path.append(node)
            path.reverse()
            frontier = list({entry[3] for entry in open_heap if entry[3] not in closed})
            return SearchResult(path, explored, frontier, (time.perf_counter() - t0) * 1000, mode)

        for dx, dy in DIRECTIONS:
            nb = (node[0] + dx, node[1] + dy)
            if nb in closed or not passable(nb):
                continue
            new_g = g_cost[node] + 1
            if new_g < g_cost.get(nb, float("inf")):
                g_cost[nb] = new_g
                parent[nb] = node
                h = manhattan(nb, goal)
                counter += 1
                heapq.heappush(open_heap, (wg * new_g + wh * h, h, counter, nb))

    return SearchResult([], explored, [], (time.perf_counter() - t0) * 1000, mode)


if __name__ == "__main__":
    maze = [
        "#################",
        "#S......#.......#",
        "#.#####.#.#####.#",
        "#.#...#...#...#.#",
        "#.#.#.#####.#.#.#",
        "#...#.......#...#",
        "#####.#####.#####",
        "#.....#...#.....#",
        "#.#####.#.#####.#",
        "#.......#......G#",
        "#################",
    ]
    cells = {(x, y): ch for y, row in enumerate(maze) for x, ch in enumerate(row)}
    start = next(c for c, ch in cells.items() if ch == "S")
    goal = next(c for c, ch in cells.items() if ch == "G")

    def passable(c):
        return cells.get(c, "#") != "#"

    print("Search            Path length   Cells explored")
    for m in MODE_ORDER:
        r = find_path(start, goal, passable, m)
        print(f"{MODES[m][0]:16s}  {len(r.path) - 1:11d}   {len(r.explored):14d}")

    r = find_path(start, goal, passable, "astar")
    print("\nA* path (* = path, . = explored, o = open set):")
    for y, row in enumerate(maze):
        line = ""
        for x, ch in enumerate(row):
            c = (x, y)
            if ch in "SG#":
                line += ch
            elif c in r.path:
                line += "*"
            elif c in r.frontier:
                line += "o"
            elif c in r.explored:
                line += "."
            else:
                line += " "
        print(line)
