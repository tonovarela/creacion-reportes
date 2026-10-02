#!/usr/bin/env sh
# Compila web/cliente/estilos.css → web/static/app.css con el binario standalone de Tailwind (sin Node).
# La primera vez descarga el binario a web/bin/ (ignorado en git).
#   web/tailwind.sh           compila minificado
#   web/tailwind.sh --watch   recompila al guardar cambios en web/cliente/
set -eu
DIR=$(cd "$(dirname "$0")" && pwd)
VERSION=${TAILWIND_VERSION:-v4.1.13}
BIN="$DIR/bin/tailwindcss-$VERSION"

if [ ! -x "$BIN" ]; then
  case "$(uname -s)" in Darwin) os=macos ;; Linux) os=linux ;; *) echo "Sistema no soportado: $(uname -s)"; exit 1 ;; esac
  case "$(uname -m)" in arm64|aarch64) arch=arm64 ;; x86_64|amd64) arch=x64 ;; *) echo "Arquitectura no soportada: $(uname -m)"; exit 1 ;; esac
  mkdir -p "$DIR/bin"
  echo "Descargando Tailwind $VERSION ($os-$arch)…"
  curl -fsSL -o "$BIN" "https://github.com/tailwindlabs/tailwindcss/releases/download/$VERSION/tailwindcss-$os-$arch"
  chmod +x "$BIN"
fi

cd "$DIR/cliente"
if [ "${1:-}" = "--watch" ]; then
  exec "$BIN" -i estilos.css -o ../static/app.css --watch
else
  "$BIN" -i estilos.css -o ../static/app.css --minify
fi
