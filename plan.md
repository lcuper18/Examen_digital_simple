# Plan de Implementación: Examen Digital Simple v2

## Objetivo Principal
Migrar a plataforma completa con backend FastAPI + SQLite, login de estudiantes por credenciales autogeneradas, sistema de códigos de examen, temporizador, persistencia, y reportes mejorados con desglose por tema y diseño institucional.

## Resumen de Fases

| Fase | Descripción | Total Tareas |
|------|------------|:------------:|
| FASE 0 | Preparación y datos | 5 |
| FASE 1 | Backend FastAPI + SQLite | 8 |
| FASE 2 | Frontend — Login + Códigos | 6 |
| FASE 3 | Seguridad | 3 |
| FASE 4 | Reporte Mejorado (pantalla + PDF) | 7 |
| FASE 5 | Persistencia + Temporizador | 4 |
| FASE 6 | DevOps y Entrega | 6 |
| **Total** | | **39** |

---

## FASE 0: Preparación y Datos

| # | Tarea | Agente | Descripción |
|---|-------|--------|-------------|
| 0.1 | Extraer estudiantes del PDF a CSV/JSON | `SeniorDev` | Leer `lista de alumnos.pdf` con PyMuPDF, estructurar 26 registros con cédula, nombre, apellidos, sección |
| 0.2 | Crear `codigos.json` | `SeniorDev` | Mapeo: CCS01, EMP01, ADM01, RED01 → nombres de archivo en `examenes/` |
| 0.3 | Renombrar y consolidar JSONs | `SeniorDev` | Mover `preguntas.json` a `examenes/Introducción a las Redes.json`; estandarizar estructura |
| 0.4 | Unificar estructura de JSONs | `SeniorDev` | Asegurar que todos los exámenes tengan los mismos campos (`codigo`, `año`, `duracion_minutos`, etc.) |
| 0.5 | Agregar campo `duracion_minutos` a JSONs | `SeniorDev` | Para el temporizador (valor por defecto: 60) |

---

## FASE 1: Backend FastAPI + SQLite

| # | Tarea | Agente | Descripción |
|---|-------|--------|-------------|
| 1.1 | Crear `main.py` con FastAPI | `SeniorDev` | Servidor con Uvicorn, sirve static files y API REST. Reemplaza `servidor.py` |
| 1.2 | Crear `database.py` | `ExpertSQL` | Conexión SQLite, creación de tablas: `estudiantes`, `intentos` |
| 1.3 | Diseñar tabla `estudiantes` | `ExpertSQL` | Columnas: id, cedula, nombre, apellido1, apellido2, seccion, username, password_hash, created_at |
| 1.4 | Diseñar tabla `intentos` | `ExpertSQL` | Columnas: id, estudiante_id, codigo_examen, respuestas_json, puntuacion, total, fecha_inicio, fecha_fin |
| 1.5 | Endpoint `POST /api/login` | `SeniorDev` | Validar username + password_hash, devolver token de sesión |
| 1.6 | Endpoint `GET /api/examen/{codigo}` | `SeniorDev` | Leer `codigos.json` → devolver preguntas del JSON correspondiente |
| 1.7 | Endpoint `POST /api/intentos` | `SeniorDev` | Guardar respuestas, puntuación, fecha fin del intento |
| 1.8 | Poblar BD con 26 estudiantes | `SeniorDev` | Generar username y contraseña, insertar en SQLite |

---

## FASE 2: Frontend — Login + Carga por Código

| # | Tarea | Agente | Descripción |
|---|-------|--------|-------------|
| 2.1 | Pantalla de login | `FrontendDev` | Formulario usuario/contraseña, conecta a `POST /api/login`, manejo de errores |
| 2.2 | Pantalla ingreso de código de examen | `FrontendDev` | Input de 4+ caracteres, validación, carga del examen |
| 2.3 | Reemplazar carga fija de `preguntas.json` | `FrontendDev` | Cambiar `fetch('preguntas.json')` por `fetch(/api/examen/${codigo})` |
| 2.4 | Eliminar contenido hardcodeado del header | `FrontendDev` | Líneas 1213-1219 del HTML, todo debe venir del JSON |
| 2.5 | Guardar sesión del estudiante | `FrontendDev` | Almacenar token y datos del estudiante en memoria/sessionStorage |
| 2.6 | Actualizar `updateExamMetadata()` | `FrontendDev` | Usar datos desde API en lugar de variables globales fijas |

---

## FASE 3: Seguridad

| # | Tarea | Agente | Descripción |
|---|-------|--------|-------------|
| 3.1 | Implementar hash SHA-256 real en login | `SeniorDev` | Usar `hashlib` en backend para contraseñas de estudiantes; corregir `sha256()` en frontend para docente |
| 3.2 | Eliminar `TEACHER_PASSWORD` en texto plano | `FrontendDev` | Reemplazar `verifyPassword()` con comparación de hash |
| 3.3 | Mover contraseña docente a backend | `SeniorDev` | Endpoint `POST /api/verificar-docente` con hash almacenado seguro |

