"""Retro sound effects, synthesised in code, so the game needs no audio files."""
import array
import math
import random

import pygame


class Sfx:
    def __init__(self):
        self.enabled = False
        self.muted = False
        self.sounds = {}
        try:
            if not pygame.mixer.get_init():
                pygame.mixer.init(44100, -16, 2, 512)
            freq, size, channels = pygame.mixer.get_init()
            if abs(size) != 16:
                return
            self.freq, self.channels = freq, channels
            tone, S = self._tone, self._sound
            self.sounds = {
                "core": S(tone(0.06, 880, 1320, "square", 0.18) + tone(0.14, 1320, 1980, "sine", 0.3)),
                "portal": S(self._arp([523, 659, 784, 1047, 1319], 0.08, "square", 0.16)),
                "firewall": S(tone(0.3, 170, 80, "saw", 0.28, noise=0.3)),
                "deny": S(tone(0.12, 200, 160, "square", 0.15)),
                "caught": S(tone(0.75, 420, 35, "saw", 0.42, noise=0.5)),
                "level": S(self._arp([392, 523, 659, 784, 1047, 1319], 0.085, "square", 0.17)),
                "beat": S(tone(0.17, 80, 38, "sine", 0.75)),
                "select": S(tone(0.07, 660, 990, "sine", 0.25)),
                "boot": S(tone(0.55, 55, 260, "saw", 0.16, noise=0.1)),
                "gameover": S(self._arp([392, 330, 262, 196], 0.2, "saw", 0.22)),
            }
            self.enabled = True
        except Exception:
            self.enabled = False

    def play(self, name, volume=1.0):
        if self.enabled and not self.muted and name in self.sounds:
            snd = self.sounds[name]
            snd.set_volume(volume)
            snd.play()

    # ---------- synthesis ----------
    def _tone(self, dur, f0, f1, wave="sine", vol=0.3, noise=0.0):
        n = int(self.freq * dur)
        buf = array.array("h")
        phase = 0.0
        attack = max(1, int(self.freq * 0.004))
        for i in range(n):
            t = i / n
            phase += math.tau * (f0 + (f1 - f0) * t) / self.freq
            if wave == "square":
                s = 1.0 if math.sin(phase) >= 0 else -1.0
            elif wave == "saw":
                s = 2.0 * ((phase / math.tau) % 1.0) - 1.0
            else:
                s = math.sin(phase)
            if noise:
                s = s * (1 - noise) + random.uniform(-1, 1) * noise
            env = min(1.0, i / attack) * (1 - t) ** 1.6
            v = int(max(-1.0, min(1.0, s * env * vol)) * 32767)
            buf.extend([v] * self.channels)
        return buf

    def _arp(self, notes, step, wave, vol):
        buf = array.array("h")
        for f in notes:
            buf += self._tone(step, f, f, wave, vol)
        return buf

    @staticmethod
    def _sound(buf):
        return pygame.mixer.Sound(buffer=buf.tobytes())
