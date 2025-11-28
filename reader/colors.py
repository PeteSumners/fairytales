"""
Color themes for fairytale e-reader.
Default theme: Gothic antiquarian - aged parchment with dark ink.
"""

THEMES = {
    'parchment': {
        'name': 'Parchment',
        # Aged, stained paper - warm yellowed cream
        'SCREEN_BG': (235, 220, 190),
        # Dark brown-black ink
        'TEXT_DEFAULT': (35, 25, 20),
        # Faded text
        'TEXT_DIM': (120, 100, 75),
        'TEXT_LIGHT': (235, 220, 190),
        # Accent - deep burgundy like old book bindings
        'ACCENT': (120, 45, 40),
        # Decorative borders - aged brass/gold
        'SHELL': (160, 140, 100),
        'SHELL_LIGHT': (190, 170, 130),
        'SHELL_DARK': (100, 85, 60),
        # Highlight for selection
        'HIGHLIGHT': (35, 25, 20),
    },
    'vellum': {
        'name': 'Vellum',
        # Lighter, cleaner parchment
        'SCREEN_BG': (248, 242, 230),
        'TEXT_DEFAULT': (45, 35, 30),
        'TEXT_DIM': (140, 120, 100),
        'TEXT_LIGHT': (248, 242, 230),
        'ACCENT': (100, 60, 50),
        'SHELL': (180, 165, 145),
        'SHELL_LIGHT': (210, 195, 175),
        'SHELL_DARK': (120, 105, 85),
        'HIGHLIGHT': (45, 35, 30),
    },
    'night': {
        'name': 'Night',
        # Dark reading mode - deep navy/black
        'SCREEN_BG': (25, 25, 35),
        'TEXT_DEFAULT': (200, 190, 170),
        'TEXT_DIM': (100, 95, 80),
        'TEXT_LIGHT': (25, 25, 35),
        'ACCENT': (180, 140, 90),
        'SHELL': (45, 45, 55),
        'SHELL_LIGHT': (65, 65, 75),
        'SHELL_DARK': (15, 15, 20),
        'HIGHLIGHT': (200, 190, 170),
    },
    'sepia_dark': {
        'name': 'Sepia',
        # Deep sepia - like very old manuscripts
        'SCREEN_BG': (60, 45, 35),
        'TEXT_DEFAULT': (220, 200, 170),
        'TEXT_DIM': (140, 120, 100),
        'TEXT_LIGHT': (60, 45, 35),
        'ACCENT': (200, 160, 100),
        'SHELL': (80, 60, 45),
        'SHELL_LIGHT': (100, 80, 60),
        'SHELL_DARK': (40, 30, 25),
        'HIGHLIGHT': (220, 200, 170),
    },
    'manuscript': {
        'name': 'Manuscript',
        # Cream with rich brown ink - medieval feel
        'SCREEN_BG': (245, 235, 215),
        'TEXT_DEFAULT': (50, 35, 25),
        'TEXT_DIM': (130, 110, 90),
        'TEXT_LIGHT': (245, 235, 215),
        # Vermillion accent like illuminated capitals
        'ACCENT': (180, 55, 40),
        'SHELL': (140, 120, 95),
        'SHELL_LIGHT': (175, 155, 130),
        'SHELL_DARK': (95, 80, 60),
        'HIGHLIGHT': (50, 35, 25),
    },
}

current_theme = 'parchment'


def set_theme(theme_name):
    global current_theme
    if theme_name in THEMES:
        current_theme = theme_name
        _update_colors()


def get_theme_name():
    return THEMES[current_theme]['name']


def next_theme():
    global current_theme
    theme_list = list(THEMES.keys())
    idx = theme_list.index(current_theme)
    current_theme = theme_list[(idx + 1) % len(theme_list)]
    _update_colors()
    return current_theme


def _update_colors():
    global SCREEN_BG, TEXT_DEFAULT, TEXT_DIM, TEXT_LIGHT
    global ACCENT, SHELL, SHELL_LIGHT, SHELL_DARK, HIGHLIGHT

    t = THEMES[current_theme]
    SCREEN_BG = t['SCREEN_BG']
    TEXT_DEFAULT = t['TEXT_DEFAULT']
    TEXT_DIM = t['TEXT_DIM']
    TEXT_LIGHT = t['TEXT_LIGHT']
    ACCENT = t['ACCENT']
    SHELL = t['SHELL']
    SHELL_LIGHT = t['SHELL_LIGHT']
    SHELL_DARK = t['SHELL_DARK']
    HIGHLIGHT = t['HIGHLIGHT']


# Initialize
_update_colors()
