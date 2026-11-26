"""Constantes, rutas y configuración por defecto."""
from __future__ import annotations

import os
import subprocess


APP_NAME = "Aly Music Player"
AUDIO_EXTS = (".mp3", ".flac", ".wav", ".ogg", ".opus", ".m4a", ".aac")

# Sistema de bordes
R_XL = 24   # contenedores principales
R_L = 16    # carátula y elementos destacados
R_M = 12    # buscador y tarjeta de la onda
R_S = 8     # botones, ítems de lista, sliders

ART_SIZE = 236
TILE_ART_SIZE = 128
LIST_ART_SIZE = 42
WAVE_BINS = 480          # resolución máxima de la forma de onda calculada
WAVE_CACHE_SIZE = 48     # ondas guardadas en memoria
MAX_RESULTS = 300
MAX_RECENT = 100
SEEK_STEP = 5            # segundos

WAL_PATH = os.path.expanduser("~/.cache/wal/colors.json")
CONFIG_DIR = os.path.expanduser("~/.config/omatunes")
CONFIG_FILE = os.path.join(CONFIG_DIR, "config.json")
USER_DATA_FILE = os.path.join(CONFIG_DIR, "user_data.json")
CACHE_DIR = os.path.join(os.path.expanduser("~/.cache/aly-music-player"))
COVERS_DIR = os.path.join(CACHE_DIR, "covers")
THUMBS_DIR = os.path.join(COVERS_DIR, "thumbs")   # miniaturas JPG: se decodifican al instante
THUMB_PX = 256
LIB_CACHE_FILE = os.path.join(CACHE_DIR, "library_cache.json")


def default_music_directory() -> str:
    """Obtiene la carpeta Música del usuario (XDG) o usa una ruta habitual."""
    try:
        result = subprocess.run(
            ["xdg-user-dir", "MUSIC"],
            check=False, capture_output=True, text=True, timeout=2
        ).stdout.strip()
        if result:
            return os.path.expanduser(result)
    except (OSError, subprocess.SubprocessError):
        pass

    for candidate in ("~/Música", "~/Music"):
        path = os.path.expanduser(candidate)
        if os.path.isdir(path):
            return path

    return os.path.expanduser("~/Music")


DEFAULT_CONFIG = {
    "default_directory": default_music_directory(),
    "volume": 80,
    "progress_mode": "wave",   # "wave" | "bar"
    "view_mode": "list",       # "list" | "grid"
    "play_mode": "normal",     # "normal" | "shuffle" | "repeat_all" | "repeat_one"
}

DEFAULT_THEME = {"background": "#1e1e2e", "foreground": "#cdd6f4", "accent": "#89b4fa"}

# Atajos mostrados en la tarjeta: (teclas, descripción)
SHORTCUTS = (
    (("/", "Ctrl+F"), "Buscar"),
    (("Esc",), "Volver"),
    (("J", "K"), "Bajar / subir"),
    (("H", "L"), "Cerrar / abrir"),
    (("Enter",), "Reproducir"),
    (("Espacio",), "Pausa"),
    (("N", "P"), "Sig. / ant."),
    (("⇧←", "⇧→"), "∓5 s"),
    (("W",), "Onda / barra"),
    (("G",), "Lista / galería"),
    (("F",), "Favorito"),
    (("R",), "Modo"),
)

# Modos de reproducción, en el orden en que cicla el botón:
# clave -> (texto del botón, descripción para el tooltip)
PLAY_MODES = {
    "normal": ("➡", "Orden normal: se detiene al terminar la lista"),
    "shuffle": ("🔀", "Aleatorio"),
    "repeat_all": ("🔁", "Repetir playlist"),
    "repeat_one": ("🔂", "Repetir canción"),
}
MPRIS_LOOP = {"normal": "None", "shuffle": "None",
              "repeat_all": "Playlist", "repeat_one": "Track"}
