import io

from openpyxl import Workbook

from backend import database
from tests.test_actividades import _crear, _preparar
from tests.test_docente import _docente, _materia


def _ajuste(client, hd, **valores):
    assert client.put("/api/docente/ajustes", headers=hd, json={"ajustes": valores}).status_code == 200


def test_ficha_observaciones_y_permisos(client):
    hd, mid = _preparar(client)
    assert client.get("/api/docente/estudiantes/1/ficha").status_code == 401
    assert client.get("/api/docente/estudiantes/99/ficha", headers=hd).status_code == 404

    r = client.put("/api/docente/estudiantes/1/ficha", headers=hd, json={
        "telefono": "8888-0000", "encargado_nombre": "PEREZ ROJAS MARTA", "encargado_cedula": "1-1111-1111",
        "encargado_telefono": "7000-1111", "direccion": "La Rita", "adecuacion": True, "adecuacion_detalle": "Acceso"})
    assert r.status_code == 200
    ficha = client.get("/api/docente/estudiantes/1/ficha", headers=hd).json()
    e = ficha["estudiante"]
    assert e["encargado_nombre"] == "PEREZ ROJAS MARTA" and e["adecuacion"] is True and e["telefono"] == "8888-0000"
    assert len(ficha["materias"]) == 6 and ficha["observaciones"] == []

    mala = {"fecha": "2026-03-02", "tipo": "inventado", "texto": "x"}
    assert client.post("/api/docente/estudiantes/1/observaciones", headers=hd, json=mala).status_code == 400
    assert client.post("/api/docente/estudiantes/1/observaciones", headers=hd, json={**mala, "tipo": "logro", "fecha": "ayer"}).status_code == 400
    assert client.post("/api/docente/estudiantes/1/observaciones", headers=hd, json={**mala, "tipo": "logro", "texto": ""}).status_code == 422
    ok = client.post("/api/docente/estudiantes/1/observaciones", headers=hd,
                     json={"fecha": "2026-03-02", "tipo": "familia", "texto": "Llamada a la madre", "materia_id": mid})
    assert ok.status_code == 200
    obs = client.get("/api/docente/estudiantes/1/ficha", headers=hd).json()["observaciones"]
    assert obs[0]["texto"] == "Llamada a la madre" and obs[0]["materia"]
    assert client.delete(f"/api/docente/observaciones/{ok.json()['id']}", headers=hd).status_code == 200
    assert client.delete(f"/api/docente/observaciones/{ok.json()['id']}", headers=hd).status_code == 404


def _lista_alumnos():
    libro = Workbook()
    hoja = libro.active
    hoja.title = "11-1"
    hoja.append([None, None, "11-1"])
    hoja.append([None, None, "DATOS DEL ESTUDIANTE"])
    hoja.append([])
    hoja.append([None, None, "Grupo", "Cédula", "Primer apellido", "Teléfono estudiante", "Apellidos   /  Nombre del encargado",
                 "Cédula del encargado", "Teléfono 1 de contacto", "Teléfono 2 de contacto", "Dirección Domicilio", "ADECUACIÓN", "Observaciones"])
    hoja.append([None, None, "11-1", "1-0234-0567", "PEREZ", "8999-1234", "SOTO RUIZ ELENA", "2-2222-2222", "7111-2222", None, "Pococí", "Acceso curricular", None])
    hoja.append([None, None, "11-1", "7-0344-0226", "MORA", None, "RUIZ LUIS", "3-3333-3333", 7222.0, None, "Guápiles", "NO posee", None])
    hoja.append([None, None, "11-1", "9-9999-9999", "NADIE", None, "X", None, None, None, None, None, None])
    otra = libro.create_sheet("Correos")
    otra.append(["Cédula", "Correo"])
    salida = io.BytesIO()
    libro.save(salida)
    return salida.getvalue()


def test_importar_encargados_desde_lista_alumnos(client):
    hd, _ = _preparar(client)
    r = client.post("/api/docente/estudiantes/importar-encargados", headers=hd, content=_lista_alumnos())
    assert r.status_code == 200, r.text
    assert r.json()["actualizados"] == 2 and r.json()["sin_pareja"] == ["9-9999-9999"]
    ana = client.get("/api/docente/estudiantes/1/ficha", headers=hd).json()["estudiante"]
    luis = client.get("/api/docente/estudiantes/2/ficha", headers=hd).json()["estudiante"]
    assert ana["encargado_nombre"] == "SOTO RUIZ ELENA" and ana["telefono"] == "8999-1234" and ana["adecuacion"] is True
    assert ana["adecuacion_detalle"] == "Acceso curricular"
    assert luis["encargado_telefono"] == "7222" and luis["adecuacion"] is False       # «NO posee» no es adecuación
    assert client.post("/api/docente/estudiantes/importar-encargados", headers=hd, content=b"no es excel").status_code == 400


