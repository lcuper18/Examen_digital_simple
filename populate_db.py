"""
Script para poblar la base de datos con los 26 estudiantes.
Ejecutar una sola vez: python populate_db.py
"""
import hashlib
import sys

# Agregar el directorio padre al path para poder importar database
sys.path.insert(0, '.')

import database


def hash_password(password: str) -> str:
    """Genera hash SHA-256 de una contraseña."""
    return hashlib.sha256(password.encode()).hexdigest()


# Lista de estudiantes con datos del proyecto
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


def calcular_username(nombre: str, apellido1: str) -> str:
    """
    Calcula el username según la fórmula:
    username = nombre.split(' ')[0].lower() + '.' + apellido1.lower()

    Args:
        nombre: Nombre completo del estudiante.
        apellido1: Primer apellido.

    Returns:
        str: Username generado.
    """
    primer_nombre = nombre.split(' ')[0].lower()
    return f"{primer_nombre}.{apellido1.lower()}"


def calcular_password(cedula: str, apellido1: str) -> str:
    """
    Calcula el password según la fórmula:
    password = apellido1[0:3].upper() + cedula.replace('-','')[-4:]

    Args:
        cedula: Cédula del estudiante con guiones.
        apellido1: Primer apellido.

    Returns:
        str: Password generado.
    """
    cedula_sin_guiones = cedula.replace('-', '')
    ultimos_4 = cedula_sin_guiones[-4:]
    return f"{apellido1[0:3].upper()}{ultimos_4}"


def poblar_estudiantes():
    """Inserta los 26 estudiantes en la base de datos."""
    # Inicializar la base de datos (crea tablas si no existen)
    database.init_db()

    with database.get_db_context() as conn:
        cursor = conn.cursor()

        insertados = 0
        errores = 0

        for cedula, nombre, apellido1, apellido2, seccion in ESTUDIANTES:
            username = calcular_username(nombre, apellido1)
            password_texto = calcular_password(cedula, apellido1)
            password_hash = hash_password(password_texto)

            try:
                cursor.execute(
                    """
                    INSERT INTO estudiantes
                    (cedula, nombre, apellido1, apellido2, seccion, username, password_hash)
                    VALUES (?, ?, ?, ?, ?, ?, ?)
                    """,
                    (cedula, nombre, apellido1, apellido2, seccion, username, password_hash)
                )
                insertados += 1
                print(f"  ✓ {username} | Password: {password_texto}")

            except Exception as e:
                errores += 1
                print(f"  ✗ Error con {cedula}: {e}")

        conn.commit()

    print(f"\n{'='*60}")
    print(f"RESULTADO: {insertados} insertados, {errores} errores")
    print(f"{'='*60}")

    return insertados, errores


if __name__ == "__main__":
    print("=" * 60)
    print("POBLANDO BASE DE DATOS - 26 ESTUDIANTES")
    print("=" * 60)
    poblar_estudiantes()
