"""Favoritos, estadísticas de reproducción y playlists."""
from __future__ import annotations

from PyQt6.QtWidgets import QInputDialog, QMessageBox

from .constants import APP_NAME, MAX_RECENT
from .storage import save_user_data


class FavoritesMixin:
    """Favoritos, estadísticas de reproducción y playlists."""

    def _commit_user_data(self):
        """Guarda los datos del usuario e invalida las colecciones en caché."""
        save_user_data(self.user_data)
        self._invalidate_collections()

    def is_favorite(self, path: str | None) -> bool:
        return bool(path and path in self.user_data["favorites"])

    def _sync_fav_button(self):
        fav = self.is_favorite(self.current_path)
        self.btn_fav.setChecked(fav)
        self.btn_fav.setText("♥" if fav else "♡")

    def toggle_current_favorite(self):
        if self.current_path:
            self.toggle_favorite(self.current_path)

    def toggle_favorite(self, path: str):
        favs = self.user_data["favorites"]
        if path in favs:
            favs.remove(path)
        else:
            favs.insert(0, path)
        self._commit_user_data()
        self._sync_fav_button()
        if self.stack.currentIndex() == 1 and (
                self.drill_key is not None
                or self.current_category in ("favorites", "recent", "most_played")):
            self._render_collection()

    def _record_play_stats(self, path: str):
        rec = [p for p in self.user_data["recent"] if p != path]
        rec.insert(0, path)
        self.user_data["recent"] = rec[:MAX_RECENT]

        counts = self.user_data["play_counts"]
        counts[path] = int(counts.get(path, 0)) + 1
        save_user_data(self.user_data)
        self._invalidate_collections("recent", "most_played")

    def _create_playlist_dialog(self, initial_tracks: list[str] | None = None) -> str | None:
        name, ok = QInputDialog.getText(self, "Nueva playlist", "Nombre de la playlist:")
        if not ok:
            return None
        name = name.strip()
        if not name:
            return None
        playlists = self.user_data["playlists"]
        if name not in playlists:
            playlists[name] = []
        if initial_tracks:
            for p in initial_tracks:
                if p not in playlists[name]:
                    playlists[name].append(p)
        self._commit_user_data()
        if self.current_category == "playlists" and self.stack.currentIndex() == 1:
            self._render_collection()
        return name

    def _add_tracks_to_playlist(self, playlist_name: str, paths: list[str]):
        playlists = self.user_data["playlists"]
        plist = playlists.setdefault(playlist_name, [])
        added = 0
        for p in paths:
            if p not in plist:
                plist.append(p)
                added += 1
        self._commit_user_data()
        self.status.setText(
            f"Agregada{'s' if added != 1 else ''} {added} pista{'s' if added != 1 else ''} a «{playlist_name}»"
        )
        if self.current_category == "playlists" and self.stack.currentIndex() == 1:
            self._render_collection()

    def _remove_from_current_playlist(self, path: str):
        if self.current_category != "playlists" or not self.drill_key:
            return
        plist = self.user_data["playlists"].get(self.drill_key, [])
        if path in plist:
            plist.remove(path)
            self._commit_user_data()
            self._render_collection()

    def _rename_playlist(self, old_name: str):
        new_name, ok = QInputDialog.getText(self, "Renombrar playlist", "Nuevo nombre:", text=old_name)
        if not ok:
            return
        new_name = new_name.strip()
        if not new_name or new_name == old_name:
            return
        playlists = self.user_data["playlists"]
        if new_name in playlists:
            QMessageBox.warning(self, APP_NAME, "Ya existe una playlist con ese nombre.")
            return
        playlists[new_name] = playlists.pop(old_name, [])
        self._commit_user_data()
        self._render_collection()

    def _delete_playlist(self, name: str):
        ans = QMessageBox.question(
            self, "Eliminar playlist", f"¿Eliminar la playlist «{name}»?",
            QMessageBox.StandardButton.Yes | QMessageBox.StandardButton.No
        )
        if ans == QMessageBox.StandardButton.Yes:
            self.user_data["playlists"].pop(name, None)
            self._commit_user_data()
            self._render_collection()
