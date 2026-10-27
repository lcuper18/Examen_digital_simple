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
