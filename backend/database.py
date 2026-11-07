"""
Database module for Examen Digital.
Provides SQLite connection and table creation.
"""
import csv
import hashlib
import hmac
import os
import secrets
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

import bcrypt

# Database path - project root (parent of backend/)
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "examen_db.sqlite"

# Listado de estudiantes (datos personales: fuera de git). Ver data/estudiantes.example.csv
ESTUDIANTES_CSV = Path(os.environ.get("ESTUDIANTES_CSV", PROJECT_ROOT / "data" / "estudiantes.csv"))


# Materias por sección (se crean para los periodos 1 y 2)
MATERIAS = {
    "11-1": [
        "Emprendimiento e Innovación",
        "Administración y Soporte a las Computadoras",
        "Configuración y Soporte a Redes",
    ],
    "11-2": [
        "Emprendimiento e Innovación",
        "Pruebas de SQA",
        "Gestión y Control de la Calidad del Software",
    ],
}


def cargar_estudiantes() -> list[tuple[str, str, str, str, str]]:
    """Lee el CSV de estudiantes: cedula, nombre, apellido1, apellido2, seccion."""
    if not ESTUDIANTES_CSV.exists():
        print(f"[AVISO] No existe {ESTUDIANTES_CSV}; no se cargarán estudiantes")
        return []
    with open(ESTUDIANTES_CSV, newline="", encoding="utf-8") as f:
        return [
            (r["cedula"], r["nombre"], r["apellido1"], r["apellido2"], r["seccion"])
            for r in csv.DictReader(f)
        ]


def hash_password(password: str) -> str:
    """Genera un hash bcrypt (con sal) de una contraseña."""
    rounds = int(os.environ.get("BCRYPT_ROUNDS", "12"))
    return bcrypt.hashpw(password.encode(), bcrypt.gensalt(rounds)).decode()


def is_legacy_hash(hashed: str) -> bool:
    """Los hashes antiguos eran SHA-256 hexadecimal sin sal (64 caracteres)."""
    return len(hashed) == 64 and all(c in "0123456789abcdef" for c in hashed)


def verify_password(password: str, hashed: str) -> bool:
    """Verifica una contraseña contra un hash bcrypt o, por compatibilidad, SHA-256."""
    if is_legacy_hash(hashed):
        return hmac.compare_digest(hashlib.sha256(password.encode()).hexdigest(), hashed)
    try:
        return bcrypt.checkpw(password.encode(), hashed.encode())
    except ValueError:
        return False


def calcular_username(nombre: str, apellido1: str) -> str:
    """Calcula el username."""
    primer_nombre = nombre.split(' ')[0].lower()
    return f"{primer_nombre}.{apellido1.lower()}"


def calcular_password(cedula: str, nombre: str, apellido1: str) -> str:
    """Calcula el password: 3 letras del nombre + ultimos 4 de cedula."""
    cedula_sin_guiones = cedula.replace('-', '')
    ultimos_4 = cedula_sin_guiones[-4:]
    primer_nombre = nombre.split(' ')[0]  # Toma solo el primer nombre
    return f"{primer_nombre[0:3].upper()}{ultimos_4}"


def get_db() -> sqlite3.Connection:
    """
    Obtiene una conexión a la base de datos SQLite.

    Returns:
        sqlite3.Connection: Conexión activa a la base de datos.
    """
    conn = sqlite3.connect(DATABASE_PATH, timeout=10)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")  # lecturas y escrituras simultáneas sin bloqueos
    return conn


@contextmanager
def get_db_context() -> Generator[sqlite3.Connection, None, None]:
    """
    Context manager para obtener conexión a la BD con cleanup automático.

    Yields:
        sqlite3.Connection: Conexión a la base de datos.
    """
    conn = get_db()
    try:
        yield conn
    finally:
        conn.close()


# Configuración institucional y de evaluación (editable desde el panel; ver tabla `ajustes`)
AJUSTES_DEFAULT = {
    "institucion": "CTP Las Palmitas",
    "direccion_regional": "Guápiles",
    "circuito": "06",
    "docente": "Fallas Rivas Luis Cupertino",
    "curso_lectivo": "2026",
    "nota_minima": "70",
}

RESPALDOS_DIR = PROJECT_ROOT / "respaldos"


def leer_ajustes(conn: sqlite3.Connection) -> dict[str, str]:
    """Ajustes guardados sobre los valores por defecto."""
    ajustes = dict(AJUSTES_DEFAULT)
    ajustes.update({r["clave"]: r["valor"] for r in conn.execute("SELECT clave, valor FROM ajustes")})
    return ajustes


