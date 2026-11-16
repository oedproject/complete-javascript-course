#!/usr/bin/env bash
# AI Video Stüdyo — Mac kurulumu (tek seferlik)
set -euo pipefail
cd "$(dirname "$0")"

echo "==> AI Video Stüdyo kuruluyor"

if [[ "$(uname -s)" == "Darwin" && "$(uname -m)" != "arm64" ]]; then
  echo "!! Bu Mac Apple Silicon (M1/M2/M3/M4) değil. Uygulama çalışır ama AI çok yavaş olur."
fi

# uv: Python'u ve paketleri hızlıca kuran araç (Homebrew gerekmez)
if ! command -v uv >/dev/null 2>&1; then
  if [[ -x "$HOME/.local/bin/uv" ]]; then
    export PATH="$HOME/.local/bin:$PATH"
  else
    echo "==> uv kuruluyor"
    curl -LsSf https://astral.sh/uv/install.sh | sh
    export PATH="$HOME/.local/bin:$PATH"
  fi
fi

echo "==> Python 3.11 ortamı hazırlanıyor (.venv)"
uv venv --python 3.11 .venv
uv pip install --python .venv/bin/python -r requirements.txt

if [[ "${1:-}" == "--no-ai" ]]; then
  echo "==> AI paketleri atlandı (test modu)"
else
  echo "==> AI paketleri kuruluyor (PyTorch, Diffusers…) — birkaç dakika sürebilir"
  uv pip install --python .venv/bin/python -r requirements-ai.txt
fi

chmod +x start.sh
echo
echo "✅ Kurulum tamam. Başlatmak için:  ./start.sh"
echo "   (İlk kare üretiminde görsel modeli ~7 GB indirilir; sonra internetsiz çalışır.)"
