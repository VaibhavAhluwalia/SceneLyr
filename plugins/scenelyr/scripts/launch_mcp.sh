#!/bin/zsh
set -e

SCENELYR_PLUGIN_DIR="${0:A:h:h}"
SCENELYR_REPOSITORY="${SCENELYR_PLUGIN_DIR:h:h}"
SCENELYR_VENV="$SCENELYR_REPOSITORY/.venv"

if [[ ! -f "$SCENELYR_REPOSITORY/pyproject.toml" ]]; then
  echo "SceneLyr repository could not be located from the plugin directory." >&2
  exit 2
fi

if [[ ! -x "$SCENELYR_VENV/bin/python" ]]; then
  SCENELYR_BOOTSTRAP_PYTHON="$(command -v python3)"
  if ! "$SCENELYR_BOOTSTRAP_PYTHON" -c 'import sys; raise SystemExit(sys.version_info < (3, 11))'; then
    echo "SceneLyr requires Python 3.11 or newer." >&2
    exit 3
  fi
  "$SCENELYR_BOOTSTRAP_PYTHON" -m venv "$SCENELYR_VENV"
fi

if ! "$SCENELYR_VENV/bin/python" -c 'import scenelyr, mcp' >/dev/null 2>&1; then
  "$SCENELYR_VENV/bin/python" -m pip install -e "$SCENELYR_REPOSITORY"
fi

cd "$SCENELYR_REPOSITORY"
exec "$SCENELYR_VENV/bin/python" -m scenelyr.mcp_server
