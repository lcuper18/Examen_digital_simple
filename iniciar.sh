#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Activar venv si existe
if [ -f "$SCRIPT_DIR/venv/bin/activate" ]; then
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
echo "  Acceso local:   http://localhost:8080"
echo "  Acceso red:     http://$IP:8080"
echo ""
echo "  Presiona Ctrl+C para detener"
echo "=============================================="

uvicorn main:app --host 0.0.0.0 --port 8080 --reload
