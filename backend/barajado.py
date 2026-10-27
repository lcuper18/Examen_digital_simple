"""
Barajado determinista por intento: orden de preguntas (dentro de cada tema) y de opciones.
Con la misma semilla se obtiene siempre la misma presentación, así el servidor puede
convertir las letras que ve el estudiante a las letras originales del examen.
"""
import random
from typing import Any

LETRAS = ("a", "b", "c")


def barajar(preguntas: list[dict[str, Any]], semilla: int) -> list[dict[str, Any]]:
    """
    Devuelve las preguntas barajadas. Cada una trae `opciones` re-etiquetadas a/b/c y
    `_mapa` (letra mostrada -> letra original). Los temas conservan su orden.
    """
    rng = random.Random(semilla)
    por_tema: dict[str, list[dict[str, Any]]] = {}
    for p in preguntas:
        por_tema.setdefault(p["tema"], []).append(p)

    resultado = []
    for grupo in por_tema.values():
        grupo = grupo[:]
        rng.shuffle(grupo)
        for p in grupo:
            originales = [l for l in LETRAS if l in p["opciones"]]
            rng.shuffle(originales)
            resultado.append({
                **p,
                "opciones": {mostrada: p["opciones"][orig] for mostrada, orig in zip(LETRAS, originales)},
                "_mapa": dict(zip(LETRAS, originales)),
            })
    return resultado


def letra_correcta_mostrada(pregunta_barajada: dict[str, Any]) -> str:
    """Letra (a/b/c) que ocupa la respuesta correcta en la presentación barajada."""
    for mostrada, orig in pregunta_barajada["_mapa"].items():
        if orig == pregunta_barajada["respuesta_correcta"].lower():
            return mostrada
    raise ValueError("respuesta_correcta inválida")