def test_alertas_de_riesgo_asistencia_pendientes_y_examenes(client):
    hd, mid = _preparar(client)
    _ajuste(client, hd, periodo_actual="1", umbral_ausencias="20")
    assert client.get("/api/docente/alertas", headers=hd).json()["estudiantes"] == []       # sin datos, sin alertas

    client.put("/api/docente/notas", headers=hd, json={"materia_id": mid, "notas": [
        {"estudiante_id": 1, "trabajo_cotidiano": 100, "tareas": 90, "prueba01": 95},
        {"estudiante_id": 2, "trabajo_cotidiano": 30, "tareas": 20, "prueba01": 40}]})
    aid = _crear(client, hd, mid, criterios=[], puntos_max=10).json()["id"]
    client.put(f"/api/docente/actividades/{aid}/calificaciones", headers=hd, json={"calificaciones": [
        {"estudiante_id": 1, "estado": "entregado", "puntos": 10}, {"estudiante_id": 2, "estado": "sin_entrega"}]})
    for dia in ("2026-03-02", "2026-03-03", "2026-03-04", "2026-03-05"):
        client.put("/api/docente/asistencia/sesion", headers=hd, json={
            "materia_id": mid, "fecha": dia, "lecciones": 2,
            "registros": [{"estudiante_id": 1, "estado": "P"}, {"estudiante_id": 2, "estado": "A" if dia < "2026-03-04" else "P"}]})
    client.put("/api/docente/examenes/SGC01", headers=hd, json={"materia_id": mid, "componente": "prueba02"})

    d = client.get("/api/docente/alertas", headers=hd).json()
    assert d["periodo"] == 1
    por_id = {e["estudiante_id"]: {a["tipo"] for a in e["alertas"]} for e in d["estudiantes"]}
    assert por_id[2] >= {"riesgo", "asistencia", "pendientes", "examen"}
    assert 1 in por_id and por_id[1] == {"examen"}              # Ana va bien; solo le falta el examen vinculado
    assert d["estudiantes"][0]["estudiante_id"] == 2             # el de más riesgo, primero
    assert client.get("/api/docente/alertas?seccion=11-2", headers=hd).json()["estudiantes"] == []

    # la ficha trae solo las alertas del estudiante
    f = client.get("/api/docente/estudiantes/2/ficha", headers=hd).json()
    assert {a["tipo"] for a in f["alertas"]} >= {"riesgo", "asistencia"}

    # validación de los nuevos ajustes
    assert client.put("/api/docente/ajustes", headers=hd, json={"ajustes": {"periodo_actual": "9"}}).status_code == 400
    assert client.put("/api/docente/ajustes", headers=hd, json={"ajustes": {"umbral_ausencias": "0"}}).status_code == 400


def test_cierre_del_curso_archiva_y_deja_limpio(client, tmp_path, monkeypatch):
    monkeypatch.setattr(database, "RESPALDOS_DIR", tmp_path / "respaldos")
    hd, mid = _preparar(client)
    client.put("/api/docente/notas", headers=hd, json={"materia_id": mid, "notas": [
        {"estudiante_id": 1, "trabajo_cotidiano": 100, "tareas": 100, "prueba01": 100, "prueba02": 100, "proyecto": 100, "asistencia": 100}]})
    client.put("/api/docente/estudiantes/1/ficha", headers=hd, json={"telefono": "1234"})

    assert client.post("/api/docente/cierre", headers=hd, json={"confirmacion": "no", "nuevo_curso": "2027"}).status_code == 400
    assert client.post("/api/docente/cierre", headers=hd, json={"confirmacion": "CERRAR", "nuevo_curso": "2026"}).status_code == 400
    assert client.post("/api/docente/cierre", json={"confirmacion": "CERRAR", "nuevo_curso": "2027"}).status_code == 401
    assert (tmp_path / "respaldos").exists() is False                 # nada se tocó con los intentos fallidos

    r = client.post("/api/docente/cierre", headers=hd,
                    json={"confirmacion": "cerrar", "nuevo_curso": "2027", "desactivar_secciones": ["11-1"]})
    assert r.status_code == 200, r.text
    assert r.json()["desactivados"] == 2
    nombres = client.get("/api/docente/cierre/archivos", headers=hd).json()["archivos"]
    assert len(nombres) == 2 and any(n.endswith(".sqlite") for n in nombres) and any(n.endswith("_notas.xlsx") for n in nombres)

    # el archivo conserva todo lo del curso cerrado
    import sqlite3
    copia = sqlite3.connect(tmp_path / "respaldos" / r.json()["copia"])
    assert copia.execute("SELECT COUNT(*) FROM notas").fetchone()[0] == 1
    copia.close()

    # y la base queda limpia, con el nuevo curso y los estudiantes conservados
    assert client.get(f"/api/docente/notas?materia_id={mid}", headers=hd).json()["resumen"]["completas"] == 0
    assert client.get("/api/docente/ajustes", headers=hd).json()["ajustes"]["curso_lectivo"] == "2027"
    assert client.get("/api/docente/ajustes", headers=hd).json()["ajustes"]["periodo_actual"] == "1"
    with database.get_db_context() as conn:
        assert conn.execute("SELECT COUNT(*) FROM estudiantes").fetchone()[0] == 2
        assert conn.execute("SELECT COUNT(*) FROM estudiantes WHERE activo = 1").fetchone()[0] == 0
        assert conn.execute("SELECT telefono FROM estudiantes WHERE id = 1").fetchone()[0] == "1234"
