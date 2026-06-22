# Examen Digital Simple v2

Plataforma de examen digital con login de estudiantes y registro de intentos.

## Requisitos

- Python 3.10+
- fastapi
- uvicorn[standard]
- aiosqlite
- PyMuPDF

## Instalación

1. Crear entorno virtual:
```bash
python -m venv venv
source venv/bin/activate  # Linux/Mac
venv\Scripts\activate     # Windows
```

2. Instalar dependencias:
```bash
pip install -r requirements.txt
```

## Iniciar el servidor

### Linux/Mac:
```bash
bash scripts/iniciar.sh
```

### Windows:
```bash
scripts\iniciar.bat
```

## Códigos de Examen

| Código | Examen |
|--------|---------|
| CCS01 | Control de Calidad del Software |
| EMP01 | Emprendimiento |
| ADM01 | Administración y Soporte a Computadoras Portátiles |
| RED01 | Introducción a las Redes |
| PER01 | Mantenimiento y Reparación de Dispositivos Periféricos |

## Acceso

- **Local:** http://localhost:8000
- **Red:** http://IP:8000

## Contraseña Docente

La contraseña por defecto es: `docente2026`

Para cambiarla, modifica el hash en `backend/routes/auth.py`.

## Estructura del Proyecto

```
├── backend/
│   ├── __init__.py
│   ├── main.py           # FastAPI app
│   ├── database.py        # SQLite connection
│   ├── models.py         # Pydantic models
│   └── routes/
│       ├── __init__.py
│       ├── auth.py       # Login endpoints
│       ├── examenes.py   # Exam endpoints
│       └── intentos.py   # Attempt endpoints
├── frontend/
│   ├── index.html       # Main HTML
│   ├── css/
│   │   └── styles.css   # All styles
│   └── js/
│       └── app.js        # All JavaScript
├── data/
│   ├── codigos.json     # Exam code mappings
│   └── examenes/        # Exam JSON files
├── fonts/               # Self-hosted fonts
├── static/              # Static assets
├── scripts/              # Startup scripts
├── requirements.txt
└── .gitignore
```
