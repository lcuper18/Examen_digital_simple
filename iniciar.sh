#!/bin/bash
cd /home/dw/workspace/Examen_digital_simple
python3 -m http.server 8080 -b 0.0.0.0 > /dev/null 2>&1 &
echo "Servidor iniciado en http://0.0.0.0:8080"
echo "Desde otro dispositivo accede a: http://192.168.8.108:8080"