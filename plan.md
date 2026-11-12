# Lectiva · Hoja de ruta

Lectiva (antes «Examen Digital») es una plataforma de gestión educativa para el aula: exámenes en línea, asistencia,
actividades con rúbrica, notas por componente, reportes e informes, con panel docente y app del estudiante.
Versión actual: **4.0.0** (definida en `backend/version.py`).

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
| **v4.0.0 · Lectiva** | nov 2026 | Cambio de nombre a Lectiva; selector Grupo/Período con botones de un toque y aviso al cambiar la materia; menú **Importar / exportar** agrupado; boleta limitada al grupo elegido, con período 1.º, 2.º o General (nota anual) y componentes en puntos sobre su valor; puerto 8090 (el 8001 chocaba con Packet Tracer); «Detener servidor y salir» libera el puerto; encabezados sin caché para evitar interfaz sin estilos. |

### Sobre el plan v3 original

El plan inicial (Docker, PostgreSQL, JWT, Nginx, Redis, Prometheus/Grafana y un panel `/admin` con Alpine.js) se
**descartó** a favor de un servidor local simple en la Mac del docente, que cubre el uso real de un aula. Varias de sus
metas se cumplieron por otro camino: contraseñas con bcrypt, límite de intentos, respaldos diarios, módulo de notas con
ponderaciones configurables, reportes con Excel y una suite de pruebas.

---

## Pendientes

### Datos y funcionalidad
- [ ] **Vincular cada examen a su materia y componente** en la pestaña Exámenes (hoy ninguno lo está). Con el vínculo, «Notas de los exámenes vinculados» importa Prueba 1/2 con un clic, y la boleta ya no depende del sufijo del código para saber el período.
- [ ] Revisar con el docente la nota anual (hoy promedio simple de los períodos) por si el reglamento pide otra fórmula.

### Idiomas y marca
- [ ] **Internacionalización:** separar los textos de la interfaz en archivos de idioma y agregar un selector (inglés, francés, portugués y chino simplificado; hoy todo está en español).
- [ ] Nombre de marca en chino simplificado, elegido por significado y revisado por un hablante nativo.
- [ ] **Verificar la marca y el dominio «Lectiva»** (base de marcas de la OMPI, Registro Nacional de Costa Rica; dominios `.com`, `.app`, `.cr`).

### Diseño
- [ ] Resumen compacto del selector de contexto en el celular (una línea que abre una hoja con Grupo, Período y Materia).
- [ ] Título de la sección junto al selector, para que se vea en qué pestaña se está.
- [ ] Revisar el aspecto de los botones segmentados en el tema claro y con distintos navegadores.

### Opcional
- [ ] Renombrar la carpeta del proyecto y el repositorio de GitHub (requiere reinstalar la app de Mac, que guarda la ruta).
- [ ] Renombrar el archivo de base de datos y la variable `EXAMEN_SECRET_KEY` con una migración que no pierda datos.
- [ ] Despliegue en la nube con HTTPS, solo si se necesita acceso fuera del aula (lo que quedó del plan v3).
