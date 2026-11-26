"""Búsqueda y navegación con teclado."""
from __future__ import annotations

from PyQt6.QtWidgets import QListWidgetItem

from .constants import MAX_RESULTS
from .utils import fold


class NavigationMixin:
    """Búsqueda y navegación con teclado."""

    def focus_search(self):
        self.search.setFocus()
        self.search.selectAll()

    def leave_search(self):
        self.search_timer.stop()
        if self.search.text():
            self.search.clear()
            self._run_search()
        elif self.stack.currentIndex() == 1 and self.drill_key is not None:
            self._drill_up()
        self._active_view().setFocus()

    def _run_search(self):
        query = self.search.text().strip()
        if not query:
            if self.current_category == "folders":
                self.stack.setCurrentIndex(0)
                self._update_status()
            else:
                self.stack.setCurrentIndex(1)
                self._render_collection()
            return

        self.btn_back.hide()
        self.btn_play_all.hide()
        self.btn_new_playlist.hide()
        self.stack.setCurrentIndex(2)
        if not self.library_ready:
            self.results.clear()
            self.result_paths = []
            self.status.setText("Indexando biblioteca…")
            return

        tokens = fold(query).split()
        matches = [e for e in self.library if all(t in e["hay"] for t in tokens)]

        def title_miss(e: dict) -> bool:        # los que coinciden en el título, primero
            title = fold(e["title"])
            return not all(t in title for t in tokens)

        matches.sort(key=title_miss)
        truncated = len(matches) > MAX_RESULTS
        matches = matches[:MAX_RESULTS]

        self.result_paths = [e["path"] for e in matches]
        self.results.setUpdatesEnabled(False)
        self.results.clear()
        for e in matches:
            item = QListWidgetItem(f"{e['title']}\n{e['artist']} · {e['album']}")
            item.setToolTip(e["path"])
            self.results.addItem(item)
        self.results.setUpdatesEnabled(True)
        if matches:
            self.results.setCurrentRow(0)

        n = len(matches)
        self.status.setText("Sin resultados" if n == 0 else
                            f"{n}{'+' if truncated else ''} resultado{'s' if n != 1 else ''}")

    def _focus_results(self):
        if self.stack.currentIndex() == 2 and self.results.count():
            self.results.setFocus()
            if self.results.currentRow() < 0:
                self.results.setCurrentRow(0)
        elif self.stack.currentIndex() == 1:
            self.collection_view.setFocus()
        else:
            self.tree.setFocus()

    def _play_first_result(self):
        if self.stack.currentIndex() == 2 and self.result_paths:
            row = max(self.results.currentRow(), 0)
            self.play_playlist(list(self.result_paths), row)

    def _on_result_activated(self, item: QListWidgetItem):
        self.play_playlist(list(self.result_paths), self.results.row(item))

    def _active_view(self):
        idx = self.stack.currentIndex()
        if idx == 2:
            return self.results
        if idx == 1:
            return self.collection_view
        return self.tree

    def _move_selection(self, delta: int):
        view = self._active_view()
        if view in (self.results, self.collection_view):
            count = view.count()
            if count:
                row = view.currentRow()
                view.setCurrentRow(max(0, min(count - 1, row + delta)))
            return

        cur = self.tree.currentIndex()
        if not cur.isValid():
            first = self.model.index(0, 0, self.tree.rootIndex())
            if first.isValid():
                self.tree.setCurrentIndex(first)
            return
        nxt = self.tree.indexBelow(cur) if delta > 0 else self.tree.indexAbove(cur)
        if nxt.isValid():
            self.tree.setCurrentIndex(nxt)

    def _collapse_or_parent(self):
        view = self._active_view()
        if view is self.collection_view:
            self._drill_up()
            return
        if view is not self.tree:
            return
        cur = self.tree.currentIndex()
        if not cur.isValid():
            return
        if self.model.isDir(cur) and self.tree.isExpanded(cur):
            self.tree.collapse(cur)
        else:
            parent = cur.parent()
            if parent.isValid() and parent != self.tree.rootIndex():
                self.tree.setCurrentIndex(parent)

    def _expand_or_play(self):
        view = self._active_view()
        if view is self.results:
            row = self.results.currentRow()
            if row >= 0:
                self.play_playlist(list(self.result_paths), row)
            return
        if view is self.collection_view:
            item = self.collection_view.currentItem()
            if item is not None:
                self._on_collection_activated(item)
            return
        cur = self.tree.currentIndex()
        if not cur.isValid():
            return
        if self.model.isDir(cur):
            if not self.tree.isExpanded(cur):
                self.tree.expand(cur)
            else:
                child = self.model.index(0, 0, cur)
                if child.isValid():
                    self.tree.setCurrentIndex(child)
        else:
            self._play_from_tree(cur)

    def _on_tree_activated(self, index):
        if self.model.isDir(index):
            self.tree.setExpanded(index, not self.tree.isExpanded(index))
        else:
            self._play_from_tree(index)

    def _play_from_tree(self, index):
        parent = index.parent()
        if self.model.canFetchMore(parent):
            self.model.fetchMore(parent)
        paths = []
        for row in range(self.model.rowCount(parent)):
            child = self.model.index(row, 0, parent)
            if not self.model.isDir(child):
                paths.append(self.model.filePath(child))
        target = self.model.filePath(index)
        if target in paths:
            self.play_playlist(paths, paths.index(target))

    def _highlight_current(self, path: str):
        idx = self.stack.currentIndex()
        if idx == 2:
            if path in self.result_paths:
                self.results.setCurrentRow(self.result_paths.index(path))
        elif idx == 1:
            for i, entry in enumerate(self.collection_items):
                if entry.get("path") == path:
                    self.collection_view.setCurrentRow(i)
                    break
        else:
            tidx = self.model.index(path)
            if tidx.isValid():
                self.tree.setCurrentIndex(tidx)
                self.tree.scrollTo(tidx)
