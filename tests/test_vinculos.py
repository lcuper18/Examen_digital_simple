from backend import database
from backend.routes import reportes
from tests.conftest import login
from tests.test_docente import _docente

CODIGO = "SGC01"


def _materia(client, hd, seccion, periodo, nombre=None):
    materias = client.get("/api/docente/materias", headers=hd).json()["materias"]
    return next(m for m in materias if m["seccion"] == seccion and m["periodo"] == periodo
                and (nombre is None or m["nombre"] == nombre))["id"]


def _enviar(client, h):
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}})


def test_un_examen_se_vincula_a_varias_materias_y_cada_una_importa_su_seccion(client):
    hd = _docente(client)
    _enviar(client, login(client))                        # Ana, 11-1
    _enviar(client, login(client, "luis.mora", "LUI5678"))  # Luis, 11-2
    m1, m2 = _materia(client, hd, "11-1", 2), _materia(client, hd, "11-2", 2)
    r = client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"vinculos": [
        {"materia_id": m1, "componente": "prueba02"}, {"materia_id": m2, "componente": "prueba02"}]})
    assert r.status_code == 200
    v = next(e for e in client.get("/api/docente/examenes", headers=hd).json()["examenes"] if e["codigo"] == CODIGO)["vinculos"]
    assert {(x["seccion"], x["periodo"]) for x in v} == {("11-1", 2), ("11-2", 2)}

    # cada materia importa solo a los estudiantes de su sección
    for mid in (m1, m2):
        r = client.post("/api/docente/notas/importar-prueba", headers=hd, json={"materia_id": mid})
        assert r.json()["importadas"] == 1 and r.json()["examenes"] == [CODIGO]
    # ...y el período del examen sale del vínculo, no del sufijo del código (SGC01 sugeriría el 1.º)
    with database.get_db_context() as conn:
        assert reportes._periodo_del_examen(conn, CODIGO) == 2


def test_los_vinculos_anteriores_se_migran_a_la_tabla_nueva(client):
    hd = _docente(client)
    mid = _materia(client, hd, "11-1", 1)
    with database.get_db_context() as conn:
        conn.execute("INSERT INTO examenes_config (codigo, habilitado, materia_id, componente) VALUES ('ADM02', 1, ?, 'prueba01')", (mid,))
        conn.execute("DELETE FROM examen_vinculos")
        conn.commit()
    database.init_db()
    with database.get_db_context() as conn:
        filas = conn.execute("SELECT codigo, materia_id, componente FROM examen_vinculos").fetchall()
    assert [tuple(f) for f in filas] == [("ADM02", mid, "prueba01")]
    database.init_db()  # volver a arrancar no duplica nada
    with database.get_db_context() as conn:
        assert conn.execute("SELECT COUNT(*) FROM examen_vinculos").fetchone()[0] == 1
