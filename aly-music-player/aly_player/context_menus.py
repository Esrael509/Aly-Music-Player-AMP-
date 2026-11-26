"""Menús contextuales (clic derecho)."""
from __future__ import annotations

import os

from PyQt6.QtWidgets import QMenu

from .constants import AUDIO_EXTS
from .utils import fold


class ContextMenuMixin:
    """Menús contextuales (clic derecho)."""

    def _show_track_context_menu(self, global_pos, paths: list[str], allow_remove_playlist: bool = False):
        if not paths:
            return
        menu = QMenu(self)
        single = paths[0] if len(paths) == 1 else None

        act_play = menu.addAction("▶ Reproducir ahora")
        act_play.triggered.connect(lambda: self.play_playlist(paths, 0))

        if single:
            fav = self.is_favorite(single)
            act_fav = menu.addAction("💔 Quitar de Favoritos" if fav else "♥ Agregar a Favoritos")
            act_fav.triggered.connect(lambda: self.toggle_favorite(single))

        pl_menu = menu.addMenu("➕ Agregar a playlist")
        for pname in sorted(self.user_data["playlists"].keys(), key=fold):
            act_p = pl_menu.addAction(pname)
            act_p.triggered.connect(lambda _c=False, n=pname: self._add_tracks_to_playlist(n, paths))
        if self.user_data["playlists"]:
            pl_menu.addSeparator()
        act_new_p = pl_menu.addAction("+ Nueva playlist…")
        act_new_p.triggered.connect(lambda: self._create_playlist_dialog(paths))

        if allow_remove_playlist and single:
            menu.addSeparator()
            act_rem = menu.addAction("🗑 Quitar de esta playlist")
            act_rem.triggered.connect(lambda: self._remove_from_current_playlist(single))

        menu.exec(global_pos)

    def _on_tree_context_menu(self, pos):
        idx = self.tree.indexAt(pos)
        if not idx.isValid():
            return
        path = self.model.filePath(idx)
        if self.model.isDir(idx):
            tracks = [
                os.path.join(dp, fn)
                for dp, _, fns in os.walk(path)
                for fn in sorted(fns)
                if fn.lower().endswith(AUDIO_EXTS)
            ]
            self._show_track_context_menu(self.tree.viewport().mapToGlobal(pos), tracks)
        else:
            self._show_track_context_menu(self.tree.viewport().mapToGlobal(pos), [path])

    def _on_results_context_menu(self, pos):
        item = self.results.itemAt(pos)
        if not item:
            return
        row = self.results.row(item)
        if 0 <= row < len(self.result_paths):
            self._show_track_context_menu(self.results.viewport().mapToGlobal(pos), [self.result_paths[row]])

    def _on_collection_context_menu(self, pos):
        item = self.collection_view.itemAt(pos)
        if not item:
            return
        row = self.collection_view.row(item)
        if not (0 <= row < len(self.collection_items)):
            return
        entry = self.collection_items[row]
        gpos = self.collection_view.viewport().mapToGlobal(pos)

        if entry["kind"] == "track":
            in_pl = (self.current_category == "playlists" and self.drill_key is not None)
            self._show_track_context_menu(gpos, [entry["path"]], allow_remove_playlist=in_pl)
        elif entry["kind"] == "group":
            self._show_track_context_menu(gpos, entry["paths"])
        elif entry["kind"] == "playlist":
            menu = QMenu(self)
            menu.addAction("▶ Reproducir playlist").triggered.connect(
                lambda: self.play_playlist(entry["paths"], 0) if entry["paths"] else None
            )
            menu.addAction("✏ Renombrar").triggered.connect(lambda: self._rename_playlist(entry["key"]))
            menu.addAction("🗑 Eliminar playlist").triggered.connect(lambda: self._delete_playlist(entry["key"]))
            menu.exec(gpos)
