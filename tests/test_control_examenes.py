from datetime import timedelta

from backend import barajado, database
from backend.routes import examenes
from tests.conftest import login

CODIGO = "SGC01"


def _docente(client):
    token = client.post("/api/verificar-docente", json={"password": "docente2026"}).json()["token"]
    return {"Authorization": f"Bearer {token}"}


def _intento_id(client, hd):
    return client.get("/api/docente/intentos", headers=hd).json()["intentos"][0]["id"]


def _acciones(client, hd):
    return [e["accion"] for e in client.get("/api/docente/bitacora", headers=hd).json()["entradas"]]


def test_catalogo_de_examenes_requiere_docente_y_lista_codigos(client):
    assert client.get("/api/docente/examenes").status_code == 401
    lista = client.get("/api/docente/examenes", headers=_docente(client)).json()["examenes"]
    assert CODIGO in {e["codigo"] for e in lista}
    assert all(e["habilitado"] for e in lista)


def test_examen_deshabilitado_no_se_puede_iniciar_pero_el_abierto_continua(client):
    hd, h = _docente(client), login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)  # ana ya empezó
    client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"habilitado": False})
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client, "luis.mora", "LUI5678")).status_code == 403
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).status_code == 200  # retoma
    client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"habilitado": True})
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client, "luis.mora", "LUI5678")).status_code == 200


def test_restriccion_por_seccion_y_ventana(client):
    hd = _docente(client)
    client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"secciones": ["11-1"]})
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client, "luis.mora", "LUI5678")).status_code == 403
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client)).status_code == 200

    client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"desde": "2999-01-01T00:00:00Z"})
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client, "luis.mora", "LUI5678")).status_code == 403
    client.put(f"/api/docente/examenes/{CODIGO}", headers=hd, json={"hasta": "2000-01-01T00:00:00Z"})
    assert client.post(f"/api/examen/{CODIGO}/iniciar", headers=login(client, "luis.mora", "LUI5678")).status_code == 403

    malo = client.put(f"/api/docente/examenes/{CODIGO}", headers=hd,
                      json={"desde": "2030-01-02T00:00:00Z", "hasta": "2030-01-01T00:00:00Z"})
    assert malo.status_code == 400
    assert client.put("/api/docente/examenes/NOPE", headers=hd, json={}).status_code == 404


def test_autosave_guarda_y_se_recupera_al_retomar(client):
    h = login(client)
    ex = client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).json()["examen"]
    assert ex["respuestas_guardadas"] == {}
    n = str(ex["preguntas"][0]["numero"])
    r = client.put(f"/api/examen/{CODIGO}/progreso", headers=h,
                   json={"respuestas": {n: "b", "9999": "a", n + "x": "z"}, "incidencias": 2})
    assert r.status_code == 200 and r.json()["segundos_restantes"] > 0
    otra = client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).json()["examen"]
    assert otra["respuestas_guardadas"] == {n: "b"}  # solo las válidas


def test_tiempo_extra_se_refleja_en_el_cronometro(client):
    hd, h = _docente(client), login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    antes = client.put(f"/api/examen/{CODIGO}/progreso", headers=h, json={}).json()["segundos_restantes"]
    iid = _intento_id(client, hd)
    assert client.post(f"/api/docente/intentos/{iid}/tiempo-extra", headers=hd, json={"minutos": 15}).status_code == 200
    despues = client.put(f"/api/examen/{CODIGO}/progreso", headers=h, json={}).json()["segundos_restantes"]
    assert despues - antes >= 15 * 60 - 5
    assert client.post(f"/api/docente/intentos/{iid}/tiempo-extra", headers=hd, json={"minutos": 0}).status_code == 422
    assert "tiempo_extra" in _acciones(client, hd)


