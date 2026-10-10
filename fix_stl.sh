#!/bin/sh
# Wrapper per Platypus: trova python3 e fix_stl.py (bundled) e li esegue
# sui file trascinati sull'app.

DIR="$(cd "$(dirname "$0")" && pwd)"

PYTHON=$(command -v python3)
if [ -z "$PYTHON" ]; then
  # fallback per Homebrew su Apple Silicon / Intel
  for p in /opt/homebrew/bin/python3 /usr/local/bin/python3 /usr/bin/python3; do
    if [ -x "$p" ]; then PYTHON="$p"; break; fi
  done
fi

if [ -z "$PYTHON" ]; then
  echo "python3 non trovato. Installalo da python.org o con 'brew install python3'."
  exit 1
fi

exec "$PYTHON" "$DIR/fix_stl.py" "$@"
