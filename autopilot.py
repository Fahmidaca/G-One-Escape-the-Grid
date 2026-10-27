"""G.One's auto-pilot: collect the cores, keep away from Ra.One, then reach the portal.

It plans one step at a time, every time G.One or Ra.One reaches a new cell:
  1. Breadth-first search from Ra.One gives its distance to every cell (the "danger map").
  2. If Ra.One is close, run: step to the neighbour that is furthest from Ra.One,
     preferring cells with more exits so G.One does not run into a dead end.
  3. Otherwise breadth-first search from G.One to the nearest core (or the portal once
     every core is collected), treating cells right next to Ra.One as blocked so the
     route goes around it.
"""
from collections import deque

from world import DIRS

PANIC = 3     # Ra.One this many steps away (or fewer): run instead of collecting
BUFFER = 2    # cells this close to Ra.One are avoided when planning a route
FAR = 999


def _bfs(world, start, blocked=None):
    """Distance and parent of every cell reachable from start."""
    dist, parent = {start: 0}, {start: None}
    queue = deque([start])
    while queue:
        c = queue.popleft()
        for dx, dy in DIRS:
            n = (c[0] + dx, c[1] + dy)
            if n in dist or not world.passable(n) or (blocked and blocked(n)):
                continue
            dist[n], parent[n] = dist[c] + 1, c
            queue.append(n)
    return dist, parent


def _first_step(parent, start, goal):
    c = goal
    while parent[c] != start:
        c = parent[c]
    return (c[0] - start[0], c[1] - start[1])


def _exits(world, c):
    return sum(world.passable((c[0] + dx, c[1] + dy)) for dx, dy in DIRS)


def plan(world, me, hunter, portal_open):
    """Return (direction or None, True when a firewall behind G.One would help)."""
    danger, _ = _bfs(world, hunter)
    gap = danger.get(me, FAR)

    if gap <= PANIC:
        best, best_score = None, None
        for dx, dy in DIRS:
            n = (me[0] + dx, me[1] + dy)
            if not world.passable(n) or n == hunter:
                continue
            score = danger.get(n, FAR) * 3 + _exits(world, n)
            if best_score is None or score > best_score:
                best, best_score = (dx, dy), score
        return best, gap <= 2

    targets = list(world.cores) if world.cores else ([world.portal] if portal_open else [])
    if not targets:
        return None, False
    # Try a route that keeps clear of Ra.One first, then any route at all.
    for blocked in (lambda c: danger.get(c, FAR) <= BUFFER, None):
        dist, parent = _bfs(world, me, blocked)
        reachable = [t for t in targets if t in dist and t != me]
        if reachable:
            goal = min(reachable, key=lambda t: dist[t])
            return _first_step(parent, me, goal), False
    return None, False
