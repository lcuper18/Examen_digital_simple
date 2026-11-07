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

Acceso local: http://localhost:8001 · Red: http://IP:8001 (el puerto se cambia con la variable `PORT` si se usa `python -m backend.main`)

## Configuración (variables de entorno)

| Variable | Uso |
|----------|-----|
| `PORT` | Puerto al ejecutar `python -m backend.main` (por defecto 8001). |
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

- **Resumen:** tablero con totales, alertas que requieren atención (intentos vencidos, muchas salidas de pestaña, logins bloqueados, claves temporales pendientes), quién está presentando examen ahora y actividad reciente.
- **Resultados:** lista de intentos con filtro por examen y sección, nota, estado (enviado / sin enviar), salidas de la pestaña y detalle pregunta por pregunta. Permite **reiniciar** un intento (el estudiante puede presentar el examen de nuevo) y exportar a CSV.
- **Notas:** por materia (sección y periodo), tabla editable **en puntos**, como en las hojas del docente. Por defecto: Trabajo cotidiano 25, Tareas 10, Prueba 01 22.5, Prueba 02 22.5, Proyecto 15 y Asistencia 5 (suman 100; se pueden cambiar por materia en **Ajustes**). La nota final se calcula al escribir (un componente vacío cuenta como 0). **Importar exámenes vinculados** copia la nota de los exámenes que, en la pestaña Exámenes, se vincularon a esa materia y componente (también se puede importar un código a mano). Exporta a CSV.

- **Estudiantes:** reinicio de contraseña (clave temporal aleatoria que se muestra una sola vez; el estudiante debe crear la suya), desbloqueo de login, activar/desactivar, cambio de sección, alta, baja, importación CSV y hoja imprimible de credenciales por sección.
- **Exámenes:** habilitar/deshabilitar, ventana de inicio y restricción por sección. Por intento: tiempo extra, cerrar y calificar, anular, marcar sospechoso y reiniciar. Las respuestas se guardan en el servidor mientras el estudiante responde.
- **Reportes:** boleta del estudiante, resultado por examen (estadísticas, distribución, rendimiento por tema, clasificación), preguntas críticas y notas por sección y periodo. Cada uno se imprime o guarda como PDF desde el navegador y se exporta a Excel.
- **Ajustes:** datos institucionales (institución, dirección regional, circuito, docente, curso lectivo), nota mínima de aprobación, ponderación por materia y las direcciones (IP y nombre `.local`) para que los estudiantes entren.
- **Bitácora:** registro de las acciones del docente (nunca guarda contraseñas).

Las materias se siembran en `backend/database.py` (`MATERIAS`).

## Códigos de examen

Se definen en `data/codigos.json` (código → archivo JSON, nombre y duración). Cada pregunta puede tener 3 o 4 opciones (a-c o a-d).
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

## Respaldos

Al arrancar y cada hora, el servidor guarda una copia de la base de datos por día en `respaldos/` (se conservan las últimas 30). La base usa el modo WAL, por lo que pueden aparecer archivos `examen_db.sqlite-wal` y `-shm` junto a ella.
