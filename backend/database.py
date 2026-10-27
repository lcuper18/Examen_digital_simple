"""
Database module for Examen Digital.
Provides SQLite connection and table creation.
"""
import csv
import hashlib
import hmac
import os
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
    conn = sqlite3.connect(DATABASE_PATH)
    conn.row_factory = sqlite3.Row
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

        # Migración: semilla del barajado e incidencias (cambios de pestaña) por intento
        columnas = {r["name"] for r in cursor.execute("PRAGMA table_info(intentos)")}
        if "semilla" not in columnas:
            cursor.execute("ALTER TABLE intentos ADD COLUMN semilla INTEGER NOT NULL DEFAULT 0")
        if "incidencias" not in columnas:
            cursor.execute("ALTER TABLE intentos ADD COLUMN incidencias INTEGER NOT NULL DEFAULT 0")

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
