#!/usr/bin/env bash
# AI Video Stüdyo'yu başlatır ve tarayıcıda açar.
set -euo pipefail
cd "$(dirname "$0")"

if [[ ! -x .venv/bin/python ]]; then
  echo "Önce kurulum gerekli:  ./install.sh"
  exit 1
fi

PORT="${PORT:-8765}"
URL="http://127.0.0.1:${PORT}"

# Apple GPU'da desteklenmeyen nadir işlemler CPU'ya düşsün, hata vermesin
export PYTORCH_ENABLE_MPS_FALLBACK=1
# Hugging Face indirmelerinde gereksiz uyarıları kapat
export HF_HUB_DISABLE_TELEMETRY=1

( sleep 2; command -v open >/dev/null && open "$URL" ) &
echo "==> AI Video Stüdyo: $URL   (kapatmak için Ctrl+C)"
exec .venv/bin/python -m uvicorn app.server:app --host 127.0.0.1 --port "$PORT"
