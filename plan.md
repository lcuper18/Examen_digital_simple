# Lectiva · Hoja de ruta

Lectiva (antes «Examen Digital») es una plataforma de gestión educativa para el aula: exámenes en línea, asistencia,
actividades con rúbrica, notas por componente, reportes e informes, con panel docente y app del estudiante.
Versión actual: **4.5.0** (definida en `backend/version.py`).

---

## Arquitectura actual

| Componente | Tecnología |
|------------|-----------|
| Servidor | Python 3.12 + FastAPI + Uvicorn, puerto **8090** |
| Base de datos | SQLite (modo WAL), archivo `examen_db.sqlite`; copia diaria en `respaldos/` (últimas 30) |
| Seguridad | Contraseñas con bcrypt, sesiones firmadas, límite de intentos de login (`ratelimit.py`), bitácora de acciones |
| Interfaz | HTML, CSS y JavaScript sin frameworks; tema claro/oscuro; PDF con jsPDF; Excel con openpyxl |
| Panel docente | `/docente` (`frontend/docente.html` + un módulo por pestaña en `frontend/js/docente/`) |
| App del estudiante | `/` (`frontend/index.html`): examen, «Mis notas», pensada para el celular |
| App de Mac | `mac/Lectiva.swift` (Swift/AppKit): levanta el servidor local, muestra la dirección y el QR para los estudiantes, lo apaga al salir |
| Pruebas | pytest (`tests/`) |

Ponderaciones por defecto (suman 100, configurables por materia en Ajustes): Trabajo cotidiano 25, Tareas 10,
Prueba 01 22,5, Prueba 02 22,5, Proyecto 15, Asistencia 5.

El servidor corre en la computadora del docente, dentro de la red del aula; los estudiantes entran con la dirección
`http://<IP>:8090` (o el nombre `.local`).

---

## Historial

| Versión | Fechas | Qué se hizo |
|---------|--------|-------------|
| v1 | abr-may 2026 | Examen estático cargado desde JSON, con diseño propio y banco de preguntas por especialidad. |
| v2 | jun 2026 | Backend FastAPI + SQLite, login de estudiantes, códigos de examen, PDF de resultados, scripts de inicio para Mac, Linux y Windows. |
| v3 | oct-nov 2026 | Calificación en el servidor con sesión firmada; seguridad (bcrypt, límite de intentos, barajado por estudiante); **panel docente** modular (resultados, notas, estudiantes, exámenes, reportes, boleta, Excel); exámenes ADM02, GCS02, EMP02 y SQA02 y la skill `crear-examen-digital`; **fases 0-5** (ajustes y ponderación por materia, asistencia por lección, actividades con rúbrica, acta e informes, «Mis notas» con publicación controlada, ficha de seguimiento y cierre del curso lectivo); **etapas de diseño 1-5** (sistema de diseño claro/oscuro, menú lateral y selector global, pasar lista táctil, inicio útil, app del estudiante accesible); respaldos automáticos; app de Mac. |
| v4.5.0 | nov 2026 | Uso diario del docente: Ajustes disponible aunque no haya materias; Resultados con búsqueda, paginación y menú de acciones; Bitácora con búsqueda, filtro por acción y etiquetas legibles; confirmaciones al desactivar una cuenta y al eliminar una observación; cambio de sección con lista; aviso al cambiar de pestaña o cerrar con cambios sin guardar. |
| v4.4.0 | nov 2026 | Copia de respaldo externa: en Ajustes se elige una carpeta (iCloud, disco o USB) donde Lectiva guarda cada hora una copia verificada de la base, con las últimas 30; aviso en el Inicio si falla o se atrasa. |
| v4.3.0 | nov 2026 | Vínculo examen-materia: un examen se vincula a una o varias materias (por ejemplo EMP02 a Emprendimiento de 11-1 y de 11-2) con su componente; la pantalla Exámenes muestra a qué notas va cada uno; «Un examen como prueba…» elige de una lista; la boleta toma el período del vínculo. |
| v4.2.0 | nov 2026 | Robustez del examen: el envío doble o simultáneo ya no pisa la nota ni da error; si se cae la red el envío se reintenta solo y no se pierden respuestas; el estudiante puede continuar su examen tras recargar sin escribir el código; «Cerrar y calificar» los intentos en curso desde Exámenes. |
| v4.1.0 | nov 2026 | Contraseña del docente editable desde Ajustes; reloj del examen corregido; cambio de clave obligatorio para estudiantes nuevos y «Pedir cambio de clave» por grupo; plantilla del colegio en Reportes. |
| **v4.0.0 · Lectiva** | nov 2026 | Cambio de nombre a Lectiva; selector Grupo/Período con botones de un toque y aviso al cambiar la materia; menú **Importar / exportar** agrupado; boleta limitada al grupo elegido, con período 1.º, 2.º o General (nota anual) y componentes en puntos sobre su valor; puerto 8090 (el 8001 chocaba con Packet Tracer); «Detener servidor y salir» libera el puerto; encabezados sin caché para evitar interfaz sin estilos. |

### Sobre el plan v3 original

El plan inicial (Docker, PostgreSQL, JWT, Nginx, Redis, Prometheus/Grafana y un panel `/admin` con Alpine.js) se
**descartó** a favor de un servidor local simple en la Mac del docente, que cubre el uso real de un aula. Varias de sus
metas se cumplieron por otro camino: contraseñas con bcrypt, límite de intentos, respaldos diarios, módulo de notas con
ponderaciones configurables, reportes con Excel y una suite de pruebas.

