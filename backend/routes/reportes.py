"""
Reportes routes - Boletas, estadísticas por examen, preguntas críticas y notas por sección (solo docente).
"""
import io
import json
import statistics
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, Response
from openpyxl import Workbook
from openpyxl.styles import Font
from openpyxl.utils import get_column_letter

from backend import barajado, database, security
from backend.routes.examenes import _get_examen, load_codigos
from backend.routes.notas import COMPONENTES, ETIQUETAS as ETIQUETAS_NOTA, nota_minima, _filas, pesos_de

router = APIRouter(
    prefix="/api/docente/reportes", tags=["reportes"], dependencies=[Depends(security.require_docente)]
)

def _institucion() -> str:
    with database.get_db_context() as conn:
        return database.leer_ajustes(conn)["institucion"]


def _nota(puntuacion: int, total: int) -> float:
    return round(puntuacion / total * 100, 1) if total else 0.0


def _nombre(fila) -> str:
    return f"{fila['apellido1']} {fila['apellido2'] or ''}, {fila['nombre']}".replace("  ", " ").strip()


def _intentos_enviados(conn, codigo: str, seccion: str | None):
    """Intentos enviados y no anulados de un examen, opcionalmente de una sección."""
    sql = (
        "SELECT i.*, e.nombre, e.apellido1, e.apellido2, e.seccion FROM intentos i "
        "JOIN estudiantes e ON e.id = i.estudiante_id "
        "WHERE i.codigo_examen = ? AND i.fecha_fin IS NOT NULL AND i.anulado = 0"
    )
    params: list[Any] = [codigo]
    if seccion:
        sql += " AND e.seccion = ?"
        params.append(seccion)
    return conn.execute(sql + " ORDER BY e.apellido1, e.apellido2, e.nombre", params).fetchall()


def desglose_por_tema(preguntas: list[dict[str, Any]], semilla: int, respuestas: dict[str, str]) -> list[dict[str, Any]]:
    """Aciertos y total por tema de un intento (respuestas en letras mostradas)."""
    temas: dict[str, dict[str, int]] = {}
    for p in barajado.barajar(preguntas, semilla):
        t = temas.setdefault(p["tema"], {"aciertos": 0, "total": 0})
        t["total"] += 1
        if respuestas.get(str(p["numero"])) == barajado.letra_correcta_mostrada(p):
            t["aciertos"] += 1
    return [
        {"tema": tema, **v, "porcentaje": round(v["aciertos"] / v["total"] * 100, 1) if v["total"] else 0}
        for tema, v in temas.items()
    ]


# ---------- Boleta del estudiante ----------

def _periodo_del_examen(conn, codigo: str) -> int | None:
    """Período al que pertenece un examen: el de la materia a la que está vinculado; si no hay vínculo,
    el que indica el sufijo del código (EMP02 → 2). None si no se puede saber."""
    fila = conn.execute(
        "SELECT m.periodo FROM examenes_config c JOIN materias m ON m.id = c.materia_id WHERE c.codigo = ?", (codigo,)
    ).fetchone()
    if fila:
        return fila["periodo"]
    sufijo = codigo[-2:]
    return int(sufijo) if sufijo.isdigit() and int(sufijo) in (1, 2) else None


