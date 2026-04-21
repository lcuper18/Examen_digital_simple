#!/usr/bin/env python3
"""
Servidor local simple para el Examen Digital.
Ejecuta: python3 servidor.py
Luego abre: http://localhost:8000
"""
import http.server
import socketserver
import webbrowser
import os

PORT = 8000
DIRECTORY = "."

class Handler(http.server.SimpleHTTPRequestHandler):
    def end_headers(self):
        self.send_header('Cache-Control', 'no-store, no-cache, must-revalidate')
        super().end_headers()

os.chdir(DIRECTORY)

with socketserver.TCPServer(("", PORT), Handler) as httpd:
    print(f"""
╔═══════════════════════════════════════════════════════════════╗
║           SERVIDOR LOCAL - EXAMEN DIGITAL                 ║
╠═══════════════════════════════════════════════════════════════╣
║                                                           ║
║  Servidor iniciado en:                                    ║
║                                                           ║
║    http://localhost:{PORT}                                 ║
║                                                           ║
║  Presiona Ctrl+C para detener el servidor                   ║
║                                                           ║
╚═══════════════════════════════════════════════════════════════╝
    """)
    
    # Abrir navegador automáticamente
    webbrowser.open(f"http://localhost:{PORT}")
    
    try:
        httpd.serve_forever()
    except KeyboardInterrupt:
        print("\n🛑 Servidor detenido")