from backend import database
from backend.routes.asistencia import puntos_asistencia
from tests.test_docente import _docente, _materia


def test_tabla_del_articulo_37():
    assert [puntos_asistencia(p) for p in (0, 9.9, 10, 19.9, 20, 29.9, 30, 39.9, 40, 49.9, 50, 100)] == \
        [5, 5, 4, 4, 3, 3, 2, 2, 1, 1, 0, 0]


def _lista(client, hd, mid, fecha, estado, lecciones=2, obs=""):
    return client.put("/api/docente/asistencia/sesion", headers=hd, json={
        "materia_id": mid, "fecha": fecha, "lecciones": lecciones, "tema": "Tema",
        "registros": [{"estudiante_id": 1, "estado": estado, "observacion": obs}],
    })


def test_pasar_lista_calcula_puntos_y_llena_la_nota(client):
    hd = _docente(client)
    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET seccion = '11-1'")
        conn.commit()
    mid = _materia(client, hd)

    # una fecha nueva viene con todos presentes
    nueva = client.get(f"/api/docente/asistencia/sesion?materia_id={mid}&fecha=2026-03-02", headers=hd).json()
    assert not nueva["existe"] and {r["estado"] for r in nueva["registros"]} == {"P"}

    # 5 sesiones de 2 lecciones = 10 lecciones; ausente en una (2 lecciones = 20 %) -> 3 puntos
    for dia, estado in [(2, "A"), (3, "P"), (4, "P"), (5, "P"), (6, "P")]:
        assert _lista(client, hd, mid, f"2026-03-0{dia}", estado).status_code == 200
    r = client.get(f"/api/docente/asistencia/resumen?materia_id={mid}", headers=hd).json()
    e = next(x for x in r["estudiantes"] if x["estudiante_id"] == 1)
    assert r["lecciones_totales"] == 10 and e["injustificadas"] == 2 and e["porcentaje_ausencias"] == 20.0 and e["puntos"] == 3
    notas = client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()["notas"]
    assert next(n for n in notas if n["estudiante_id"] == 1)["asistencia"] == 60  # 3 de 5 puntos

    # justificada no cuenta; tardías: menos de 10 min = 0.5, más de 10 min = 1
    _lista(client, hd, mid, "2026-03-02", "AJ")
    _lista(client, hd, mid, "2026-03-03", "T")
    _lista(client, hd, mid, "2026-03-04", "TM")
    e = next(x for x in client.get(f"/api/docente/asistencia/resumen?materia_id={mid}", headers=hd).json()["estudiantes"]
             if x["estudiante_id"] == 1)
    assert e["injustificadas"] == 1.5 and e["porcentaje_ausencias"] == 15.0 and e["puntos"] == 4
    assert e["justificadas"] == 1 and e["tardias"] == 2

    # eliminar una sesión recalcula (quedan 8 lecciones)
    sesion = client.get(f"/api/docente/asistencia/resumen?materia_id={mid}", headers=hd).json()["sesiones"][0]
    assert client.delete(f"/api/docente/asistencia/sesion/{sesion['id']}", headers=hd).status_code == 200
    r = client.get(f"/api/docente/asistencia/resumen?materia_id={mid}", headers=hd).json()
    assert r["lecciones_totales"] == 8 and len(r["sesiones"]) == 4


def test_validaciones_y_permisos(client):
    hd = _docente(client)
    mid = _materia(client, hd)
    assert client.get(f"/api/docente/asistencia/resumen?materia_id={mid}").status_code == 401
    assert client.get(f"/api/docente/asistencia/sesion?materia_id={mid}&fecha=mañana", headers=hd).status_code == 400
    assert _lista(client, hd, mid, "2026-03-02", "X").status_code == 400            # estado inventado
    assert _lista(client, hd, mid, "2026-13-45", "P").status_code == 400            # fecha inválida
    assert _lista(client, hd, mid, "2026-03-02", "P", lecciones=0).status_code == 422
    # el estudiante 2 es de 11-2: no pertenece a la sección de la materia
    r = client.put("/api/docente/asistencia/sesion", headers=hd, json={
        "materia_id": mid, "fecha": "2026-03-02", "lecciones": 2,
        "registros": [{"estudiante_id": 2, "estado": "P"}]})
    assert r.status_code == 400
    assert client.get(f"/api/docente/asistencia/excel?materia_id={mid}", headers=hd).status_code == 200