@router.get("/boleta/{estudiante_id}")
def boleta_estudiante(estudiante_id: int, periodo: int | None = None) -> dict[str, Any]:
    """
    Boleta consolidada: exámenes presentados (con desglose por tema) y notas por materia.
    Con `periodo` (1 o 2) solo trae ese período; sin él, es el resultado general con la nota anual por materia.
    """
    if periodo is not None and periodo not in (1, 2):
        raise HTTPException(status_code=400, detail="El período debe ser 1 o 2")
    minima = nota_minima()
    with database.get_db_context() as conn:
        est = conn.execute("SELECT * FROM estudiantes WHERE id = ?", (estudiante_id,)).fetchone()
        if est is None:
            raise HTTPException(status_code=404, detail="Estudiante no encontrado")
        intentos = conn.execute(
            "SELECT * FROM intentos WHERE estudiante_id = ? AND fecha_fin IS NOT NULL AND anulado = 0 "
            "ORDER BY fecha_fin", (estudiante_id,)
        ).fetchall()
        materias = conn.execute(
            "SELECT * FROM materias WHERE seccion = ? AND (? IS NULL OR periodo = ?) ORDER BY periodo, nombre",
            (est["seccion"], periodo, periodo),
        ).fetchall()
        if periodo is not None:
            intentos = [i for i in intentos if _periodo_del_examen(conn, i["codigo_examen"]) in (periodo, None)]
        notas = []
        for m in materias:
            fila = next((f for f in _filas(conn, m) if f["estudiante_id"] == estudiante_id), None)
            if fila and any(fila[c] is not None for c in COMPONENTES):
                pesos = pesos_de(conn, m["id"])
                notas.append({
                    "materia": m["nombre"], "periodo": m["periodo"],
                    # Cada componente en puntos (lo que vale en la nota final), no en escala 0-100
                    **{c: None if fila[c] is None else round(fila[c] * pesos[c] / 100, 2) for c in COMPONENTES},
                    "pesos": {c: pesos[c] for c in COMPONENTES},
                    "completa": fila["completa"], "nota_final": fila["nota_final"],
                })

    # Nota anual por materia (promedio simple de los períodos con nota); solo en el resultado general
    anual = []
    if periodo is None:
        por_materia: dict[str, dict[str, Any]] = {}
        for n in notas:
            f = por_materia.setdefault(n["materia"], {"materia": n["materia"], "p1": None, "p2": None, "completa": True})
            f[f"p{n['periodo']}"] = n["nota_final"]
            f["completa"] = f["completa"] and n["completa"]
        for f in por_materia.values():
            finales = [v for v in (f["p1"], f["p2"]) if v is not None]
            f["anual"] = round(sum(finales) / len(finales), 1)
            f["completa"] = f["completa"] and len(finales) == 2
            anual.append(f)

    codigos = load_codigos()
    examenes, institucion = [], _institucion()
    for i in intentos:
        if i["codigo_examen"] not in codigos:
            continue
        info, examen = _get_examen(i["codigo_examen"])
        examenes.append({
            "codigo": i["codigo_examen"], "nombre": info["nombre"], "fecha": i["fecha_fin"],
            "puntuacion": i["puntuacion"], "total": i["total"], "nota": _nota(i["puntuacion"], i["total"]),
            "aprobado": _nota(i["puntuacion"], i["total"]) >= minima,
            "temas": desglose_por_tema(examen["preguntas"], i["semilla"], json.loads(i["respuestas_json"])),
        })
    return {
        "ok": True, "institucion": institucion, "nota_minima": minima,
        "estudiante": {
            "id": est["id"], "nombre": f"{est['nombre']} {est['apellido1']} {est['apellido2'] or ''}".strip(),
            "cedula": est["cedula"], "seccion": est["seccion"], "username": est["username"],
        },
        "periodo": periodo, "examenes": examenes, "notas": notas, "anual": anual,
    }


# ---------- Reporte por examen ----------

