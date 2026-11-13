# Lectiva

Plataforma de gestión educativa: exámenes en línea, asistencia, actividades, notas por componente, reportes e informes, con panel docente y app del estudiante. (Antes «Examen Digital».)

## Requisitos

- Python 3.10+
- Dependencias en `requirements.txt` (fastapi, uvicorn, bcrypt, openpyxl)

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

Acceso local: http://localhost:8090 · Red: http://IP:8090 (el puerto se cambia con la variable `PORT` si se usa `python -m backend.main`)

## Configuración (variables de entorno)

| Variable | Uso |
|----------|-----|
| `PORT` | Puerto al ejecutar `python -m backend.main` (por defecto 8090). |
| `DOCENTE_PASSWORD_HASH` | Opcional. Hash (SHA-256 hexadecimal o bcrypt) de la contraseña inicial del docente. Normalmente no se usa: la contraseña se cambia desde **Ajustes** y se guarda cifrada en la base. |
| `EXAMEN_SECRET_KEY` | Clave para firmar sesiones. Si no existe, se genera en `.secret_key`. |
| `ESTUDIANTES_CSV` | Ruta alternativa al CSV de estudiantes. |

## Cómo funciona un examen

1. El estudiante inicia sesión (los estudiantes nuevos deben crear su propia contraseña) y escribe el código del examen.
2. El servidor crea el intento, baraja preguntas (dentro de cada tema) y opciones, y calcula el tiempo restante. **Nunca envía las respuestas correctas.**
3. Al enviar, el servidor califica y cierra el intento (uno por estudiante y examen). Si se cae la red, la app reintenta el envío sola (cada 5 segundos y apenas vuelve el wifi) sin perder las respuestas; un doble envío no cambia la nota. Si el estudiante recarga la página o vuelve a entrar a medias, la pantalla del código le ofrece **Continuar mi examen** con sus respuestas guardadas y el tiempo que le queda.
4. El docente ve nota y detalle en el panel docente (`/docente`) o con "Acceso docente" al terminar el examen.

## Panel docente (`/docente`)

Se entra con la contraseña del docente. Mientras se use la contraseña de fábrica (que es pública, está en el código del proyecto), el panel muestra un aviso fijo con **Cambiar ahora**; también se cambia en **Ajustes → Contraseña del docente** (mínimo 8 caracteres, se guarda con bcrypt).

- **Resumen:** tablero con totales, alertas que requieren atención (intentos vencidos, muchas salidas de pestaña, logins bloqueados, claves temporales pendientes), quién está presentando examen ahora y actividad reciente.
- **Resultados:** lista de intentos con búsqueda por estudiante, filtro por examen, sección y estado, paginación (25 por página), nota, salidas de la pestaña y detalle pregunta por pregunta. El menú «⋯» de cada fila permite dar tiempo extra, cerrar y calificar, anular, marcar como sospechoso y **reiniciar** el intento (el estudiante puede presentar el examen de nuevo). Exporta a CSV.
- **Notas:** por materia (sección y periodo), tabla editable **en puntos**, como en las hojas del docente. Por defecto: Trabajo cotidiano 25, Tareas 10, Prueba 01 22.5, Prueba 02 22.5, Proyecto 15 y Asistencia 5 (suman 100; se pueden cambiar por materia en **Ajustes**). La nota final se calcula al escribir (un componente vacío cuenta como 0). El menú **Importar / exportar** agrupa las acciones: *Notas de los exámenes vinculados…* copia la nota de los exámenes que, en la pestaña Exámenes, se vincularon a esa materia y componente (pide confirmación porque **reemplaza** lo que haya en Prueba 1 y 2, incluidos los ajustes manuales); *Un examen como prueba…* importa un examen elegido de la lista como Prueba 1 o Prueba 2; *Hoja de notas (Excel o CSV)…* carga un CSV (`;`) o Excel en puntos (Id o Nombre, TC, Tareas, Prueba1, Prueba2, Proyecto, Asistencia); y *Descargar notas en CSV* exporta a Excel.

