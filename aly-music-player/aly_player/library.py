"""Biblioteca: indexado, categorías, colección en lista/galería."""
from __future__ import annotations

import os
import time

from PyQt6.QtCore import QSize, Qt
from PyQt6.QtGui import QIcon, QPixmap
from PyQt6.QtWidgets import QListWidget, QListWidgetItem

from .constants import LIST_ART_SIZE, R_M, R_S, TILE_ART_SIZE
from .metadata import (placeholder_tile, read_full_metadata, rounded_cover_from_pixmap,
                       thumbnail_path)
from .storage import save_config, save_user_data
from .utils import fold
from .workers import LibraryScanJob


class LibraryMixin:
    """Biblioteca: indexado, categorías, colección en lista/galería."""

    def start_scan(self):
        if self._scanning:
            return
        self._scanning = True
        self._invalidate_collections()
        self.library_ready = False
        self._update_status()
        self.pool.start(LibraryScanJob(self.root_dir, self.signals))

    def _on_scan_done(self, entries: list):
        self.library = entries
        self.meta_by_path = {e["path"]: e for e in entries}
        self.library_ready = True
        self._scanning = False
        self._invalidate_collections()
        self._prune_missing_user_data()
        if self.search.text().strip():
            self._run_search()
        elif self.stack.currentIndex() == 1:
            self._render_collection()
        else:
            self._update_status()

    def _prune_missing_user_data(self):
        """Limpia entradas inexistentes si el usuario borró archivos de disco."""
        valid = set(self.meta_by_path.keys())
        if not valid:
            return
        changed = False
        favs = [p for p in self.user_data["favorites"] if p in valid]
        if len(favs) != len(self.user_data["favorites"]):
            self.user_data["favorites"] = favs
            changed = True
        rec = [p for p in self.user_data["recent"] if p in valid]
        if len(rec) != len(self.user_data["recent"]):
            self.user_data["recent"] = rec
            changed = True
        if changed:
            save_user_data(self.user_data)

    def _update_status(self):
        if self.stack.currentIndex() == 2:
            return
        if self.stack.currentIndex() == 0:
            name = os.path.basename(self.root_dir.rstrip(os.sep)) or self.root_dir
            if self.library_ready:
                self.status.setText(f"{len(self.library)} canciones · {name}")
            else:
                self.status.setText("Indexando biblioteca…")

    def _on_dir_loaded(self, path: str):
        if self._initial_select_done:
            return
        if os.path.realpath(path) != os.path.realpath(self.root_dir):
            return
        self._initial_select_done = True
        first = self.model.index(0, 0, self.tree.rootIndex())
        if first.isValid() and not self.tree.currentIndex().isValid():
            self.tree.setCurrentIndex(first)

    def set_category(self, category: str):
        if self.search.text():
            self.search.blockSignals(True)
            self.search.clear()
            self.search.blockSignals(False)

        self.current_category = category
        self.drill_key = None
        for k, btn in self.nav_buttons.items():
            btn.setChecked(k == category)

        if category == "folders":
            self.btn_back.hide()
            self.btn_play_all.hide()
            self.btn_new_playlist.hide()
            self.stack.setCurrentIndex(0)
            self._update_status()
            self.tree.setFocus()
        else:
            self.stack.setCurrentIndex(1)
            self._render_collection()
            self.collection_view.setFocus()

    def _drill_up(self):
        if self.drill_key is not None:
            self.drill_key = None
            self._render_collection()
            self.collection_view.setFocus()

    def _cover_icon(self, cover_path: str, size: int) -> QIcon | None:
        """Icono redondeado de una carátula (desde su miniatura); None si no hay."""
        key = ("c", cover_path, size)
        if key in self._icon_cache:
            return self._icon_cache[key]
        icon = None
        if cover_path and os.path.isfile(cover_path):
            src = QPixmap(thumbnail_path(cover_path))
            if not src.isNull():
                radius = R_M if size >= 80 else R_S
                pix = rounded_cover_from_pixmap(src, size, radius, self.devicePixelRatioF())
                icon = QIcon(pix) if pix else None
        self._icon_cache[key] = icon
        return icon

    def _placeholder_icon(self, label: str, size: int) -> QIcon:
        """Icono con la inicial; se comparte entre todos los ítems con la misma letra."""
        accent = self.theme["accent"]
        initial = label.strip()[:1].upper()
        key = ("p", initial, size, accent)
        icon = self._icon_cache.get(key)
        if icon is None:
            radius = R_M if size >= 80 else R_S
            icon = QIcon(placeholder_tile(initial, size, radius, self.theme["card"], accent,
                                          self.devicePixelRatioF()))
            self._icon_cache[key] = icon
        return icon

    def _load_covers_chunk(self):
        """Carga carátulas poco a poco (≈12 ms por pasada) para no congelar la interfaz."""
        queue, view = self._cover_queue, self.collection_view
        deadline = time.perf_counter() + 0.012
        while queue and time.perf_counter() < deadline:
            row, cover, size = queue.popleft()
            item = view.item(row)
            icon = self._cover_icon(cover, size)
            if item is not None and icon is not None:
                item.setIcon(icon)
        if not queue:
            self._cover_timer.stop()

    def _invalidate_collections(self, *categories: str):
        """Descarta colecciones en caché (todas, o solo las categorías indicadas)."""
        for key in [k for k in self._collection_cache if not categories or k[0] in categories]:
            del self._collection_cache[key]

    def _group_library(self, field: str) -> list[dict]:
        groups: dict[str, dict] = {}
        for track in self.library:
            key = track.get(field) or "Desconocido"
            grp = groups.get(key)
            if grp is None:
                grp = {
                    "kind": "group",
                    "key": key,
                    "title": key,
                    "subtitle": "",
                    "cover_path": track.get("cover_path", ""),
                    "paths": [],
                }
                groups[key] = grp
            grp["paths"].append(track["path"])
            if not grp["cover_path"] and track.get("cover_path"):
                grp["cover_path"] = track["cover_path"]

        out = sorted(groups.values(), key=lambda g: fold(g["title"]))
        for g in out:
            n = len(g["paths"])
            if field == "albums":
                first_meta = self.meta_by_path.get(g["paths"][0], {})
                artist = first_meta.get("artist", "")
                g["subtitle"] = f"{artist} · {n} pista{'s' if n != 1 else ''}" if artist else f"{n} pistas"
            else:
                g["subtitle"] = f"{n} canción{'es' if n != 1 else ''}"
        return out

    def _track_entry(self, path: str, extra_sub: str = "") -> dict:
        meta = self.meta_by_path.get(path)
        if meta is None:
            raw = read_full_metadata(path, extract_cover=True)
            meta = {
                "path": path,
                "title": raw["title"],
                "artist": raw["artist"],
                "album": raw["album"],
                "genre": raw["genre"],
                "cover_path": raw["cover_path"],
            }
        fav_mark = "♥ " if path in self._fav_set else ""
        sub = f"{meta['artist']} · {meta['album']}"
        if extra_sub:
            sub = f"{extra_sub} · {sub}"
        return {
            "kind": "track",
            "path": path,
            "title": f"{fav_mark}{meta['title']}",
            "subtitle": sub,
            "cover_path": meta.get("cover_path", ""),
        }

    def _build_collection_data(self) -> tuple[list[dict], str]:
        cat = self.current_category
        self._fav_set = set(self.user_data["favorites"])   # O(1) en _track_entry

        if not self.library_ready and cat in ("songs", "artists", "albums", "genres"):
            return [], "Indexando biblioteca…"

        if cat == "songs":
            tracks = [self._track_entry(t["path"]) for t in self.library]
            tracks.sort(key=lambda item: fold(item["title"]))
            return tracks, f"Todas las canciones · {len(tracks)}"

        if cat in ("artists", "albums", "genres"):
            field = {"artists": "artist", "albums": "album", "genres": "genre"}[cat]
            if self.drill_key is None:
                groups = self._group_library(field)
                label_map = {"artists": "artistas", "albums": "álbumes", "genres": "géneros"}
                return groups, f"{len(groups)} {label_map[cat]}"
            tracks = [
                self._track_entry(t["path"])
                for t in self.library
                if (t.get(field) or "Desconocido") == self.drill_key
            ]
            return tracks, f"{self.drill_key} · {len(tracks)} canción{'es' if len(tracks) != 1 else ''}"

        if cat == "recent":
            items = [self._track_entry(p) for p in self.user_data["recent"] if os.path.isfile(p)]
            return items, f"Reproducido recientemente · {len(items)}"

        if cat == "most_played":
            counts = self.user_data["play_counts"]
            ranked = sorted(
                [(p, c) for p, c in counts.items() if c > 0 and os.path.isfile(p)],
                key=lambda x: (-x[1], fold(os.path.basename(x[0])))
            )
            items = [self._track_entry(p, f"{c}×") for p, c in ranked]
            return items, f"Más reproducido · {len(items)}"

        if cat == "favorites":
            items = [self._track_entry(p) for p in self.user_data["favorites"] if os.path.isfile(p)]
            return items, f"Favoritos · {len(items)} canción{'es' if len(items) != 1 else ''}"

        if cat == "playlists":
            playlists = self.user_data["playlists"]
            if self.drill_key is None:
                out = []
                for name in sorted(playlists.keys(), key=fold):
                    plist = [p for p in playlists[name] if os.path.isfile(p)]
                    cover = ""
                    for p in plist:
                        m = self.meta_by_path.get(p)
                        if m and m.get("cover_path"):
                            cover = m["cover_path"]
                            break
                    out.append({
                        "kind": "playlist",
                        "key": name,
                        "title": name,
                        "subtitle": f"{len(plist)} canción{'es' if len(plist) != 1 else ''}",
                        "cover_path": cover,
                        "paths": plist,
                    })
                return out, f"{len(out)} playlist{'s' if len(out) != 1 else ''}"
            plist = [p for p in playlists.get(self.drill_key, []) if os.path.isfile(p)]
            items = [self._track_entry(p) for p in plist]
            return items, f"Playlist: {self.drill_key} · {len(items)}"

        return [], ""

    def _render_collection(self):
        key = (self.current_category, self.drill_key)
        cached = self._collection_cache.get(key)
        if cached is None:
            cached = self._collection_cache[key] = self._build_collection_data()
        items, status_text = cached
        self.collection_items = items
        self.status.setText(status_text)

        self.btn_back.setVisible(self.drill_key is not None)
        self.btn_new_playlist.setVisible(self.current_category == "playlists" and self.drill_key is None)
        has_tracks = any(it["kind"] == "track" for it in items)
        self.btn_play_all.setVisible(has_tracks)

        is_grid = self.view_mode == "grid"
        icon_size = TILE_ART_SIZE if is_grid else LIST_ART_SIZE

        view = self.collection_view
        view.setUpdatesEnabled(False)
        view.clear()
        self._cover_queue.clear()

        if self._applied_grid is not is_grid:       # reconfigurar la vista solo si cambió
            self._applied_grid = is_grid
            if is_grid:
                view.setViewMode(QListWidget.ViewMode.IconMode)
                view.setFlow(QListWidget.Flow.LeftToRight)
                view.setWrapping(True)
                view.setSpacing(10)
                view.setIconSize(QSize(TILE_ART_SIZE, TILE_ART_SIZE))
                view.setGridSize(QSize(TILE_ART_SIZE + 28, TILE_ART_SIZE + 54))
            else:
                view.setViewMode(QListWidget.ViewMode.ListMode)
                view.setFlow(QListWidget.Flow.TopToBottom)
                view.setWrapping(False)
                view.setSpacing(2)
                view.setIconSize(QSize(LIST_ART_SIZE, LIST_ART_SIZE))
                view.setGridSize(QSize())
            view.setUniformItemSizes(True)          # diseño mucho más rápido en listas largas

        grid_align = Qt.AlignmentFlag.AlignHCenter | Qt.AlignmentFlag.AlignTop
        for row, entry in enumerate(items):
            title, sub = entry["title"], entry["subtitle"]
            item = QListWidgetItem(title if is_grid or not sub else f"{title}\n{sub}")
            item.setIcon(self._placeholder_icon(title, icon_size))
            item.setToolTip(f"{title}\n{sub}" if sub else title)
            if is_grid:
                item.setTextAlignment(grid_align)
            view.addItem(item)
            if entry.get("cover_path"):
                self._cover_queue.append((row, entry["cover_path"], icon_size))

        view.setUpdatesEnabled(True)
        if items:
            view.setCurrentRow(0)
        if self._cover_queue:
            self._cover_timer.start()

    def _on_collection_activated(self, item: QListWidgetItem):
        row = self.collection_view.row(item)
        if not (0 <= row < len(self.collection_items)):
            return
        entry = self.collection_items[row]
        if entry["kind"] in ("group", "playlist"):
            self.drill_key = entry["key"]
            self._render_collection()
        elif entry["kind"] == "track":
            track_paths = [e["path"] for e in self.collection_items if e["kind"] == "track"]
            if entry["path"] in track_paths:
                self.play_playlist(track_paths, track_paths.index(entry["path"]))

    def _play_all_collection(self):
        track_paths = [e["path"] for e in self.collection_items if e["kind"] == "track"]
        if track_paths:
            self.play_playlist(track_paths, 0)

    def toggle_view_mode(self):
        self.view_mode = "grid" if self.view_mode == "list" else "list"
        self.config["view_mode"] = self.view_mode
        save_config(self.config)
        self._sync_view_mode_ui()
        if self.current_category == "folders" and self.stack.currentIndex() == 0:
            # En Carpetas no hay galería: al activarla se pasa a Álbumes.
            if self.view_mode == "grid":
                self.set_category("albums")
        elif self.stack.currentIndex() == 1:
            self._render_collection()

    def _sync_view_mode_ui(self):
        is_grid = self.view_mode == "grid"
        self.btn_view_mode.setText("☰ Lista" if is_grid else "⊞ Galería")
