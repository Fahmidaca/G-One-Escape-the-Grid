"""G.One (the player) and Ra.One (the A* hunter)."""
from astar import find_path, manhattan
from settings import PREDICT_STEPS


class Mover:
    """Moves one grid cell at a time, sliding smoothly between cells."""

    def __init__(self, cell, speed):
        self.cell = cell          # the cell we are moving into (or standing on)
        self.prev = cell          # the cell we came from
        self.t = 1.0              # progress from prev to cell, 0..1
        self.speed = speed        # cells per second
        self.dir = (0, 0)
        self.arrivals = []        # cells reached since the game last checked

    @property
    def moving(self):
        return self.t < 1.0

    def pos(self):
        """Position in grid units, between prev and cell."""
        return (self.prev[0] + (self.cell[0] - self.prev[0]) * self.t,
                self.prev[1] + (self.cell[1] - self.prev[1]) * self.t)

    def reset(self, cell):
        self.cell = self.prev = cell
        self.t = 1.0
        self.dir = (0, 0)
        self.arrivals.clear()

    def choose_next(self, world):
        return None

    def update(self, dt, world):
        remaining = dt
        for _ in range(4):
            if self.t >= 1.0:
                nxt = self.choose_next(world)
                if nxt is None:
                    return
                self.prev, self.cell = self.cell, nxt
                self.dir = (nxt[0] - self.prev[0], nxt[1] - self.prev[1])
                self.t = 0.0
            need = (1.0 - self.t) / self.speed
            if remaining < need:
                self.t += remaining * self.speed
                return
            remaining -= need
            self.t = 1.0
            self.arrivals.append(self.cell)


class Player(Mover):
    def __init__(self, cell, speed):
        super().__init__(cell, speed)
        self.held = []            # direction keys being held, most recent last
        self.tap = None           # a quick key press, remembered briefly
        self.tap_timer = 0.0

    def press(self, d):
        self.tap, self.tap_timer = d, 0.3
        # Turning around is allowed instantly, even between cells.
        if self.moving and d == (-self.dir[0], -self.dir[1]):
            self.prev, self.cell = self.cell, self.prev
            self.t = 1.0 - self.t
            self.dir = d

    def update(self, dt, world):
        self.tap_timer -= dt
        if self.tap_timer <= 0:
            self.tap = None
        super().update(dt, world)

    def choose_next(self, world):
        options = ([self.tap] if self.tap else []) + list(reversed(self.held))
        for d in options:
            n = (self.cell[0] + d[0], self.cell[1] + d[1])
            if world.passable(n):
                if d == self.tap:
                    self.tap = None
                return n
        return None


class RaOne(Mover):
    """Plans a fresh A* path every time it reaches a cell."""

    def __init__(self, cell, speed):
        super().__init__(cell, speed)
        self.search = None
        self.path = [cell]
        self.target = cell
        self.goal_mode = "IDLE"
        self._context = None

    def plan(self, world, player, mode, predict):
        target, goal_mode = player.cell, "CHASE"

        # Prediction: aim a few cells ahead of where the player is heading,
        # to cut them off, unless Ra.One is already close.
        if predict and player.moving and manhattan(self.cell, player.cell) > 5:
            c = player.cell
            for _ in range(PREDICT_STEPS):
                n = (c[0] + player.dir[0], c[1] + player.dir[1])
                if not world.passable(n):
                    break
                c = n
            if c != player.cell:
                target, goal_mode = c, "PREDICT"

        result = find_path(self.cell, target, world.passable, mode)
        if goal_mode == "PREDICT" and len(result.path) < 2:
            target, goal_mode = player.cell, "CHASE"
            result = find_path(self.cell, target, world.passable, mode)
        if not result.found:
            goal_mode = "BLOCKED"

        self.search, self.path, self.target, self.goal_mode = result, result.path, target, goal_mode

    def update(self, dt, world, player=None, mode="astar", predict=False):
        self._context = (player, mode, predict)
        super().update(dt, world)

    def choose_next(self, world):
        player, mode, predict = self._context
        self.plan(world, player, mode, predict)
        if len(self.path) >= 2:
            return self.path[1]
        return None
