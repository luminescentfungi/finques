#!/usr/bin/env bash
# run.sh — convenience wrapper that activates .venv before running main.py
# Usage: ./run.sh --max-price 1000
#        ./run.sh --max-price 1000 --loop

DIR="$(cd "$(dirname "$0")" && pwd)"

if [ ! -d "$DIR/.venv" ]; then
    echo "No .venv found. Creating it..."
    python3 -m venv "$DIR/.venv"
    "$DIR/.venv/bin/pip" install -q --upgrade pip
    "$DIR/.venv/bin/pip" install -q -r "$DIR/requirements.txt"
    "$DIR/.venv/bin/playwright" install chromium
fi

source "$DIR/.venv/bin/activate"
exec python3 "$DIR/main.py" "$@"
