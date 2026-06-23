# Plan de Desarrollo: Examen Digital v3

## Panel de Administración Docente + Despliegue en Producción

---

## Estrategia de Ramas

```
master (v2 estable)
  └── v3-panel-docente (desarrollo nuevo)
         ├── Fase 0: Dockerización + PostgreSQL
         ├── Fase 1: Backend del Panel Admin
         ├── Fase 2: Frontend del Panel Admin
         ├── Fase 3: Mejoras al Frontend Estudiante
         └── Fase 4: Seguridad y Producción
```

| Rama | Propósito |
|------|-----------|
| `master` | Versión v2 actual. **Sigue funcionando** para los estudiantes sin interrupción. Solo recibe hotfixes críticos. |
| `v3-panel-docente` | Nueva rama creada desde `master`. Contiene todo el desarrollo del plan. Al finalizar, se fusiona a `master`. |
| `desarrollo` | (opcional) Para hotfixes urgentes a v2 mientras v3 está en desarrollo. |

---

## Stack Tecnológico

| Componente | Tecnología |
|------------|-----------|
| Backend API | FastAPI + SQLAlchemy + Alembic |
| Base de Datos | PostgreSQL 16 |
| Frontend Estudiante | Vanilla JS (existente) + mejoras PWA |
| Frontend Admin | Alpine.js + Chart.js (ligero, sin bundler) |
| Autenticación Admin | JWT (access + refresh token) |
| Passwords | bcrypt (migración desde SHA-256) |
| Proxy | Nginx + Certbot (SSL Let's Encrypt) |
| Cache | Redis (sesiones, rate limiting) |
| Despliegue | Dokploy (Docker Compose) |
| Monitoreo | Prometheus + Grafana (contenedores) |
| Backup | pg_dump + rclone a Backblaze B2 / S3 |

---

## Fase 0 — Dockerización y Despliegue Base

**Objetivo:** Empaquetar la aplicación actual en Docker, migrar a PostgreSQL y dejarla operativa en Dokploy con dominio HTTPS.

### Tareas

| # | Tarea | Agente | Depende de | Tiempo |
|---|-------|--------|------------|--------|
| 0.1 | Crear `Dockerfile` multi-etapa para FastAPI | DevOps | — | 1 día |
| 0.2 | Crear `docker-compose.yml` con servicios: api, postgres, nginx, redis | DevOps | 0.1 | 1 día |
| 0.3 | Migrar de SQLite a PostgreSQL | ExpertSQL + SeniorDev | — | 2 días |
| 0.3.1 | Definir modelos SQLAlchemy (`Student`, `Attempt`, `ExamCode`) | ExpertSQL | — | |
| 0.3.2 | Configurar Alembic con migración inicial | ExpertSQL | 0.3.1 | |
| 0.3.3 | Escribir script de migración de datos SQLite → PostgreSQL | SeniorDev | 0.3.2 | |
| 0.3.4 | Adaptar endpoints existentes para usar SQLAlchemy | SeniorDev | 0.3.1 | |
| 0.4 | Configurar Nginx como reverse proxy con SSL | DevOps | 0.2 | 1 día |
| 0.4.1 | Crear `nginx.conf` con proxy a FastAPI + archivos estáticos | | | |
| 0.4.2 | Configurar Certbot para SSL automático | | | |
| 0.5 | Configurar despliegue en Dokploy | DevOps | 0.2, 0.4 | 1 día |
| 0.5.1 | Crear `Dokploy.yml` con variables de entorno | | | |
| 0.5.2 | Configurar healthchecks y restart policies | | | |
| 0.5.3 | Apuntar dominio al VPS y verificar SSL | | | |
| 0.6 | Pruebas de humo post-despliegue | QA | 0.5 | 1 día |
| 0.6.1 | Probar login de estudiantes | | | |
| 0.6.2 | Probar carga y envío de exámenes | | | |
| 0.6.3 | Probar generación de PDF de resultados | | | |
| 0.6.4 | Verificar logs y monitoreo básico | | | |

### Entregables de Fase 0

- `Dockerfile`, `docker-compose.yml`, `nginx.conf`
- Proyecto corriendo en `https://tudominio.com`
- Estudiantes pueden hacer exámenes sin cambios
- BD PostgreSQL con datos migrados

---

## Fase 1 — Backend del Panel de Administración

**Objetivo:** API REST segura con JWT para que el docente administre estudiantes, exámenes, resultados y códigos.

### Tareas

| # | Tarea | Agente | Depende de | Tiempo |
|---|-------|--------|------------|--------|
| 1.1 | Modelos de administración en SQLAlchemy | ExpertSQL | 0.3.1 | 1 día |
| 1.1.1 | Modelo `AdminUser` (id, email, password_hash, role, created_at) | | | |
| 1.1.2 | Modelo `ExamSession` (id, codigo, examen_id, activo, creado_por, expira_en) | | | |
| 1.1.3 | Modelo `Exam` (id, codigo, nombre, archivo_json, activo, creado_por, created_at) | | | |
| 1.1.4 | Migración Alembic para nuevos modelos | | | |
| 1.2 | Autenticación JWT para admin | SeniorDev | 1.1 | 2 días |
| 1.2.1 | Endpoint `POST /api/admin/login` (devuelve access + refresh token) | | | |
| 1.2.2 | Middleware de verificación JWT | | | |
| 1.2.3 | Endpoint `POST /api/admin/refresh` | | | |
| 1.2.4 | Endpoint `POST /api/admin/change-password` | | | |
| 1.3 | CRUD de Estudiantes | SeniorDev | 1.2 | 2 días |
| 1.3.1 | `GET /api/admin/estudiantes` (paginado, filtros por sección/nombre) | | | |
| 1.3.2 | `POST /api/admin/estudiantes` (crear individual) | | | |
| 1.3.3 | `PUT /api/admin/estudiantes/{id}` (editar) | | | |
| 1.3.4 | `DELETE /api/admin/estudiantes/{id}` (eliminar) | | | |
| 1.3.5 | `POST /api/admin/estudiantes/importar-csv` (subir CSV masivo) | | | |
| 1.3.6 | `POST /api/admin/estudiantes/{id}/reset-password` (resetear contraseña) | | | |
| 1.4 | CRUD de Exámenes | SeniorDev | 1.2 | 2 días |
| 1.4.1 | `GET /api/admin/examenes` (listar con estados) | | | |
| 1.4.2 | `POST /api/admin/examenes` (subir JSON + registrar) | | | |
| 1.4.3 | `PUT /api/admin/examenes/{id}` (editar metadatos) | | | |
| 1.4.4 | `DELETE /api/admin/examenes/{id}` (eliminar) | | | |
| 1.4.5 | `PATCH /api/admin/examenes/{id}/toggle` (activar/desactivar) | | | |
| 1.5 | Gestión de Códigos de Examen | SeniorDev | 1.2 | 1 día |
| 1.5.1 | `POST /api/admin/codigos` (generar código con vigencia) | | | |
| 1.5.2 | `GET /api/admin/codigos` (listar históricos) | | | |
| 1.5.3 | `DELETE /api/admin/codigos/{id}` (revocar) | | | |
| 1.6 | Endpoints de Reportes y Estadísticas | SeniorDev | 1.2 | 2 días |
| 1.6.1 | `GET /api/admin/reportes/notas` (notas por sección/examen) | | | |
| 1.6.2 | `GET /api/admin/reportes/desglose-temas` (rendimiento por tema) | | | |
| 1.6.3 | `GET /api/admin/reportes/preguntas-criticas` (preguntas con más errores) | | | |
| 1.6.4 | `GET /api/admin/reportes/exportar-excel` (exportar a Excel) | | | |
| 1.7 | Endpoint de Monitoreo Antitrampas | SeniorDev | 1.2 | 1 día |
| 1.7.1 | WebSocket `ws://api/admin/monitor` (progreso en vivo) | | | |
| 1.7.2 | `POST /api/admin/intentos/{id}/marcar-sospechoso` | | | |
| 1.8 | Módulo de Notas del Docente | SeniorDev | 1.1 | 7 días |
| 1.8.1 | Modelo `Subject` (sección, nombre_materia, periodo, ponderaciones) | ExpertSQL | | |
| 1.8.2 | Modelo `Grade` (estudiante_id, subject_id, tc, tareas, p01, p02, proyecto, asistencia) | ExpertSQL | | |
| 1.8.3 | Seed data: 3 materias por sección × 2 periodos = 6 subjects | SeniorDev | | |
| 1.8.4 | Endpoint `GET /api/admin/subjects` (listar materias con ponderaciones) | SeniorDev | | |
| 1.8.5 | Endpoint `GET /api/admin/grades?subject_id=X` (notas de una materia) | SeniorDev | | |
| 1.8.6 | Endpoint `PUT /api/admin/grades/{id}` (actualizar nota individual) | SeniorDev | | |
| 1.8.7 | Endpoint `POST /api/admin/grades/batch` (guardar todas las notas de una materia) | SeniorDev | | |
| 1.8.8 | Endpoint `GET /api/admin/grades/calculate?subject_id=X&estudiante_id=Y` (nota final ponderada) | SeniorDev | | |
| 1.8.9 | Endpoint `GET /api/admin/grades/report?seccion=X&periodo=Y` (reporte completo) | SeniorDev | | |

### Entregables de Fase 1

- API admin completa con JWT
- CRUD de estudiantes, exámenes, códigos
- Reportes y estadísticas vía API
- WebSocket de monitoreo en vivo
- **Módulo de notas completo (6 materias, 2 periodos, ponderaciones configurables)**

---

## Fase 2 — Frontend del Panel de Administración

**Objetivo:** Interfaz web moderna, responsive y funcional para el docente.

### Tareas

| # | Tarea | Agente | Depende de | Tiempo |
|---|-------|--------|------------|--------|
| 2.1 | Layout base + Login | FrontendDev | — | 2 días |
| 2.1.1 | HTML base con sidebar + header + content area | | | |
| 2.1.2 | Pantalla de login admin separada | | | |
| 2.1.3 | Manejo de sesión con localStorage + redirect | | | |
| 2.1.4 | Protección de rutas (redirigir si no hay token) | | | |
| 2.2 | Dashboard principal | FrontendDev | 2.1 | 2 días |
| 2.2.1 | Cards: total estudiantes, exámenes activos, intentos hoy, % aprobación | | | |
| 2.2.2 | Gráfica de notas (Chart.js) | | | |
| 2.2.3 | Últimos intentos (tabla resumen) | | | |
| 2.2.4 | Selector de sección para filtrar | | | |
| 2.3 | Gestión de Estudiantes | FrontendDev | 2.1 | 3 días |
| 2.3.1 | Tabla con búsqueda, filtro por sección, paginación | | | |
| 2.3.2 | Modal de crear/editar estudiante | | | |
| 2.3.3 | Botón importar CSV (drag & drop) | | | |
| 2.3.4 | Botón reset contraseña (con confirmación) | | | |
| 2.3.5 | Botón eliminar (con confirmación) | | | |
| 2.4 | Gestión de Exámenes | FrontendDev | 2.1 | 2 días |
| 2.4.1 | Lista de exámenes con toggle activo/inactivo | | | |
| 2.4.2 | Modal subir nuevo examen (JSON + metadatos) | | | |
| 2.4.3 | Vista previa de preguntas del JSON | | | |
| 2.4.4 | Editar metadatos (nombre, duración, profesor) | | | |
| 2.5 | Visor de Resultados | FrontendDev | 2.1 | 3 días |
| 2.5.1 | Filtros combinados: sección + examen + estudiante + fecha | | | |
| 2.5.2 | Tabla con notas, columnas ordenables | | | |
| 2.5.3 | Modal detalle por intento (respuestas correctas/incorrectas) | | | |
| 2.5.4 | Botón exportar Excel | | | |
| 2.5.5 | Botón ver PDF del resultado | | | |
| 2.6 | Estadísticas por Examen | FrontendDev | 2.1 | 2 días |
| 2.6.1 | Curva de distribución de notas (histograma) | | | |
| 2.6.2 | Tabla de preguntas con % de acierto | | | |
| 2.6.3 | Gráfico por tema (radar o barras) | | | |
| 2.6.4 | Tiempo promedio por examen | | | |
| 2.7 | Generador de Códigos | FrontendDev | 2.1 | 1 día |
| 2.7.1 | Selector de examen + botón generar código | | | |
| 2.7.2 | Tabla de códigos activos con tiempo restante | | | |
| 2.7.3 | Botón revocar código | | | |
| 2.8 | Monitoreo en Vivo | FrontendDev | 2.1 | 2 días |
| 2.8.1 | Tabla en tiempo real (WebSocket): quién rinde, progreso, tiempo | | | |
| 2.8.2 | Alertas de comportamiento sospechoso | | | |
| 2.9 | Módulo de Notas | FrontendDev | 2.1 | 5 días |
| 2.9.1 | Selector sección → materia → periodo | | | |
| 2.9.2 | Tabla de notas editable inline (TC, Tareas, Prueba01, Prueba02, Proyecto, Asistencia) | | | |
| 2.9.3 | Cálculo automático de nota final con barra de progreso por estudiante | | | |
| 2.9.4 | Botón guardar/batch (guardar todas las notas de una materia) | | | |
| 2.9.5 | Reporte de notas por sección y periodo (PDF/Excel) | | | |
| 2.9.6 | Vista de promedios por materia y sección | | | |

### Entregables de Fase 2

- Panel admin completo en `/admin/`
- Dashboard, CRUD estudiantes, CRUD exámenes
- Visor de resultados con filtros y exportación
- Estadísticas gráficas, códigos, monitoreo en vivo
- **Módulo de notas (edición inline, cálculo automático, exportación)**

---

## Fase 3 — Mejoras al Frontend del Estudiante

**Objetivo:** Mejorar la experiencia del estudiante y agregar funcionalidades faltantes.

### Tareas

| # | Tarea | Agente | Depende de | Tiempo |
|---|-------|--------|------------|--------|
| 3.1 | Modo revisión post-examen | FrontendDev | — | 2 días |
| 3.1.1 | Mostrar respuestas correctas/incorrectas después de enviar | | | |
| 3.1.2 | Botón "Ver detalle" en pantalla de resultados | | | |
| 3.1.3 | Mantener el detalle accesible por 24h (sessionStorage) | | | |
| 3.2 | Soporte de imágenes en preguntas | FrontendDev + SeniorDev | — | 2 días |
| 3.2.1 | Endpoint `POST /api/admin/examenes/subir-imagen` | SeniorDev | | |
| 3.2.2 | Campo `imagen_url` opcional en pregunta JSON | SeniorDev | | |
| 3.2.3 | Renderizar imagen dentro de la pregunta | FrontendDev | | |
| 3.3 | PWA (Progressive Web App) | FrontendDev | — | 2 días |
| 3.3.1 | Service Worker para cachear app shell | | | |
| 3.3.2 | Manifest.json con íconos | | | |
| 3.3.3 | Estrategia offline-first para exámenes ya cargados | | | |
| 3.3.4 | Sincronizar intentos al recuperar conexión | | | |

### Entregables de Fase 3

- Estudiantes ven resultados detallados post-examen
- Preguntas pueden incluir imágenes
- App funciona offline (exámenes cacheados)

---

## Fase 4 — Seguridad y Producción

**Objetivo:** Endurecer la aplicación para uso real en producción.

### Tareas

| # | Tarea | Agente | Depende de | Tiempo |
|---|-------|--------|------------|--------|
| 4.1 | Migrar contraseñas a bcrypt | SeniorDev | — | 1 día |
| 4.1.1 | Reemplazar `hashlib.sha256` por `bcrypt` en registro | | | |
| 4.1.2 | Script de rehash para contraseñas existentes | | | |
| 4.1.3 | Actualizar endpoint de login | | | |
| 4.2 | Rate limiting | SeniorDev | — | 1 día |
| 4.2.1 | `slowapi` en FastAPI: 5 intentos/min por IP en login | | | |
| 4.2.2 | Límite de 1 request/segundo en envío de examen | | | |
| 4.3 | Backups automáticos | DevOps | 0.2 | 1 día |
| 4.3.1 | Script `backup.sh` con pg_dump + compresión | | | |
| 4.3.2 | Cron diario en el host o contenedor | | | |
| 4.3.3 | Subida a Backblaze B2 / S3 con rclone | | | |
| 4.4 | Monitoreo y alertas | DevOps | 0.2 | 2 días |
| 4.4.1 | Prometheus config para métricas de FastAPI | | | |
| 4.4.2 | Grafana dashboard: requests, errores, latencia, BD | | | |
| 4.4.3 | Alerta si el servicio cae (healthcheck + webhook) | | | |
| 4.5 | Tests automatizados | QA | 0.3, 1.2, 1.6 | 3 días |
| 4.5.1 | Tests de integración para login (estudiante y admin) | | | |
| 4.5.2 | Tests de envío y corrección de exámenes | | | |
| 4.5.3 | Tests de CRUD estudiantes y exámenes | | | |
| 4.5.4 | Tests de reportes y estadísticas | | | |
| 4.5.5 | Tests de WebSocket de monitoreo | | | |

### Entregables de Fase 4

- Contraseñas con bcrypt
- Rate limiting activo
- Backups automáticos diarios
- Dashboard de monitoreo (Prometheus + Grafana)
- Suite de tests automatizados

---

## Diagrama de Arquitectura Final

```
                          ┌─────────────┐
                          │   Dominio    │
                          │  (HTTPS 443) │
                          └──────┬──────┘
                                 │
                          ┌──────▼──────┐
                          │   Nginx     │ ←── Certbot (SSL)
                          │  (reverse)  │
                          └──┬───────┬──┘
                             │       │
                    ┌────────┘       └────────┐
                    │                         │
             ┌──────▼──────┐          ┌───────▼───────┐
             │  FastAPI    │          │   Static       │
             │  :8000      │          │   /frontend    │
             └──┬──────┬───┘          └───────────────┘
                │      │
         ┌──────▼─┐  ┌─▼────────┐
         │Postgres│  │  Redis   │
         │ :5432  │  │ :6379    │
         └────────┘  └──────────┘
```

### Contenedores Docker (Dokploy)

| Servicio | Puerto Interno | Volumen Persistente |
|----------|---------------|-------------------|
| `api` | 8000 | `./backend/` (código) |
| `postgres` | 5432 | `pgdata/` |
| `redis` | 6379 | `redisdata/` |
| `nginx` | 80/443 | `certs/` (Let's Encrypt) |
| `prometheus` | 9090 | `promdata/` |
| `grafana` | 3000 | `granadata/` |

---

## Cronograma Estimado

| Fase | Días | Agentes involucrados |
|------|------|---------------------|
| Fase 0 — Docker + PostgreSQL + Despliegue | 7 | DevOps, ExpertSQL, SeniorDev, QA |
| Fase 1 — Backend Admin | 18 | SeniorDev, ExpertSQL |
| Fase 2 — Frontend Admin | 22 | FrontendDev |
| Fase 3 — Mejoras Estudiante | 6 | FrontendDev, SeniorDev |
| Fase 4 — Seguridad y Producción | 8 | SeniorDev, DevOps, QA |
| **Total** | **~61 días** | **Múltiples agentes en paralelo** |

> **Nota:** Las fases 0, 1 y 2 pueden ejecutarse con agentes en paralelo:
> - DevOps en Fase 0 mientras SeniorDev hace Fase 1
> - FrontendDev puede empezar Fase 2 con endpoints simulados (mock API)

---

## Modelo de Datos — Módulo de Notas

### Materias por Sección

| Sección | Materia 1 | Materia 2 | Materia 3 |
|---------|-----------|-----------|-----------|
| **11-1** | Emprendimiento e Innovación | Administración y Soporte a las Computadoras | Configuración y Soporte a Redes |
| **11-2** | Emprendimiento e Innovación | Pruebas de SQA | Gestión y Control de la Calidad del Software |

### Ponderaciones estándar

| # | Componente | Porcentaje |
|---|-----------|-----------|
| 1 | Trabajo cotidiano | 25% |
| 2 | Tareas | 10% |
| 3 | Prueba 01 | 20% |
| 4 | Prueba 02 | 25% |
| 5 | Proyecto | 15% |
| 6 | Asistencia | 5% |
| | **Total** | **100%** |

### Modelo de datos

```python
# Seed data — 6 subjects (3 materias × 2 periodos)
SUBJECTS = [
    # Sección 11-1 — Periodo 1
    {"seccion": "11-1", "materia": "Emprendimiento e Innovación", "periodo": 1},
    {"seccion": "11-1", "materia": "Administración y Soporte a las Computadoras", "periodo": 1},
    {"seccion": "11-1", "materia": "Configuración y Soporte a Redes", "periodo": 1},
    # Sección 11-1 — Periodo 2
    {"seccion": "11-1", "materia": "Emprendimiento e Innovación", "periodo": 2},
    {"seccion": "11-1", "materia": "Administración y Soporte a las Computadoras", "periodo": 2},
    {"seccion": "11-1", "materia": "Configuración y Soporte a Redes", "periodo": 2},
    # Sección 11-2 — Periodo 1
    {"seccion": "11-2", "materia": "Emprendimiento e Innovación", "periodo": 1},
    {"seccion": "11-2", "materia": "Pruebas de SQA", "periodo": 1},
    {"seccion": "11-2", "materia": "Gestión y Control de la Calidad del Software", "periodo": 1},
    # Sección 11-2 — Periodo 2
    {"seccion": "11-2", "materia": "Emprendimiento e Innovación", "periodo": 2},
    {"seccion": "11-2", "materia": "Pruebas de SQA", "periodo": 2},
    {"seccion": "11-2", "materia": "Gestión y Control de la Calidad del Software", "periodo": 2},
]

PONDERACIONES = {
    "trabajo_cotidiano": 25,
    "tareas": 10,
    "prueba01": 20,
    "prueba02": 25,
    "proyecto": 15,
    "asistencia": 5,
}

# Fórmula de nota final:
# nota = (tc*0.25) + (tareas*0.10) + (p01*0.20) + (p02*0.25) + (proyecto*0.15) + (asistencia*0.05)
```

---

## Criterios de Aceptación por Fase

### Fase 0

- [ ] App corre en Docker en el VPS
- [ ] HTTPS funciona con dominio personalizado
- [ ] Estudiantes pueden loguearse y rendir exámenes
- [ ] Datos migrados de SQLite a PostgreSQL sin pérdida

### Fase 1

- [ ] Admin puede loguearse con JWT
- [ ] CRUD completo de estudiantes (incluye import CSV)
- [ ] CRUD completo de exámenes (incluye toggle activo)
- [ ] Generación y revocación de códigos de examen
- [ ] Reportes de notas y desglose por tema
- [ ] WebSocket de monitoreo funcional
- [ ] **Módulo de notas: CRUD de subjects, grades, cálculo ponderado, reporte por sección**

### Fase 2

- [ ] Dashboard con datos reales del servidor
- [ ] Gestión de estudiantes funcional (crear, editar, eliminar, importar)
- [ ] Gestión de exámenes funcional (subir, activar, desactivar)
- [ ] Visor de resultados con filtros y exportación Excel
- [ ] Estadísticas gráficas funcionales
- [ ] Monitoreo en vivo con WebSocket
- [ ] **Módulo de notas: tabla editable, cálculo automático, exportación**

### Fase 3

- [ ] Estudiantes ven resultados detallados post-examen
- [ ] Preguntas pueden incluir imágenes
- [ ] App funciona offline (exámenes cacheados)

### Fase 4

- [ ] Contraseñas almacenadas con bcrypt
- [ ] Rate limiting activo y probado
- [ ] Backups automáticos funcionando
- [ ] Dashboard de Grafana con métricas
- [ ] Tests pasan en CI
