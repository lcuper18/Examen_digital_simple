from datetime import timedelta

from backend import barajado, database
from backend.routes import examenes
from tests.conftest import login

CODIGO = "SGC01"


def _correctas(client):
    """Letra correcta tal como la ve el estudiante 1 (con su barajado)."""
    from backend.routes.examenes import _get_examen
    _, ex = _get_examen(CODIGO)
    with database.get_db_context() as conn:
        semilla = conn.execute("SELECT semilla FROM intentos WHERE estudiante_id = 1").fetchone()[0]
    return {
        str(p["numero"]): barajado.letra_correcta_mostrada(p)
        for p in barajado.barajar(ex["preguntas"], semilla)
    }


def test_login_devuelve_token_y_rechaza_malas_credenciales(client):
    assert client.post("/api/login", json={"username": "ana.perez", "password": "x"}).json()["ok"] is False
    assert login(client)["Authorization"].startswith("Bearer ")


def test_examen_requiere_sesion(client):
    assert client.post(f"/api/examen/{CODIGO}/iniciar").status_code == 401
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers={"Authorization": "Bearer x.y"}).status_code == 401


def test_examen_no_expone_respuesta_correcta(client):
    r = client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client))
    assert r.status_code == 200
    assert "respuesta_correcta" not in r.text
    assert r.json()["examen"]["segundos_restantes"] > 0


def test_codigo_inexistente(client):
    assert client.post("/api/examen/NOPE/iniciar", headers=login(client)).status_code == 404


def test_califica_en_servidor_e_impide_segundo_envio(client):
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    correctas = _correctas(client)
    mitad = dict(list(correctas.items())[: len(correctas) // 2])
    r = client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": mitad})
    assert r.status_code == 200
    assert "puntuacion" not in r.text
    assert client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": mitad}).status_code == 409
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 409

    dt = client.post("/api/verificar-docente", json={"password": "docente2026"}).json()
    hd = {"Authorization": f"Bearer {dt['token']}"}
    intentos = client.get("/api/docente/intentos", headers=hd).json()["intentos"]
    assert intentos[0]["puntuacion"] == len(mitad)
    detalle = client.get(f"/api/docente/intentos/{intentos[0]['id']}", headers=hd).json()["intento"]
    assert detalle["respuestas_correctas"] == correctas


def test_envio_sin_iniciar(client):
    assert client.post(f"/api/examen/{CODIGO}/enviar", headers=login(client), json={"respuestas": {}}).status_code == 404


def test_tiempo_agotado(client, monkeypatch):
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    real_now = examenes._now
    monkeypatch.setattr(examenes, "_now", lambda: real_now() + timedelta(hours=5))
    assert client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}}).status_code == 403
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 403


def test_recargar_no_reinicia_el_tiempo(client):
    h = login(client)
    a = client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).json()["examen"]["segundos_restantes"]
    b = client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).json()["examen"]["segundos_restantes"]
    assert b <= a


def test_rutas_docente_exigen_token_de_docente(client):
    assert client.get("/api/docente/intentos").status_code == 401
    assert client.get("/api/docente/intentos", headers=login(client)).status_code == 401
    assert client.post("/api/verificar-docente", json={"password": "mala"}).json()["ok"] is False


def test_incidencias_se_guardan(client):
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}, "incidencias": 3})
    dt = client.post("/api/verificar-docente", json={"password": "docente2026"}).json()
    lista = client.get("/api/docente/intentos", headers={"Authorization": f"Bearer {dt['token']}"}).json()
    assert lista["intentos"][0]["incidencias"] == 3


def test_cada_estudiante_ve_un_orden_distinto(client):
    a = client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client)).json()["examen"]["preguntas"]
    b = client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client, "luis.mora", "LUI5678")).json()["examen"]["preguntas"]
    assert sorted(p["numero"] for p in a) == sorted(p["numero"] for p in b)
    assert [p["numero"] for p in a] != [p["numero"] for p in b]
