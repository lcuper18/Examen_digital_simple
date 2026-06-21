"""
Módulo de base de datos para Examen Digital Simple v2.
Proporciona conexión SQLite y creación de tablas.
"""
import sqlite3
from contextlib import contextmanager
from pathlib import Path
from typing import Generator

DATABASE_PATH = Path(__file__).parent / "examen_db.sqlite"


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


def init_db() -> None:
    """
    Inicializa la base de datos creando las tablas necesarias:
    - estudiantes: Información de estudiantes
    - intentos: Intentos de examen realizados
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
