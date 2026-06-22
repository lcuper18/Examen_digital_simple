"""
Database module for Examen Digital.
Provides SQLite connection and table creation.
"""
import sqlite3
import hashlib
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

# Database path - project root (parent of backend/)
PROJECT_ROOT = Path(__file__).parent.parent
DATABASE_PATH = PROJECT_ROOT / "examen_db.sqlite"

# Student data for auto-population
ESTUDIANTES = [
    # Sección 11-1
    ("1-2050-0131", "WESLY ABDRIEL", "ALVARADO", "MORA", "11-1"),
    ("7-0457-0912", "MARIA", "ARTAVIA", "MONDRAGON", "11-1"),
    ("7-0344-0360", "KARINA YULIETH", "CARRILLO", "AGUIRRE", "11-1"),
    ("7-0345-0802", "DIANA FIORELLA", "CASTRO", "LEON", "11-1"),
    ("1-2055-0786", "BRENAN SOFIA", "CENTENO", "SALAS", "11-1"),
    ("4-0276-0494", "YARELIS ILDANIA", "GARCIA", "JAIME", "11-1"),
    ("7-0345-0108", "KIARA", "JIMENEZ", "OPORTA", "11-1"),
    ("7-0348-0137", "EVONY SIDALI", "MARTINEZ", "ROMERO", "11-1"),
    ("7-0343-0576", "ANDERSON FABIAN", "MATARRITA", "ARTAVIA", "11-1"),
    ("7-0343-0144", "YOJAIRA", "NAVARRO", "CORRALES", "11-1"),
    ("7-0344-0226", "FABIOLA", "PORRAS", "CASTRILLO", "11-1"),
    ("4-0284-0531", "JIMENA TATIANA", "ROSALES", "CAMPOS", "11-1"),
    ("7-0349-0570", "JAYLIN VANESSA", "TORRES", "TORRES", "11-1"),
    # Sección 11-2
    ("1-2054-0014", "ASHLY", "CALDERON", "ALVARADO", "11-2"),
    ("7-0347-0484", "CALET", "CHAVES", "MORA", "11-2"),
    ("1-2013-0714", "JARED", "CHAVES", "MORA", "11-2"),
    ("7-0347-0617", "HANNA", "ELIZONDO", "FERNANDEZ", "11-2"),
    ("7-0345-0003", "STACEY SOFIA", "GAMBOA", "VARGAS", "11-2"),
    ("1-2057-0035", "CHENOA", "JIMENEZ", "ARIAS", "11-2"),
    ("7-0349-0706", "JOSEBETH", "LEIVA", "LAZO", "11-2"),
    ("1-2066-0846", "DYLAN ANDRES", "MENA", "JUAREZ", "11-2"),
    ("1-2047-0722", "YEIKOL ANDREY", "MONTIEL", "VARELA", "11-2"),
    ("7-0344-0049", "KEVIN", "MORENO", "MORALES", "11-2"),
    ("7-0347-0025", "MILEY SUSANA", "RODRIGUEZ", "QUIROS", "11-2"),
    ("7-0347-0598", "MIJAIL", "SALAS", "RODRIGUEZ", "11-2"),
    ("7-0349-0603", "SUYEN DE JESUS", "SIBAJA", "MADRIGAL", "11-2"),
]


def hash_password(password: str) -> str:
    """Genera hash SHA-256 de una contraseña."""
    return hashlib.sha256(password.encode()).hexdigest()


def calcular_username(nombre: str, apellido1: str) -> str:
    """Calcula el username."""
    primer_nombre = nombre.split(' ')[0].lower()
    return f"{primer_nombre}.{apellido1.lower()}"


def calcular_password(cedula: str, apellido1: str) -> str:
    """Calcula el password."""
    cedula_sin_guiones = cedula.replace('-', '')
    ultimos_4 = cedula_sin_guiones[-4:]
    return f"{apellido1[0:3].upper()}{ultimos_4}"


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
        for cedula, nombre, apellido1, apellido2, seccion in ESTUDIANTES:
            username = calcular_username(nombre, apellido1)
            password_texto = calcular_password(cedula, apellido1)
            password_hash = hash_password(password_texto)

            try:
                cursor.execute(
                    """INSERT INTO estudiantes
                    (cedula, nombre, apellido1, apellido2, seccion, username, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)""",
                    (cedula, nombre, apellido1, apellido2, seccion, username, password_hash)
                )
                insertados += 1
            except Exception:
                pass  # Ignorar duplicados

        conn.commit()
        return insertados
