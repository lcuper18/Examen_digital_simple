from backend import database
from tests.conftest import login
from tests.test_actividades import _crear, _preparar
from tests.test_docente import _docente, _materia


def _publicar(client, hd, mid, publicado=True):
    return client.put(f"/api/docente/materias/{mid}/publicacion", headers=hd, json={"publicado": publicado})


def _cargar_datos(client, hd, mid):
    client.put("/api/docente/notas", headers=hd, json={"materia_id": mid, "notas": [
        {"estudiante_id": 1, "trabajo_cotidiano": 100, "tareas": 80, "prueba01": 90, "prueba02": 70, "proyecto": 60, "asistencia": 100},
        {"estudiante_id": 2, "trabajo_cotidiano": 10, "tareas": 0, "prueba01": 0, "prueba02": 0, "proyecto": 0, "asistencia": 0}]})
    aid = _crear(client, hd, mid, criterios=[], puntos_max=10).json()["id"]
    client.put(f"/api/docente/actividades/{aid}/calificaciones", headers=hd, json={"calificaciones": [
        {"estudiante_id": 1, "estado": "entregado", "puntos": 9, "observacion": "Muy bien, Ana", "nota_interna": "SECRETO-ANA"},
        {"estudiante_id": 2, "estado": "entregado", "puntos": 3, "observacion": "Luis debe mejorar", "nota_interna": "SECRETO-LUIS"}]})
    client.put("/api/docente/asistencia/sesion", headers=hd, json={
        "materia_id": mid, "fecha": "2026-03-02", "lecciones": 2,
        "registros": [{"estudiante_id": 1, "estado": "P"}, {"estudiante_id": 2, "estado": "A", "observacion": "falta de Luis"}]})


def test_portal_requiere_sesion_de_estudiante(client):
    assert client.get("/api/mis-notas").status_code == 401
    assert client.get("/api/mis-notas", headers=_docente(client)).status_code == 401   # el token del docente no sirve
    assert client.put("/api/docente/materias/1/publicacion", json={"publicado": True}).status_code == 401
    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET debe_cambiar_password = 1 WHERE id = 1")
        conn.commit()
    assert client.get("/api/mis-notas", headers=login(client)).status_code == 403


def test_solo_se_ve_lo_publicado_y_lo_propio(client):
    hd, mid = _preparar(client)          # ana y luis, ambos de 11-1
    _cargar_datos(client, hd, mid)
    ana = login(client)
    luis = login(client, "luis.mora", "LUI5678")

    # sin publicar: nada
    assert client.get("/api/mis-notas", headers=ana).json()["materias"] == []

    assert _publicar(client, hd, mid).status_code == 200
    r = client.get("/api/mis-notas", headers=ana)
    texto = r.text
    assert "SECRETO" not in texto                                   # nunca la nota interna
    assert "Luis" not in texto and "LUIS" not in texto and "falta de Luis" not in texto and "7-0344-0226" not in texto
    d = r.json()
    assert d["nombre"] == "PEREZ SOTO ANA" and d["seccion"] == "11-1" and len(d["materias"]) == 1
    m = d["materias"][0]
    assert m["componentes"][0]["puntos"] == 25 and m["actividades"][0]["observacion"] == "Muy bien, Ana"
    assert m["asistencia"]["ausencias"] == 0 and m["asistencia"]["puntos"] == 5

    # cada quien ve lo suyo
    dl = client.get("/api/mis-notas", headers=luis).json()["materias"][0]
    assert dl["actividades"][0]["observacion"] == "Luis debe mejorar" and dl["asistencia"]["ausencias"] == 2
    assert "Muy bien, Ana" not in client.get("/api/mis-notas", headers=luis).text

    # ocultar la materia la retira otra vez
    assert _publicar(client, hd, mid, False).status_code == 200
    assert client.get("/api/mis-notas", headers=ana).json()["materias"] == []
    assert client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()["publicado"] is False


def test_lo_publicado_en_una_seccion_no_lo_ve_otra(client):
    hd = _docente(client)
    mid = _materia(client, hd)            # materia de 11-1 (ana); luis es de 11-2
    _publicar(client, hd, mid)
    assert len(client.get("/api/mis-notas", headers=login(client)).json()["materias"]) == 1
    assert client.get("/api/mis-notas", headers=login(client, "luis.mora", "LUI5678")).json()["materias"] == []
    assert client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()["publicado"] is True
