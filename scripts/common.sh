#!/usr/bin/env bash

PROJECT_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

project_python() {
  if [ -n "${PROJECT_PYTHON_BIN:-}" ]; then
    "$PROJECT_PYTHON_BIN" "$@"
    return
  fi

  if [ -n "${VIRTUAL_ENV:-}" ] && python -c "import openhands" >/dev/null 2>&1; then
    python "$@"
    return
  fi

  if command -v poetry >/dev/null 2>&1; then
    (
      cd "$PROJECT_ROOT"
      poetry run python "$@"
    )
    return
  fi

  if python -c "import openhands" >/dev/null 2>&1; then
    python "$@"
    return
  fi

  echo "Could not find a Python interpreter with the root OpenHands package installed." >&2
  echo "Run 'poetry install --with evaluation' from $PROJECT_ROOT or set PROJECT_PYTHON_BIN." >&2
  return 1
}
