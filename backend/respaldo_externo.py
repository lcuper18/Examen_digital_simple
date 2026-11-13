"""
Copia de respaldo externa: una copia de la base de datos fuera del computador (iCloud Drive, disco o USB).

El docente elige una carpeta en Ajustes. Cada hora (y al pulsar «Respaldar ahora») se guarda ahí una copia
consistente de la base, un archivo por día (`lectiva_respaldo_AAAA-MM-DD.sqlite`, que se reescribe durante el día),
y se conservan los últimos 30. La copia se escribe en un archivo temporal y se verifica antes de reemplazar la
anterior, así un corte o una memoria desconectada a medias nunca daña la copia buena.
"""
import os
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from backend import database

CLAVE_CARPETA = "respaldo_externo_carpeta"
CLAVE_ULTIMO = "respaldo_externo_ultimo"      # fecha ISO (UTC) de la última copia que sí se hizo
CLAVE_ERROR = "respaldo_externo_error"        # motivo del último fallo; vacío si todo bien
SUBCARPETA = "Lectiva respaldos"
PREFIJO = "lectiva_respaldo_"
MANTENER = 30

# Volúmenes del sistema que no sirven como destino
_VOLUMENES_DEL_SISTEMA = {"Macintosh HD", "Macintosh HD - Data", "Recovery", "Preboot", "VM", "Update", "xarts", "iSCPreboot", "Hardware"}


class RespaldoError(Exception):
    """Fallo explicable al docente (carpeta no disponible, sin permiso, copia dañada…)."""


def _leer(conn, clave: str) -> str:
    fila = conn.execute("SELECT valor FROM ajustes WHERE clave = ?", (clave,)).fetchone()
    return fila["valor"] if fila else ""


def _guardar(conn, **valores: str) -> None:
    for clave, valor in valores.items():
        conn.execute(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            (clave, valor),
        )


def estado(conn) -> dict[str, Any]:
    """Configuración y estado actual para mostrar en pantalla."""
    carpeta = _leer(conn, CLAVE_CARPETA)
    return {
        "carpeta": carpeta,
        "destino": str(Path(carpeta) / SUBCARPETA) if carpeta else "",
        "ultimo": _leer(conn, CLAVE_ULTIMO) or None,
        "error": _leer(conn, CLAVE_ERROR) or None,
    }


def sugerencias() -> list[dict[str, str]]:
    """Lugares razonables para guardar la copia: iCloud Drive y los discos o memorias conectados."""
    lugares = []
    icloud = Path.home() / "Library" / "Mobile Documents" / "com~apple~CloudDocs"
    if icloud.is_dir():
        lugares.append({"nombre": "iCloud Drive", "ruta": str(icloud)})
    volumenes = Path("/Volumes")
    if volumenes.is_dir():
        for v in sorted(volumenes.iterdir()):
            if v.is_dir() and v.name not in _VOLUMENES_DEL_SISTEMA and not v.is_symlink():
                lugares.append({"nombre": f"Disco o USB «{v.name}»", "ruta": str(v)})
    return lugares


def validar_carpeta(ruta: str) -> Path:
    """La carpeta debe ser absoluta, existir, estar fuera del proyecto y permitir escribir."""
    ruta = (ruta or "").strip()
    if not ruta:
        raise RespaldoError("Escribe la ruta de la carpeta.")
    carpeta = Path(os.path.expanduser(ruta))
    if not carpeta.is_absolute():
        raise RespaldoError("La ruta debe ser completa (empieza con /).")
    carpeta = carpeta.resolve()
    if not carpeta.is_dir():
        raise RespaldoError("La carpeta no existe o no está disponible (¿está conectada la memoria USB o el disco?).")
    if database.PROJECT_ROOT.resolve() in (carpeta, *carpeta.parents):
        raise RespaldoError("Elige una carpeta fuera del proyecto: una copia en el mismo lugar no protege de nada.")
    try:
        prueba = carpeta / f".lectiva_prueba_{os.getpid()}"
        prueba.write_text("ok")
        prueba.unlink()
    except PermissionError:
        raise RespaldoError(
            "macOS no deja escribir en esa carpeta. Abre Ajustes del Sistema → Privacidad y seguridad → "
            "Archivos y carpetas (o Acceso total al disco) y permite a Lectiva, o elige otra carpeta."
        )
    except OSError as error:
        raise RespaldoError(f"No se puede escribir en esa carpeta: {error.strerror or error}")
    return carpeta


