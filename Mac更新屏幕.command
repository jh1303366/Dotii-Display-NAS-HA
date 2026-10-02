#!/bin/sh
set -eu
cd "$(dirname "$0")"
PYTHON_BIN="$(command -v python3)"
VENV_DIR="$(pwd)/.flash-venv"
if [ ! -x "$VENV_DIR/bin/python" ]; then
  "$PYTHON_BIN" -m venv "$VENV_DIR"
fi
"$VENV_DIR/bin/python" -m pip install --disable-pip-version-check 'esptool==4.8.1' 'pyserial==3.5'
"$VENV_DIR/bin/python" docker/flash_mac.py
printf '\n按回车关闭窗口。'
read answer