def test_tiempo_extra_permite_enviar_fuera_del_plazo_original(client, monkeypatch):
    hd, h = _docente(client), login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    iid = _intento_id(client, hd)
    client.post(f"/api/docente/intentos/{iid}/tiempo-extra", headers=hd, json={"minutos": 240})
    real = examenes._now
    monkeypatch.setattr(examenes, "_now", lambda: real() + timedelta(hours=3))  # duración base: 2 h
    assert client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}}).status_code == 200


def test_anular_y_restaurar_intento(client):
    hd, h = _docente(client), login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}})
    iid = _intento_id(client, hd)
    client.post(f"/api/docente/intentos/{iid}/anular", headers=hd, json={"anulado": True, "motivo": "copia"})
    assert client.get("/api/docente/intentos", headers=hd).json()["intentos"][0]["anulado"] == 1
    # un intento anulado no se importa a notas
    materia = next(m for m in client.get("/api/docente/materias", headers=hd).json()["materias"]
                   if m["seccion"] == "11-1" and m["periodo"] == 1)["id"]
    r = client.post("/api/docente/notas/importar-prueba", headers=hd,
                    json={"materia_id": materia, "componente": "prueba01", "codigo_examen": CODIGO})
    assert r.json()["importadas"] == 0
    client.post(f"/api/docente/intentos/{iid}/anular", headers=hd, json={"anulado": False})
    r = client.post("/api/docente/notas/importar-prueba", headers=hd,
                    json={"materia_id": materia, "componente": "prueba01", "codigo_examen": CODIGO})
    assert r.json()["importadas"] == 1
    assert {"anular_intento", "restaurar_intento"} <= set(_acciones(client, hd))


def test_anular_un_intento_abierto_impide_continuar(client):
    hd, h = _docente(client), login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    client.post(f"/api/docente/intentos/{_intento_id(client, hd)}/anular", headers=hd, json={})
    assert client.put(f"/api/examen/{CODIGO}/progreso", headers=h, json={}).status_code == 409
    assert client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}}).status_code == 409


def test_marcar_sospechoso(client):
    hd, h = _docente(client), login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    iid = _intento_id(client, hd)
    client.post(f"/api/docente/intentos/{iid}/sospechoso", headers=hd, json={"sospechoso": True, "nota": "mucho tiempo fuera"})
    i = client.get("/api/docente/intentos", headers=hd).json()["intentos"][0]
    assert i["sospechoso"] == 1 and i["nota_docente"] == "mucho tiempo fuera"


def test_cerrar_intento_abierto_califica_lo_guardado(client):
    hd, h = _docente(client), login(client)
    ex = client.post(f"/api/examen/{CODIGO}/iniciar", headers=h).json()["examen"]
    _, original = examenes._get_examen(CODIGO)
    with database.get_db_context() as conn:
        semilla = conn.execute("SELECT semilla FROM intentos").fetchone()[0]
    correctas = {str(p["numero"]): barajado.letra_correcta_mostrada(p)
                 for p in barajado.barajar(original["preguntas"], semilla)}
    tres = dict(list(correctas.items())[:3])
    client.put(f"/api/examen/{CODIGO}/progreso", headers=h, json={"respuestas": tres})
    iid = _intento_id(client, hd)
    r = client.post(f"/api/docente/intentos/{iid}/cerrar", headers=hd).json()
    assert r["puntuacion"] == 3 and r["total"] == len(ex["preguntas"])
    assert client.post(f"/api/docente/intentos/{iid}/cerrar", headers=hd).status_code == 409
    assert client.post(f"/api/examen/{CODIGO}/enviar", headers=h, json={"respuestas": {}}).status_code == 409
    assert client.post(f"/api/docente/intentos/{iid}/tiempo-extra", headers=hd, json={"minutos": 5}).status_code == 409


def test_acciones_del_docente_requieren_sesion_de_docente(client):
    h = login(client)
    client.post(f"/api/examen/{CODIGO}/iniciar", headers=h)
    for ruta in ("tiempo-extra", "anular", "sospechoso", "cerrar"):
        assert client.post(f"/api/docente/intentos/1/{ruta}", headers=h, json={"minutos": 5}).status_code == 401
