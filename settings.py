"""Game-wide settings: window, grid, colours and difficulty."""
from pathlib import Path

TITLE = "G.ONE: Escape the Grid"
WIDTH, HEIGHT = 1280, 720
FPS = 60

# The maze grid. COLS and ROWS must be odd for the maze generator.
CELL = 40
COLS, ROWS = 31, 15
GRID_X = (WIDTH - COLS * CELL) // 2
GRID_Y = 82
GRID_BOTTOM = GRID_Y + ROWS * CELL

ASSETS = Path(__file__).with_name("assets")
FONT_DISPLAY = ASSETS / "fonts" / "Orbitron-Black.ttf"
FONT_UI = ASSETS / "fonts" / "Orbitron-Bold.ttf"
FONT_MONO = ASSETS / "fonts" / "ShareTechMono-Regular.ttf"
HIGHSCORE_FILE = Path(__file__).with_name("highscore.json")

# Colours
BG = (4, 6, 16)
FLOOR_LINE = (13, 19, 42)
WALL_FILL = (9, 12, 32)
HUD_BG = (7, 10, 24)
WHITE = (235, 245, 255)
DIM = (105, 120, 158)
CYAN = (0, 235, 255)
RED = (255, 38, 70)
ORANGE = (255, 140, 30)
YELLOW = (255, 215, 60)
MAGENTA = (255, 60, 220)
LEVEL_COLORS = [
    (0, 200, 255),
    (170, 80, 255),
    (30, 230, 140),
    (255, 150, 40),
    (255, 60, 170),
]

# Gameplay
LIVES = 3
PLAYER_SPEED = 7.0           # cells per second
RAONE_BASE_SPEED = 3.9       # Ra.One's speed on level 1
RAONE_SPEED_STEP = 0.5       # extra speed per level
RAONE_MAX_SPEED = 6.6        # always a little slower than G.One
BOOT_TIME = 2.0              # seconds before Ra.One starts hunting
FIREWALL_TIME = 6.0
FIREWALL_CHARGES = 3
PREDICT_FROM_LEVEL = 2       # level where Ra.One starts predicting your route
PREDICT_STEPS = 4            # how many cells ahead it predicts
