"""
Lectura de hojas del docente (CSV con ';' o ',' y xlsx) y emparejamiento de estudiantes por cédula o nombre.
"""
import csv
import io
import re
import unicodedata
import zipfile
from typing import Any

from fastapi import HTTPException, Request
from openpyxl import load_workbook

# Una hoja de notas o una lista de estudiantes pesa unos pocos KB; 5 MB es de sobra y evita que un archivo enorme
# (o un .xlsx que se descomprime a cientos de MB) deje sin memoria al servidor.
MAX_ARCHIVO_BYTES = 5 * 1024 * 1024
MAX_XLSX_DESCOMPRIMIDO = 50 * 1024 * 1024


async def leer_cuerpo(request: Request, maximo: int = MAX_ARCHIVO_BYTES) -> bytes:
    """Lee el cuerpo de la petición (un archivo subido) y rechaza con 413 si pasa del máximo, sin cargarlo completo."""
    detalle = f"El archivo es demasiado grande (máximo {maximo // (1024 * 1024)} MB)"
    declarado = request.headers.get("content-length")
    if declarado and declarado.isdigit() and int(declarado) > maximo:
        raise HTTPException(status_code=413, detail=detalle)
    partes, total = [], 0
    async for trozo in request.stream():
        total += len(trozo)
        if total > maximo:
            raise HTTPException(status_code=413, detail=detalle)
        partes.append(trozo)
    return b"".join(partes)


def sin_tildes(texto: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFD", texto) if unicodedata.category(c) != "Mn")


def palabras(nombre: str) -> frozenset[str]:
    """Nombre sin tildes, en minúscula y sin importar el orden ('CASTRO LEÓN, Diana' == 'Diana Castro León')."""
    return frozenset(re.sub(r"[^a-z ]", " ", sin_tildes(nombre).lower()).split())


def a_numero(valor: Any) -> float | None:
    """Número de una celda: acepta coma decimal; vacío o texto no numérico da None."""
    if valor is None or isinstance(valor, bool):
        return None
    if isinstance(valor, (int, float)):
        return float(valor)
    texto = str(valor).strip().replace(",", ".")
    try:
        return float(texto) if texto else None
    except ValueError:
        return None


def _filas_de(hoja) -> list[list[Any]]:
    """Filas de una hoja; corta tras muchas filas vacías seguidas (algunos Excel declaran un millón de filas)."""
    filas, vacias = [], 0
    for fila in hoja.iter_rows(values_only=True):
        if all(c is None for c in fila):
            vacias += 1
            if vacias >= 100:
                break
        else:
            vacias = 0
        filas.append(list(fila))
    while filas and all(c is None for c in filas[-1]):
        filas.pop()
    return filas


def _revisar_xlsx(datos: bytes) -> None:
    """Un .xlsx es un zip: uno pequeño puede abrirse a cientos de MB. Se revisa el tamaño abierto antes de leerlo."""
    try:
        if sum(i.file_size for i in zipfile.ZipFile(io.BytesIO(datos)).infolist()) > MAX_XLSX_DESCOMPRIMIDO:
            raise HTTPException(status_code=413, detail="El archivo de Excel es demasiado grande al abrirse")
    except zipfile.BadZipFile:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo de Excel")


def leer_filas(datos: bytes) -> list[list[Any]]:
    """Filas de la primera hoja de un xlsx, o de un CSV (utf-8 con o sin BOM, separado por ';' o ',')."""
    if not datos:
        raise HTTPException(status_code=400, detail="El archivo está vacío")
    if datos[:2] == b"PK":
        _revisar_xlsx(datos)
        try:
            hoja = load_workbook(io.BytesIO(datos), data_only=True, read_only=True).worksheets[0]
            return _filas_de(hoja)
        except Exception:
            raise HTTPException(status_code=400, detail="No se pudo leer el archivo de Excel")
    try:
        texto = datos.decode("utf-8-sig")
    except UnicodeDecodeError:
        texto = datos.decode("latin-1")
    primera = texto.splitlines()[0] if texto.strip() else ""
    delimitador = ";" if primera.count(";") >= primera.count(",") else ","
    return [list(f) for f in csv.reader(io.StringIO(texto), delimiter=delimitador)]


def leer_hojas(datos: bytes) -> list[tuple[str, list[list[Any]]]]:
    """Todas las hojas de un xlsx como (nombre, filas)."""
    if datos[:2] != b"PK":
        raise HTTPException(status_code=400, detail="Se esperaba un archivo de Excel (.xlsx)")
    _revisar_xlsx(datos)
    try:
        libro = load_workbook(io.BytesIO(datos), data_only=True, read_only=True)
        return [(h.title, _filas_de(h)) for h in libro.worksheets]
    except Exception:
        raise HTTPException(status_code=400, detail="No se pudo leer el archivo de Excel")


def emparejar(estudiantes: list[Any]):
    """Devuelve una función que encuentra el id de un estudiante por cédula (sin guiones) o por nombre."""
    por_cedula = {re.sub(r"\D", "", e["cedula"]): e["id"] for e in estudiantes}
    por_nombre = {
        palabras(f"{e['nombre']} {e['apellido1']} {e['apellido2'] or ''}"): e["id"] for e in estudiantes
    }

    def buscar(cedula: Any = None, nombre: Any = None) -> int | None:
        if cedula is not None:
            digitos = re.sub(r"\D", "", str(int(cedula)) if isinstance(cedula, float) else str(cedula))
            if digitos in por_cedula:
                return por_cedula[digitos]
        if nombre:
            clave = palabras(str(nombre))
            if clave in por_nombre:
                return por_nombre[clave]
            # nombres incompletos: coincide si todas las palabras de uno están en el otro (y es único)
            candidatos = [i for k, i in por_nombre.items() if clave and (clave <= k or k <= clave)]
            if len(candidatos) == 1:
                return candidatos[0]
        return None

    return buscar