def _verificar(copia: Path) -> None:
    """Abre la copia y comprueba que no esté dañada y que tenga las tablas principales."""
    try:
        con = sqlite3.connect(f"file:{copia}?mode=ro", uri=True)
        try:
            if con.execute("PRAGMA integrity_check").fetchone()[0] != "ok":
                raise RespaldoError("La copia salió dañada; se conserva la anterior.")
            con.execute("SELECT COUNT(*) FROM estudiantes").fetchone()
            con.execute("SELECT COUNT(*) FROM materias").fetchone()
        finally:
            con.close()
    except sqlite3.Error as error:
        raise RespaldoError(f"La copia no se pudo verificar: {error}")


def _copiar(carpeta: Path) -> Path:
    """Escribe la copia del día en `carpeta/Lectiva respaldos/`, verificada, y poda las más antiguas."""
    destino = carpeta / SUBCARPETA
    destino.mkdir(exist_ok=True)  # sin parents: si la carpeta elegida ya no existe, falla en vez de inventarla
    archivo = destino / f"{PREFIJO}{datetime.now():%Y-%m-%d}.sqlite"
    temporal = destino / f".{archivo.name}.tmp"
    try:
        database.copiar_base(temporal)
        # La base original usa el modo WAL (archivos -wal y -shm aparte); la copia debe ser un solo archivo
        # autosuficiente, que se pueda abrir o restaurar sin nada más.
        con = sqlite3.connect(temporal)
        try:
            con.execute("PRAGMA journal_mode = DELETE")
        finally:
            con.close()
        _verificar(temporal)
        os.replace(temporal, archivo)
    finally:
        for resto in (temporal, Path(f"{temporal}-wal"), Path(f"{temporal}-shm")):
            resto.unlink(missing_ok=True)
    for viejo in sorted(destino.glob(f"{PREFIJO}*.sqlite"))[:-MANTENER]:
        viejo.unlink()
    return archivo


def respaldar_externo() -> dict[str, Any]:
    """
    Hace la copia externa si hay una carpeta configurada. Guarda el resultado (fecha o motivo del fallo) para
    mostrarlo en pantalla; nunca lanza: un fallo aquí no debe afectar al servidor.
    """
    with database.get_db_context() as conn:
        carpeta_texto = _leer(conn, CLAVE_CARPETA)
    if not carpeta_texto:
        return {"ok": False, "motivo": "sin_configurar"}
    try:
        carpeta = validar_carpeta(carpeta_texto)
        archivo = _copiar(carpeta)
        resultado = {"ok": True, "archivo": archivo.name, "bytes": archivo.stat().st_size}
        cambios = {CLAVE_ULTIMO: datetime.now(timezone.utc).isoformat(), CLAVE_ERROR: ""}
    except RespaldoError as error:
        resultado, cambios = {"ok": False, "motivo": "error", "error": str(error)}, {CLAVE_ERROR: str(error)}
    except OSError as error:
        mensaje = f"No se pudo guardar la copia: {error.strerror or error}"
        resultado, cambios = {"ok": False, "motivo": "error", "error": mensaje}, {CLAVE_ERROR: mensaje}
    with database.get_db_context() as conn:
        _guardar(conn, **cambios)
        conn.commit()
    return resultado


def configurar(ruta: str | None) -> dict[str, Any]:
    """Elige (o quita, con vacío) la carpeta externa y, si se eligió, hace la primera copia de inmediato."""
    if not (ruta or "").strip():
        with database.get_db_context() as conn:
            _guardar(conn, **{CLAVE_CARPETA: "", CLAVE_ERROR: ""})
            conn.commit()
        return {"ok": True, "desactivado": True}
    carpeta = validar_carpeta(ruta)  # lanza RespaldoError si no sirve; no se guarda nada
    with database.get_db_context() as conn:
        _guardar(conn, **{CLAVE_CARPETA: str(carpeta), CLAVE_ERROR: ""})
        conn.commit()
    return respaldar_externo()
