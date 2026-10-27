from backend import barajado, database
from backend.routes import examenes
from tests.conftest import login

CODIGO = "SGC01"


def _docente(client):
    token = client.post("/api/verificar-docente", json={"password": "docente2026"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def presentar(client, estudiante_id, usuario, clave, aciertos):
    """El estudiante envía todas las preguntas: las primeras `aciertos` bien y el resto mal."""
    h = login(client, usuario, clave)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    _, ex = examenes._get_examen(CODIGO)
    with database.get_db_context() as conn:
        semilla = conn.execute("SELECT semilla FROM intentos WHERE estudiante_id = ?", (estudiante_id,)).fetchone()[0]
    respuestas = {}
    for i, p in enumerate(barajado.barajar(ex["preguntas"], semilla)):
        correcta = barajado.letra_correcta_mostrada(p)
        respuestas[str(p["numero"])] = correcta if i < aciertos else next(l for l in "abc" if l != correcta)
    assert client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": respuestas}).status_code == 200
    return len(ex["preguntas"])


def _dos_intentos(client):
    total = presentar(client, 1, "ana.perez", "ANA1234", 70)       # nota 100, sección 11-1
    presentar(client, 2, "luis.mora", "LUI5678", 35)               # nota 50, sección 11-2
    return total


def test_reportes_requieren_docente(client):
    for ruta in (f"/api/docente/reportes/examen/{CODIGO}", f"/api/docente/reportes/preguntas-criticas/{CODIGO}",
                 "/api/docente/reportes/boleta/1", "/api/docente/reportes/seccion?seccion=11-1&periodo=1",
                 f"/api/docente/reportes/examen/{CODIGO}/excel"):
        assert client.get(ruta).status_code == 401
        assert client.get(ruta, headers=login(client)).status_code == 401


def test_reporte_de_examen(client):
    hd = _docente(client)
    assert _dos_intentos(client) == 70
    r = client.get(f"/api/docente/reportes/examen/{CODIGO}", headers=hd).json()
    assert r["resumen"]["enviados"] == 2
    assert r["resumen"]["promedio"] == 75.0 and r["resumen"]["mediana"] == 75.0
    assert (r["resumen"]["maxima"], r["resumen"]["minima"]) == (100.0, 50.0)
    assert (r["resumen"]["aprobados"], r["resumen"]["reprobados"]) == (1, 1)
    assert [x["nota"] for x in r["ranking"]] == [100.0, 50.0]
    assert r["histograma"][9]["cantidad"] == 1 and r["histograma"][5]["cantidad"] == 1
    assert sum(t["total"] for t in r["temas"]) == 140  # 70 preguntas x 2 intentos
    solo = client.get(f"/api/docente/reportes/examen/{CODIGO}?seccion=11-1", headers=hd).json()
    assert solo["resumen"]["enviados"] == 1 and solo["resumen"]["promedio"] == 100.0


def test_reporte_ignora_anulados_y_cuenta_los_sin_enviar(client):
    hd = _docente(client)
    _dos_intentos(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client, "luis.mora", "LUI5678"))  # ya enviado: 409
    iid = next(i["id"] for i in client.get("/api/docente/intentos", headers=hd).json()["intentos"] if i["estudiante_id"] == 2)
    client.post(f"/api/docente/intentos/{iid}/anular", headers=hd, json={})
    r = client.get(f"/api/docente/reportes/examen/{CODIGO}", headers=hd).json()
    assert r["resumen"]["enviados"] == 1 and r["resumen"]["promedio"] == 100.0


def test_preguntas_criticas(client):
    hd = _docente(client)
    _dos_intentos(client)
    r = client.get(f"/api/docente/reportes/preguntas-criticas/{CODIGO}", headers=hd).json()
    assert r["intentos"] == 2 and len(r["preguntas"]) == 70
    errores = [q["porcentaje_error"] for q in r["preguntas"]]
    assert errores == sorted(errores, reverse=True)
    assert sum(q["errores"] for q in r["preguntas"]) == 35  # luis falló 35 y ana ninguna
    peor = r["preguntas"][0]
    assert peor["porcentaje_error"] == 50.0 and peor["distractor"]["veces"] == 1
    assert peor["distractor"]["texto"] != peor["correcta"]


def test_boleta_del_estudiante(client):
    hd = _docente(client)
    _dos_intentos(client)
    materia = next(m for m in client.get("/api/docente/materias", headers=hd).json()["materias"]
                   if m["seccion"] == "11-1" and m["periodo"] == 1)["id"]
    completa = dict(trabajo_cotidiano=80, tareas=80, prueba01=80, prueba02=80, proyecto=80, asistencia=80)
    client.put("/api/docente/notas", headers=hd, json={"materia_id": materia, "notas": [{"estudiante_id": 1, **completa}]})

    b = client.get("/api/docente/reportes/boleta/1", headers=hd).json()
    assert b["estudiante"]["username"] == "ana.perez" and b["estudiante"]["seccion"] == "11-1"
    assert len(b["examenes"]) == 1 and b["examenes"][0]["nota"] == 100.0 and b["examenes"][0]["aprobado"]
    assert sum(t["aciertos"] for t in b["examenes"][0]["temas"]) == 70
    assert len(b["notas"]) == 1 and b["notas"][0]["nota_final"] == 80.0
    assert client.get("/api/docente/reportes/boleta/999", headers=hd).status_code == 404


def test_reporte_de_seccion(client):
    hd = _docente(client)
    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET seccion = '11-1'")
        conn.commit()
    materia = next(m for m in client.get("/api/docente/materias", headers=hd).json()["materias"]
                   if m["seccion"] == "11-1" and m["periodo"] == 1)["id"]
    cien = dict(trabajo_cotidiano=100, tareas=100, prueba01=100, prueba02=100, proyecto=100, asistencia=100)
    client.put("/api/docente/notas", headers=hd, json={"materia_id": materia, "notas": [
        {"estudiante_id": 1, **cien}, {"estudiante_id": 2, "prueba01": 10}]})
    r = client.get("/api/docente/reportes/seccion?seccion=11-1&periodo=1", headers=hd).json()
    assert len(r["materias"]) == 3 and len(r["estudiantes"]) == 2
    prom = next(p for p in r["promedios"] if p["materia_id"] == materia)
    assert prom["promedio"] == 100.0 and prom["completas"] == 1 and prom["aprobados"] == 1
    assert client.get("/api/docente/reportes/seccion?seccion=99-9&periodo=1", headers=hd).status_code == 404


def test_exportaciones_excel(client):
    hd = _docente(client)
    _dos_intentos(client)
    for ruta in (f"/api/docente/reportes/examen/{CODIGO}/excel", "/api/docente/reportes/boleta/1/excel",
                 "/api/docente/reportes/seccion/excel?seccion=11-1&periodo=1"):
        r = client.get(ruta, headers=hd)
        assert r.status_code == 200, ruta
        assert "spreadsheetml" in r.headers["content-type"]
        assert r.content[:2] == b"PK"  # un .xlsx es un zip