def respaldar(destino: Path | None = None, mantener: int = 30) -> Path | None:
    """
    Copia consistente de la base (API de respaldo de SQLite), una por día.
    Conserva solo los últimos `mantener` respaldos. Devuelve la ruta creada o None si ya existía el de hoy.
    """
    from datetime import date

    destino = destino or RESPALDOS_DIR
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"examen_db_{date.today().isoformat()}.sqlite"
    if archivo.exists():
        return None
    origen = get_db()
    try:
        copia = sqlite3.connect(archivo)
        try:
            origen.backup(copia)
        finally:
            copia.close()
    finally:
        origen.close()
    for viejo in sorted(destino.glob("examen_db_*.sqlite"))[:-mantener]:
        viejo.unlink()
    return archivo


def _agregar_columnas(cursor: sqlite3.Cursor, tabla: str, columnas: dict[str, str]) -> None:
    """Agrega las columnas que aún no existan en la tabla."""
    existentes = {r["name"] for r in cursor.execute(f"PRAGMA table_info({tabla})")}
    for nombre, definicion in columnas.items():
        if nombre not in existentes:
            cursor.execute(f"ALTER TABLE {tabla} ADD COLUMN {nombre} {definicion}")


def init_db() -> int:
    """
    Inicializa la base de datos creando las tablas necesarias y poblando estudiantes.
    Returns:
        int: Número de estudiantes insertados (0 si ya existían)
    """
    with get_db_context() as conn:
        cursor = conn.cursor()

        # Tabla de estudiantes
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS estudiantes (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                cedula TEXT NOT NULL UNIQUE,
                nombre TEXT NOT NULL,
                apellido1 TEXT NOT NULL,
                apellido2 TEXT,
                seccion TEXT NOT NULL,
                username TEXT NOT NULL UNIQUE,
                password_hash TEXT NOT NULL,
                created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        """)

        # Tabla de intentos de examen
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS intentos (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                estudiante_id INTEGER NOT NULL,
                codigo_examen TEXT NOT NULL,
                respuestas_json TEXT NOT NULL,
                puntuacion INTEGER NOT NULL,
                total INTEGER NOT NULL,
                fecha_inicio TIMESTAMP,
                fecha_fin TIMESTAMP,
                FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
            )
        """)

        # Materias (sección, nombre, periodo) y notas del docente por estudiante y materia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS materias (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                seccion TEXT NOT NULL,
                nombre TEXT NOT NULL,
                periodo INTEGER NOT NULL,
                UNIQUE (seccion, nombre, periodo)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS notas (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                estudiante_id INTEGER NOT NULL,
                materia_id INTEGER NOT NULL,
                trabajo_cotidiano REAL,
                tareas REAL,
                prueba01 REAL,
                prueba02 REAL,
                proyecto REAL,
                asistencia REAL,
                UNIQUE (estudiante_id, materia_id),
                FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id),
                FOREIGN KEY (materia_id) REFERENCES materias(id)
            )
        """)
        cursor.executemany(
            "INSERT OR IGNORE INTO materias (seccion, nombre, periodo) VALUES (?, ?, ?)",
            [(sec, nombre, periodo) for sec, nombres in MATERIAS.items()
             for periodo in (1, 2) for nombre in nombres],
        )

        # Migraciones aditivas (se aplican a bases creadas con versiones anteriores)
        _agregar_columnas(cursor, "intentos", {
            "semilla": "INTEGER NOT NULL DEFAULT 0",       # semilla del barajado
            "incidencias": "INTEGER NOT NULL DEFAULT 0",   # salidas de la pestaña
            "anulado": "INTEGER NOT NULL DEFAULT 0",       # no cuenta en notas ni reportes
            "sospechoso": "INTEGER NOT NULL DEFAULT 0",
            "nota_docente": "TEXT",
            "minutos_extra": "INTEGER NOT NULL DEFAULT 0",
            "respuestas_parciales_json": "TEXT",
        })
        _agregar_columnas(cursor, "estudiantes", {
            "activo": "INTEGER NOT NULL DEFAULT 1",
            "debe_cambiar_password": "INTEGER NOT NULL DEFAULT 0",
            "ultimo_acceso": "TEXT",
        })

        # Configuración por examen (habilitado y ventana de disponibilidad)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS examenes_config (
                codigo TEXT PRIMARY KEY,
                habilitado INTEGER NOT NULL DEFAULT 1,
                desde TEXT,
                hasta TEXT,
                secciones TEXT
            )
        """)

        # Ajustes institucionales (clave/valor) y ponderaciones por materia
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ajustes (
                clave TEXT PRIMARY KEY,
                valor TEXT NOT NULL
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS ponderaciones (
                materia_id INTEGER NOT NULL,
                componente TEXT NOT NULL,
                peso REAL NOT NULL,
                PRIMARY KEY (materia_id, componente),
                FOREIGN KEY (materia_id) REFERENCES materias(id)
            )
        """)
        # Asistencia por lección: una sesión (fecha) por materia y el estado de cada estudiante
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sesiones (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL,
                fecha TEXT NOT NULL,
                lecciones INTEGER NOT NULL DEFAULT 1,
                tema TEXT,
                UNIQUE (materia_id, fecha),
                FOREIGN KEY (materia_id) REFERENCES materias(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS asistencia (
                sesion_id INTEGER NOT NULL,
                estudiante_id INTEGER NOT NULL,
                estado TEXT NOT NULL,
                observacion TEXT,
                PRIMARY KEY (sesion_id, estudiante_id),
                FOREIGN KEY (sesion_id) REFERENCES sesiones(id) ON DELETE CASCADE,
                FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
            )
        """)
        # Actividades evaluativas (tareas, proyectos, trabajo cotidiano...) con rúbrica opcional
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS actividades (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                materia_id INTEGER NOT NULL,
                componente TEXT NOT NULL,
                nombre TEXT NOT NULL,
                fecha_entrega TEXT,
                puntos_max REAL NOT NULL,
                criterios_json TEXT NOT NULL DEFAULT '[]',
                UNIQUE (materia_id, componente, nombre),
                FOREIGN KEY (materia_id) REFERENCES materias(id)
            )
        """)
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS calificaciones (
                actividad_id INTEGER NOT NULL,
                estudiante_id INTEGER NOT NULL,
                estado TEXT NOT NULL DEFAULT 'entregado',
                puntos REAL,
                criterios_json TEXT NOT NULL DEFAULT '[]',
                observacion TEXT,
                nota_interna TEXT,
                PRIMARY KEY (actividad_id, estudiante_id),
                FOREIGN KEY (actividad_id) REFERENCES actividades(id) ON DELETE CASCADE,
                FOREIGN KEY (estudiante_id) REFERENCES estudiantes(id)
            )
        """)
        _agregar_columnas(cursor, "examenes_config", {
            "materia_id": "INTEGER",  # materia y componente (prueba01/prueba02) donde se importa la nota
            "componente": "TEXT",
        })

        # Bitácora de acciones del docente
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS bitacora (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                fecha TEXT NOT NULL,
                accion TEXT NOT NULL,
                detalle TEXT
            )
        """)

        # Un solo intento por estudiante y examen
        cursor.execute(
            "CREATE UNIQUE INDEX IF NOT EXISTS idx_intento_unico "
            "ON intentos (estudiante_id, codigo_examen)"
        )

        conn.commit()

    # Poblar estudiantes si la tabla está vacía
    return ensure_students()


def ensure_students() -> int:
    """
    Verifica si hay estudiantes en la BD y los pobla si no existen.
    Returns:
        int: Número de estudiantes insertados (0 si ya existían)
    """
    with get_db_context() as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM estudiantes")
        count = cursor.fetchone()[0]

        if count > 0:
            return 0  # Ya hay estudiantes

        # Poblar estudiantes
        insertados = 0
        for cedula, nombre, apellido1, apellido2, seccion in cargar_estudiantes():
            username = calcular_username(nombre, apellido1)
            password_texto = calcular_password(cedula, nombre, apellido1)
            password_hash = hash_password(password_texto)

            try:
                cursor.execute(
                    """INSERT INTO estudiantes
                    (cedula, nombre, apellido1, apellido2, seccion, username, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cedula, nombre, apellido1, apellido2, seccion, username, password_hash)
                )
                insertados += 1
            except sqlite3.IntegrityError:
                pass  # Ignorar duplicados

        conn.commit()
        return insertados


