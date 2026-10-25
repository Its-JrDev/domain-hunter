#!/usr/bin/env bash
set -e

# Resolver symlink para encontrar el directorio real del script
SOURCE="${BASH_SOURCE[0]}"
while [ -h "$SOURCE" ]; do
    DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"
    SOURCE="$(readlink "$SOURCE")"
    [[ $SOURCE != /* ]] && SOURCE="$DIR/$SOURCE"
done
SCRIPT_DIR="$(cd -P "$(dirname "$SOURCE")" && pwd)"

# Ejecutar vía uv si está disponible, o con python del entorno activo
if command -v uv >/dev/null 2>&1; then
    exec uv run --project "$SCRIPT_DIR" "$SCRIPT_DIR/main.py" "$@"
else
    exec python3 "$SCRIPT_DIR/main.py" "$@"
fi