- **Estudiantes:** **Pedir cambio de clave** a un grupo (cada estudiante crea su propia clave la próxima vez que entre, sin cambiarle la actual; no lo hagas durante un examen), reinicio de contraseña (clave temporal aleatoria que se muestra una sola vez; el estudiante debe crear la suya), desbloqueo de login, activar/desactivar, cambio de sección, alta, baja, importación CSV y hoja imprimible de credenciales por sección.
- **Exámenes:** habilitar/deshabilitar (quienes ya lo iniciaron pueden terminarlo), ventana de inicio y restricción por sección. En **Configurar…** se vincula el examen a las notas de **una o varias materias** (por período, con el componente Prueba 1 o Prueba 2 de cada una); la columna «Va a las notas de» muestra el vínculo y avisa si falta («Sin vincular»). Cada materia importa solo a los estudiantes de su grupo. **Cerrar y calificar los N en curso…** cierra todos los intentos abiertos de un examen y los califica con lo que tengan guardado (útil al terminar la clase). Por intento: tiempo extra, cerrar y calificar, anular, marcar sospechoso y reiniciar. Las respuestas se guardan en el servidor mientras el estudiante responde.
- **Reportes:** boleta del estudiante (ver abajo), resultado por examen (estadísticas, distribución, rendimiento por tema, clasificación), preguntas críticas y notas por sección y periodo. Cada uno se imprime o guarda como PDF desde el navegador y se exporta a Excel.
  - **Boleta del estudiante:** sigue el grupo elegido arriba (solo lista a los estudiantes de ese grupo). Se elige el **período**: 1.º, 2.º o **General** (todos los períodos), que agrega la tabla **Nota anual** (promedio simple de los períodos). Cada componente se muestra **en puntos sobre lo que vale** (por ejemplo `20 /25`), no en escala de 0 a 100. Los exámenes se asignan al período de la materia a la que están vinculados o, si no hay vínculo, por el sufijo del código (`EMP02` → 2.º período). El Excel respeta el período y, en General, agrega la hoja «Nota anual».
  - **Acta de calificaciones:** con el formato oficial (Dirección Regional, circuito, centro educativo, docente, asignatura, nivel, sección, período; tabla Id, Nombre y Nota entera con redondeo escolar; línea de firma). Imprimir/PDF o Excel.
  - **Informe para encargados:** una hoja por estudiante (o de toda la sección) con los componentes en puntos, la nota, la asistencia, el detalle de actividades con la observación para el estudiante y las pendientes, y firmas del docente y del encargado. Nunca incluye la nota interna.
  - **Notas para el sistema del colegio (plantilla):** subes la plantilla CSV que entrega el colegio (Id = cédula, Nombre, Trabajo cotidiano, Tareas, Prueba, Proyecto, Asistencia) y Lectiva la rellena con la materia elegida arriba: puntos con **punto decimal** y hasta 2 decimales, **Prueba = Prueba 1 + Prueba 2**, 0 en lo no calificado. Respeta el orden, los nombres, el separador, el BOM y los finales de línea de la plantilla, y avisa qué estudiantes tienen componentes sin calificar, cuáles de la plantilla no están en Lectiva y cuáles de Lectiva faltan en la plantilla. El archivo se sube tal cual (abrirlo y guardarlo en Excel puede cambiar los decimales).
  - **Registro de notas (en puntos):** CSV (`;`, coma decimal) o Excel en el mismo formato de tus hojas; se puede volver a cargar con *Hoja de notas (Excel o CSV)…* en Notas.
  - El consolidado por sección ahora muestra el estado (Aprobado, Reprobó N o Incompleto).