---

## FASE 4: Reporte Mejorado (Pantalla + PDF)

| # | Tarea | Agente | Descripción |
|---|-------|--------|-------------|
| 4.1 | Mostrar nombre del estudiante en resultados | `FrontendDev` | En modal de resultados, encabezado con "Estudiante: María Luisa Artavia Campos" |
| 4.2 | Desglose por tema en pantalla | `FrontendDev` | Tabla: Tema \| Correctas \| Incorrectas \| Total \| % |
| 4.3 | Mostrar preguntas completas (sin truncar) | `FrontendDev` | Eliminar `substring(0, 80)` en resultados |
| 4.4 | PDF con diseño institucional | `FrontendDev` | Encabezado CTP Las Palmitas, nombre estudiante, fecha, código examen; tabla resumen; desglose por tema; detalle completo; footer |
| 4.5 | Agregar texto institucional al PDF | `FrontendDev` | "Colegio Técnico Profesional Las Palmitas" como parte del encabezado |
| 4.6 | Generar calificación numérica | `FrontendDev` | Nota de 0 a 100 basada en porcentaje de respuestas correctas |
| 4.7 | Mejorar estilo visual de resultados en pantalla | `FrontendDev` | Tarjetas por tema, mejor diseño responsive |

---

## FASE 5: Persistencia + Temporizador

| # | Tarea | Agente | Descripción |
|---|-------|--------|-------------|
| 5.1 | Guardar respuestas en localStorage | `FrontendDev` | Cada respuesta se persiste con key `examen_{codigo}_{estudianteId}` |
| 5.2 | Restaurar respuestas al recargar | `FrontendDev` | Al cargar el examen, buscar respuestas guardadas y restaurar estado |
| 5.3 | Temporizador regresivo | `FrontendDev` | Leer `duracion_minutos` del JSON, mostrar en header, actualizar cada segundo |
| 5.4 | Envío automático al agotar tiempo | `FrontendDev` | Forzar submit del examen al llegar a 0:00 |

---

## FASE 6: DevOps y Entrega

| # | Tarea | Agente | Descripción |
|---|-------|--------|-------------|
| 6.1 | Actualizar `iniciar.sh` | `DevOps` | Usar ruta relativa, iniciar con `uvicorn main:app` |
| 6.2 | Crear `requirements.txt` | `DevOps` | fastapi, uvicorn, aiosqlite, python-multipart, PyMuPDF |
| 6.3 | Crear rama `desarrollo` | `GitExpert` | `git checkout -b desarrollo`, push a remote |
| 6.4 | Commit inicial de Fase 0 | `GitExpert` | Commit con codigos.json, estudiantes extraídos, JSONs consolidados |
| 6.5 | Pruebas de integración | `QA` | Verificar login, carga de examen, envío, reporte, PDF, timer |
| 6.6 | Merge desarrollo → master | `GitExpert` | Usar skill `git-merge-desarrollo-main` al finalizar |

---

## Diagrama de Flujo del Sistema

```
┌──────────────────────────────────────────────────────────────────┐
│                        NAVEGADOR                                │
│                                                                  │
│  [Login] ──POST /api/login──►  ¿Credenciales válidas?            │
│      │                            │                              │
│      │  Sí ◄──────────────────────┘                              │
│      ▼                                                            │
│  [Ingresar Código Examen] ──GET /api/examen/{codigo}──►         │
│      │                                                            │
│      ▼                                                            │
│  [Tomar Examen]  ◄── JSON de preguntas                           │
│      │                                                            │
│      │  ├── Timer regresivo (60 min)                             │
│      │  ├── localStorage (persistencia)                          │
│      │  └── Estadísticas (contestadas/pendientes)                │
│      │                                                            │
│      ▼                                                            │
│  [Enviar Examen] ──POST /api/intentos──►                         │
│      │                                                            │
│      ▼                                                            │
│  [Modal Contraseña Docente]                                      │
│      │                                                            │
│      ├── Contraseña incorrecta → error                           │
│      └── Contraseña correcta →                                   │
│              ▼                                                    │
│      [Resultados]                                                │
│      ├── Nombre estudiante                                       │
│      ├── Puntuación: 28/40 (70%) - Nota: 70                     │
│      ├── Tabla desglose por tema                                 │
│      ├── Lista detalle preguntas completas                       │
│      └── [Descargar PDF]  → Reporte institucional               │
└──────────────────────────────────────────────────────────────────┘

┌──────────────────────────────────────────────────────────────────┐
│                     BACKEND (FastAPI)                            │
│                                                                  │
│  SQLite (examenes.db)                                            │
│  ├── estudiantes (26 registros desde PDF)                        │
│  ├── intentos (historial de intentos)                            │
│                                                                  │
│  codigos.json  ──mapeo──►  examenes/*.json                       │
│                                                                  │
│  Endpoints:                                                      │
│  ├── POST /api/login                                             │
│  ├── GET  /api/examen/{codigo}                                   │
│  ├── POST /api/intentos                                          │
│  └── POST /api/verificar-docente                                 │
└──────────────────────────────────────────────────────────────────┘
```

