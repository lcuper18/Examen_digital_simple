#!/bin/bash
# Examen Digital Simple v2 - Script de inicio (Linux/Mac)
# Uso: bash scripts/iniciar.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Activar venv si existe (.venv o venv)
for VENV in .venv venv; do
    if [ -f "$PROJECT_ROOT/$VENV/bin/activate" ]; then
        source "$PROJECT_ROOT/$VENV/bin/activate"
        break
    fi
done

# Verificar dependencias
pip install -q -r requirements.txt || { echo "Error instalando dependencias"; exit 1; }

# Obtener IP de red para acceso desde otros dispositivos
IP=$(hostname -I 2>/dev/null | awk '{print $1}')
[ -z "$IP" ] && IP=$(ipconfig getifaddr en0 2>/dev/null)
[ -z "$IP" ] && IP=localhost

echo "=============================================="
VERSION=$(python3 -c "from backend.version import VERSION; print(VERSION)" 2>/dev/null || echo "?")
echo "  EXAMEN DIGITAL  ·  versión $VERSION"
echo "=============================================="
echo ""
echo "  Acceso local:   http://localhost:8001"
echo "  Acceso red:     http://$IP:8001"
echo ""
echo "  Presiona Ctrl+C para detener"
echo "=============================================="

uvicorn backend.main:app --host 0.0.0.0 --port 8001
