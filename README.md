# Examen Digital Simple v2

Plataforma de examen digital con login de estudiantes, calificación en el servidor y registro de intentos.

## Requisitos

- Python 3.10+
- Dependencias en `requirements.txt` (fastapi, uvicorn, bcrypt)

## Instalación

```bash
python3 -m venv .venv
source .venv/bin/activate      # Windows: .venv\Scripts\activate
pip install -r requirements.txt
```

### Lista de estudiantes

Los datos personales **no** están en el repositorio. Crea `data/estudiantes.csv`
(ignorado por git) siguiendo `data/estudiantes.example.csv`:

```
cedula,nombre,apellido1,apellido2,seccion
```

Se carga al crear la base de datos (`examen_db.sqlite`). Usuario: `primernombre.apellido1`
en minúsculas; contraseña: 3 primeras letras del primer nombre en mayúsculas + últimos 4 dígitos de la cédula.
Las contraseñas se guardan con bcrypt.

## Iniciar el servidor

```bash
bash scripts/iniciar.sh      # Linux/Mac
scripts\iniciar.bat          # Windows
```

Acceso local: http://localhost:8000 · Red: http://IP:8000

## Configuración (variables de entorno)

| Variable | Uso |
|----------|-----|
| `DOCENTE_PASSWORD_HASH` | Hash de la contraseña del docente (SHA-256 hexadecimal o bcrypt). Si no se define, se usa un valor por defecto: **cámbialo antes de usarlo en producción**. |
| `EXAMEN_SECRET_KEY` | Clave para firmar sesiones. Si no existe, se genera en `.secret_key`. |
| `ESTUDIANTES_CSV` | Ruta alternativa al CSV de estudiantes. |

## Cómo funciona un examen

1. El estudiante inicia sesión y escribe el código del examen.
2. El servidor crea el intento, baraja preguntas (dentro de cada tema) y opciones, y calcula el tiempo restante. **Nunca envía las respuestas correctas.**
3. Al enviar, el servidor califica y cierra el intento (uno por estudiante y examen).
4. El docente ve nota y detalle en el panel docente (`/docente`) o con "Acceso docente" al terminar el examen.

## Panel docente (`/docente`)

Se entra con la contraseña del docente.

- **Resultados:** lista de intentos con filtro por examen y sección, nota, estado (enviado / sin enviar), salidas de la pestaña y detalle pregunta por pregunta. Permite **reiniciar** un intento (el estudiante puede presentar el examen de nuevo) y exportar a CSV.
- **Notas:** por materia (sección y periodo), tabla editable con Trabajo cotidiano 25 %, Tareas 10 %, Prueba 01 20 %, Prueba 02 25 %, Proyecto 15 % y Asistencia 5 %. La nota final se calcula al escribir (un componente vacío cuenta como 0). **Importar Prueba 01/02** copia la nota (0-100) de los intentos enviados de un examen. Exporta a CSV.

Las materias se siembran en `backend/database.py` (`MATERIAS`).

## Códigos de examen

Se definen en `data/codigos.json` (código → archivo JSON, nombre y duración).
Vigentes: ver ese archivo; los exámenes antiguos quedan como histórico.

## Tests

```bash
pip install -r requirements-dev.txt
python -m pytest -q
```

## Estructura

```
backend/        FastAPI: main.py, database.py, security.py, ratelimit.py, barajado.py, routes/
frontend/       index.html, css/, js/app.js, fonts/, static/
data/           codigos.json, examenes/*.json, estudiantes.example.csv
scripts/        iniciar.sh, iniciar.bat
tests/          pytest
```
