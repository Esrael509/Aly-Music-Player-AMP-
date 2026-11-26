"""Lectura y escritura de configuración, datos de usuario y tema de Pywal."""
from __future__ import annotations

import json
import os

from .constants import (
    CONFIG_DIR, CONFIG_FILE, DEFAULT_CONFIG, DEFAULT_THEME, USER_DATA_FILE,
    WAL_PATH,
)
from .utils import mix


def load_pywal_theme() -> dict:
    """Lee ~/.cache/wal/colors.json y deriva todos los tonos de la interfaz."""
    bg = DEFAULT_THEME["background"]
    fg = DEFAULT_THEME["foreground"]
    accent = DEFAULT_THEME["accent"]

    if os.path.exists(WAL_PATH):
        try:
            with open(WAL_PATH, "r", encoding="utf-8") as f:
                data = json.load(f)
            special = data.get("special", {})
            colors = data.get("colors", {})
            bg = special.get("background", bg)
            fg = special.get("foreground", fg)
            for key in ("color4", "color2", "color6", "color1", "color5"):
                cand = colors.get(key)
                if cand and cand.lower() != bg.lower():
                    accent = cand
                    break
        except (json.JSONDecodeError, OSError) as e:
            print(f"No se pudo leer pywal ({e}), usando tema por defecto.")

    return {
        "bg": bg,
        "fg": fg,
        "accent": accent,
        "card": mix(bg, fg, 0.06),
        "hover": mix(bg, fg, 0.12),
        "dim": mix(bg, fg, 0.55),
        "rest": mix(bg, fg, 0.25),
    }


def save_config(cfg: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(CONFIG_FILE, "w", encoding="utf-8") as f:
            json.dump(cfg, f, indent=4, ensure_ascii=False)
    except OSError as e:
        print(f"No se pudo guardar la configuración: {e}")


def load_user_config() -> dict:
    cfg = dict(DEFAULT_CONFIG)
    if os.path.exists(CONFIG_FILE):
        try:
            with open(CONFIG_FILE, "r", encoding="utf-8") as f:
                data = json.load(f)
            if isinstance(data, dict):
                cfg.update(data)
        except (json.JSONDecodeError, OSError):
            print("Error leyendo config.json, usando valores por defecto.")
    else:
        save_config(cfg)
    return cfg


def load_user_data() -> dict:
    data = {
        "favorites": [],
        "playlists": {},     # {nombre: [ruta, ...]}
        "recent": [],        # [ruta, ...] más reciente primero
        "play_counts": {},   # {ruta: int}
    }
    if os.path.exists(USER_DATA_FILE):
        try:
            with open(USER_DATA_FILE, "r", encoding="utf-8") as f:
                raw = json.load(f)
            if isinstance(raw, dict):
                if isinstance(raw.get("favorites"), list):
                    data["favorites"] = [str(p) for p in raw["favorites"]]
                if isinstance(raw.get("playlists"), dict):
                    data["playlists"] = {
                        str(k): [str(p) for p in v]
                        for k, v in raw["playlists"].items()
                        if isinstance(v, list)
                    }
                if isinstance(raw.get("recent"), list):
                    data["recent"] = [str(p) for p in raw["recent"]]
                if isinstance(raw.get("play_counts"), dict):
                    data["play_counts"] = {
                        str(k): int(v) for k, v in raw["play_counts"].items()
                    }
        except (json.JSONDecodeError, OSError, ValueError):
            print("Error leyendo user_data.json, iniciando datos vacíos.")
    return data


def save_user_data(data: dict) -> None:
    try:
        os.makedirs(CONFIG_DIR, exist_ok=True)
        with open(USER_DATA_FILE, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except OSError as e:
        print(f"No se pudo guardar user_data.json: {e}")