ALFABETO_TEMPORAL = "ABCDEFGHJKMNPQRSTUVWXYZ23456789"  # sin caracteres ambiguos (0/O, 1/I/L)


def generar_password_temporal(largo: int = 8) -> str:
    """Contraseña temporal aleatoria y fácil de dictar."""
    return "".join(secrets.choice(ALFABETO_TEMPORAL) for _ in range(largo))


def crear_estudiante(
    conn: sqlite3.Connection, cedula: str, nombre: str, apellido1: str,
    apellido2: str, seccion: str, password: str | None = None,
) -> tuple[int, str, str]:
    """
    Inserta un estudiante con contraseña temporal (debe cambiarla al entrar).

    Returns:
        (id, username, password_temporal)
    Raises:
        sqlite3.IntegrityError: si la cédula o el usuario ya existen.
    """
    username = calcular_username(nombre, apellido1)
    password = password or generar_password_temporal()
    cursor = conn.execute(
        "INSERT INTO estudiantes (cedula, nombre, apellido1, apellido2, seccion, username, "
        "password_hash, debe_cambiar_password) VALUES (?, ?, ?, ?, ?, ?, ?, 1)",
        (cedula, nombre, apellido1, apellido2, seccion, username, hash_password(password)),
    )
    return cursor.lastrowid, username, password