- **Asistencia:** se pasa lista por fecha y materia (presente, ausente, tardía de menos o más de 10 min, ausencia y tardía justificadas, con observación). El porcentaje de ausencias injustificadas sobre las lecciones impartidas da los puntos de asistencia según el artículo 37 del Reglamento de Evaluación (0-<10 % = 5, <20 % = 4, <30 % = 3, <40 % = 2, <50 % = 1, desde 50 % = 0; tardía injustificada de menos de 10 min = media ausencia, de más de 10 min = una ausencia). Cada vez que se guarda o elimina una lista, el componente Asistencia de Notas se recalcula (si ya habías escrito ese componente a mano, se reemplaza desde la primera lista que guardes). Resumen del período, Excel e informe imprimible.
- **Actividades:** tareas, proyectos y otras actividades por materia, con rúbrica opcional (criterios con sus puntos). Se califica por criterio, con estado (entregado, tardío, sin entrega, en revisión, exonerado), observación para el estudiante y nota interna que nunca se muestra. El componente de Notas se calcula solo: puntos obtenidos entre los posibles de las actividades ya calificadas (sin entrega cuenta 0; en revisión y exonerado no cuentan). **Importar hoja (Excel)** carga hojas como `Calificacion_*.xlsx` (columnas de criterios con sus puntos entre paréntesis, Estado, Observaciones y Notas internas), emparejando por nombre.
- **Mis notas para estudiantes (publicación en Notas):** por materia, el interruptor «Visible / Oculta para los estudiantes» muestra a cada estudiante, en **Ver mis notas** (pantalla del código del examen), sus componentes en puntos, su nota, su asistencia y sus actividades con la observación para el estudiante. Cada estudiante solo ve lo suyo y solo de las materias publicadas de su sección; la nota interna nunca se muestra. Apagar el interruptor lo retira.
- **Seguimiento:** cada estudiante tiene una **Ficha** (botón en Estudiantes y en el Resumen) con teléfono, datos del encargado, adecuación, historial por materia, exámenes presentados y un registro de observaciones (anecdótico, logro, conducta, familia, apoyo) que solo ve el docente. **Importar encargados (Excel)** carga esos datos desde `Lista_Alumnos.xlsx` por cédula («NO posee» en ADECUACIÓN no cuenta como adecuación). El **Resumen** lista a los estudiantes en riesgo del período actual: nota proyectada bajo la mínima, ausencias injustificadas sobre el umbral, actividades sin entrega y exámenes vinculados sin presentar.
- **Ajustes:** datos institucionales (institución, dirección regional, circuito, docente, curso lectivo), nota mínima de aprobación, ponderación por materia, la copia de respaldo externa, la contraseña del docente y las direcciones (IP y nombre `.local`) para que los estudiantes entren. Esta pestaña está disponible aunque todavía no haya materias. Si cambias de pestaña o cierras la página con cambios sin guardar (notas, asistencia o calificaciones), Lectiva avisa antes de perderlos.
- **Bitácora:** registro de las acciones del docente (nunca guarda contraseñas), con búsqueda, filtro por acción y paginación.

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
backend/        FastAPI: main.py, database.py, security.py, ratelimit.py, barajado.py, version.py, routes/
frontend/       index.html (estudiante), docente.html (panel docente), css/, js/app.js, js/docente/ (un módulo por pestaña), fonts/, static/
data/           codigos.json, examenes/*.json, estudiantes.example.csv
mac/            app de Mac en Swift (Lectiva.swift) y su icono (icono.swift)
scripts/        iniciar.sh, iniciar.bat, mac/instalar_app.sh
respaldos/      copias de la base de datos (no se sube a git)
logs/           servidor.log de la app de Mac (no se sube a git)
tests/          pytest
.claude/skills/ crear-examen-digital: elabora exámenes para la plataforma
```

## Cierre del curso lectivo

En **Ajustes → Cierre del curso lectivo**: guarda en `respaldos/` una copia completa de la base (`cierre_<curso>_<fecha>.sqlite`) y un Excel con las notas finales, borra notas, asistencia, actividades, exámenes presentados, publicaciones y observaciones, pone el nuevo curso lectivo y el período 1, y desactiva (si lo indicas) a los estudiantes de las secciones que egresan. Se conservan estudiantes, materias, ponderaciones y exámenes. Requiere escribir CERRAR.

## Respaldos

- **Integridad:** la base hace cumplir las claves foráneas, así que no pueden quedar datos sueltos de un estudiante eliminado. Las cargas de archivos (hojas de notas, listas, plantillas) se limitan a 5 MB.
- **Copia local:** al arrancar y cada hora, el servidor guarda una copia de la base de datos por día en `respaldos/` (se conservan las últimas 30). La base usa el modo WAL, por lo que pueden aparecer archivos `examen_db.sqlite-wal` y `-shm` junto a ella.
- **Copia externa (recomendada):** en **Ajustes → Copia de respaldo externa** eliges una carpeta fuera del computador (iCloud Drive, un disco externo o una memoria USB; Lectiva sugiere las que encuentra). Lectiva crea ahí la carpeta `Lectiva respaldos` y guarda `lectiva_respaldo_AAAA-MM-DD.sqlite`, **cada hora mientras la app esté abierta** (se reescribe durante el día, así incluye tu trabajo reciente) y conserva los últimos 30 días. Cada copia se verifica antes de reemplazar la anterior, así que una memoria desconectada a medias no daña la copia buena. **Respaldar ahora** hace una copia al instante. Si la copia falla (por ejemplo, la memoria USB está desconectada) o pasan 2 días sin copia, el Inicio muestra un aviso. Contiene datos personales de los estudiantes: elige un lugar privado. La primera vez, macOS puede pedir permiso a Lectiva para acceder a esa carpeta (Ajustes del Sistema → Privacidad y seguridad → Archivos y carpetas).
- **Restaurar:** cierra Lectiva, copia el archivo de respaldo al proyecto con el nombre `examen_db.sqlite` (guarda antes el actual por si acaso) y abre Lectiva de nuevo.

## Abrir el sistema con un clic (Mac)

Para instalar la aplicación **Lectiva** (una sola vez, o cada vez que cambie la versión):

```bash
bash scripts/mac/instalar_app.sh
```

Compila la app, la instala en Aplicaciones, crea el acceso directo en el Escritorio y la agrega al Dock. Al abrirla:
- muestra la **versión** del sistema (se define en `backend/version.py`);
- **levanta el servidor** (si ya había uno corriendo, lo usa);
- muestra la **dirección para los estudiantes** (`http://<IP>:8090`) con un código QR, el nombre `.local` y un botón para copiarla. Si la IP cambia al reconectarse al wifi, la ventana lo avisa y se actualiza sola;
- mantiene la Mac despierta mientras el servidor corre.

Botones: **Abrir panel docente**, **Ver registro** (`logs/servidor.log`) y **Detener servidor y salir**. Al salir, la app **apaga el servidor y libera el puerto** (también si ya estaba corriendo), pero solo si es el de Lectiva, nunca otro programa; si cierras la ventana, el sistema se detiene (pide confirmación). El instalador retira la versión anterior llamada «Examen Digital» (app, acceso directo e icono del Dock). Tras actualizar el código, usa **Reiniciar servidor** en la ventana de la app. Si macOS pregunta por conexiones entrantes de Python, permítelas.

## Apariencia

Panel docente: menú lateral agrupado (en tablet y celular es un cajón con el botón «Menú»), selector único de grupo, período y materia en la cabecera (Grupo y Período como botones de un toque; si al cambiarlos la materia cambia sola, un aviso lo indica), menús de acciones agrupados (en el celular se anclan abajo), pasar lista de un toque, hojas de notas con teclado (Enter y flechas) e inicio con accesos rápidos y primeros pasos. App del estudiante: formularios con etiquetas visibles, opciones del examen que se pueden usar con teclado y «Mis notas» pensado para el celular.

La plataforma sigue el tema claro u oscuro del dispositivo y tiene un botón (sol o luna) para cambiarlo; la preferencia se recuerda en el navegador. Los colores, espacios y tipografía viven en `frontend/css/base.css`.

## Instalar Lectiva en el celular

La app del estudiante se puede añadir a la pantalla de inicio para abrirla como una app, sin la barra del navegador:
- **iPhone (Safari):** abre la dirección de Lectiva, toca Compartir → **Añadir a pantalla de inicio**.
- **Android (Chrome):** menú ⋮ → **Añadir a pantalla de inicio** (o «Instalar app»).

Lectiva funciona dentro de la red del aula con `http://`, y los navegadores solo permiten el modo sin conexión (service worker) con `https://`; por eso necesita wifi para presentar el examen. Si se cae la conexión a mitad del examen, las respuestas quedan guardadas en el teléfono y se envían solas cuando vuelve.

## Solución de problemas

- **La interfaz se ve sin colores o con botones sin estilo:** recarga sin caché (⌘⇧R en Mac, Ctrl+Shift+R en Windows). El servidor ya indica al navegador que revalide los archivos, pero una copia vieja puede quedar la primera vez.
- **Puerto ocupado:** la app de Mac lo avisa. Cierra la otra copia con **Detener servidor y salir**, o cambia el puerto con la variable `PORT` (la app de Mac usa el 8090, definido en `mac/Lectiva.swift`).
- **Los cambios de código no se ven:** reinicia el servidor (botón **Reiniciar servidor** de la app) y recarga el panel.

## Nombres heredados

La plataforma se llamaba «Examen Digital». Por compatibilidad se conservan el archivo de base de datos `examen_db.sqlite`, la variable `EXAMEN_SECRET_KEY`, la carpeta del proyecto `Examen_digital_simple` y el nombre del repositorio en GitHub, para no romper datos ni rutas.
