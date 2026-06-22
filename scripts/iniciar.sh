#!/bin/bash
# Examen Digital Simple v2 - Script de inicio (Linux/Mac)
# Uso: bash scripts/iniciar.sh

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"
cd "$PROJECT_ROOT"

# Activar venv si existe
if [ -f "$PROJECT_ROOT/venv/bin/activate" ]; then
    source venv/bin/activate
fi

# Verificar dependencias
pip install -q -r requirements.txt 2>/dev/null

# Obtener IP de red para acceso desde otros dispositivos
IP=$(hostname -I | awk '{print $1}')

echo "=============================================="
echo "  SERVIDOR EXAMEN DIGITAL v2"
echo "=============================================="
echo ""
echo "  Acceso local:   http://localhost:8000"
echo "  Acceso red:     http://$IP:8000"
echo ""
echo "  Presiona Ctrl+C para detener"
echo "=============================================="

uvicorn backend.main:app --host 0.0.0.0 --port 8000 --reload
