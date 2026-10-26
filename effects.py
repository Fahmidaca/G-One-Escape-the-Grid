"""Neon look: glow, particles, screen shake, CRT overlay, glitch and glowing text."""
import math
import random

import pygame

from settings import FONT_DISPLAY, FONT_MONO, FONT_UI

_glow_cache = {}


def glow_sprite(radius, color, strength=1.0):
    """A soft radial light on black, meant to be drawn with additive blending."""
    radius = max(2, int(radius))
    strength = round(max(0.0, min(1.5, strength)), 1)
    key = (radius, color, strength)
    surf = _glow_cache.get(key)
    if surf is None:
        surf = pygame.Surface((radius * 2, radius * 2))
        surf.fill((0, 0, 0))
        steps = max(6, radius // 2)
        for i in range(steps, 0, -1):
            k = (1 - i / steps) ** 2.2 * strength
            c = tuple(min(255, int(ch * k)) for ch in color)
            pygame.draw.circle(surf, c, (radius, radius), max(1, int(radius * i / steps)))
        _glow_cache[key] = surf
    return surf


def blit_glow(target, center, radius, color, strength=1.0):
    s = glow_sprite(radius, color, strength)
    r = s.get_width() // 2
    target.blit(s, (int(center[0]) - r, int(center[1]) - r), special_flags=pygame.BLEND_RGB_ADD)


def blur(surface, scale=0.25):
    w, h = surface.get_size()
    small = pygame.transform.smoothscale(surface, (max(1, int(w * scale)), max(1, int(h * scale))))
    return pygame.transform.smoothscale(small, (w, h))


def scale_color(color, k):
    return tuple(max(0, min(255, int(c * k))) for c in color)


# ---------------------------------------------------------------- particles
class Particle:
    __slots__ = ("x", "y", "vx", "vy", "life", "max_life", "color", "size", "drag")

    def __init__(self, x, y, vx, vy, life, color, size, drag):
        self.x, self.y, self.vx, self.vy = x, y, vx, vy
        self.life = self.max_life = life
        self.color, self.size, self.drag = color, size, drag


class Particles:
    def __init__(self):
        self.items = []

    def clear(self):
        self.items.clear()

    def burst(self, pos, color, n=30, speed=260, life=0.8, size=3.0):
        for _ in range(n):
            a = random.uniform(0, math.tau)
            s = random.uniform(0.25, 1.0) * speed
            self.items.append(Particle(pos[0], pos[1], math.cos(a) * s, math.sin(a) * s,
                                       random.uniform(0.5, 1.0) * life, color, size, 3.0))

    def trail(self, pos, color, size=2.2, life=0.35):
        a = random.uniform(0, math.tau)
        self.items.append(Particle(pos[0] + random.uniform(-4, 4), pos[1] + random.uniform(-4, 4),
                                   math.cos(a) * 20, math.sin(a) * 20, life, color, size, 1.0))

    def swirl(self, center, color, radius=34):
        a = random.uniform(0, math.tau)
        x, y = center[0] + math.cos(a) * radius, center[1] + math.sin(a) * radius
        self.items.append(Particle(x, y, -math.sin(a) * 90 - math.cos(a) * 60,
                                   math.cos(a) * 90 - math.sin(a) * 60, 0.6, color, 2.4, 0.5))

    def update(self, dt):
        alive = []
        for p in self.items:
            p.life -= dt
            if p.life <= 0:
                continue
            f = max(0.0, 1 - p.drag * dt)
            p.vx *= f
            p.vy *= f
            p.x += p.vx * dt
            p.y += p.vy * dt
            alive.append(p)
        self.items = alive[-600:]

    def draw(self, surf):
        for p in self.items:
            k = p.life / p.max_life
            blit_glow(surf, (p.x, p.y), p.size * 4, p.color, 0.6 * k + 0.1)
            pygame.draw.circle(surf, scale_color(p.color, 0.6 + 0.4 * k), (int(p.x), int(p.y)), max(1, int(p.size * k)))


# ---------------------------------------------------------------- screen shake
class Shake:
    def __init__(self):
        self.trauma = 0.0

    def add(self, amount):
        self.trauma = min(1.0, self.trauma + amount)

    def update(self, dt):
        self.trauma = max(0.0, self.trauma - dt * 1.6)

    def offset(self):
        s = self.trauma ** 2 * 16
        return (random.uniform(-s, s), random.uniform(-s, s))


# ---------------------------------------------------------------- overlays
def make_vignette(size, color=(0, 0, 0), inner=0.55, power=1.6, max_alpha=210):
    w, h = size
    small = pygame.Surface((64, 36), pygame.SRCALPHA)
    for yy in range(36):
        for xx in range(64):
            dx = (xx + 0.5) / 64 * 2 - 1
            dy = (yy + 0.5) / 36 * 2 - 1
            d = math.sqrt(dx * dx * 0.85 + dy * dy * 1.15)
            a = max(0.0, min(1.0, (d - inner) / (1.25 - inner))) ** power
            small.set_at((xx, yy), (*color, int(a * max_alpha)))
    return pygame.transform.smoothscale(small, size)


def make_crt_overlay(size):
    w, h = size
    surf = make_vignette(size, (0, 0, 0), 0.72, 1.8, 130)
    lines = pygame.Surface(size, pygame.SRCALPHA)
    for y in range(0, h, 3):
        pygame.draw.line(lines, (0, 0, 0, 34), (0, y), (w, y))
    surf.blit(lines, (0, 0))
    return surf


def glitch(surface, intensity):
    """Shift random horizontal bands sideways and tint some of them."""
    w, h = surface.get_size()
    for _ in range(int(4 + intensity * 16)):
        y = random.randrange(0, h - 4)
        bh = min(random.randrange(3, 30), h - y)
        dx = int(random.uniform(-50, 50) * intensity)
        band = surface.subsurface((0, y, w, bh)).copy()
        if random.random() < 0.4:
            band.fill(random.choice([(255, 90, 110), (90, 255, 255)]), special_flags=pygame.BLEND_RGB_MULT)
        surface.blit(band, (dx, y))


# ---------------------------------------------------------------- text
class TextRenderer:
    FILES = {"display": FONT_DISPLAY, "ui": FONT_UI, "mono": FONT_MONO}

    def __init__(self):
        self.fonts = {}
        self.cache = {}

    def font(self, size, kind="ui"):
        key = (size, kind)
        if key not in self.fonts:
            try:
                self.fonts[key] = pygame.font.Font(str(self.FILES[kind]), size)
            except (OSError, FileNotFoundError):
                self.fonts[key] = pygame.font.SysFont("bahnschrift,consolas,dejavusans", size, bold=kind != "mono")
        return self.fonts[key]

    def _surfaces(self, text, size, color, glow, kind):
        key = (text, size, color, glow, kind)
        hit = self.cache.get(key)
        if hit:
            return hit
        if len(self.cache) > 500:
            self.cache.clear()
        base = self.font(size, kind).render(text, True, color)
        glow_surf = None
        if glow:
            pad = max(8, size // 2)
            w, h = base.get_size()
            g = pygame.Surface((w + pad * 2, h + pad * 2))
            g.fill((0, 0, 0))
            g.blit(base, (pad, pad))
            glow_surf = (blur(g, 0.22 if size >= 40 else 0.4), pad)
        self.cache[key] = (base, glow_surf)
        return base, glow_surf

    def draw(self, target, text, size, color, pos, anchor="center", glow=False, kind="ui", alpha=255):
        base, glow_surf = self._surfaces(text, size, color, glow, kind)
        rect = base.get_rect(**{anchor: (int(pos[0]), int(pos[1]))})
        if glow_surf:
            g, pad = glow_surf
            for _ in range(2 if size >= 40 else 1):
                target.blit(g, (rect.x - pad, rect.y - pad), special_flags=pygame.BLEND_RGB_ADD)
        if alpha < 255:
            base = base.copy()
            base.set_alpha(alpha)
        target.blit(base, rect)
        return rect

    def size(self, text, size, kind="ui"):
        return self.font(size, kind).size(text)
