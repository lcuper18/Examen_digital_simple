"""
Ajustes routes - Datos institucionales, nota mínima y datos de red del servidor (docente).
"""
import socket
import subprocess
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from backend import bitacora, database, ratelimit, security
from backend.routes.auth import CLAVE_DOCENTE_AJUSTE, HASH_DE_FABRICA, clave_de_fabrica, hash_docente
from backend.version import VERSION

router = APIRouter(
    prefix="/api/docente", tags=["ajustes"], dependencies=[Depends(security.require_docente)]
)
publico = APIRouter(prefix="/api", tags=["config"])


@publico.get("/config")
def config_publica() -> dict[str, Any]:
    """Datos institucionales para mostrar en pantalla y PDF (no son sensibles)."""
    with database.get_db_context() as conn:
        a = database.leer_ajustes(conn)
    return {"ok": True, "institucion": a["institucion"], "curso_lectivo": a["curso_lectivo"], "version": VERSION}


@router.get("/ajustes")
def obtener_ajustes() -> dict[str, Any]:
    with database.get_db_context() as conn:
        return {"ok": True, "ajustes": database.leer_ajustes(conn), "clave_de_fabrica": clave_de_fabrica(conn)}


class CambiarClaveDocente(BaseModel):
    actual: str
    nueva: str


@router.post("/cambiar-password")
def cambiar_password_docente(request: CambiarClaveDocente) -> dict[str, Any]:
    """Cambia la contraseña del docente (se guarda con bcrypt). Pide la actual y una nueva distinta de la de fábrica."""
    ratelimit.verificar("docente-cambio")
    with database.get_db_context() as conn:
        if not database.verify_password(request.actual, hash_docente(conn)):
            ratelimit.registrar_fallo("docente-cambio", maximo=5)
            raise HTTPException(status_code=400, detail="La contraseña actual no es correcta")
        if len(request.nueva) < 8:
            raise HTTPException(status_code=400, detail="La nueva contraseña debe tener al menos 8 caracteres")
        if database.verify_password(request.nueva, HASH_DE_FABRICA) or request.nueva == request.actual:
            raise HTTPException(status_code=400, detail="Elige una contraseña distinta de la actual y de la de fábrica")
        conn.execute(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            (CLAVE_DOCENTE_AJUSTE, database.hash_password(request.nueva)),
        )
        bitacora.registrar(conn, "cambiar_clave_docente", "")
        conn.commit()
    ratelimit.limpiar("docente-cambio")
    return {"ok": True}


class GuardarAjustes(BaseModel):
    ajustes: dict[str, str]


@router.put("/ajustes")
def guardar_ajustes(request: GuardarAjustes) -> dict[str, Any]:
    desconocidas = set(request.ajustes) - set(database.AJUSTES_DEFAULT)
    if desconocidas:
        raise HTTPException(status_code=400, detail=f"Ajuste desconocido: {', '.join(sorted(desconocidas))}")
    valores = {k: v.strip() for k, v in request.ajustes.items()}
    if any(not v for v in valores.values()):
        raise HTTPException(status_code=400, detail="Ningún ajuste puede quedar vacío")
    if "nota_minima" in valores:
        try:
            if not 0 <= float(valores["nota_minima"]) <= 100:
                raise ValueError
        except ValueError:
            raise HTTPException(status_code=400, detail="La nota mínima debe estar entre 0 y 100")
    for clave, minimo, maximo in (("periodo_actual", 1, 4), ("umbral_ausencias", 1, 100)):
        if clave in valores:
            try:
                if not minimo <= float(valores[clave]) <= maximo:
                    raise ValueError
            except ValueError:
                raise HTTPException(status_code=400, detail=f"«{clave}» debe estar entre {minimo} y {maximo}")
    with database.get_db_context() as conn:
        conn.executemany(
            "INSERT INTO ajustes (clave, valor) VALUES (?, ?) "
            "ON CONFLICT (clave) DO UPDATE SET valor = excluded.valor",
            list(valores.items()),
        )
        bitacora.registrar(conn, "guardar_ajustes", ", ".join(sorted(valores)))
        conn.commit()
        return {"ok": True, "ajustes": database.leer_ajustes(conn)}


@router.get("/primeros-pasos")
def primeros_pasos() -> dict[str, Any]:
    """Lista de arranque para el docente nuevo; cada paso se marca solo cuando ya hay datos que lo demuestran."""
    with database.get_db_context() as conn:
        cuenta = lambda sql: conn.execute(sql).fetchone()[0]
        guardados = {r["clave"] for r in conn.execute("SELECT clave FROM ajustes")}
        pasos = [
            ("institucion", "Revisa los datos de la institución y del docente", "institucion" in guardados, "ajustes"),
            ("encargados", "Importa los datos de los encargados de tus estudiantes",
             cuenta("SELECT COUNT(*) FROM estudiantes WHERE COALESCE(encargado_nombre, '') <> ''") > 0, "estudiantes"),
            ("vinculos", "Vincula cada examen a su materia para importar las notas con un clic",
             cuenta("SELECT COUNT(*) FROM examenes_config WHERE materia_id IS NOT NULL") > 0, "examenes"),
            ("lista", "Pasa tu primera lista de asistencia", cuenta("SELECT COUNT(*) FROM sesiones") > 0, "asistencia"),
            ("actividad", "Crea o importa una actividad con su rúbrica", cuenta("SELECT COUNT(*) FROM actividades") > 0, "actividades"),
            ("publicar", "Publica las notas de una materia para tus estudiantes",
             cuenta("SELECT COUNT(*) FROM publicaciones WHERE publicado = 1") > 0, "notas"),
        ]
    return {"ok": True, "pasos": [{"id": i, "texto": t, "hecho": h, "ir": ir} for i, t, h, ir in pasos]}


def _ip_local() -> str | None:
    """IP de la Mac en la red (no envía tráfico: solo consulta la ruta por defecto)."""
    s = socket.socket(socket.AF_INET, socket.SOCK_DGRAM)
    try:
        s.connect(("10.255.255.255", 1))
        return s.getsockname()[0]
    except OSError:
        return None
    finally:
        s.close()


def _nombre_local() -> str | None:
    """Nombre Bonjour de la Mac (el que permite entrar con http://nombre.local, aunque cambie la IP)."""
    try:
        nombre = subprocess.run(
            ["scutil", "--get", "LocalHostName"], capture_output=True, text=True, timeout=2, check=True,
        ).stdout.strip()
    except (OSError, subprocess.SubprocessError):
        nombre = socket.gethostname().split(".")[0]
    return f"{nombre}.local" if nombre and not nombre.replace(".", "").isdigit() else None


@router.get("/red")
def datos_de_red(request: Request) -> dict[str, Any]:
    """Direcciones para que los estudiantes entren (la IP puede cambiar; el nombre .local no)."""
    puerto = request.url.port or 80
    ip, nombre = _ip_local(), _nombre_local()
    return {
        "ok": True, "ip": ip, "nombre": nombre,
        "url_ip": f"http://{ip}:{puerto}" if ip else None,
        "url_nombre": f"http://{nombre}:{puerto}" if nombre else None,
    }
