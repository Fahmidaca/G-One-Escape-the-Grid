"""
G.ONE: ESCAPE THE GRID
A neon maze chase inspired by Ra.One. You are G.One. Ra.One hunts you with A* search.

Run:  python main.py
Web:  pygbag .   (builds a browser version)
"""
import asyncio
import json
import math
import random
import sys

import pygame

from astar import MODES, MODE_ORDER, manhattan
from effects import (Particles, Shake, TextRenderer, blit_glow, blur, glitch,
                     make_crt_overlay, make_vignette, scale_color)
from entities import Player, RaOne
from settings import (BG, BOOT_TIME, CELL, COLS, CYAN, DIM, FIREWALL_CHARGES, FIREWALL_TIME,
                      FLOOR_LINE, FPS, GRID_BOTTOM, GRID_X, GRID_Y, HEIGHT, HIGHSCORE_FILE, HUD_BG,
                      LEVEL_COLORS, LIVES, MAGENTA, ORANGE, PLAYER_SPEED, PREDICT_FROM_LEVEL,
                      RAONE_BASE_SPEED, RAONE_MAX_SPEED, RAONE_SPEED_STEP, RED, ROWS, TITLE,
                      WALL_FILL, WHITE, WIDTH, YELLOW)
from sound import Sfx
from world import DIRS, World

IS_WEB = sys.platform == "emscripten"

KEY_DIRS = {
    pygame.K_UP: (0, -1), pygame.K_w: (0, -1),
    pygame.K_DOWN: (0, 1), pygame.K_s: (0, 1),
    pygame.K_LEFT: (-1, 0), pygame.K_a: (-1, 0),
    pygame.K_RIGHT: (1, 0), pygame.K_d: (1, 0),
}

LEVEL_INTEL = {
    1: "Ra.One hunts you with A* search. Collect every energy core.",
    2: "Ra.One now PREDICTS where you are heading and cuts you off.",
    3: "Ra.One is faster, and the grid has fewer escape loops.",
}


def cell_px(c):
    """Pixel centre of a grid cell."""
    return (GRID_X + c[0] * CELL + CELL / 2, GRID_Y + c[1] * CELL + CELL / 2)


def grid_px(p):
    """Pixel position of a point in grid units (used for moving characters)."""
    return (GRID_X + (p[0] + 0.5) * CELL, GRID_Y + (p[1] + 0.5) * CELL)


def polygon(center, radius, sides, angle):
    return [(center[0] + radius * math.cos(angle + k * math.tau / sides),
             center[1] + radius * math.sin(angle + k * math.tau / sides)) for k in range(sides)]


def raone_speed(level):
    return min(RAONE_MAX_SPEED, RAONE_BASE_SPEED + RAONE_SPEED_STEP * (level - 1))


def load_high_score():
    try:
        if IS_WEB:
            import platform
            return int(platform.window.localStorage.getItem("gone_high_score") or 0)
        return int(json.loads(HIGHSCORE_FILE.read_text())["high_score"])
    except Exception:
        return 0


def save_high_score(value):
    try:
        if IS_WEB:
            import platform
            platform.window.localStorage.setItem("gone_high_score", str(value))
            return
        HIGHSCORE_FILE.write_text(json.dumps({"high_score": value}))
    except Exception:
        pass


