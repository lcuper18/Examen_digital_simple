from datetime import date

from backend import database
from tests.conftest import login
from tests.test_docente import CODIGO, _docente, _materia


def test_ponderaciones_por_materia_deben_sumar_100(client):
    hd = _docente(client)
    mid = _materia(client, hd)
    pesos = {"trabajo_cotidiano": 20, "tareas": 10, "prueba01": 25, "prueba02": 25, "proyecto": 15, "asistencia": 5}

    r = client.put(f"/api/docente/materias/{mid}/ponderaciones", headers=hd, json={"ponderaciones": {**pesos, "tareas": 20}})
    assert r.status_code == 400 and "100" in r.json()["detail"]
    assert client.put(f"/api/docente/materias/{mid}/ponderaciones", headers=hd,
                      json={"ponderaciones": {"tareas": 100}}).status_code == 400
    assert client.put(f"/api/docente/materias/{mid}/ponderaciones", headers=hd,
                      json={"ponderaciones": pesos}).status_code == 200

    completa = dict(trabajo_cotidiano=100, tareas=0, prueba01=0, prueba02=0, proyecto=0, asistencia=0)
    client.put("/api/docente/notas", headers=hd, json={"materia_id": mid, "notas": [{"estudiante_id": 1, **completa}]})
    data = client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()
    assert data["ponderaciones"]["prueba01"] == 25
    assert next(n for n in data["notas"] if n["estudiante_id"] == 1)["nota_final"] == 20  # TC pesa 20
    # otra materia conserva los pesos por defecto
    otra = next(m for m in client.get("/api/docente/materias", headers=hd).json()["materias"]
                if m["id"] != mid and m["seccion"] == "11-1")
    assert otra["ponderaciones"]["trabajo_cotidiano"] == 25


def test_ajustes_se_guardan_y_nota_minima_se_aplica(client):
    hd = _docente(client)
    assert client.get("/api/docente/ajustes").status_code == 401
    assert client.get("/api/config").json()["institucion"] == "CTP Las Palmitas"  # público

    assert client.put("/api/docente/ajustes", headers=hd, json={"ajustes": {"inventado": "x"}}).status_code == 400
    assert client.put("/api/docente/ajustes", headers=hd, json={"ajustes": {"nota_minima": "150"}}).status_code == 400
    assert client.put("/api/docente/ajustes", headers=hd, json={"ajustes": {"institucion": " "}}).status_code == 400
    r = client.put("/api/docente/ajustes", headers=hd, json={"ajustes": {"institucion": "CTP Prueba", "nota_minima": "65"}})
    assert r.status_code == 200
    assert client.get("/api/config").json()["institucion"] == "CTP Prueba"
    assert client.get("/api/docente/materias", headers=hd).json()["nota_minima"] == 65


def test_importar_examen_vinculado_a_materia(client):
    hd = _docente(client)
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}})
    mid = _materia(client, hd)

    # sin vínculo no hay nada que importar
    assert client.post("/api/docente/notas/importar-prueba", headers=hd, json={"materia_id": mid}).status_code == 400
    # componente inválido o materia sin componente
    assert client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"materia_id": mid}).status_code == 400
    assert client.put(f"/api/docente/examenes/{CODIGO}", headers=hd,
                      json={"materia_id": mid, "componente": "tareas"}).status_code == 400
    assert client.put(f"/api/docente/examenes/{CODIGO}", headers=hd,
                      json={"materia_id": mid, "componente": "prueba02"}).status_code == 200
    listado = client.get("/api/docente/examenes", headers=hd).json()["examenes"]
    assert next(e for e in listado if e["codigo"] == CODIGO)["componente"] == "prueba02"

    r = client.post("/api/docente/notas/importar-prueba", headers=hd, json={"materia_id": mid})
    assert r.json()["importadas"] == 1 and r.json()["examenes"] == [CODIGO]
    notas = client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()["notas"]
    assert next(n for n in notas if n["estudiante_id"] == 1)["prueba02"] == 0


def test_respaldo_diario_una_vez_y_conserva_los_ultimos(client, tmp_path):
    destino = tmp_path / "respaldos"
    destino.mkdir()
    for dia in ("2025-01-01", "2025-01-02", "2025-01-03"):
        (destino / f"examen_db_{dia}.sqlite").write_bytes(b"x")

    archivo = database.respaldar(destino, mantener=2)
    assert archivo == destino / f"examen_db_{date.today().isoformat()}.sqlite"
    assert sorted(p.name for p in destino.glob("*.sqlite")) == ["examen_db_2025-01-03.sqlite", archivo.name]
    assert database.respaldar(destino, mantener=2) is None  # ya existe el de hoy

    copia = database.sqlite3.connect(archivo)
    assert copia.execute("SELECT COUNT(*) FROM estudiantes").fetchone()[0] == 2
    copia.close()


def test_primeros_pasos_se_marcan_solos(client):
    hd = _docente(client)
    assert client.get("/api/docente/primeros-pasos").status_code == 401
    hechos = lambda: {p["id"]: p["hecho"] for p in client.get("/api/docente/primeros-pasos", headers=hd).json()["pasos"]}
    assert not any(hechos().values())

    mid = _materia(client, hd)
    client.put("/api/docente/ajustes", headers=hd, json={"ajustes": {"institucion": "CTP Prueba"}})
    client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"materia_id": mid, "componente": "prueba01"})
    client.put("/api/docente/asistencia/sesion", headers=hd, json={
        "materia_id": mid, "fecha": "2026-03-02", "lecciones": 1, "registros": [{"estudiante_id": 1, "estado": "P"}]})
    client.put(f"/api/docente/materias/{mid}/publicacion", headers=hd, json={"publicado": True})
    h = hechos()
    assert h["institucion"] and h["vinculos"] and h["lista"] and h["publicar"]
    assert not h["encargados"] and not h["actividad"]


def test_config_publica_informa_la_version(client):
    from backend.version import VERSION

    d = client.get("/api/config").json()
    assert d["version"] == VERSION and VERSION.count(".") == 2
