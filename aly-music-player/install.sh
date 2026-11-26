#!/usr/bin/env bash
# Instalador de Aly Music Player (Linux / Hyprland) — instalación por usuario, sin root
# salvo para instalar paquetes del sistema (mpv/ffmpeg).
#
#   ./install.sh                  instala o actualiza
#   ./install.sh --skip-system-deps   no toca paquetes del sistema
#   ./install.sh --uninstall      desinstala (conserva tus datos)
#   ./install.sh --uninstall --purge  desinstala y borra configuración, favoritos y caché
set -euo pipefail

APP_ID="aly-music-player"
APP_NAME="Aly Music Player"
SRC="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

DATA_HOME="${XDG_DATA_HOME:-$HOME/.local/share}"
PREFIX="$DATA_HOME/$APP_ID"
BIN_DIR="$HOME/.local/bin"
LAUNCHER="$BIN_DIR/$APP_ID"
DESKTOP_FILE="$DATA_HOME/applications/$APP_ID.desktop"
ICON_FILE="$DATA_HOME/icons/hicolor/scalable/apps/$APP_ID.svg"

PY_PACKAGES=(PyQt6 python-mpv mutagen numpy dbus-next)

say()  { printf '\033[1;34m==>\033[0m %s\n' "$*"; }
warn() { printf '\033[1;33m!!\033[0m  %s\n' "$*" >&2; }
die()  { printf '\033[1;31mxx\033[0m  %s\n' "$*" >&2; exit 1; }

usage() { sed -n '2,8p' "${BASH_SOURCE[0]}" | sed 's/^# \{0,1\}//'; }

SKIP_SYSTEM=0; UNINSTALL=0; PURGE=0
for arg in "$@"; do
  case "$arg" in
    --skip-system-deps) SKIP_SYSTEM=1 ;;
    --uninstall) UNINSTALL=1 ;;
    --purge) PURGE=1 ;;
    -h|--help) usage; exit 0 ;;
    *) die "Opción desconocida: $arg (usa --help)" ;;
  esac
done

refresh_desktop_caches() {
  command -v update-desktop-database >/dev/null && update-desktop-database "$DATA_HOME/applications" 2>/dev/null || true
  command -v gtk-update-icon-cache  >/dev/null && gtk-update-icon-cache -qtf "$DATA_HOME/icons/hicolor" 2>/dev/null || true
}

# ------------------------------------------------------------------ desinstalar
if [[ $UNINSTALL -eq 1 ]]; then
  say "Desinstalando $APP_NAME…"
  rm -rf "$PREFIX"
  rm -f "$LAUNCHER" "$DESKTOP_FILE" "$ICON_FILE"
  refresh_desktop_caches
  if [[ $PURGE -eq 1 ]]; then
    rm -rf "$HOME/.config/omatunes" "$HOME/.cache/$APP_ID"
    say "Configuración, favoritos y caché eliminados."
  else
    say "Tus datos se conservaron (~/.config/omatunes). Usa --purge para borrarlos."
  fi
  exit 0
fi

# ------------------------------------------------------------------ comprobaciones
[[ -f "$SRC/Aly_Music_Player.py" && -d "$SRC/aly_player" ]] \
  || die "No encuentro Aly_Music_Player.py y la carpeta aly_player/ junto a install.sh."
[[ $EUID -ne 0 ]] || die "No lo ejecutes como root: se instala solo para tu usuario."

# ------------------------------------------------------------------ paquetes del sistema
install_system_deps() {
  local sudo=""
  command -v sudo >/dev/null && sudo="sudo"
  if command -v pacman >/dev/null; then
    say "Instalando dependencias del sistema (pacman)…"
    $sudo pacman -S --needed --noconfirm mpv ffmpeg python python-pip
  elif command -v apt-get >/dev/null; then
    say "Instalando dependencias del sistema (apt)…"
    $sudo apt-get update
    $sudo apt-get install -y ffmpeg python3 python3-venv python3-pip \
      libegl1 libxkbcommon0 libdbus-1-3 libfontconfig1 libglib2.0-0
    $sudo apt-get install -y libmpv2 || $sudo apt-get install -y libmpv1
  elif command -v dnf >/dev/null; then
    say "Instalando dependencias del sistema (dnf)…"
    $sudo dnf install -y mpv-libs ffmpeg-free python3 python3-pip
  elif command -v zypper >/dev/null; then
    say "Instalando dependencias del sistema (zypper)…"
    $sudo zypper --non-interactive install libmpv2 ffmpeg python3 python3-pip
  else
    warn "Gestor de paquetes no reconocido. Instala a mano: libmpv (mpv), ffmpeg, python3 con venv y pip."
  fi
}