def _datos_examen(codigo: str, seccion: str | None) -> dict[str, Any]:
    minima = nota_minima()
    codigo = codigo.upper()
    info, examen = _get_examen(codigo)
    with database.get_db_context() as conn:
        enviados = _intentos_enviados(conn, codigo, seccion)
        sql = ("SELECT COUNT(*) FROM intentos i JOIN estudiantes e ON e.id = i.estudiante_id "
               "WHERE i.codigo_examen = ? AND i.fecha_fin IS NULL AND i.anulado = 0")
        params: list[Any] = [codigo]
        if seccion:
            sql += " AND e.seccion = ?"
            params.append(seccion)
        sin_enviar = conn.execute(sql, params).fetchone()[0]

    ranking = sorted(
        ({
            "estudiante_id": i["estudiante_id"], "nombre": _nombre(i), "seccion": i["seccion"],
            "puntuacion": i["puntuacion"], "total": i["total"], "nota": _nota(i["puntuacion"], i["total"]),
        } for i in enviados),
        key=lambda r: (-r["nota"], r["nombre"]),
    )
    notas = [r["nota"] for r in ranking]
    resumen = {
        "enviados": len(notas), "sin_enviar": sin_enviar,
        "promedio": round(statistics.mean(notas), 1) if notas else None,
        "mediana": round(statistics.median(notas), 1) if notas else None,
        "maxima": max(notas) if notas else None, "minima": min(notas) if notas else None,
        "aprobados": sum(n >= minima for n in notas),
        "reprobados": sum(n < minima for n in notas),
    }
    histograma = [{"desde": d, "hasta": d + 9 if d < 90 else 100, "cantidad": 0} for d in range(0, 100, 10)]
    for n in notas:
        histograma[min(int(n // 10), 9)]["cantidad"] += 1

    acumulado: dict[str, dict[str, int]] = {}
    for i in enviados:
        for t in desglose_por_tema(examen["preguntas"], i["semilla"], json.loads(i["respuestas_json"])):
            a = acumulado.setdefault(t["tema"], {"aciertos": 0, "total": 0})
            a["aciertos"] += t["aciertos"]
            a["total"] += t["total"]
    temas = [
        {"tema": tema, **v, "porcentaje": round(v["aciertos"] / v["total"] * 100, 1) if v["total"] else 0}
        for tema, v in acumulado.items()
    ]
    return {
        "ok": True, "codigo": codigo, "nombre": info["nombre"], "institucion": _institucion(),
        "seccion": seccion or "Todas", "nota_minima": minima,
        "resumen": resumen, "histograma": histograma, "temas": temas, "ranking": ranking,
    }


@router.get("/examen/{codigo}")
def reporte_examen(codigo: str, seccion: str | None = None) -> dict[str, Any]:
    return _datos_examen(codigo, seccion)


# ---------- Preguntas críticas ----------

def _datos_criticas(codigo: str, seccion: str | None) -> dict[str, Any]:
    codigo = codigo.upper()
    info, examen = _get_examen(codigo)
    originales = {str(p["numero"]): p for p in examen["preguntas"]}
    estadistica = {n: {"respondidas": 0, "errores": 0, "elegidas": {}} for n in originales}

    with database.get_db_context() as conn:
        enviados = _intentos_enviados(conn, codigo, seccion)
    for i in enviados:
        barajadas = {str(p["numero"]): p for p in barajado.barajar(examen["preguntas"], i["semilla"])}
        for n, letra in json.loads(i["respuestas_json"]).items():
            if n not in barajadas or n not in estadistica:
                continue
            e = estadistica[n]
            e["respondidas"] += 1
            if letra != barajado.letra_correcta_mostrada(barajadas[n]):
                e["errores"] += 1
                original = barajadas[n]["_mapa"][letra]  # letra en el examen original
                e["elegidas"][original] = e["elegidas"].get(original, 0) + 1

    filas = []
    for n, p in originales.items():
        e = estadistica[n]
        peor = max(e["elegidas"].items(), key=lambda kv: kv[1]) if e["elegidas"] else None
        filas.append({
            "numero": p["numero"], "tema": p["tema"], "pregunta": p["pregunta"],
            "correcta": p["opciones"][p["respuesta_correcta"].lower()],
            "respondidas": e["respondidas"], "errores": e["errores"],
            "sin_responder": len(enviados) - e["respondidas"],
            "porcentaje_error": round(e["errores"] / e["respondidas"] * 100, 1) if e["respondidas"] else 0,
            "distractor": {"texto": p["opciones"][peor[0]], "veces": peor[1]} if peor else None,
        })
    filas.sort(key=lambda f: (-f["porcentaje_error"], -f["errores"], f["numero"]))
    return {
        "ok": True, "codigo": codigo, "nombre": info["nombre"], "institucion": _institucion(),
        "seccion": seccion or "Todas", "intentos": len(enviados), "preguntas": filas,
    }


@router.get("/preguntas-criticas/{codigo}")
def preguntas_criticas(codigo: str, seccion: str | None = None) -> dict[str, Any]:
    return _datos_criticas(codigo, seccion)


# ---------- Notas por sección y periodo ----------

def _datos_seccion(seccion: str, periodo: int) -> dict[str, Any]:
    minima = nota_minima()
    with database.get_db_context() as conn:
        materias = conn.execute(
            "SELECT * FROM materias WHERE seccion = ? AND periodo = ? ORDER BY nombre", (seccion, periodo)
        ).fetchall()
        if not materias:
            raise HTTPException(status_code=404, detail="No hay materias para esa sección y periodo")
        estudiantes: dict[int, dict[str, Any]] = {}
        promedios = []
        for m in materias:
            finales = []
            for f in _filas(conn, m):
                e = estudiantes.setdefault(f["estudiante_id"], {
                    "estudiante_id": f["estudiante_id"], "nombre": _nombre(f), "notas": {}})
                e["notas"][str(m["id"])] = {"nota_final": f["nota_final"], "completa": f["completa"]}
                if f["completa"]:
                    finales.append(f["nota_final"])
            promedios.append({
                "materia_id": m["id"], "nombre": m["nombre"], "completas": len(finales),
                "promedio": round(sum(finales) / len(finales), 1) if finales else None,
                "aprobados": sum(n >= minima for n in finales),
            })
    for e in estudiantes.values():
        completas = [v["nota_final"] for v in e["notas"].values() if v["completa"]]
        e["promedio_general"] = round(sum(completas) / len(completas), 1) if completas else None
        e["reprobadas"] = sum(n < minima for n in completas)
        e["estado"] = (
            "Incompleto" if len(completas) < len(materias)
            else f"Reprobó {e['reprobadas']}" if e["reprobadas"] else "Aprobado"
        )
    return {
        "ok": True, "seccion": seccion, "periodo": periodo, "nota_minima": minima,
        "materias": [{"id": m["id"], "nombre": m["nombre"]} for m in materias],
        "promedios": promedios, "estudiantes": list(estudiantes.values()),
    }


@router.get("/seccion")
def reporte_seccion(seccion: str, periodo: int) -> dict[str, Any]:
    return _datos_seccion(seccion, periodo)


# ---------- Excel ----------

def _xlsx(nombre: str, hojas: dict[str, list[list[Any]]]) -> Response:
    libro = Workbook()
    libro.remove(libro.active)
    for titulo, filas in hojas.items():
        hoja = libro.create_sheet(titulo[:31])
        for fila in filas:
            hoja.append(fila)
        for celda in hoja[1]:
            celda.font = Font(bold=True)
        for col in range(1, hoja.max_column + 1):
            ancho = max((len(str(c.value)) for c in hoja[get_column_letter(col)] if c.value is not None), default=8)
            hoja.column_dimensions[get_column_letter(col)].width = min(ancho + 2, 60)
    salida = io.BytesIO()
    libro.save(salida)
    return Response(
        content=salida.getvalue(),
        media_type="application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
        headers={"Content-Disposition": f'attachment; filename="{nombre}"'},
    )


@router.get("/examen/{codigo}/excel")
def excel_examen(codigo: str, seccion: str | None = None) -> Response:
    d = _datos_examen(codigo, seccion)
    c = _datos_criticas(codigo, seccion)
    r = d["resumen"]
    return _xlsx(f"reporte_{d['codigo']}.xlsx", {
        "Resumen": [
            ["Indicador", "Valor"], ["Examen", f"{d['codigo']} · {d['nombre']}"], ["Sección", d["seccion"]],
            ["Enviados", r["enviados"]], ["Sin enviar", r["sin_enviar"]], ["Promedio", r["promedio"]],
            ["Mediana", r["mediana"]], ["Nota máxima", r["maxima"]], ["Nota mínima", r["minima"]],
            ["Aprobados", r["aprobados"]], ["Reprobados", r["reprobados"]], ["Nota mínima de aprobación", nota_minima()],
        ],
        "Ranking": [["Puesto", "Estudiante", "Sección", "Puntuación", "Total", "Nota (0-100)"]] + [
            [i + 1, x["nombre"], x["seccion"], x["puntuacion"], x["total"], x["nota"]] for i, x in enumerate(d["ranking"])
        ],
        "Por tema": [["Tema", "Aciertos", "Total", "% aciertos"]] + [
            [t["tema"], t["aciertos"], t["total"], t["porcentaje"]] for t in d["temas"]
        ],
        "Preguntas críticas": [["N.º", "Tema", "Pregunta", "Respondidas", "Errores", "% error",
                                "Respuesta correcta", "Distractor más elegido", "Veces"]] + [
            [q["numero"], q["tema"], q["pregunta"], q["respondidas"], q["errores"], q["porcentaje_error"],
             q["correcta"], q["distractor"]["texto"] if q["distractor"] else "", q["distractor"]["veces"] if q["distractor"] else ""]
            for q in c["preguntas"]
        ],
    })


@router.get("/seccion/excel")
def excel_seccion(seccion: str, periodo: int) -> Response:
    d = _datos_seccion(seccion, periodo)
    cabecera = ["Estudiante"] + [m["nombre"] for m in d["materias"]] + ["Promedio general"]
    filas = [cabecera] + [
        [e["nombre"]] + [
            (e["notas"].get(str(m["id"]), {}).get("nota_final") if e["notas"].get(str(m["id"]), {}).get("completa") else "")
            for m in d["materias"]
        ] + [e["promedio_general"] if e["promedio_general"] is not None else ""]
        for e in d["estudiantes"]
    ]
    filas.append(["Promedio de la materia"] + [p["promedio"] if p["promedio"] is not None else "" for p in d["promedios"]] + [""])
    return _xlsx(f"notas_{seccion}_P{periodo}.xlsx", {f"{seccion} periodo {periodo}": filas})


@router.get("/boleta/{estudiante_id}/excel")
def excel_boleta(estudiante_id: int, periodo: int | None = None) -> Response:
    d = boleta_estudiante(estudiante_id, periodo)
    columnas = COMPONENTES
    hojas = {
        "Exámenes": [["Código", "Examen", "Fecha", "Puntuación", "Total", "Nota (0-100)", "Aprobado"]] + [
            [x["codigo"], x["nombre"], x["fecha"], x["puntuacion"], x["total"], x["nota"], "sí" if x["aprobado"] else "no"]
            for x in d["examenes"]
        ],
        "Notas por materia": [["Materia", "Periodo", *[f"{ETIQUETAS_NOTA[c]} (puntos)" for c in columnas], "Nota final (de 100)"]] + [
            [n["materia"], n["periodo"], *["" if n[c] is None else n[c] for c in columnas], n["nota_final"]]
            for n in d["notas"]
        ],
        "Valor de cada componente": [["Materia", "Periodo", *[f"{ETIQUETAS_NOTA[c]} (valor)" for c in columnas]]] + [
            [n["materia"], n["periodo"], *[n["pesos"][c] for c in columnas]] for n in d["notas"]
        ],
    }
    if d["periodo"] is None:
        hojas["Nota anual"] = [["Materia", "1.º período", "2.º período", "Nota anual (promedio)"]] + [
            [a["materia"], "" if a["p1"] is None else a["p1"], "" if a["p2"] is None else a["p2"], a["anual"]]
            for a in d["anual"]
        ]
    sufijo = "" if d["periodo"] is None else f"_P{d['periodo']}"
    return _xlsx(f"boleta_{d['estudiante']['username']}{sufijo}.xlsx", hojas)
