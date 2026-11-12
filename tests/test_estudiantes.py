from backend import database
from tests.conftest import login

CODIGO = "SGC01"


def _docente(client):
    token = client.post("/api/verificar-docente", json={"password": "docente2026"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def test_gestion_requiere_docente(client):
    assert client.get("/api/docente/estudiantes").status_code == 401
    assert client.get("/api/docente/estudiantes", headers=login(client)).status_code == 401
    assert client.get("/api/docente/bitacora").status_code == 401


def test_listar_filtra_por_seccion_y_busqueda(client):
    hd = _docente(client)
    todos = client.get("/api/docente/estudiantes", headers=hd).json()["estudiantes"]
    assert len(todos) == 2
    assert all("password_hash" not in e for e in todos)
    solo = client.get("/api/docente/estudiantes?seccion=11-2", headers=hd).json()["estudiantes"]
    assert [e["username"] for e in solo] == ["luis.mora"]
    assert len(client.get("/api/docente/estudiantes?q=ana", headers=hd).json()["estudiantes"]) == 1


def test_reiniciar_password_obliga_a_cambiarla(client):
    hd = _docente(client)
    r = client.post("/api/docente/estudiantes/1/reiniciar-password", headers=hd).json()
    temporal = r["password_temporal"]
    assert len(temporal) == 8

    # la clave anterior ya no sirve; la temporal sí, pero no deja entrar a los exámenes
    assert client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).json()["ok"] is False
    entrada = client.post("/api/login", json={"username": "ana.perez", "password": temporal}).json()
    assert entrada["ok"] and entrada["estudiante"]["debe_cambiar_password"] is True
    h = {"Authorization": f"Bearer {entrada['token']}"}
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 403

    # validaciones del cambio
    corta = client.post("/api/cambiar-password", headers=h, json={"password_actual": temporal, "password_nueva": "abc"})
    assert corta.status_code == 400
    igual = client.post("/api/cambiar-password", headers=h, json={"password_actual": temporal, "password_nueva": temporal})
    assert igual.status_code == 400
    mala = client.post("/api/cambiar-password", headers=h, json={"password_actual": "otra-cosa", "password_nueva": "NuevaClave1"})
    assert mala.status_code == 400

    ok = client.post("/api/cambiar-password", headers=h, json={"password_actual": temporal, "password_nueva": "NuevaClave1"})
    assert ok.status_code == 200
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 200
    assert client.post("/api/login", json={"username": "ana.perez", "password": "NuevaClave1"}).json()["ok"]


def test_desbloquear_login(client):
    hd = _docente(client)
    for _ in range(5):
        client.post("/api/login", json={"username": "ana.perez", "password": "mal"})
    assert client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).status_code == 429
    lista = client.get("/api/docente/estudiantes", headers=hd).json()["estudiantes"]
    assert next(e for e in lista if e["username"] == "ana.perez")["bloqueado"] is True
    client.post("/api/docente/estudiantes/1/desbloquear", headers=hd)
    assert client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).json()["ok"]


def test_desactivar_cuenta_bloquea_login_y_sesion_abierta(client):
    hd = _docente(client)
    h = login(client)
    client.patch("/api/docente/estudiantes/1", headers=hd, json={"activo": False})
    assert client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).json()["ok"] is False
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 401
    client.patch("/api/docente/estudiantes/1", headers=hd, json={"activo": True, "seccion": "11-2"})
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 200
    lista = client.get("/api/docente/estudiantes?seccion=11-2", headers=hd).json()["estudiantes"]
    assert {e["username"] for e in lista} == {"ana.perez", "luis.mora"}


