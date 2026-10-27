import pytest
from fastapi.testclient import TestClient

from backend import database
from backend.main import app


@pytest.fixture()
def client(tmp_path, monkeypatch):
    monkeypatch.setattr(database, "DATABASE_PATH", tmp_path / "test.sqlite")
    database.init_db()
    with database.get_db_context() as conn:
        conn.execute("DELETE FROM estudiantes")
        for i, (user, pwd) in enumerate([("ana.perez", "ANA1234"), ("luis.mora", "LUI5678")], 1):
            conn.execute(
                "INSERT INTO estudiantes (id, cedula, nombre, apellido1, apellido2, seccion, "
                "username, password_hash) VALUES (?, ?, 'N', 'A', '', '12-1', ?, ?)",
                (i, f"c{i}", user, database.hash_password(pwd)),
            )
        conn.commit()
    return TestClient(app)


def login(client, user="ana.perez", pwd="ANA1234"):
    r = client.post("/api/login", json={"username": user, "password": pwd})
    return {"Authorization": f"Bearer {r.json()['token']}"}
