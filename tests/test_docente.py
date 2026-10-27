from backend import database
from tests.conftest import login

CODIGO = "SGC01"


def _docente(client):
    token = client.post("/api/verificar-docente", json={"password": "docente2026"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _materia(client, hd, seccion="11-1"):
    materias = client.get("/api/docente/materias", headers=hd).json()["materias"]
    return next(m for m in materias if m["seccion"] == seccion and m["periodo"] == 1)["id"]


def test_materias_sembradas_y_requieren_docente(client):
    assert client.get("/api/docente/materias").status_code == 401
    data = client.get("/api/docente/materias", headers=_docente(client)).json()
    assert len(data["materias"]) == 12
    assert sum(data["ponderaciones"].values()) == 100


def test_nota_final_ponderada_y_guardado(client):
    hd = _docente(client)
    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET seccion = '11-1'")
        conn.commit()
    mid = _materia(client, hd)

    completa = dict(trabajo_cotidiano=100, tareas=100, prueba01=100, prueba02=100, proyecto=100, asistencia=100)
    r = client.put("/api/docente/notas", headers=hd, json={
        "materia_id": mid,
        "notas": [{"estudiante_id": 1, **completa}, {"estudiante_id": 2, "prueba01": 50}],
    })
    assert r.status_code == 200

    data = client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()
    por_id = {n["estudiante_id"]: n for n in data["notas"]}
    assert por_id[1]["nota_final"] == 100 and por_id[1]["completa"]
    assert por_id[2]["nota_final"] == 10.0 and not por_id[2]["completa"]  # 50 * 20 %
    assert data["resumen"]["completas"] == 1 and data["resumen"]["promedio"] == 100


def test_rechaza_notas_fuera_de_rango_y_estudiante_de_otra_seccion(client):
    hd = _docente(client)
    mid = _materia(client, hd)
    assert client.put("/api/docente/notas", headers=hd, json={
        "materia_id": mid, "notas": [{"estudiante_id": 1, "tareas": 150}]}).status_code == 422
    # el estudiante 2 es de la sección 11-2, no de 11-1
    assert client.put("/api/docente/notas", headers=hd, json={
        "materia_id": mid, "notas": [{"estudiante_id": 2, "tareas": 90}]}).status_code == 400


def test_importar_prueba_desde_intentos(client):
    hd = _docente(client)
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}})  # 0 aciertos
    mid = _materia(client, hd)
    r = client.post("/api/docente/notas/importar-prueba", headers=hd, json={
        "materia_id": mid, "componente": "prueba01", "codigo_examen": CODIGO})
    assert r.json()["importadas"] == 1
    notas = client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()["notas"]
    assert next(n for n in notas if n["estudiante_id"] == 1)["prueba01"] == 0
    assert client.post("/api/docente/notas/importar-prueba", headers=hd, json={
        "materia_id": mid, "componente": "tareas", "codigo_examen": CODIGO}).status_code == 400


def test_exportar_csv_de_notas_e_intentos(client):
    hd = _docente(client)
    mid = _materia(client, hd)
    r = client.get(f"/api/docente/notas/exportar?materia_id={mid}", headers=hd)
    assert r.headers["content-type"].startswith("text/csv")
    assert "nota_final" in r.text
    assert "Apellido 1" in client.get("/api/docente/intentos-exportar", headers=hd).text


def test_reiniciar_intento_permite_repetir(client):
    hd = _docente(client)
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}})
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 409
    intento_id = client.get("/api/docente/intentos", headers=hd).json()["intentos"][0]["id"]
    assert client.delete(f"/api/docente/intentos/{intento_id}", headers=hd).status_code == 200
    assert client.delete(f"/api/docente/intentos/{intento_id}", headers=hd).status_code == 404
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 200


def test_detalle_incluye_preguntas_barajadas(client):
    hd = _docente(client)
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}})
    intento_id = client.get("/api/docente/intentos", headers=hd).json()["intentos"][0]["id"]
    d = client.get(f"/api/docente/intentos/{intento_id}", headers=hd).json()["intento"]
    assert len(d["preguntas"]) == d["total"]
    assert all("respuesta_correcta" not in p for p in d["preguntas"])
    assert set(d["respuestas_correctas"]) == {str(p["numero"]) for p in d["preguntas"]}