def test_alta_baja_e_importacion(client):
    hd = _docente(client)
    nuevo = {"cedula": "9-9999-0001", "nombre": "Pedro", "apellido1": "Soto", "apellido2": "Lara", "seccion": "11-1"}
    creado = client.post("/api/docente/estudiantes", headers=hd, json=nuevo).json()
    assert creado["username"] == "pedro.soto"
    assert client.post("/api/docente/estudiantes", headers=hd, json=nuevo).status_code == 409
    entrada = client.post("/api/login", json={"username": "pedro.soto", "password": creado["password_temporal"]}).json()
    assert entrada["ok"] and entrada["estudiante"]["debe_cambiar_password"]
    assert client.delete(f"/api/docente/estudiantes/{creado['id']}", headers=hd).status_code == 200

    csv_texto = "cedula,nombre,apellido1,apellido2,seccion\n8-0000-0001,Rosa,Vega,Luna,11-2\nc1,Ana,Perez,,11-1\n"
    r = client.post("/api/docente/estudiantes/importar", headers=hd, json={"csv": csv_texto}).json()
    assert [c["username"] for c in r["creados"]] == ["rosa.vega"]
    assert r["omitidos"] == ["c1"]
    assert client.post("/api/docente/estudiantes/importar", headers=hd, json={"csv": "x,y\n1,2"}).status_code == 400


def test_no_se_elimina_estudiante_con_intentos(client):
    hd = _docente(client)
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    assert client.delete("/api/docente/estudiantes/1", headers=hd).status_code == 409


def test_reiniciar_seccion_y_bitacora(client):
    hd = _docente(client)
    r = client.post("/api/docente/estudiantes/reiniciar-seccion", headers=hd, json={"seccion": "11-2"}).json()
    assert len(r["credenciales"]) == 1
    assert client.post("/api/login", json={"username": "luis.mora", "password": r["credenciales"][0]["password_temporal"]}).json()["ok"]
    client.post("/api/docente/estudiantes/1/reiniciar-password", headers=hd)
    acciones = [e["accion"] for e in client.get("/api/docente/bitacora", headers=hd).json()["entradas"]]
    assert acciones[:2] == ["reiniciar_password", "reiniciar_seccion"]
    # la bitácora nunca guarda contraseñas
    assert all("temporal" not in (e["detalle"] or "").lower() for e in client.get("/api/docente/bitacora", headers=hd).json()["entradas"])


def test_resumen_del_tablero(client):
    hd = _docente(client)
    assert client.get("/api/docente/resumen").status_code == 401
    r0 = client.get("/api/docente/resumen", headers=hd).json()
    assert r0["estudiantes"]["total"] == 2 and r0["intentos"]["enviados"] == 0 and r0["alertas"] == []

    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.put(f"/api/examen/{CODIGO}/progreso", headers=h, json={"respuestas": {}, "incidencias": 4})
    client.post("/api/docente/estudiantes/2/reiniciar-password", headers=hd)
    r = client.get("/api/docente/resumen", headers=hd).json()
    assert r["intentos"]["en_curso"] == 1 and r["en_curso"][0]["incidencias"] == 4
    tipos = {a["tipo"] for a in r["alertas"]}
    assert {"salidas", "temporales"} <= tipos
    assert r["reciente"][0]["accion"] == "reiniciar_password"

    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}})
    r = client.get("/api/docente/resumen", headers=hd).json()
    assert r["intentos"]["enviados"] == 1 and r["intentos"]["promedio"] == 0.0 and r["en_curso"] == []


def test_exigir_cambio_de_clave_a_una_seccion_no_cambia_la_clave(client):
    hd = _docente(client)
    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET debe_cambiar_password = 0")
        conn.commit()
    r = client.post("/api/docente/estudiantes/exigir-cambio-seccion", headers=hd, json={"seccion": "11-1"})
    assert r.status_code == 200 and r.json()["estudiantes"] >= 1
    with database.get_db_context() as conn:
        marcados = conn.execute("SELECT seccion, debe_cambiar_password FROM estudiantes").fetchall()
    assert all((f["debe_cambiar_password"] == 1) == (f["seccion"] == "11-1") for f in marcados)
    # entra con la misma clave de siempre, pero se le pide crear una nueva
    d = client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).json()
    assert d["ok"] and d["estudiante"]["debe_cambiar_password"] is True
    assert client.post("/api/docente/estudiantes/exigir-cambio-seccion", json={"seccion": "11-1"}).status_code == 401
