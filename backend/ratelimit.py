"""
Limitador simple en memoria: bloquea una clave tras varios fallos seguidos.
"""
import time

from fastapi import HTTPException

_fallos: dict[str, list[float]] = {}
_bloqueos: dict[str, float] = {}

VENTANA_SEGUNDOS = 300
BLOQUEO_SEGUNDOS = 300


def verificar(clave: str) -> None:
    """Lanza 429 si la clave está bloqueada."""
    hasta = _bloqueos.get(clave)
    if hasta and hasta > time.time():
        raise HTTPException(
            status_code=429,
            detail="Demasiados intentos fallidos. Espera unos minutos e intenta de nuevo.",
        )
    _bloqueos.pop(clave, None)


def registrar_fallo(clave: str, maximo: int = 5) -> None:
    """Registra un fallo y bloquea la clave si supera el máximo en la ventana."""
    ahora = time.time()
    recientes = [t for t in _fallos.get(clave, []) if ahora - t < VENTANA_SEGUNDOS] + [ahora]
    _fallos[clave] = recientes
    if len(recientes) >= maximo:
        _bloqueos[clave] = ahora + BLOQUEO_SEGUNDOS
        _fallos.pop(clave, None)


def limpiar(clave: str) -> None:
    """Olvida los fallos de una clave tras un acceso correcto."""
    _fallos.pop(clave, None)


def reiniciar() -> None:
    """Vacía todo el estado (usado por los tests)."""
    _fallos.clear()
    _bloqueos.clear()


def bloqueada_con_sufijo(sufijo: str) -> bool:
    """True si alguna clave bloqueada termina en el sufijo (p. ej. ':usuario')."""
    ahora = time.time()
    return any(k.endswith(sufijo) and hasta > ahora for k, hasta in _bloqueos.items())


def limpiar_con_sufijo(sufijo: str) -> None:
    """Quita bloqueos y fallos de todas las claves que terminan en el sufijo."""
    for almacen in (_fallos, _bloqueos):
        for clave in [k for k in almacen if k.endswith(sufijo)]:
            almacen.pop(clave, None)
