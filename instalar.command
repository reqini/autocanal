#!/bin/bash
# Instalador de AutoCanal para macOS (correr una sola vez)
set -e
cd "$(dirname "$0")"
echo "== Instalando AutoCanal en $PWD =="
if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do [ -x $b ] && eval "$($b shellenv)"; done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Falta Homebrew. Pegá esto en la Terminal, esperá que termine y volvé a correr el instalador:"
  echo '/bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"'
  exit 1
fi
echo "• ffmpeg y python (Homebrew)…"
brew list ffmpeg >/dev/null 2>&1 || brew install ffmpeg
brew list python@3.12 >/dev/null 2>&1 || brew install python@3.12
PY="$(brew --prefix python@3.12)/bin/python3.12"
echo "• librerías de Python…"
[ -d .venv ] || "$PY" -m venv .venv
.venv/bin/pip install -q --upgrade pip
.venv/bin/pip install -q -r requirements.txt
chmod +x bin/autocanal instalar.command "AutoCanal Web.command"
xattr -dr com.apple.quarantine . 2>/dev/null || true
mkdir -p partidos
if ! grep -q "$PWD/bin" ~/.zshrc 2>/dev/null; then
  echo "export PATH=\"$PWD/bin:\$PATH\"" >> ~/.zshrc
  echo "• comando 'autocanal' agregado a la Terminal (abrí una ventana nueva para usarlo)"
fi
echo
read -p "¿Instalar whisper local (gratis, ~500 MB) para leer el relato y poner nombres en los shorts de deportes? [s/N] " w
if [[ "$w" =~ ^[sS] ]]; then
  brew list whisper-cpp >/dev/null 2>&1 || brew install whisper-cpp
  mkdir -p assets/modelos
  [ -f assets/modelos/ggml-small.bin ] || curl -L --fail -o assets/modelos/ggml-small.bin \
    https://huggingface.co/ggerganov/whisper.cpp/resolve/main/ggml-small.bin
fi
if [ ! -f client_secret.json ]; then
  CS=$(ls -t ~/Downloads/client_secret_*.json 2>/dev/null | head -1)
  if [ -n "$CS" ]; then cp "$CS" client_secret.json && echo "• Permiso de YouTube encontrado en Descargas y copiado ✔"; fi
fi
echo
echo "• Prueba rápida…"
./bin/autocanal prueba
echo
echo "✅ AutoCanal instalado. Próximo paso: editá config.json con el nombre de tus canales."
echo "   • Interfaz: doble clic en «AutoCanal Web.command» (o 'autocanal web')"
echo "   • Ayuda:    autocanal ayuda"
