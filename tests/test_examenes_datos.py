import json
from collections import Counter

import pytest

from backend import barajado, database
from backend.routes import examenes
from tests.conftest import login

CODIGOS = examenes.load_codigos()
NUEVO = "ADM02"


def _examen(codigo):
    return examenes.load_examen_data(CODIGOS[codigo]["archivo"])["examen"]


@pytest.mark.parametrize("codigo", sorted(CODIGOS))
def test_estructura_de_cada_examen(codigo):
    ex = _examen(codigo)
    preguntas = ex["preguntas"]
    assert ex["total_preguntas"] == len(preguntas)
    assert [p["numero"] for p in preguntas] == list(range(1, len(preguntas) + 1))
    for p in preguntas:
        letras = list(p["opciones"])
        assert letras == list("abcd"[: len(letras)]) and len(letras) >= 3
        assert p["respuesta_correcta"] in letras
        assert len(set(p["opciones"].values())) == len(letras), f"{codigo} #{p['numero']}: opciones repetidas"
    assert len({p["pregunta"] for p in preguntas}) == len(preguntas), f"{codigo}: preguntas repetidas"


def test_examen_adm02_cobertura_y_equilibrio():
    ex = _examen(NUEVO)
    preguntas = ex["preguntas"]
    assert len(preguntas) == 60 and CODIGOS[NUEVO]["duracion_minutos"] == 80
    assert all(len(p["opciones"]) == 4 for p in preguntas)
    # reparto por horas de clase (8 h = 5 preguntas; 16 h = 10 preguntas)
    por_tema = Counter(p["tema"] for p in preguntas)
    assert sorted(por_tema.values()) == [5, 5, 5, 5, 10, 10, 10, 10]
    # la respuesta correcta no debe delatarse por su posición ni por su longitud
    posiciones = Counter(p["respuesta_correcta"] for p in preguntas)
    assert all(12 <= posiciones[l] <= 18 for l in "abcd"), posiciones
    mas_larga = sum(
        1 for p in preguntas
        if len(p["opciones"][p["respuesta_correcta"]]) > max(
            len(v) for k, v in p["opciones"].items() if k != p["respuesta_correcta"])
    )
    assert mas_larga <= 0.35 * len(preguntas), mas_larga


def test_examen_gcs02_cobertura_y_equilibrio():
    ex = _examen("GCS02")
    preguntas = ex["preguntas"]
    assert len(preguntas) == 60 and CODIGOS["GCS02"]["duracion_minutos"] == 80
    assert all(len(p["opciones"]) == 4 for p in preguntas)
    # puntos de selección única de la tabla de especificaciones x 3
    por_tema = Counter(p["tema"].split(" · ")[0] for p in preguntas)
    assert sorted(por_tema.values()) == [3, 3, 6, 6, 6, 6, 6, 12, 12]
    assert sum(1 for p in preguntas if "origen" in p) == 20
    posiciones = Counter(p["respuesta_correcta"] for p in preguntas)
    assert all(12 <= posiciones[l] <= 18 for l in "abcd"), posiciones
    mas_larga = sum(
        1 for p in preguntas
        if len(p["opciones"][p["respuesta_correcta"]]) > max(
            len(v) for k, v in p["opciones"].items() if k != p["respuesta_correcta"])
    )
    assert mas_larga <= 0.35 * len(preguntas), mas_larga


def test_examen_emp02_cobertura_y_equilibrio():
    ex = _examen("EMP02")
    preguntas = ex["preguntas"]
    assert len(preguntas) == 60 and CODIGOS["EMP02"]["duracion_minutos"] == 80
    assert all(len(p["opciones"]) == 4 for p in preguntas)
    # puntos de selección única de la tabla de especificaciones (4, 5, 5, 6) x 3
    por_tema = Counter(p["tema"].split(" · ")[0] for p in preguntas)
    assert sorted(por_tema.values()) == [12, 15, 15, 18]
    assert sum(1 for p in preguntas if "origen" in p) == 19
    posiciones = Counter(p["respuesta_correcta"] for p in preguntas)
    assert all(12 <= posiciones[l] <= 18 for l in "abcd"), posiciones
    mas_larga = sum(
        1 for p in preguntas
        if len(p["opciones"][p["respuesta_correcta"]]) > max(
            len(v) for k, v in p["opciones"].items() if k != p["respuesta_correcta"])
    )
    assert mas_larga <= 0.35 * len(preguntas), mas_larga


def test_barajado_con_cuatro_opciones_conserva_la_correcta():
    for p in barajado.barajar(_examen(NUEVO)["preguntas"], 12345):
        assert set(p["opciones"]) == set("abcd")
        original = _examen(NUEVO)["preguntas"][p["numero"] - 1]
        mostrada = barajado.letra_correcta_mostrada(p)
        assert p["opciones"][mostrada] == original["opciones"][original["respuesta_correcta"]]


def test_flujo_completo_con_examen_de_cuatro_opciones(client):
    h = login(client)
    ex = client.post(f"/api/examen/{NUEVO}/iniciar", headers=h).json()["examen"]
    assert len(ex["preguntas"]) == 60 and "respuesta_correcta" not in json.dumps(ex)
    assert all(set(p["opciones"]) == set("abcd") for p in ex["preguntas"])

    with database.get_db_context() as conn:
        semilla = conn.execute("SELECT semilla FROM intentos").fetchone()[0]
    original = _examen(NUEVO)["preguntas"]
    barajadas = barajado.barajar(original, semilla)
    respuestas = {str(p["numero"]): barajado.letra_correcta_mostrada(p) for p in barajadas[:45]}
    # una respuesta con letra inexistente (e) se descarta
    respuestas[str(barajadas[50]["numero"])] = "e"
    assert client.post(f"/api/examen/{NUEVO}/enviar", headers=h, json={"respuestas": respuestas}).status_code == 200

    token = client.post("/api/verificar-docente", json={"password": "docente2026"}).json()["token"]
    i = client.get("/api/docente/intentos", headers={"Authorization": f"Bearer {token}"}).json()["intentos"][0]
    assert (i["puntuacion"], i["total"]) == (45, 60)


def test_adm02_incluye_20_preguntas_del_cuestionario_sin_exponer_su_origen(client):
    preguntas = _examen(NUEVO)["preguntas"]
    assert sum(1 for p in preguntas if "origen" in p) == 20
    h = login(client)
    respuesta = client.post(f"/api/examen/{NUEVO}/iniciar", headers=h).text
    assert "origen" not in respuesta and "Cuestionario" not in respuesta