def render_static(world, color):
    """Draw the floor grid and the neon maze walls once per level."""
    layer = pygame.Surface((WIDTH, HEIGHT))
    layer.fill(BG)
    gw, gh = COLS * CELL, ROWS * CELL
    for x in range(COLS + 1):
        X = GRID_X + x * CELL
        pygame.draw.line(layer, FLOOR_LINE, (X, GRID_Y), (X, GRID_Y + gh))
    for y in range(ROWS + 1):
        Y = GRID_Y + y * CELL
        pygame.draw.line(layer, FLOOR_LINE, (GRID_X, Y), (GRID_X + gw, Y))

    edges = pygame.Surface((WIDTH, HEIGHT))
    edges.fill((0, 0, 0))
    detail = scale_color(color, 0.16)
    for y in range(ROWS):
        for x in range(COLS):
            if not world.wall[y][x]:
                continue
            r = pygame.Rect(GRID_X + x * CELL, GRID_Y + y * CELL, CELL, CELL)
            pygame.draw.rect(layer, WALL_FILL, r)
            pygame.draw.rect(layer, detail, r.inflate(-16, -16), 1)
            for dx, dy in DIRS:
                nx, ny = x + dx, y + dy
                if 0 <= nx < COLS and 0 <= ny < ROWS and not world.wall[ny][nx]:
                    if dx == 1:
                        a, b = (r.right - 2, r.top), (r.right - 2, r.bottom - 1)
                    elif dx == -1:
                        a, b = (r.left + 1, r.top), (r.left + 1, r.bottom - 1)
                    elif dy == 1:
                        a, b = (r.left, r.bottom - 2), (r.right - 1, r.bottom - 2)
                    else:
                        a, b = (r.left, r.top + 1), (r.right - 1, r.top + 1)
                    pygame.draw.line(edges, color, a, b, 3)
    glow = blur(edges, 0.2)
    layer.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    layer.blit(glow, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    layer.blit(edges, (0, 0), special_flags=pygame.BLEND_RGB_ADD)
    pygame.draw.rect(layer, scale_color(color, 0.35), (GRID_X - 4, GRID_Y - 4, gw + 8, gh + 8), 1)
    return layer


class Game:
    def __init__(self, screen):
        self.screen = screen
        self.canvas = pygame.Surface((WIDTH, HEIGHT))
        self.text = TextRenderer()
        self.sfx = Sfx()
        self.particles = Particles()
        self.shake = Shake()
        self.crt = make_crt_overlay((WIDTH, HEIGHT))
        self.danger_overlay = make_vignette((WIDTH, HEIGHT), (255, 20, 60), 0.35, 1.3, 230)
        self.vision_layer = pygame.Surface((COLS * CELL, ROWS * CELL), pygame.SRCALPHA)
        self.shade = pygame.Surface((WIDTH, HEIGHT), pygame.SRCALPHA)
        self.band = pygame.Surface((WIDTH, 176), pygame.SRCALPHA)
        self.band.fill((3, 5, 14, 220))
        self.flash_surf = pygame.Surface((WIDTH, HEIGHT))
        self.flash_surf.fill((255, 40, 70))

        self.running = True
        self.state = "menu"           # menu, play, paused, gameover
        self.phase = "intro"          # inside play: intro, run, caught, clear
        self.time = 0.0
        self.vision = False
        self.mode = "astar"
        self.held_dirs = []
        self.mouse_down = False       # left button held: steer towards the cursor
        self.high_score = load_high_score()
        self.new_record = False
        self.toast_text, self.toast_timer = "", 0.0
        self.flash = 0.0
        self.danger = 0.0
        self.beat_timer = 0.0

        self.menu_world = World(1)
        self.menu_layer = render_static(self.menu_world, LEVEL_COLORS[0])
        self.level, self.lives, self.score = 1, LIVES, 0
        self.color = LEVEL_COLORS[0]
        self.world = None

    # ------------------------------------------------------------ flow
    @property
    def predicting(self):
        return self.level >= PREDICT_FROM_LEVEL

    def new_game(self):
        self.level, self.lives, self.score = 1, LIVES, 0
        self.new_record = False
        self.start_level()

    def start_level(self):
        self.world = World(self.level)
        self.color = LEVEL_COLORS[(self.level - 1) % len(LEVEL_COLORS)]
        self.static_layer = render_static(self.world, self.color)
        self.player = Player(self.world.player_start, PLAYER_SPEED)
        self.raone = RaOne(self.world.raone_start, raone_speed(self.level))
        self.cores_total = len(self.world.cores)
        self.charges = FIREWALL_CHARGES
        self.portal_open = False
        self.level_time = 0.0
        self.phase, self.phase_timer = "intro", 3.2
        self.boot_timer = BOOT_TIME
        self.invuln = 0.0
        self.clear_bonus = 0
        self.danger = 0.0
        self.particles.clear()
        self.raone.plan(self.world, self.player, self.mode, self.predicting)
        self.state = "play"

    def to_menu(self):
        self.record_score()
        self.particles.clear()
        self.state = "menu"

    def record_score(self):
        if self.score > self.high_score:
            self.high_score = self.score
            self.new_record = True
            save_high_score(self.score)

    def show_toast(self, text, seconds=2.2):
        self.toast_text, self.toast_timer = text, seconds

    # ------------------------------------------------------------ input
    def handle_event(self, e):
        if e.type == pygame.QUIT:
            self.record_score()
            self.running = False
            return
        if e.type == getattr(pygame, "WINDOWFOCUSLOST", -1):
            self.held_dirs.clear()
            self.mouse_down = False
            return
        if e.type == pygame.MOUSEBUTTONDOWN:
            self.handle_click(e.pos, e.button)
            return
        if e.type == pygame.MOUSEBUTTONUP and e.button == 1:
            self.mouse_down = False
            return
        if e.type == pygame.KEYUP and e.key in KEY_DIRS:
            d = KEY_DIRS[e.key]
            pressed = pygame.key.get_pressed()
            if not any(pressed[k] for k, kd in KEY_DIRS.items() if kd == d) and d in self.held_dirs:
                self.held_dirs.remove(d)
            return
        if e.type != pygame.KEYDOWN:
            return

        k = e.key
        if k == pygame.K_F11:
            pygame.display.toggle_fullscreen()
            return
        if k == pygame.K_m:
            self.sfx.muted = not self.sfx.muted
            self.show_toast("SOUND OFF" if self.sfx.muted else "SOUND ON", 1.2)
            return
        if k in KEY_DIRS:
            d = KEY_DIRS[k]
            if d in self.held_dirs:
                self.held_dirs.remove(d)
            self.held_dirs.append(d)

        if self.state == "menu":
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE):
                self.sfx.play("select")
                self.new_game()
            elif k == pygame.K_ESCAPE:
                self.running = False
            elif k == pygame.K_v:
                self.vision = not self.vision
        elif self.state == "play":
            if k in (pygame.K_ESCAPE, pygame.K_p):
                self.state = "paused"
            elif self.phase == "intro" and (k in (pygame.K_RETURN, pygame.K_KP_ENTER, pygame.K_SPACE) or k in KEY_DIRS):
                self.phase_timer = 0
            elif k in KEY_DIRS and self.phase == "run":
                self.player.press(KEY_DIRS[k])
            elif k == pygame.K_SPACE and self.phase == "run":
                self.drop_firewall()
            elif k == pygame.K_v:
                self.vision = not self.vision
                self.sfx.play("select")
                self.show_toast("AI VISION ON" if self.vision else "AI VISION OFF", 1.2)
            elif k == pygame.K_h:
                self.mode = MODE_ORDER[(MODE_ORDER.index(self.mode) + 1) % len(MODE_ORDER)]
                self.raone.plan(self.world, self.player, self.mode, self.predicting)
                self.sfx.play("select")
                self.show_toast("RA.ONE SEARCH:  " + MODES[self.mode][0])
        elif self.state == "paused":
            if k in (pygame.K_ESCAPE, pygame.K_p, pygame.K_RETURN):
                self.state = "play"
            elif k == pygame.K_q:
                self.to_menu()
        elif self.state == "gameover":
            if k in (pygame.K_RETURN, pygame.K_KP_ENTER):
                self.sfx.play("select")
                self.new_game()
            elif k == pygame.K_ESCAPE:
                self.to_menu()

    def mouse_dirs(self, pos):
        """Grid directions from G.One towards a screen point: the larger axis first,
        then the other one as a fallback when the first is walled off."""
        px, py = grid_px(self.player.pos())
        dx, dy = pos[0] - px, pos[1] - py
        if max(abs(dx), abs(dy)) < CELL / 2:
            return []
        h = (1 if dx > 0 else -1, 0)
        v = (0, 1 if dy > 0 else -1)
        dirs = [h, v] if abs(dx) > abs(dy) else [v, h]
        if min(abs(dx), abs(dy)) < CELL / 2:
            dirs.pop()
        return dirs

    def handle_click(self, pos, button):
        """Left click (or tap) starts / continues; in play, hold it to steer.
        Right click, or a tap on G.One, drops a firewall (phones have no right button)."""
        if self.state == "menu":
            if button == 1:
                self.sfx.play("select")
                self.new_game()
        elif self.state == "paused":
            self.state = "play"
        elif self.state == "gameover":
            if button == 1:
                self.sfx.play("select")
                self.new_game()
        elif self.state == "play":
            if self.phase == "intro":
                self.phase_timer = 0
            elif self.phase == "run":
                px, py = grid_px(self.player.pos())
                if button == 3 or (button == 1 and math.hypot(pos[0] - px, pos[1] - py) < CELL):
                    self.drop_firewall()
                elif button == 1:
                    self.mouse_down = True
                    dirs = self.mouse_dirs(pos)
                    if dirs:
                        self.player.press(dirs[0])

    # ------------------------------------------------------------ actions
    def drop_firewall(self):
        p = self.player
        if p.moving:
            target = p.prev
        elif p.dir != (0, 0):
            target = (p.cell[0] - p.dir[0], p.cell[1] - p.dir[1])
        else:
            target = None
        if self.charges <= 0:
            self.sfx.play("deny", 0.6)
            self.show_toast("NO FIREWALLS LEFT", 1.4)
            return
        if (target is None or self.world.is_wall(target) or target in self.world.firewalls
                or target in (p.cell, self.raone.cell, self.world.portal)):
            self.sfx.play("deny", 0.6)
            return
        self.world.firewalls[target] = FIREWALL_TIME
        self.charges -= 1
        self.particles.burst(cell_px(target), ORANGE, 30, 220)
        self.sfx.play("firewall", 0.8)
        self.shake.add(0.15)

    def collect_core(self, cell):
        self.world.cores.discard(cell)
        self.score += 100 * self.level
        self.particles.burst(cell_px(cell), YELLOW, 34, 280)
        self.sfx.play("core", 0.8)
        self.shake.add(0.18)
        if not self.world.cores:
            self.portal_open = True
            self.particles.burst(cell_px(self.world.portal), MAGENTA, 60, 340, 1.0)
            self.sfx.play("portal", 0.8)
            self.show_toast("PORTAL ONLINE  |  REACH THE EXIT")

    def level_clear(self):
        self.phase, self.phase_timer = "clear", 2.6
        self.clear_bonus = 500 * self.level + max(0, int(90 - self.level_time)) * 10
        self.score += self.clear_bonus
        self.danger = 0.0
        self.particles.burst(cell_px(self.world.portal), CYAN, 80, 380, 1.1)
        self.sfx.play("level", 0.8)
        self.shake.add(0.35)

    def caught(self):
        self.lives -= 1
        self.phase, self.phase_timer = "caught", 1.7
        pos = grid_px(self.player.pos())
        self.particles.burst(pos, CYAN, 70, 420, 1.1, 3.5)
        self.particles.burst(pos, RED, 50, 300, 0.9)
        self.shake.add(1.0)
        self.flash = 1.0
        self.danger = 0.0
        self.sfx.play("caught", 0.9)

    def after_caught(self):
        if self.lives <= 0:
            self.state = "gameover"
            self.record_score()
            self.sfx.play("gameover", 0.8)
            return
        self.player.reset(self.world.player_start)
        self.raone.reset(self.world.raone_start)
        self.raone.plan(self.world, self.player, self.mode, self.predicting)
        self.phase = "run"
        self.boot_timer = 1.5
        self.invuln = 2.5
        self.sfx.play("boot", 0.6)

    # ------------------------------------------------------------ update
    def update(self, dt):
        self.time += dt
        if self.state == "paused":
            return
        self.shake.update(dt)
        self.particles.update(dt)
        self.flash = max(0.0, self.flash - dt * 2.5)
        self.toast_timer = max(0.0, self.toast_timer - dt)
        if self.state == "play":
            self.update_play(dt)
        elif self.state == "menu" and random.random() < dt * 18:
            self.particles.trail((random.uniform(0, WIDTH), random.uniform(0, HEIGHT)),
                                 random.choice([CYAN, MAGENTA, LEVEL_COLORS[0]]), 1.8, 1.4)

    def update_play(self, dt):
        if self.phase == "intro":
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self.phase = "run"
                self.sfx.play("boot", 0.7)
            return
        if self.phase == "caught":
            self.phase_timer -= dt
            if self.phase_timer <= 0:
                self.after_caught()
            return
        if self.phase == "clear":
            self.phase_timer -= dt
            if random.random() < dt * 40:
                self.particles.swirl(cell_px(self.world.portal), random.choice([MAGENTA, CYAN]))
            if self.phase_timer <= 0:
                self.level += 1
                self.start_level()
            return

        # ---- the chase ----
        self.level_time += dt
        self.world.update(dt)
        self.player.held = list(self.held_dirs)
        if self.mouse_down:
            # held is tried last-first, so the preferred direction goes on the end
            self.player.held.extend(reversed(self.mouse_dirs(pygame.mouse.get_pos())))
        self.player.update(dt, self.world)
        if self.player.moving and random.random() < 0.8:
            self.particles.trail(grid_px(self.player.pos()), CYAN)

        if self.boot_timer > 0:
            self.boot_timer -= dt
            if random.random() < dt * 30:
                self.particles.swirl(grid_px(self.raone.pos()), RED, 30)
        else:
            self.raone.update(dt, self.world, self.player, self.mode, self.predicting)
            if self.raone.moving and random.random() < 0.5:
                self.particles.trail(grid_px(self.raone.pos()), RED, 2.0, 0.3)

        for cell in self.player.arrivals:
            if cell in self.world.cores:
                self.collect_core(cell)
            if self.portal_open and cell == self.world.portal:
                self.level_clear()
                break
        self.player.arrivals.clear()
        self.raone.arrivals.clear()
        if self.phase != "run":
            return

        if self.portal_open and random.random() < dt * 25:
            self.particles.swirl(cell_px(self.world.portal), random.choice([MAGENTA, CYAN]))

        # Danger rises as Ra.One's A* path to you gets shorter.
        if self.boot_timer <= 0:
            if self.raone.goal_mode == "CHASE" and self.raone.path:
                gap = len(self.raone.path) - 1
            else:
                gap = manhattan(self.raone.cell, self.player.cell)
            self.danger = max(0.0, min(1.0, (7 - gap) / 6))
        else:
            self.danger = 0.0
        if self.danger > 0.25:
            self.beat_timer -= dt
            if self.beat_timer <= 0:
                self.sfx.play("beat", 0.4 + 0.6 * self.danger)
                self.beat_timer = 0.95 - 0.55 * self.danger
            self.shake.trauma = max(self.shake.trauma, 0.22 * self.danger)

        if self.invuln > 0:
            self.invuln -= dt
        elif self.boot_timer <= 0:
            px, py = self.player.pos()
            rx, ry = self.raone.pos()
            if math.hypot(px - rx, py - ry) < 0.62:
                self.caught()

    # ------------------------------------------------------------ drawing
    def draw(self):
        s = self.screen
        if self.state == "menu":
            self.draw_menu(s)
            s.blit(self.crt, (0, 0))
            return

        c = self.canvas
        self.draw_world(c)
        if self.state == "play" and self.phase == "caught":
            glitch(c, min(1.0, self.phase_timer / 1.2))
        s.fill((0, 0, 0))
        ox, oy = self.shake.offset()
        s.blit(c, (int(ox), int(oy)))
        self.draw_hud(s)
        self.draw_footer(s)

        if self.state == "play" and self.phase == "run" and self.danger > 0.05:
            pulse = 0.65 + 0.35 * math.sin(self.time * (6 + 6 * self.danger))
            self.danger_overlay.set_alpha(int(255 * self.danger * pulse))
            s.blit(self.danger_overlay, (0, 0))
        if self.flash > 0:
            self.flash_surf.set_alpha(int(140 * self.flash))
            s.blit(self.flash_surf, (0, 0))

        if self.toast_timer > 0:
            a = int(255 * min(1.0, self.toast_timer / 0.4))
            self.text.draw(s, self.toast_text, 18, WHITE, (WIDTH // 2, GRID_Y + 26), glow=True, alpha=a)

        if self.state == "play" and self.phase == "intro":
            intel = LEVEL_INTEL.get(self.level, f"Ra.One upgraded: speed {raone_speed(self.level):.1f} cells per second.")
            self.draw_banner(s, f"LEVEL {self.level}", intel,
                             f"Collect {self.cores_total} cores, then reach the portal   |   ENTER to start", self.color)
        elif self.state == "play" and self.phase == "clear":
            self.draw_banner(s, "LEVEL CLEAR", f"+{self.clear_bonus} BONUS", "Ra.One is learning...", CYAN)
        elif self.state == "paused":
            self.shade.fill((2, 3, 10, 170))
            s.blit(self.shade, (0, 0))
            self.text.draw(s, "PAUSED", 64, WHITE, (WIDTH // 2, HEIGHT // 2 - 30), glow=True, kind="display")
            self.text.draw(s, "P, ESC or click to resume   |   Q to quit to menu", 16, DIM, (WIDTH // 2, HEIGHT // 2 + 40), kind="mono")
        elif self.state == "gameover":
            self.draw_game_over(s)
        s.blit(self.crt, (0, 0))

    def draw_world(self, c):
        c.blit(self.static_layer, (0, 0))
        if self.vision:
            self.draw_vision(c)
        self.draw_firewalls(c)
        self.draw_portal(c)
        self.draw_cores(c)
        self.particles.draw(c)
        self.draw_raone(c)
        self.draw_player(c)

    def draw_vision(self, c):
        res = self.raone.search
        if not res:
            return
        layer = self.vision_layer
        layer.fill((0, 0, 0, 0))
        n = max(1, len(res.explored) - 1)
        for i, (x, y) in enumerate(res.explored):
            a = int(26 + 72 * i / n)
            pygame.draw.rect(layer, (255, 50, 90, a), (x * CELL + 3, y * CELL + 3, CELL - 6, CELL - 6), border_radius=4)
        for x, y in res.frontier:
            pygame.draw.rect(layer, (255, 190, 60, 210), (x * CELL + 7, y * CELL + 7, CELL - 14, CELL - 14), 2, border_radius=3)
        c.blit(layer, (GRID_X, GRID_Y))

        if len(res.path) >= 2:
            pts = [grid_px(self.raone.pos())] + [cell_px(p) for p in res.path[1:]]
            pygame.draw.lines(c, (110, 8, 28), False, pts, 9)
            pygame.draw.lines(c, (255, 95, 115), False, pts, 3)
            for p in pts[1:]:
                blit_glow(c, p, 12, RED, 0.5)

        tx, ty = cell_px(self.raone.target)
        size = 16 + 3 * math.sin(self.time * 8)
        col = YELLOW if self.raone.goal_mode == "PREDICT" else RED
        for sx, sy in ((-1, -1), (1, -1), (1, 1), (-1, 1)):
            cx, cy = tx + sx * size, ty + sy * size
            pygame.draw.line(c, col, (cx, cy), (cx - sx * 8, cy), 2)
            pygame.draw.line(c, col, (cx, cy), (cx, cy - sy * 8), 2)

    def draw_firewalls(self, c):
        for cell, left in self.world.firewalls.items():
            if left < 1.5 and int(self.time * 10) % 2 == 0:
                continue
            r = pygame.Rect(GRID_X + cell[0] * CELL + 2, GRID_Y + cell[1] * CELL + 2, CELL - 4, CELL - 4)
            blit_glow(c, r.center, 36, ORANGE, 0.6)
            pygame.draw.rect(c, (70, 22, 0), r, border_radius=4)
            for k in range(4):
                yy = r.top + 3 + (self.time * 30 + k * 9) % (r.height - 6)
                pygame.draw.line(c, ORANGE, (r.left + 4, yy), (r.right - 5, yy), 2)
            pygame.draw.rect(c, (255, 190, 90), r, 2, border_radius=4)
            w = int((r.width - 8) * min(1.0, left / FIREWALL_TIME))
            pygame.draw.rect(c, WHITE, (r.left + 4, r.bottom - 5, w, 2))

    def draw_portal(self, c):
        x, y = cell_px(self.world.portal)
        if self.portal_open:
            blit_glow(c, (x, y), 74, MAGENTA, 0.8 + 0.2 * math.sin(self.time * 4))
            for r, col, speed in ((22, MAGENTA, 2.0), (15, CYAN, -3.0), (8, WHITE, 4.5)):
                rect = pygame.Rect(0, 0, r * 2, r * 2)
                rect.center = (x, y)
                for seg in range(3):
                    a0 = self.time * speed + seg * math.tau / 3
                    pygame.draw.arc(c, col, rect, a0, a0 + 1.4, 3)
        else:
            blit_glow(c, (x, y), 36, (90, 100, 140), 0.35)
            rect = pygame.Rect(0, 0, 40, 40)
            rect.center = (x, y)
            for seg in range(6):
                a0 = seg * math.tau / 6 + self.time * 0.4
                pygame.draw.arc(c, (80, 92, 135), rect, a0, a0 + 0.6, 2)
            pygame.draw.rect(c, (125, 135, 175), (x - 6, y - 2, 12, 9), 2, border_radius=2)
            pygame.draw.arc(c, (125, 135, 175), (x - 5, y - 10, 10, 13), 0, math.pi, 2)

    def draw_cores(self, c):
        for i, cell in enumerate(sorted(self.world.cores)):
            x, y = cell_px(cell)
            y += math.sin(self.time * 3 + cell[0]) * 3
            blit_glow(c, (x, y), 30, YELLOW, 0.55 + 0.15 * math.sin(self.time * 5 + i))
            pts = polygon((x, y), 9, 4, self.time * 2 + i)
            pygame.draw.polygon(c, (90, 70, 0), pts)
            pygame.draw.polygon(c, YELLOW, pts, 2)
            pygame.draw.circle(c, WHITE, (int(x), int(y)), 2)

    def draw_player(self, c):
        if self.phase == "caught":
            return
        p = self.player
        x, y = grid_px(p.pos())
        scale = 1.0
        if self.phase == "clear":
            x, y = cell_px(self.world.portal)
            scale = max(0.0, 1 - (1 - self.phase_timer / 2.6) * 1.8)
            if scale <= 0.02:
                return
        if self.invuln > 0 and self.phase == "run" and int(self.time * 12) % 2 == 0:
            return
        blit_glow(c, (x, y), 46 * scale, CYAN, 0.85)
        r = 13 * scale
        pygame.draw.polygon(c, (0, 140, 170), polygon((x, y), r + 6 * scale, 4, self.time * 2.2), 2)
        diamond = polygon((x, y), r, 4, math.pi / 4)
        pygame.draw.polygon(c, (10, 40, 60), diamond)
        pygame.draw.polygon(c, CYAN, diamond, 2)
        pygame.draw.circle(c, WHITE, (int(x), int(y)), max(1, int(4 * scale)))
        dx, dy = p.dir
        if (dx, dy) != (0, 0) and scale > 0.5:
            tip = (x + dx * (r + 10), y + dy * (r + 10))
            left = (x + dx * (r + 4) - dy * 5, y + dy * (r + 4) + dx * 5)
            right = (x + dx * (r + 4) + dy * 5, y + dy * (r + 4) - dx * 5)
            pygame.draw.polygon(c, WHITE, [tip, left, right])

    def draw_raone(self, c):
        ra = self.raone
        x, y = grid_px(ra.pos())
        booting = self.phase == "intro" or self.boot_timer > 0
        pulse = 0.5 + 0.5 * math.sin(self.time * 7)
        if booting:
            prog = 0.0 if self.phase == "intro" else 1 - max(0.0, self.boot_timer) / BOOT_TIME
            blit_glow(c, (x, y), 52, RED, 0.2 + 0.5 * prog)
            ring = pygame.Rect(0, 0, 58, 58)
            ring.center = (x, y)
            if prog > 0:
                pygame.draw.arc(c, RED, ring, math.pi / 2, math.pi / 2 + math.tau * prog, 3)
        else:
            blit_glow(c, (x, y), 60, RED, 0.75 + 0.35 * pulse)

        body_col = (140, 20, 40) if booting else RED
        hexagon = polygon((x, y), 17, 6, self.time * 0.8)
        pygame.draw.polygon(c, (60, 0, 14), hexagon)
        pygame.draw.polygon(c, body_col, hexagon, 2)
        for k in range(3):
            a = -self.time * 2.5 + k * math.tau / 3
            pygame.draw.line(c, body_col, (x + math.cos(a) * 21, y + math.sin(a) * 21),
                             (x + math.cos(a) * 29, y + math.sin(a) * 29), 3)
        px, py = grid_px(self.player.pos())
        d = math.hypot(px - x, py - y) or 1.0
        ux, uy = (px - x) / d, (py - y) / d
        pygame.draw.circle(c, (255, 225, 230), (int(x + ux * 5), int(y + uy * 5)), 6)
        pygame.draw.circle(c, RED, (int(x + ux * 7), int(y + uy * 7)), 3)

        if booting and self.phase == "run":
            self.text.draw(c, "BOOTING", 11, RED, (x, y - 38), kind="mono")
        elif self.vision and self.phase == "run":
            self.text.draw(c, ra.goal_mode, 11, RED, (x, y - 38), kind="mono")

    def draw_hud(self, s):
        t = self.text
        top = GRID_Y - 12
        pygame.draw.rect(s, HUD_BG, (0, 0, WIDTH, top))
        pygame.draw.line(s, scale_color(self.color, 0.7), (0, top), (WIDTH, top), 1)

        t.draw(s, "G.ONE", 30, CYAN, (GRID_X + 4, 14), "topleft", glow=True, kind="display")
        t.draw(s, "ESCAPE THE GRID", 10, DIM, (GRID_X + 6, 52), "topleft")

        t.draw(s, "LEVEL", 10, DIM, (250, 16), "topleft")
        t.draw(s, f"{self.level:02d}", 26, self.color, (250, 30), "topleft", glow=True)

        cx = 360
        t.draw(s, "ENERGY CORES", 10, DIM, (cx, 16), "topleft")
        got = self.cores_total - len(self.world.cores)
        for i in range(self.cores_total):
            p = (cx + 9 + i * 25, 46)
            pts = polygon(p, 9, 4, 0)
            if i < got:
                blit_glow(s, p, 18, YELLOW, 0.5)
                pygame.draw.polygon(s, YELLOW, pts)
            else:
                pygame.draw.polygon(s, (85, 78, 40), pts, 2)

        fx = 610
        t.draw(s, "FIREWALLS  [SPACE]", 10, DIM, (fx, 16), "topleft")
        for i in range(FIREWALL_CHARGES):
            r = pygame.Rect(fx + i * 30, 38, 22, 16)
            if i < self.charges:
                pygame.draw.rect(s, ORANGE, r, border_radius=3)
            else:
                pygame.draw.rect(s, (90, 50, 22), r, 2, border_radius=3)

        lx = 810
        t.draw(s, "LIVES", 10, DIM, (lx, 16), "topleft")
        for i in range(LIVES):
            p = (lx + 10 + i * 28, 46)
            pts = polygon(p, 10, 4, math.pi / 4)
            if i < self.lives:
                pygame.draw.polygon(s, CYAN, pts)
            else:
                pygame.draw.polygon(s, (30, 62, 74), pts, 2)

        bx = 960
        t.draw(s, "BEST", 10, DIM, (bx, 16), "topleft")
        t.draw(s, f"{max(self.high_score, self.score):07d}", 20, DIM, (bx, 32), "topleft", kind="mono")

        t.draw(s, "SCORE", 10, DIM, (WIDTH - GRID_X - 4, 16), "topright")
        t.draw(s, f"{self.score:07d}", 30, WHITE, (WIDTH - GRID_X - 4, 28), "topright", kind="mono")

    def draw_footer(self, s):
        y = GRID_BOTTOM + 19
        res = self.raone.search if self.world else None
        if self.vision and res:
            x = GRID_X
            pygame.draw.rect(s, (150, 30, 60), (x, y - 6, 12, 12), border_radius=2)
            self.text.draw(s, "explored", 13, DIM, (x + 18, y), "midleft", kind="mono")
            x += 100
            pygame.draw.rect(s, (255, 190, 60), (x, y - 6, 12, 12), 2, border_radius=2)
            self.text.draw(s, "open set", 13, DIM, (x + 18, y), "midleft", kind="mono")
            x += 100
            pygame.draw.line(s, (255, 95, 115), (x, y), (x + 14, y), 3)
            self.text.draw(s, "path", 13, DIM, (x + 20, y), "midleft", kind="mono")
            info = (f"AI VISION   {MODES[self.mode][0]}   explored {len(res.explored)}   open {len(res.frontier)}"
                    f"   path {max(0, len(res.path) - 1)}   {res.time_ms:.2f} ms   target {self.raone.goal_mode}")
            self.text.draw(s, info, 15, (255, 125, 145), (WIDTH - GRID_X, y), "midright", kind="mono")
        else:
            hint = "ARROWS/WASD move    SPACE firewall    V AI vision    H search type    P pause    M mute    F11 fullscreen"
            self.text.draw(s, hint, 14, DIM, (WIDTH // 2, y), kind="mono")

    def draw_banner(self, s, title, subtitle, small, color):
        y0 = HEIGHT // 2 - 88
        s.blit(self.band, (0, y0))
        pygame.draw.line(s, color, (0, y0), (WIDTH, y0), 1)
        pygame.draw.line(s, color, (0, y0 + 175), (WIDTH, y0 + 175), 1)
        self.text.draw(s, title, 50, color, (WIDTH // 2, y0 + 58), glow=True, kind="display")
        self.text.draw(s, subtitle, 18, WHITE, (WIDTH // 2, y0 + 112))
        self.text.draw(s, small, 14, DIM, (WIDTH // 2, y0 + 146), kind="mono")

    def draw_game_over(self, s):
        self.shade.fill((8, 0, 4, 190))
        s.blit(self.shade, (0, 0))
        jx = random.uniform(-3, 3) if random.random() < 0.15 else 0
        self.text.draw(s, "GAME OVER", 78, RED, (WIDTH // 2 + jx, HEIGHT // 2 - 90), glow=True, kind="display")
        self.text.draw(s, "RA.ONE HAS TAKEN THE GRID", 20, WHITE, (WIDTH // 2, HEIGHT // 2 - 20))
        self.text.draw(s, f"SCORE {self.score:07d}     LEVEL {self.level}", 24, WHITE, (WIDTH // 2, HEIGHT // 2 + 30), kind="mono")
        if self.new_record:
            self.text.draw(s, "NEW HIGH SCORE!", 20, YELLOW, (WIDTH // 2, HEIGHT // 2 + 70), glow=True)
        else:
            self.text.draw(s, f"BEST {self.high_score:07d}", 18, DIM, (WIDTH // 2, HEIGHT // 2 + 70), kind="mono")
        self.text.draw(s, "ENTER or click to play again   |   ESC menu", 16, DIM, (WIDTH // 2, HEIGHT // 2 + 120), kind="mono")

    def draw_menu(self, s):
        t = self.text
        s.blit(self.menu_layer, (0, 0))
        self.shade.fill((2, 3, 10, 185))
        s.blit(self.shade, (0, 0))
        sy = (self.time * 140) % HEIGHT
        pygame.draw.line(s, (0, 70, 100), (0, sy), (WIDTH, sy), 2)
        self.particles.draw(s)

        # Ra.One's eye, watching the title
        ex, ey = WIDTH - 250, 290
        pulse = 0.5 + 0.5 * math.sin(self.time * 3)
        blit_glow(s, (ex, ey), 170, RED, 0.55 + 0.25 * pulse)
        hexagon = polygon((ex, ey), 66, 6, self.time * 0.4)
        pygame.draw.polygon(s, (50, 0, 12), hexagon)
        pygame.draw.polygon(s, RED, hexagon, 3)
        for k in range(3):
            a = -self.time * 1.2 + k * math.tau / 3
            pygame.draw.line(s, RED, (ex + math.cos(a) * 80, ey + math.sin(a) * 80),
                             (ex + math.cos(a) * 108, ey + math.sin(a) * 108), 5)
        look = math.sin(self.time * 0.9) * 0.4
        pygame.draw.circle(s, (255, 225, 230), (int(ex - 18 + look * 10), int(ey + look * 6)), 22)
        pygame.draw.circle(s, RED, (int(ex - 26 + look * 12), int(ey + look * 8)), 10)
        t.draw(s, "RA.ONE", 16, RED, (ex, ey + 140), glow=True, kind="display")

        flicker = 0.45 if random.random() < 0.03 else 1.0
        t.draw(s, "G.ONE", 118, scale_color(CYAN, flicker), (104, 186), "midleft", glow=True, kind="display")
        t.draw(s, "ESCAPE THE GRID", 30, MAGENTA, (110, 272), "midleft", glow=True)
        t.draw(s, "Ra.One has escaped the game. It hunts you with A* search.", 17, WHITE, (112, 330), "midleft")
        t.draw(s, "Collect every energy core, then reach the exit portal.", 17, DIM, (112, 358), "midleft")
        if int(self.time * 2) % 2 == 0:
            t.draw(s, "PRESS ENTER OR TAP TO START", 24, WHITE, (110, 420), "midleft", glow=True)

        rows = [("ARROWS / WASD", "Move  (or hold a finger / the mouse and point)"),
                ("SPACE", "Drop a firewall behind you  (or tap G.One / right click)"),
                ("V", "AI Vision: watch A* think" + ("   [ON]" if self.vision else "")),
                ("H", "Switch A* / Dijkstra / Greedy"),
                ("P / ESC", "Pause"),
                ("F11", "Fullscreen")]
        for i, (key, action) in enumerate(rows):
            y = 486 + i * 30
            w = t.size(key, 13, "mono")[0] + 18
            pygame.draw.rect(s, (12, 22, 44), (112, y - 12, w, 24), border_radius=4)
            pygame.draw.rect(s, (40, 90, 130), (112, y - 12, w, 24), 1, border_radius=4)
            t.draw(s, key, 13, CYAN, (112 + w / 2, y), kind="mono")
            t.draw(s, action, 14, DIM, (112 + w + 14, y), "midleft", kind="mono")

        t.draw(s, f"BEST  {self.high_score:07d}", 18, YELLOW, (WIDTH - 250, 520), kind="mono")
        t.draw(s, "Python  |  Pygame  |  A* pathfinding        Made by Fahmida Rahman", 13, DIM,
               (WIDTH // 2, HEIGHT - 24), kind="mono")


def make_icon():
    icon = pygame.Surface((32, 32), pygame.SRCALPHA)
    pygame.draw.polygon(icon, CYAN, polygon((16, 16), 14, 4, math.pi / 4))
    pygame.draw.polygon(icon, (10, 40, 60), polygon((16, 16), 8, 4, math.pi / 4))
    return icon


async def main():
    pygame.mixer.pre_init(44100, -16, 2, 512)
    pygame.init()
    pygame.display.set_caption(TITLE)
    pygame.display.set_icon(make_icon())
    try:
        if IS_WEB:
            raise pygame.error  # the web page scales the canvas itself
        screen = pygame.display.set_mode((WIDTH, HEIGHT), pygame.SCALED | pygame.RESIZABLE)
    except pygame.error:
        screen = pygame.display.set_mode((WIDTH, HEIGHT))
    game = Game(screen)
    clock = pygame.time.Clock()
    while game.running:
        dt = min(clock.tick(FPS) / 1000.0, 1 / 20)
        for event in pygame.event.get():
            game.handle_event(event)
        game.update(dt)
        game.draw()
        pygame.display.flip()
        await asyncio.sleep(0)  # hand control back to the browser each frame (pygbag)
    pygame.quit()


if __name__ == "__main__":
    asyncio.run(main())
