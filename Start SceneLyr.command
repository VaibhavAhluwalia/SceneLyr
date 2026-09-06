#!/bin/zsh
set -e

SCENELYR_REPO_DIR="${0:A:h}"
SCENELYR_APP_DIR="$HOME/Library/Application Support/SceneLyr"
SCENELYR_VENV_DIR="$SCENELYR_APP_DIR/venv"
SCENELYR_URL="http://127.0.0.1:8765"
SCENELYR_BOOTSTRAP_PYTHON="$(command -v python3)"

mkdir -p "$SCENELYR_APP_DIR"

if /usr/bin/curl --silent --fail "$SCENELYR_URL/health" >/dev/null 2>&1; then
  /usr/bin/open "$SCENELYR_URL"
  exit 0
fi

if [[ ! -x "$SCENELYR_VENV_DIR/bin/python" ]]; then
  echo "Preparing SceneLyr for the first time…"
  if ! "$SCENELYR_BOOTSTRAP_PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    /usr/bin/osascript -e 'display dialog "SceneLyr needs Python 3.11 or newer." buttons {"OK"} default button "OK" with icon caution'
    exit 1
  fi
  "$SCENELYR_BOOTSTRAP_PYTHON" -m venv "$SCENELYR_VENV_DIR"
  "$SCENELYR_VENV_DIR/bin/python" -m pip install --upgrade pip
fi

if ! "$SCENELYR_VENV_DIR/bin/python" -c 'import scenelyr, fastapi, cv2, pptx, mcp' >/dev/null 2>&1; then
  echo "Installing SceneLyr…"
  "$SCENELYR_VENV_DIR/bin/python" -m pip install -e "$SCENELYR_REPO_DIR"
fi

echo "SceneLyr is opening in your browser. Keep this window open while you use it."
(sleep 1; /usr/bin/open "$SCENELYR_URL") &
cd "$SCENELYR_REPO_DIR"
exec "$SCENELYR_VENV_DIR/bin/python" -m uvicorn scenelyr.api:app --host 127.0.0.1 --port 8765
