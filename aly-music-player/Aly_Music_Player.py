#!/usr/bin/env python3
"""
Aly Music Player — reproductor de música para Hyprland con colores de Pywal.

Dependencias:  PyQt6, python-mpv (+ libmpv), mutagen, numpy, python-dbus-next
Opcional:      ffmpeg (necesario para dibujar la forma de onda de cada canción)

Este archivo solo arranca la aplicación; el código vive en la carpeta aly_player/
(debe estar junto a este script).

Atajos principales
    /  o  Ctrl+F    Buscar          Esc        Salir de la búsqueda / volver
    J / K           Bajar / subir   H / L      Cerrar·volver / abrir·reproducir
    Enter           Reproducir      Espacio    Pausa / reanudar
    N / P           Siguiente / anterior       Shift+← / Shift+→   ∓5 s
    W               Alternar onda / barra      G          Alternar lista / galería
    F               Favorito                   F5         Reindexar biblioteca
    R               Modo: normal · aleatorio · repetir playlist · repetir canción
"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.realpath(__file__)))

from aly_player.app import main  # noqa: E402

if __name__ == "__main__":
    main()
