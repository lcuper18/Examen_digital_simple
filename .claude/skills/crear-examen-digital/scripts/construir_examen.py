"""Convierte un banco de preguntas (JSON) en el examen de la plataforma y lo registra.

Uso:  python3 construir_examen.py banco.json
      (ejecutar desde la raíz del proyecto)

El banco tiene la forma:
{
  "meta": {"codigo": "XXX02", "nombre": "...", "archivo": "Nombre.json", "duracion_minutos": 80,
           "titulo": "...", "institucion": "CTP Las Palmitas", "especialidad": "...",
           "nivel": "Undécimo", "curso_lectivo": 2026, "profesor": "...", "instrucciones": "...",
           "semilla": 11},
  "preguntas": [{"tema": "...", "pregunta": "...", "correcta": "...",
                 "incorrectas": ["...", "...", "..."], "origen": "Cuestionario 02 · P22"}]
}
`origen` es opcional (solo para el docente; la plataforma nunca lo envía al estudiante).
"""
import json
import random
import sys
from collections import Counter
from pathlib import Path

MAX_CORRECTA_MAS_LARGA = 0.35


def main(ruta_banco: str) -> int:
    banco = json.loads(Path(ruta_banco).read_text(encoding="utf-8"))
    meta, items = banco["meta"], banco["preguntas"]
    n = len(items)
    errores = []

    for i, q in enumerate(items, 1):
        if len(q["incorrectas"]) != 3:
            errores.append(f"#{i}: debe tener exactamente 3 incorrectas")
        todas = [q["correcta"], *q["incorrectas"]]
        if len({t.strip().lower() for t in todas}) != 4:
            errores.append(f"#{i}: opciones repetidas")
    if len({q["pregunta"] for q in items}) != n:
        errores.append("hay preguntas repetidas")

    # Letras de la respuesta correcta repartidas por igual (n/4 por letra, el resto al azar)
    rng = random.Random(meta.get("semilla", 11))
    objetivos = list("abcd") * (n // 4) + rng.sample("abcd", n % 4)
    rng.shuffle(objetivos)

    preguntas = []
    for i, (q, letra) in enumerate(zip(items, objetivos), 1):
        malas = list(q["incorrectas"])
        rng.shuffle(malas)
        opciones = {letra: q["correcta"]}
        for l, m in zip([x for x in "abcd" if x != letra], malas):
            opciones[l] = m
        p = {"numero": i, "tema": q["tema"], "pregunta": q["pregunta"],
             "opciones": {l: opciones[l] for l in "abcd"}, "respuesta_correcta": letra}
        if q.get("origen"):
            p["origen"] = q["origen"]
        preguntas.append(p)

    mas_larga = sum(
        1 for p in preguntas
        if len(p["opciones"][p["respuesta_correcta"]]) > max(
            len(v) for k, v in p["opciones"].items() if k != p["respuesta_correcta"]))
    print(f"Preguntas: {n} | por letra: {sorted(Counter(p['respuesta_correcta'] for p in preguntas).items())}")
    print(f"Correcta = opción más larga: {mas_larga} de {n} (tope {int(MAX_CORRECTA_MAS_LARGA * n)})")
    print("Por tema:")
    for t, c in Counter(p["tema"] for p in preguntas).items():
        print(f"  {c:>3}  {t}")
    print(f"Con origen (cuestionario): {sum('origen' in p for p in preguntas)}")
    if mas_larga > MAX_CORRECTA_MAS_LARGA * n:
        errores.append("demasiadas respuestas correctas son la opción más larga: acorta correctas o alarga incorrectas")
    if errores:
        print("\nERRORES:\n - " + "\n - ".join(errores))
        return 1

    examen = {"examen": {
        "titulo": meta["titulo"], "institucion": meta["institucion"], "especialidad": meta["especialidad"],
        "nivel": meta["nivel"], "curso_lectivo": meta["curso_lectivo"], "profesor": meta["profesor"],
        "instrucciones": meta["instrucciones"], "total_preguntas": n, "preguntas": preguntas}}
    destino = Path("data/examenes") / meta["archivo"]
    destino.write_text(json.dumps(examen, ensure_ascii=False, indent=2), encoding="utf-8")

    codigos_ruta = Path("data/codigos.json")
    codigos = json.loads(codigos_ruta.read_text(encoding="utf-8"))
    codigos[meta["codigo"]] = {"nombre": meta["nombre"], "archivo": meta["archivo"],
                               "duracion_minutos": meta["duracion_minutos"]}
    codigos_ruta.write_text(json.dumps(codigos, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(f"\nEscrito {destino} y registrado el código {meta['codigo']} en data/codigos.json")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1]))
