"""Metadatos de audio, carátulas y generación de miniaturas."""
from __future__ import annotations

import base64
import hashlib
import os

from PyQt6.QtCore import QRect, QRectF, Qt
from PyQt6.QtGui import QColor, QImage, QPainter, QPainterPath, QPixmap
from mutagen import File as MutagenFile
from mutagen.flac import Picture

from .constants import COVERS_DIR, THUMB_PX, THUMBS_DIR


def _make_thumbnail(src_file: str, thumb_file: str) -> bool:
    """Recorta al centro y reduce la carátula a THUMB_PX (QImage es seguro en hilos)."""
    img = QImage(src_file)
    if img.isNull():
        return False
    scaled = img.scaled(THUMB_PX, THUMB_PX, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation)
    x, y = (scaled.width() - THUMB_PX) // 2, (scaled.height() - THUMB_PX) // 2
    os.makedirs(THUMBS_DIR, exist_ok=True)
    return scaled.copy(QRect(x, y, THUMB_PX, THUMB_PX)).save(thumb_file, "JPG", 90)


def thumbnail_path(cover_path: str) -> str:
    """Miniatura de una carátula (se crea una sola vez); si falla, devuelve la original."""
    stem = os.path.splitext(os.path.basename(cover_path))[0]
    thumb = os.path.join(THUMBS_DIR, f"{stem}.jpg")
    if os.path.isfile(thumb) or _make_thumbnail(cover_path, thumb):
        return thumb
    return cover_path


def save_cover_to_cache(cover: bytes) -> str:
    """Guarda la carátula (y su miniatura) en ~/.cache/aly-music-player/covers."""
    if not cover:
        return ""
    try:
        os.makedirs(COVERS_DIR, exist_ok=True)
        digest = hashlib.sha256(cover).hexdigest()
        cover_file = os.path.join(COVERS_DIR, f"{digest}.png")
        if not os.path.exists(cover_file):
            img = QImage()
            if img.loadFromData(cover):
                img.save(cover_file, "PNG")
        if os.path.isfile(cover_file):
            thumbnail_path(cover_file)
            return cover_file
        return ""
    except Exception:
        return ""


def read_full_metadata(path: str, extract_cover: bool = True) -> dict:
    """Lee título, artista, álbum, género y carátula (bytes + caché en disco)."""
    stem = os.path.splitext(os.path.basename(path))[0]
    parent_name = os.path.basename(os.path.dirname(path))
    meta = {
        "path": path,
        "title": stem,
        "artist": "Artista desconocido",
        "album": parent_name or "Álbum desconocido",
        "genre": "Sin género",
        "cover_path": "",
        "cover_bytes": None,
    }
    try:
        audio = MutagenFile(path)
    except Exception:
        return meta
    if audio is None:
        return meta

    cover = None
    try:
        pics = getattr(audio, "pictures", None)          # FLAC
        if pics:
            cover = pics[0].data

        tags = audio.tags
        if tags is not None:
            if hasattr(tags, "getall"):                   # ID3 (MP3, WAV)
                def id3_first(*keys):
                    for k in keys:
                        vals = tags.getall(k)
                        if vals:
                            txt = str(vals[0]).strip()
                            if txt:
                                return txt
                    return ""

                meta["title"] = id3_first("TIT2") or meta["title"]
                meta["artist"] = id3_first("TPE1", "TPE2") or meta["artist"]
                meta["album"] = id3_first("TALB") or meta["album"]
                genre = id3_first("TCON")
                if genre:
                    meta["genre"] = genre.split(";")[0].split("/")[0].strip() or meta["genre"]
                apic = tags.getall("APIC")
                if apic and cover is None:
                    cover = apic[0].data
            else:                                         # Vorbis / MP4
                def get(key):
                    try:
                        return tags.get(key)
                    except Exception:
                        return None

                def first(*keys):
                    for k in keys:
                        v = get(k)
                        if v:
                            val = str(v[0] if isinstance(v, (list, tuple)) else v).strip()
                            if val:
                                return val
                    return ""

                meta["title"] = first("title", "TITLE", "\xa9nam") or meta["title"]
                meta["artist"] = first("artist", "ARTIST", "albumartist", "ALBUMARTIST", "\xa9ART", "aART") or meta["artist"]
                meta["album"] = first("album", "ALBUM", "\xa9alb") or meta["album"]
                genre = first("genre", "GENRE", "\xa9gen")
                if genre:
                    meta["genre"] = genre.split(";")[0].split("/")[0].strip() or meta["genre"]

                if cover is None:
                    covr = get("covr")
                    if covr:
                        cover = bytes(covr[0])
                if cover is None:
                    mbp = get("metadata_block_picture")
                    if mbp:
                        cover = Picture(base64.b64decode(mbp[0])).data
    except Exception as e:
        print(f"Metadatos incompletos en {os.path.basename(path)}: {e}")

    if cover:
        meta["cover_bytes"] = cover
        if extract_cover:
            meta["cover_path"] = save_cover_to_cache(cover)
    return meta


def rounded_cover_from_pixmap(src: QPixmap, size: int, radius: int, dpr: float) -> QPixmap | None:
    if src.isNull():
        return None
    px = max(1, int(round(size * dpr)))
    scaled = src.scaled(px, px, Qt.AspectRatioMode.KeepAspectRatioByExpanding,
                        Qt.TransformationMode.SmoothTransformation)
    out = QPixmap(px, px)
    out.fill(Qt.GlobalColor.transparent)

    painter = QPainter(out)
    painter.setRenderHints(QPainter.RenderHint.Antialiasing |
                           QPainter.RenderHint.SmoothPixmapTransform)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, px, px), radius * dpr, radius * dpr)
    painter.setClipPath(path)
    painter.drawPixmap((px - scaled.width()) // 2, (px - scaled.height()) // 2, scaled)
    painter.end()
    out.setDevicePixelRatio(dpr)
    return out


def rounded_cover(data: bytes, size: int, radius: int, dpr: float) -> QPixmap | None:
    """Recorta al centro, escala y redondea la carátula (nítida en pantallas HiDPI)."""
    src = QPixmap()
    if not src.loadFromData(data):
        return None
    return rounded_cover_from_pixmap(src, size, radius, dpr)


def placeholder_tile(text: str, size: int, radius: int, bg_hex: str, fg_hex: str, dpr: float) -> QPixmap:
    """Genera una miniatura elegante con inicial o nota musical para vistas de lista/galería."""
    px = max(1, int(round(size * dpr)))
    out = QPixmap(px, px)
    out.fill(Qt.GlobalColor.transparent)
    p = QPainter(out)
    p.setRenderHint(QPainter.RenderHint.Antialiasing)
    path = QPainterPath()
    path.addRoundedRect(QRectF(0, 0, px, px), radius * dpr, radius * dpr)
    p.setClipPath(path)
    p.fillRect(0, 0, px, px, QColor(bg_hex))
    p.setPen(QColor(fg_hex))
    font = p.font()
    font.setBold(True)
    font.setPixelSize(max(12, int(px * 0.42)))
    p.setFont(font)
    glyph = (text.strip()[:1].upper() if text and text.strip() else "♪")
    p.drawText(QRectF(0, 0, px, px), Qt.AlignmentFlag.AlignCenter, glyph)
    p.end()
    out.setDevicePixelRatio(dpr)
    return out