---

## Esquema de Base de Datos SQLite

```sql
CREATE TABLE estudiantes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    cedula TEXT NOT NULL UNIQUE,
    nombre TEXT NOT NULL,
    apellido1 TEXT NOT NULL,
    apellido2 TEXT,
    seccion TEXT NOT NULL,
    username TEXT NOT NULL UNIQUE,
    password_hash TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);

CREATE TABLE intentos (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    estudiante_id INTEGER NOT NULL,
    codigo_examen TEXT NOT NULL,
    respuestas_json TEXT NOT NULL,
    puntuacion INTEGER NOT NULL,
    total INTEGER NOT NULL,
    fecha_inicio TIMESTAMP,
    fecha_fin TIMESTAMP,
    FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
);
```

---

## Formato de Códigos (`codigos.json`)

```json
{
  "CCS01": "Control de Calidad del Software.json",
  "EMP01": "Emprendimiento.json",
  "ADM01": "Administración y Soporte a Computadoras Portátiles.json",
  "RED01": "Introducción a las Redes.json"
}
```

---

## Generación de Credenciales

| Estudiante | Usuario | Contraseña |
|-----------|---------|-----------|
| WESLY ABDRIEL ALVARADO MORA | wesly.alvarado | ALV2050 |
| MARIA LUISA ARTAVIA CAMPOS | maria.artavia | ART0343 |
| KARINA YULIETH CARRILLO AGUIRRE | karina.carrillo | CAR0360 |
| DIANA FIORELLA CASTRO LEON | diana.castro | CAS0802 |
| BRENAN SOFIA CENTENO SALAS | brenan.centeno | CEN0786 |
| YARELIS ILDANIA GARCIA JAIME | yarelis.garcia | GAR0494 |
| KIARA JIMENEZ OPORTA | kiara.jimenez | JIM0108 |
| EVONY SIDALI MARTINEZ ROMERO | evony.martinez | MAR0137 |
| ANDERSON FABIAN MATARRITA ARTAVIA | anderson.matarrta | MAT0576 |
| YOJAIRA NAVARRO CORRALES | yojaira.navarro | NAV0144 |
| FABIOLA PORRAS CASTRILLO | fabiola.porras | POR0226 |
| JIMENA TATIANA ROSALES CAMPOS | jimena.rosales | ROS0531 |
| JAYLIN VANESSA TORRES TORRES | jaylin.torres | TOR0570 |
| ASHLY CALDERON ALVARADO | ashly.calderon | CAL0014 |
| CALET CHAVES MORA | calet.chaves | CHA0484 |
| JARED CHAVES MORA | jared.chaves | CHA0714 |
| HANNA ELIZONDO FERNANDEZ | hanna.elizondo | ELI0617 |
| STACEY SOFIA GAMBOA VARGAS | stacey.gamboa | GAM0003 |
| CHENOA JIMENEZ ARIAS | chenoa.jimenez | JIM0035 |
| JOSEBETH LEIVA LAZO | josebeth.leiva | LEI0706 |
| DYLAN ANDRES MENA JUAREZ | dylan.mena | MEN0846 |
| YEIKOL ANDREY MONTIEL VARELA | yeikol.montiel | MON0722 |
| KEVIN MORENO MORALES | kevin.moreno | MOR0049 |
| MILEY SUSANA RODRIGUEZ QUIROS | miley.rodriguez | ROD0025 |
| MIJAIL SALAS RODRIGUEZ | mijail.salas | SAL0598 |
| SUYEN DE JESUS SIBAJA MADRIGAL | suyen.sibaja | SIB0603 |

**Fórmula**: `username = nombre.toLowerCase().split(' ')[0] + '.' + apellido1.toLowerCase()` / `password = primeros 3 de apellido1 en mayúscula + últimos 4 de cédula sin guión`

---

## Agentes Disponibles

| Agente | Especialidad |
|--------|-------------|
| `SeniorDev` | Arquitectura, backend Python, lógica de negocio |
| `FrontendDev` | HTML, CSS, JavaScript, UI/UX |
| `ExpertSQL` | Bases de datos, esquemas, consultas |
| `DevOps` | Despliegue, scripts, infraestructura |
| `GitExpert` | Git, ramas, commits, merges |
| `QA` | Pruebas, validación, calidad |

---

## Historial de Avances

| Fecha | Fase | Tareas Completadas | Observaciones |
|-------|------|-------------------|---------------|
| — | — | — | Pendiente de inicio |

---

*Plan creado el 20 de junio de 2026*  
*Proyecto: Examen Digital Simple v2*  
*Total: 39 tareas | 6 fases | 6 agentes*
