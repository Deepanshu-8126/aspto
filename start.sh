#!/usr/bin/env bash
# Diya server start — ek command.
#   ./start.sh          server chalu karo
#   ./start.sh status   abhi kya chal raha hai
set -euo pipefail
cd "$(dirname "$0")"

[ -f .env ] && set -a && . ./.env && set +a
export KAGGLE_API_TOKEN="${KAGGLE_KEY:-${KAGGLE_API_TOKEN:-}}"
if [ -z "${KAGGLE_API_TOKEN}" ]; then
  echo "❌ .env me KAGGLE_KEY nahi mila"; exit 1
fi

st() { kaggle kernels status ukboy7u787/diya-rai-server 2>&1 | tail -1; }

if [ "${1:-start}" = "status" ]; then
  echo "server : $(st)"
  echo "train  : $(kaggle kernels status ukboy7u787/diya-rai-lora-train 2>&1 | tail -1)"
  exit 0
fi

cur="$(st)"
case "$cur" in
  *RUNNING*|*QUEUED*)
    echo "✅ Server already chal raha hai — Telegram pe prompt bhejo."; exit 0;;
esac

echo "🚀 Server start kar raha hoon..."
python3 scripts/push_kaggle.py server --force | grep -E "Kernel version|✅ http" || true
cat <<'MSG'

⏳ Model load hone me ~3-4 min lagenge.
   Taiyaar hote hi Telegram pe "Server ready" aayega.

   Phir:  /best   phir apna prompt
   Band:  /sleep   (ya 5 min idle pe khud band)
MSG
