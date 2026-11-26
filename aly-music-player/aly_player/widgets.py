"""Widgets propios: forma de onda, barra de progreso, buscador y etiqueta recortada."""
from __future__ import annotations

import numpy as np

from PyQt6.QtCore import pyqtSignal, QRectF, Qt
from PyQt6.QtGui import QColor, QPainter
from PyQt6.QtWidgets import QLabel, QLineEdit, QSizePolicy, QWidget

from .constants import R_M


class _SeekWidget(QWidget):
    """Base común: tarjeta redondeada, progreso, hover y arrastre para buscar."""
    seek_requested = pyqtSignal(float)   # fracción 0..1

    def __init__(self, object_name: str):
        super().__init__()
        self.setObjectName(object_name)
        self.setFixedHeight(78)
        self.setCursor(Qt.CursorShape.PointingHandCursor)
        self.setMouseTracking(True)
        self._progress = 0.0
        self._hover: float | None = None
        self._dragging = False
        self._c_card = QColor("#222")
        self._c_played = QColor("#89b4fa")
        self._c_rest = QColor("#666")

    def set_colors(self, card: str, played: str, rest: str):
        self._c_card, self._c_played, self._c_rest = QColor(card), QColor(played), QColor(rest)
        self.update()

    def set_progress(self, frac: float):
        if self._dragging:
            return
        frac = min(max(frac, 0.0), 1.0)
        if abs(frac - self._progress) > 1e-4:
            self._progress = frac
            self.update()

    def _span(self) -> tuple[float, float]:
        """(izquierda, ancho) de la zona interactiva."""
        raise NotImplementedError

    def _fraction_at(self, x: float) -> float:
        left, width = self._span()
        return min(max((x - left) / max(width, 1.0), 0.0), 1.0)

    def _paint_card(self, p: QPainter):
        p.setRenderHint(QPainter.RenderHint.Antialiasing)
        p.setPen(Qt.PenStyle.NoPen)
        p.setBrush(self._c_card)
        p.drawRoundedRect(QRectF(self.rect()), R_M, R_M)

    def mousePressEvent(self, e):
        if e.button() == Qt.MouseButton.LeftButton:
            self._dragging = True
            self._progress = self._fraction_at(e.position().x())
            self.update()

    def mouseMoveEvent(self, e):
        frac = self._fraction_at(e.position().x())
        if self._dragging:
            self._progress = frac
        self._hover = frac
        self.update()

    def mouseReleaseEvent(self, e):
        if self._dragging and e.button() == Qt.MouseButton.LeftButton:
            self._dragging = False
            self.seek_requested.emit(self._fraction_at(e.position().x()))

    def leaveEvent(self, _):
        self._hover = None
        self.update()


class WaveformWidget(_SeekWidget):
    """Forma de onda de la canción que además funciona como barra de progreso."""

    BAR_W, GAP = 3, 2

    def __init__(self):
        super().__init__("Waveform")
        self._peaks: np.ndarray | None = None
        self._amps: np.ndarray | None = None
        self._amps_n = 0

    def set_peaks(self, peaks: np.ndarray | None):
        self._peaks, self._amps_n = peaks, 0
        self.update()

    def _inner(self) -> QRectF:
        return QRectF(self.rect()).adjusted(R_M, 10, -R_M, -10)

    def _span(self):
        inner = self._inner()
        return inner.left(), inner.width()

    def _amplitudes(self, n: int) -> np.ndarray:
        if self._amps is not None and self._amps_n == n:
            return self._amps
        if self._peaks is None or len(self._peaks) == 0:
            amps = np.full(n, 0.05, dtype=np.float32)
        elif len(self._peaks) <= n:
            idx = (np.arange(n) * len(self._peaks) / n).astype(int)
            amps = self._peaks[idx]
        else:
            edges = np.linspace(0, len(self._peaks), n, endpoint=False).astype(int)
            amps = np.maximum.reduceat(self._peaks, edges)
        self._amps, self._amps_n = amps, n
        return amps

    def paintEvent(self, _):
        p = QPainter(self)
        self._paint_card(p)

        inner = self._inner()
        step = self.BAR_W + self.GAP
        n = max(1, int((inner.width() + self.GAP) // step))
        amps = self._amplitudes(n)
        mid, full = inner.center().y(), inner.height()
        split = int(round(self._progress * n))

        for color, lo, hi in ((self._c_played, 0, split), (self._c_rest, split, n)):
            p.setBrush(color)
            for i in range(lo, hi):
                h = max(3.0, float(amps[i]) * full)
                p.drawRoundedRect(QRectF(inner.left() + i * step, mid - h / 2,
                                         self.BAR_W, h), 1.5, 1.5)

        if self._hover is not None and not self._dragging:
            p.setBrush(self._c_played)
            x = inner.left() + self._hover * inner.width()
            p.drawRoundedRect(QRectF(x - 1, inner.top(), 2, inner.height()), 1, 1)
        p.end()


class ProgressBarWidget(_SeekWidget):
    """Barra de progreso clásica interactiva (alternativa a la forma de onda)."""

    def __init__(self):
        super().__init__("LinearProgress")

    def _track_rect(self) -> QRectF:
        r = QRectF(self.rect()).adjusted(R_M + 4, 0, -(R_M + 4), 0)
        cy = r.center().y()
        return QRectF(r.left(), cy - 4.0, r.width(), 8.0)

    def _span(self):
        tr = self._track_rect()
        return tr.left(), tr.width()

    def paintEvent(self, _):
        p = QPainter(self)
        self._paint_card(p)

        tr = self._track_rect()
        p.setBrush(self._c_rest)
        p.drawRoundedRect(tr, 4.0, 4.0)

        fill_w = tr.width() * self._progress
        if fill_w > 0:
            p.setBrush(self._c_played)
            p.drawRoundedRect(QRectF(tr.left(), tr.top(), fill_w, tr.height()), 4.0, 4.0)

        if self._hover is not None and not self._dragging:
            hx = tr.left() + tr.width() * self._hover
            c_hover = QColor(self._c_played)
            c_hover.setAlpha(130)
            p.setBrush(c_hover)
            p.drawEllipse(QRectF(hx - 5.0, tr.center().y() - 5.0, 10.0, 10.0))

        kx = tr.left() + fill_w
        radius = 8.0 if (self._dragging or self._hover is not None) else 6.5
        p.setBrush(self._c_played)
        p.drawEllipse(QRectF(kx - radius, tr.center().y() - radius, radius * 2, radius * 2))
        p.end()


class SearchEdit(QLineEdit):
    navigate = pyqtSignal()   # ↓ pasa el foco a los resultados

    def keyPressEvent(self, e):
        if e.key() == Qt.Key.Key_Down:
            self.navigate.emit()
            return
        super().keyPressEvent(e)


class ElidedLabel(QLabel):
    """Etiqueta que recorta con '…' en vez de ensanchar el panel."""

    def __init__(self, text: str = ""):
        super().__init__()
        self._full = ""
        self.setSizePolicy(QSizePolicy.Policy.Ignored, QSizePolicy.Policy.Preferred)
        self.set_full_text(text)

    def set_full_text(self, text: str):
        self._full = text
        self.setToolTip(text)
        self._elide()

    def _elide(self):
        shown = self.fontMetrics().elidedText(self._full, Qt.TextElideMode.ElideRight,
                                              max(self.width() - 4, 10))
        super().setText(shown)

    def resizeEvent(self, e):
        super().resizeEvent(e)
        self._elide()
