import hashlib

from backend import barajado, database
from tests.conftest import login


def test_hash_bcrypt_y_verificacion():
    h = database.hash_password("ABC1234")
    assert h.startswith("$2") and not database.is_legacy_hash(h)
    assert database.verify_password("ABC1234", h)
    assert not database.verify_password("otra", h)


def test_hash_legacy_se_migra_a_bcrypt_al_iniciar_sesion(client):
    legacy = hashlib.sha256(b"ANA1234").hexdigest()
    with database.get_db_context() as conn:
        conn.execute("UPDATE estudiantes SET password_hash = ? WHERE id = 1", (legacy,))
        conn.commit()
    assert client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).json()["ok"]
    with database.get_db_context() as conn:
        nuevo = conn.execute("SELECT password_hash FROM estudiantes WHERE id = 1").fetchone()[0]
    assert nuevo.startswith("$2")
    assert client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).json()["ok"]


def test_login_se_bloquea_tras_cinco_fallos(client):
    for _ in range(5):
        assert client.post("/api/login", json={"username": "ana.perez", "password": "mal"}).json()["ok"] is False
    assert client.post("/api/login", json={"username": "ana.perez", "password": "ANA1234"}).status_code == 429
    # otro usuario no se ve afectado
    assert client.post("/api/login", json={"username": "luis.mora", "password": "LUI5678"}).json()["ok"]


def test_docente_se_bloquea_tras_diez_fallos(client):
    for _ in range(10):
        client.post("/api/verificar-docente", json={"password": "mala"})
    assert client.post("/api/verificar-docente", json={"password": "docente2026"}).status_code == 429


def test_barajado_es_determinista_y_conserva_la_respuesta_correcta():
    preguntas = [
        {"numero": i, "tema": "T1" if i < 5 else "T2", "pregunta": "?",
         "opciones": {"a": "A", "b": "B", "c": "C"}, "respuesta_correcta": "b"}
        for i in range(10)
    ]
    x, y = barajado.barajar(preguntas, 42), barajado.barajar(preguntas, 42)
    assert x == y
    assert [p["tema"] for p in x] == sorted(p["tema"] for p in x)  # temas en su orden
    for p in x:
        assert p["opciones"][barajado.letra_correcta_mostrada(p)] == "B"


def _entrar_docente(client, clave="docente2026"):
    r = client.post("/api/verificar-docente", json={"password": clave}).json()
    return {"Authorization": f"Bearer {r['token']}"} if r["ok"] else None


def test_clave_de_fabrica_del_docente_se_detecta_y_se_cambia(client):
    hd = _entrar_docente(client)
    assert client.get("/api/docente/ajustes", headers=hd).json()["clave_de_fabrica"] is True

    cambiar = lambda actual, nueva: client.post("/api/docente/cambiar-password", headers=hd, json={"actual": actual, "nueva": nueva})
    assert cambiar("incorrecta", "NuevaClave2026").status_code == 400          # la actual debe ser correcta
    assert cambiar("docente2026", "corta").status_code == 400                   # mínimo 8 caracteres
    assert cambiar("docente2026", "docente2026").status_code == 400             # no puede seguir siendo la de fábrica
    assert cambiar("docente2026", "NuevaClave2026").status_code == 200

    # la nueva entra, la de fábrica ya no, y la base guarda un bcrypt (no la clave ni el SHA-256 público)
    assert _entrar_docente(client, "docente2026") is None
    hd = _entrar_docente(client, "NuevaClave2026")
    assert hd is not None
    d = client.get("/api/docente/ajustes", headers=hd).json()
    assert d["clave_de_fabrica"] is False and "docente_password_hash" not in d["ajustes"]
    with database.get_db_context() as conn:
        guardado = conn.execute("SELECT valor FROM ajustes WHERE clave = 'docente_password_hash'").fetchone()[0]
    assert guardado.startswith("$2") and "NuevaClave2026" not in guardado
    assert client.post("/api/docente/cambiar-password", json={"actual": "x", "nueva": "OtraClave2026"}).status_code == 401
