#!/bin/sh
set -eu

uv run pytest
uv run tradukens translate hola
uv run tradukens savings "arregla este bug sin cambiar la API pública" --json
uv run tradukens doctor