if [[ $SKIP_SYSTEM -eq 0 ]]; then
  install_system_deps || warn "No se pudieron instalar los paquetes del sistema; continúo con el resto."
else
  say "Omitiendo paquetes del sistema (--skip-system-deps)."
fi

command -v python3 >/dev/null || die "Falta python3."

# ------------------------------------------------------------------ copiar la aplicación
say "Copiando archivos a $PREFIX…"
mkdir -p "$PREFIX/app" "$BIN_DIR" "$(dirname "$DESKTOP_FILE")" "$(dirname "$ICON_FILE")"
rm -rf "$PREFIX/app/aly_player"
cp -r "$SRC/aly_player" "$PREFIX/app/aly_player"
cp "$SRC/Aly_Music_Player.py" "$PREFIX/app/Aly_Music_Player.py"
find "$PREFIX/app" -name __pycache__ -prune -exec rm -rf {} +
cp "$SRC/$APP_ID.svg" "$ICON_FILE"

# ------------------------------------------------------------------ entorno de Python
if [[ ! -x "$PREFIX/venv/bin/python" ]]; then
  say "Creando entorno virtual de Python…"
  python3 -m venv "$PREFIX/venv" || die "No se pudo crear el entorno (en Debian/Ubuntu instala python3-venv)."
fi
say "Instalando dependencias de Python (${PY_PACKAGES[*]})…"
"$PREFIX/venv/bin/python" -m pip install --quiet --upgrade pip
"$PREFIX/venv/bin/python" -m pip install --quiet --upgrade "${PY_PACKAGES[@]}"

# ------------------------------------------------------------------ lanzador y entrada de menú
say "Creando lanzador y acceso en el menú de aplicaciones…"
cat > "$LAUNCHER" <<LAUNCH
#!/usr/bin/env bash
exec "$PREFIX/venv/bin/python" "$PREFIX/app/Aly_Music_Player.py" "\$@"
LAUNCH
chmod +x "$LAUNCHER"

cat > "$DESKTOP_FILE" <<DESKTOP
[Desktop Entry]
Type=Application
Name=$APP_NAME
GenericName=Reproductor de música
Comment=Reproductor de música con colores de Pywal y controles MPRIS
Exec=$LAUNCHER
Icon=$APP_ID
Terminal=false
Categories=AudioVideo;Audio;Player;Qt;
Keywords=música;audio;mp3;flac;player;
StartupWMClass=$APP_ID
DESKTOP
refresh_desktop_caches

# ------------------------------------------------------------------ verificación
say "Verificando la instalación…"
if QT_QPA_PLATFORM=offscreen "$PREFIX/venv/bin/python" -c \
   "import sys; sys.path.insert(0, '$PREFIX/app'); import aly_player.window" 2>/tmp/aly-install-check.log; then
  say "Todo correcto."
else
  warn "La aplicación se copió, pero al importarla hubo un error (¿falta libmpv?):"
  sed 's/^/    /' /tmp/aly-install-check.log >&2
fi

case ":$PATH:" in
  *":$BIN_DIR:"*) ;;
  *) warn "$BIN_DIR no está en tu PATH; añade esto a tu shell:  export PATH=\"\$HOME/.local/bin:\$PATH\"" ;;
esac

cat <<DONE

$APP_NAME instalado.
  Ejecutar:     $APP_ID           (o búscalo en tu lanzador: rofi/wofi/fuzzel…)
  Hyprland:     bind = SUPER, M, exec, $APP_ID
  Actualizar:   vuelve a ejecutar ./install.sh
  Desinstalar:  ./install.sh --uninstall   (añade --purge para borrar tus datos)
DONE
