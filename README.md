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
- **Notas:** por materia (sección y periodo), tabla editable **en puntos**, como en las hojas del docente. Por defecto: Trabajo cotidiano 25, Tareas 10, Prueba 01 22.5, Prueba 02 22.5, Proyecto 15 y Asistencia 5 (suman 100; se pueden cambiar por materia en **Ajustes**). La nota final se calcula al escribir (un componente vacío cuenta como 0). **Importar exámenes vinculados** copia la nota de los exámenes que, en la pestaña Exámenes, se vincularon a esa materia y componente (también se puede importar un código a mano). **Importar hoja…** carga un CSV (`;`) o Excel en puntos (Id o Nombre, TC, Tareas, Prueba1, Prueba2, Proyecto, Asistencia). Exporta a CSV.

- **Estudiantes:** reinicio de contraseña (clave temporal aleatoria que se muestra una sola vez; el estudiante debe crear la suya), desbloqueo de login, activar/desactivar, cambio de sección, alta, baja, importación CSV y hoja imprimible de credenciales por sección.
- **Exámenes:** habilitar/deshabilitar, ventana de inicio y restricción por sección. Por intento: tiempo extra, cerrar y calificar, anular, marcar sospechoso y reiniciar. Las respuestas se guardan en el servidor mientras el estudiante responde.
- **Reportes:** boleta del estudiante, resultado por examen (estadísticas, distribución, rendimiento por tema, clasificación), preguntas críticas y notas por sección y periodo. Cada uno se imprime o guarda como PDF desde el navegador y se exporta a Excel.
  - **Acta de calificaciones:** con el formato oficial (Dirección Regional, circuito, centro educativo, docente, asignatura, nivel, sección, período; tabla Id, Nombre y Nota entera con redondeo escolar; línea de firma). Imprimir/PDF o Excel.
  - **Informe para encargados:** una hoja por estudiante (o de toda la sección) con los componentes en puntos, la nota, la asistencia, el detalle de actividades con la observación para el estudiante y las pendientes, y firmas del docente y del encargado. Nunca incluye la nota interna.
  - **Registro de notas (en puntos):** CSV (`;`, coma decimal) o Excel en el mismo formato de tus hojas; se puede volver a cargar con **Importar hoja…** en Notas.
  - El consolidado por sección ahora muestra el estado (Aprobado, Reprobó N o Incompleto).
- **Asistencia:** se pasa lista por fecha y materia (presente, ausente, tardía de menos o más de 10 min, ausencia y tardía justificadas, con observación). El porcentaje de ausencias injustificadas sobre las lecciones impartidas da los puntos de asistencia según el artículo 37 del Reglamento de Evaluación (0-<10 % = 5, <20 % = 4, <30 % = 3, <40 % = 2, <50 % = 1, desde 50 % = 0; tardía injustificada de menos de 10 min = media ausencia, de más de 10 min = una ausencia). Cada vez que se guarda o elimina una lista, el componente Asistencia de Notas se recalcula (si ya habías escrito ese componente a mano, se reemplaza desde la primera lista que guardes). Resumen del período, Excel e informe imprimible.
- **Actividades:** tareas, proyectos y otras actividades por materia, con rúbrica opcional (criterios con sus puntos). Se califica por criterio, con estado (entregado, tardío, sin entrega, en revisión, exonerado), observación para el estudiante y nota interna que nunca se muestra. El componente de Notas se calcula solo: puntos obtenidos entre los posibles de las actividades ya calificadas (sin entrega cuenta 0; en revisión y exonerado no cuentan). **Importar hoja (Excel)** carga hojas como `Calificacion_*.xlsx` (columnas de criterios con sus puntos entre paréntesis, Estado, Observaciones y Notas internas), emparejando por nombre.
- **Publicar a estudiantes (Notas):** por materia, el botón **Publicar a estudiantes** muestra a cada estudiante, en **Ver mis notas** (pantalla del código del examen), sus componentes en puntos, su nota, su asistencia y sus actividades con la observación para el estudiante. Cada estudiante solo ve lo suyo y solo de las materias publicadas de su sección; la nota interna nunca se muestra. **Ocultar a estudiantes** lo retira.
- **Seguimiento:** cada estudiante tiene una **Ficha** (botón en Estudiantes y en el Resumen) con teléfono, datos del encargado, adecuación, historial por materia, exámenes presentados y un registro de observaciones (anecdótico, logro, conducta, familia, apoyo) que solo ve el docente. **Importar encargados (Excel)** carga esos datos desde `Lista_Alumnos.xlsx` por cédula («NO posee» en ADECUACIÓN no cuenta como adecuación). El **Resumen** lista a los estudiantes en riesgo del período actual: nota proyectada bajo la mínima, ausencias injustificadas sobre el umbral, actividades sin entrega y exámenes vinculados sin presentar.
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

## Cierre del curso lectivo

En **Ajustes → Cierre del curso lectivo**: guarda en `respaldos/` una copia completa de la base (`cierre_<curso>_<fecha>.sqlite`) y un Excel con las notas finales, borra notas, asistencia, actividades, exámenes presentados, publicaciones y observaciones, pone el nuevo curso lectivo y el período 1, y desactiva (si lo indicas) a los estudiantes de las secciones que egresan. Se conservan estudiantes, materias, ponderaciones y exámenes. Requiere escribir CERRAR.

## Respaldos

Al arrancar y cada hora, el servidor guarda una copia de la base de datos por día en `respaldos/` (se conservan las últimas 30). La base usa el modo WAL, por lo que pueden aparecer archivos `examen_db.sqlite-wal` y `-shm` junto a ella.

## Abrir el sistema con un clic (Mac)

Para instalar la aplicación **Examen Digital** (una sola vez, o cada vez que cambie la versión):

```bash
bash scripts/mac/instalar_app.sh
```

Compila la app, la instala en Aplicaciones, crea el acceso directo en el Escritorio y la agrega al Dock. Al abrirla:
- muestra la **versión** del sistema (se define en `backend/version.py`);
- **levanta el servidor** (si ya había uno corriendo, lo usa y no lo apaga al salir);
- muestra la **dirección para los estudiantes** (`http://<IP>:8001`) con un código QR, el nombre `.local` y un botón para copiarla. Si la IP cambia al reconectarse al wifi, la ventana lo avisa y se actualiza sola;
- mantiene la Mac despierta mientras el servidor corre.

Botones: **Abrir panel docente**, **Ver registro** (`logs/servidor.log`) y **Detener servidor y salir**. Si cierras la ventana, el sistema se detiene (pide confirmación). Si macOS pregunta por conexiones entrantes de Python, permítelas.

## Apariencia

Panel docente: menú lateral agrupado (en tablet y celular es un cajón con el botón «Menú»), selector único de grupo, período y materia en la cabecera, pasar lista de un toque, hojas de notas con teclado (Enter y flechas) e inicio con accesos rápidos y primeros pasos. App del estudiante: formularios con etiquetas visibles, opciones del examen que se pueden usar con teclado y «Mis notas» pensado para el celular.

La plataforma sigue el tema claro u oscuro del dispositivo y tiene un botón (sol o luna) para cambiarlo; la preferencia se recuerda en el navegador. Los colores, espacios y tipografía viven en `frontend/css/base.css`.