---

## Hecho en la ronda de mejoras (v4.1.0)

- [x] **Contraseña del docente editable desde Ajustes** (guardada con bcrypt). Mientras se use la de fábrica, que es pública, el panel muestra un aviso fijo con «Cambiar ahora».
- [x] **Reloj del examen:** ya no se congela si el estudiante cancela el aviso de preguntas sin responder; el examen se envía solo al acabarse el tiempo.
- [x] **Claves de estudiantes:** los estudiantes nuevos deben cambiar su clave al entrar y el docente puede pedirlo a un grupo con «Pedir cambio de clave» en Estudiantes.
- [x] **Envío doble y arranque simultáneo del examen:** el cierre del intento es atómico (el segundo envío recibe «ya enviado» y no toca la nota) y dos inicios a la vez retoman el mismo intento en vez de dar error 500.
- [x] **Reintento sin conexión:** si se cae la red o el servidor no responde, la app reintenta sola cada 5 s y apenas vuelve el wifi; un «ya enviado» tras reintentar se toma como éxito.
- [x] **Continuar el examen tras recargar:** la pantalla del código muestra «Tienes un examen en curso… Continuar mi examen» sin volver a escribirlo.
- [x] **Exámenes en curso:** botón «Cerrar y calificar los N en curso…» en Exámenes (deshabilitar un examen sigue sin detener a quienes ya lo iniciaron).
- [x] **Ajustes sin materias, Resultados y Bitácora:** Ajustes (institución, contraseña, copia de respaldo) ya no se oculta si no hay materias; Resultados tiene búsqueda por estudiante, paginación (25 por página) y el mismo menú «⋯» de las demás pestañas; Bitácora con búsqueda, filtro por acción, paginación y las mismas etiquetas legibles del Inicio.
- [x] **Confirmaciones:** desactivar una cuenta y eliminar una observación piden confirmar; «Cambiar sección» ofrece la lista de secciones; al cambiar de pestaña o cerrar con cambios sin guardar se avisa antes de perderlos.
- [x] **Respaldo fuera del equipo:** carpeta externa elegida en Ajustes (sugiere iCloud Drive y discos conectados), copia horaria verificada y atómica, últimas 30, «Respaldar ahora», aviso en el Inicio y paso en «Primeros pasos».
- [x] **Vínculo examen-materia:** un examen puede alimentar las notas de varias materias, cada una con su componente (tabla `examen_vinculos`, con migración automática de los vínculos anteriores). Exámenes muestra «Va a las notas de» y marca «Sin vincular»; Configurar tiene la lista de materias por período; «Un examen como prueba…» elige de una lista.
- [x] **Plantilla del colegio:** Reportes rellena el CSV del sistema del colegio (Prueba = Prueba 1 + Prueba 2, puntos con punto decimal).

---

## Pendientes priorizados

### Prioridad alta: robustez del examen y de los datos
- [ ] **Claves foráneas apagadas:** al borrar un estudiante quedan asistencia, calificaciones y observaciones huérfanas (`backend/routes/estudiantes.py`).
- [ ] **Límite de tamaño** en las cargas de archivos (CSV y Excel).
- [ ] **Sesión del estudiante:** invalidar el token al reiniciar su clave (hoy dura 12 horas).

### Prioridad media: uso diario del docente
- [ ] **Secciones permitidas del examen** con casillas en vez de texto separado por comas.
- [ ] **Cierre del curso:** reiniciar también la configuración de exámenes para que no se repitan códigos viejos.
- [ ] Revisar con el docente la **nota anual** (hoy promedio simple de los períodos).

### Prioridad media: app del estudiante
- [ ] **PWA:** manifest, ícono y `theme-color` para instalarla en el celular.
- [ ] **Reloj basado en la hora de fin** en lugar de un contador, para que no se desfase si el teléfono se bloquea.
- [ ] **Accesibilidad:** avisos y resultados como diálogos reales (foco, `aria-modal`) y estados que no dependan solo del color.
- [ ] **«Mis notas»:** cerrar sesión si el token venció.

### Diseño pendiente
- [ ] Resumen compacto del selector de contexto en el celular (una línea que abre una hoja).
- [ ] Título de la sección junto al selector.
- [ ] Revisar los botones segmentados en el tema claro.

### Idiomas y marca
- [ ] **Internacionalización:** separar los textos en archivos de idioma y agregar un selector (inglés, francés, portugués y chino simplificado; hoy todo está en español).
- [ ] Nombre de marca en chino simplificado, revisado por un hablante nativo.
- [ ] **Verificar la marca y el dominio «Lectiva»** (OMPI, Registro Nacional de Costa Rica; `.com`, `.app`, `.cr`).

### Calidad interna
- [ ] Unificar utilidades repetidas (`num`, fechas, etiquetas de componentes, `escapeHtml`) en `core.js` y quitar código muerto.
- [ ] **Rendimiento:** cachear `codigos.json` y los exámenes; evitar recalcular `_filas` por materia en la boleta y las alertas.
- [ ] **Pruebas** para portal, asistencia, seguimiento, bitácora y `/red`.

### Opcional
- [ ] Renombrar la carpeta del proyecto y el repositorio de GitHub (obliga a reinstalar la app de Mac).
- [ ] Renombrar el archivo de base de datos y la variable `EXAMEN_SECRET_KEY` con una migración que no pierda datos.
- [ ] Despliegue en la nube con HTTPS, solo si se necesita acceso fuera del aula.
